# -*- coding: utf-8 -*-
"""3-D steady-state thermal solve on the real copper distribution.

Each copper layer is a slab whose in-plane conductivity in every 0.5 mm cell
is the measured copper fraction of that cell (rasterised from the board file
through raster.py) times copper, plus FR-4 for the rest; dielectric slabs
are FR-4. The stack used is the JLC 4-layer 1.6 mm build (0.21 / 1.065 /
0.21 mm, 1 oz outer, 0.5 oz inner), because the board file's own stackup
(1.524 mm between top and the first plane) is not a fabricated one; the
difference moves the hottest part by under 2 C either way (sweep in __main__).

Dissipations come from power_budget.json (which names its sources); the
shunt at 10 A adds 1.0 W.

Cases:
  open      bare board in still air, both faces to ambient, h = 10 W/m2K
            (natural convection plus radiation, EST)
  case      in the 50 x 58 x 24 mm aluminium case: faces to the case
            interior at h = 5 W/m2K, edges to the rails through a contact
            conductance, the case to ambient at 12 W/m2K over its outer
            area; the case temperature is the lumped balance

Validation (printed first): a uniformly heated plate against P/(2 h A), and
the energy balance of every solve.

    python thermal.py
"""
import io
import json
import os
import sys

import numpy as np
from scipy import ndimage
from scipy.sparse import coo_matrix, csr_matrix
from scipy.sparse.linalg import spsolve
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt                              # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from board_model import Board                                # noqa: E402
from raster import Grid, copper_of                           # noqa: E402

PROJ = os.path.dirname(os.path.dirname(HERE))
BOARD = os.path.join(PROJ, "Revision 3", "MelansonTech Isolated Shunt Amplifier Rev3.CSPcbDoc")
FIG = os.path.join(PROJ, "docs", "design-review", "figures")
PITCH = 0.5e-3
K_CU, K_FR4 = 385.0, 0.3
H_OPEN, H_IN, H_EXT = 10.0, 5.0, 12.0
H_CONTACT = 1500.0            # W/m2K, anodised aluminium on FR-4 edge, light load (EST)
ENGAGE = 1.0e-3               # rail engagement, m
A_CASE = 2 * (0.058 * 0.050 + 0.024 * 0.050 + 0.058 * 0.024)
# slabs top to bottom: (kind, thickness m, layer byte or None)
STACK = [("cu", 35e-6, 1), ("di", 0.21e-3, None), ("cu", 17.5e-6, 2), ("di", 1.065e-3, None),
         ("cu", 17.5e-6, 3), ("di", 0.21e-3, None), ("cu", 35e-6, 32)]
STACK_FILE = [("cu", 35.6e-6, 1), ("di", 1.524e-3, None), ("cu", 17.8e-6, 2), ("di", 0.254e-3, None),
              ("cu", 17.8e-6, 3), ("di", 0.254e-3, None), ("cu", 35.6e-6, 32)]


def copper_fractions(b, g, nx, ny, sub):
    out = {}
    for lay in (1, 2, 3, 32):
        im = copper_of(b, g, lay) & g.inb
        im = im[:ny * sub, :nx * sub].reshape(ny, sub, nx, sub).mean(axis=(1, 3))
        out[lay] = im
    inb = g.inb[:ny * sub, :nx * sub].reshape(ny, sub, nx, sub).mean(axis=(1, 3)) > 0.5
    return out, inb


WIRE_MM2 = 2.5                # the 10 A leads at J2, copper cross-section (EST: 2.5 mm2 PVC, OD 3 mm)
WIRE_OD_MM = 3.0


def wire_fin_conductance(mm2=WIRE_MM2, od_mm=WIRE_OD_MM, h=H_OPEN):
    """A long lead is a fin: G = sqrt(h P k A), W/K, per lead."""
    import math
    P = math.pi * od_mm * 1e-3
    A = mm2 * 1e-6
    return math.sqrt(h * P * K_CU * A)


def build(frac, inb, stack, sources, case, t_case_rel=0.0, wires=None):
    """Assemble and solve. sources: {(iz, iy, ix): W}. Returns T (nz, ny, nx) relative to ambient."""
    nz = len(stack); ny, nx = inb.shape
    N = nz * ny * nx
    idx = lambda iz, iy, ix: (iz * ny + iy) * nx + ix
    rows, cols, vals = [], [], []
    diag = np.zeros(N)
    rhs = np.zeros(N)

    def add(a, bb, G):
        rows.extend([a, bb]); cols.extend([bb, a]); vals.extend([-G, -G])
        diag[a] += G; diag[bb] += G

    k_xy = np.zeros((nz, ny, nx)); k_z = np.zeros((nz, ny, nx)); t = np.zeros(nz)
    for iz, (kind, th, lay) in enumerate(stack):
        t[iz] = th
        if kind == "cu":
            f = frac[lay]
            k_xy[iz] = f * K_CU + (1 - f) * K_FR4
            k_z[iz] = f * K_CU + (1 - f) * K_FR4
        else:
            k_xy[iz] = K_FR4; k_z[iz] = K_FR4
    for iz in range(nz):
        for iy in range(ny):
            for ix in range(nx):
                if not inb[iy, ix]:
                    continue
                a = idx(iz, iy, ix)
                if ix + 1 < nx and inb[iy, ix + 1]:
                    k = 2 * k_xy[iz, iy, ix] * k_xy[iz, iy, ix + 1] / (k_xy[iz, iy, ix] + k_xy[iz, iy, ix + 1])
                    add(a, idx(iz, iy, ix + 1), k * t[iz])
                if iy + 1 < ny and inb[iy + 1, ix]:
                    k = 2 * k_xy[iz, iy, ix] * k_xy[iz, iy + 1, ix] / (k_xy[iz, iy, ix] + k_xy[iz, iy + 1, ix])
                    add(a, idx(iz, iy + 1, ix), k * t[iz])
                if iz + 1 < nz:
                    R = 0.5 * t[iz] / k_z[iz, iy, ix] + 0.5 * t[iz + 1] / k_z[iz + 1, iy, ix]
                    add(a, idx(iz + 1, iy, ix), PITCH ** 2 / R)
    # boundary: faces
    h_face = H_OPEN if case == "open" else H_IN
    face_G = h_face * PITCH ** 2
    for iy in range(ny):
        for ix in range(nx):
            if inb[iy, ix]:
                for iz in (0, nz - 1):
                    a = idx(iz, iy, ix); diag[a] += face_G; rhs[a] += face_G * t_case_rel
    # rails: edge cells on the left and right outline edges, every slab
    if case == "case":
        edge = inb & ~ndimage.binary_erosion(inb, iterations=1)
        xs_edge = np.zeros_like(inb)
        xs_edge[:, :2] = True; xs_edge[:, -2:] = True
        for iz in range(nz):
            for iy in range(ny):
                for ix in range(nx):
                    if edge[iy, ix] and xs_edge[iy, ix]:
                        G = H_CONTACT * t[iz] * PITCH
                        a = idx(iz, iy, ix); diag[a] += G; rhs[a] += G * t_case_rel
    # the 10 A leads: a fin conductance to ambient at each J2 pad cell, both outer slabs
    if wires:
        for (iy, ix), G in wires.items():
            for iz in (0, nz - 1):
                a = idx(iz, iy, ix); diag[a] += G / 2
    for (iz, iy, ix), p in sources.items():
        rhs[idx(iz, iy, ix)] += p
    rows.extend(range(N)); cols.extend(range(N)); vals.extend(diag)
    # cells outside the board: pin to 0 so the matrix is non-singular
    out = ~inb
    for iz in range(nz):
        for iy, ix in zip(*np.nonzero(out)):
            a = idx(iz, iy, ix)
            if diag[a] == 0:
                rows.append(a); cols.append(a); vals.append(1.0)
    A = csr_matrix(coo_matrix((vals, (rows, cols)), shape=(N, N)))
    T = spsolve(A, rhs)
    return T.reshape(nz, ny, nx), face_G


def place_sources(b, g, nx, ny, sub, stack, powers):
    """Spread each part's power over the cells under its pads (+0.5 mm), on its side's copper slab."""
    src = {}
    top_iz = 0; bot_iz = len(stack) - 1
    comps = {c["designator"]: c for c in b.components}
    for ref, p in powers.items():
        if p <= 0:
            continue
        pads = [q for q in b.pads if q["comp"] == ref]
        if not pads:
            continue
        xs = [q["x"] for q in pads]; ys = [q["y"] for q in pads]
        x0, x1 = min(xs) - 0.5, max(xs) + 0.5; y0, y1 = min(ys) - 0.5, max(ys) + 0.5
        iz = bot_iz if comps[ref]["side"] == "BOTTOM" else top_iz
        cells = []
        for iy in range(ny):
            for ix in range(nx):
                x, y = g.mm(iy * sub + sub / 2, ix * sub + sub / 2)
                if x0 <= x <= x1 and y0 <= y <= y1:
                    cells.append((iz, iy, ix))
        if not cells:
            continue
        for c in cells:
            src[c] = src.get(c, 0.0) + p / len(cells)
    return src


if __name__ == "__main__":
    b = Board(BOARD)
    regions = json.load(io.open(os.path.join(HERE, "board_regions.json")))
    g = Grid(b, cutouts=[regions["cutout"]], margin=0.0)
    sub = int(round(PITCH / (g.pitch * 1e-3)))
    ny, nx = g.H // sub, g.W // sub
    frac, inb = copper_fractions(b, g, nx, ny, sub)
    area = inb.sum() * PITCH ** 2
    print("grid %d x %d at %.1f mm, board area %.1f cm2, copper fractions: %s" % (
        nx, ny, PITCH * 1e3, area * 1e4, {k: round(float(v[inb].mean()), 2) for k, v in frac.items()}))
    # --- validation: uniform 1 W over the plate, open case
    src_u = {(0, iy, ix): 1.0 / inb.sum() for iy, ix in zip(*np.nonzero(inb))}
    Tu, fG = build(frac, inb, STACK, src_u, "open")
    tmean = float(Tu[0][inb].mean()); tref = 1.0 / (2 * H_OPEN * area)
    loss = float(fG * (Tu[0][inb].sum() + Tu[-1][inb].sum()))
    print("validation: uniform 1 W -> mean rise %.2f C vs P/(2hA) = %.2f C (%.1f %%); convective loss %.3f W of 1.000 W" % (
        tmean, tref, 100 * (tmean / tref - 1), loss))
    pb = json.load(io.open(os.path.join(HERE, "power_budget.json")))
    cases = {}
    results = {"validation": dict(uniform_mean_rise=tmean, closed_form=tref, loss_w=loss), "cases": {}}
    for label, key, i_shunt in (("15 V x100, 10 A", "x100_15.0", 10.0), ("16 V x10, 10 A", "x10_16.0", 10.0), ("15 V x100, 0 A", "x100_15.0", 0.0)):
        d = pb["cases"][key]["diss_w"]
        powers = dict(d)
        powers["R5"] = 0.010 * i_shunt ** 2
        src = place_sources(b, g, nx, ny, sub, STACK, powers)
        ptot = sum(src.values())
        # J2 pad cells for the lead fins
        j2 = {}
        for q in b.pads:
            if q["comp"] == "J2":
                cells = [(iy, ix) for iy in range(ny) for ix in range(nx)
                         if abs(g.mm(iy * sub + sub / 2, ix * sub + sub / 2)[0] - q["x"]) <= 1.3 and abs(g.mm(iy * sub + sub / 2, ix * sub + sub / 2)[1] - q["y"]) <= 1.3 and inb[iy, ix]]
                for c in cells:
                    j2[c] = wire_fin_conductance() / len(cells)
        for case in ("open", "case", "open+leads", "case+leads"):
            for ta in (25.0, 40.0):
                wires = j2 if case.endswith("+leads") else None
                base = case.split("+")[0]
                if i_shunt == 0 and wires:
                    continue
                tcase_rel = ptot / (H_EXT * A_CASE) if base == "case" else 0.0
                T, fG = build(frac, inb, STACK, src, base, tcase_rel, wires=wires)
                hot = {}
                for ref in ("U6", "U1", "R5", "Rel1", "PSU1", "U2", "R6", "D3"):
                    cells = [c for c in src if c in src and True]
                    pads = [q for q in b.pads if q["comp"] == ref]
                    xs = [q["x"] for q in pads]; ys = [q["y"] for q in pads]
                    vals = []
                    for iy in range(ny):
                        for ix in range(nx):
                            x, y = g.mm(iy * sub + sub / 2, ix * sub + sub / 2)
                            if min(xs) - 0.5 <= x <= max(xs) + 0.5 and min(ys) - 0.5 <= y <= max(ys) + 0.5 and inb[iy, ix]:
                                vals.append(max(T[0, iy, ix], T[-1, iy, ix]))
                    hot[ref] = ta + (max(vals) if vals else float("nan"))
                tag = "%s | %s | Ta %.0f" % (label, case, ta)
                results["cases"][tag] = dict(label=label, case=case, ta=ta, p_total=ptot, t_case=ta + tcase_rel, hotspots=hot, wire_fin_w_per_k=(wire_fin_conductance() if wires else 0.0),
                                             board_max=ta + float(T[0][inb].max()), board_mean=ta + float(T[0][inb].mean()))
                print("%-32s P %.2f W  case %.1f C  board max %.1f mean %.1f | U6 %.1f  R5 %.1f  Rel1 %.1f  PSU1 %.1f  U1 %.1f  U2 %.1f" % (
                    tag, ptot, ta + tcase_rel, ta + T[0][inb].max(), ta + T[0][inb].mean(), hot["U6"], hot["R5"], hot["Rel1"], hot["PSU1"], hot["U1"], hot["U2"]))
                if label.startswith("16 V") and case == "case+leads" and ta == 40.0:
                    fig, ax = plt.subplots(figsize=(7.0, 6.2))
                    m = np.ma.masked_where(~inb, np.maximum(T[0], T[-1]) + ta)
                    ext = [g.ox, g.ox + nx * PITCH * 1e3, g.oy, g.oy + ny * PITCH * 1e3]
                    im = ax.imshow(m, origin="lower", extent=ext, cmap="inferno")
                    fig.colorbar(im, ax=ax, label="C")
                    for ref in ("U6", "R5", "Rel1", "PSU1", "U1"):
                        c = next(cc for cc in b.components if cc["designator"] == ref)
                        ax.annotate("%s %.0f C" % (ref, hot[ref]), (c["x"], c["y"]), color="white", fontsize=8)
                    ax.set_title("Outer-face temperature, 16 V x10, 10 A, aluminium case, 40 C ambient, 2.5 mm2 leads as fins", fontsize=9)
                    ax.set_xlabel("x mm"); ax.set_ylabel("y mm")
                    fig.tight_layout(); fig.savefig(os.path.join(FIG, "thermal-map.png"), dpi=110)
    # stack sensitivity: the file's own stackup, worst case
    d = pb["cases"]["x10_16.0"]["diss_w"]; powers = dict(d); powers["R5"] = 1.0
    src = place_sources(b, g, nx, ny, sub, STACK_FILE, powers)
    T, _ = build(frac, inb, STACK_FILE, src, "case", sum(src.values()) / (H_EXT * A_CASE), wires=j2)
    results["stack_sensitivity_file_stackup_board_max_rise"] = float(T[0][inb].max())
    results["wire_fin_w_per_k"] = wire_fin_conductance()
    print("file stackup (1.524 mm core under top) instead of the JLC stack: board max rise %.1f C vs %.1f C" % (
        T[0][inb].max(), results["cases"]["16 V x10, 10 A | case+leads | Ta 40"]["board_max"] - 40.0))
    io.open(os.path.join(HERE, "thermal.json"), "w", encoding="utf-8", newline="\n").write(json.dumps(results, indent=1))
    print("written -> thermal.json, figures/thermal-map.png")
