# -*- coding: utf-8 -*-
"""Draw the reference section as built and as proposed (recommendation 1) as
readable LTspice schematics, prove each against its bench netlist in
ref_trim.py, and render both to PNG for the proposal page.

    python ref_trim_asc.py
"""
import io
import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(Path.home() / ".claude/skills/ltspice/scripts"))
from asc_builder import Asc, Block, STOCK, rot_pt, netlist_of, elements   # noqa: E402
from ltspice_run import LTSPICE                                            # noqa: E402
import ref_trim                                                            # noqa: E402

FIG = HERE.parent.parent.parent / "docs" / "design-review" / "figures"
RENDER = Path.home() / ".claude/skills/ltspice/scripts/render_asc.py"
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
    return (line[0] + 128, line[1]), u5p


def draw_asbuilt(r21):
    s = Asc(2400, 1400)
    y = 224
    irtn_pt, _ = draw_common(s, y)
    # second divider with the trimmer, on a second row
    y2 = y + 512
    s.text((48, y2 - 120), "DiffAmpRef as built: a second 100k/100k divider with R28 (100 R) in the middle, R21 (%s), 100 nF, buffer U9; C10 22 uF ties the two references" % ("10 k on the board" if r21 else "0 R on the sheet"), size=2)
    x = 112
    s.wire((x, y2 - 48), (x, y2)); s.flag((x, y2 - 48), "v12")
    b = vert(s, "res", "R26", "100k", (x, y2), note="0.1 %")
    a = (b[0], b[1] + 32); s.wire(b, a); s.wire(a, (a[0] + 64, a[1])); s.flag((a[0] + 64, a[1]), "r28a")
    b = vert(s, "res", "R28a", "50", a, note="R28 100 R")
    w = (b[0], b[1] + 32); s.wire(b, w)
    s.wire(w, (w[0] + 64, w[1])); s.flag((w[0] + 64, w[1]), "wiper")
    b = vert(s, "res", "R28b", "50", w)
    a = (b[0], b[1] + 32); s.wire(b, a); s.wire(a, (a[0] + 64, a[1])); s.flag((a[0] + 64, a[1]), "r28b")
    b = vert(s, "res", "R29", "100k", a, note="0.1 %"); gnd(s, b)
    # R21 from the wiper to the right, then C26 and U9
    r = horiz(s, "res", "R21", "10k" if r21 else "0", (w[0] + 160, w[1]), note="board / sheet")
    s.wire((w[0] + 64, w[1]), (w[0] + 160, w[1]))
    u9p = (r[0] + 64, r[1]); s.wire(r, u9p)
    c = vert(s, "cap", "C26", "100n", u9p); gnd(s, c)
    s.wire(u9p, (u9p[0] + 192, u9p[1])); s.flag((u9p[0] + 112, u9p[1]), "u9p")
    out, vp, vn = opamp(s, "U9", (u9p[0] + 192, u9p[1]))
    line = (out[0] + 96, out[1]); s.wire(out, line); s.flag((out[0] + 48, out[1]), "dref")
    c10 = vert(s, "cap", "C10", "22u", line, note="to ISenseRTN")
    s.wire(c10, (c10[0], c10[1] + 32), (c10[0] + 48, c10[1] + 32)); s.flag((c10[0] + 48, c10[1] + 32), "irtn")
    return s


def draw_proposed():
    s = Asc(2400, 1400)
    y = 224
    irtn_pt, _ = draw_common(s, y)
    y2 = y + 512
    s.text((48, y2 - 120), "DiffAmpRef proposed: ISenseRTN through R21 (100 R, 0.1 %) to the U9 input; the trim is a current from R28's wiper through R33 (100 k); R26 and R29 deleted", size=2)
    s.text((48, y2 - 96), "dV = (Vwiper - ISenseRTN) x 100 / 100.1k = +/-6 mV over the pot's travel, 18 turns; 200 nA of U9 bias current moves it 20 uV", size=2)
    # the pot across the rails, a column at the right of the row
    xp = 1232
    y2 = y2 + 160
    s.wire((xp, y2 - 48), (xp, y2)); s.flag((xp, y2 - 48), "v12")
    b = vert(s, "res", "R28a", "5k", (xp, y2), note="R28 10k")
    w = (b[0], b[1] + 32); s.wire(b, w)
    b = vert(s, "res", "R28b", "5k", w)
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
    # node up to the R33 row and across to R33's left pin
    s.wire(node, (node[0] + 256, node[1])); s.flag((node[0] + 112, node[1]), "u9p")
    out, vp, vn = opamp(s, "U9", (node[0] + 256, node[1]))
    s.wire((node[0] + 176, node[1]), (node[0] + 176, w[1]), u9p)
    line = (out[0] + 96, out[1]); s.wire(out, line); s.flag((out[0] + 48, out[1]), "dref")
    c10 = vert(s, "cap", "C10", "22u", line, note="to ISenseRTN")
    s.wire(c10, (c10[0], c10[1] + 32), (c10[0] + 48, c10[1] + 32)); s.flag((c10[0] + 48, c10[1] + 32), "irtn")
    return s


def prove(asc_path, bench_lines):
    """LTspice netlists the drawing; compare elements with the bench."""
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
            for pre in ("X\u00a7", "X\u00c2\u00a7", "X"):
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
    return bad


if __name__ == "__main__":
    out = {}
    for name, s, bench in (("ref_asbuilt", draw_asbuilt(True), ref_trim.asbuilt(k=0.5, r21=10e3)),
                           ("ref_proposed", draw_proposed(), ref_trim.proposed(k=0.5))):
        p = HERE / (name + ".asc")
        s.write(p)
        ov = s.check()
        bad = prove(p, bench)
        print("%s: %d overlap(s) %s; netlist differences: %d %s" % (name, len(ov), ov[:4], len(bad), bad[:6]))
        png = FIG / (name + ".png")
        subprocess.run([sys.executable, str(RENDER), str(p), str(png)], check=False)
        out[name] = dict(overlaps=ov, netlist_diff=[list(map(str, b)) for b in bad])
    io.open(HERE / "ref_trim_asc.json", "w", encoding="utf-8", newline="\n").write(__import__("json").dumps(out, indent=1))
