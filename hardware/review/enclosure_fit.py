# -*- coding: utf-8 -*-
"""Height budget of the board in the 50 x 58 x 24 mm split aluminium case.

The case has no drawing; the only geometry on record is docs/ASSEMBLY.md's
panel table, read from the printed end plates: the J1 SMA cutout centre at
Y = 8.75 mm from the panel bottom, the LED holes at Y = 18.0, the J4 cutout
8.1-19.6. An end-launch SMA sits on the board's mid-plane, so the board's
mid-plane is 8.75 mm above the panel bottom with the BOTTOM side of the
board (J4, SW1, C7, Rel1, PSU1, CM1, LEDs) facing up.

Wall thickness is not on record either; 1.5 mm is assumed and swept, and
that is the input the check needs.

Component heights: the board file's HEIGHT where the library set one, the
datasheet drawing otherwise (named), EST where neither.

    python enclosure_fit.py
"""
import io
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
CASE_H = 24.0
BOARD_T = 1.6
Y_MID = 8.75                     # board mid-plane above the panel bottom, from the SMA cutout
HEIGHTS = {  # ref: (side, height mm, source)
    "J4": ("BOTTOM", 11.0, "pj-002a.pdf drawing, 11.00"),
    "C7 standing": ("BOTTOM", 16.0, "a750.pdf: MV size code = 10 x 16 mm can; if mounted upright"),
    "C7 lying (RA1)": ("BOTTOM", 10.0, "a750.pdf: 10 mm diameter; the footprint name (RA1) implies a right-angle, lying mount"),
    "SW1": ("BOTTOM", 4.7, "os103011.pdf: frame H = 4.7 mm; actuator passes through the panel slot"),
    "Rel1": ("BOTTOM", 4.2, "g6l.pdf G6L-1F drawing 4.2 +/-0.2"),
    "CM1": ("BOTTOM", 5.0, "board file HEIGHT 5.0"),
    "PSU1": ("BOTTOM", 4.0, "board file HEIGHT 4.0"),
    "J2": ("BOTTOM", 10.5, "EST: BCH-508HS 2-pos header, through Panel B cutout 9.5 mm tall"),
    "R28": ("BOTTOM", 5.0, "EST: CT-94 top-adjust body"),
    "D4/D5": ("BOTTOM", 9.0, "panel LED holes at Y 18.0: leads formed to reach the panel, EST"),
    "U2": ("TOP", 2.8, "board file HEIGHT 2.8"),
    "Q5/Q6": ("TOP", 2.4, "board file HEIGHT 2.38"),
    "U1/U6": ("TOP", 2.0, "board file HEIGHT 2.0"),
    "C11/C12": ("TOP", 1.6, "EST: 1206 4.7 uF 50 V"),
    "C1 (0805 HD)": ("TOP", 1.4, "board file HEIGHT 1.4"),
}

if __name__ == "__main__":
    out = dict(case_h=CASE_H, board_t=BOARD_T, y_mid=Y_MID, cases={})
    for wall in (1.0, 1.5, 2.0):
        avail_bottom = CASE_H - wall - (Y_MID + BOARD_T / 2)
        avail_top = (Y_MID - BOARD_T / 2) - wall
        rows = []
        for ref, (side, h, src) in HEIGHTS.items():
            avail = avail_bottom if side == "BOTTOM" else avail_top
            rows.append(dict(ref=ref, side=side, h=h, avail=avail, margin=avail - h, src=src))
        out["cases"]["wall_%.1f" % wall] = dict(avail_bottom=avail_bottom, avail_top=avail_top, rows=rows)
        print("wall %.1f mm: available above the bottom side (facing up) %.2f mm, above the top side (facing down) %.2f mm" % (wall, avail_bottom, avail_top))
        for r in sorted(rows, key=lambda r: r["margin"]):
            flag = "INTERFERES" if r["margin"] < 0 else ("tight" if r["margin"] < 1.0 else "")
            print("   %-13s %-6s h %5.1f  avail %5.2f  margin %+5.2f  %s  (%s)" % (r["ref"], r["side"], r["h"], r["avail"], r["margin"], flag, r["src"][:60]))
    io.open(os.path.join(HERE, "enclosure_fit.json"), "w", encoding="utf-8", newline="\n").write(json.dumps(out, indent=1))
    print("written -> enclosure_fit.json")
