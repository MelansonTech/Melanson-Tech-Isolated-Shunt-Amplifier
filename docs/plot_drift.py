#!/usr/bin/env python3
"""
Expected drift versus ambient temperature — MelansonTech Isolated Shunt Amplifier Rev 2.

Assumes the board is zero-trimmed (R28) and gain-corrected at 23 C, then the ambient
moves. Everything plotted is what happens AFTER that point: static offset and initial
tolerance are gone, so these curves are drift only.

    python3 plot_drift.py            # writes drift-vs-temperature.svg and .png

Inputs mirror docs/Tolerance Budget - Isolated Shunt Amplifier Rev 2.xlsx.
"""
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import MultipleLocator

# ── palette (validated: node validate_palette.js "#2a78d6,#eb6834,#1baf7a,#eda100" --mode light)
S1, S2, S3, S4 = "#2a78d6", "#eb6834", "#1baf7a", "#eda100"
SURFACE, INK, INK2, INK3 = "#fcfcfb", "#0b0b0b", "#52514e", "#8a8880"
GRID, BAND = "#e6e5e1", "#eef2f7"

TRIM_C, SHUNT = 23.0, 0.010
T = np.linspace(0, 40, 401)
dT = np.abs(T - TRIM_C)

# ── gain drift, % of reading ────────────────────────────────────────────────
gain = {
    "Shunt TCR, 50 ppm/°C":       (0.005   * dT, S2),
    "U3 TCR mismatch, 35 ppm/°C": (0.0035  * dT, S3),
    "Si8921 gain drift, 24 ppm/°C": (0.0024 * dT, S4),
}
gain_rss = np.sqrt(sum(v**2 for v, _ in gain.values()))
gain_sum = sum(v for v, _ in gain.values())

# ── zero drift, mA referred to the input ───────────────────────────────────
# Referring each term back through its own gain makes these identical on both
# ranges — a useful property of the range plan, not a coincidence.
mA = lambda volts_at_input: volts_at_input / SHUNT * 1000
zero = {
    "Si8921 Vos drift, 3 µV/°C":  (mA(3e-6 * dT),                     S2),
    "Reference drift (Ib × R21)": (mA(0.01 * dT * 50e-9 * 10e3 / 10), S3),
    "LM7321 Vos drift, 2.5 µV/°C": (mA(2.5e-6 * np.sqrt(2) * dT / 10), S4),
}
zero_rss = np.sqrt(sum(v**2 for v, _ in zero.values()))
zero_sum = sum(v for v, _ in zero.values())

# ── total error at a full-scale reading ────────────────────────────────────
def total(imax, high_gain, combine):
    g = [0.005 * dT, 0.0035 * dT, 0.0024 * dT]
    if high_gain:
        g.append(0.9 * 25e-6 * dT * 100)
    z = [mA(3e-6 * dT), mA(0.01 * dT * 50e-9 * 10e3 / 10),
         mA(2.5e-6 * np.sqrt(2) * dT / 10)]
    gp = (np.sqrt(sum(x**2 for x in g)) if combine == "rss" else sum(g))
    zz = (np.sqrt(sum(x**2 for x in z)) if combine == "rss" else sum(z))
    return gp / 100 * imax * 1000 + zz          # mA at a full-scale reading

fig = plt.figure(figsize=(8.8, 12.4))
fig.patch.set_facecolor(SURFACE)
AX = [fig.add_axes([0.098, y, 0.655, 0.213]) for y in (0.680, 0.395, 0.110)]
axes = AX


def style(ax, ylab):
    ax.set_facecolor(SURFACE)
    ax.grid(True, color=GRID, lw=0.8, zorder=0)
    ax.set_axisbelow(True)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(GRID)
    ax.tick_params(colors=INK2, labelsize=9, length=0)
    ax.set_ylabel(ylab, color=INK2, fontsize=9.5)
    ax.set_xlim(0, 47)
    ax.xaxis.set_major_locator(MultipleLocator(5))
    ax.axvspan(TRIM_C - 5, TRIM_C + 5, color=BAND, zorder=0)
    ax.axvline(TRIM_C, color=INK3, lw=1, ls=(0, (4, 3)), zorder=1)


def place(ax, items, gap_frac=0.085):
    """items = [(y_end, text, color)] -> draw right-margin labels, de-overlapped."""
    lo, hi = ax.get_ylim()
    gap = (hi - lo) * gap_frac
    items = sorted(items, key=lambda t: -t[0])
    floor = lo + gap * 0.75          # keep labels clear of the x-axis furniture
    ys = [min(max(v, floor), hi) for v, _, _ in items]
    for i in range(1, len(ys)):                       # push down if too close
        if ys[i - 1] - ys[i] < gap:
            ys[i] = ys[i - 1] - gap
    if ys and ys[-1] < floor:                         # ran into the floor - push the stack up
        ys[-1] = floor
    for i in range(len(ys) - 2, -1, -1):
        if ys[i] - ys[i + 1] < gap:
            ys[i] = ys[i + 1] + gap
    for (_, text, color), y in zip(items, ys):
        ax.annotate(text, xy=(41.2, y), xycoords="data", color=color, fontsize=8.7,
                    va="center", ha="left", fontweight="medium", annotation_clip=False)


def caption(ax, text):
    b = ax.get_position()
    fig.text(b.x0, b.y0 - 0.031, text, color=INK2, fontsize=8.8, va="top", ha="left")


# ── panel A ────────────────────────────────────────────────────────────────
ax = axes[0]
style(ax, "Gain drift  (% of reading)")
for name, (y, c) in gain.items():
    ax.plot(T, y, color=c, lw=2, zorder=3)
ax.plot(T, gain_rss, color=S1, lw=2.8, zorder=4)
ax.set_ylim(0, 0.16)
place(ax, [(gain_rss[-1], "Total (RSS)", S1)] +
          [(y[-1], n, c) for n, (y, c) in gain.items()])
fig.text(0.098, 0.962, "Expected drift after trimming at 23 °C",
         color=INK, fontsize=16, fontweight="bold", va="top", ha="left")
fig.text(0.098, 0.936,
         "Zero and gain are corrected at 23 °C, so every curve here is drift alone — "
         "initial tolerance\nand static offset have already been removed.",
         color=INK2, fontsize=9.6, va="top", ha="left")
caption(ax, "Shunt TCR dominates: it is over half the total on its own.")

# ── panel B ────────────────────────────────────────────────────────────────
ax = axes[1]
style(ax, "Zero drift  (mA referred to the input)")
for name, (y, c) in zero.items():
    ax.plot(T, y, color=c, lw=2, zorder=3)
ax.plot(T, zero_rss, color=S1, lw=2.8, zorder=4)
ax.set_ylim(0, 8.8)
place(ax, [(zero_rss[-1], "Total (RSS)", S1)] +
          [(y[-1], n, c) for n, (y, c) in zero.items()])
caption(ax, "Si8921 offset drift is nearly the whole of it — the total and that one term "
            "almost coincide.\nReferred through each range's own gain, zero drift is the same "
            "on both ranges.")

# ── panel C ────────────────────────────────────────────────────────────────
ax = axes[2]
style(ax, "Total error at full scale  (mA)")
items = []
for imax, hg, c, nm in ((10.0, False, S1, "10 A range"), (5.0, True, S2, "5 A range")):
    lo, hi = total(imax, hg, "rss"), total(imax, hg, "sum")
    ax.fill_between(T, lo, hi, color=c, alpha=0.15, lw=0, zorder=2)
    ax.plot(T, lo, color=c, lw=2.4, zorder=3)
    ax.plot(T, hi, color=c, lw=1.2, ls=(0, (3, 2)), zorder=3)
    items += [(hi[-1], f"{nm} — worst case", c), (lo[-1], f"{nm} — typical", c)]
ax.set_ylim(0, 30)
place(ax, items)
ax.set_xlabel("Ambient temperature  (°C)", color=INK2, fontsize=9.5)
caption(ax, "Shaded vertical band = the ±5 °C accuracy window the specification is written "
            "against.\nDashed = linear sum, solid = RSS; the real value lies between them.")
fig.text(0.098, 0.028,
         "MelansonTech Isolated Shunt Amplifier Rev 2  ·  drift only, after zero trim and gain "
         "correction at 23 °C\nValues from docs/Tolerance Budget - Isolated Shunt Amplifier "
         "Rev 2.xlsx  ·  regenerate with docs/plot_drift.py",
         color=INK3, fontsize=8.2, va="top", ha="left")

for ext in ("svg", "png"):
    fig.savefig(f"/home/claude/drift-vs-temperature.{ext}", dpi=200,
                facecolor=SURFACE)

# ── the table view, required because two slots sit under 3:1 contrast ──────
print(f"{'T (°C)':>7}{'gain drift %':>14}{'zero drift mA':>15}"
      f"{'10 A total mA':>15}{'5 A total mA':>14}")
for t in (0, 5, 10, 15, 18, 23, 28, 33, 35, 40):
    i = int(np.argmin(np.abs(T - t)))
    print(f"{t:>7}{gain_rss[i]:>14.3f}{zero_rss[i]:>15.2f}"
          f"{total(10.0, False, 'rss')[i]:>15.2f}{total(5.0, True, 'rss')[i]:>14.2f}")
