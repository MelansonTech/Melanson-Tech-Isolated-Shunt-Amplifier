# -*- coding: utf-8 -*-
"""Datasheet numbers used by the review, each with its source. Nothing here
is typed from memory: every value was read from the PDF in ./datasheets in
this session (file, table or page). Estimates are marked EST with their basis.

    import ds_params as DS
    DS.P["si8921"]["gain"]
"""
P = {
    "si8921": dict(src="si8921.pdf, Table 5 (rev E, June 2026), Table 4, pp. 8-9, 25-28",
                   vdd_min=3.0, vdd_max=5.5, idda_typ=4.6e-3, idda_max=6.0e-3, iddb_typ=3.5e-3, iddb_max=4.5e-3,
                   bw_hz=600e3, gain=8.2, gain_err_max=0.002, gain_err_typ=0.0006, gain_drift_ppm=(-24, -9),
                   vin_fs=0.250, vos_max=0.15e-3, vos_drift_max=3e-6, nonlin_max=0.0002, nonlin_drift_ppm=16,
                   snr_db=77.0, snr_bw_hz=100e3, thd_db=-82.0, tpd_typ=0.8e-6, tpd_max=1.0e-6,
                   vocm_min=1.34, vocm_typ=1.39, vocm_max=1.49, vout_fs_diff=2.05,
                   rload_min=5e3, cload_max=100e-12, cmti_min=50e9,
                   abs_in_min=-0.5, abs_in_max_above_vdda=0.5, rin_max_ohm=33.0,
                   viorm_vpk=2121, v62368_reinf_vrms=600, v62368_basic_vrms=1000, creepage_mm=8.5, clearance_mm=8.5,
                   pins={1: "VDDA", 2: "AIP", 3: "AIN", 4: "GNDA", 5: "GNDB", 6: "AON", 7: "AOP", 8: "VDDB"}),
    "lm7321": dict(src="lm7321.pdf SNOSAW8F (Jul 2026), 5.5 Electrical Characteristics",
                   vos_typ=0.35e-3, vos_max=5e-3, tcvos_typ=2.5e-6, ib_typ=0.4e-6, ib_min=-2e-6, ib_max=1e-6,
                   ib_min_temp=-2.5e-6, ib_max_temp=1.5e-6, ios_typ=7e-9, ios_max=200e-9,
                   is_typ=1.35e-3, is_max=1.93e-3, gbw_hz=24e6, sr=35e6, en=12e-9, inoise=1e-12,
                   swing_mv_10k=(50, 150), swing_mv_2k=(250, 280), iout_min=40e-3, iout_typ=125e-3,
                   avol_db_min=75, psrr_db_min=78, cmvr=("V- -0.1", "V+ +0.1"), cload="unlimited",
                   model="LM7321.MOD (National, 30 V group as published; 10 V group used for the 12 V supply, see models/LM7321_12V.lib)"),
    "opa197": dict(src="opa197.pdf SBOS737, Electrical Characteristics VS = 8 V to 36 V",
                   vos_typ=25e-6, vos_max=100e-6, tcvos_max=2.5e-6, ib_typ=5e-12, en_1k=5.5e-9, en_pp=1.3e-6,
                   gbw_hz=10e6, sr=20e6, swing_mv_noload=(5, 25), swing_mv_10k=(95, 125), swing_mv_2k=(430, 500),
                   isc=65e-3, iq_typ=1.0e-3, iq_max=1.3e-3, cload_max=1e-9, vs_min=4.5, vs_max=36,
                   model="OPA197.LIB (TI, 30JAN2019, Green-Williams-Lis macro-model)"),
    "ua78l12": dict(src="ua78l12.pdf SLVS010X (Jun 2023), 6.3, 6.4, 6.8 and 7.3.3",
                    vo_min=11.5, vo_max=12.5, vi_min_rec=14.5, vi_max_rec=27, vi_absmax=35, io_max=100e-3,
                    vdo_typ=1.7, vdo_io=40e-3, ibias_typ=3.84e-3, ibias_max=4.35e-3, ibias_max_legacy=6e-3,
                    rtheta_ja_pk=54.7, rtheta_jb_pk=9.6, pins={1: "OUTPUT", 2: "COMMON", 3: "INPUT"}),
    "ht7550_1": dict(src="ht7550-1.pdf (Holtek V2.81, Dec 2025), Thermal Information p.4, HT7550-1 table p.8",
                     vout_min=4.85, vout_max=5.15, vin_max=30, io_rated=100e-3, iss_typ=2.5e-6, iss_max=4e-6,
                     load_reg_mv=(25, 60), line_reg_mv=(25, 55), tc_ppm=100,
                     vdo="see rails.py: dropout column read from the table image",
                     rtheta_ja=200.0, pd_max_w=0.5, tj_max=150, ta_max=85, pins={1: "GND", 2: "VIN", 3: "VOUT"}),
    "g6l": dict(src="g6l.pdf (Omron G6L), Coil Ratings and Engineering Data p.3",
                coil_v=12.0, coil_ohm=800.0, coil_tol=0.10, coil_ma=15.0, coil_mw=180, pickup_pct=75, dropout_pct=10,
                vmax_pct=150, vmax_pct_to_degC=70, contact_a=1.0, contact_vdc_max=60, contact_r_mohm_max=100,
                note="maximum coil voltage 150 % of rated, flat to 70 C ambient (Ambient Temperature vs Maximum Voltage, 3 to 12 VDC curve)"),
    "wsl3637": dict(src="wsl3637.pdf (Vishay 30099, Dec 2023)", r=0.010, tol=0.005, p70_w=3.0, tcr_ppm=50, el_tcr_ppm=20,
                    l_nh=(0.5, 5.0), emf_uv_per_c=3.0, tmax=170, derate="100 % to 70 C, linear to 0 at 170 C (DERATING curve)",
                    kelvin="E1 sense tab at the I1 end, E2 at the I2 end (4 TERMINAL KELVIN CONNECTIONS figure)"),
    "os103011": dict(src="os103011.pdf (C&K OS series)", rating_a=0.1, rating_vdc=12, contact_mohm=20, life_cycles=10000,
                     pole_terminal=2, positions="1-2, 2-3, 2-4"),
    "pj002a": dict(src="pj-002a.pdf (Same Sky, Mar 2025)", rated_a=2.5, pins={1: "centre pin", 2: "sleeve", 3: "switch, closed to 2 unplugged"}),
    "5442002": dict(src="5442002.pdf (Phoenix Contact catalog, BCH-508HS-2)", rated_v={"III/3": 250, "III/2": 320, "II/2": 400},
                    surge_kv=4, rated_a=12, material_group="I", ul94="V0"),
    "nxj1s0505": dict(src="nxj1s0505.pdf (Murata NXJ1T series)", vin=(4.5, 5.0, 5.5), iout_max=0.200, iin_rated=0.250,
                      load_reg_pct=(24, 35), ripple_mvpp=(5, 20), eff_pct=(71, 76), fsw_hz=1.5e6, ciso_pf=2.5,
                      viso_vdc=4200, ul62368_reinf_vrms=200, ul62368_basic_vrms=400, creepage_mm=4.0, clearance_mm=4.0,
                      min_load_pct=10, pins={1: "-Vin", 3: "+Vin", 7: "-Vout", 8: "+Vout", 12: "NC", 14: "NC"}),
    "mbr0560": dict(src="mbr0560.pdf (MCC MBR0520-0580)", vf_max_at_0p5a=0.55, vf_est_95ma=0.36, vf_est_50ma=0.32, ir_max=0.1e-3,
                    note="VF at 50-100 mA estimated from the MCC curve: EST"),
    "bas31": dict(src="bas31.pdf (onsemi)", vf_max_10ma=0.75, ir_max_90v=100e-9, ct_pf=35, vr=120),
    "bat54s": dict(src="bat54s.pdf (onsemi BAT54SL)", vf_typ={0.1e-3: 0.22, 1e-3: 0.29, 10e-3: 0.35, 30e-3: 0.41, 100e-3: 0.52},
                   ir_typ_25v=0.15e-6, ir_max_25v=2e-6, pins={1: "anode", 2: "cathode", 3: "cathode/anode common"}),
    "ct94": dict(src="ct94.pdf (Nidec Copal CT-94)", turns=18, p70_w=0.5, tol=0.10, vmax_dc=300),
    "dr331": dict(src="dr331.pdf (Bourns)", l_uh=1000, tol=0.25, i_a=0.5),
    "mlz2012": dict(src="mlz2012.pdf (TDK MLZ2012)", m2r2={"l_uh": 2.2, "dcr_ohm": 0.16, "i_ma": 600},
                    n6r8={"l_uh": 6.8, "dcr_ohm": 0.25, "i_ma": 550}),
    "a750": dict(src="a750.pdf (KEMET A750) and the BOM description", c_uf=1000, v=25, esr_mohm=14),
    "cl21a226": dict(src="cl21a226.pdf (Samsung page render) for the rating; DC-bias curve shape from the review's class-2 fit",
                     c_uf=22, v=25, dielectric="X5R",
                     derate_note="C(V)/C0 = 1/(1 + 4.94 (V/25)^2): 0.78 at 6 V, 0.48 at 12 V, 0.36 at 15 V - EST, fitted to typical Samsung CL curves"),
    "measured": dict(src="docs/TEST_REPORT.md, bench 2026-09-05/06, Rev 3.1 board",
                     i_aux_15v_x100=95.8e-3, i_aux_13_to_15p5=(94.2e-3, 97.0e-3), vclamp_x100=5.70, bw_x100=60e3, bw_x10=580e3,
                     gain_err_x100=-0.0005, gain_err_x10=-0.0024, rout=50.5, noise_x100_input_rms=2e-3, spur_x10_hz=108.3e3),
}


def derate_x5r(v, vrated=25.0):
    return 1.0 / (1.0 + 4.94 * (v / vrated) ** 2)


if __name__ == "__main__":
    import json
    print(json.dumps({k: {kk: (vv if not isinstance(vv, dict) else str(vv)) for kk, vv in v.items()} for k, v in P.items()}, indent=1, default=str)[:3000])
