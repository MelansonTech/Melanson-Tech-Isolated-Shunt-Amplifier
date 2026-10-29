# -*- coding: utf-8 -*-
"""The supply chain and the output headroom, calculated per input voltage and
range. The previous review counted one Schottky; the netlist (SW1 pole is
terminal 2, fed from Vin through D3; position 4 feeds VregIn through D1)
puts two in series on the x100 range, which is the range that needs 5.0 V of
output swing.

  VregIn  = Vin - VF(D3) [- VF(D1) on x100]
  +12     = 12.0 if VregIn >= 12 + Vdo, else VregIn - Vdo   (UA78L12, Vdo 1.7 V typ at 40 mA)
  Vref    = +12 / 2  (both 100k/100k dividers, buffered)
  Vclamp  = +12 - Vswing(U8)  with Vswing ~0.30 V at the ~5 mA the U8 output
            sources at 11.7 V (OPA197: 95-125 mV at 10k, 430-500 mV at 2k;
            the bench measured 5.70 V above a 6.0 V reference = 0.30 V)
  headroom = (Vclamp - Vref) - 5.0 V full scale on the x100 range, - 1.0 V on x10

Also: the relay coil against its 150 % maximum, SW1 against 0.1 A / 12 V,
U6 against its 0.5 W package rating (thermal.py does the real number).

    python rails.py
"""
import io
import json
import os

import ds_params as DS
from power_budget import budget

HERE = os.path.dirname(os.path.abspath(__file__))
P = DS.P
VSWING_U8 = 0.30            # from the measured 5.70 V clamp on a 12.0 V rail (test report 4.2)
VDO = {"typ": P["ua78l12"]["vdo_typ"], "guaranteed": P["ua78l12"]["vi_min_rec"] - 12.0}   # 1.7 V typ, 2.5 V by the 14.5 V minimum

if __name__ == "__main__":
    pb = json.load(io.open(os.path.join(HERE, "power_budget.json")))
    i_psu = pb["psu_in_ma_residual"]
    rows = []
    print("%-5s %-5s %-6s %-6s | %-9s %-9s | %-9s %-9s | %-7s %-7s" % ("Vin", "range", "VregIn", "Icoil", "+12 typ", "+12 guar", "hdrm typ", "hdrm guar", "coil %", "note"))
    for vin in (13.0, 13.5, 14.0, 14.5, 14.9, 15.0, 15.2, 15.6, 16.0):
        for rng in ("x10", "x100"):
            b = budget(vin, rng, psu_in_ma=i_psu)
            fs = 5.0 if rng == "x100" else 1.0
            r = dict(vin=vin, range=rng, vregin=b["vregin"], i_coil_ma=b["i_coil"] * 1e3)
            for k, vdo in VDO.items():
                v12 = min(12.0, b["vregin"] - vdo)
                vclamp = v12 - VSWING_U8
                vref = v12 / 2
                r["v12_" + k] = v12
                r["headroom_" + k] = (vclamp - vref) - fs
            r["coil_pct"] = 100 * b["highgain"] / 12.0 if rng == "x100" else 0.0
            r["sw1_pct_i"] = 100 * b["i_total"] / 0.1
            r["u6_w"] = b["diss_w"]["U6"]
            rows.append(r)
            print("%-5.1f %-5s %-6.2f %-6.1f | %-9.2f %-9.2f | %-+9.2f %-+9.2f | %-7.0f %s" % (
                vin, rng, r["vregin"], r["i_coil_ma"], r["v12_typ"], r["v12_guaranteed"], r["headroom_typ"], r["headroom_guaranteed"],
                r["coil_pct"], "U6 %.2f W, SW1 %.0f %% of 0.1 A" % (r["u6_w"], r["sw1_pct_i"])))
    # the regulation thresholds at the jack
    thr = {}
    for rng, nd in (("x10", 1), ("x100", 2)):
        for k, vdo in VDO.items():
            thr["%s_%s" % (rng, k)] = 12.0 + vdo + nd * P["mbr0560"]["vf_est_95ma"]
    print("\n+12 regulation threshold at the jack:", {k: round(v, 2) for k, v in thr.items()})
    # where does the x100 headroom reach zero (typ)?
    import numpy as np
    for rng, fs in (("x100", 5.0), ("x10", 1.0)):
        for k, vdo in VDO.items():
            for vin in np.arange(12.5, 16.01, 0.05):
                b = budget(float(vin), rng, psu_in_ma=i_psu)
                v12 = min(12.0, b["vregin"] - vdo)
                if (v12 - VSWING_U8) - v12 / 2 - fs >= 0:
                    print("  %s full scale (%.1f V) reachable above Vin = %.2f V (%s dropout)" % (rng, fs, vin, k))
                    break
    out = dict(rows=rows, thresholds=thr, vswing_u8=VSWING_U8, vdo=VDO,
               relay=dict(vmax_pct=P["g6l"]["vmax_pct"], vmax_v=12 * P["g6l"]["vmax_pct"] / 100.0, note=P["g6l"]["note"]),
               sw1=dict(rating_a=P["os103011"]["rating_a"], rating_vdc=P["os103011"]["rating_vdc"]))
    io.open(os.path.join(HERE, "rails.json"), "w", encoding="utf-8", newline="\n").write(json.dumps(out, indent=1))
    print("written -> rails.json")
