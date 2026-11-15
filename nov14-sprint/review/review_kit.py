#!/usr/bin/env python3
"""Blinded review kit for one frozen TV decision packet.

PAPER ONLY. It copies files, writes a prompt and stores answers. It calls no
model, places no order, and the replay runner never reads anything here.
Standard library only (system python3 3.9). Run with /usr/bin/python3 -I.

  prepare PACKET.json BARS.jsonl     make review/<packet_id>/inputs/ with the two
                                     files and PROMPT.txt for either reviewer
  attach PACKET_ID --reviewer claude|astra --model MODEL --answer FILE [--note TEXT]
                                     check the answer and store it as RECORDED
  show PACKET_ID                     print what is stored, with its labels

An answer is only ever shown as "RECORDED", with the time it was captured, the
model named, and the packet file it was given. Preparing a new packet makes a
new folder with no answers in it, so an old answer can't stand in for a new run.
"""
import argparse
import datetime
import hashlib
import json
import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PROMPT_SRC = os.path.join(HERE, "REVIEW_PROMPT.md")
REVIEWERS = ("claude", "astra")
VERDICTS = ("agree", "challenge", "cannot_tell")
AUTHORITY = "advisory only; cannot authorize a fill"
KEYS = ("packet_id", "verdict", "rule_followed", "arithmetic", "concerns",
        "missing_information", "live_or_recorded", "reviewed_utc", "authority", "reviewer_model")


def utc():
    return datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")


def sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        h.update(fh.read())
    return h.hexdigest()


def die(msg, code=2):
    print("REFUSED: " + msg)
    sys.exit(code)


def pkt_dir(pid):
    if not (pid.startswith("PKT-") and pid[4:].isalnum() and len(pid) <= 40):
        die("not a packet id: %r" % pid)
    return os.path.join(HERE, pid)


def forward_only(packet, bars_path):
    """Refuse a packet that shows anything after the decision."""
    fz = packet.get("frozen", {})
    if fz.get("data_source") != "synthetic":
        return "data_source is %r, not synthetic" % fz.get("data_source")
    seq = fz.get("decision", {}).get("bar_seq")
    text = json.dumps(packet)
    if "tradingview" in text.lower().replace("nothing here came from tradingview", ""):
        return "the packet mentions TradingView data"
    for word in ("fill_price", "net_pnl", "gross_pnl", "exit_fill", "entry_fill"):
        if word in text:
            return "the packet carries an outcome field (%s)" % word
    if fz.get("all_bars_sha256") and fz["all_bars_sha256"] != sha(bars_path):
        return "the bars file does not match the packet's all_bars_sha256"
    with open(bars_path) as fh:
        rows = [json.loads(l) for l in fh if l.strip()]
    if any(r.get("source", "synthetic") != "synthetic" for r in rows):
        return "a line in the bars file is not synthetic"
    seqs = [r["seq"] for r in rows if isinstance(r.get("seq"), int)]
    if not seqs or max(seqs) != seq:
        return "the bars run to seq %s but the decision is at seq %s" % (max(seqs or [None]), seq)
    return None


def prepare(a):
    with open(a.packet) as fh:
        packet = json.load(fh)
    pid = packet.get("packet_id", "")
    bad = forward_only(packet, a.bars)
    if bad:
        die(bad)
    inputs = os.path.join(pkt_dir(pid), "inputs")
    pk_name, bars_name = pid + ".json", "bars_through_signal_bar.jsonl"
    if os.path.isdir(inputs):
        same = (os.path.exists(os.path.join(inputs, pk_name))
                and sha(os.path.join(inputs, pk_name)) == sha(a.packet)
                and sha(os.path.join(inputs, bars_name)) == sha(a.bars))
        if not same:
            die("%s already holds different files for this packet id. Nothing was changed." % inputs)
        print("Already prepared, same files: " + inputs)
        return
    os.makedirs(inputs)
    shutil.copyfile(a.packet, os.path.join(inputs, pk_name))
    shutil.copyfile(a.bars, os.path.join(inputs, bars_name))
    with open(PROMPT_SRC, encoding="utf-8") as fh:
        prompt = fh.read().split("\n---\n", 1)[1].strip()
    with open(os.path.join(inputs, "PROMPT.txt"), "w", encoding="utf-8") as fh:
        fh.write(prompt.replace("{FOLDER}", inputs) + "\n")
    manifest = {"packet_id": pid, "prepared_utc": utc(), "packet_file": pk_name,
                "packet_sha256": sha(a.packet), "bars_file": bars_name, "bars_sha256": sha(a.bars),
                "source_packet": os.path.abspath(a.packet),
                "how_to_review": "Give a fresh reviewer PROMPT.txt and only these two files, by a "
                                 "local run or by pasting into a chat you already pay for. Then "
                                 "store the reply with: review_kit.py attach %s ..." % pid}
    with open(os.path.join(inputs, "MANIFEST.json"), "w") as fh:
        json.dump(manifest, fh, indent=1)
    print("Prepared " + inputs)
    print("Give the reviewer PROMPT.txt plus %s and %s, and nothing else." % (pk_name, bars_name))


def first_json(text):
    start = text.find("{")
    if start < 0:
        return None
    try:
        obj, _ = json.JSONDecoder().raw_decode(text[start:])
        return obj if isinstance(obj, dict) else None
    except ValueError:
        return None


def attach(a):
    d = pkt_dir(a.packet_id)
    man_path = os.path.join(d, "inputs", "MANIFEST.json")
    if not os.path.exists(man_path):
        die("run prepare for %s first" % a.packet_id)
    with open(man_path) as fh:
        man = json.load(fh)
    with open(a.answer, encoding="utf-8") as fh:
        raw = fh.read()
    ans = first_json(raw)
    if ans is None:
        die("no JSON object found in the answer")
    missing = [k for k in KEYS if k not in ans]
    if missing:
        die("the answer lacks %s" % ", ".join(missing))
    if ans["packet_id"] != a.packet_id:
        die("the answer is for %s, not %s" % (ans["packet_id"], a.packet_id))
    if ans["verdict"] not in VERDICTS:
        die("verdict %r is not one of %s" % (ans["verdict"], ", ".join(VERDICTS)))
    if str(ans["authority"]).strip() != AUTHORITY:
        die("authority text is not the exact text the packet requires")
    meta_path = os.path.join(d, a.reviewer + "_review.json")
    if os.path.exists(meta_path):
        die("%s already has a %s answer. Move it aside yourself to replace it." % (a.packet_id, a.reviewer))
    raw_path = os.path.realpath(a.answer)
    if os.path.dirname(raw_path) != os.path.realpath(d):
        raw_path = os.path.join(d, a.reviewer + "_answer.txt")
        with open(raw_path, "w", encoding="utf-8") as fh:
            fh.write(raw)
    meta = {"label": "RECORDED", "packet_id": a.packet_id, "reviewer": a.reviewer,
            "model": a.model, "model_said": ans.get("reviewer_model"), "captured_utc": utc(),
            "reviewed_utc_said": ans.get("reviewed_utc"),
            "packet_sha256": man["packet_sha256"], "bars_sha256": man["bars_sha256"],
            "answer_file": os.path.basename(raw_path), "answer_sha256": sha(raw_path),
            "verdict": ans["verdict"], "rule_followed": ans["rule_followed"],
            "concerns": ans["concerns"], "missing_information": ans["missing_information"],
            "arithmetic_all_match": all(str(x.get("match")).lower() == "true" for x in ans["arithmetic"]),
            "note": a.note or ""}
    with open(meta_path, "w") as fh:
        json.dump(meta, fh, indent=1)
    print("Stored as RECORDED: %s (%s, model %s, verdict %s)" % (meta_path, a.reviewer, a.model, ans["verdict"]))


def stored(pid):
    """Both reviewers' stored answers for one packet, each checked against the inputs."""
    d = pkt_dir(pid)
    try:
        with open(os.path.join(d, "inputs", "MANIFEST.json")) as fh:
            man = json.load(fh)
    except (OSError, ValueError):
        return None, {}
    out = {}
    for r in REVIEWERS:
        try:
            with open(os.path.join(d, r + "_review.json")) as fh:
                m = json.load(fh)
        except (OSError, ValueError):
            out[r] = None
            continue
        ok = m.get("packet_sha256") == man["packet_sha256"]
        try:
            ok = ok and sha(os.path.join(d, m["answer_file"])) == m["answer_sha256"]
        except (OSError, KeyError):
            ok = False
        m["matches_inputs"] = ok
        out[r] = m
    return man, out


def show(a):
    man, out = stored(a.packet_id)
    if man is None:
        die("%s has not been prepared" % a.packet_id)
    print("Packet %s, prepared %s, packet sha %s" % (a.packet_id, man["prepared_utc"], man["packet_sha256"][:12]))
    for r in REVIEWERS:
        m = out.get(r)
        if not m:
            print("  %-6s no answer attached yet" % r)
            continue
        flag = "" if m["matches_inputs"] else "  WARNING: does not match these inputs"
        print("  %-6s RECORDED %s, model %s: %s%s" % (r, m["captured_utc"], m["model"], m["verdict"], flag))


def main():
    ap = argparse.ArgumentParser(description="Blinded review kit (paper only)")
    sub = ap.add_subparsers(dest="cmd")
    p = sub.add_parser("prepare"); p.add_argument("packet"); p.add_argument("bars")
    t = sub.add_parser("attach"); t.add_argument("packet_id")
    t.add_argument("--reviewer", required=True, choices=REVIEWERS)
    t.add_argument("--model", required=True); t.add_argument("--answer", required=True)
    t.add_argument("--note")
    s = sub.add_parser("show"); s.add_argument("packet_id")
    a = ap.parse_args()
    {"prepare": prepare, "attach": attach, "show": show}.get(a.cmd, lambda _: ap.print_help())(a)


if __name__ == "__main__":
    main()
