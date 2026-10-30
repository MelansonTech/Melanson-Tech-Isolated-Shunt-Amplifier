# -*- coding: utf-8 -*-
"""Draw the reference section as built and as proposed (recommendation 1) as
readable LTspice schematics that run as they are: supplies, the trimmer as a
stepped parameter, a bias-imbalance current source and the model include.

Layout follows the hand-redraw of 2026-10-29: parts to a rail rise to a rail
label, parts between two drawn nodes go between them (C26 is a loop under
R21), the trimmer sits beside R33 at the left of its row, net names end
their lines, a far return is a vertical stub with a rotated name.

Each drawing is proved three ways before it is handed over:
  1. LTspice netlists it; every R/C and buffer is compared, node by node, with
     the bench block in ref_trim.py that produced the proposal's numbers;
  2. LTspice runs it in batch; the stepped operating point is compared with
     the spans in ref_trim.json (the bench's separate runs);
  3. it is rendered to PNG (docs/design-review/figures) and looked at.

    python ref_trim_asc.py

To use: open ref_proposed.asc (or ref_asbuilt.asc) in LTspice and run it. The
plot of V(dref)-V(irtn) against k is DiffAmpRef - ISenseRTN over the R28
wiper's travel (k = 0 at the GND end). Set ios=200n in the .param line to see
the LM7321 offset-current maximum at the U9 input. LM7321_12V.lib must sit
beside the .asc: this script copies it from ../models, where
make_lm7321_12v.py writes it from the vendor model. It is not in git.
"""
import io
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(Path.home() / ".claude/skills/ltspice/scripts"))
from asc_builder import Asc, opamp_block, netlist_of                    # noqa: E402
from ltspice_run import LTSPICE, run_ltspice, read_raw                  # noqa: E402
import ref_trim                                                          # noqa: E402

FIG = HERE.parent.parent.parent / "docs" / "design-review" / "figures"
RENDER = Path.home() / ".claude/skills/ltspice/scripts/render_asc.py"
MODEL = HERE.parent / "models" / "LM7321_12V.lib"
OA = opamp_block("LM7321_12V")      # .SUBCKT LM7321_12V 3 4 5 2 1 = +IN -IN +V -V OUT


def opamp(s, name, at_inp):
    """Place the buffer with IN+ at at_inp; wire IN- to OUT; returns (out point, v+ point, v- point)."""
    _, px, py, _ = OA.pins[0]
    o = (at_inp[0] - px, at_inp[1] - py)
    s.part(None, name, None, o, "R0", None, None, block=OA)
    pts = [(o[0] + x, o[1] + y) for _, x, y, _ in OA.pins]
    inn, vp, vn, out = pts[1], pts[2], pts[3], pts[4]
    # feedback: IN- left, down under the V- ground symbol, right past the body, up to OUT
    fb = inn[1] + 96
    s.wire(inn, (inn[0] - 32, inn[1]), (inn[0] - 32, fb), (out[0] + 24, fb), (out[0] + 24, out[1]), out)
    s.wire(vp, (vp[0], vp[1] - 24)); s.flag((vp[0], vp[1] - 24), "v12")
    s.wire(vn, (vn[0], vn[1] + 24)); s.flag((vn[0], vn[1] + 24), "0")
    return out, vp, vn


def gnd(s, pt):
    s.flag(pt, "0")


def isrc_into(s, name, value, node):
    """A current source hanging below `node` with its arrow pointing up into it: pin 1 (+) at
    ground, pin 2 (-) at the node, so LTspice writes 'name 0 node value' as the bench does."""
    o = (node[0], node[1] + 80)
    s.part("current", name, value, o, "R180")
    gnd(s, o)


def return_stub(s, pt, name, dy=64):
    """A far return: a vertical stub down from pt with the net name at its end, rotated."""
    s.wire(pt, (pt[0], pt[1] + dy))
    s.flag((pt[0], pt[1] + dy), name)


def draw_supplies(s, x, y):
    s.text((x - 32, y - 112), "supplies", size=2)
    for dx, name, val, net in ((0, "V12", "12", "v12"), (160, "Vin", "15", "vin")):
        top = (x + dx, y)
        s.wire((top[0], top[1] - 32), top); s.flag((top[0], top[1] - 32), net)
        gnd(s, s.vpart("voltage", name, val, top))


def directives(s, y, params, note):
    s.text((48, y), "Run: a stepped operating point. Plot V(dref)-V(irtn), DiffAmpRef - ISenseRTN, against k, the R28 wiper position: 0 = GND end, 1 = +12 end", size=2)
    s.text((48, y + 32), note, size=2)
    s.text((48, y + 64), "ios: current into the U9 input, 200n = the LM7321 offset-current maximum. Model: LM7321_12V.lib beside this file, written by ../models/make_lm7321_12v.py", size=2)
    s.directive((48, y + 104), ".include LM7321_12V.lib")
    s.directive((48, y + 136), ".param " + params)
    s.directive((48, y + 168), ".step param k 0 1 0.25")
    s.directive((48, y + 200), ".op")


def draw_common(s, y):
    """+12 divider, C4, U5 -> ISenseRTN with C29 rising to Vin and C30 to ground, and the supplies."""
    s.text((48, y - 144), "ISenseRTN: 100k/100k divider off +12, 100 nF, unity buffer U5 (LM7321), 22 uF to GND and to Vin", size=2)
    x = 112
    s.wire((x, y - 48), (x, y)); s.flag((x, y - 48), "v12")
    b = s.vpart("res", "R22", "100k", (x, y), note="0.1 %")
    u5p = (b[0], b[1] + 64); s.wire(b, u5p)
    gnd(s, s.vpart("res", "R17", "100k", u5p, note="0.1 %"))
    # C4 hangs to the right of the junction, clear of the R22/R17 notes; the buffer further right
    s.wire(u5p, (u5p[0] + 160, u5p[1]), (u5p[0] + 352, u5p[1]))
    s.flag((u5p[0] + 80, u5p[1]), "u5p")
    gnd(s, s.vpart("cap", "C4", "100n", (u5p[0] + 160, u5p[1])))
    out, vp, vn = opamp(s, "U5", (u5p[0] + 352, u5p[1]))
    # the ISenseRTN line: C29 rises to Vin, C30 hangs to ground, the name ends the line
    s.wire(out, (out[0] + 64, out[1]), (out[0] + 96, out[1]), (out[0] + 208, out[1]))
    s.flag((out[0] + 208, out[1]), "irtn")
    top = s.vpart("cap", "C29", "22u", (out[0] + 64, out[1]), note="to Vin", up=True)
    s.wire(top, (top[0], top[1] - 32)); s.flag((top[0], top[1] - 32), "vin")
    gnd(s, s.vpart("cap", "C30", "22u", (out[0] + 96, out[1]), note="to GND"))
    draw_supplies(s, 1040, y + 32)


def draw_asbuilt():
    s = Asc(2400, 1500)
    y = 224
    draw_common(s, y)
    # second divider with the trimmer, on a second row
    y2 = y + 512
    s.text((48, y2 - 144), "DiffAmpRef as built: a second 100k/100k divider with R28 (100 R) in the middle, R21 (10 k on the board, 0 R on the sheet), 100 nF, buffer U9; C10 22 uF ties the two references", size=2)
    x = 128
    s.wire((x, y2 - 48), (x, y2)); s.flag((x, y2 - 48), "v12")
    b = s.vpart("res", "R26", "100k", (x, y2), note="0.1 %")
    a = (b[0], b[1] + 32); s.wire(b, a); s.wire(a, (a[0] - 48, a[1])); s.flag((a[0] - 48, a[1]), "r28a")
    b = s.vpart("res", "R28a", "{ra}", a)
    w = (b[0], b[1] + 32); s.wire(b, w)
    s.wire(w, (w[0] - 48, w[1])); s.flag((w[0] - 48, w[1]), "wiper")
    b = s.vpart("res", "R28b", "{rb}", w)
    a = (b[0], b[1] + 32); s.wire(b, a); s.wire(a, (a[0] - 48, a[1])); s.flag((a[0] - 48, a[1]), "r28b")
    gnd(s, s.vpart("res", "R29", "100k", a, note="0.1 %"))
    # the wiper row: R21, then C26 to ground, the bias-imbalance source, U9, C10 and the name at the end
    s.wire(w, (w[0] + 224, w[1]))
    r = s.hpart("res", "R21", "{r21}", (w[0] + 224, w[1]), note="board 10k")
    u9p = (r[0] + 64, r[1])
    s.wire(r, u9p, (u9p[0] + 176, u9p[1]), (u9p[0] + 336, u9p[1])); s.flag((u9p[0] + 112, u9p[1]), "u9p")
    gnd(s, s.vpart("cap", "C26", "100n", u9p))
    isrc_into(s, "Ios", "{ios}", (u9p[0] + 176, u9p[1]))
    out, vp, vn = opamp(s, "U9", (u9p[0] + 336, u9p[1]))
    s.wire(out, (out[0] + 96, out[1]), (out[0] + 176, out[1])); s.flag((out[0] + 176, out[1]), "dref")
    return_stub(s, s.vpart("cap", "C10", "22u", (out[0] + 96, out[1]), note="to ISenseRTN"), "irtn")
    directives(s, 1232, "r21=10k ra=100*(1-k)+1m rb=100*k+1m ios=0",
               "r21: 10k as fitted on the Rev 3.1 board; the sheet says 0 R (use 1m). ra, rb: the two halves of R28 (100 R) either side of the wiper")
    return s


def draw_proposed():
    s = Asc(2400, 1500)
    y = 224
    draw_common(s, y)
    y2 = y + 512
    s.text((48, y2 - 128), "DiffAmpRef proposed: ISenseRTN through R21 (100 R, 0.1 %) to the U9 input; the trim is a current from the wiper of R28 (10 k) through R33 (100 k); R26 and R29 deleted", size=2)
    s.text((48, y2 - 96), "dV = (Vwiper - ISenseRTN) x 100 / 100.1k = +/-6 mV over the pot's travel, 18 turns; 200 nA of U9 bias current moves it 20 uV", size=2)
    # ISenseRTN comes in from the left through R21 to the U9 input node
    x0, yr = 112, y2 + 64
    s.wire((x0, yr), (x0 + 16, yr), (x0 + 48, yr)); s.flag((x0, yr), "irtn")
    r = s.hpart("res", "R21", "100", (x0 + 48, yr), note="0.1 %")
    node = (r[0] + 64, r[1])
    # the node row: junction label, riser down to the R33 row, the bias-imbalance source, then U9
    s.wire(r, node, (node[0] + 224, node[1]), (node[0] + 288, node[1]), (node[0] + 448, node[1]))
    s.flag((node[0] + 128, node[1]), "u9p")
    # C26 is a loop under R21, between ISenseRTN and the node
    yl = yr + 112
    s.wire((x0 + 16, yr), (x0 + 16, yl), (x0 + 48, yl))
    cr = s.hpart("cap", "C26", "100n", (x0 + 48, yl), note_at=((x0 + 16 + node[0]) // 2, yr + 24, "Center"))
    s.wire(cr, (node[0], yl), node)
    # the trimmer beside R33 at the left of the wiper row, R33 feeding the riser
    xp, yw = 64, yl + 128
    s.wire((xp, yw - 160), (xp, yw - 112)); s.flag((xp, yw - 160), "v12")
    b = s.vpart("res", "R28a", "{ra}", (xp, yw - 112))
    s.wire(b, (xp, yw), (xp + 272, yw)); s.flag((xp + 144, yw), "wiper")
    gnd(s, s.vpart("res", "R28b", "{rb}", (xp, yw)))
    r33 = s.hpart("res", "R33", "100k", (xp + 272, yw))
    s.wire(r33, (node[0] + 224, yw), (node[0] + 224, node[1]))
    isrc_into(s, "Ios", "{ios}", (node[0] + 288, node[1]))
    out, vp, vn = opamp(s, "U9", (node[0] + 448, node[1]))
    s.wire(out, (out[0] + 96, out[1]), (out[0] + 176, out[1])); s.flag((out[0] + 176, out[1]), "dref")
    return_stub(s, s.vpart("cap", "C10", "22u", (out[0] + 96, out[1]), note="to ISenseRTN"), "irtn")
    directives(s, 1232, "ra=10k*(1-k)+1m rb=10k*k+1m ios=0",
               "ra, rb: the two halves of R28 (10 k) either side of the wiper")
    return s


def prove(asc_path, bench_lines):
    """LTspice netlists the drawing; compare elements with the bench. Returns (differences, netlist text)."""
    net = netlist_of(asc_path, LTSPICE)
    models = {"LM7321_12V"}

    def parse(text):
        # the skill's elements() drops the node list of a block once it has stripped LTspice's X-section prefix
        out = {}
        for line in text.splitlines():
            line = line.strip()
            if not line or line[0] in "*.+":
                continue
            tok = line.split()
            name = tok[0]
            for pre in ("X§", "XÂ§", "X"):
                if name.startswith(pre) and len(name) > len(pre):
                    name = name[len(pre):]
                    break
            name = name.upper()
            if tok[0][0].upper() == "X":
                i = next(k for k, t in enumerate(tok) if t in models)
                out[name] = tuple(t.lower() for t in tok[1:i]) + (tok[i],)
            elif tok[0][0].upper() in "RLC":
                out[name] = tuple(sorted(t.lower() for t in tok[1:3]))
        return out
    a, b = parse(net), parse("\n".join(bench_lines))
    bad = []
    for k in sorted(set(a) | set(b)):
        if k not in a:
            bad.append(("missing in drawing", k, b[k]))
        elif k not in b:
            bad.append(("extra in drawing", k, a[k]))
        elif a[k] != b[k]:
            bad.append(("nodes differ", k, a[k], b[k]))
    return bad, net


def run_check(asc_path, expect_mV):
    """Run the schematic itself in batch; compare its stepped operating point with the bench spans."""
    log = run_ltspice(asc_path)
    r = read_raw(asc_path.with_suffix(".raw"))
    k = r.get("k")
    dv = (r.get("V(dref)") - r.get("V(irtn)")) * 1e3
    diff = np.abs(dv - np.array(expect_mV, dtype=float))
    warnings = sorted({l.strip() for l in log.splitlines() if "warn" in l.lower() or "listed twice" in l})
    return dict(k=[float(v) for v in k], dv_mV=[float(v) for v in dv], bench_mV=list(expect_mV),
                max_diff_uV=float(diff.max() * 1e3), log_warnings=warnings)


if __name__ == "__main__":
    shutil.copy(MODEL, HERE / MODEL.name)
    R = json.load(io.open(HERE / "ref_trim.json", encoding="utf-8"))["circuits"]
    out, ok = {}, True
    for name, s, bench, key in (("ref_asbuilt", draw_asbuilt(), ref_trim.asbuilt(k=0.5, r21=10e3), "asbuilt_r21_10k"),
                                ("ref_proposed", draw_proposed(), ref_trim.proposed(k=0.5), "proposed")):
        p = HERE / (name + ".asc")
        s.write(p)
        ov = s.check()
        bad, net = prove(p, bench)
        ios_ok = re.search(r"(?im)^Ios\s+0\s+u9p\s", net) is not None
        run = run_check(p, R[key]["dv_mV"])
        good = not ov and not bad and ios_ok and run["max_diff_uV"] < 5.0 and not run["log_warnings"]
        ok = ok and good
        print("%s: %d overlap(s) %s; netlist differences: %d %s; Ios into u9p: %s; stepped .op vs bench: max %.2f uV; log warnings: %s -> %s" % (
            name, len(ov), ov[:4], len(bad), bad[:6], ios_ok, run["max_diff_uV"], run["log_warnings"] or "none", "OK" if good else "FAIL"))
        png = FIG / (name + ".png")
        subprocess.run([sys.executable, str(RENDER), str(p), str(png)], check=False)
        out[name] = dict(overlaps=ov, netlist_diff=[list(map(str, b)) for b in bad], ios_into_u9p=ios_ok, stepped_op=run)
    io.open(HERE / "ref_trim_asc.json", "w", encoding="utf-8", newline="\n").write(json.dumps(out, indent=1))
    sys.exit(0 if ok else 1)
