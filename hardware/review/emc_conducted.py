# -*- coding: utf-8 -*-
"""Conducted emission estimate at the 15 V input port, from the isolated
DC-DC module, against CISPR 32 Class B DC-port limits.

The only switching source on the board is PSU1 (NXJ1S0505, 1.5 MHz). Its
emissions were de-embedded from Murata's conducted scan in the FTCAN review
(the same module; hardware/review/psu1_conducted.json there, copied here as
ftcan_psu1_conducted.json): each harmonic as a common-mode current source
I_src through the 2.5 pF barrier, which is what reaches the LISN whatever
the differential filter does (trap 17). On this board the common-mode path
from the measured side back to the input cable runs through the barrier
capacitance, the measured circuit's capacitance to earth (unknown, taken as
large), the LISN, the input cable and CM1 (1 mH common-mode choke, DR331).

  V_LISN(n) = 25 ohm x I_src(n) x | Z_src / (Z_src + Z_cm) |
  Z_src = 1/(j w 2.5 pF)   Z_cm = j w L || 1/(j w C_w), C_w 5 pF (EST, SRF 2.3 MHz)

Marked CALCULATED, module only: the Si8921 modulator has no vendor scan and
is not included; a bench scan on a LISN settles both.

    python emc_conducted.py
"""
import io
import json
import math
import os

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt                              # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
FIG = os.path.join(os.path.dirname(os.path.dirname(HERE)), "docs", "design-review", "figures")
C_BARRIER, L_CM, C_W = 2.5e-12, 1e-3, 5e-12


def cispr32_dc(f, det):
    """CISPR 32 Class B, DC power port, dBuV. QP: 66-56 (0.15-0.5 MHz, log), 56 (0.5-5), 60 (5-30). AVG 10 dB lower."""
    if f < 0.5e6:
        q = 66 - 10 * math.log10(f / 0.15e6) / math.log10(0.5 / 0.15)
    elif f < 5e6:
        q = 56
    else:
        q = 60
    return q if det == "qp" else q - 10


if __name__ == "__main__":
    d = json.load(io.open(os.path.join(HERE, "ftcan_psu1_conducted.json")))
    H = d["harmonics"]
    print("source: %d harmonics, keys %s" % (len(H), sorted(H[0].keys())))
    rows = []
    for h in H:
        f = h["f"]
        i_src = h.get("i_src") or h.get("i_cm") or None
        if i_src is None:
            # fall back: from Murata's QP level through 25 ohm
            i_src = 10 ** (h["murata_qp"] / 20) * 1e-6 / 25.0
        w = 2 * math.pi * f
        z_src = 1 / (w * C_BARRIER)
        z_cm = abs((1j * w * L_CM) / (1 - w * w * L_CM * C_W))
        att = z_src / math.hypot(z_src, z_cm)
        v = 25.0 * i_src * att
        v_db = 20 * math.log10(max(v, 1e-12) / 1e-6)
        v_db_nochoke = 20 * math.log10(max(25.0 * i_src, 1e-12) / 1e-6)
        rows.append(dict(n=h["n"], f=f, i_src_uA=i_src * 1e6, murata_qp=h.get("murata_qp"), murata_av=h.get("murata_av"),
                         choke_att_db=20 * math.log10(att), v_lisn_db=v_db, v_lisn_nochoke_db=v_db_nochoke,
                         limit_qp=cispr32_dc(f, "qp"), limit_av=cispr32_dc(f, "av")))
    worst = min(r["limit_av"] - r["v_lisn_db"] for r in rows if r["f"] <= 30e6)
    print("%-3s %-8s %-9s %-8s %-9s %-9s %-7s %-7s" % ("n", "MHz", "Isrc uA", "choke", "VLISN", "Murata QP", "limAV", "margin"))
    for r in rows:
        if r["f"] <= 30e6:
            print("%-3d %-8.1f %-9.2f %-8.1f %-9.1f %-9s %-7.0f %+7.1f" % (r["n"], r["f"] / 1e6, r["i_src_uA"], r["choke_att_db"], r["v_lisn_db"],
                                                                      "%.1f" % r["murata_qp"] if r["murata_qp"] is not None else "-", r["limit_av"], r["limit_av"] - r["v_lisn_db"]))
    print("worst margin to the Class B AVG limit: %+.1f dB (module only, CM path through the 2.5 pF barrier)" % worst)
    fig, ax = plt.subplots(figsize=(7.5, 4.0))
    fs = np.array([r["f"] for r in rows if r["f"] <= 30e6])
    ax.plot(fs / 1e6, [r["v_lisn_db"] for r in rows if r["f"] <= 30e6], "o", label="estimate at the LISN, with CM1")
    ax.plot(fs / 1e6, [r["v_lisn_nochoke_db"] for r in rows if r["f"] <= 30e6], "x", color="grey", label="without the choke")
    ff = np.logspace(math.log10(0.15e6), math.log10(30e6), 200)
    ax.plot(ff / 1e6, [cispr32_dc(f, "qp") for f in ff], "r-", lw=0.8, label="CISPR 32 B QP")
    ax.plot(ff / 1e6, [cispr32_dc(f, "av") for f in ff], "r--", lw=0.8, label="CISPR 32 B AVG")
    ax.set_xscale("log"); ax.set_xlabel("MHz"); ax.set_ylabel("dBuV"); ax.grid(True, which="both", alpha=0.3); ax.legend(fontsize=8)
    ax.set_title("Conducted emission at the 15 V port from PSU1 (de-embedded vendor scan), calculated", fontsize=9)
    fig.tight_layout(); fig.savefig(os.path.join(FIG, "emc-conducted.png"), dpi=110)
    # radiated bound from the common-mode current on a 1 m cable at 3 m
    i_max = max(r["i_src_uA"] for r in rows) * 1e-6
    f_max = [r["f"] for r in rows if r["i_src_uA"] * 1e-6 == i_max][0]
    e = 1.257e-6 * i_max * f_max * 1.0 / 3.0
    e_db = 20 * math.log10(e / 1e-6)
    print("radiated bound: %.2f uA at %.1f MHz on a 1 m cable at 3 m -> %.1f dBuV/m (Class B 30-230 MHz limit 40 dBuV/m at 10 m; the harmonics are below 30 MHz)" % (i_max * 1e6, f_max / 1e6, e_db))
    io.open(os.path.join(HERE, "emc_conducted.json"), "w", encoding="utf-8", newline="\n").write(json.dumps(dict(rows=rows, worst_margin_av_db=worst, c_barrier=C_BARRIER, l_cm=L_CM, c_w=C_W, radiated_bound_dbuv_m=e_db), indent=1))
    print("written -> emc_conducted.json, figures/emc-conducted.png")
