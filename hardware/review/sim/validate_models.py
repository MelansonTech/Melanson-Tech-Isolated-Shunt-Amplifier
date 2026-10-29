# -*- coding: utf-8 -*-
"""Validate the op-amp models at the board's 12 V single supply against the
datasheets before any chain result is trusted: quiescent current, input
offset, input bias current, gain-bandwidth and output swing.

OPA197: TI OPA197.LIB (Jan 2019). LM7321: the National LM7321.MOD with its
10 V supply group active (models/LM7321_12V.lib), which is what the file
itself says to do for supplies between its 2.7 / 10 / 30 V groups.

    python validate_models.py
"""
import io
import json
import os
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent))
from ltspice_run import run_ltspice, read_raw          # noqa: E402
import ds_params as DS                                  # noqa: E402

MODELS = HERE.parent / "models"
PARTS = {
    "OPA197": dict(inc="OPA197.LIB", sub="OPA197", order="p n vp vn o",
                   ds=dict(iq=DS.P["opa197"]["iq_typ"], vos=DS.P["opa197"]["vos_typ"], ib=DS.P["opa197"]["ib_typ"],
                           gbw=DS.P["opa197"]["gbw_hz"], swing10k=DS.P["opa197"]["swing_mv_10k"][0] * 1e-3)),
    "LM7321": dict(inc="LM7321_12V.lib", sub="LM7321_12V", order="p n vp vn o",
                   ds=dict(iq=DS.P["lm7321"]["is_typ"], vos=DS.P["lm7321"]["vos_typ"], ib=DS.P["lm7321"]["ib_typ"],
                           gbw=DS.P["lm7321"]["gbw_hz"], swing10k=DS.P["lm7321"]["swing_mv_10k"][0] * 1e-3)),
}


def deck(name, part, body, analysis):
    inc = (MODELS / part["inc"]).as_posix()
    return "\n".join(["* %s validation" % name, ".include \"%s\"" % inc, "V12 vp 0 12", body, analysis, ".end", ""])


def run(name, txt):
    p = HERE / ("val_%s.cir" % name)
    io.open(p, "w", encoding="latin-1", newline="\n").write(txt)
    run_ltspice(p)
    return read_raw(p.with_suffix(".raw"))


if __name__ == "__main__":
    out = {}
    print("%-8s %-10s %-10s %-10s | %-10s %-10s %-10s" % ("part", "Iq model", "Iq DS", "Vos model", "Vos DS", "Ib model", "Ib DS"))
    for nm, part in PARTS.items():
        sub = part["sub"]
        # 1. unity buffer at mid-rail: Iq, Vos, Ib
        body = "Vin p 0 6\nX1 p o vp 0 o %s\nRL o 0 10k" % sub
        r = run(nm + "_op", deck(nm, part, body, ".op"))
        iq = -float(r.get("I(V12)")[0]); vos = float(r.get("V(o)")[0]) - 6.0; ib = -float(r.get("I(Vin)")[0])
        # 2. GBW from a gain-of-101 non-inverting stage
        body = "Vin p 0 6 AC 1\nX1 p n vp 0 o %s\nRf o n 100k\nRg n m 1k\nVm m 0 6\nRL o 0 10k"
        body = body % sub
        r = run(nm + "_ac", deck(nm, part, body, ".ac dec 50 10 100Meg"))
        f = r.x(); g = np.abs(r.get("V(o)"))
        g0 = g[0]; k = int(np.argmax(g < g0 / np.sqrt(2)))
        gbw = f[k] * g0
        # 3. swing: unity buffer driven to the rails, RL 10k to 6 V
        body = "Vin p 0 0\nX1 p o vp 0 o %s\nRL o m 10k\nVm m 0 6" % sub
        r = run(nm + "_dc", deck(nm, part, body, ".dc Vin 0 12 0.01"))
        vo = r.get("V(o)"); sw_hi = 12.0 - float(vo.max()); sw_lo = float(vo.min())
        out[nm] = dict(iq=iq, vos=vos, ib=ib, gbw=gbw, swing_hi=sw_hi, swing_lo=sw_lo, datasheet=part["ds"], model=part["inc"])
        d = part["ds"]
        print("%-8s %-10.3g %-10.3g %-10.3g | %-10.3g %-10.3g %-10.3g" % (nm, iq, d["iq"], vos, d["vos"], ib, d["ib"]))
        print("         GBW model %.3g Hz (DS %.3g); swing from rails: high %.0f mV, low %.0f mV (DS typ %.0f mV at 10k)" % (
            gbw, d["gbw"], sw_hi * 1e3, sw_lo * 1e3, d["swing10k"] * 1e3))
    io.open(HERE / "validate_models.json", "w", encoding="utf-8", newline="\n").write(json.dumps(out, indent=1))
    print("written -> sim/validate_models.json")
