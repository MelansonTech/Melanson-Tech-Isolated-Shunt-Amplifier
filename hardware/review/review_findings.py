# -*- coding: utf-8 -*-
"""Assemble this run's findings from every solver's JSON and carry them into
the findings register under stable ids, then add the read findings (sheet,
datasheet and documentation items) that no solver emits.

Severity: 1 blocks build or operation, 2 fix before release, 3 note.

    python review_findings.py [--run LABEL]
"""
import io
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REG = os.path.join(HERE, "findings_register.json")
J = lambda n: json.load(io.open(os.path.join(HERE, n), encoding="utf-8"))


def carry(area, source, items):
    p = os.path.join(HERE, "_carry_%s.json" % area)
    io.open(p, "w", encoding="utf-8", newline="\n").write(json.dumps(items, indent=1))
    r = subprocess.run([sys.executable, os.path.join(HERE, "register.py"), REG, "carry", p, "--area", area, "--source", source, "--run", RUN],
                       capture_output=True, text=True)
    print(r.stdout.strip() or r.stderr.strip())


if __name__ == "__main__":
    RUN = sys.argv[sys.argv.index("--run") + 1] if "--run" in sys.argv else "2026-10-29"
    # ---- gates
    nd = J("netlist_diff.json")
    items = []
    if nd.get("mismatches"):
        pins = sorted({m["pin"].split(".")[0] for m in nd["mismatches"]})
        items.append(dict(finding="Sheet and board differ: R21 is fitted the other way round and renamed on the sheet (0 ohm link) after the last ECO",
                          detail="pins %s; board carries CRCW080510K0FKTA (10 k), sheets and BOM carry CR0805-J/-000ELF (0 R). Electrically symmetric, but the board has not been synchronised since the 2026-08-20 sheet edit" % ", ".join(pins), severity=2, net="OFFSETADJ"))
    if nd.get("sheet_only_components"):
        items.append(dict(finding="R10 exists on the sheets but the board's R10 footprint is not linked to it",
                          detail="the board component at (29.10, 69.80) has no SOURCEDESIGNATOR / unique id (a free part whose silkscreen text says R10); the next Update PCB adds a second R10. Nets NetR10_1 / NetR7_1 are correct", severity=2, net="NetR10_1"))
    carry("sync", "netlist_diff.py, comment_diff.py", items)
    cd = J("comment_diff.json")
    items = []
    for d in cd["diffs"]:
        if d["designator"] == "R21":
            continue
        items.append(dict(finding="%s: sheet/BOM says %s, board says %s" % (d["designator"], d["sheet_comment"], d["board_comment"]),
                          detail="the BOM orders the sheet's part; the board's comment is what an assembler reading the P&P sees. %s" % (
                              "D6: the board's BAT54S (Schottky) conducts 2 uA at 100 mV and ~0.3 mA at 250 mV through the 20 ohm sense resistors; the sheet's BAS31 (silicon) does not - the silicon part must be the one fitted" if d["designator"] == "D6" else
                              "R2/R9: RR1220P-8251-D-M is 8.25 k 0.5 %, the sheet's ERA-6VRW8201V is 8.2 k 0.05 %; the difference amplifier ratio moves 0.6 % between them"),
                          severity=2, net=None))
    carry("bom", "comment_diff.py", items)
    gb = J("gerber_vs_binary.json")
    items = []
    if not gb["_verdict"]["agree"]:
        items.append(dict(finding="Gerbers and saved board disagree", detail=str(gb["_verdict"]), severity=1))
    carry("outputs", "gerber_vs_binary.py, pnp_vs_board.py, bom_vs_board.py", items)
    # ---- isolation
    iso = J("isolation_geom.json")
    cr_top = iso["layers"]["Top"]["creepage"]["mm"]; cr_bot = iso["layers"]["Bottom"]["creepage"]["mm"]
    req = iso["requirements"]
    items = [dict(finding="Barrier creepage %.2f mm (bottom) / %.2f mm (top) around the slot's left end, below the 4.0 mm basic figure for 400 V" % (cr_bot, cr_top),
                  detail="shortest surface path from the GND_ISO / +5_ISO pours at (25.3-25.6, 43.9) round the slot tip to the +5 pour that wraps into the bridge at (23.7, 46.5). IEC 60664-1 table F.5, PD2, material group IIIb: 4.0 mm basic / 8.0 mm reinforced at 400 V (5.0 mm at 500 V); the DC-DC module's own creepage is 4.0 mm. Supported working voltage at %.2f mm is about 340 V basic" % cr_bot,
                  severity=2, net="+5")]
    rail = iso["rail"]["e_1.0"]
    items.append(dict(finding="Aluminium case rail (bonded to ISenseRTN) is %.2f mm from PSU1's -Vout pad along the bottom surface at 1 mm groove engagement" % rail["creep_32"]["mm"],
                      detail="the right-hand rail lands next to the isolated secondary at the slot's right end; %.1f mm at 0.5 mm engagement, %.1f mm at 2.0 mm. Anodising is a film, not rated insulation (trap 1). Engagement depth is on no drawing" % (
                          iso["rail"]["e_0.5"]["creep_32"]["mm"], iso["rail"]["e_2.0"]["creep_32"]["mm"]), severity=2, net="GND_ISO"))
    items.append(dict(finding="Free 3.5 mm plated hole at (21.75, 43.0) sits 2.1 mm from measured-side copper and 1.8 mm from output-side copper",
                      detail="no net, no component; a metal fastener in it bridges the barrier at 2.1 mm. Its purpose is not recorded", severity=2, net=None))
    items.append(dict(finding="Pours on every layer come within 0.21 mm of the slot wall",
                      detail="GND (inner planes), +5, +12 and GND_ISO / +5_ISO all stop 0.21-0.22 mm from the routed slot; routing tolerance is of that order, so inner copper can be exposed in the slot. The clearance across the 2.5 mm slot itself is adequate", severity=2, net="GND"))
    items.append(dict(finding="No design rule enforces the barrier",
                      detail="the exported rule set has one 0.200 mm clearance rule scoped to the whole board; a clearance rule between a measured-side net class and everything else at 4.0 mm (and 0.5 mm pour-to-cutout) would have caught both findings above", severity=2, net=None))
    items.append(dict(finding="J2's 400 V rating applies to overvoltage category II / pollution degree 2 only",
                      detail="5442002 catalog: 400 V (II/2), 320 V (III/2), 250 V (III/3), 4 kV surge, material group I. SAFETY.md quotes 400 V without the category", severity=3, net=None))
    carry("isolation", "isolation_geom.py", items)
    # ---- power / rails
    rl = J("rails.json")
    r13 = next(r for r in rl["rows"] if r["vin"] == 13.0 and r["range"] == "x100")
    items = [dict(finding="x100 full scale (5.0 V) is at the output clamp at 13 V in: two Schottky drops plus the regulator dropout",
                  detail="headroom %+.2f V typical, %+.2f V at the guaranteed 14.5 V regulator input; full scale is reachable above 13.05 V (typ) / 13.85 V (guaranteed). Regulation thresholds at the jack: x10 %.2f / %.2f V, x100 %.2f / %.2f V (typ / guaranteed)" % (
                      r13["headroom_typ"], r13["headroom_guaranteed"], rl["thresholds"]["x10_typ"], rl["thresholds"]["x10_guaranteed"], rl["thresholds"]["x100_typ"], rl["thresholds"]["x100_guaranteed"]),
                  severity=2, net="+12")]
    pb = J("power_budget.json")
    u6 = pb["cases"]["x10_16.0"]["diss_w"]["U6"]; u6_15 = pb["cases"]["x100_15.0"]["diss_w"]["U6"]
    th = J("thermal.json")
    hot = th["cases"]["16 V x10, 10 A | case+leads | Ta 40"]["hotspots"]
    hot25 = th["cases"]["16 V x10, 10 A | open+leads | Ta 25"]["hotspots"]
    items.append(dict(finding="U6 (HT7550-1, SOT-89) dissipates %.2f W at 15 V and %.2f W at 16 V against a 0.5 W package rating" % (u6_15, u6),
                      detail="63 mA of module input (the measured 95.8 mA total less everything else, implying 43 %% module efficiency at 14 %% load) plus 3.5 mA for the Si8921 from VregIn 14.3-15.6 V. Simulated hotspot %.0f C in free air at 25 C, %.0f C in the case at 40 C (operating range of the part is 85 C ambient, 150 C junction)" % (hot25["U6"], hot["U6"]),
                      severity=2, net="+5"))
    items.append(dict(finding="SW1 carries 93-97 % of its 0.1 A rating at 15 V (rated 12 V) and makes/breaks the board supply",
                      detail="pole terminal 2 confirmed from the C&K table (1-2, 2-3, 2-4); 10,000-cycle life; switching into C3 (22 uF) from the 1176 uF input bank", severity=2, net="VREGIN"))
    items.append(dict(finding="Relay coil at 16 V is 130 % of rating, within the G6L's 150 % maximum to 70 C",
                      detail="corrects finding 15: the 13-16 V silkscreen is not what limits the input; U6 dissipation is (0.71 W at 16 V)", severity=3, net="HIGHGAIN"))
    carry("power", "rails.py, power_budget.py", items)
    # ---- thermal
    items = [dict(finding="The slot makes the shunt area a thermal island: R5 at 10 A reaches %.0f C in free air and %.0f C in the case at 40 C with 2.5 mm2 leads as fins" % (hot25["R5"], hot["R5"]),
                  detail="without the leads the model gives %.0f-%.0f C, so the shunt is cooled by its wiring. At +85 C the shunt's 50 ppm/C is a 0.4 %% gain term on the 10 A range (the budget assumed a 33 C rise); the Si8921 input side sits at %.0f-%.0f C. Measure the shunt at 10 A with the real leads, or derate the continuous current on the x10 range" % (
                      th["cases"]["16 V x10, 10 A | open | Ta 25"]["hotspots"]["R5"], th["cases"]["16 V x10, 10 A | case | Ta 40"]["hotspots"]["R5"], hot25["U2"], hot["U2"]),
                  severity=2, net="NetJ2_1")]
    dfm = J("dfm_check.json")
    items.append(dict(finding="J2-to-shunt pours rise ~%.0f C at 10 A (IPC-2221, 1 oz, top layer only)" % dfm["shunt_path"]["ipc2221_rise_c"],
                      detail="%.2f mm wide; a second copper layer or 2 oz halves it" % dfm["shunt_path"]["pour_width_mm"], severity=3, net="NetJ2_1"))
    carry("thermal", "thermal.py, dfm_check.py", items)
    # ---- analog (from the chain simulation)
    ch = J(os.path.join("sim", "chain_results.json"))
    items = []
    for key, v in ch.get("loop", {}).items():
        if v["pm_deg"] < 45 or (v["gm_db"] == v["gm_db"] and v["gm_db"] < 10):
            lm = key.startswith(("U5", "U9"))
            items.append(dict(finding="%s loop: phase margin %.0f deg%s (simulated%s)" % (key, v["pm_deg"], (", gain margin %.0f dB" % v["gm_db"]) if v["gm_db"] == v["gm_db"] else "", ", LM7321 model at its 10 V group" if lm else ""),
                              detail="Tian probe at the amplifier output with the board's loads (%.0f uF derated on the references); crossover %.3g Hz. %s" % (
                                  ch["model"]["c10"] * 1e6, v["fc"], "The LM7321 is specified for unlimited capacitive load and the bench board shows no instability, so this is a question about the model's output stage, not a fault found: confirm with a step on DiffAmpRef" if lm else "below the 45 deg pass line"),
                              severity=3 if lm else 2, net=None))
    op = ch.get("op", [])
    d10 = [r for r in op if r["r21"] == 10e3 and r["vsh"] == 0.0 and r["v12"] == 12.0]
    d0 = [r for r in op if r["r21"] == 0.0 and r["vsh"] == 0.0 and r["v12"] == 12.0]
    if d10 and d0:
        dref10 = (d10[0]["dref"] - d10[0]["irtn"]) * 1e3; dref0 = (d0[0]["dref"] - d0[0]["irtn"]) * 1e3
    else:
        dref10 = dref0 = float("nan")
    ac = ch.get("ac", {})
    if ac:
        items.append(dict(finding="x100 bandwidth is set by C9 (47 nF) against the 50 ohm output resistors: simulated %.0f kHz, measured 60 kHz" % (ac["x100"]["f_3db"] / 1e3),
                          detail="C9 is switched to board GND by Q6 on the x100 range; C8 (680 pF) with R32 (1 k) adds a 234 kHz pole. x10: %.0f kHz simulated against 580 kHz measured, set by the Si8921" % (ac["x10"]["f_3db"] / 1e3), severity=3, net="ISENSEOUT"))
    nz = ch.get("noise", {})
    if nz:
        items.append(dict(finding="Input-referred noise %.1f mA rms (x100, 60 kHz) and %.1f mA rms (x10, 580 kHz), dominated by the Si8921" % (nz["x100"]["in_rms_band_A"] * 1e3, nz["x10"]["in_rms_band_A"] * 1e3),
                          detail="bench: ~2 mA rms on x100; the x10 bench figure (12 mA rms) is a 108 kHz spur, not the noise floor", severity=3, net="ISENSEOUT"))
    items.append(dict(finding="LM7321 bias current (0.4 uA typ, up to 2 uA) through the R21 asymmetry: 4 mV typ / 20 mV max offset between the two references with the board's 10 k, zero with the sheet's 0 R",
                      detail="simulated with the vendor model (Ib -1.1 uA): DiffAmpRef - ISenseRTN = %+.1f mV with 10 k, %+.2f mV with 0 R, against a +/-3 mV trim span. A 10 k R21 can put the zero out of reach on a worst-case LM7321; the sheet's 0 R (or 100 R) removes it. The datasheet figure is ten times the 50 nA the previous review assumed" % (dref10, dref0), severity=2, net="OFFSETADJ"))
    items.append(dict(finding="D6 as drawn is an antiparallel clamp across AIP/AIN (+/-0.7 V with BAS31), not a series pair",
                      detail="pins 1 and 2 on AIN, pin 3 on AIP. The Si8921 absolute maximum is -0.5 V / VDDA + 0.5 V, so the clamp protects; with the board's BAT54S it also leaks 0.3 mA at the 250 mV input maximum (2.4 %% of full scale through the 20 ohm) - see bom-2", severity=3, net="NetC41_1"))
    carry("analog", "sim/chain.py, ds_params.py", items)
    # ---- dfm and fabrication package
    items = [dict(finding=f["title"], detail=f.get("detail", ""), severity=f["severity"], net=f.get("net")) for f in dfm["findings"] if f["area"] in ("dfm", "fab-package")]
    carry("dfm", "dfm_check.py", items)
    # ---- emc
    emc = J("emc_conducted.json")
    items = [dict(finding="Conducted emission at the 15 V port from PSU1: worst margin %+.1f dB to CISPR 32 Class B AVG (10-30 MHz), module scan de-embedded" % emc["worst_margin_av_db"],
                  detail="common-mode current through the 2.5 pF barrier, CM1 buys ~1 dB against a 40 kohm source; the Si8921 modulator and the real earth path of the measured circuit are not in the estimate. A LISN scan settles it", severity=2, net="VIN")]
    carry("emc", "emc_conducted.py", items)
    # ---- sourcing
    src = J("sourcing.json")
    items = []
    for p in src["parts"]:
        if p["severity"] in (1, 2):
            items.append(dict(finding="%s (%s): %s" % (p["mpn"], p["ref"], p["status"]), detail="%s. %s" % (p["status_src"], p["note"]), severity=p["severity"], net=None))
    items.append(dict(finding="Part numbers that no distributor listing matched: NXJ1S0505T6MC-R7, ERA-6VRW8201V, ERA-6AEB471V, C0805X102J1GACAUTO",
                      detail="the BOM carries Digi-Key numbers for the first three; C0805X102J1GACAUTO looks like C0805C102J1GACAUTO. Verify at order time", severity=3, net=None))
    carry("sourcing", "sourcing.json (web check 2026-10-29)", items)
    # ---- documentation
    items = [dict(finding="Documents give the board as 68.25 x 85.00 mm; it is 50.00 x 50.00 mm", detail="CONNECTORS.md and ASSEMBLY.md read the outline's maximum coordinate as a size; ASSEMBLY.md's enclosure section has the right 50 x 50", severity=3),
             dict(finding="README says Revision 3 'has not been fabricated or tested' while the test report characterises a Rev 3.1 board", detail="the repository-layout paragraph is stale since 2026-09-06", severity=3),
             dict(finding="The board file's stackup is not a fabricated one: 1.524 mm between top and the first plane, then 0.254 / 0.254", detail="JLC's 4-layer 1.6 mm stack is 0.21 / 1.065 / 0.21; thermal and plane-coupling results use the JLC stack and say so", severity=3),
             dict(finding="C7 is a 10 x 16 mm can (A750 MV); upright it cannot fit the 24 mm case, lying flat it clears by ~3 mm with 1.5 mm walls", detail="the footprint name (RA1, 14 mm high) implies a right-angle mount; the case wall thickness is on no drawing", severity=3),
             dict(finding="Rev 1 Bode files and the sheet note 'Circuit Requires 300mW' are stale", detail="measured 1.4 W; the sheet note is where the README's 300 mW came from", severity=3)]
    carry("documentation", "review 2026-10-29", items)
    # ---- the register's open list
    r = subprocess.run([sys.executable, os.path.join(HERE, "register.py"), REG, "list", "--open"], capture_output=True, text=True)
    print(r.stdout)
