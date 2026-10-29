# -*- coding: utf-8 -*-
"""Gate: port and sheet-entry directions against what actually drives each net.

A port's I/O type (Input / Output / Bidirectional) is documentation the tools
also check, and on a hierarchical project the sheet entries on the top sheet
repeat it. Drawn by hand they drift: on the FTCAN project 58 of 113 were
wrong. The direction is inferred per sheet from two sources, in this order:

  1. the gateware: the top-level HDL port direction of the signal the pin file
     puts on that FPGA pin (output -> the FPGA sheet drives the net -> OUTPUT;
     input -> INPUT; inout -> BIDIRECTIONAL). This is the function. Symbol pin
     types cannot give it, every FPGA pin is "I/O".
  2. the symbols: a sheet whose pins on the net include an Output / Open-
     collector / Open-emitter pin and no Input or I/O pin -> OUTPUT; only
     Inputs -> INPUT; I/O pins or a mix -> BIDIRECTIONAL. Many library symbols
     carry "passive" on every pin, which decides nothing.

A sheet with no evidence takes the complement of a definite partner sheet
(partner OUTPUT -> this INPUT); a definite BIDIRECTIONAL anywhere makes every
sheet on that port bidirectional; with nothing to go on the port is reported
undecidable and left alone.

    python port_directions.py TOP.SchDoc [--hdl top.v --pinfile board.lpf --fpga U2]
                              [--fix] [--json OUT]

Without --fix it reports. With --fix it rewrites IOTYPE in place in every port
and sheet entry that disagrees (same byte length, so the OLE stream is written
back unchanged in size) after copying each file it touches into
<pcb dir>/_backup_ports_<stamp>/. Close the sheets in CircuitStudio first: an
open document is written from the editor's memory on its next save.
"""
import argparse
import collections
import datetime as dt
import io
import json
import os
import re
import shutil
import struct
import sys

import olefile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from sheet_netlist import records, u8, netlist                       # noqa: E402
from pin_constraints_check import parse_lpf, parse_xdc, parse_qsf    # noqa: E402

IOT = {"0": "unspec", "1": "out", "2": "in", "3": "bidir"}
CODE = {"out": "1", "in": "2", "bidir": "3"}
ELEC = {"0": "input", "1": "io", "2": "output", "3": "oc", "4": "passive", "5": "hiz", "6": "oe", "7": "power"}
DRIVES = {"output", "oc", "oe"}
HDL_DIR = {"output": "out", "input": "in", "inout": "bidir"}


def sheet_symbols(top):
    recs = records(top)
    syms, ents = {}, collections.defaultdict(list)
    for i, r in enumerate(recs):
        if r.get("RECORD") == "15":
            syms[i] = dict(file="", name="")
        if r.get("RECORD") in ("32", "33") and "OWNERINDEX" in r:
            o = int(r["OWNERINDEX"]) + 1
            if o in syms:
                syms[o]["name" if r.get("RECORD") == "32" else "file"] = u8(r, "TEXT")
        if r.get("RECORD") == "16" and "OWNERINDEX" in r:
            ents[int(r["OWNERINDEX"]) + 1].append((u8(r, "NAME"), IOT.get(r.get("IOTYPE", "0"), "unspec")))
    return [(s["file"], s["name"], i, ents.get(i, [])) for i, s in syms.items()]


def pin_types(path):
    recs = records(path)
    comps, desig = {}, {}
    for i, r in enumerate(recs):
        if r.get("RECORD") == "1":
            comps[i] = int(r.get("CURRENTPARTID", "1"))
    for r in recs:
        if r.get("RECORD") == "34" and "OWNERINDEX" in r:
            desig[int(r["OWNERINDEX"]) + 1] = r.get("TEXT", "")
    out = {}
    for r in recs:
        if r.get("RECORD") == "2" and "OWNERINDEX" in r:
            o = int(r["OWNERINDEX"]) + 1
            if o in comps and int(r.get("OWNERPARTID", "1")) == comps[o]:
                out[(desig.get(o, "?"), r.get("DESIGNATOR", ""))] = ELEC.get(r.get("ELECTRICAL", "4"), "passive")
    return out


def hdl_ports(path):
    """{signal: input|output|inout} from a Verilog/SystemVerilog or VHDL top level."""
    txt = io.open(path, encoding="utf-8", errors="replace").read()
    txt = re.sub(r"//.*", "", txt); txt = re.sub(r"/\*.*?\*/", "", txt, flags=re.S); txt = re.sub(r"--.*", "", txt)
    out = {}
    # a declaration can list several ports: "output wire a, b, c," - take every name up to the next
    # direction keyword, ';' or the port list's closing ')' (only the first was read until 2026-10-28)
    ident = r"(?!(?:input|output|inout)\b)[A-Za-z_]\w*"       # a name, never the next declaration's keyword
    for m in re.finditer(r"\b(input|output|inout)\b\s*(?:wire|reg|logic)?\s*(?:signed\s*)?(?:\[[^\]]*\]\s*)?"
                         r"((?:%s\s*,\s*)*%s)" % (ident, ident), txt):
        for name in re.split(r"\s*,\s*", m.group(2).strip()):
            if name and name not in ("input", "output", "inout", "wire", "reg", "logic"):
                out[name] = m.group(1)
    for m in re.finditer(r"([A-Za-z_]\w*)\s*:\s*(in|out|inout)\b", txt, flags=re.I):      # VHDL entity ports
        out.setdefault(m.group(1), {"in": "input", "out": "output", "inout": "inout"}[m.group(2).lower()])
    return out


def site_directions(pinfile, hdl):
    """site -> (signal, input|output|inout) through the pin file."""
    text = io.open(pinfile, encoding="utf-8", errors="replace").read()
    ext = os.path.splitext(pinfile)[1].lower()
    locs = {".lpf": parse_lpf, ".xdc": parse_xdc, ".qsf": parse_qsf}.get(ext, parse_lpf)(text)
    out = {}
    for sig, site in locs:
        base = re.sub(r"\[\d+\]$", "", sig)
        if base in hdl:
            out[str(site)] = (sig, hdl[base])
    return out


def port_evidence(path, fpga=None, sites=None):
    recs = records(path)
    cur = {}
    for r in recs:
        if r.get("RECORD") == "18":
            cur.setdefault(u8(r, "NAME"), IOT.get(r.get("IOTYPE", "0"), "unspec"))
    comps, desig, nets = netlist(path)
    types = pin_types(path)
    ev = {}
    for label, pins in nets:
        names = set(label.split("/"))
        for pn in names & set(cur):
            tl = [("%s.%s" % (d, p), types.get((d, p), "passive")) for d, p, _ in pins]
            role, src = None, "symbols"
            if fpga and sites:
                hd = [sites[p][1] for d, p, _ in pins if d == fpga and p in sites]
                if hd:
                    dirs = set(hd)
                    role = "bidir!" if ("inout" in dirs or len(dirs) > 1) else ("out!" if "output" in dirs else "in!")
                    src = "hdl %s" % "/".join(sorted(dirs))
            if role is None:
                kinds = {t for _, t in tl if t != "power"}
                drives = bool(kinds & DRIVES); receives = "input" in kinds; io_ = "io" in kinds
                if drives and not receives and not io_:
                    role = "out!"
                elif receives and not drives and not io_:
                    role = "in!"
                elif drives or receives or io_:
                    role = "bidir"
                else:
                    role = "passive"
            ev[pn] = dict(current=cur[pn], pins=tl, role=role, src=src)
    for pn in cur:
        ev.setdefault(pn, dict(current=cur[pn], pins=[], role="none", src="no net"))
    return ev


def infer(all_ev):
    out = {}
    by_port = collections.defaultdict(dict)
    for sheet, ev in all_ev.items():
        for pn, e in ev.items():
            by_port[pn][sheet] = e
    for pn, sheets in by_port.items():
        definite = {s: e["role"].rstrip("!") for s, e in sheets.items() if e["role"].endswith("!")}
        for s, e in sheets.items():
            role = e["role"]
            others = [r for s2, r in definite.items() if s2 != s]
            if role.endswith("!"):
                out[(s, pn)] = role.rstrip("!")
            elif "bidir" in others:
                out[(s, pn)] = "bidir"
            elif others and all(r == "out" for r in others):
                out[(s, pn)] = "in"
            elif others and all(r == "in" for r in others):
                out[(s, pn)] = "out"
            elif role == "bidir":
                out[(s, pn)] = "bidir"
            else:
                out[(s, pn)] = "?"
    return out, by_port


def patch_stream(path, wanted, record_kind, owner_filter=None):
    ole = olefile.OleFileIO(path, write_mode=True)
    data = ole.openstream("FileHeader").read()
    out = bytearray(); i = 0; changed = []
    while i + 4 <= len(data):
        hdr = data[i:i + 4]
        ln = struct.unpack_from("<I", data, i)[0] & 0xFFFFFF
        if ln == 0:
            out += hdr; i += 4
            continue
        body = data[i + 4:i + 4 + ln]; i += 4 + ln
        txt = body.decode("latin-1")
        if txt.startswith("|RECORD=%s|" % record_kind):
            fields = dict(p.split("=", 1) for p in txt.rstrip("\x00").split("|") if "=" in p)
            name = fields.get("NAME", "")
            ok_owner = owner_filter is None or int(fields.get("OWNERINDEX", "-1")) + 1 in owner_filter
            if name in wanted and ok_owner and "IOTYPE" in fields:
                old = "|IOTYPE=%s" % fields["IOTYPE"]; new = "|IOTYPE=%s" % CODE[wanted[name]]
                if old != new:
                    txt2 = txt.replace(old, new, 1)
                    assert len(txt2) == len(txt), "length changed on %s" % name
                    body = txt2.encode("latin-1"); changed.append(name)
        out += hdr + body
    assert len(out) == len(data), "stream size changed"
    if changed:
        ole.write_stream("FileHeader", bytes(out))
    ole.close()
    return changed


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("top", help="the top sheet with the sheet symbols, or with --flat the first of the sheets")
    ap.add_argument("--flat", nargs="*", help="flat project: list every sheet here; ports join by name and there are no sheet entries")
    ap.add_argument("--hdl"); ap.add_argument("--pinfile"); ap.add_argument("--fpga")
    ap.add_argument("--fix", action="store_true"); ap.add_argument("--json")
    ap.add_argument("--roles", help='JSON {port: {sheet-file-substring: "in|out|bidir"}} for ports no evidence decides (a divider between the pin and the port)')
    a = ap.parse_args()
    pcbdir = os.path.dirname(os.path.abspath(a.top))
    sites = site_directions(a.pinfile, hdl_ports(a.hdl)) if (a.hdl and a.pinfile and a.fpga) else None
    roles = json.load(io.open(a.roles, encoding="utf-8")) if a.roles else {}
    if a.flat is not None:
        flat = [a.top] + list(a.flat)
        syms = [(os.path.basename(f), os.path.basename(f).replace(".SchDoc", ""), None, []) for f in flat]
    else:
        syms = sheet_symbols(a.top)
    all_ev = {}
    for f, name, idx, ents in syms:
        p = os.path.join(pcbdir, f)
        if os.path.exists(p):
            all_ev[f] = port_evidence(p, a.fpga, sites)
            for pn, bysheet in roles.items():
                if pn in all_ev[f]:
                    for frag, d in bysheet.items():
                        if frag.lower() in f.lower():
                            all_ev[f][pn]["role"] = d + "!"; all_ev[f][pn]["src"] = "roles file"
    inferred, by_port = infer(all_ev)
    rows, n_bad, n_unk = [], 0, 0
    for f, name, idx, ents in syms:
        if f not in all_ev:
            continue
        ent_cur = dict(ents)
        for pn, e in sorted(all_ev[f].items()):
            want = inferred[(f, pn)]
            r = dict(sheet=f.split(" - ")[-1].replace(".SchDoc", ""), symbol=name, port=pn, port_now=e["current"], entry_now=ent_cur.get(pn, "missing"),
                     inferred=want, role_here=e["role"].rstrip("!"), source=e["src"], partners=len(by_port[pn]) - 1,
                     evidence=", ".join("%s %s" % x for x in e["pins"][:4]) + (" ..." if len(e["pins"]) > 4 else ""),
                     port_ok=(want == "?" or e["current"] == want), entry_ok=(want == "?" or a.flat is not None or ent_cur.get(pn) == want))
            if want == "?":
                n_unk += 1
            elif not (r["port_ok"] and r["entry_ok"]):
                n_bad += 1
            rows.append(r)
    print("%d ports on %d sheets: %d need a change (port or sheet entry), %d undecidable" % (len(rows), len(all_ev), n_bad, n_unk))
    print("\n%-14s %-16s %-6s %-7s %-6s %-14s %s" % ("sheet", "port", "port", "entry", "want", "source", "evidence"))
    for r in rows:
        if r["port_ok"] and r["entry_ok"] and r["inferred"] != "?":
            continue
        print("%-14s %-16s %-6s %-7s %-6s %-14s %s" % (r["sheet"][:14], r["port"][:16], r["port_now"], r["entry_now"], r["inferred"], r["source"][:14], r["evidence"][:60]))
    dang = [r for r in rows if r["partners"] == 0]
    if dang:
        print("\nports with no partner on any other sheet: %s" % ", ".join("%s/%s" % (r["sheet"], r["port"]) for r in dang))
    if a.json:
        io.open(a.json, "w", encoding="utf-8", newline="\n").write(json.dumps(dict(rows=rows, n_bad=n_bad, n_unknown=n_unk), indent=1))
        print("written -> %s" % a.json)
    if a.fix and n_bad:
        stamp = dt.datetime.now().strftime("%Y%m%d-%H%M")
        bdir = os.path.join(pcbdir, "_backup_ports_" + stamp); os.makedirs(bdir, exist_ok=True)
        total = 0
        for f, name, idx, ents in syms:
            if f not in all_ev:
                continue
            wanted = {r["port"]: r["inferred"] for r in rows if r["symbol"] == name and r["inferred"] != "?" and not r["port_ok"]}
            if wanted:
                p = os.path.join(pcbdir, f); shutil.copy2(p, os.path.join(bdir, f))
                ch = patch_stream(p, wanted, "18"); total += len(ch)
                print("  %s: %d port(s) rewritten" % (f, len(ch)))
        wanted_ent = collections.defaultdict(dict)
        for r in rows:
            if r["inferred"] != "?" and not r["entry_ok"] and r["entry_now"] != "missing":
                wanted_ent[r["symbol"]][r["port"]] = r["inferred"]
        if wanted_ent and a.flat is None:
            shutil.copy2(a.top, os.path.join(bdir, os.path.basename(a.top)))
            for f, name, idx, ents in syms:
                if name in wanted_ent:
                    ch = patch_stream(a.top, wanted_ent[name], "16", owner_filter={idx}); total += len(ch)
                    print("  top sheet, symbol %s: %d entr(ies) rewritten" % (name, len(ch)))
        print("backups in %s; %d records changed. Reopen the sheets in CircuitStudio before saving anything." % (bdir, total))
