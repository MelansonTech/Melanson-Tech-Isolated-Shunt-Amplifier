# -*- coding: utf-8 -*-
"""Per-rail currents and per-part dissipation, by range and input voltage.

Every entry names its source: DS (datasheet, ds_params.py), CALC (from the
circuit), MEAS (bench 2026-09-06, 95.8 mA at 15 V on the x100 range), EST
(stated basis). The one number the budget cannot derive is the isolated
module's input current at its 14 % load, so it is taken as the residual of
the measured total and cross-checked against the module's efficiency.

Feeds rails.py (headroom) and thermal.py (dissipation).

    python power_budget.py
"""
import io
import json
import os

import ds_params as DS

HERE = os.path.dirname(os.path.abspath(__file__))
P = DS.P


def budget(vin, rng, psu_in_ma=None):
    """Return dict of loads and rails for one input voltage and range ('x10' or 'x100')."""
    vf_d3 = P["mbr0560"]["vf_est_95ma"]
    vf_d1 = P["mbr0560"]["vf_est_95ma"]
    highgain = vin - vf_d3 if rng == "x100" else 0.0
    vregin = vin - vf_d3 - (vf_d1 if rng == "x100" else 0.0)
    v12 = min(12.0, vregin - P["ua78l12"]["vdo_typ"])          # regulator or dropout, typical
    vref = v12 / 2.0
    loads = []
    # +12 domain
    loads.append(("U3", "+12", P["opa197"]["iq_typ"], "DS", "OPA197 IQ 1.0 mA typ"))
    loads.append(("U8", "+12", P["opa197"]["iq_typ"], "DS", "OPA197 IQ 1.0 mA typ"))
    loads.append(("U5", "+12", P["lm7321"]["is_typ"], "DS", "LM7321 IS 1.35 mA typ"))
    loads.append(("U9", "+12", P["lm7321"]["is_typ"], "DS", "LM7321 IS 1.35 mA typ"))
    loads.append(("R22/R17", "+12", v12 / 200e3, "CALC", "100k + 100k reference divider"))
    loads.append(("R26/R28/R29", "+12", v12 / 200.1e3, "CALC", "100k + 100 R + 100k trim divider"))
    loads.append(("D4 or D5", "+12", (v12 - 3.2) / 10e3, "CALC", "one blue LED through 10k, Vf 3.2 V (BOM description)"))
    loads.append(("R13", "+12", vref / 10e3, "CALC", "10k from U3 out (~Vref) to GND, sourced by U3"))
    loads.append(("R15", "+12", vref / 10e3, "CALC", "10k from U8 out (~Vref) to GND, sourced by U8"))
    i12 = sum(l[2] for l in loads if l[1] == "+12")
    loads.append(("U1", "VregIn", P["ua78l12"]["ibias_typ"], "DS", "UA78L12 bias 3.84 mA typ (new chip)"))
    # +5 domain
    loads.append(("U2 VDDB", "+5", P["si8921"]["iddb_typ"], "DS", "Si8921 output side 3.5 mA typ"))
    p_iso_out = 5.0 * (5.0 / 220.0 + P["si8921"]["idda_typ"])
    if psu_in_ma is None:
        eff = 0.60
        i_psu = p_iso_out / eff / 5.0
        loads.append(("PSU1 in", "+5", i_psu, "EST", "137 mW isolated load at 60 %% efficiency (14 %% of rated load)"))
    else:
        i_psu = psu_in_ma * 1e-3
        loads.append(("PSU1 in", "+5", i_psu, "MEAS", "residual of the measured 95.8 mA total at 15 V, x100"))
    loads.append(("R6", "+5_ISO", 5.0 / 220.0, "CALC", "220 R preload on the isolated 5 V"))
    loads.append(("U2 VDDA", "+5_ISO", P["si8921"]["idda_typ"], "DS", "Si8921 input side 4.6 mA typ"))
    i5 = sum(l[2] for l in loads if l[1] == "+5")
    loads.append(("U6", "VregIn", P["ht7550_1"]["iss_typ"], "DS", "HT7550-1 quiescent 2.5 uA"))
    # relay coil on the x100 range
    i_coil = highgain / P["g6l"]["coil_ohm"] if rng == "x100" else 0.0
    loads.append(("Rel1 coil", "HighGain", i_coil, "CALC", "G6L-1F DC12 coil 800 R at HighGain"))
    i_vregin = i12 + P["ua78l12"]["ibias_typ"] + i5 + P["ht7550_1"]["iss_typ"]
    i_total = i_vregin + i_coil
    diss = {
        "U1": (vregin - v12) * (i12 + P["ua78l12"]["ibias_typ"]),
        "U6": (vregin - 5.0) * i5,
        "Rel1": highgain * i_coil,
        "D3": vf_d3 * i_total,
        "D1": vf_d1 * i_vregin if rng == "x100" else 0.0,
        "PSU1": 5.0 * i_psu - p_iso_out,
        "R6": 5.0 ** 2 / 220.0,
        "U2": 5.0 * (P["si8921"]["idda_typ"] + P["si8921"]["iddb_typ"]),
        "U3": v12 * P["opa197"]["iq_typ"], "U8": v12 * P["opa197"]["iq_typ"],
        "U5": v12 * P["lm7321"]["is_typ"], "U9": v12 * P["lm7321"]["is_typ"],
        "SW1": 0.02 * i_total ** 2,
    }
    return dict(vin=vin, range=rng, vf_d3=vf_d3, vf_d1=vf_d1, highgain=highgain, vregin=vregin, v12=v12, vref=vref,
                i12=i12, i5=i5, i_psu=i_psu, i_coil=i_coil, i_vregin=i_vregin, i_total=i_total,
                loads=[dict(ref=r, rail=rail, i_a=i, src=s, note=n) for r, rail, i, s, n in loads], diss_w=diss,
                p_in_w=vin * i_total)


if __name__ == "__main__":
    meas = P["measured"]["i_aux_15v_x100"]
    est = budget(15.0, "x100")
    # residual: module input = measured total - everything else
    other = est["i_total"] - est["i_psu"]
    i_psu_meas = (meas - other) * 1e3
    eff = (5.0 * (5.0 / 220 + P["si8921"]["idda_typ"])) / (5.0 * i_psu_meas * 1e-3)
    print("estimate at 15 V x100: %.1f mA (module in at 60 %% eff.: %.1f mA); measured %.1f mA" % (est["i_total"] * 1e3, est["i_psu"] * 1e3, meas * 1e3))
    print("-> module input current as the residual: %.1f mA, implied module efficiency %.0f %% at %.0f mW out (datasheet 71-76 %% at full load)" % (
        i_psu_meas, 100 * eff, 1e3 * 5.0 * (5.0 / 220 + P["si8921"]["idda_typ"])))
    out = {"psu_in_ma_residual": i_psu_meas, "psu_eff_implied": eff, "cases": {}}
    print("\n%-6s %-5s %-7s %-7s %-6s | %-7s %-7s %-7s %-7s | %-6s %-6s %-6s %-6s %-6s" % (
        "Vin", "range", "VregIn", "+12", "Itot", "I12", "I5", "Ipsu", "Icoil", "P_U6", "P_U1", "P_Rel1", "P_D3", "P_PSU1"))
    for vin in (13.0, 14.0, 15.0, 15.6, 16.0):
        for rng in ("x10", "x100"):
            b = budget(vin, rng, psu_in_ma=i_psu_meas)
            out["cases"]["%s_%.1f" % (rng, vin)] = b
            d = b["diss_w"]
            print("%-6.1f %-5s %-7.2f %-7.2f %-6.1f | %-7.1f %-7.1f %-7.1f %-7.1f | %-6.2f %-6.3f %-6.2f %-6.3f %-6.3f" % (
                vin, rng, b["vregin"], b["v12"], b["i_total"] * 1e3, b["i12"] * 1e3, b["i5"] * 1e3, b["i_psu"] * 1e3, b["i_coil"] * 1e3,
                d["U6"], d["U1"], d["Rel1"], d["D3"], d["PSU1"]))
    b = out["cases"]["x100_15.0"]
    print("\nloads at 15 V x100:")
    for l in b["loads"]:
        print("  %-12s %-9s %7.2f mA  %-4s %s" % (l["ref"], l["rail"], l["i_a"] * 1e3, l["src"], l["note"]))
    print("\ndissipation at 15 V x100 (W):", {k: round(v, 3) for k, v in b["diss_w"].items()})
    io.open(os.path.join(HERE, "power_budget.json"), "w", encoding="utf-8", newline="\n").write(json.dumps(out, indent=1))
    print("written -> power_budget.json")
