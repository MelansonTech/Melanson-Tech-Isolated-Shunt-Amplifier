# -*- coding: utf-8 -*-
"""Isolation geometry of the Rev 3.1 board: creepage, clearance, the slot,
the inner-layer edge exposure, and the aluminium case.

Domains, by net:
  ISO      the measured side: GND_ISO, +5_ISO, the shunt and its sense
           nets, the Si8921 input nets, PSU1 secondary
  PRIMARY  everything else, which is the output side; the case is bonded to
           ISenseRTN through the SMA nut and so belongs here
  NC       PSU1 pins 12 and 14, netless - which side they belong to depends
           on the module's internal construction (see the datasheet note)
  HOLE     the free 3.5 mm plated hole at (21.75, 43.0), netless

What is computed, per copper layer:
  plane     straight-line distance between ISO and PRIMARY copper in the
            layer plane (air clearance on the outer layers; on inner layers
            it is through FR-4 and reported for information)
  creepage  geodesic along the outer surface, inside the board outline and
            around the slot (skimage MCP_Geometric, cost 1 on the surface,
            infinite in the slot and off the board)
  edge      inner-layer copper to the routed edges (outline and slot wall):
            a pour reaching the wall is exposed there
  rail      the case rails land on the left and right edges; for a groove
            engagement e the landing strip is x in [18.25, 18.25+e] and
            [68.25-e, 68.25]; creepage from ISO copper to the strip on each
            outer surface, and the straight-line distance to the strip edge

Standard figures (IEC 60664-1, stated as the assumptions they are):
  creepage  400 V working, PD2, material group IIIb (FR-4): 4.0 mm basic,
            8.0 mm reinforced (table F.5); 500 V: 5.0 / 10.0 mm
  clearance table F.2: 1.5 mm for 2.5 kV impulse (300 V system, OVC II),
            3.0 mm for 4 kV; basic. Reinforced takes the next impulse step.

    python isolation_geom.py
"""
import io
import json
import math
import os
import sys

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt                              # noqa: E402
from scipy import ndimage                                    # noqa: E402
from skimage.graph import MCP_Geometric                      # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from board_model import Board                                # noqa: E402
from raster import Grid, copper_of, disc, fill               # noqa: E402

PROJ = os.path.dirname(os.path.dirname(HERE))
BOARD = os.path.join(PROJ, "Revision 3", "MelansonTech Isolated Shunt Amplifier Rev3.CSPcbDoc")
FIG = os.path.join(PROJ, "docs", "design-review", "figures")

ISO_NETS = {"GND_ISO", "+5_ISO", "NetJ2_1", "NetJ2_2", "NetR5_3", "NetC41_1", "NetC41_2", "NetL3_2"}
LAYERS = [(1, "Top"), (2, "Signal 1"), (3, "Signal 2"), (32, "Bottom")]
OUTER = (1, 32)
X_LEFT, X_RIGHT = 18.25, 68.25
ENGAGE = [0.5, 1.0, 1.5, 2.0]
REQ = dict(creep_basic_400=4.0, creep_reinf_400=8.0, creep_basic_500=5.0,
           clear_2500V=1.5, clear_4000V=3.0)


def nearest(mask_from, mask_to, g):
    """Straight-line distance (mm) from mask_from to the nearest mask_to, with
    the points. EDT of the complement of mask_to, sampled on mask_from."""
    if not mask_from.any() or not mask_to.any():
        return None
    d, (ir, ic) = ndimage.distance_transform_edt(~mask_to, return_indices=True)
    dd = np.where(mask_from, d, np.inf)
    r, c = np.unravel_index(np.argmin(dd), dd.shape)
    r2, c2 = ir[r, c], ic[r, c]
    return dict(mm=float(dd[r, c] * g.pitch), a=[round(v, 2) for v in g.mm(r, c)], b=[round(v, 2) for v in g.mm(r2, c2)])


def geodesic(seed, target, g, surface):
    """Shortest path along the surface from any seed pixel to any target
    pixel. Returns mm, the end points and the path."""
    if not seed.any() or not target.any():
        return None
    cost = np.where(surface, 1.0, np.inf)
    mcp = MCP_Geometric(cost, fully_connected=True)
    starts = list(zip(*np.nonzero(seed & surface)))
    if not starts:
        return None
    cum, _ = mcp.find_costs(starts)
    dd = np.where(target & surface, cum, np.inf)
    if not np.isfinite(dd).any():
        return dict(mm=None, note="no surface path (domains separated by the slot or the edge)")
    r, c = np.unravel_index(np.argmin(dd), dd.shape)
    path = mcp.traceback((r, c))
    pts = [g.mm(pr, pc) for pr, pc in path]
    return dict(mm=float(dd[r, c] * g.pitch), a=[round(v, 2) for v in pts[0]], b=[round(v, 2) for v in pts[-1]],
                path=[[round(x, 3), round(y, 3)] for x, y in pts[::4]])


if __name__ == "__main__":
    b = Board(BOARD)
    regions = json.load(io.open(os.path.join(HERE, "board_regions.json")))
    g = Grid(b, cutouts=[regions["cutout"]])
    slot = np.zeros((g.H, g.W), bool)
    fill(slot, [regions["cutout"]], g)
    surface = g.inb
    primary_nets = {n for n in b.nets if n not in ISO_NETS}
    nc_pads = [p for p in b.pads if p["comp"] == "PSU1" and p["net"] is None]
    hole_pads = [p for p in b.pads if p["comp"] is None]
    out = dict(iso_nets=sorted(ISO_NETS), primary_nets=sorted(primary_nets), pitch=g.pitch, layers={},
               requirements=REQ, rail={}, hole={}, nc={})
    dom = {}
    for lay, nm in LAYERS:
        iso = copper_of(b, g, lay, nets=ISO_NETS)
        pri = copper_of(b, g, lay, nets=primary_nets)
        dom[lay] = (iso, pri)
        row = dict(iso_mm2=float(iso.sum() * g.pitch ** 2), pri_mm2=float(pri.sum() * g.pitch ** 2))
        row["plane"] = nearest(iso, pri, g)
        # edge exposure: copper to the slot wall and to the outer edge
        to_slot = ndimage.distance_transform_edt(~slot) * g.pitch
        outside = ~g.outline
        to_edge = ndimage.distance_transform_edt(~outside) * g.pitch
        for dn, m in (("iso", iso), ("pri", pri)):
            row["%s_to_slot_mm" % dn] = float(np.min(np.where(m, to_slot, np.inf))) if m.any() else None
            row["%s_to_edge_mm" % dn] = float(np.min(np.where(m, to_edge, np.inf))) if m.any() else None
        if lay in OUTER:
            row["creepage"] = geodesic(iso, pri, g, surface)
        out["layers"][nm] = row
        print("%-9s iso %7.1f mm2  pri %7.1f mm2  plane %.3f mm at %s-%s   iso->slot %.3f  pri->slot %.3f  iso->edge %.3f  pri->edge %.3f" % (
            nm, row["iso_mm2"], row["pri_mm2"], row["plane"]["mm"], row["plane"]["a"], row["plane"]["b"],
            row["iso_to_slot_mm"], row["pri_to_slot_mm"], row["iso_to_edge_mm"], row["pri_to_edge_mm"]))
        if lay in OUTER and row["creepage"]:
            print("          surface creepage %s mm  %s -> %s" % (
                "%.3f" % row["creepage"]["mm"] if row["creepage"].get("mm") else "none", row["creepage"].get("a"), row["creepage"].get("b")))

    # --- the case rails ---------------------------------------------------
    xs = np.array([g.mm(0, c)[0] for c in range(g.W)])
    for e in ENGAGE:
        strip = np.zeros((g.H, g.W), bool)
        strip[:, (xs >= X_LEFT) & (xs <= X_LEFT + e)] = True
        strip[:, (xs >= X_RIGHT - e) & (xs <= X_RIGHT)] = True
        strip &= g.outline
        res = {}
        for lay in OUTER:
            iso, pri = dom[lay]
            res["creep_%d" % lay] = geodesic(iso, strip, g, surface)
            res["clear_%d" % lay] = nearest(iso, strip, g)
        out["rail"]["e_%.1f" % e] = res
        print("rail e=%.1f mm: creepage top %s  bottom %s | straight top %.3f bottom %.3f" % (
            e, "%.3f" % res["creep_1"]["mm"] if res["creep_1"] and res["creep_1"].get("mm") else "n/a",
            "%.3f" % res["creep_32"]["mm"] if res["creep_32"] and res["creep_32"].get("mm") else "n/a",
            res["clear_1"]["mm"], res["clear_32"]["mm"]))
    # the inner-layer ISO copper's distance to the left/right edges (exposed at the routed edge if < ~0.2 mm)
    for lay, nm in LAYERS:
        iso, pri = dom[lay]
        for side, xe in (("left", X_LEFT), ("right", X_RIGHT)):
            cols = np.abs(xs - xe) < g.pitch
            dist = np.abs(xs[None, :] - xe)
            out["layers"][nm]["iso_to_%s_edge_mm" % side] = float(np.min(np.where(iso, dist, np.inf))) if iso.any() else None
            out["layers"][nm]["pri_to_%s_edge_mm" % side] = float(np.min(np.where(pri, dist, np.inf))) if pri.any() else None

    # --- the free hole and the NC pins -----------------------------------
    hole = np.zeros((g.H, g.W), bool)
    for p in hole_pads:
        disc(hole, p["x"], p["y"], max(p["w"], p["hole"]), g)
    out["hole"]["pads"] = [dict(x=p["x"], y=p["y"], w=p["w"], h=p["h"], hole=p["hole"]) for p in hole_pads]
    nc = np.zeros((g.H, g.W), bool)
    for p in nc_pads:
        from raster import pad_shape
        pad_shape(nc, p, g)
    for lay, nm in LAYERS:
        iso, pri = dom[lay]
        out["hole"][nm] = dict(to_iso=nearest(hole, iso, g), to_pri=nearest(hole, pri, g))
        if lay == 32:
            out["nc"][nm] = dict(to_iso=nearest(nc, iso, g), to_pri=nearest(nc, pri, g),
                                 creep_to_iso=geodesic(nc, iso, g, surface), creep_to_pri=geodesic(nc, pri, g, surface))
    print("free 3.5 mm hole: nearest ISO %s mm, nearest PRIMARY %s mm (top)" % (
        round(out["hole"]["Top"]["to_iso"]["mm"], 3), round(out["hole"]["Top"]["to_pri"]["mm"], 3)))
    print("PSU1 NC pins 12/14 (bottom): to ISO %.3f mm straight / %s creep; to PRIMARY %.3f mm straight / %s creep" % (
        out["nc"]["Bottom"]["to_iso"]["mm"], out["nc"]["Bottom"]["creep_to_iso"].get("mm"),
        out["nc"]["Bottom"]["to_pri"]["mm"], out["nc"]["Bottom"]["creep_to_pri"].get("mm")))

    # --- figures -----------------------------------------------------------
    os.makedirs(FIG, exist_ok=True)
    fig, axs = plt.subplots(2, 2, figsize=(9.0, 9.4))
    for (lay, nm), ax in zip(LAYERS, axs.ravel()):
        iso, pri = dom[lay]
        img = np.ones((g.H, g.W, 3))
        img[~g.outline] = (0.97, 0.97, 0.97)
        img[pri] = (0.55, 0.65, 0.95)
        img[iso] = (0.95, 0.45, 0.35)
        img[slot] = (0.15, 0.15, 0.15)
        img[hole] = (0.2, 0.7, 0.2)
        if lay == 32:
            img[nc] = (0.9, 0.75, 0.1)
        ax.imshow(img, origin="lower", extent=g.extent(), interpolation="nearest")
        row = out["layers"][nm]
        if lay in OUTER and row["creepage"] and row["creepage"].get("path"):
            pth = np.array(row["creepage"]["path"])
            ax.plot(pth[:, 0], pth[:, 1], "k-", lw=1.2)
            ax.set_title("%s: creepage %.2f mm (black path)" % (nm, row["creepage"]["mm"]), fontsize=9)
        else:
            ax.set_title("%s: ISO/PRIMARY plane gap %.2f mm" % (nm, row["plane"]["mm"]), fontsize=9)
        pl = row["plane"]
        ax.plot([pl["a"][0], pl["b"][0]], [pl["a"][1], pl["b"][1]], "g-", lw=1.0)
        for e in (1.0,):
            ax.axvspan(X_LEFT, X_LEFT + e, color="gold", alpha=0.35, lw=0)
            ax.axvspan(X_RIGHT - e, X_RIGHT, color="gold", alpha=0.35, lw=0)
        ax.set_xlabel("x mm", fontsize=8); ax.set_ylabel("y mm", fontsize=8); ax.tick_params(labelsize=7)
    fig.suptitle("Isolation domains per layer: red = measured side, blue = output side, black = slot, gold = case rail landing (1 mm)", fontsize=9)
    fig.tight_layout()
    fig.savefig(os.path.join(FIG, "isolation-domains.png"), dpi=110)

    # creepage distance map on the top surface
    iso, pri = dom[1]
    cost = np.where(surface, 1.0, np.inf)
    mcp = MCP_Geometric(cost, fully_connected=True)
    cum, _ = mcp.find_costs(list(zip(*np.nonzero(iso & surface))))
    cum = cum * g.pitch
    fig2, ax = plt.subplots(figsize=(8.0, 7.6))
    m = np.ma.masked_where(~surface, np.minimum(cum, 12.0))
    im = ax.imshow(m, origin="lower", extent=g.extent(), cmap="viridis", vmin=0, vmax=12)
    ax.contour(np.where(surface, cum, 99), levels=[4.0, 8.0], colors=["white", "orange"], linewidths=0.8, extent=g.extent(), origin="lower")
    ax.imshow(np.ma.masked_where(~pri, pri), origin="lower", extent=g.extent(), cmap="Greys", alpha=0.55, vmin=0, vmax=1)
    cr = out["layers"]["Top"]["creepage"]
    if cr and cr.get("path"):
        pth = np.array(cr["path"]); ax.plot(pth[:, 0], pth[:, 1], "r-", lw=1.5, label="shortest creepage %.2f mm" % cr["mm"])
    ax.legend(loc="upper right", fontsize=8)
    fig2.colorbar(im, ax=ax, label="surface distance from measured-side copper, mm (white 4.0, orange 8.0)")
    ax.set_title("Top surface: creepage distance from the measured side; grey = output-side copper", fontsize=9)
    ax.set_xlabel("x mm", fontsize=8); ax.set_ylabel("y mm", fontsize=8); ax.tick_params(labelsize=7)
    fig2.tight_layout()
    fig2.savefig(os.path.join(FIG, "isolation-creepage-top.png"), dpi=110)
    io.open(os.path.join(HERE, "isolation_geom.json"), "w", encoding="utf-8", newline="\n").write(json.dumps(out, indent=1))
    print("written -> isolation_geom.json, figures/isolation-domains.png, figures/isolation-creepage-top.png")
