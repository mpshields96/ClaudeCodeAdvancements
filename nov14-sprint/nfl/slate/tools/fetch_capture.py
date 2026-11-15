"""Fetch public keyless URLs into a NEW folder  slate/inputs/<name>.<UTC>/  with a MANIFEST.json.

Usage: /usr/bin/env -i PATH=/usr/bin:/bin /usr/bin/python3 -I fetch_capture.py <name> <label>=<url> [<label>=<url> ...]
Stdlib only (Python 3.9.6). Never overwrites: refuses if the folder exists. No credentials, no cookies,
default urllib User-Agent replaced by a plain generic client name (no spoofing of a browser).
A non-200 answer (403, 404, ...) is recorded in the manifest and the body (if any) is kept; nothing is bypassed.
"""
import hashlib, json, os, sys, time, urllib.request, urllib.error, datetime

HERE = os.path.dirname(os.path.abspath(__file__))
INPUTS = os.path.join(os.path.dirname(HERE), "inputs")


def utc_now():
    return datetime.datetime.now(datetime.timezone.utc)


def main(argv):
    name = argv[1]
    pairs = [a.split("=", 1) for a in argv[2:]]
    stamp = utc_now().strftime("%Y%m%dT%H%M%SZ")
    folder = os.path.join(INPUTS, "%s.%s" % (name, stamp))
    os.makedirs(folder)  # raises if it exists: never overwrite
    entries = []
    for label, url in pairs:
        t0 = utc_now()
        status, body, err = None, b"", None
        req = urllib.request.Request(url, headers={"User-Agent": "nfl-slate-data-paper-research/1.0", "Accept": "application/json, text/html;q=0.8"})
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                status = r.status
                body = r.read()
        except urllib.error.HTTPError as e:
            status = e.code
            try:
                body = e.read()
            except Exception:
                body = b""
            err = "HTTPError %s" % e.code
        except Exception as e:  # network / ssl
            err = "%s: %s" % (type(e).__name__, e)
        fname = label if "." in label else label + ".json"
        if body:
            with open(os.path.join(folder, fname), "wb") as f:
                f.write(body)
        entries.append({
            "label": label,
            "file": fname if body else None,
            "url": url,
            "retrieved_utc": t0.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "http_status": status,
            "bytes": len(body),
            "sha256": hashlib.sha256(body).hexdigest() if body else None,
            "error": err,
        })
        time.sleep(0.4)
    with open(os.path.join(folder, "MANIFEST.json"), "w") as f:
        json.dump({"name": name, "folder": os.path.basename(folder), "created_utc": stamp, "files": entries}, f, indent=1)
    print(folder)
    for e in entries:
        print(e["label"], e["http_status"], e["bytes"], e["error"] or "")


if __name__ == "__main__":
    main(sys.argv)
