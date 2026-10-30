# -*- coding: utf-8 -*-
"""Draw the reference section as built and as proposed (recommendation 1) as
readable LTspice schematics that run as they are: supplies, the trimmer as a
stepped parameter, a bias-imbalance current source and the model include.

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
from asc_builder import Asc, Block, STOCK, rot_pt, netlist_of          # noqa: E402
from ltspice_run import LTSPICE, run_ltspice, read_raw                  # noqa: E402
import ref_trim                                                          # noqa: E402

FIG = HERE.parent.parent.parent / "docs" / "design-review" / "figures"
RENDER = Path.home() / ".claude/skills/ltspice/scripts/render_asc.py"
MODEL = HERE.parent / "models" / "LM7321_12V.lib"
OA = Block("LM7321_12V", 128, 96, [("IN+", 0, 32, "LEFT"), ("IN-", 0, 64, "LEFT"), ("V+", 64, 0, "TOP"),
                                   ("V-", 64, 96, "BOTTOM"), ("OUT", 128, 48, "RIGHT")], title="buffer")
STUB = 48


def vert(s, sym, name, value, top, note=None):
    p = STOCK[sym][0]
    o = (top[0] - p[0][0], top[1] - p[0][1])
    s.part(sym, name, value, o, "R0", None, note)
    return (o[0] + p[1][0], o[1] + p[1][1])


def horiz(s, sym, name, value, left, note=None):
    p = STOCK[sym][0]
    r1, r2 = rot_pt(*p[0], "R270"), rot_pt(*p[1], "R270")
    o = (left[0] - r1[0], left[1] - r1[1])
    s.part(sym, name, value, o, "R270", None, note)
    return (o[0] + r2[0], o[1] + r2[1])


def opamp(s, name, at_inp, note=None):
    """Place the buffer with IN+ at at_inp; wire IN- to OUT; returns (out point, v+ point, v- point)."""
    _, px, py, _ = OA.pins[0]
    o = (at_inp[0] - px, at_inp[1] - py)
    s.part(None, name, None, o, "R0", None, note, block=OA)
    pts = [(o[0] + x, o[1] + y) for _, x, y, _ in OA.pins]
    inn, vp, vn, out = pts[1], pts[2], pts[3], pts[4]
    # feedback: IN- left, down, right under the body, up to OUT
    s.wire(inn, (inn[0] - 32, inn[1]), (inn[0] - 32, inn[1] + 128), (out[0] + 24, inn[1] + 128), (out[0] + 24, out[1]), out)
    s.wire(vp, (vp[0], vp[1] - 24)); s.flag((vp[0], vp[1] - 24), "v12")
    s.wire(vn, (vn[0], vn[1] + 24)); s.flag((vn[0], vn[1] + 24), "0")
    return out, vp, vn


def gnd(s, pt):
    s.flag(pt, "0")


def label(s, pt, name, dx=STUB):
    b = (pt[0] + dx, pt[1])
    s.wire(pt, b)
    s.flag(b, name)


def isrc_into(s, name, value, node):
    """A current source hanging below `node` with its arrow pointing up into it: pin 1 (+) at
    ground, pin 2 (-) at the node, so LTspice writes 'name 0 node value' as the bench does."""
    o = (node[0], node[1] + 80)
    s.part("current", name, value, o, "R180")
    gnd(s, o)


def draw_supplies(s, x, y):
    s.text((x - 32, y - 96), "supplies", size=2)
    for dx, name, val, net in ((0, "V12", "12", "v12"), (160, "Vin", "15", "vin")):
        top = (x + dx, y)
        s.wire((top[0], top[1] - 32), top); s.flag((top[0], top[1] - 32), net)
        gnd(s, vert(s, "voltage", name, val, top))


def directives(s, y, params, note):
    s.text((48, y), "Run: a stepped operating point. Plot V(dref)-V(irtn), DiffAmpRef - ISenseRTN, against k, the R28 wiper position: 0 = GND end, 1 = +12 end", size=2)
    s.text((48, y + 24), note, size=2)
    s.text((48, y + 48), "ios: current into the U9 input, 200n = the LM7321 offset-current maximum. Model: LM7321_12V.lib beside this file, written by ../models/make_lm7321_12v.py", size=2)
    s.directive((48, y + 88), ".include LM7321_12V.lib")
    s.directive((48, y + 112), ".param " + params)
    s.directive((48, y + 136), ".step param k 0 1 0.25")
    s.directive((48, y + 160), ".op")


def draw_common(s, y):
    """+12 divider, C4, U5 -> ISenseRTN with C30 and C29. Returns the ISenseRTN line point."""
    s.text((48, y - 120), "ISenseRTN: 100k/100k divider off +12, 100 nF, unity buffer U5 (LM7321), 22 uF to GND and to Vin", size=2)
    x = 112
    s.wire((x, y - 48), (x, y)); s.flag((x, y - 48), "v12")
    b = vert(s, "res", "R22", "100k", (x, y), note="0.1 %")
    u5p = (b[0], b[1] + 48); s.wire(b, u5p)
    b2 = vert(s, "res", "R17", "100k", u5p, note="0.1 %")
    gnd(s, b2)
    # C4 hangs to the right of the junction, clear of the R22/R17 notes
    s.wire(u5p, (u5p[0] + 160, u5p[1]))
    s.flag((u5p[0] + 80, u5p[1]), "u5p")
    c = vert(s, "cap", "C4", "100n", (u5p[0] + 160, u5p[1])); gnd(s, c)
    # buffer, far enough right that its feedback wire clears the C4 note
    s.wire((u5p[0] + 160, u5p[1]), (u5p[0] + 352, u5p[1]))
    out, vp, vn = opamp(s, "U5", (u5p[0] + 352, u5p[1]))
    line = (out[0] + 96, out[1])
    s.wire(out, line)
    s.flag((out[0] + 48, out[1] - 0), "irtn")
    # C30 to ground, C29 to Vin, hanging from the line
    c30 = vert(s, "cap", "C30", "22u", (line[0], line[1]), note="to GND"); gnd(s, c30)
    s.wire(line, (line[0] + 128, line[1]))
    c29 = vert(s, "cap", "C29", "22u", (line[0] + 128, line[1]), note="to Vin")
    s.wire(c29, (c29[0], c29[1] + 32), (c29[0] + 48, c29[1] + 32)); s.flag((c29[0] + 48, c29[1] + 32), "vin")
    draw_supplies(s, 1040, y + 32)
    return (line[0] + 128, line[1]), u5p


def draw_asbuilt():
    s = Asc(2400, 1500)
    y = 224
    draw_common(s, y)
    # second divider with the trimmer, on a second row
    y2 = y + 512
    s.text((48, y2 - 120), "DiffAmpRef as built: a second 100k/100k divider with R28 (100 R) in the middle, R21 (10 k on the board, 0 R on the sheet), 100 nF, buffer U9; C10 22 uF ties the two references", size=2)
    x = 112
    s.wire((x, y2 - 48), (x, y2)); s.flag((x, y2 - 48), "v12")
    b = vert(s, "res", "R26", "100k", (x, y2), note="0.1 %")
    a = (b[0], b[1] + 32); s.wire(b, a); s.wire(a, (a[0] + 64, a[1])); s.flag((a[0] + 64, a[1]), "r28a")
    b = vert(s, "res", "R28a", "{ra}", a, note="R28 100 R")
    w = (b[0], b[1] + 32); s.wire(b, w)
    s.wire(w, (w[0] + 64, w[1])); s.flag((w[0] + 64, w[1]), "wiper")
    b = vert(s, "res", "R28b", "{rb}", w)
    a = (b[0], b[1] + 32); s.wire(b, a); s.wire(a, (a[0] + 64, a[1])); s.flag((a[0] + 64, a[1]), "r28b")
    b = vert(s, "res", "R29", "100k", a, note="0.1 %"); gnd(s, b)
    # R21 from the wiper to the right, then C26, the bias-imbalance source and U9
    r = horiz(s, "res", "R21", "{r21}", (w[0] + 160, w[1]), note="board 10k")
    s.wire((w[0] + 64, w[1]), (w[0] + 160, w[1]))
    u9p = (r[0] + 64, r[1]); s.wire(r, u9p)
    c = vert(s, "cap", "C26", "100n", u9p); gnd(s, c)
    s.wire(u9p, (u9p[0] + 176, u9p[1]), (u9p[0] + 336, u9p[1])); s.flag((u9p[0] + 112, u9p[1]), "u9p")
    isrc_into(s, "Ios", "{ios}", (u9p[0] + 176, u9p[1]))
    out, vp, vn = opamp(s, "U9", (u9p[0] + 336, u9p[1]))
    line = (out[0] + 96, out[1]); s.wire(out, line); s.flag((out[0] + 48, out[1]), "dref")
    c10 = vert(s, "cap", "C10", "22u", line, note="to ISenseRTN")
    s.wire(c10, (c10[0], c10[1] + 32), (c10[0] + 48, c10[1] + 32)); s.flag((c10[0] + 48, c10[1] + 32), "irtn")
    directives(s, 1232, "r21=10k ra=100*(1-k)+1m rb=100*k+1m ios=0",
               "r21: 10k as fitted on the Rev 3.1 board; the sheet says 0 R (use 1m). ra, rb: the two halves of R28 (100 R) either side of the wiper")
    return s


def draw_proposed():
    s = Asc(2400, 1500)
    y = 224
    draw_common(s, y)
    y2 = y + 512
    s.text((48, y2 - 120), "DiffAmpRef proposed: ISenseRTN through R21 (100 R, 0.1 %) to the U9 input; the trim is a current from R28's wiper through R33 (100 k); R26 and R29 deleted", size=2)
    s.text((48, y2 - 96), "dV = (Vwiper - ISenseRTN) x 100 / 100.1k = +/-6 mV over the pot's travel, 18 turns; 200 nA of U9 bias current moves it 20 uV", size=2)
    # the pot across the rails, a column at the right of the row
    xp = 1232
    y2 = y2 + 160
    s.wire((xp, y2 - 48), (xp, y2)); s.flag((xp, y2 - 48), "v12")
    b = vert(s, "res", "R28a", "{ra}", (xp, y2), note="R28 10k")
    w = (b[0], b[1] + 32); s.wire(b, w)
    b = vert(s, "res", "R28b", "{rb}", w)
    gnd(s, b)
    # R33 from the wiper leftward to the U9 input node
    s.wire(w, (w[0] - 48, w[1]))
    r33 = horiz(s, "res", "R33", "100k", (w[0] - 128, w[1]))     # right pin lands on the wiper wire at w-48
    u9p = (w[0] - 128, w[1])                                      # the left pin of R33
    s.wire(w, (w[0] + 48, w[1])); s.flag((w[0] + 48, w[1]), "wiper")
    # ISenseRTN comes in from the left through R21 to the U9 input node
    x0 = 112
    y2 = y2 - 160
    s.wire((x0, y2 + 64), (x0 + 48, y2 + 64)); s.flag((x0, y2 + 64), "irtn")
    r = horiz(s, "res", "R21", "100", (x0 + 48, y2 + 64), note="0.1 %")
    node = (r[0] + 64, r[1]); s.wire(r, node)
    c = vert(s, "cap", "C26", "100n", node, note="to ISenseRTN")
    s.wire(c, (c[0], c[1] + 32), (c[0] + 48, c[1] + 32)); s.flag((c[0] + 48, c[1] + 32), "irtn")
    # the node row: riser down to the R33 row, the bias-imbalance source, then U9
    s.wire(node, (node[0] + 176, node[1]), (node[0] + 240, node[1]), (node[0] + 384, node[1]))
    s.flag((node[0] + 112, node[1]), "u9p")
    s.wire((node[0] + 176, node[1]), (node[0] + 176, w[1]), u9p)
    isrc_into(s, "Ios", "{ios}", (node[0] + 240, node[1]))
    out, vp, vn = opamp(s, "U9", (node[0] + 384, node[1]))
    line = (out[0] + 96, out[1]); s.wire(out, line); s.flag((out[0] + 48, out[1]), "dref")
    c10 = vert(s, "cap", "C10", "22u", line, note="to ISenseRTN")
    s.wire(c10, (c10[0], c10[1] + 32), (c10[0] + 48, c10[1] + 32)); s.flag((c10[0] + 48, c10[1] + 32), "irtn")
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
    # the drawing's buffers have V+ / V- on the rails as the bench does; compare the parts both carry
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
    run_ltspice(asc_path)
    r = read_raw(asc_path.with_suffix(".raw"))
    k = r.get("k")
    dv = (r.get("V(dref)") - r.get("V(irtn)")) * 1e3
    diff = np.abs(dv - np.array(expect_mV, dtype=float))
    return dict(k=[float(v) for v in k], dv_mV=[float(v) for v in dv], bench_mV=list(expect_mV),
                max_diff_uV=float(diff.max() * 1e3))


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
        good = not ov and not bad and ios_ok and run["max_diff_uV"] < 5.0
        ok = ok and good
        print("%s: %d overlap(s) %s; netlist differences: %d %s; Ios into u9p: %s; stepped .op vs bench: max %.2f uV -> %s" % (
            name, len(ov), ov[:4], len(bad), bad[:6], ios_ok, run["max_diff_uV"], "OK" if good else "FAIL"))
        png = FIG / (name + ".png")
        subprocess.run([sys.executable, str(RENDER), str(p), str(png)], check=False)
        out[name] = dict(overlaps=ov, netlist_diff=[list(map(str, b)) for b in bad], ios_into_u9p=ios_ok, stepped_op=run)
    io.open(HERE / "ref_trim_asc.json", "w", encoding="utf-8", newline="\n").write(json.dumps(out, indent=1))
    sys.exit(0 if ok else 1)
