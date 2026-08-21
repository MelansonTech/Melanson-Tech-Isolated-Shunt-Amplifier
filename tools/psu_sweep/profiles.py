"""
Board-specific supply envelopes and stock sweep plans.

The driver knows nothing about what is plugged into it. This is where the
Isolated Shunt Amplifier's own numbers live, so that the limits enforced in
software are traceable to a line in the documentation rather than to a
magic number in a script.

Every figure below comes from README.md and docs/DESIGN_REVIEW.md.
"""
from __future__ import annotations

from typing import List

from .supply import Limits
from .sweep import steps

# ── Isolated Shunt Amplifier Rev 3.1 ────────────────────────────────────────

#: Specified auxiliary supply range.
AUX_MIN, AUX_NOMINAL, AUX_MAX = 13.0, 15.0, 15.6

#: Below this the UA78L12 drops out of regulation (14.5 V plus a Schottky) and
#: the +12 V rail — and the 6 V reference riding on it — sags with the input.
REGULATION_KNEE = 14.9

#: Absolute ceiling: Rel1's coil is driven straight from the input, and 15.6 V
#: is already 130 % of its rating.
ABSOLUTE_MAX = 15.6

#: The board draws about 300 mW, so roughly 20 mA at 15 V. 100 mA is loose
#: enough never to fold back in normal operation and tight enough that a
#: mis-wired input or a shorted rail trips CC instead of cooking something.
DEFAULT_CURRENT_LIMIT = 0.100

ISOLATION_WARNING = """\
The supply's negative output MUST be floating.

ISenseRTN — the output return, on the SMA shell — is bonded to chassis, and the
board's 0 V rail floats about 6 V below it. If the supply's negative terminal is
strapped to the earth post, the reference buffer is shorted to earth: the
measurement collapses and the part overheats, with nothing visible from outside.

Before the first run, confirm continuity is OPEN between the supply's negative
output terminal and its earth pin. See README.md and docs/SAFETY.md."""


SHUNT_AMP_AUX = Limits(
    min_voltage=AUX_MIN,
    max_voltage=ABSOLUTE_MAX,
    max_current=0.5,
    name="shunt amplifier aux",
    rationale=(
        f"The board is specified for {AUX_MIN}–{AUX_NOMINAL} V and must never see more than "
        f"{ABSOLUTE_MAX} V — Rel1's coil is driven from the input and that is already 130 % of "
        "its rating (README.md, 'On the supply voltage')."
    ),
)

#: For bringing a supply up on the bench with nothing connected.
BENCH_UNLOADED = Limits(
    min_voltage=0.0,
    max_voltage=36.0,
    max_current=8.0,
    name="IPS3608 unloaded",
    rationale="Front-panel ratings of the supply itself — no device-under-test envelope applied.",
)

PROFILES = {
    "shunt-amp": SHUNT_AMP_AUX,
    "bench": BENCH_UNLOADED,
}


def annotate(volts: float) -> str:
    """The one-line note attached to a sweep point at this supply voltage."""
    if volts < REGULATION_KNEE:
        return "+12 V rail unregulated"
    if volts > AUX_NOMINAL:
        return "above 15 V nominal"
    return ""


def default_points() -> List[float]:
    """
    The stock supply sweep for this board: 13.0 V to 15.6 V in 100 mV steps,
    with the 14.9 V regulation knee landing on a step boundary so the two
    points either side of it bracket the transition.
    """
    return steps(AUX_MIN, ABSOLUTE_MAX, 0.1)
