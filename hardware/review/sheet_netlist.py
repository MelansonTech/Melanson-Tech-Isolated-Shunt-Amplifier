# -*- coding: utf-8 -*-
"""Netlist of one schematic sheet from its own geometry (not the board), so
parts drawn since the last PCB sync are covered. Union-find over wires, pin
electrical ends, net labels, power ports and ports, per
references/project-documents.md section 3.

    python sheet_netlist.py "SHEET.SchDoc" [DESIGNATOR ...]
"""
import collections
import olefile
import re
import struct
import sys

DIRV = {0: (1, 0), 1: (0, 1), 2: (-1, 0), 3: (0, -1)}


def records(path):
    f = olefile.OleFileIO(path)
    d = f.openstream("FileHeader").read()
    f.close()
    out, i = [], 0
    while i + 4 <= len(d):
        ln = struct.unpack_from("<I", d, i)[0] & 0xFFFFFF
        if ln == 0:
            i += 4
            continue
        t = d[i + 4:i + 4 + ln]
        i += 4 + ln
        out.append(dict(p.split("=", 1) for p in t.rstrip(b"\x00").decode("latin-1", "replace").split("|") if "=" in p) if t.startswith(b"|RECORD=") else {})
    return out


def u8(r, k):
    v = r.get("%UTF8%" + k)
    if v:
        try:
            return v.encode("latin-1").decode("utf-8")
        except Exception:
            pass
    return r.get(k, "")


class UF(object):
    def __init__(self):
        self.p = {}

    def find(self, a):
        self.p.setdefault(a, a)
        while self.p[a] != a:
            self.p[a] = self.p[self.p[a]]
            a = self.p[a]
        return a

    def union(self, a, b):
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.p[ra] = rb


TOL = 2     # schematic units (10 mil). CircuitStudio joins a wire end that lands within a
            # hair of a pin's hot end; symbols whose pins sit off the 100 mil grid (SW1 on
            # the FTCAN CAN sheet: pin length 11, ends at x = 1009 against a wire at 1010)
            # make that common, and an exact match reported them as unconnected.


def on_segment(pt, a, b, tol=TOL):
    (x, y), (x1, y1), (x2, y2) = pt, a, b
    if x1 == x2:
        return abs(x - x1) <= tol and min(y1, y2) - tol <= y <= max(y1, y2) + tol
    if y1 == y2:
        return abs(y - y1) <= tol and min(x1, x2) - tol <= x <= max(x1, x2) + tol
    return False


def offgrid_pins(path, grid=10):
    """Pins whose hot end is off the schematic grid - the usual cause of a near-miss
    connection. Returns [(designator, pin, name, (x, y))]."""
    recs = records(path)
    desig = {}
    for r in recs:
        if r.get("RECORD") == "34" and "OWNERINDEX" in r:
            desig[int(r["OWNERINDEX"]) + 1] = r.get("TEXT", "")
    out = []
    for r in recs:
        if r.get("RECORD") == "2" and "OWNERINDEX" in r:
            x, y = int(r.get("LOCATION.X", "0")), int(r.get("LOCATION.Y", "0"))
            dx, dy = DIRV[int(r.get("PINCONGLOMERATE", "0")) & 3]
            L = int(r.get("PINLENGTH", "0"))
            ex, ey = x + dx * L, y + dy * L
            if ex % grid or ey % grid:
                out.append((desig.get(int(r["OWNERINDEX"]) + 1, "?"), r.get("DESIGNATOR", ""), r.get("NAME", ""), (ex, ey)))
    return out


def netlist(path):
    recs = records(path)
    comps, desig, partid = {}, {}, {}
    for i, r in enumerate(recs):
        if r.get("RECORD") == "1":
            comps[i] = dict(libref=u8(r, "LIBREFERENCE"), part=int(r.get("CURRENTPARTID", "1")), comment="",
                            mode=int(r.get("DISPLAYMODE", "0") or 0))
    for i, r in enumerate(recs):
        if "OWNERINDEX" in r:
            o = int(r["OWNERINDEX"]) + 1
            if o in comps:
                if r.get("RECORD") == "34":
                    desig[o] = r.get("TEXT", "")
                elif r.get("RECORD") == "41" and r.get("NAME") == "Comment":
                    comps[o]["comment"] = u8(r, "TEXT")
    uf = UF()
    segs = []
    for r in recs:
        if r.get("RECORD") == "27":
            n = int(r.get("LOCATIONCOUNT", "0"))
            pts = [(int(r.get("X%d" % k, "0")), int(r.get("Y%d" % k, "0"))) for k in range(1, n + 1)]
            for a, b in zip(pts, pts[1:]):
                segs.append((a, b))
                uf.union(("p", a), ("p", b))
    # every vertex onto any other segment it lies on (T junctions)
    verts = {a for s in segs for a in s}
    for v in verts:
        for a, b in segs:
            if v not in (a, b) and on_segment(v, a, b):
                uf.union(("p", v), ("p", a))
    anchors = []                     # (point, kind, name)
    for i, r in enumerate(recs):
        rec = r.get("RECORD")
        if rec == "2" and "OWNERINDEX" in r:
            o = int(r["OWNERINDEX"]) + 1
            if o not in comps:
                continue
            if int(r.get("OWNERPARTID", "1")) != comps[o]["part"]:
                continue                # pins of another part of a multi-part symbol
            if int(r.get("OWNERPARTDISPLAYMODE", "0") or 0) != comps[o]["mode"]:
                # pins of an alternate display mode (a resistor symbol drawn
                # vertically keeps its horizontal mode's pins in the file).
                # They sit on top of each other and on the shunt amplifier
                # sheet they joined R4.1 to R8.2 and shorted the 50 ohm output.
                continue
            x, y = int(r.get("LOCATION.X", "0")), int(r.get("LOCATION.Y", "0"))
            dx, dy = DIRV[int(r.get("PINCONGLOMERATE", "0")) & 3]
            L = int(r.get("PINLENGTH", "0"))
            anchors.append(((x + dx * L, y + dy * L), "pin", (desig.get(o, "?"), r.get("DESIGNATOR", ""), r.get("NAME", ""))))
        elif rec in ("25", "17"):
            anchors.append(((int(r.get("LOCATION.X", "0")), int(r.get("LOCATION.Y", "0"))), "label", u8(r, "TEXT")))
        elif rec == "18":
            x, y = int(r.get("LOCATION.X", "0")), int(r.get("LOCATION.Y", "0"))
            w = int(r.get("WIDTH", "0"))
            anchors.append(((x, y), "port", u8(r, "NAME")))
            anchors.append(((x + w, y), "port", u8(r, "NAME")))
    for pt, kind, name in anchors:
        uf.find(("p", pt))
        for a, b in segs:
            if on_segment(pt, a, b):
                uf.union(("p", pt), ("p", a))
    # anchors on top of each other with no wire (a power port sitting on a pin,
    # two pins touching): join those within the tolerance too
    pts = [pt for pt, _, _ in anchors]
    for i in range(len(pts)):
        for j in range(i + 1, len(pts)):
            if pts[i] != pts[j] and abs(pts[i][0] - pts[j][0]) <= TOL and abs(pts[i][1] - pts[j][1]) <= TOL:
                uf.union(("p", pts[i]), ("p", pts[j]))
    nets = collections.defaultdict(lambda: dict(names=set(), pins=[]))
    for pt, kind, name in anchors:
        root = uf.find(("p", pt))
        if kind == "pin":
            nets[root]["pins"].append(name)
        else:
            nets[root]["names"].add(name)
    out = []
    for root, n in nets.items():
        label = "/".join(sorted(n["names"])) if n["names"] else ("Net_" + "_".join("%s.%s" % (d, p) for d, p, _ in sorted(n["pins"])[:2]))
        out.append((label, sorted(n["pins"])))
    return comps, desig, sorted(out)


if __name__ == "__main__":
    comps, desig, nets = netlist(sys.argv[1])
    want = set(sys.argv[2:])
    for label, pins in nets:
        if want and not any(d in want for d, _, _ in pins):
            continue
        print("%-16s %s" % (label[:16], "  ".join("%s.%s(%s)" % (d, p, nm[:8]) for d, p, nm in pins)))
