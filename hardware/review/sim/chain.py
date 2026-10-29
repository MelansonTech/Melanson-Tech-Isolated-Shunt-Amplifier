# -*- coding: utf-8 -*-
"""The signal chain of the Rev 3.1 amplifier sheet in LTspice: shunt sense
network, a behavioural Si8921, the OPA197 difference amplifier (U3), the
relay-switched OPA197 gain stage (U8), the output network, and the two
LM7321 reference buffers (U5 ISenseRTN, U9 DiffAmpRef) with their real
capacitive loads.

Every part value is the sheet's (netlist of MelansonTech Isolated Shunt
Amplifier Rev3.SchDoc); the Si8921 is a behavioural block built from
datasheet Table 5 (gain 8.2, 600 kHz, 0.8 us delay, 1.39 V output common
mode, +/-2.5 V differential clip, 77 dB SNR over 100 kHz as a 79 nV/rtHz
input-referred source) because Skyworks publishes no SPICE model. Op-amps
are the vendor models validated in validate_models.py.

Analyses, both ranges unless noted:
  ac      gain IsenseOut/Vshunt, -3 dB corner, 0.1 dB flatness
  op      bias at the supply corners: every amplifier input and output
  noise   output and input-referred density, integrated over each band
  loop    Tian loop gain and margins for U3, U8 (x10 and x100), U5, U9
  tran    full-scale step on each range: rise, overshoot, settling; a step
          past full scale to show the clamp

    python chain.py [ac|op|noise|loop|tran|all]
"""
import io
import json
import math
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
from ltspice_run import run_ltspice, read_raw, tian_loop_gain, phase_margin, integrated_noise   # noqa: E402
import ds_params as DS                                                                           # noqa: E402

MODELS = (HERE.parent / "models")
FIG = HERE.parent.parent.parent / "docs" / "design-review" / "figures"
SI = DS.P["si8921"]
# input-referred noise density from SNR: full scale 250 mV peak -> rms/sqrt2, over the 100 kHz SNR bandwidth
EN_IN = (SI["vin_fs"] / math.sqrt(2)) / 10 ** (SI["snr_db"] / 20) / math.sqrt(SI["snr_bw_hz"])
RN = EN_IN ** 2 / (4 * 1.380649e-23 * 298.15)             # resistor whose thermal noise is that density
FP = 600e3 / math.sqrt(math.sqrt(2) - 1)                  # two identical real poles -> -3 dB at 600 kHz
CP = 1 / (2 * math.pi * FP * 1e3)
TD_EXTRA = max(SI["tpd_typ"] - 2 / (2 * math.pi * FP), 50e-9)
C30D = 22e-6 * DS.derate_x5r(6.0)                          # ISenseRTN to GND, 6 V bias
C29D = 22e-6 * DS.derate_x5r(9.0)                          # ISenseRTN to Vin, 9 V bias
C10D = 22e-6                                               # DiffAmpRef to ISenseRTN, ~0 V bias


def si8921_block(tran=False):
    # the pure delay: a transmission line for transient runs, a Laplace
    # exponential otherwise - the line stalls LTspice's operating-point search
    delay = (("Tdel f2b 0 f2d 0 Td=%.4g Z0=1k" % TD_EXTRA) + chr(10) + "Rt f2d 0 1k") if tran else ("Edel f2d 0 f2b 0 Laplace=exp(-s*%.4g)" % TD_EXTRA)
    return """
* --- behavioural Si8921B: gain %.1f, two real poles at %.0f kHz (-3 dB 600 kHz), %.0f ns extra delay,
* --- output common mode %.2f V, differential clip +/-2.5 V, input-referred noise %.0f nV/rtHz as R=%.0f k
.subckt SI8921B aip ain aop aon
Rn aip aipn %.4g
Ein sin 0 aipn ain 1
Rf1 sin f1 1k
Cf1 f1 0 %.4g
Eb1 f1b 0 f1 0 1
Rf2 f1b f2 1k
Cf2 f2 0 %.4g
Eb2 f2b 0 f2 0 1
%s
Bop aopi 0 V=%.3f + 0.5*%.1f*min(max(V(f2d),-0.305),0.305)
Bon aoni 0 V=%.3f - 0.5*%.1f*min(max(V(f2d),-0.305),0.305)
Rop aopi aop 50
Ron aoni aon 50
.ends SI8921B
""" % (SI["gain"], FP / 1e3, TD_EXTRA * 1e9, SI["vocm_typ"], EN_IN * 1e9, RN / 1e3,
       RN, CP, CP, delay, SI["vocm_typ"], SI["gain"], SI["vocm_typ"], SI["gain"])


def chain(ctl, v12=12.0, r21=0.0, vsh="DC 0 AC 1", loop=None, load="1Meg", cload="20p", tran=False):
    """The board between the shunt sense terminals and J1. ctl=1 is the x100
    range (relay closed, C8 and C9 switched in), ctl=0 is x10. loop names an
    amplifier whose output is broken for the Tian probe: U3, U8, U5, U9."""
    def out(name, pin):
        return pin + "_a" if loop == name else pin
    L = ["* shunt amplifier chain, ctl=%d (1 = x100), V12=%.2f, R21=%g" % (ctl, v12, r21),
         ".include \"%s\"" % (MODELS / "OPA197.LIB").as_posix(),
         ".include \"%s\"" % (MODELS / "LM7321_12V.lib").as_posix(),
         si8921_block(tran),
         ".model DBAS31 D(Is=2.5n N=1.0 Rs=1 Cjo=30p)",
         ".model SWON SW(Ron=2 Roff=1G Vt=0.5 Vh=0)",
         ".model SWREL SW(Ron=0.1 Roff=1G Vt=0.5 Vh=0)",
         "V12 v12 0 %.3f" % v12, "Vin vin 0 15", "Vctl ctl 0 %d" % ctl,
         "* shunt sense: V(aip)-V(ain) = +Vsh", "Vsh 0 shn %s" % vsh,
         "R1 0 aip 10", "R12 shn ain 10", "C41 aip ain 1n", "D6a ain aip DBAS31", "D6b aip ain DBAS31",
         "XU2 aip ain aop aon SI8921B",
         "* U3 difference amplifier", "XU3 u3p u3n v12 0 %s OPA197" % out("U3", "u3o"),
         "R2 aop u3p 8.2k", "R3 u3p dref 10k", "C16 u3p dref 3p", "R9 aon u3n 8.2k", "R20 u3o u3n 10k", "C17 u3o u3n 3p", "R13 u3o 0 10k",
         "* U8 gain stage", "R32 u3o u8p 1k", "C28 u8p 0 3p", "C8 u8p q5d 680p", "S5 q5d 0 ctl 0 SWON",
         "XU8 u8p u8n v12 0 %s OPA197" % out("U8", "u8o"),
         "R15 u8o 0 10k", "R11 u8o fb1 470", "R10 fb1 fb2 470", "R7 fb2 u8n 470", "C43 u8o u8n 680p",
         "Rg u8n rg 156.667", "Srel rg irtn ctl 0 SWREL",
         "R4 u8o out 100", "R8 u8o out 100", "C18 out irtn 3.3n", "C9 out q6d 47n", "S6 q6d 0 ctl 0 SWON",
         "Rload out irtn %s" % load, "Cload out irtn %s" % cload,
         "* U5 ISenseRTN buffer", "XU5 u5p irtn v12 0 %s LM7321_12V" % out("U5", "irtn"),
         "R22 v12 u5p 100k", "R17 u5p 0 100k", "C4 u5p 0 100n", "C30 irtn 0 %.4g" % C30D, "C29 irtn vin %.4g" % C29D, "C10 dref irtn %.4g" % C10D,
         "* U9 DiffAmpRef buffer", "XU9 u9p dref v12 0 %s LM7321_12V" % out("U9", "dref"),
         "R26 v12 r28a 100k", "R28a r28a wiper 50", "R28b wiper r28b 50", "R29 r28b 0 100k", "R21 wiper u9p %g" % max(r21, 1e-3), "C26 u9p 0 100n"]
    if tran:
        # the transmission line defeats the direct Newton operating point; a
        # nodeset at the known bias (references at +12/2, outputs at the
        # reference, the Si8921 outputs at its common mode) lets it converge
        L += [".nodeset V(irtn)=%.3f V(dref)=%.3f V(u3o)=%.3f V(u8o)=%.3f V(out)=%.3f V(u8p)=%.3f V(u5p)=%.3f V(u9p)=%.3f V(wiper)=%.3f" % ((v12 / 2,) * 9)
              + " V(aop)=%.2f V(aon)=%.2f V(u3p)=%.2f V(u3n)=%.2f V(aopi)=%.2f V(aoni)=%.2f" % ((SI["vocm_typ"],) * 6)]
    if loop:
        node = {"U3": "u3o", "U8": "u8o", "U5": "irtn", "U9": "dref"}[loop]
        L += ["* Tian probe at the %s output" % loop, "Vt %s %s_a DC 0 AC {1-iv}" % (node, node), "It 0 %s AC {iv}" % node,
              ".step param iv list 0 1"]
    return "\n".join(L) + "\n"


def run(name, txt, analysis):
    p = HERE / ("chain_%s.cir" % name)
    io.open(p, "w", encoding="latin-1", newline="\n").write(txt + analysis + "\n.end\n")
    run_ltspice(p)
    return read_raw(p.with_suffix(".raw"))


def do_ac(res):
    fig, ax = plt.subplots(figsize=(7.5, 4.2))
    for ctl, nm, g0 in ((1, "x100", 100.0), (0, "x10", 10.0)):
        r = run("ac_%s" % nm, chain(ctl), ".ac dec 100 1 10Meg")
        f = r.x(); g = np.abs(r.get("V(out)") - r.get("V(irtn)"))
        db = 20 * np.log10(g / g0)
        lf = db[(f > 10) & (f < 100)].mean()
        f3 = f[np.argmax(db < lf - 3)]; f01 = f[np.argmax(np.abs(db - lf) > 0.1)]; f1 = f[np.argmax(db < lf - 1)]
        res["ac"][nm] = dict(gain_lf=float(10 ** (lf / 20) * g0), f_3db=float(f3), f_0p1db=float(f01), f_1db=float(f1))
        ax.semilogx(f, db, label="%s: %.0f kHz (-3 dB), flat to %.0f kHz" % (nm, f3 / 1e3, f01 / 1e3))
        print("ac %s: gain %.3f, -3 dB %.0f kHz, 0.1 dB %.1f kHz, 1 dB %.0f kHz (bench: %s)" % (
            nm, 10 ** (lf / 20) * g0, f3 / 1e3, f01 / 1e3, f1 / 1e3, "60 kHz" if ctl else "580 kHz"))
    ax.axhline(-3, color="grey", lw=0.6, ls="--"); ax.set_ylim(-20, 3); ax.set_xlim(10, 10e6)
    ax.set_xlabel("Hz"); ax.set_ylabel("dB re nominal gain"); ax.grid(True, which="both", alpha=0.3); ax.legend(fontsize=8)
    ax.set_title("Simulated small-signal response, IsenseOut/Vshunt (behavioural Si8921, vendor op-amp models)", fontsize=9)
    fig.tight_layout(); fig.savefig(FIG / "sim-ac-response.png", dpi=110)


def do_op(res):
    rows = []
    for v12 in (12.0, 10.6):
        for ctl, nm in ((1, "x100"), (0, "x10")):
            for vsh in (0.0, 0.05 if ctl else 0.10, -(0.05 if ctl else 0.10)):
                for r21 in (0.0, 10e3):
                    r = run("op", chain(ctl, v12=v12, r21=r21, vsh="DC %.4f" % vsh), ".op")
                    g = lambda n: float(r.get("V(%s)" % n)[0])
                    row = dict(v12=v12, range=nm, vsh=vsh, r21=r21, aop=g("aop"), aon=g("aon"), u3p=g("u3p"), u3o=g("u3o"), u8p=g("u8p"),
                               u8o=g("u8o"), out=g("out") - g("irtn"), irtn=g("irtn"), dref=g("dref"), u5p=g("u5p"), u9p=g("u9p"),
                               i12_ma=-float(r.get("I(V12)")[0]) * 1e3)
                    rows.append(row)
                    print("op V12=%.1f %-5s Vsh=%+.3f R21=%5.0f: out %+.4f V, ref %.3f / %.3f (dref-irtn %+.2f mV), U3o %.3f U8o %.3f, I12 %.2f mA" % (
                        v12, nm, vsh, r21, row["out"], row["irtn"], row["dref"], (row["dref"] - row["irtn"]) * 1e3, row["u3o"], row["u8o"], row["i12_ma"]))
    res["op"] = rows


def do_noise(res):
    fig, ax = plt.subplots(figsize=(7.5, 4.2))
    for ctl, nm, bw in ((1, "x100", 60e3), (0, "x10", 580e3)):
        r = run("noise_%s" % nm, chain(ctl), ".noise V(out,irtn) Vsh dec 50 0.1 10Meg")
        f = r.x(); on = r.get("V(onoise)"); inn = r.get("V(inoise)")
        gain = 100.0 if ctl else 10.0
        tot = integrated_noise(f, on, 0.1, bw)
        res["noise"][nm] = dict(onoise_1k=float(np.interp(1e3, f, on)), onoise_10k=float(np.interp(10e3, f, on)),
                                inoise_1k=float(np.interp(1e3, f, inn)), out_rms_band=float(tot), in_rms_band_A=float(tot / gain / 0.01),
                                band_hz=bw)
        ax.loglog(f, on * 1e9, label="%s output: %.2f mV rms over %.0f kHz = %.1f mA rms input" % (nm, tot * 1e3, bw / 1e3, tot / gain / 0.01 * 1e3))
        print("noise %s: output %.1f nV/rtHz at 1 kHz, %.3f mV rms over %.0f kHz -> %.2f mA rms input-referred (bench x100: ~2 mA rms)" % (
            nm, np.interp(1e3, f, on) * 1e9, tot * 1e3, bw / 1e3, tot / gain / 0.01 * 1e3))
    ax.set_xlabel("Hz"); ax.set_ylabel("nV/rtHz at IsenseOut"); ax.grid(True, which="both", alpha=0.3); ax.legend(fontsize=8)
    ax.set_title("Simulated output noise density (Si8921 noise from its 77 dB SNR, op-amp models with noise)", fontsize=9)
    fig.tight_layout(); fig.savefig(FIG / "sim-noise.png", dpi=110)


def do_loop(res):
    fig, axs = plt.subplots(2, 1, figsize=(7.5, 7.0), sharex=True)
    cases = [("U3", 1), ("U8", 1), ("U8", 0), ("U5", 1), ("U9", 1)]
    for amp, ctl in cases:
        node = {"U3": "u3o", "U8": "u8o", "U5": "irtn", "U9": "dref"}[amp]
        r = run("loop_%s_%d" % (amp, ctl), chain(ctl, loop=amp), ".ac dec 60 10 100Meg")
        f = r.x(0)
        tv = (r.get("V(%s_a)" % node, 0), r.get("V(%s)" % node, 0))
        ti = r.get("I(Vt)", 1)
        T = tian_loop_gain(tv, ti)
        fc, _ = phase_margin(f, T)
        mag = 20 * np.log10(np.abs(T)); ph = np.degrees(np.unwrap(np.angle(T)))
        # unwrap leaves the whole curve offset by a multiple of 360: anchor the
        # low-frequency phase inside (-180, 180] so the margin reads as a margin
        # the margin is read from the phase wrapped into (-180, 180]; the
        # unwrapped curve accumulates +/-360 through the crossover region
        phw = (ph + 180.0) % 360.0 - 180.0
        pm = float(180.0 + ((np.interp(np.log10(fc), np.log10(f), ph) + 180.0) % 360.0 - 180.0)) if fc == fc else float("nan")
        # gain margin at the first -180 crossing above fc: a wrap of the wrapped phase
        gm = float("nan")
        above = f[1:] > fc
        wrap = (np.abs(np.diff(phw)) > 300) & above
        idx = np.nonzero(wrap)[0]
        if len(idx):
            gm = -float(mag[idx[0]])
        ph = phw
        key = "%s_%s" % (amp, "x100" if ctl else "x10")
        res["loop"][key] = dict(fc=fc, pm_deg=pm, gm_db=gm)
        print("loop %-8s crossover %.3g Hz, phase margin %.1f deg, gain margin %.1f dB" % (key, fc, pm, gm))
        axs[0].semilogx(f, mag, label="%s: fc %.2g Hz, PM %.0f deg" % (key, fc, pm)); axs[1].semilogx(f, ph)
    axs[0].axhline(0, color="grey", lw=0.6); axs[1].axhline(-180, color="grey", lw=0.6, ls="--")
    axs[0].set_ylabel("|T| dB"); axs[1].set_ylabel("phase deg"); axs[1].set_xlabel("Hz"); axs[0].set_ylim(-40, 120)
    axs[0].legend(fontsize=7); axs[0].grid(True, which="both", alpha=0.3); axs[1].grid(True, which="both", alpha=0.3)
    axs[0].set_title("Tian loop gain at each amplifier output, with the real loads", fontsize=9)
    fig.tight_layout(); fig.savefig(FIG / "sim-loop-gain.png", dpi=110)


def do_tran(res):
    fig, axs = plt.subplots(1, 2, figsize=(8.5, 3.6))
    for ax, (ctl, nm, step, fs) in zip(axs, ((1, "x100", 0.050, 5.0), (0, "x10", 0.100, 1.0))):
        r = run("tran_%s" % nm, chain(ctl, vsh="PWL(0 0 20u 0 20.05u %.4f 120u %.4f 120.05u %.4f 200u %.4f)" % (step, step, step * 1.3, step * 1.3), tran=True),
                ".tran 0 200u 0 20n")
        t = r.x(); v = r.get("V(out)") - r.get("V(irtn)")
        m = (t >= 20e-6) & (t <= 115e-6)
        vf = float(np.mean(v[(t > 100e-6) & (t < 115e-6)]))
        t10 = t[m][np.argmax(v[m] >= 0.1 * vf)]; t90 = t[m][np.argmax(v[m] >= 0.9 * vf)]; t50 = t[m][np.argmax(v[m] >= 0.5 * vf)]
        ovs = (float(v[m].max()) - vf) / vf * 100
        tol = 0.001 * fs
        outside = np.nonzero(np.abs(v[m] - vf) > tol)[0]
        tset = float(t[m][outside[-1]] - 20e-6) if len(outside) and outside[-1] < len(v[m]) - 1 else float("nan")
        vclamp = float(np.mean(v[(t > 180e-6)]))
        res["tran"][nm] = dict(final=vf, rise_10_90=float(t90 - t10), delay_50=float(t50 - 20e-6), overshoot_pct=ovs,
                               settle_0p1pct=tset, step_input_v=step, clamp_at_130pct=vclamp)
        print("tran %s: final %.4f V (%.1f %% of %.2f), rise %.2f us, delay %.2f us, overshoot %.2f %%, settle to 0.1 %% %.1f us, 130 %% step -> %.3f V" % (
            nm, vf, 100 * vf / fs, fs, (t90 - t10) * 1e6, (t50 - 20e-6) * 1e6, ovs, tset * 1e6, vclamp))
        ax.plot(t * 1e6, v, lw=1.0); ax.set_title("%s: %.0f mV shunt step (then 130 %%)" % (nm, step * 1e3), fontsize=9)
        ax.set_xlabel("us"); ax.set_ylabel("IsenseOut - ISenseRTN, V"); ax.grid(True, alpha=0.3)
    fig.tight_layout(); fig.savefig(FIG / "sim-step.png", dpi=110)


if __name__ == "__main__":
    what = sys.argv[1] if len(sys.argv) > 1 else "all"
    FIG.mkdir(parents=True, exist_ok=True)
    res_path = HERE / "chain_results.json"
    res = json.load(io.open(res_path)) if res_path.exists() else {}
    for k in ("ac", "op", "noise", "loop", "tran"):
        res.setdefault(k, {})
    res["model"] = dict(si8921="behavioural, Table 5: gain 8.2, two real poles (-3 dB 600 kHz), delay %.2f us total, Vocm %.2f V, clip 2.5 V diff, noise %.0f nV/rtHz" % (SI["tpd_typ"] * 1e6, SI["vocm_typ"], EN_IN * 1e9),
                        opa197="TI OPA197.LIB 2019", lm7321="LM7321.MOD 10 V group", c30_derated=C30D, c29_derated=C29D, c10=C10D)
    if what in ("ac", "all"):
        do_ac(res)
    if what in ("op", "all"):
        do_op(res)
    if what in ("noise", "all"):
        do_noise(res)
    if what in ("loop", "all"):
        do_loop(res)
    if what in ("tran", "all"):
        do_tran(res)
    io.open(res_path, "w", encoding="utf-8", newline="\n").write(json.dumps(res, indent=1))
    print("written -> sim/chain_results.json")
