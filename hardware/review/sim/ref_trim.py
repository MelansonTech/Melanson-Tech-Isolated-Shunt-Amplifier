# -*- coding: utf-8 -*-
"""Recommendation 1 of the 2026-10-29 review: one reference source, the zero
trim as a small current injected after it.

Two circuits, written as netlist blocks so the drawing (ref_trim_asc.py) and
these benches come from the same text:

  asbuilt   the Rev 3.1 reference section: two 100k/100k dividers off +12,
            R28 (100 R) in the second one, R21 between the wiper and the
            DiffAmpRef buffer input, LM7321 buffers U5 (ISenseRTN) and U9
            (DiffAmpRef). R21 is 10 k on the board, 0 R on the sheet.
  proposed  one 100k/100k divider and buffer (ISenseRTN) as built; DiffAmpRef
            = ISenseRTN + dV, with dV = (Vwiper - ISenseRTN) x R21/(R21 + R33):
            R21 100 R 0.1 % in series from ISenseRTN to the U9 input, R33
            100 k from the wiper of R28 (the BOM's 10 k CT94EW103, now across
            +12 and GND), C26 100 nF to ISenseRTN. R26 and R29 are deleted.

Benches, both circuits, LM7321 vendor model at its 10 V group:
  span    DiffAmpRef - ISenseRTN at five wiper positions
  ios     the same at mid travel with 200 nA (the LM7321 IOS maximum) injected
          into the U9 input: the bias-current term the proposal removes
  rail    the trim offset at full travel with +12 at 11.5 and 12.5 V
  loop    Tian loop gain at the U9 output (unchanged load, C10 22 uF)

    python ref_trim.py
"""
import io
import json
import os
import sys
from pathlib import Path

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt                              # noqa: E402

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent))
from ltspice_run import run_ltspice, read_raw, tian_loop_gain, phase_margin   # noqa: E402
import ds_params as DS                                                        # noqa: E402

MODELS = HERE.parent / "models"
FIG = HERE.parent.parent.parent / "docs" / "design-review" / "figures"
C30D = 22e-6 * DS.derate_x5r(6.0)
C29D = 22e-6 * DS.derate_x5r(9.0)
OPAMP = "LM7321_12V"


def common(v12=12.0):
    return ["V12 v12 0 %.3f" % v12, "Vin vin 0 15",
            "* ISenseRTN: 100k/100k divider, 100 nF, unity buffer U5",
            "R22 v12 u5p 100k", "R17 u5p 0 100k", "C4 u5p 0 100n",
            "XU5 u5p irtn v12 0 irtn %s" % OPAMP,
            "C30 irtn 0 %.4g" % C30D, "C29 irtn vin %.4g" % C29D]


def asbuilt(k=0.5, r21=10e3, ios=0.0, v12=12.0, loop=False):
    """k is the R28 wiper position, 0 = toward R29 (GND side), 1 = toward R26."""
    out = "dref_a" if loop else "dref"
    L = ["* reference section, as built (R21 = %g)" % r21] + common(v12) + [
        "* DiffAmpRef: second 100k/100k divider with R28 100 R in the middle, R21, 100 nF, buffer U9",
        "R26 v12 r28a 100k", "R28a r28a wiper %.4g" % max(100 * (1 - k), 1e-3), "R28b wiper r28b %.4g" % max(100 * k, 1e-3), "R29 r28b 0 100k",
        "R21 wiper u9p %.4g" % max(r21, 1e-3), "C26 u9p 0 100n",
        "Ios 0 u9p %.4g" % ios,
        "XU9 u9p dref v12 0 %s %s" % (out, OPAMP), "C10 dref irtn 22u"]
    return L


def proposed(k=0.5, ios=0.0, v12=12.0, loop=False):
    """k is the R28 wiper position, 0 = GND end, 1 = +12 end."""
    out = "dref_a" if loop else "dref"
    L = ["* reference section, proposed: one source, trim injected after it"] + common(v12) + [
        "* DiffAmpRef = ISenseRTN + (Vwiper - ISenseRTN) * R21 / (R21 + R33)",
        "R28a v12 wiper %.4g" % max(10e3 * (1 - k), 1e-3), "R28b wiper 0 %.4g" % max(10e3 * k, 1e-3),
        "R33 wiper u9p 100k", "R21 irtn u9p 100", "C26 u9p irtn 100n",
        "Ios 0 u9p %.4g" % ios,
        "XU9 u9p dref v12 0 %s %s" % (out, OPAMP), "C10 dref irtn 22u"]
    return L


def deck(lines, analysis):
    return "\n".join([".include \"%s\"" % (MODELS / "LM7321_12V.lib").as_posix()] + lines + [analysis, ".end", ""])


def run(name, lines, analysis):
    p = HERE / ("reftrim_%s.cir" % name)
    io.open(p, "w", encoding="latin-1", newline="\n").write("* " + name + "\n" + deck(lines, analysis))
    run_ltspice(p)
    return read_raw(p.with_suffix(".raw"))


def dv(r):
    return float(r.get("V(dref)")[0] - r.get("V(irtn)")[0])


if __name__ == "__main__":
    res = dict(model=OPAMP, c30_derated=C30D, c29_derated=C29D, circuits={})
    ks = [0.0, 0.25, 0.5, 0.75, 1.0]
    cases = {"asbuilt_r21_10k": lambda **kw: asbuilt(r21=10e3, **kw),
             "asbuilt_r21_0": lambda **kw: asbuilt(r21=0.0, **kw),
             "proposed": lambda **kw: proposed(**kw)}
    for name, mk in cases.items():
        span = [dv(run("%s_k%d" % (name, int(k * 100)), mk(k=k), ".op")) for k in ks]
        mid = dv(run(name + "_mid", mk(k=0.5), ".op"))
        ios = dv(run(name + "_ios", mk(k=0.5, ios=200e-9), ".op")) - mid
        full = dv(run(name + "_full", mk(k=1.0), ".op"))
        rail = [dv(run(name + "_rail%d" % int(v * 10), mk(k=1.0, v12=v), ".op")) - full for v in (11.5, 12.5)]
        irtn = float(run(name + "_mid", mk(k=0.5), ".op").get("V(irtn)")[0])
        # U9 loop
        L = mk(k=0.5, loop=True) + ["Vt dref dref_a DC 0 AC {1-iv}", "It 0 dref AC {iv}", ".step param iv list 0 1"]
        r = run(name + "_loop", L, ".ac dec 60 10 100Meg")
        f = r.x(0)
        T = tian_loop_gain((r.get("V(dref_a)", 0), r.get("V(dref)", 0)), r.get("I(Vt)", 1))
        fc, _ = phase_margin(f, T)
        ph = np.degrees(np.unwrap(np.angle(T)))
        pm = float(180 + ((np.interp(np.log10(fc), np.log10(f), ph) + 180) % 360 - 180))
        res["circuits"][name] = dict(k=ks, dv_mV=[v * 1e3 for v in span], mid_offset_mV=mid * 1e3, ios_term_mV=ios * 1e3,
                                     rail_term_uV={"11.5": rail[0] * 1e6, "12.5": rail[1] * 1e6}, isensertn_V=irtn,
                                     u9_loop=dict(fc=fc, pm_deg=pm))
        print("%-16s span %+.2f .. %+.2f mV (mid %+.3f mV), IOS 200 nA -> %+.3f mV, rail +/-0.5 V at full trim -> %+.0f / %+.0f uV, U9 loop fc %.3g Hz PM %.0f deg" % (
            name, span[0] * 1e3, span[-1] * 1e3, mid * 1e3, ios * 1e3, rail[0] * 1e6, rail[1] * 1e6, fc, pm))
    # datasheet budget of the reference DIFFERENCE drift, both circuits (calculated)
    lm = DS.P["lm7321"]
    budget = {
        "asbuilt_r21_10k": {"U9 Ib x R21 (10k) static": lm["ib_typ"] * 10e3 * 1e3, "IOS max x 50k": lm["ios_max"] * 50e3 * 1e3,
                            "two Vos drifts, uV/C": 2 * lm["tcvos_typ"] * 1e6, "Ib drift x 10k, 20 % of Ib, mV": 0.2 * lm["ib_typ"] * 10e3 * 1e3},
        "asbuilt_r21_0": {"IOS max x 50k": lm["ios_max"] * 50e3 * 1e3, "two Vos drifts, uV/C": 2 * lm["tcvos_typ"] * 1e6,
                          "IOS drift x 50k, 20 % of IOS max, mV": 0.2 * lm["ios_max"] * 50e3 * 1e3},
        "proposed": {"U9 Ib x R21 (100 R) static": lm["ib_typ"] * 100 * 1e3, "IOS max x 100 R": lm["ios_max"] * 100 * 1e3,
                     "one Vos drift, uV/C": lm["tcvos_typ"] * 1e6, "trim resistors 125 ppm/C at 6 mV, uV/C": 6e-3 * 125e-6 * 1e6,
                     "Ib drift x 100 R, 20 % of Ib, mV": 0.2 * lm["ib_typ"] * 100 * 1e3},
    }
    res["budget_datasheet"] = budget
    # figure
    fig, axs = plt.subplots(1, 2, figsize=(8.5, 3.6))
    for name, c in res["circuits"].items():
        axs[0].plot(c["k"], c["dv_mV"], "o-", label=name)
    axs[0].set_xlabel("R28 wiper position"); axs[0].set_ylabel("DiffAmpRef - ISenseRTN, mV"); axs[0].grid(alpha=0.3); axs[0].legend(fontsize=8)
    axs[0].set_title("Trim span (simulated, LM7321 model)", fontsize=9)
    names = list(res["circuits"]); vals = [abs(res["circuits"][n]["ios_term_mV"]) for n in names]
    axs[1].bar(range(len(names)), vals); axs[1].set_xticks(range(len(names))); axs[1].set_xticklabels(names, fontsize=7)
    axs[1].set_ylabel("|dV| for 200 nA into the U9 input, mV"); axs[1].set_yscale("log"); axs[1].grid(alpha=0.3, which="both")
    axs[1].axhline(3.0, color="r", lw=0.8, ls="--"); axs[1].text(0.02, 3.3, "as-built trim span +/-3 mV", color="r", fontsize=7)
    axs[1].set_title("Bias-current sensitivity (simulated)", fontsize=9)
    fig.tight_layout(); FIG.mkdir(parents=True, exist_ok=True); fig.savefig(FIG / "ref-trim-sim.png", dpi=110)
    io.open(HERE / "ref_trim.json", "w", encoding="utf-8", newline="\n").write(json.dumps(res, indent=1))
    print("written -> ref_trim.json, figures/ref-trim-sim.png")
