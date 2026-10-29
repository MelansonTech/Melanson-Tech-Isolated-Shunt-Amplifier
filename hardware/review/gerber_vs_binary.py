# -*- coding: utf-8 -*-
"""Gate: do the fabrication Gerbers carry the copper the saved board carries?

CircuitStudio writes outputs from the in-memory document. On this project the
board was saved 2026-08-20 20:37 and the outputs written 20:43, so the two
could differ by six minutes of editing. Every geometric result of the review
is computed from the binary; this settles with a number whether that is the
same copper the fab received.

Both are rasterised on the same grid (raster.PITCH) and compared per copper
layer. Distributed one-pixel halos are the two rasterisers disagreeing about
aperture edges; a localised block is a real edit, and the largest blobs of
each one-sided difference are listed with their position so it can be looked
at.

    python gerber_vs_binary.py
"""
import glob
import io
import json
import os
import sys

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt                              # noqa: E402
from scipy import ndimage                                    # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from board_model import Board                                # noqa: E402
from raster import Grid, copper_of, fill, disc, rect, stroke, label_blobs  # noqa: E402

PROJ = os.path.dirname(os.path.dirname(HERE))
REV = os.path.join(PROJ, "Revision 3")
BOARD = os.path.join(REV, "MelansonTech Isolated Shunt Amplifier Rev3.CSPcbDoc")
GERBER = os.path.join(REV, "Default Configuration", "Outputs", "Gerber")
FIG = os.path.join(PROJ, "docs", "design-review", "figures")
LAYERS = [("GTL", 1, "Top"), ("G1", 2, "Signal 1"), ("G2", 3, "Signal 2"), ("GBL", 32, "Bottom")]


def gerber_layer(ext, g):
    from gerbonara.rs274x import GerberFile
    f = glob.glob(os.path.join(GERBER, "*." + ext))[0]
    gf = GerberFile.open(f)
    im = np.zeros((g.H, g.W), bool)
    n_arc = 0
    for o in gf.objects:
        for pr in o.to_primitives(unit="mm"):
            name = type(pr).__name__
            dark = getattr(pr, "polarity_dark", True)
            tmp = np.zeros_like(im)
            if name == "Circle":
                disc(tmp, pr.x, pr.y, 2 * pr.r, g)
            elif name == "Rectangle":
                rect(tmp, pr.x, pr.y, pr.w, pr.h, g, pr.rotation or 0.0)
            elif name == "Line":
                stroke(tmp, pr.x1, pr.y1, pr.x2, pr.y2, pr.width, g)
            elif name == "ArcPoly":
                # pour cut-outs round vias and pads are arcs; chording them
                # shrinks every hole and the Gerber copper reads 100 mm2 too
                # large. Sample the arcs to 5 um first.
                if any(a is not None for a in pr.arc_centers):
                    n_arc += 1
                    pr = pr.approximate_arcs(max_error=0.005)
                fill(tmp, [list(pr.outline)], g)
            else:
                continue
            if dark:
                im |= tmp
            else:
                im &= ~tmp
    return im, os.path.basename(f), n_arc


if __name__ == "__main__":
    b = Board(BOARD)
    cut = json.load(io.open(os.path.join(HERE, "board_regions.json")))["cutout"]
    g = Grid(b, cutouts=[cut])
    px = g.pitch ** 2
    print("grid %d x %d at %.3f mm; board area %.1f mm2 (outline minus slot)" % (g.W, g.H, g.pitch, g.inb.sum() * px))
    print("  %-10s %-11s %-11s %-11s %-11s %-7s" % ("layer", "binary mm2", "gerber mm2", "only bin", "only grb", "IoU"))
    out = {}
    fig, axs = plt.subplots(2, 2, figsize=(9.0, 9.4))
    for (ext, lay, nm), ax in zip(LAYERS, axs.ravel()):
        bb = copper_of(b, g, lay) & g.inb
        gg, fname, n_arc = gerber_layer(ext, g)
        gg &= g.inb
        only_b = bb & ~gg
        only_g = gg & ~bb
        iou = float((bb & gg).sum()) / max(1, float((bb | gg).sum()))
        core_b = ndimage.binary_erosion(only_b, iterations=1)
        core_g = ndimage.binary_erosion(only_g, iterations=1)
        # CircuitStudio removes unused inner-layer pads of vias and
        # through-hole parts from the Gerbers; the binary model draws every
        # via and multi-layer pad on every layer. Binary-only copper that sits
        # on a via or through-hole pad on an inner layer is that option, not
        # an edit, and is reported apart.
        pads_vias = copper_of(b, g, lay, pours=False, tracks=False) & g.inb
        unused = core_b & pads_vias if lay in (2, 3) else np.zeros_like(core_b)
        resid_b = core_b & ~unused
        row = dict(file=fname, binary_mm2=float(bb.sum() * px), gerber_mm2=float(gg.sum() * px),
                   only_binary_mm2=float(only_b.sum() * px), only_gerber_mm2=float(only_g.sum() * px),
                   only_binary_core_mm2=float(core_b.sum() * px), only_gerber_core_mm2=float(core_g.sum() * px),
                   unused_inner_pads_mm2=float(unused.sum() * px), only_binary_residual_mm2=float(resid_b.sum() * px),
                   iou=iou, arc_polys=n_arc,
                   blobs_only_binary=label_blobs(resid_b, g), blobs_only_gerber=label_blobs(core_g, g))
        out[nm] = row
        print("  %-10s %-11.1f %-11.1f %-11.2f %-11.2f %.4f   core: bin %.2f (unused inner pads %.2f, residual %.2f)  grb %.2f mm2" %
              (nm, row["binary_mm2"], row["gerber_mm2"], row["only_binary_mm2"], row["only_gerber_mm2"], iou,
               row["only_binary_core_mm2"], row["unused_inner_pads_mm2"], row["only_binary_residual_mm2"], row["only_gerber_core_mm2"]))
        img = np.zeros((g.H, g.W, 3), float) + 1.0
        img[bb & gg] = (0.75, 0.75, 0.75)
        img[only_b] = (0.85, 0.1, 0.1)
        img[only_g] = (0.1, 0.2, 0.9)
        img[~g.inb] = (0.97, 0.97, 0.97)
        ax.imshow(img, origin="lower", extent=g.extent(), interpolation="nearest")
        ax.set_title("%s: red = binary only, blue = Gerber only" % nm, fontsize=9)
        ax.set_xlabel("x mm", fontsize=8); ax.set_ylabel("y mm", fontsize=8)
        ax.tick_params(labelsize=7)
    worst = max(max(v["only_binary_residual_mm2"], v["only_gerber_core_mm2"]) for v in out.values())
    print()
    verdict = "agree" if worst < 8.0 else "DISAGREE"      # 8 mm2 is under 0.5 % of a layer, and distributed
    print("  largest one-sided difference after removing edge halos: %.2f mm2 -> the two %s" % (worst, verdict))
    out["_verdict"] = dict(worst_core_mm2=worst, agree=(verdict == "agree"), pitch_mm=g.pitch,
                           board_saved="2026-08-20 20:37", outputs_written="2026-08-20 20:43")
    os.makedirs(FIG, exist_ok=True)
    fig.suptitle("Fabrication Gerbers against the saved board, per copper layer", fontsize=10)
    fig.tight_layout()
    fig.savefig(os.path.join(FIG, "gerber-vs-binary.png"), dpi=110)
    io.open(os.path.join(HERE, "gerber_vs_binary.json"), "w", encoding="utf-8", newline="\n").write(json.dumps(out, indent=1))
    print("written -> gerber_vs_binary.json, figures/gerber-vs-binary.png")
