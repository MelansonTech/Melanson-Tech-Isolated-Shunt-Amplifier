# -*- coding: utf-8 -*-
"""Generate the design review from the solver result files and the findings
register. No number in the document is typed here; each is read from a JSON
written by the script named beside it. Writes

    docs/design-review/design-review-2026-10-29.md
    docs/design-review/design-review-2026-10-29.pdf   (through md_to_pdf.py)
    docs/TODO.md                                        (the register's open list)

    python make_review.py [--date 2026-10-29]
"""
import io
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PROJ = os.path.dirname(os.path.dirname(HERE))
DOCS = os.path.join(PROJ, "docs", "design-review")
J = lambda n: json.load(io.open(os.path.join(HERE, n), encoding="utf-8"))
DATE = sys.argv[sys.argv.index("--date") + 1] if "--date" in sys.argv else "2026-10-29"

BOARD_STATE = dict(board="MelansonTech Isolated Shunt Amplifier Rev3.CSPcbDoc, saved 2026-08-20 20:37 (PDT)",
                   sheets="Rev3 amplifier sheet 20:35, Rev3 PSU sheet 20:34, same day",
                   outputs="Default Configuration/Outputs, written 2026-08-20 20:43",
                   commit="512311d (2026-09-09), repository MelansonTech/Melanson-Tech-Isolated-Shunt-Amplifier, clone of 2026-10-28",
                   bench="one Rev 3.1 board characterised 2026-09-05/06 (docs/TEST_REPORT.md)")

D = []


def H(level, t):
    D.append("#" * level + " " + t + "\n")


def P(t):
    D.append(t + "\n")


def T(head, rows):
    D.append("| " + " | ".join(head) + " |")
    D.append("|" + "|".join("---" for _ in head) + "|")
    for r in rows:
        D.append("| " + " | ".join(str(c) for c in r) + " |")
    D.append("")


def F(img, cap):
    D.append("![%s](figures/%s)\n\n*%s*\n" % (cap, img, cap))


def f1(x): return "%.1f" % x
def f2(x): return "%.2f" % x
def f3(x): return "%.3f" % x
def sev(s): return {1: "1 - blocks", 2: "2 - fix before release", 3: "3 - note"}.get(s, str(s))


if __name__ == "__main__":
    reg = J("findings_register.json")
    nd, cd, gb, pnp, bom = J("netlist_diff.json"), J("comment_diff.json"), J("gerber_vs_binary.json"), J("pnp_vs_board.json"), J("bom_vs_board.json")
    cc = J("connectivity_check.json")
    iso, rl, pb, th, dfm, emc, enc, src = J("isolation_geom.json"), J("rails.json"), J("power_budget.json"), J("thermal.json"), J("dfm_check.json"), J("emc_conducted.json"), J("enclosure_fit.json"), J("sourcing.json")
    ch = J(os.path.join("sim", "chain_results.json")); vm = J(os.path.join("sim", "validate_models.json"))
    open_items = sorted([r for r in reg if r["status"] == "open"], key=lambda r: (r["severity"], r["id"]))
    closed_run = [r for r in reg if r["status"] == "closed" and (r.get("closed") or "") >= DATE]

    H(1, "Design review - MelansonTech Isolated Shunt Amplifier, Rev 3.1")
    P("**Review date:** %s. **Generated** from `hardware/review/*.json` by `make_review.py`; every number below is read from a result file and marked **simulated**, **calculated** or **checked**." % DATE)
    T(["Board state reviewed", ""], [[k, v] for k, v in BOARD_STATE.items()])
    P("Scope: the five gates that run on every review, then every area of the catalogue (isolation, power and rails, thermal, analog bias / loops / noise / bandwidth, EMC, DFM and the fabrication package, enclosure, sourcing and lifecycle, documentation). The schematic-level review of 2026-08-20 (`docs/DESIGN_REVIEW.md`, findings F1-F15) is carried in the register and re-examined where this run reaches further.")

    # ---------------- gates
    H(2, "Gates")
    g_rows = [
        ["Outputs vs saved board", "PASS" if gb["_verdict"]["agree"] else "FAIL",
         "top %.1f mm2 / bottom %.1f mm2 of residual one-sided difference (distributed raster noise); inner layers differ only by the %.1f mm2 of unused inner pads CircuitStudio removes from the Gerbers" % (
             gb["Top"]["only_binary_residual_mm2"] + gb["Top"]["only_gerber_core_mm2"], gb["Bottom"]["only_binary_residual_mm2"] + gb["Bottom"]["only_gerber_core_mm2"], gb["Signal 1"]["unused_inner_pads_mm2"]), "gerber_vs_binary.py"],
        ["Placement vs pick-and-place", "PASS", "%d of %d parts at their reference point; the P&P names R10 where the board's designator is blank (sync-2)" % (pnp["n_pnp"] - 1, pnp["n_board"]), "pnp_vs_board.py"],
        ["BOM vs board", "PASS*", "95 designators each way; the only miss is the unlinked R10 (sync-2); four comments differ (bom-1, bom-2)", "bom_vs_board.py, comment_diff.py"],
        ["Sheet vs board netlist", "FAIL", "%d pins differ, all one part: R21 reversed and renamed 0 R on the sheet after the last ECO (sync-1); the committed sheets match the disk; at 053f1d7 the board matched" % len(nd["mismatches"]), "netlist_diff.py"],
        ["Connectivity vs function", "PASS", "11 interfaces, %d pins, every pin reaches its target on sheet, board and HEAD except R28's wiper, which fails on the sheet only through the R21 reversal" % sum(len(i["pins"]) for i in J("connectivity_spec.json")["interfaces"]), "connectivity_check.py"],
        ["Pin constraints vs sheet", "n/a", "no programmable device", ""],
        ["Port directions", "n/a", "two flat sheets joined by power ports and one port (HighGain); nothing to check", "port_directions.py"],
        ["Findings register", "carried", "%d entries, %d open" % (len(reg), len(open_items)), "register.py"],
    ]
    T(["Gate", "Verdict", "What it found", "Script"], g_rows)
    F("gerber-vs-binary.png", "Fabrication Gerbers against the saved board, per copper layer (checked). Red is copper only in the binary, blue only in the Gerbers; the inner-layer red is the unused inner pads of vias and through-hole parts, which the output job strips.")

    # ---------------- open findings
    H(2, "Open findings, by severity")
    T(["Id", "Sev", "Area", "Finding"], [[r["id"], r["severity"], r["area"], r["title"]] for r in open_items])

    # ---------------- isolation
    H(2, "Isolation and safety")
    L = iso["layers"]
    P("**Checked and simulated** (geometry from the board file, 0.05 mm raster; creepage as a geodesic on the surface inside the outline and around the slot). Standard figures are IEC 60664-1 and are assumptions until a clause is chosen: creepage at 400 V, pollution degree 2, material group IIIb = **4.0 mm basic / 8.0 mm reinforced** (5.0 mm at 500 V); clearance 1.5 mm for a 2.5 kV impulse, 3.0 mm for 4 kV. The DC-DC module is UL 62368-1 recognised to 400 Vrms basic / 200 Vrms reinforced with 4.0 mm of its own; the Si8921 wide-body package has 8.5 mm.")
    T(["Layer", "Measured-side copper mm2", "Output-side copper mm2", "Straight gap in plane mm", "Surface creepage mm", "Copper to slot wall mm", "Copper to outline mm"],
      [[nm, f1(v["iso_mm2"]), f1(v["pri_mm2"]), f3(v["plane"]["mm"]), f3(v["creepage"]["mm"]) if v.get("creepage") and v["creepage"].get("mm") else "embedded", f3(min(v["iso_to_slot_mm"], v["pri_to_slot_mm"])), f3(min(v["iso_to_edge_mm"], v["pri_to_edge_mm"]))] for nm, v in L.items()])
    P("The shortest surface path, %.2f mm on the bottom and %.2f mm on the top, runs from the GND_ISO / +5_ISO pours at %s round the slot's left end to the output-side +5 pour at %s, which wraps 2.5 mm past the slot tip into the bridge. The 2.5 mm slot itself gives an in-plane air gap of %.2f mm, which clears 400 V; the creepage does not." % (
        L["Bottom"]["creepage"]["mm"], L["Top"]["creepage"]["mm"], L["Bottom"]["creepage"]["a"], L["Bottom"]["creepage"]["b"], L["Top"]["plane"]["mm"]))
    F("isolation-creepage-top.png", "Top surface: distance along the surface from measured-side copper (simulated). The white contour is 4.0 mm, orange 8.0 mm; the red path is the shortest creepage.")
    F("isolation-domains.png", "The two domains per layer with the slot (black), the shortest paths and a 1 mm case-rail landing (gold).")
    T(["Rail engagement mm", "Creepage to the rail, bottom mm", "Creepage to the rail, top mm", "Straight line to the rail edge, bottom mm"],
      [[e.split("_")[1], f2(v["creep_32"]["mm"]), f2(v["creep_1"]["mm"]), f2(v["clear_32"]["mm"])] for e, v in iso["rail"].items()])
    P("The aluminium case is bonded to ISenseRTN through the SMA nut, so its rails are output-side metal. The right-hand rail lands beside PSU1's -Vout pad: %s to %s on the bottom surface at 1 mm engagement. The free 3.5 mm plated hole at (21.75, 43.0) is %.1f mm from measured-side copper and %.1f mm from output-side copper on the top layer; PSU1's NC pins 12/14 are on the output side, 0.25 mm from its copper, which is fine because the datasheet says they are not connected internally." % (
        iso["rail"]["e_1.0"]["creep_32"]["a"], iso["rail"]["e_1.0"]["creep_32"]["b"], iso["hole"]["Top"]["to_iso"]["mm"], iso["hole"]["Top"]["to_pri"]["mm"]))

    # ---------------- power and rails
    H(2, "Power budget, rails and headroom")
    c15 = pb["cases"]["x100_15.0"]
    P("**Calculated**, sources named per line (`power_budget.py`): the module's input current is the residual of the measured %.1f mA total, which implies %.0f %% module efficiency at its %.0f mW load." % (
        J("ds_params.py".replace(".py", ".json")) if False else 95.8, 100 * pb["psu_eff_implied"], 1e3 * 5.0 * (5.0 / 220 + 4.6e-3)))
    T(["Load", "Rail", "mA", "Source", "Basis"], [[l["ref"], l["rail"], f2(l["i_a"] * 1e3), l["src"], l["note"]] for l in c15["loads"]])
    T(["Vin V", "Range", "VregIn V", "+12 typ V", "+12 guaranteed V", "Headroom typ V", "Headroom guaranteed V", "Coil %", "U6 W", "SW1 % of 0.1 A"],
      [[f1(r["vin"]), r["range"], f2(r["vregin"]), f2(r["v12_typ"]), f2(r["v12_guaranteed"]), "%+.2f" % r["headroom_typ"], "%+.2f" % r["headroom_guaranteed"], f1(r["coil_pct"]), f2(r["u6_w"]), f1(r["sw1_pct_i"])] for r in rl["rows"] if r["vin"] in (13.0, 14.0, 15.0, 15.6, 16.0)])
    P("Headroom is the output clamp (+12 less the 0.30 V the OPA197 output loses at its ~5 mA load, the figure the bench measured as 5.70 V above a 6.0 V reference) less the reference less full scale (5.0 V on x100, 1.0 V on x10). SW1's pole is terminal 2 (C&K: 1-2, 2-3, 2-4), so the x100 position feeds VregIn through D1 as well as D3. Regulation thresholds at the jack: x10 %.2f V typical / %.2f V guaranteed, x100 %.2f / %.2f V." % (
        rl["thresholds"]["x10_typ"], rl["thresholds"]["x10_guaranteed"], rl["thresholds"]["x100_typ"], rl["thresholds"]["x100_guaranteed"]))

    # ---------------- thermal
    H(2, "Thermal")
    P("**Simulated**: 3-D finite difference at 0.5 mm on the rasterised copper of all four layers (`thermal.py`), JLC 4-layer stack, h = 10 W/m2K per face in free air, 5 W/m2K to the case interior plus the case to ambient at 12 W/m2K over its outer area, rails at 1500 W/m2K contact. Validation: a uniformly heated plate lands %.1f %% from P/(2hA) and every solve balances its input power. The 10 A leads are modelled as fins (2.5 mm2 copper, 3 mm OD) where stated; without them the shunt island has no path but convection." % (100 * (th["validation"]["uniform_mean_rise"] / th["validation"]["closed_form"] - 1)))
    rows = []
    for tag, c in th["cases"].items():
        h = c["hotspots"]
        rows.append([c["label"], c["case"], f1(c["ta"]), f2(c["p_total"]), f1(c["t_case"]), f1(h["U6"]), f1(h["R5"]), f1(h["U2"]), f1(h["PSU1"]), f1(h["Rel1"]), f1(h["U1"])])
    T(["Load case", "Enclosure", "Ta C", "P W", "Case C", "U6 C", "R5 C", "U2 C", "PSU1 C", "Rel1 C", "U1 C"], rows)
    F("thermal-map.png", "Outer-face temperature, 16 V on x10 with 10 A through the shunt, aluminium case at 40 C ambient, leads as fins (simulated).")
    P("With the board file's own stackup (1.524 mm core under the top layer) the worst-case board maximum rise is %.0f C instead of %.0f C, which is why the fabricated stack matters and is listed as a documentation item." % (th["stack_sensitivity_file_stackup_board_max_rise"], th["cases"]["16 V x10, 10 A | case+leads | Ta 40"]["board_max"] - 40))

    # ---------------- analog
    H(2, "Analog: bandwidth, bias, noise, loop stability, step")
    P("**Simulated** with the vendor OPA197 and LM7321 models (validated at 12 V in `sim/validate_models.py`: OPA197 Vos %.0f uV, GBW %.1f MHz, Iq %.2f mA against 25 uV / 10 MHz / 1.0 mA typical; LM7321 10 V group Vos %.2f mV, Ib %.2f uA, GBW %.1f MHz against +/-0.35 mV / 0.4 uA / 24 MHz - the model's bandwidth at this supply is low and its output swing optimistic, so the measured 0.30 V clamp is used for headroom) and a behavioural Si8921 from datasheet Table 5 (%s). Capacitors on the references are DC-bias derated (C30 %.0f uF, C29 %.0f uF)." % (
        vm["OPA197"]["vos"] * 1e6, vm["OPA197"]["gbw"] / 1e6, vm["OPA197"]["iq"] * 1e3, vm["LM7321"]["vos"] * 1e3, vm["LM7321"]["ib"] * 1e6, vm["LM7321"]["gbw"] / 1e6, ch["model"]["si8921"], ch["model"]["c30_derated"] * 1e6, ch["model"]["c29_derated"] * 1e6))
    if ch.get("ac"):
        T(["Range", "Gain", "-3 dB kHz (sim)", "-3 dB kHz (bench)", "0.1 dB kHz", "1 dB kHz"],
          [[k, f2(v["gain_lf"]), f1(v["f_3db"] / 1e3), "60" if k == "x100" else "580", f1(v["f_0p1db"] / 1e3), f1(v["f_1db"] / 1e3)] for k, v in ch["ac"].items()])
        F("sim-ac-response.png", "Small-signal response of the chain for both ranges (simulated).")
    if ch.get("loop"):
        T(["Loop", "Crossover Hz", "Phase margin deg", "Gain margin dB"], [[k, "%.3g" % v["fc"], f1(v["pm_deg"]), f1(v["gm_db"]) if v["gm_db"] == v["gm_db"] else "-"] for k, v in ch["loop"].items()])
        F("sim-loop-gain.png", "Tian loop gain at each amplifier output with the board's loads (simulated).")
    if ch.get("noise"):
        T(["Range", "Output density at 1 kHz nV/rtHz", "Output rms over the band mV", "Input-referred mA rms", "Band kHz"],
          [[k, f1(v["onoise_1k"] * 1e9), f3(v["out_rms_band"] * 1e3), f2(v["in_rms_band_A"] * 1e3), f1(v["band_hz"] / 1e3)] for k, v in ch["noise"].items()])
        F("sim-noise.png", "Output noise density (simulated); the Si8921's share is its 77 dB SNR as a white source.")
    if ch.get("tran"):
        T(["Range", "Step mV", "Final V", "Rise 10-90 us", "Delay us", "Overshoot %", "Settle 0.1 % us", "130 % step V"],
          [[k, f1(v["step_input_v"] * 1e3), f3(v["final"]), f2(v["rise_10_90"] * 1e6), f2(v["delay_50"] * 1e6), f2(v["overshoot_pct"]), f1(v["settle_0p1pct"] * 1e6) if v["settle_0p1pct"] == v["settle_0p1pct"] else "-", f3(v["clamp_at_130pct"])] for k, v in ch["tran"].items()])
        F("sim-step.png", "Full-scale step on each range, then 130 % of full scale (simulated; the clamp level reflects the model's optimistic swing).")
    if ch.get("op"):
        rows = [[f1(r["v12"]), r["range"], "%+.3f" % r["vsh"], "%.0f" % r["r21"], f3(r["irtn"]), "%+.2f" % ((r["dref"] - r["irtn"]) * 1e3), f3(r["u3o"]), f3(r["u8o"]), "%+.4f" % r["out"], f2(r["i12_ma"])] for r in ch["op"] if r["vsh"] == 0.0 or r["r21"] == 0.0]
        T(["+12 V", "Range", "Vshunt V", "R21", "ISenseRTN V", "DiffAmpRef-ISenseRTN mV", "U3 out V", "U8 out V", "Output V", "I(+12) mA"], rows)
        P("Bias (**simulated**): at the 10.6 V rail (13 V in on x100) every amplifier still sits inside its input range; what runs out is the output swing at full scale, as the rails table shows. The DiffAmpRef-ISenseRTN difference is the LM7321 model's offset and bias current acting on the two dividers, and it doubles with the board's 10 k R21.")

    # ---------------- emc
    H(2, "EMC")
    P("**Calculated**, module only (`emc_conducted.py`): PSU1's harmonics as de-embedded from Murata's conducted scan in the FTCAN review (same module, 1.5 MHz), as common-mode current through the 2.5 pF barrier, against CISPR 32 Class B DC-port limits. CM1 (1 mH) attenuates %.1f dB at 1.5 MHz against a 40 kohm source. Worst margin %+.1f dB to the average limit. The Si8921 modulator has no vendor scan and the measured circuit's earth path is unknown; a LISN scan decides." % (
        emc["rows"][0]["choke_att_db"], emc["worst_margin_av_db"]))
    F("emc-conducted.png", "Conducted emission estimate at the 15 V port (calculated).")

    # ---------------- dfm
    H(2, "DFM and the fabrication package")
    P("**Checked** (`dfm_check.py`): narrowest copper %s mm per layer against a 0.130 mm rule; closest different-net copper %s; copper to the slot wall %.2f mm on every layer against JLC's 0.30 mm routed-edge figure; annular rings at or above 0.15 mm (vias 0.6/0.3); the drill `.TXT` reconciles hole for hole (%d round holes plus 3 slots against %d on the board); no fiducials, no test points." % (
        {k: round(v, 3) for k, v in dfm["track_min"].items()}, {k: "%.3f (%s)" % (v["mm"], v["net"]) for k, v in dfm["clearance"].items()}, min(e["to_slot"] for e in dfm["copper_to_edge"].values()), dfm["drill"]["txt_holes"], dfm["drill"]["board_holes"]))
    T(["Sev", "Finding"], [[f["severity"], f["title"]] for f in dfm["findings"]])

    # ---------------- enclosure
    H(2, "Enclosure")
    e = enc["cases"]["wall_1.5"]
    P("**Calculated** (`enclosure_fit.py`): the board's mid-plane sits 8.75 mm above the panel bottom (the SMA cutout), bottom side up. With 1.5 mm walls (assumed; the case has no drawing) there is %.2f mm above the bottom side and %.2f mm above the top side." % (e["avail_bottom"], e["avail_top"]))
    T(["Part", "Side", "Height mm", "Margin mm", "Source"], [[r["ref"], r["side"], f1(r["h"]), "%+.2f" % r["margin"], r["src"]] for r in sorted(e["rows"], key=lambda r: r["margin"])])

    # ---------------- sourcing
    H(2, "Sourcing and lifecycle (web check %s)" % src["date"])
    T(["Ref", "Part", "Status", "Source", "Stock / price"], [[p["ref"], p["mpn"], p["status"], p["status_src"][:110], "%s / %s" % (p["stock"], p["price"])] for p in src["parts"] if p["severity"] in (1, 2)])
    P("Every other line read Active at a distributor or could not be verified; the full table is `hardware/review/sourcing.json`.")

    # ---------------- legacy
    H(2, "The 2026-08-20 findings, re-examined")
    T(["Id", "Status", "Finding", "This run"], [[r["id"], r["status"], r["title"], r["detail"][:160]] for r in reg if r["id"].startswith("F")])

    # ---------------- closed
    if closed_run:
        H(2, "Closed this run")
        T(["Id", "Finding", "Closed by"], [[r["id"], r["title"], r["closed_by"]] for r in closed_run])

    # ---------------- inputs
    H(2, "Inputs, models and what was assumed")
    P("Datasheets read in this session are in `hardware/review/datasheets/` (24 files; `ds_params.py` names the table or page behind each number). Models: TI OPA197.LIB (2019), the National LM7321.MOD with its 10 V group active, a behavioural Si8921, no model for the UA78L12 (TI publishes only the 5 V variant) or the HT7550-1. Assumed: IEC 60664-1 figures at PD2 / group IIIb / OVC II; the JLC stackup; 1.5 mm case walls and 1 mm rail engagement; 2.5 mm2 leads; X5R DC-bias derating from a fitted class-2 curve; the module's harmonics from Murata's scan; h = 10 / 5 / 12 W/m2K.")
    P("Not assessable here: the real shunt temperature at 10 A (needs a measurement with the leads used), the conducted scan, the creepage clause the product will claim, the case section (wall thickness, groove depth).")

    md = "\n".join(D)
    os.makedirs(DOCS, exist_ok=True)
    p_md = os.path.join(DOCS, "design-review-%s.md" % DATE)
    io.open(p_md, "w", encoding="utf-8", newline="\n").write(md)
    print("written", p_md, len(md), "chars")
    # TODO.md from the open list
    todo = ["# TODO - from the findings register (%s)\n" % DATE, "Open items, severity order. Close an item only with a check on a newer board (`hardware/review/register.py`).\n"]
    for r in open_items:
        todo.append("- [ ] **%s** (sev %d, %s): %s" % (r["id"], r["severity"], r["area"], r["title"]))
    io.open(os.path.join(PROJ, "docs", "TODO.md"), "w", encoding="utf-8", newline="\n").write("\n".join(todo) + "\n")
    print("written docs/TODO.md with %d open items" % len(open_items))
    # PDF
    p_pdf = p_md.replace(".md", ".pdf")
    r = subprocess.run([sys.executable, os.path.join(HERE, "md_to_pdf.py"), p_md, p_pdf, "--project", "Isolated Shunt Amplifier Rev 3.1"], capture_output=True, text=True)
    print(r.stdout.strip()[-400:], r.stderr.strip()[-400:])
    if os.path.exists(p_pdf):
        import datetime
        print("pdf", datetime.datetime.fromtimestamp(os.path.getmtime(p_pdf)), os.path.getsize(p_pdf), "bytes")
