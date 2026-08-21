#!/usr/bin/env python3
"""
Monte Carlo for the MelansonTech Isolated Shunt Amplifier tolerance budget.

Reproduces the statistical figures quoted in docs/DESIGN_REVIEW.md, section 7 —
specifically the claim that a linear worst-case sum is a bound no real board reaches,
and the hybrid basis used for the published specification.

    python3 tolerance_monte_carlo.py            # 2,000,000 trials, both ranges
    python3 tolerance_monte_carlo.py -n 100000  # quicker
    python3 tolerance_monte_carlo.py --dt 20    # full 0-40 C operating range

Requires numpy. Every input mirrors the Assumptions sheet of
docs/Tolerance Budget - Isolated Shunt Amplifier Rev 2.xlsx — change them there and here
together, or this stops being a check on that model and becomes a second opinion.

Sources for the device figures:
  Skyworks Si8921/22 datasheet  - gain error, gain drift, Vos, Vos drift, nonlinearity
  Vishay WSL3637 datasheet      - 10 mOhm, +/-0.5 %, +/-50 ppm/C, 3.0 W at 70 C
  TI LM7321 datasheet           - Vos, TCVos, Ib
"""
import argparse
import math

try:
    import numpy as np
except ImportError:
    raise SystemExit("numpy required:  pip install numpy")

SHUNT = 0.010          # ohms
THETA = (170 - 70) / 3.0   # C/W, from the WSL3637 derating curve
SHUNT_TCR = 50e-6      # /C

# Terms that come from ONE reel or tube and therefore do not average out across a
# batch of boards. These are held at their limits rather than sampled.
BATCH_CORRELATED = {"R5 initial tolerance", "Si8921 gain error"}


def terms(high_gain: bool, dT: float):
    """Return [(name, +/- limit in %, is_gain_term)] for one range."""
    imax = 5.0 if high_gain else 10.0
    fs_out = imax * SHUNT * (100 if high_gain else 10)     # volts
    self_heat = THETA * imax**2 * SHUNT * SHUNT_TCR * 100  # %

    gain = [
        ("R5 initial tolerance", 0.500),
        ("R5 self-heating", self_heat),
        ("R5 ambient drift", SHUNT_TCR * dT * 100),
        ("Si8921 gain error", 0.200),
        ("Si8921 gain drift", 24e-6 * dT * 100),
        ("R2/R9 tolerance", 0.050),
        ("R3/R20 tolerance", 0.100),
        ("U3 TCR mismatch", 35e-6 * dT * 100),
    ]
    if high_gain:
        k = (1410 / 156.67) / (1 + 1410 / 156.67)
        gain += [
            ("U8 network ratio", k * 0.1 / math.sqrt(3) * math.sqrt(2)),
            ("U8 TCR mismatch", k * 25e-6 * dT * 100),
            ("Rel1 contact resistance", k * 0.100 / 156.67 * 100),
        ]

    g_total = 100 if high_gain else 10          # shunt to output
    pc = lambda volts: volts / fs_out * 100     # volts at the output -> % of full scale
    g_u8 = 10 if high_gain else 1

    offset = [
        ("Si8921 offset drift", pc(3e-6 * dT * g_total)),
        ("Si8921 nonlinearity", 0.080),
        ("Reference drift", pc(0.01 * dT * 50e-9 * (60e3 - 50e3) * g_u8)),
        ("LM7321 Vos drift", pc(2.5e-6 * dT * math.sqrt(2) * g_u8)),
        ("R28 trim resolution", pc(12.0 * 100 / (2 * 100e3 + 100) * 0.01 * g_u8)),
        ("Shunt thermal EMF", pc(5e-6 * g_total)),
    ]
    return ([(n, v, True) for n, v in gain] + [(n, v, False) for n, v in offset],
            imax, fs_out)


def simulate(limits, n, dist, rng):
    total = np.zeros(n)
    for lim in limits:
        if dist == "uniform":
            total += rng.uniform(-lim, lim, n)
        else:
            sigma = lim / (3 if dist == "normal3" else 2)
            total += np.clip(rng.normal(0, sigma, n), -lim, lim)
    return np.abs(total)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("-n", type=int, default=2_000_000, help="trials (default 2e6)")
    ap.add_argument("--dt", type=float, default=5.0,
                    help="+/-C about the trim temperature (default 5, the accuracy window)")
    ap.add_argument("--seed", type=int, default=12345)
    args = ap.parse_args()
    rng = np.random.default_rng(args.seed)

    for high_gain, label in ((False, "10 A range (x10)"), (True, "5 A range (x100)")):
        t, imax, fs_out = terms(high_gain, args.dt)
        lims = np.array([v for _, v, _ in t])
        wc, rss = lims.sum(), math.sqrt((lims**2).sum())

        print(f"\n{'='*74}\n{label}  -  full scale {imax:.0f} A / {fs_out:.1f} V, "
              f"23 C +/-{args.dt:g} C\n{'='*74}")
        for n, v, _ in t:
            tag = "  <- batch-correlated" if n in BATCH_CORRELATED else ""
            print(f"   {n:<28} +/-{v:6.3f} %{tag}")
        print(f"\n   linear worst case  {wc:6.3f} %")
        print(f"   pure RSS           {rss:6.3f} %")

        for dist, desc in (("uniform", "uniform within limit (most conservative)"),
                           ("normal3", "normal, limit = 3 sigma (tested parts)"),
                           ("normal2", "normal, limit = 2 sigma")):
            a = simulate(lims, args.n, dist, rng)
            p = lambda q: np.percentile(a, q)
            over = (a > 1.0).mean()
            odds = "never" if over == 0 else f"~1 in {1/over:,.0f}"
            print(f"\n   {desc}")
            print(f"      median {p(50):.3f} %   99th {p(99):.3f} %   "
                  f"99.9th {p(99.9):.3f} %   worst {a.max():.3f} %")
            print(f"      that worst case is {a.max()/wc*100:.0f} % of the linear sum;  "
                  f"P(> 1.0 %) = {odds}")

        dom = sum(v for n, v, _ in t if n in BATCH_CORRELATED)
        rest = math.sqrt(sum(v*v for n, v, _ in t if n not in BATCH_CORRELATED))
        gain_only = [(n, v) for n, v, g in t if g]
        off_only = [(n, v) for n, v, g in t if not g]
        dom_g = sum(v for n, v in gain_only if n in BATCH_CORRELATED)
        rest_g = math.sqrt(sum(v*v for n, v in gain_only if n not in BATCH_CORRELATED))
        fixed = sum(v for _, v in off_only) / 100 * imax * 1000

        print(f"\n   HYBRID BASIS - batch-correlated terms at their limits, rest in quadrature")
        print(f"      proportional  {dom_g:.3f} % + {rest_g:.3f} % = {dom_g + rest_g:.3f} %"
              f"   -> publish {math.ceil((dom_g + rest_g) * 10) / 10:.1f} %")
        print(f"      fixed         {fixed:.1f} mA"
              f"   -> publish {math.ceil(fixed):.0f} mA")
        print(f"      SPEC:  +/-({math.ceil((dom_g + rest_g)*10)/10:.1f} % of reading "
              f"+ {math.ceil(fixed):.0f} mA)")

    print("\nWhy hybrid: the linear sum assumes every tolerance hits its limit in the same")
    print("direction, which the simulation above shows never happens. But pure RSS assumes")
    print("independence, and boards built from one reel of shunts share the same offset from")
    print("nominal. Holding the batch-correlated terms at their limits and combining the rest")
    print("in quadrature survives a bad reel without quoting an unreachable bound.\n")


if __name__ == "__main__":
    main()
