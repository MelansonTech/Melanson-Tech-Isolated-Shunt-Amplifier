"""
The supply interface the sweep engine talks to, and the IPS3608 driver.

`PowerSupply` is the whole contract: set a voltage, set a current limit, switch
the output, read back what the supply thinks is happening. Anything satisfying
it can be swept — a different FNIRSI model, a SCPI supply, or the simulator.

Two properties matter more than features here, because this drives a live
board:

  * **Every setpoint is checked against a limit envelope before it is sent.**
    A voltage outside the envelope raises; it is never clamped silently, since
    a silently clamped sweep produces data that looks fine and is wrong.
  * **Every write is confirmed by readback.** These units acknowledge with a
    state dump rather than a status code, and a dropped frame is otherwise
    invisible. A write that does not take within the retry budget raises.

The output is switched off on exit, including on an exception or a Ctrl-C.
"""
from __future__ import annotations

import abc
import time
from dataclasses import dataclass, replace

from . import protocol as pr
from .transport import Transport


class SupplyError(RuntimeError):
    """The supply did not do what it was asked."""


class LimitError(SupplyError):
    """A setpoint fell outside the configured envelope. Nothing was sent."""


class ProtectionTripped(SupplyError):
    """The supply's own OVP/OCP/OPP/OTP fired."""


@dataclass(frozen=True)
class Limits:
    """
    The envelope a supply is allowed to be driven within.

    This is a property of *what is connected to the supply*, not of the supply
    itself, which is why it is passed in rather than read from the device.
    `profiles.py` holds the envelope for the shunt amplifier.
    """

    min_voltage: float
    max_voltage: float
    max_current: float
    name: str = "generic"
    #: Shown verbatim when a setpoint is refused — say *why* the limit exists.
    rationale: str = ""

    def check_voltage(self, volts: float) -> None:
        if not (self.min_voltage <= volts <= self.max_voltage):
            raise LimitError(
                f"{volts:.3f} V is outside the {self.name} envelope "
                f"({self.min_voltage:.3f}–{self.max_voltage:.3f} V)."
                + (f"\n  {self.rationale}" if self.rationale else "")
            )

    def check_current(self, amps: float) -> None:
        if not (0.0 <= amps <= self.max_current):
            raise LimitError(
                f"{amps:.4f} A is outside the {self.name} envelope "
                f"(0–{self.max_current:.4f} A)."
                + (f"\n  {self.rationale}" if self.rationale else "")
            )


@dataclass(frozen=True)
class Reading:
    """One measurement of the supply's output."""

    #: What the supply is actually delivering.
    voltage: float
    current: float
    power: float
    #: What the supply says it was *asked* for — a disagreement with the
    #: requested value means a setpoint was clamped or a write went astray.
    set_voltage: float = 0.0
    set_current: float = 0.0
    temperature: float = 0.0
    mode: str = "CV"
    protection: str = "OK"
    output_enabled: bool = False
    samples: int = 1
    #: Peak-to-peak spread across the averaged samples, volts and amps.
    voltage_spread: float = 0.0
    current_spread: float = 0.0

    @property
    def in_protection(self) -> bool:
        return self.protection != pr.Protection.OK.name


class PowerSupply(abc.ABC):
    """A programmable supply the sweep engine can drive."""

    limits: Limits

    @abc.abstractmethod
    def open(self) -> "PowerSupply": ...

    @abc.abstractmethod
    def close(self) -> None: ...

    @abc.abstractmethod
    def set_voltage(self, volts: float) -> None: ...

    @abc.abstractmethod
    def set_current(self, amps: float) -> None: ...

    @abc.abstractmethod
    def set_output(self, on: bool) -> None: ...

    @abc.abstractmethod
    def read(self) -> Reading: ...

    def measure(self, samples: int = 1, interval: float = 0.05) -> Reading:
        """Average `samples` readings, reporting the spread across them."""
        if samples <= 1:
            return self.read()
        taken = [self.read()]
        for _ in range(samples - 1):
            time.sleep(interval)
            taken.append(self.read())

        volts = [r.voltage for r in taken]
        amps = [r.current for r in taken]
        last = taken[-1]
        return replace(
            last,
            voltage=sum(volts) / len(volts),
            current=sum(amps) / len(amps),
            power=sum(r.power for r in taken) / len(taken),
            temperature=sum(r.temperature for r in taken) / len(taken),
            samples=len(taken),
            voltage_spread=max(volts) - min(volts),
            current_spread=max(amps) - min(amps),
        )

    def __enter__(self) -> "PowerSupply":
        return self.open()

    def __exit__(self, exc_type, exc, tb) -> None:
        # Runs on Ctrl-C and on any exception. Best-effort: a supply that has
        # stopped answering must not stop us from closing the port.
        try:
            self.set_output(False)
        except Exception:
            pass
        self.close()


class IPS3608(PowerSupply):
    """FNIRSI IPS3608, 36 V / 8 A."""

    def __init__(
        self,
        transport: Transport,
        limits: Limits,
        *,
        timeout: float = 2.0,
        write_retries: int = 3,
        voltage_tolerance: float = 0.05,
        current_tolerance: float = 0.02,
        poll_interval: float = 0.01,
    ) -> None:
        self.transport = transport
        self.limits = limits
        self.timeout = timeout
        self.write_retries = write_retries
        self.voltage_tolerance = voltage_tolerance
        self.current_tolerance = current_tolerance
        self.poll_interval = poll_interval

        self.state = pr.DeviceState()
        self._buffer = bytearray()
        self._open = False

    # ── connection ──────────────────────────────────────────────────────────

    def open(self) -> "IPS3608":
        self.transport.write(pr.connect())
        if not self._pump_until(lambda s: s.frames_seen > 0, self.timeout):
            raise SupplyError(
                f"no reply from {self.transport.name} within {self.timeout:.1f} s.\n"
                "  Check the port, and that the baud rate matches the unit's "
                "System menu (it ships at 9600).\n"
                "  If the vendor PC software is running, close it — it holds the port."
            )
        self._open = True
        self.refresh()
        return self

    def close(self) -> None:
        if self._open:
            try:
                self.transport.write(pr.disconnect())
            except Exception:
                pass
            self._open = False
        self.transport.close()

    # ── setpoints ───────────────────────────────────────────────────────────

    def set_voltage(self, volts: float) -> None:
        self.limits.check_voltage(volts)
        self._write_confirmed(
            pr.set_voltage(volts), "voltage setpoint", volts,
            lambda s: s.set_voltage, self.voltage_tolerance, "V")

    def set_current(self, amps: float) -> None:
        self.limits.check_current(amps)
        self._write_confirmed(
            pr.set_current(amps), "current limit", amps,
            lambda s: s.set_current, self.current_tolerance, "A")

    def set_output(self, on: bool) -> None:
        if not self._open:
            return
        try:
            self._write_confirmed(
                pr.set_output(on), "output state", float(on),
                lambda s: float(s.output_enabled), 0.5, "")
        except SupplyError:
            # A supply that has tripped refuses to come on, and reports it only
            # by staying off. Say which protection fired rather than leaving
            # the caller to guess at a dropped frame.
            if on and self.state.in_protection:
                raise ProtectionTripped(
                    f"supply is in {self.state.protection_label} and will not enable its output — "
                    f"clear the trip at the front panel "
                    f"(setpoint {self.state.set_voltage:.3f} V, "
                    f"OVP {self.state.ovp:.3f} V, OCP {self.state.ocp:.3f} A)."
                ) from None
            raise

    def _write_confirmed(self, frame, what, target, getter, tolerance, unit) -> None:
        last = None
        for attempt in range(self.write_retries):
            self.transport.write(frame)
            if self._pump_until(
                lambda s: abs(getter(s) - target) <= tolerance,
                self.timeout,
                refresh_after=0.3,
            ):
                return
            last = getter(self.state)
        raise SupplyError(
            f"{what} did not take after {self.write_retries} attempts: "
            f"asked for {target:g}{unit}, supply reports {last:g}{unit}."
        )

    # ── readback ────────────────────────────────────────────────────────────

    def refresh(self) -> pr.DeviceState:
        """Ask for a full state dump and wait for one to land."""
        before = self.state.frames_seen
        self.transport.write(pr.read(pr.Reg.ALL))
        self._pump_until(lambda s: s.frames_seen > before, self.timeout)
        return self.state

    def read(self) -> Reading:
        s = self.refresh()
        return Reading(
            voltage=s.output_voltage,
            current=s.output_current,
            power=s.output_power,
            set_voltage=s.set_voltage,
            set_current=s.set_current,
            temperature=s.temperature,
            mode=s.mode_label,
            protection=s.protection_label,
            output_enabled=s.output_enabled,
        )

    def _pump(self) -> int:
        """Drain the transport into `state`. Returns the frame count decoded."""
        data = self.transport.read_available()
        if data:
            self._buffer.extend(data)
        count = 0
        for frame in pr.parse_frames(self._buffer):
            pr.apply(frame, self.state)
            count += 1
        return count

    def _pump_until(self, predicate, timeout: float, refresh_after: float = 0.0) -> bool:
        """
        Pump frames until `predicate(state)` holds or `timeout` expires.

        `refresh_after` re-asks for a state dump partway through: these units
        stream telemetry on their own, but not always promptly after a write,
        and one nudge is cheaper than burning the whole timeout.
        """
        deadline = time.monotonic() + timeout
        nudge_at = time.monotonic() + refresh_after if refresh_after else None

        while True:
            self._pump()
            if predicate(self.state):
                return True
            now = time.monotonic()
            if nudge_at is not None and now >= nudge_at:
                nudge_at = None
                self.transport.write(pr.read(pr.Reg.ALL))
            if now >= deadline:
                return False
            time.sleep(self.poll_interval)


def connect_simulated(limits: Limits, **kwargs) -> IPS3608:
    """An IPS3608 driver wired to the simulator. No hardware, no pyserial."""
    from .simulator import SimulatedSupply
    from .transport import LoopbackTransport

    sim_kwargs = {k: kwargs.pop(k) for k in list(kwargs) if k in
                  ("load_ohms", "tau", "telemetry_interval", "noise_v", "noise_a", "seed", "deaf")}
    return IPS3608(LoopbackTransport(SimulatedSupply(**sim_kwargs)), limits, **kwargs)


def connect_serial(port: str, limits: Limits, *, baud: int = pr.DEFAULT_BAUD, **kwargs) -> IPS3608:
    """An IPS3608 driver on a real serial port."""
    from .transport import SerialTransport

    return IPS3608(SerialTransport(port, baud), limits, **kwargs)
