# -*- coding: utf-8 -*-
"""DFM, fabrication package and current-carrying checks on the Rev 3.1 board.

  annular rings      vias and through-hole pads against JLC's 0.13 mm minimum
  track widths       the narrowest copper per layer against the 0.13 mm rule and JLC's 0.09 mm
  net clearance      the closest copper of different nets per layer, every pair, from the rasters
  copper to edge     copper to the outline and to the slot wall, against JLC's 0.3 mm (routed edge)
  drill file         the Excellon .TXT (METRIC 4:4, LZ) hole for hole against the board's holes
  outline file       the barrier slot is drawn on the Outline layer as a 2.5 mm stroked path (D103)
  keep-out file      a .GKO carrying only an 11.5 x 3.9 mm rectangle is in the fabrication set
  fiducials, test points  none on the board
  shunt current path the J2 pours at 10 A: IPC-2221 external-conductor temperature rise

    python dfm_check.py
"""
import glob
import io
import json
import os
import re
import sys

import numpy as np
from scipy import ndimage

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from board_model import Board                                # noqa: E402
from raster import Grid, copper_of, fill                     # noqa: E402

PROJ = os.path.dirname(os.path.dirname(HERE))
REV = os.path.join(PROJ, "Revision 3")
BOARD = os.path.join(REV, "MelansonTech Isolated Shunt Amplifier Rev3.CSPcbDoc")
OUT = os.path.join(REV, "Default Configuration", "Outputs")
JLC = dict(annular_min=0.13, track_min=0.09, clearance_min=0.09, copper_to_edge=0.30, via_drill_min=0.15, via_pad_min=0.45)
BOARD_RULES = dict(width_min=0.130, clearance_min=0.200)


def read_drill_txt(path):
    holes = []
    tool = None; tools = {}; x = y = None
    for ln in io.open(path, encoding="latin-1"):
        ln = ln.strip()
        m = re.match(r"^T(\d+)F\d+S\d+C([\d.]+)", ln)
        if m:
            tools[int(m.group(1))] = float(m.group(2)); continue
        m = re.match(r"^T0*(\d+)$", ln)
        if m:
            tool = int(m.group(1)); continue
        m = re.match(r"^(?:G0[01])?(?:X(-?\d+))?(?:Y(-?\d+))?$", ln)
        if m and (m.group(1) or m.group(2)) and tool:
            if m.group(1):
                x = int(m.group(1).ljust(8, "0")) / 1e4 if not m.group(1).startswith("-") else -int(m.group(1)[1:].ljust(8, "0")) / 1e4
            if m.group(2):
                y = int(m.group(2).ljust(8, "0")) / 1e4
            if ln.startswith("G00") or ln.startswith("G01"):
                continue
            holes.append((x, y, tools.get(tool)))
    return holes, tools


if __name__ == "__main__":
    b = Board(BOARD)
    regions = json.load(io.open(os.path.join(HERE, "board_regions.json")))
    g = Grid(b, cutouts=[regions["cutout"]])
    res = dict(jlc=JLC, board_rules=BOARD_RULES, findings=[])
    F = res["findings"]
    # --- annular rings
    rings = [dict(kind="via", x=v["x"], y=v["y"], ring=(v["pad_d"] - v["drill_d"]) / 2, drill=v["drill_d"], pad=v["pad_d"]) for v in b.vias]
    for p in b.pads:
        if p["hole"]:
            rings.append(dict(kind="pad %s.%s" % (p["comp"], p["name"]), x=p["x"], y=p["y"], ring=(min(p["w"], p["h"]) - p["hole"]) / 2, drill=p["hole"], pad=min(p["w"], p["h"])))
    worst = sorted(rings, key=lambda r: r["ring"])[:5]
    res["annular_min"] = worst[0]
    print("annular ring: minimum %.3f mm (%s, drill %.2f pad %.2f); JLC minimum %.2f; %d holes" % (
        worst[0]["ring"], worst[0]["kind"], worst[0]["drill"], worst[0]["pad"], JLC["annular_min"], len(rings)))
    bad = [r for r in rings if r["ring"] < JLC["annular_min"] and not r["kind"].startswith("pad None")]
    if bad:
        F.append(dict(area="dfm", severity=2, title="%d holes with annular ring under %.2f mm" % (len(bad), JLC["annular_min"]), detail=str(bad[:5])))
    # --- track widths
    wmin = {}
    for lay in (1, 32, 2, 3):
        ws = [t["width"] for t in b.tracks if t["layer"] == lay]
        if ws:
            wmin[lay] = min(ws)
    res["track_min"] = wmin
    print("narrowest track per layer: %s (board rule %.3f, JLC %.2f)" % ({k: round(v, 3) for k, v in wmin.items()}, BOARD_RULES["width_min"], JLC["track_min"]))
    # --- per-net clearance per layer
    clear = {}
    for lay, nm in ((1, "Top"), (2, "Signal 1"), (3, "Signal 2"), (32, "Bottom")):
        rasters = {}
        for net in b.nets:
            im = copper_of(b, g, lay, nets={net}) & g.inb
            if im.any():
                rasters[net] = im
        best = (9e9, None, None)
        for net, im in rasters.items():
            others = np.zeros_like(im)
            for n2, im2 in rasters.items():
                if n2 != net:
                    others |= im2
            if not others.any():
                continue
            d = ndimage.distance_transform_edt(~others)
            dm = float(np.min(np.where(im, d, np.inf))) * g.pitch
            if dm < best[0]:
                r, c = np.unravel_index(np.argmin(np.where(im, d, np.inf)), d.shape)
                best = (dm, net, [round(v, 2) for v in g.mm(r, c)])
        clear[nm] = dict(mm=best[0], net=best[1], at=best[2])
        print("closest different-net copper on %-9s %.3f mm (%s at %s); board rule %.3f, JLC %.2f" % (nm, best[0], best[1], best[2], BOARD_RULES["clearance_min"], JLC["clearance_min"]))
    res["clearance"] = clear
    # --- copper to the routed edges
    slot = np.zeros((g.H, g.W), bool); fill(slot, [regions["cutout"]], g)
    to_slot = ndimage.distance_transform_edt(~slot) * g.pitch
    to_edge = ndimage.distance_transform_edt(g.outline) * g.pitch     # distance INSIDE the outline to its boundary
    edge = {}
    for lay, nm in ((1, "Top"), (2, "Signal 1"), (3, "Signal 2"), (32, "Bottom")):
        im = copper_of(b, g, lay) & g.inb
        edge[nm] = dict(to_slot=float(np.min(np.where(im, to_slot, np.inf))), to_outline=float(np.min(np.where(im, to_edge, np.inf))))
        print("copper to slot wall on %-9s %.3f mm, to outline %.3f mm (JLC copper-to-edge %.2f)" % (nm, edge[nm]["to_slot"], edge[nm]["to_outline"], JLC["copper_to_edge"]))
    res["copper_to_edge"] = edge
    if min(e["to_slot"] for e in edge.values()) < JLC["copper_to_edge"]:
        F.append(dict(area="dfm", severity=2, title="Pours come within %.2f mm of the barrier slot wall on every layer" % min(e["to_slot"] for e in edge.values()),
                      detail="JLC routed-edge copper clearance is 0.30 mm; a 0.2 mm setback can leave inner-layer copper exposed in the slot after routing tolerance", net=None))
    # --- drill file vs board holes
    txt = glob.glob(os.path.join(OUT, "NC Drill", "*RoundHoles.TXT"))[0]
    holes, tools = read_drill_txt(txt)
    slots, _ = read_drill_txt(glob.glob(os.path.join(OUT, "NC Drill", "*SlotHoles.TXT"))[0])
    bh = [(v["x"], v["y"], v["drill_d"]) for v in b.vias] + [(p["x"], p["y"], p["hole"]) for p in b.pads if p["hole"]]
    unmatched = []
    for x, y, d in holes:
        if not any(abs(x - bx) < 0.03 and abs(y - by) < 0.03 and abs(d - bd) < 0.02 for bx, by, bd in bh):
            unmatched.append((x, y, d))
    inside = sum(1 for x, y, d in holes if g.outline[int((y - g.oy) / g.pitch), int((x - g.ox) / g.pitch)])
    res["drill"] = dict(txt_holes=len(holes), board_holes=len(bh), unmatched=unmatched[:10], inside_outline=inside, tools=tools, slot_moves=len(slots))
    print("drill .TXT: %d round holes (board has %d incl. 142 vias), %d unmatched, %d inside the outline; tools %s" % (
        len(holes), len(bh), len(unmatched), inside, tools))
    if unmatched or len(holes) != len(bh) - 3:
        F.append(dict(area="fab-package", severity=2, title="drill file does not reconcile with the board holes", detail=str(unmatched[:5])))
    # --- outline file: stroked apertures inside the outline
    outl = io.open(glob.glob(os.path.join(OUT, "Gerber", "*.Outline"))[0], encoding="latin-1").read()
    aps = dict(re.findall(r"%ADD(\d+)C,([\d.]+)\*%", outl))
    wide = {k: float(v) for k, v in aps.items() if float(v) > 1.0}
    res["outline_apertures"] = aps
    print("Outline layer apertures: %s" % aps)
    if wide:
        F.append(dict(area="fab-package", severity=2, title="Barrier slot is drawn on the Outline layer as a %.1f mm stroked path, not a closed cut-out contour" % max(wide.values()),
                      detail="D%s C,%.1f: a fab reading the profile layer must interpret a wide stroke as a routed slot; the saved board carries it as a board cut-out region, so an ODB++/IPC-2581 export or a drawn contour removes the ambiguity" % (list(wide)[0], max(wide.values()))))
    gko = glob.glob(os.path.join(OUT, "Gerber", "*.GKO"))
    if gko:
        F.append(dict(area="fab-package", severity=2, title="A .GKO (keep-out) file with an 11.5 x 3.9 mm rectangle is in the fabrication set",
                      detail="fabs that take GKO as the profile when present would cut the wrong board; the keep-out region under U2 should not be output, or the file dropped from the order zip"))
    # --- fiducials and test points
    fids = [c for c in b.components if c["designator"].upper().startswith(("FD", "FID", "TP"))]
    res["fiducials"] = len(fids)
    if not fids:
        F.append(dict(area="dfm", severity=3, title="No fiducials and no test points on the board",
                      detail="a 95-part double-sided board going to machine assembly needs two or three fiducials per side; the only probe points are component pads"))
    # --- the shunt current path: pours NetJ2_1 / NetJ2_2 at 10 A (IPC-2221 external)
    pours = [p for p in b.pours if p["net"] in ("NetJ2_1", "NetJ2_2")]
    widths = {}
    for p in pours:
        xs = [x for c in p["contours"] for x, y in c]
        widths[p["net"]] = (max(xs) - min(xs))
    w_mm = min(widths.values()) if widths else float("nan")
    area_mil2 = (w_mm * 0.035) / (0.0254 ** 2)
    dT = (10.0 / (0.048 * area_mil2 ** 0.725)) ** (1 / 0.44)
    res["shunt_path"] = dict(pour_width_mm=w_mm, copper_um=35, i_a=10.0, ipc2221_rise_c=dT, note="IPC-2221 external conductor, 1 oz; the pours are top-layer only")
    print("shunt current path: narrowest J2 pour %.2f mm wide, 1 oz: IPC-2221 rise %.1f C at 10 A" % (w_mm, dT))
    if dT > 20:
        F.append(dict(area="thermal", severity=3, title="J2-to-shunt pours rise ~%.0f C at 10 A (IPC-2221, 1 oz, top only)" % dT,
                      detail="%.1f mm wide copper carrying 10 A; a second copper layer or 2 oz halves it" % w_mm, net="NetJ2_1"))
    io.open(os.path.join(HERE, "dfm_check.json"), "w", encoding="utf-8", newline="\n").write(json.dumps(res, indent=1))
    print("findings:", len(F)); [print("  ", f["severity"], f["title"]) for f in F]
    print("written -> dfm_check.json")
