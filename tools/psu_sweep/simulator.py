"""
A simulated IPS3608 that speaks the real framing.

It exists for two reasons: every test in this package runs against it, and
`--simulate` lets you rehearse a sweep — argument handling, dwell times, CSV
layout, the abort path — before the board is on the bench.

What it models is the *protocol* and the coarse electrical behaviour: setpoint
tracking with a first-order lag, CV/CC crossover against a resistive load,
OVP/OCP trips, and a little seeded noise so averaging has something to do. It
is not a circuit model, and it cannot tell you whether the register map in
`protocol.py` is right — only hardware can do that.
"""
from __future__ import annotations

import math
import random
import struct
import time
from dataclasses import dataclass
from typing import Callable, List

from . import protocol as pr

#: Front-panel ratings of the IPS3608.
MAX_VOLTAGE, MAX_CURRENT = 36.0, 8.0

#: Default load: the shunt amplifier draws about 300 mW at 15 V (~20 mA), so
#: roughly 750 ohms looks like the real device under test.
DEFAULT_LOAD_OHMS = 750.0


@dataclass
class SimulatedSupply:
    """Feed it request bytes, poll it for reply bytes."""

    load_ohms: float = DEFAULT_LOAD_OHMS
    #: First-order settling of the output after a setpoint change, seconds.
    tau: float = 0.05
    telemetry_interval: float = 0.1
    noise_v: float = 0.001
    noise_a: float = 0.0002
    seed: int = 1
    clock: Callable[[], float] = time.monotonic
    #: When set, the supply ignores CONNECT until it is called — used to test
    #: the driver's handshake timeout.
    deaf: bool = False

    def __post_init__(self) -> None:
        self.state = pr.DeviceState(
            max_voltage=MAX_VOLTAGE,
            max_current=MAX_CURRENT,
            ovp=MAX_VOLTAGE,
            ocp=MAX_CURRENT,
            opp=MAX_VOLTAGE * MAX_CURRENT,
            otp=80.0,
            input_voltage=230.0,
            temperature=27.5,
            presets=[(5.0, 1.0), (12.0, 1.0), (15.0, 0.1), (24.0, 1.0), (0.0, 0.0), (0.0, 0.0)],
        )
        self._rng = random.Random(self.seed)
        self._rx = bytearray()
        self._connected = False
        self._settled_v = 0.0          # the lag state, before noise
        self._last_tick = self.clock()
        self._last_telemetry = 0.0
        #: Every request the host sent, for tests that assert on traffic.
        self.received: List[pr.Frame] = []

    # ── host side ───────────────────────────────────────────────────────────

    def feed(self, data: bytes) -> bytes:
        """Consume request bytes; return whatever the supply answers at once."""
        self._rx.extend(data)
        out = bytearray()
        for frame in pr.parse_frames(self._rx, pr.HEADER_REQUEST):
            self.received.append(frame)
            out.extend(self._handle(frame))
        return bytes(out)

    def poll(self) -> bytes:
        """Advance the model and return any unsolicited telemetry now due."""
        self._tick()
        if not self._connected:
            return b""
        now = self.clock()
        if now - self._last_telemetry < self.telemetry_interval:
            return b""
        self._last_telemetry = now
        return self._reply(pr.Reg.ALL, pr.encode_all(self.state))

    # ── internals ───────────────────────────────────────────────────────────

    def _reply(self, register: int, data: bytes, cmd_type: int = pr.CmdType.READ) -> bytes:
        frame = pr.encode(cmd_type, register, data)
        return bytes([pr.HEADER_RESPONSE]) + frame[1:]

    def _handle(self, frame: pr.Frame) -> bytes:
        reg, data = frame.register, frame.data

        if frame.cmd_type == pr.CmdType.CONNECT:
            if self.deaf:
                return b""
            self._connected = bool(data and data[0])
            if not self._connected:
                return b""
            self._last_telemetry = 0.0
            return self._reply(pr.Reg.ALL, pr.encode_all(self.state))

        if frame.cmd_type == pr.CmdType.READ:
            self._tick()
            if reg == pr.Reg.ALL:
                return self._reply(pr.Reg.ALL, pr.encode_all(self.state))
            if reg == pr.Reg.LIVE:
                return self._reply(pr.Reg.LIVE, struct.pack(
                    "<fff", self.state.set_voltage,
                    self.state.output_voltage, self.state.output_current))
            if reg == pr.Reg.SET_VOLTAGE:
                return self._reply(reg, _f(self.state.set_voltage))
            if reg == pr.Reg.SET_CURRENT:
                return self._reply(reg, _f(self.state.set_current))
            if reg == pr.Reg.TEMPERATURE:
                return self._reply(reg, _f(self.state.temperature))
            if reg == pr.Reg.OUTPUT_STATE:
                return self._reply(reg, bytes([int(self.state.output_enabled)]))
            # Anything else answers with the full dump, as the real unit does
            # for registers its firmware does not break out.
            return self._reply(pr.Reg.ALL, pr.encode_all(self.state))

        if frame.cmd_type == pr.CmdType.WRITE_FLOAT:
            value = pr.unpack_float(data)
            if value is None:
                return b""
            if reg == pr.Reg.SET_VOLTAGE:
                self.state.set_voltage = min(max(value, 0.0), MAX_VOLTAGE)
            elif reg == pr.Reg.SET_CURRENT:
                self.state.set_current = min(max(value, 0.0), MAX_CURRENT)
            return self._reply(pr.Reg.ALL, pr.encode_all(self.state))

        if frame.cmd_type == pr.CmdType.WRITE_BYTE and reg == pr.Reg.OUTPUT_STATE:
            self.state.output_enabled = bool(data and data[0])
            if not self.state.output_enabled:
                self.state.protection = int(pr.Protection.OK)
            self._tick()
            return self._reply(pr.Reg.ALL, pr.encode_all(self.state))

        return b""

    def _tick(self) -> None:
        now = self.clock()
        dt, self._last_tick = max(now - self._last_tick, 0.0), now
        s = self.state

        target = s.set_voltage if (s.output_enabled and not s.in_protection) else 0.0

        # Current limit: with a resistive load the supply drops into CC when the
        # load would draw more than the setpoint allows.
        if self.load_ohms > 0 and target / self.load_ohms > s.set_current > 0:
            target = s.set_current * self.load_ohms
            s.mode = int(pr.Mode.CC)
        else:
            s.mode = int(pr.Mode.CV)

        alpha = 1.0 if self.tau <= 0 else 1.0 - math.exp(-dt / self.tau)
        self._settled_v += (target - self._settled_v) * min(alpha, 1.0)

        v = max(self._settled_v + self._rng.gauss(0.0, self.noise_v), 0.0)
        i = v / self.load_ohms if self.load_ohms > 0 else 0.0
        i = max(i + self._rng.gauss(0.0, self.noise_a), 0.0)

        s.output_voltage, s.output_current, s.output_power = v, i, v * i
        s.capacity_ah += i * dt / 3600.0
        s.capacity_wh += v * i * dt / 3600.0

        if s.output_enabled and s.set_voltage > s.ovp:
            s.protection, s.output_enabled = int(pr.Protection.OVP), False
        elif s.output_enabled and i > s.ocp:
            s.protection, s.output_enabled = int(pr.Protection.OCP), False


def _f(value: float) -> bytes:
    return struct.pack("<f", value)
