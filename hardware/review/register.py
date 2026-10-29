# -*- coding: utf-8 -*-
"""The findings register: one JSON file per project that every review run
carries forward. A finding stays OPEN until a check closes it; a regenerated
report reads the register, so it can never drop an item just because the
solver that found it did not run this time.

    python register.py REG.json list [--open] [--area A]
    python register.py REG.json add  --id K8 --area connectivity --sev 1 --title "..." [--detail "..."] [--net N] [--source script.py]
    python register.py REG.json close ID --by "jtag_check.py, board 2026-10-20" [--note "..."]
    python register.py REG.json reopen ID --note "..."
    python register.py REG.json carry NEW.json --area sweep --source sweep.py [--run LABEL]

`carry` merges a solver's own list (dicts with finding/title, detail, severity,
net) into the register under stable ids (<area>-<n>, matched on area + net +
the first words of the finding): existing items keep their status and history,
new ones open, and open items of that area that the solver no longer reports
are closed "by rerun". Severity: 1 blocks build or operation, 2 fix before
release, 3 note.

Fields: id, area, severity, title, detail, net, source, status, opened,
closed, closed_by, notes[]. Dates are the day of the run, ISO.
"""
import argparse
import datetime as dt
import io
import json
import os
import re
import sys


def load(p):
    return json.load(io.open(p, encoding="utf-8")) if os.path.exists(p) else []


def save(p, reg):
    io.open(p, "w", encoding="utf-8", newline="\n").write(json.dumps(reg, indent=1))


def key_of(area, net, title):
    # numbers are left out of the key: "169 vias closer than" and "183 vias
    # closer than" are the same finding with a new measurement
    words = [w for w in re.sub(r"[^a-z0-9 ]", "", title.lower()).split() if not re.match(r"^\d", w)][:4]
    return "%s|%s|%s" % (area, net or "", " ".join(words))


def today():
    return dt.date.today().isoformat()


def cmd_list(reg, a):
    rows = [f for f in reg if (not a.open or f["status"] == "open") and (not a.area or f["area"] == a.area)]
    rows.sort(key=lambda f: (f["status"] != "open", f["severity"], f["id"]))
    for f in rows:
        print("%-8s %-6s sev %d  %-14s %-12s %s%s" % (f["id"], f["status"], f["severity"], f["area"][:14], (f.get("net") or "")[:12], f["title"][:80],
                                                   "  [closed %s by %s]" % (f.get("closed"), f.get("closed_by")) if f["status"] == "closed" else ""))
    print("%d listed, %d open" % (len(rows), sum(1 for f in rows if f["status"] == "open")))


def cmd_add(reg, a):
    if any(f["id"] == a.id for f in reg):
        sys.exit("id %s exists" % a.id)
    reg.append(dict(id=a.id, area=a.area, severity=a.sev, title=a.title, detail=a.detail or "", net=a.net, source=a.source or "",
                    status="open", opened=today(), closed=None, closed_by=None, notes=[]))
    print("added %s" % a.id)


def cmd_close(reg, a):
    f = next((f for f in reg if f["id"] == a.id), None) or sys.exit("no %s" % a.id)
    f["status"], f["closed"], f["closed_by"] = "closed", today(), a.by
    if a.note:
        f["notes"].append("%s: %s" % (today(), a.note))
    print("closed %s by %s" % (a.id, a.by))


def cmd_reopen(reg, a):
    f = next((f for f in reg if f["id"] == a.id), None) or sys.exit("no %s" % a.id)
    f["status"], f["closed"], f["closed_by"] = "open", None, None
    f["notes"].append("%s: reopened - %s" % (today(), a.note or ""))
    print("reopened %s" % a.id)


def cmd_carry(reg, a):
    new = json.load(io.open(a.new, encoding="utf-8"))
    if isinstance(new, dict):
        new = new.get("findings") or new.get("mismatches") or new.get("rows") or []
    existing = {key_of(f["area"], f.get("net"), f["title"]): f for f in reg if f["area"] == a.area}
    n = max([int(f["id"].split("-")[-1]) for f in reg if f["area"] == a.area and re.match(r".*-\d+$", f["id"])] + [0])
    seen, opened, kept = set(), 0, 0
    for it in new:
        title = it.get("finding") or it.get("title") or it.get("pin") or json.dumps(it)[:80]
        net = it.get("net")
        sev = int(it.get("severity", 2))
        k = key_of(a.area, net, title)
        seen.add(k)
        if k in existing:
            f = existing[k]
            f["detail"] = it.get("detail", f.get("detail", "")); f["severity"] = sev
            if f["status"] == "closed" and f.get("closed_by") == "rerun":
                f["status"], f["closed"], f["closed_by"] = "open", None, None
                f["notes"].append("%s: back in the %s output" % (today(), a.source or a.area))
            kept += 1
        else:
            n += 1
            reg.append(dict(id="%s-%d" % (a.area, n), area=a.area, severity=sev, title=title, detail=it.get("detail", ""), net=net,
                            source=a.source or "", status="open", opened=today(), closed=None, closed_by=None, notes=["run %s" % a.run] if a.run else []))
            opened += 1
    gone = 0
    for k, f in existing.items():
        if k not in seen and f["status"] == "open":
            f["status"], f["closed"], f["closed_by"] = "closed", today(), "rerun"
            f["notes"].append("%s: no longer reported by %s" % (today(), a.source or a.area))
            gone += 1
    print("carried %s: %d kept, %d opened, %d closed by rerun" % (a.area, kept, opened, gone))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("reg")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("list"); p.add_argument("--open", action="store_true"); p.add_argument("--area")
    p = sub.add_parser("add"); p.add_argument("--id", required=True); p.add_argument("--area", required=True); p.add_argument("--sev", type=int, default=2)
    p.add_argument("--title", required=True); p.add_argument("--detail"); p.add_argument("--net"); p.add_argument("--source")
    p = sub.add_parser("close"); p.add_argument("id"); p.add_argument("--by", required=True); p.add_argument("--note")
    p = sub.add_parser("reopen"); p.add_argument("id"); p.add_argument("--note")
    p = sub.add_parser("carry"); p.add_argument("new"); p.add_argument("--area", required=True); p.add_argument("--source"); p.add_argument("--run")
    a = ap.parse_args()
    reg = load(a.reg)
    {"list": cmd_list, "add": cmd_add, "close": cmd_close, "reopen": cmd_reopen, "carry": cmd_carry}[a.cmd](reg, a)
    if a.cmd != "list":
        save(a.reg, reg)
