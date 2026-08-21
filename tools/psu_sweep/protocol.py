"""
Wire protocol for the FNIRSI IPS3608 programmable bench supply.

Framing, register map and value decoding — no I/O. Everything here is a pure
function over bytes, so it is testable without hardware and without pyserial.

    request   [0xF1] [cmd_type] [register] [length] [data...] [checksum]
    response  [0xF0] [cmd_type] [register] [length] [data...] [checksum]
    checksum  = (register + length + sum(data)) & 0xFF        # cmd_type excluded

Numeric payloads are 4-byte little-endian IEEE-754 floats.

PROVENANCE — read this before trusting a field
----------------------------------------------
FNIRSI publishes no protocol document. The framing, the command types and the
0xFF layout below come from community reverse-engineering of the vendor's PC
software, cross-checked against https://github.com/alexgavs/newfnrs. The
framing and the float encoding are consistent everywhere and are safe to rely
on. Three details are *not* consistent between sources and are marked
`UNVERIFIED` where they appear:

  * the SET_CURRENT register (0xDE here; one source says 0xC2, and 0xDE is
    also cited as a model-string register),
  * the byte offset and polarity of the output-enabled flag in the 0xFF dump,
  * the 0xC3 payload layout (set-V/measured-V/measured-A here; one source
    reads it as V/A/W).

`psu_sweep.verify` exercises each of these against a real unit and prints what
it actually observed. Run it once on your bench before a long sweep, and
correct the constants here if it disagrees.
"""
from __future__ import annotations

import struct
from dataclasses import dataclass, field
from enum import IntEnum
from typing import Iterator, List, Optional, Tuple

HEADER_REQUEST = 0xF1
HEADER_RESPONSE = 0xF0

#: Frame overhead: header, cmd_type, register, length, checksum.
FRAME_OVERHEAD = 5

BAUD_RATES = (9600, 19200, 38400, 57600, 115200)
#: The unit powers up at 9600 unless its baud register has been rewritten.
DEFAULT_BAUD = 9600


class CmdType(IntEnum):
    """First payload byte — what kind of access this frame is."""

    READ = 0xA1
    WRITE_FLOAT = 0xB0
    WRITE_BYTE = 0xB1
    CONFIG = 0xC0
    CONNECT = 0xC1


class Reg(IntEnum):
    """Register addresses."""

    BAUD_RATE = 0x00
    CONNECTION = 0x00       # same address; CmdType.CONNECT distinguishes it

    SET_VOLTAGE = 0xC0
    PRESET_V1 = 0xC1
    PRESET_A1 = 0xC2
    LIVE = 0xC3             # UNVERIFIED layout — see module docstring
    TEMPERATURE = 0xC4

    CAPACITY_AH = 0xD9
    CAPACITY_WH = 0xDA
    OUTPUT_STATE = 0xDB
    PROTECTION = 0xDC
    MODE = 0xDD

    # UNVERIFIED. 0xDE is cited both as the current setpoint and as a model
    # string register. Writes here are how the vendor software sets the CC
    # limit, which is the reading this driver uses.
    SET_CURRENT = 0xDE

    SERIAL = 0xDF
    FIRMWARE = 0xE0
    DEVICE_ID = 0xE1
    MAX_VOLTAGE = 0xE2
    MAX_CURRENT = 0xE3

    ALL = 0xFF              # full state dump — the driver's source of truth


class Protection(IntEnum):
    OK = 0
    OVP = 1
    OCP = 2
    OPP = 3
    OTP = 4
    SCP = 5

    @property
    def label(self) -> str:
        return self.name


class Mode(IntEnum):
    CV = 0
    CC = 1


class ProtocolError(ValueError):
    """A frame could not be built or decoded."""


# ── encoding ────────────────────────────────────────────────────────────────

def checksum(register: int, data: bytes) -> int:
    """Frame checksum. Note that cmd_type is deliberately not included."""
    return (register + len(data) + sum(data)) & 0xFF


def encode(cmd_type: int, register: int, data: bytes = b"\x00") -> bytes:
    """Build one request frame."""
    if len(data) > 0xFF:
        raise ProtocolError(f"payload of {len(data)} bytes exceeds the 255-byte length field")
    return bytes([HEADER_REQUEST, cmd_type, register, len(data), *data, checksum(register, data)])


def encode_float(cmd_type: int, register: int, value: float) -> bytes:
    return encode(cmd_type, register, struct.pack("<f", value))


def read(register: int) -> bytes:
    return encode(CmdType.READ, register)


def connect() -> bytes:
    return encode(CmdType.CONNECT, Reg.CONNECTION, b"\x01")


def disconnect() -> bytes:
    return encode(CmdType.CONNECT, Reg.CONNECTION, b"\x00")


def set_voltage(volts: float) -> bytes:
    return encode_float(CmdType.WRITE_FLOAT, Reg.SET_VOLTAGE, volts)


def set_current(amps: float) -> bytes:
    return encode_float(CmdType.WRITE_FLOAT, Reg.SET_CURRENT, amps)


def set_output(on: bool) -> bytes:
    return encode(CmdType.WRITE_BYTE, Reg.OUTPUT_STATE, b"\x01" if on else b"\x00")


def set_baud(baud: int) -> bytes:
    """Change the unit's baud register. Takes effect on its next power cycle."""
    if baud not in BAUD_RATES:
        raise ProtocolError(f"{baud} is not one of {BAUD_RATES}")
    return encode(CmdType.WRITE_FLOAT, Reg.BAUD_RATE, bytes([BAUD_RATES.index(baud) + 1]))


# ── decoding ────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class Frame:
    cmd_type: int
    register: int
    data: bytes

    def as_float(self, offset: int = 0) -> Optional[float]:
        return unpack_float(self.data, offset)

    def __repr__(self) -> str:  # hex dump reads better than a byte list in a log
        body = " ".join(f"{b:02X}" for b in self.data)
        return f"<Frame cmd=0x{self.cmd_type:02X} reg=0x{self.register:02X} [{body}]>"


def unpack_float(data: bytes, offset: int = 0) -> Optional[float]:
    """Little-endian float at `offset`, or None if the payload is too short."""
    if len(data) < offset + 4:
        return None
    return struct.unpack_from("<f", data, offset)[0]


def parse_frames(buffer: bytearray, header: int = HEADER_RESPONSE) -> Iterator[Frame]:
    """
    Pull every complete frame out of `buffer`, consuming it in place.

    Defaults to decoding what the supply sends; the simulator passes
    `HEADER_REQUEST` to decode what the host sends, so both directions go
    through one parser and one checksum.

    Leading garbage is skipped one byte at a time so a mid-stream connection
    resynchronises, and a frame whose checksum fails is dropped the same way —
    dropping only the header byte, not the whole frame, because a bad checksum
    usually means the length byte was garbage too.
    """
    while True:
        start = buffer.find(header)
        if start < 0:
            buffer.clear()
            return
        del buffer[:start]
        if len(buffer) < FRAME_OVERHEAD:
            return

        length = buffer[3]
        size = FRAME_OVERHEAD + length
        if len(buffer) < size:
            return

        cmd_type, register = buffer[1], buffer[2]
        data, cs = bytes(buffer[4:4 + length]), buffer[size - 1]
        if cs != checksum(register, data):
            del buffer[0]
            continue

        del buffer[:size]
        yield Frame(cmd_type=cmd_type, register=register, data=data)


# ── device state ────────────────────────────────────────────────────────────

# Layout of the 0xFF full-state dump. Keeping it as a table rather than a wall
# of struct offsets means a bench correction is a one-line edit, and
# `psu_sweep.verify` can print the whole thing next to the front panel.
#
# kind: "f" = 4-byte float, "b" = single byte.
ALL_LAYOUT: Tuple[Tuple[str, int, str], ...] = (
    ("input_voltage",   0,   "f"),
    ("set_voltage",     4,   "f"),
    ("set_current",     8,   "f"),
    ("output_voltage",  12,  "f"),
    ("output_current",  16,  "f"),
    ("output_power",    20,  "f"),
    ("temperature",     24,  "f"),
    # 28..95 — six preset voltage/current pairs, handled separately below
    ("preset_index",    96,  "b"),
    ("capacity_ah",     99,  "f"),
    ("capacity_wh",     103, "f"),
    ("_output_flag",    107, "b"),   # UNVERIFIED offset and polarity
    ("protection",      108, "b"),
    ("mode",            109, "b"),
    ("max_voltage",     111, "f"),
    ("max_current",     115, "f"),
    ("ovp",             119, "f"),
    ("ocp",             123, "f"),
    ("opp",             127, "f"),
    ("otp",             131, "f"),
)

#: UNVERIFIED. The one source for this reads the flag as active-low —
#: `payload[107] == 0` means the output is live. Confirm against the front
#: panel with `psu_sweep.verify` before relying on it for a safety decision;
#: this driver never uses it as one.
OUTPUT_FLAG_ACTIVE_LOW = True

PRESET_BASE, PRESET_COUNT, PRESET_STRIDE = 28, 6, 8


@dataclass
class DeviceState:
    """Everything the supply has told us so far. Fields hold their last value."""

    input_voltage: float = 0.0
    set_voltage: float = 0.0
    set_current: float = 0.0
    output_voltage: float = 0.0
    output_current: float = 0.0
    output_power: float = 0.0
    temperature: float = 0.0

    max_voltage: float = 0.0
    max_current: float = 0.0
    ovp: float = 0.0
    ocp: float = 0.0
    opp: float = 0.0
    otp: float = 0.0

    capacity_ah: float = 0.0
    capacity_wh: float = 0.0

    output_enabled: bool = False
    protection: int = int(Protection.OK)
    mode: int = int(Mode.CV)

    presets: List[Tuple[float, float]] = field(default_factory=list)
    preset_index: int = 0

    frames_seen: int = 0
    #: Raw payload of the most recent 0xFF dump, kept for `psu_sweep verify`
    #: and for diagnosing a firmware whose layout differs from ALL_LAYOUT.
    last_all: bytes = b""
    #: Raw payload of the most recent 0xC3 live-values frame, same purpose.
    last_live: bytes = b""
    #: Registers that arrived but decoded to nothing — the first thing to look
    #: at when the map above is wrong for your firmware.
    unknown_registers: List[int] = field(default_factory=list)

    @property
    def mode_label(self) -> str:
        return Mode(self.mode).name if self.mode in (0, 1) else f"?{self.mode}"

    @property
    def protection_label(self) -> str:
        try:
            return Protection(self.protection).label
        except ValueError:
            return f"?{self.protection}"

    @property
    def in_protection(self) -> bool:
        return self.protection != int(Protection.OK)


def apply(frame: Frame, state: DeviceState) -> DeviceState:
    """Fold one decoded frame into `state`, in place."""
    state.frames_seen += 1
    reg, data = frame.register, frame.data

    if reg == Reg.ALL:
        _apply_all(data, state)
    elif reg == Reg.SET_VOLTAGE:
        _set_float(state, "set_voltage", data)
    elif reg == Reg.SET_CURRENT:
        _set_float(state, "set_current", data)
    elif reg == Reg.LIVE and len(data) >= 12:
        # UNVERIFIED layout — see the module docstring.
        state.last_live = data
        _set_float(state, "set_voltage", data, 0)
        _set_float(state, "output_voltage", data, 4)
        _set_float(state, "output_current", data, 8)
    elif reg == Reg.TEMPERATURE:
        _set_float(state, "temperature", data)
    elif reg == Reg.CAPACITY_AH:
        _set_float(state, "capacity_ah", data)
    elif reg == Reg.CAPACITY_WH:
        _set_float(state, "capacity_wh", data)
    elif reg == Reg.OUTPUT_STATE and data:
        state.output_enabled = bool(data[0])
    elif reg == Reg.PROTECTION and data:
        state.protection = data[0]
    elif reg == Reg.MODE and data:
        state.mode = data[0]
    elif reg == Reg.MAX_VOLTAGE:
        _set_float(state, "max_voltage", data)
    elif reg == Reg.MAX_CURRENT:
        _set_float(state, "max_current", data)
    elif reg not in (Reg.SERIAL, Reg.FIRMWARE, Reg.DEVICE_ID):
        if reg not in state.unknown_registers:
            state.unknown_registers.append(reg)

    return state


def _set_float(state: DeviceState, name: str, data: bytes, offset: int = 0) -> None:
    value = unpack_float(data, offset)
    # A register the unit does not implement answers with zeros or garbage;
    # NaN and infinities are never real readings, so drop them rather than
    # letting one poison a sweep row.
    if value is not None and value == value and abs(value) != float("inf"):
        setattr(state, name, value)


def _apply_all(payload: bytes, state: DeviceState) -> None:
    state.last_all = payload
    for name, offset, kind in ALL_LAYOUT:
        if kind == "f":
            _set_float(state, name, payload, offset)
        elif len(payload) > offset:
            byte = payload[offset]
            if name == "_output_flag":
                state.output_enabled = (byte == 0) if OUTPUT_FLAG_ACTIVE_LOW else bool(byte)
            else:
                setattr(state, name, byte)

    presets = []
    for i in range(PRESET_COUNT):
        base = PRESET_BASE + i * PRESET_STRIDE
        v, a = unpack_float(payload, base), unpack_float(payload, base + 4)
        if v is None or a is None:
            break
        presets.append((v, a))
    if presets:
        state.presets = presets


def encode_all(state: DeviceState) -> bytes:
    """
    Build a 0xFF payload from `state` — the inverse of `_apply_all`.

    Only the simulator needs this, but it lives here so the layout table has
    exactly one reader and one writer and the two cannot drift apart.
    """
    size = max(offset + (4 if kind == "f" else 1) for _, offset, kind in ALL_LAYOUT)
    payload = bytearray(size)

    for i, (v, a) in enumerate(state.presets[:PRESET_COUNT]):
        struct.pack_into("<ff", payload, PRESET_BASE + i * PRESET_STRIDE, v, a)

    for name, offset, kind in ALL_LAYOUT:
        if kind == "f":
            struct.pack_into("<f", payload, offset, float(getattr(state, name, 0.0)))
        elif name == "_output_flag":
            on = state.output_enabled
            payload[offset] = (0 if on else 1) if OUTPUT_FLAG_ACTIVE_LOW else int(on)
        else:
            payload[offset] = int(getattr(state, name, 0)) & 0xFF

    return bytes(payload)
