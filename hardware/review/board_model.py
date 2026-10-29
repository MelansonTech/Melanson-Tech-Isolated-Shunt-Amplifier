# -*- coding: utf-8 -*-
"""One validated model of the board, read straight out of the .CSPcbDoc.

Everything else in the review reads this. It holds no opinions and does no
physics - it turns the binary into geometry and says plainly what it could not
determine.

    from board_model import Board
    b = Board(PATH)
    b.stackup      [{index, name, kind, layer_byte, thickness_mm, er, material}]
    b.tracks       [{layer, net, x1, y1, x2, y2, width}]           mm
    b.vias         [{net, x, y, pad_d, drill_d, start, stop}]      mm
    b.pads         [{comp, name, net, x, y, w, h, layer, shape, hole, rot}]
    b.arcs         [{layer, net, cx, cy, r, a0, a1, width}]
    b.pours        [{layer, net, contours: [[(x,y), ...], ...]}]   mm
    b.outline      [(x, y), ...]                                   mm
    b.components   [{designator, x, y, rot, side, height, pattern}]
    b.nets         ["GND", ...]            index order = the net u16 in records
    b.classes      {name: [net, ...]}
    b.diffpairs    [{name, p, n}]
    b.violations   {kind: count}

Streams are found by CONTENT, never by GUID - see discover_streams.py.

    python board_model.py BOARD.CSPcbDoc          summary
    python board_model.py BOARD.CSPcbDoc --json   cache to board_model.json
"""
import collections
import json
import os
import re
import struct
import sys

import olefile

U = 393700.787401575                 # internal units per mm (1 unit = 2.54 nm)
NB = {2: 6, 5: 2}                    # blocks per record, by primitive type
LAYER_NAME = {1: "Top", 2: "MidLayer1", 3: "MidLayer2", 32: "Bottom", 74: "Multi"}


def _text_records(d):
    out, i = [], 0
    while i + 4 <= len(d):
        n = struct.unpack_from("<I", d, i)[0] & 0xFFFFFF
        if n == 0 or i + 4 + n > len(d):
            return out if i == len(d) else []
        out.append(d[i + 4:i + 4 + n].rstrip(b"\0").decode("latin-1", "replace"))
        i += 4 + n
    return out if i == len(d) else []


def _prims(d):
    out, i = [], 0
    while i + 5 <= len(d):
        t = d[i]
        p = i + 1
        bl = []
        for _ in range(NB.get(t, 1)):
            if p + 4 > len(d):
                return None
            L = struct.unpack_from("<I", d, p)[0]
            if L > len(d) or p + 4 + L > len(d):
                return None
            bl.append(d[p + 4:p + 4 + L])
            p += 4 + L
        if not bl:
            return None
        out.append((t, bl))
        i = p
    return out if i == len(d) else None


def _f(t, k, dflt=""):
    m = re.search(r"\|%s=([^|]*)" % re.escape(k), t)
    return m.group(1) if m else dflt


def _layer_byte(lid):
    """Altium LAYERID -> the layer byte used in primitive records.

    Encoding is 0x01CC_IIII: CC is the layer class (0x00 copper, 0x02
    mask/overlay/paste, 0x04 dielectric) and IIII the index within it. Copper
    indices are the primitive layer bytes directly - Top 1, MidLayer1 2,
    MidLayer2 3 - EXCEPT Bottom, which is the sentinel 0xFFFF and maps to 32.

    Observed on a real board:
        Top Layer      16777217 = 0x0100_0001 -> 1
        Signal Layer 2 16777219 = 0x0100_0003 -> 3   (MidLayer2, under Top)
        Signal Layer 3 16777218 = 0x0100_0002 -> 2   (MidLayer1, above Bottom)
        Bottom Layer   16842751 = 0x0100_FFFF -> 32
    """
    if not str(lid).isdigit():
        return None
    v = int(lid)
    if ((v >> 16) & 0xFF) != 0:
        return None                      # not a copper layer
    idx = v & 0xFFFF
    return 32 if idx == 0xFFFF else idx


def _mm(v):
    """A dimension field: '12.5mil', '0.3mm' or a bare number in mil."""
    v = str(v).strip()
    if v.endswith("mm"):
        return float(v[:-2])
    if v.endswith("mil"):
        return float(v[:-3]) * 0.0254
    try:
        return float(v) * 0.0254
    except ValueError:
        return 0.0


class Board:
    def __init__(self, path):
        self.path = path
        self.f = olefile.OleFileIO(path)
        self._raw = {}
        for e in self.f.listdir():
            k = "/".join(e)
            try:
                self._raw[k] = self.f.openstream(k).read()
            except Exception:
                pass
        self.notes = []
        self._classify()
        self.nets = self._read_nets()
        self.stackup = self._read_stackup()
        self.tracks = self._read_tracks()
        self.vias = self._read_vias()
        self.components = self._read_components()
        self.pads = self._read_pads()
        self.arcs = self._read_arcs()
        self.outline = self._read_outline()
        self.pours = self._read_pours()
        self.classes = self._read_classes()
        self.diffpairs = self._read_diffpairs()
        self.violations = self._read_violations()

    # ---------------------------------------------------------- stream finding
    def _classify(self):
        self.s = {}
        regions = []
        for k, d in self._raw.items():
            if len(d) < 8:
                continue
            recs = _text_records(d)
            if recs:
                blob = "|".join(recs[:400])
                # Order matters and one stream takes ONE role. The stackup is a
                # single enormous record that also contains HATCHSTYLE, VX0 and
                # POUROVER, so an unordered match hands it the polygon role too
                # and every pour then fails to resolve its net.
                for tag, pat in (("stackup", r"LAYER_V8_\d+NAME="),
                                 ("diffpairs", r"POSITIVENETNAME="),
                                 ("nets", r"\bTOPLAYER_MRWIDTH="),
                                 ("components", r"\bSOURCEDESIGNATOR="),
                                 ("rules", r"\bRULEKIND="),
                                 ("polygons", r"\bPOUROVER="),
                                 ("classes", r"\bSUPERCLASS=")):
                    if tag in self.s:
                        continue
                    if re.search(pat, blob):
                        self.s[tag] = k
                        break
                continue
            p = _prims(d)
            if not p:
                continue
            kinds = collections.Counter(t for t, _ in p)
            main = kinds.most_common(1)[0][0]
            tag = {1: "arcs", 2: "pads", 3: "vias", 4: "tracks", 12: "bodies"}.get(main)
            if main == 11:
                regions.append((k, p))
            elif tag and tag not in self.s:
                self.s[tag] = k
        # Several region streams exist; only the one whose contour chain
        # consumes every record exactly is parseable. The board outline is the
        # single-record one carrying OBJECTKIND=BoardRegion.
        for k, p in regions:
            ok = sum(1 for _, bl in p if self._chain(bl[0]) is not None)
            if ok != len(p):
                self.notes.append("region stream %s rejected (%d/%d parse)" % (k[:30], ok, len(p)))
                continue
            txt = p[0][1][0][22:22 + 200].decode("latin-1", "replace")
            if "BoardRegion" in txt or len(p) == 1:
                self.s["outline"] = k
            else:
                self.s["pours"] = k

    @staticmethod
    def _chain(b):
        """Contours of a region block, or None if the chain does not fit."""
        if len(b) < 22:
            return None
        L = struct.unpack_from("<I", b, 18)[0]
        p = 22 + L
        out = []
        while p + 4 <= len(b):
            cnt = struct.unpack_from("<I", b, p)[0]
            p += 4
            if cnt == 0 or p + 16 * cnt > len(b):
                return None
            pts = struct.unpack_from("<%dd" % (2 * cnt), b, p)
            out.append([(pts[2 * i] / U, pts[2 * i + 1] / U) for i in range(cnt)])
            p += 16 * cnt
        return out if p == len(b) else None

    # ---------------------------------------------------------------- readers
    def _read_nets(self):
        recs = _text_records(self._raw[self.s["nets"]]) if "nets" in self.s else []
        return [_f(t, "NAME") for t in recs]

    def _netname(self, idx):
        return self.nets[idx] if 0 <= idx < len(self.nets) else None

    def _read_stackup(self):
        if "stackup" not in self.s:
            self.notes.append("NO STACKUP STREAM - impedance cannot be solved")
            return []
        t = _text_records(self._raw[self.s["stackup"]])[0]
        out = []
        for i in range(0, 80):
            nm = _f(t, "LAYER_V8_%dNAME" % i)
            if not nm:
                continue
            lid = _f(t, "LAYER_V8_%dLAYERID" % i)
            cop = _f(t, "LAYER_V8_%dCOPTHICK" % i)
            out.append({
                "index": i,
                "name": nm,
                "layer_byte": _layer_byte(lid),
                "copper_mm": _mm(cop) if cop else None,
                "diel_type": _f(t, "LAYER_V8_%dDIELTYPE" % i),
                "diel_mm": _mm(_f(t, "LAYER_V8_%dDIELHEIGHT" % i, "0")),
                "er": float(_f(t, "LAYER_V8_%dDIELCONST" % i, "0") or 0),
                "material": _f(t, "LAYER_V8_%dDIELMATERIAL" % i),
            })
        return out

    def copper_layers(self):
        """Ordered top-to-bottom: [(layer_byte, name, copper_mm)].

        Ordered by the LAYER_V8 index, never by byte or name - 'Signal Layer 2'
        is MidLayer2 = byte 3 and sits directly under Top, while 'Signal Layer
        3' is MidLayer1 = byte 2. Ordering by either would reference the wrong
        plane in every impedance solve.
        """
        return [(L["layer_byte"], L["name"], L["copper_mm"]) for L in self.stackup
                if L["copper_mm"] and L["layer_byte"] is not None]

    def dielectrics(self):
        """[(below_layer_byte, thickness_mm, er, type)] between copper layers."""
        out, last = [], None
        for L in self.stackup:
            if L["copper_mm"]:
                last = L["layer_byte"]
            elif L["diel_mm"] and last is not None and L["diel_type"] != "Surface":
                out.append((last, L["diel_mm"], L["er"], L["diel_type"]))
        return out

    def _read_tracks(self):
        out = []
        for t, bl in _prims(self._raw[self.s["tracks"]]):
            if t != 4 or len(bl[0]) < 33:
                continue
            b = bl[0]
            x1, y1, x2, y2 = struct.unpack_from("<iiii", b, 13)
            out.append({"layer": b[0], "net": self._netname(struct.unpack_from("<H", b, 3)[0]),
                        "x1": x1 / U, "y1": y1 / U, "x2": x2 / U, "y2": y2 / U,
                        "width": struct.unpack_from("<i", b, 29)[0] / U})
        return out

    def _read_vias(self):
        out = []
        for t, bl in _prims(self._raw[self.s["vias"]]):
            if t != 3 or len(bl[0]) < 31:
                continue
            b = bl[0]
            x, y = struct.unpack_from("<ii", b, 13)
            out.append({"net": self._netname(struct.unpack_from("<H", b, 3)[0]),
                        "x": x / U, "y": y / U,
                        "pad_d": struct.unpack_from("<i", b, 21)[0] / U,
                        "drill_d": struct.unpack_from("<i", b, 25)[0] / U,
                        "start": b[29], "stop": b[30]})
        return out

    def _read_pads(self):
        out = []
        for t, bl in _prims(self._raw[self.s["pads"]]):
            if t != 2 or len(bl) < 5:
                continue
            name = bl[0][1:1 + bl[0][0]].decode("latin-1", "replace") if bl[0] else ""
            b5 = bl[4]
            if len(b5) < 60:
                continue
            x, y = struct.unpack_from("<ii", b5, 13)
            xs, ys = struct.unpack_from("<ii", b5, 21)
            ci = struct.unpack_from("<H", b5, 7)[0]
            out.append({"name": name, "net": self._netname(struct.unpack_from("<H", b5, 3)[0]),
                        "comp": (self.components[ci]["designator"]
                                 if ci < len(self.components) else None),
                        "layer": b5[0], "x": x / U, "y": y / U,
                        "w": xs / U, "h": ys / U,
                        "hole": struct.unpack_from("<i", b5, 45)[0] / U,
                        "shape": b5[49], "rot": struct.unpack_from("<d", b5, 52)[0],
                        "stack": len(bl[5]) if len(bl) > 5 else 0})
        return out

    def _read_arcs(self):
        if "arcs" not in self.s:
            return []
        out = []
        for t, bl in _prims(self._raw[self.s["arcs"]]):
            if t != 1 or len(bl[0]) < 45:
                continue
            b = bl[0]
            cx, cy, r = struct.unpack_from("<iii", b, 13)
            out.append({"layer": b[0], "net": self._netname(struct.unpack_from("<H", b, 3)[0]),
                        "cx": cx / U, "cy": cy / U, "r": r / U,
                        "a0": struct.unpack_from("<d", b, 25)[0],
                        "a1": struct.unpack_from("<d", b, 33)[0],
                        "width": struct.unpack_from("<i", b, 41)[0] / U})
        return out

    def _read_outline(self):
        if "outline" not in self.s:
            self.notes.append("NO BOARD OUTLINE FOUND")
            return []
        p = _prims(self._raw[self.s["outline"]])
        c = self._chain(p[0][1][0])
        return c[0] if c else []

    def _read_pours(self):
        """Regions with their net resolved from the polygon-definition stream.

        The region header's own net is 0xFFFF. Pairing by stream order is wrong
        (the two streams are ordered differently) and point-in-polygon is
        ambiguous because a plane pour's contour lies exactly on its outline.
        Best bounding-box IoU within the same layer is decisive.
        """
        polys = []
        if "polygons" in self.s:
            for t in _text_records(self._raw[self.s["polygons"]]):
                vs = []
                for i in range(0, 4000):
                    vx, vy = _f(t, "VX%d" % i), _f(t, "VY%d" % i)
                    if not vx:
                        break
                    vs.append((_mm(vx), _mm(vy)))
                if not vs:
                    continue
                ni = _f(t, "NET")
                polys.append({"layer": _f(t, "LAYER"), "net": self._netname(int(ni)) if ni.isdigit() else None,
                              "bbox": (min(v[0] for v in vs), min(v[1] for v in vs),
                                       max(v[0] for v in vs), max(v[1] for v in vs))})
        # MIDn is copper layer byte n+1 (MID1 = 2 ... MID30 = 31). Listing only MID1/MID2
        # left every pour on a 6-layer board's MID3/MID4 with no net (current-sense Rev 3).
        LMAP = {"TOP": 1, "BOTTOM": 32}
        LMAP.update({"MID%d" % n: n + 1 for n in range(1, 31)})
        out = []
        copper = {b for b, _, _ in self.copper_layers()}
        for t, bl in _prims(self._raw[self.s["pours"]]):
            cont = self._chain(bl[0])
            if not cont:
                continue
            lay = bl[0][0]
            if lay not in copper:
                # keepouts, board cutouts and multilayer regions live in the
                # same stream and are not copper
                self.notes.append("region on non-copper layer %d skipped (%d contours)"
                                  % (lay, len(cont)))
                continue
            # KIND=0 is a copper pour. KIND=1 is a CUTOUT - a negative region
            # that removes copper - and carries SUBPOLYINDEX=-1. Treating one
            # as copper put 185 mm2 of phantom metal on the bottom layer, which
            # the Gerber comparison caught as a solid block of disagreement.
            hdr_len = struct.unpack_from("<I", bl[0], 18)[0]
            hdr = bl[0][22:22 + hdr_len].decode("latin-1", "replace")
            if _f(hdr, "KIND", "0") != "0":
                self.notes.append("region on layer %d is KIND=%s (cutout), not copper - skipped"
                                  % (lay, _f(hdr, "KIND")))
                continue
            xs = [p[0] for c in cont for p in c]
            ys = [p[1] for c in cont for p in c]
            bb = (min(xs), min(ys), max(xs), max(ys))
            best, bestiou = None, 0.0
            for pg in polys:
                if LMAP.get(pg["layer"]) != lay:
                    continue
                iou = self._iou(bb, pg["bbox"])
                if iou > bestiou:
                    best, bestiou = pg, iou
            if bestiou < 0.2:
                # no polygon definition matches: a solid region drawn by hand
                # (the SOT-89 tab copper under U1/U6 here). Take the net of a
                # pad whose centre lies inside it on this layer; the IoU guess
                # gave U1's GND tab to VREGIN and a false 0 mm net clearance.
                hit = None
                for pd in getattr(self, "pads", None) or self._read_pads():
                    if pd["layer"] in (lay, 74) and pd["net"] and bb[0] <= pd["x"] <= bb[2] and bb[1] <= pd["y"] <= bb[3]:
                        hit = pd["net"]
                        break
                if hit:
                    best = {"net": hit}
                    self.notes.append("pour on layer %s: net %s taken from the pad inside it (best IoU %.2f)" % (lay, hit, bestiou))
            if bestiou < 0.5 and not (bestiou < 0.2 and best):
                self.notes.append("pour on layer %s: net unresolved (best IoU %.2f)" % (lay, bestiou))
            out.append({"layer": lay, "net": best["net"] if best else None,
                        "iou": round(bestiou, 4), "contours": cont})
        return out

    @staticmethod
    def _iou(a, b):
        ix = max(0.0, min(a[2], b[2]) - max(a[0], b[0]))
        iy = max(0.0, min(a[3], b[3]) - max(a[1], b[1]))
        inter = ix * iy
        ua = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter
        return inter / ua if ua > 0 else 0.0

    def _read_components(self):
        if "components" not in self.s:
            return []
        out = []
        for t in _text_records(self._raw[self.s["components"]]):
            out.append({"designator": _f(t, "SOURCEDESIGNATOR"),
                        "x": _mm(_f(t, "X", "0")), "y": _mm(_f(t, "Y", "0")),
                        "rot": float(_f(t, "ROTATION", "0") or 0),
                        "side": _f(t, "LAYER"), "height": _mm(_f(t, "HEIGHT", "0")),
                        "pattern": _f(t, "PATTERN")})
        return out

    def _read_classes(self):
        if "classes" not in self.s:
            return {}
        out = {}
        for t in _text_records(self._raw[self.s["classes"]]):
            nm = _f(t, "NAME")
            mem = [v for k, v in re.findall(r"\|(M\d+)=([^|]*)", t)]
            if nm:
                out[nm] = mem
        return out

    def _read_diffpairs(self):
        if "diffpairs" not in self.s:
            return []
        return [{"name": _f(t, "NAME"), "p": _f(t, "POSITIVENETNAME"),
                 "n": _f(t, "NEGATIVENETNAME")}
                for t in _text_records(self._raw[self.s["diffpairs"]])]

    def _read_violations(self):
        out = {}
        for k, d in self._raw.items():
            if not k.startswith("T") or not k.endswith("/Data"):
                continue
            name = k.split("/")[0]
            if "Viol" not in name:
                continue
            recs = _text_records(d)
            if recs:
                out[name] = len(recs)
        return out

    # ---------------------------------------------------------------- summary
    def summary(self):
        L = []
        A = L.append
        A("board:   %s" % os.path.basename(self.path))
        A("streams: " + ", ".join("%s=%s" % (k, v.split("/")[0][:8]) for k, v in sorted(self.s.items())))
        A("")
        A("STACKUP (ordered by LAYER_V8 index, top to bottom)")
        for s in self.stackup:
            if s["copper_mm"]:
                A("  %-18s copper %7.4f mm   byte %s"
                  % (s["name"], s["copper_mm"], s["layer_byte"]))
            elif s["diel_mm"]:
                A("  %-18s diel   %7.4f mm   Er %.3f  %s %s"
                  % (s["name"], s["diel_mm"], s["er"], s["diel_type"], s["material"]))
        cu = self.copper_layers()
        A("  copper layers top->bottom: %s" % " -> ".join("%s(byte %s)" % (n, b) for b, n, _ in cu))
        A("  dielectrics between copper: %s"
          % ", ".join("%.4f mm Er %.2f" % (t, e) for _, t, e, _ in self.dielectrics()))
        A("")
        tl = collections.Counter(t["layer"] for t in self.tracks)
        cop = [t for t in self.tracks if t["layer"] in (1, 2, 3, 32)]
        A("GEOMETRY")
        A("  tracks      %5d total, %5d on copper  %s"
          % (len(self.tracks), len(cop),
             {LAYER_NAME.get(k, k): v for k, v in sorted(tl.items()) if k in (1, 2, 3, 32)}))
        A("  routed length %.1f mm" % sum(
            ((t["x2"] - t["x1"]) ** 2 + (t["y2"] - t["y1"]) ** 2) ** 0.5 for t in cop))
        vs = collections.Counter((round(v["pad_d"], 3), round(v["drill_d"], 3)) for v in self.vias)
        A("  vias        %5d   %s" % (len(self.vias),
                                      ", ".join("%.2f/%.2f x%d" % (a, b, n) for (a, b), n in vs.most_common())))
        A("              spans %s" % dict(collections.Counter((v["start"], v["stop"]) for v in self.vias)))
        A("  pads        %5d   %d with holes, %d netless"
          % (len(self.pads), sum(1 for p in self.pads if p["hole"] > 0),
             sum(1 for p in self.pads if not p["net"])))
        A("  arcs        %5d   on copper: %d"
          % (len(self.arcs), sum(1 for a in self.arcs if a["layer"] in (1, 2, 3, 32))))
        A("  pours       %5d" % len(self.pours))
        for p in self.pours:
            A("      layer %-3s net %-10s %3d contours  IoU %.3f"
              % (p["layer"], p["net"], len(p["contours"]), p["iou"]))
        if self.outline:
            xs = [p[0] for p in self.outline]
            ys = [p[1] for p in self.outline]
            A("  outline     %d vertices  %.3f x %.3f mm  X %.3f..%.3f  Y %.3f..%.3f"
              % (len(self.outline), max(xs) - min(xs), max(ys) - min(ys),
                 min(xs), max(xs), min(ys), max(ys)))
        A("  components  %5d   %s" % (len(self.components),
                                      dict(collections.Counter(c["side"] for c in self.components))))
        A("  nets        %5d   classes %d   diff pairs %d"
          % (len(self.nets), len(self.classes), len(self.diffpairs)))
        A("")
        A("EMBEDDED DRC STATE")
        for k, v in sorted(self.violations.items(), key=lambda kv: -kv[1]):
            A("  %-40s %5d" % (k, v))
        A("  total %d" % sum(self.violations.values()))
        if self.notes:
            A("")
            A("NOTES")
            for n in self.notes:
                A("  ! " + n)
        return "\n".join(L)


if __name__ == "__main__":
    b = Board(sys.argv[1])
    print(b.summary())
    if "--json" in sys.argv:
        out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "board_model.json")
        json.dump({"stackup": b.stackup, "tracks": b.tracks, "vias": b.vias,
                   "pads": b.pads, "arcs": b.arcs, "outline": b.outline,
                   "pours": b.pours, "components": b.components,
                   "nets": b.nets, "classes": b.classes, "diffpairs": b.diffpairs,
                   "violations": b.violations, "notes": b.notes},
                  open(out, "w", encoding="utf-8"))
        print("\ncached -> %s (%.1f MB)" % (out, os.path.getsize(out) / 1e6))
