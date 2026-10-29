# -*- coding: utf-8 -*-
"""Carry the fifteen findings of docs/DESIGN_REVIEW.md (schematic-level,
2026-08-20/21) into the register under the project's own numbering F1..F15,
with the status the documentation gives them as of the 2026-09-06 bench
campaign. Run once; re-running updates titles and leaves status history alone.

    python legacy_findings.py
"""
import io
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from register import load, save, today                       # noqa: E402

REG = os.path.join(HERE, "findings_register.json")
SRC = "docs/DESIGN_REVIEW.md (schematic-level review, 2026-08-20)"

# id, area, severity, title, detail, net, status, closed_by
LEGACY = [
    ("F1", "documentation", 2, "Isolated auxiliary supply requirement was undocumented",
     "ISenseRTN is bonded to chassis and board GND floats 6 V below it; an earthed supply shorts U5. README, CONNECTORS.md and the Rev 3.1 silkscreen now state it. The suggested series resistor in the chassis-bond leg is not fitted.",
     "ISENSERTN", "closed", "README/silkscreen, Rev 3.1 outputs 2026-08-20"),
    ("F2", "power", 2, "+12 rail unregulated below ~14.9 V at the jack",
     "UA78L12 needs 14.5 V in; one Schottky on the x10 range. Headroom on the 5 A range shrinks to 0.32 V at 13 V. Re-examined in this review with both diode drops on the x100 range.",
     "+12", "open", None),
    ("F3", "analog", 3, "R21 asymmetry between the two reference buffers (10 k vs 0)",
     "Recommended 100 ohm. The sheets now carry R21 = 0 ohm (CR0805-J/-000ELF); the board still carries CRCW080510K0FKTA (10 k) - see sync-1.",
     "OFFSETADJ", "open", None),
    ("F4", "bom", 1, "R28 is 100 ohm on the schematic and CT94EW103 (10 k) in the BOM",
     "A 10 k trimmer resolves to 5.7 % of full scale on the x100 range. BOM line unchanged in the 2026-08-20 Rev 3 output.",
     "NetR21_1", "open", None),
    ("F5", "thermal", 2, "U6 HT7550-1 dissipates ~0.55-0.6 W in SOT-89",
     "Drops VregIn to 5 V for the Si8921 output side and the DC-DC module. Total board draw measured 95 mA; U6 share and junction temperature not measured. Re-examined in this review.",
     "+5", "open", None),
    ("F6", "isolation", 2, "Published common-mode figure exceeded the J2 400 V connector rating",
     "Corrected to 400 Vdc in the documentation; creepage and clearance were never checked on the layout. Re-examined in this review.",
     "GND_ISO", "closed", "docs corrected 2026-08-21; layout check is isolation-1"),
    ("F7", "tolerance", 3, "Accuracy stack-up: +/-(1.0 % + 12 mA) and +/-(0.9 % + 8 mA)",
     "Hybrid worst case; bench 2026-09-06 measured -0.24 % and -0.05 % gain error on one board.", None, "closed", "bench 2026-09-06, one board"),
    ("F8", "analog", 3, "x100 bandwidth not derivable from the schematic",
     "Measured 60 kHz on Rev 3.1. This review derives it: 50 ohm (R4||R8) with C9 47 nF switched in by Q6 gives 67.7 kHz, 63 kHz with C18 in parallel.",
     "ISENSEOUT", "closed", "bench 2026-09-06 (60 kHz); derivation in this review"),
    ("F9", "analog", 3, "C16, C17, C28 at 3 pF are below the layout parasitics", "Set nothing repeatable; raise or delete.", None, "open", None),
    ("F10", "analog", 3, "Difference-amp CMRR relies on four discrete resistors",
     "R2/R9 8.2 k 0.05 % and R3/R20 10 k 0.1 %; a matched network would remove the drift term.", None, "open", None),
    ("F11", "protection", 2, "No reverse-polarity, fuse or TVS on the 15 V input; D6 clamp topology",
     "C7 (1000 uF polymer) reverse-biased by a centre-negative adapter. D6 is an antiparallel pair across AIP/AIN (not a series pair) - see protection-1.",
     "VIN", "open", None),
    ("F12", "power", 2, "SW1 carries the whole board supply at its 100 mA / 12 V rating",
     "Confirmed from the netlist in this review: pole pin 2 fed by D3, positions 3 and 4 carry VregIn and HighGain. 95 mA measured at 15 V.",
     "VREGIN", "open", None),
    ("F13", "bom", 2, "BOM lines C8, C43, R23 are generic placeholders",
     "680 pF, 680 pF and 1 ohm on the sheet; no part number in the 2026-08-20 Rev 3 BOM.", None, "open", None),
    ("F14", "analog", 3, "Relay contact resistance sits in the x100 gain network",
     "~100 mohm in series with 156.7 ohm: 0.06 % initially, a wear-out term.", "NetR14_2", "open", None),
    ("F15", "documentation", 2, "Rev 3.1 silkscreen legends disagree with the schematic",
     "x50 fixed to x100 (2026-08-21); Vout settled at 5.70 V measured. Still open: Supply 13-16Vdc against the 12 V relay coil (15.6 V max), Max Input +/-200mV against +/-250mV on the sheet.",
     None, "open", None),
]

if __name__ == "__main__":
    reg = load(REG)
    byid = {r["id"]: r for r in reg}
    n_new = 0
    for fid, area, sev, title, detail, net, status, closed_by in LEGACY:
        if fid in byid:
            r = byid[fid]
            r.update(title=title, detail=detail, area=area, severity=sev, net=net)
            continue
        reg.append(dict(id=fid, area=area, severity=sev, title=title, detail=detail, net=net, source=SRC,
                        status=status, opened="2026-08-20", closed=("2026-09-06" if status == "closed" else None),
                        closed_by=closed_by, notes=["%s: carried into the register from DESIGN_REVIEW.md" % today()]))
        n_new += 1
    save(REG, reg)
    print("register: %d entries, %d added from the legacy review" % (len(reg), n_new))
