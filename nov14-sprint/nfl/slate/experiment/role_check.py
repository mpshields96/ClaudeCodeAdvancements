#!/usr/bin/python3
"""Carrier and test for pregame role hypotheses already registered in the journal.

This file registers nothing. Each spec below mirrors one journal hypothesis by id
and by the sha256 of its exact text, and turns its plain-English terms into a fixed
test that is written down before kickoff. After the final, the observed public box
score numbers go in and the verdict comes out:

    condition_unmet   a stated condition was false (the forecast does not apply)
    unknown           a condition or the outcome number is not known yet
    supported         every condition held and the outcome threshold was met
    contradicted      every condition held and the outcome threshold was missed

The verdict is about the role forecast only. The linked prop (for example an over
on receiving yards) is shown beside it as separate arithmetic and never changes
the verdict; the journal grades the prop. An early exit is recorded, not excused.

It reads the journal's hypotheses file read-only, and writes only its own
append-only chained file, role_data/observations.jsonl. Paper only: no network,
no accounts, no bets, no prices changed, no profit claim.

Run (system Python, isolated):
    /usr/bin/env -i PATH=/usr/bin:/bin /usr/bin/python3 -I -B role_check.py COMMAND

    list                         the carried hypotheses and their fixed tests
    verify                       specs match the journal text; own chain intact
    evaluate --id H --set k=v    verdict for trial numbers; writes nothing
    record   --id H --set k=v ... --final-utc T --source-ref S --recorded-by WHO
    status [--json]              latest verdict per hypothesis

Exit codes: 0 done, 1 refused or verification failed, 2 bad command line.
"""
import argparse
import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))  # -I leaves the script folder off the path
from comparator import Refused, Store, iso, need, parse_utc, utc_now  # noqa: E402

DEFAULT_STORE = HERE / "role_data"
LEDGER = "observations.jsonl"
JOURNAL_HYPOTHESES = HERE / "data" / "hypotheses.jsonl"
NOTE = ("Role forecast only. It adds no bet, carries no win probability and makes no "
        "profit claim. The linked prop is separate arithmetic; the journal grades it.")

SPECS = {
    "H3fb769df": {
        "hypothesis_id": "H3fb769df",
        "journal_text_sha256":
            "3fb769dfe0b16badbba558e6119ed67e7e1d37c7d9a3fe5bc5f477e9ad66c658",
        "cids": ["3840ddbfeaa1"],
        "first_kickoff_utc": "2026-11-16T01:20:00Z",
        "summary": "Jaylen Warren draws at least four targets at Cincinnati if Aaron "
                   "Rodgers starts and Warren takes an offensive snap.",
        "conditions": [
            {"key": "rodgers_started", "kind": "bool", "label": "Aaron Rodgers started"},
            {"key": "warren_offensive_snaps", "kind": "min", "min": 1,
             "label": "Jaylen Warren offensive snaps"},
        ],
        "outcome": {"key": "warren_targets", "min": 4,
                    "label": "Jaylen Warren receiving targets"},
        "record_also": {
            "warren_receptions": "number", "warren_receiving_yards": "number",
            "warren_longest_reception": "number", "early_exit": "bool",
            "early_exit_note": "text",
        },
        "linked_prop": {"cid": "3840ddbfeaa1", "key": "warren_receiving_yards",
                        "side": "over", "line": 22.5,
                        "played_key": "warren_offensive_snaps"},
    },
}

YES = ("yes", "y", "true", "1")
NO = ("no", "n", "false", "0")
UNKNOWN = ("unknown", "?", "")


def load_specs(path=None):
    if not path:
        return SPECS
    with open(str(path), encoding="utf-8") as handle:
        specs = json.load(handle)
    if not isinstance(specs, dict) or not specs:
        raise Refused("the specs file does not hold any hypothesis specs")
    for key, spec in specs.items():
        for field in ("hypothesis_id", "journal_text_sha256", "first_kickoff_utc",
                      "conditions", "outcome"):
            if field not in spec:
                raise Refused("spec %s has no %s" % (key, field))
    return specs


def spec_for(specs, hypothesis_id):
    spec = specs.get(need(hypothesis_id, "hypothesis id"))
    if spec is None:
        raise Refused("no carried hypothesis has id %s" % hypothesis_id)
    return spec


def field_kinds(spec):
    kinds = {}
    for condition in spec["conditions"]:
        kinds[condition["key"]] = "bool" if condition["kind"] == "bool" else "number"
    kinds[spec["outcome"]["key"]] = "number"
    kinds.update(spec.get("record_also") or {})
    return kinds


def parse_value(kind, text, key):
    raw = "" if text is None else str(text).strip()
    if kind == "text":
        return " ".join(raw.split()) or None
    if raw.casefold() in UNKNOWN:
        return None
    if kind == "bool":
        if raw.casefold() in YES:
            return True
        if raw.casefold() in NO:
            return False
        raise Refused("%s must be yes, no or unknown" % key)
    try:
        number = float(raw)
    except ValueError:
        raise Refused("%s must be a number or unknown" % key)
    if number != number or number in (float("inf"), float("-inf")):
        raise Refused("%s must be a number or unknown" % key)
    if number < 0 and "yards" not in key and "longest" not in key:
        raise Refused("%s cannot be negative" % key)
    return int(number) if number == int(number) else number


def parse_sets(spec, pairs):
    kinds = field_kinds(spec)
    observed = {}
    for pair in pairs or []:
        if "=" not in pair:
            raise Refused("write each observation as key=value, not %r" % pair)
        key, value = pair.split("=", 1)
        key = key.strip()
        if key not in kinds:
            raise Refused("%s is not a field of this hypothesis (fields: %s)"
                          % (key, ", ".join(sorted(kinds))))
        if key in observed:
            raise Refused("%s is given twice" % key)
        observed[key] = parse_value(kinds[key], value, key)
    return observed


def evaluate(spec, observed):
    """Pure. observed maps field name to a value; a missing or None value is unknown."""
    conditions = []
    for condition in spec["conditions"]:
        value = observed.get(condition["key"])
        if value is None:
            met = None
        elif condition["kind"] == "bool":
            met = bool(value)
        else:
            met = value >= condition["min"]
        conditions.append({"key": condition["key"], "label": condition["label"],
                           "value": value, "met": met})
    outcome = spec["outcome"]
    value = observed.get(outcome["key"])
    if any(item["met"] is False for item in conditions):
        verdict = "condition_unmet"
    elif any(item["met"] is None for item in conditions) or value is None:
        verdict = "unknown"
    elif value >= outcome["min"]:
        verdict = "supported"
    else:
        verdict = "contradicted"
    result = {"hypothesis_id": spec["hypothesis_id"], "verdict": verdict,
              "conditions": conditions,
              "outcome": {"key": outcome["key"], "label": outcome["label"],
                          "threshold": outcome["min"], "value": value},
              "early_exit": observed.get("early_exit"),
              "linked_prop": None}
    prop = spec.get("linked_prop")
    if prop:
        stat = observed.get(prop["key"])
        played = observed.get(prop.get("played_key")) if prop.get("played_key") else True
        if played is not None and not played:
            arithmetic = "not graded here: the player did not play, book rules decide"
        elif stat is None or played is None:
            arithmetic = "unknown"
        else:
            margin = stat - prop["line"] if prop["side"] == "over" else prop["line"] - stat
            arithmetic = "win" if margin > 0 else ("loss" if margin < 0 else "push")
        result["linked_prop"] = {"cid": prop["cid"], "side": prop["side"],
                                 "line": prop["line"], "value": stat,
                                 "arithmetic": arithmetic,
                                 "changes_the_verdict": False}
    return result


def verify_against_journal(specs, journal_file=None):
    """Read the journal's hypotheses file (read-only) and compare each spec to it."""
    path = Path(journal_file) if journal_file else JOURNAL_HYPOTHESES
    if not path.is_file():
        return ["the journal hypotheses file was not found: %s" % path]
    rows = {}
    with open(str(path), encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except ValueError:
                return ["the journal hypotheses file has a line that is not valid JSON"]
            if isinstance(row, dict) and row.get("hypothesis_id"):
                rows[row["hypothesis_id"]] = row
    found = []
    for key in sorted(specs):
        spec = specs[key]
        row = rows.get(spec["hypothesis_id"])
        if row is None:
            found.append("%s is not registered in the journal" % key)
            continue
        text_sha = hashlib.sha256(str(row.get("text", "")).encode("utf-8")).hexdigest()
        if text_sha != spec["journal_text_sha256"]:
            found.append("%s: the journal text no longer matches the carried test" % key)
        if row.get("text_sha256") not in (None, text_sha):
            found.append("%s: the journal's own text hash does not match its text" % key)
        if sorted(row.get("cids") or []) != sorted(spec.get("cids") or []):
            found.append("%s: linked candidate ids differ from the journal" % key)
        if row.get("first_kickoff_utc") and (
                iso(parse_utc(row["first_kickoff_utc"], "journal kickoff"))
                != iso(parse_utc(spec["first_kickoff_utc"], "spec kickoff"))):
            found.append("%s: first kickoff differs from the journal" % key)
        if row.get("recorded_utc") and (
                parse_utc(row["recorded_utc"], "journal time")
                >= parse_utc(spec["first_kickoff_utc"], "spec kickoff")):
            found.append("%s: the journal row was not recorded before kickoff" % key)
    return found


def record(store, spec, observed, final_utc, source_ref, recorded_by, correct=False,
           reason=None, now=None):
    now = now or utc_now()
    kickoff = parse_utc(spec["first_kickoff_utc"], "kickoff")
    final = parse_utc(final_utc, "final time")
    source_ref = need(source_ref, "source reference")
    recorded_by = need(recorded_by, "recorded by")
    if now < kickoff or final < kickoff:
        raise Refused("no observation before kickoff")
    if final > now:
        raise Refused("final time is in the future")
    if not any(value is not None for value in observed.values()):
        raise Refused("give at least one observed value")
    if correct:
        reason = need(reason, "a correction needs a reason; the reason")
    result = evaluate(spec, observed)

    def build(rows):
        earlier = [row for row in rows if row.get("kind") == "observation"
                   and row.get("hypothesis_id") == spec["hypothesis_id"]]
        if earlier and not correct:
            raise Refused("this hypothesis already has an observation; "
                          "use a correction with a reason")
        if correct and not earlier:
            raise Refused("there is no earlier observation to correct")
        return {"kind": "observation", "hypothesis_id": spec["hypothesis_id"],
                "journal_text_sha256": spec["journal_text_sha256"],
                "observed": observed, "verdict": result["verdict"],
                "evaluation": result, "final_utc": iso(final), "recorded_utc": iso(now),
                "source_ref": source_ref, "recorded_by": recorded_by,
                "corrects_seq": earlier[-1]["seq"] if correct else None,
                "reason": reason if correct else None}

    return store.append(build)


def build_status(specs, rows, now=None, problems=None):
    now = now or utc_now()
    latest = {}
    for row in rows:
        if row.get("kind") == "observation":
            latest[row["hypothesis_id"]] = row
    items = []
    for key in sorted(specs):
        spec = specs[key]
        row = latest.get(spec["hypothesis_id"])
        kicked = now >= parse_utc(spec["first_kickoff_utc"], "kickoff")
        if row:
            state, evaluation = row["verdict"], row["evaluation"]
        else:
            state = "unknown (no observation recorded)" if kicked else "pending (before kickoff)"
            evaluation = None
        items.append({"hypothesis_id": spec["hypothesis_id"], "summary": spec.get("summary"),
                      "first_kickoff_utc": spec["first_kickoff_utc"], "state": state,
                      "evaluation": evaluation,
                      "recorded_utc": row["recorded_utc"] if row else None,
                      "source_ref": row["source_ref"] if row else None,
                      "corrected": bool(row and row.get("corrects_seq"))})
    return {"as_of_utc": iso(now), "note": NOTE, "chain_problems": problems or [],
            "hypotheses": items}


def show(value):
    if value is None:
        return "unknown"
    if value is True:
        return "yes"
    if value is False:
        return "no"
    return str(value)


def render_evaluation(result):
    lines = ["  verdict: %s" % result["verdict"]]
    for item in result["conditions"]:
        met = {True: "met", False: "not met", None: "unknown"}[item["met"]]
        lines.append("  condition: %s = %s (%s)" % (item["label"], show(item["value"]), met))
    outcome = result["outcome"]
    lines.append("  outcome: %s = %s (needs at least %s)"
                 % (outcome["label"], show(outcome["value"]), outcome["threshold"]))
    lines.append("  early exit: %s" % show(result["early_exit"]))
    prop = result["linked_prop"]
    if prop:
        lines.append("  linked prop %s (%s %s), separate from the verdict: %s"
                     % (prop["cid"], prop["side"], prop["line"], prop["arithmetic"]))
    return lines


def render_status(status):
    lines = ["Role hypotheses as of %s" % status["as_of_utc"]]
    for problem in status["chain_problems"]:
        lines.append("  CHAIN PROBLEM: %s" % problem)
    for item in status["hypotheses"]:
        lines.append("%s: %s" % (item["hypothesis_id"], item["summary"]))
        lines.append("  first kickoff %s; state: %s" % (item["first_kickoff_utc"], item["state"]))
        if item["evaluation"]:
            lines.extend(render_evaluation(item["evaluation"])[1:])
            lines.append("  recorded %s from %s%s" % (item["recorded_utc"], item["source_ref"],
                                                     " (corrected)" if item["corrected"] else ""))
    lines.append(status["note"])
    return "\n".join(lines)


def render_list(specs):
    lines = []
    for key in sorted(specs):
        spec = specs[key]
        lines.append("%s: %s" % (key, spec.get("summary", "")))
        lines.append("  journal text sha256 %s" % spec["journal_text_sha256"])
        lines.append("  first kickoff %s; linked candidates %s"
                     % (spec["first_kickoff_utc"], ", ".join(spec.get("cids") or []) or "none"))
        for condition in spec["conditions"]:
            rule = "must be yes" if condition["kind"] == "bool" else (
                "must be at least %s" % condition["min"])
            lines.append("  condition %s: %s" % (condition["key"], rule))
        lines.append("  outcome %s: supported at %s or more, contradicted below"
                     % (spec["outcome"]["key"], spec["outcome"]["min"]))
        lines.append("  also recorded: %s" % ", ".join(sorted(spec.get("record_also") or {})))
    lines.append(NOTE)
    return "\n".join(lines)


def build_parser():
    parser = argparse.ArgumentParser(description="Pregame role hypothesis carrier and test.")
    parser.add_argument("--data", help="folder for this helper's own observations file")
    parser.add_argument("--specs", help="JSON file of specs (default: the built-in specs)")
    parser.add_argument("--journal-hypotheses", help="journal hypotheses file, read only")
    commands = parser.add_subparsers(dest="command")
    commands.add_parser("list")
    commands.add_parser("verify")
    trial = commands.add_parser("evaluate")
    final = commands.add_parser("record")
    for sub in (trial, final):
        sub.add_argument("--id")
        sub.add_argument("--set", action="append", metavar="KEY=VALUE")
    final.add_argument("--final-utc")
    final.add_argument("--source-ref")
    final.add_argument("--recorded-by")
    final.add_argument("--correct", action="store_true")
    final.add_argument("--reason")
    commands.add_parser("status").add_argument("--json", action="store_true")
    return parser


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    if not args.command:
        parser.print_usage(sys.stderr)
        return 2
    store = Store(args.data or DEFAULT_STORE, LEDGER)
    try:
        specs = load_specs(args.specs)
        if args.command == "list":
            print(render_list(specs))
        elif args.command == "verify":
            bad = verify_against_journal(specs, args.journal_hypotheses)
            rows = store.rows()
            bad.extend(store.problems(rows))
            if bad:
                print("FAILED: " + "; ".join(bad))
                return 1
            print("%d carried hypothesis spec(s) match the journal text. "
                  "Observation chain intact: %d row(s)." % (len(specs), len(rows)))
        elif args.command == "evaluate":
            spec = spec_for(specs, args.id)
            result = evaluate(spec, parse_sets(spec, args.set))
            print("%s (trial numbers, nothing written)" % spec["hypothesis_id"])
            print("\n".join(render_evaluation(result)))
            print(NOTE)
        elif args.command == "record":
            spec = spec_for(specs, args.id)
            row = record(store, spec, parse_sets(spec, args.set), args.final_utc,
                         args.source_ref, args.recorded_by, correct=args.correct,
                         reason=args.reason)
            print("Recorded %s: %s (row %d)." % (row["hypothesis_id"], row["verdict"],
                                                 row["seq"]))
            print("\n".join(render_evaluation(row["evaluation"])))
        else:
            rows = store.rows()
            status = build_status(specs, rows, problems=store.problems(rows))
            print(json.dumps(status, indent=2, sort_keys=True) if args.json
                  else render_status(status))
            if status["chain_problems"]:
                return 1
    except Refused as refusal:
        print("REFUSED: %s" % refusal, file=sys.stderr)
        return 1
    except (OSError, ValueError) as problem:
        print("REFUSED: could not read the input (%s)" % problem, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
