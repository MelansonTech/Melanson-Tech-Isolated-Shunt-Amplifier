"""
Byte transports for the supply driver.

The driver only ever needs three operations — write bytes, take whatever bytes
have arrived, close — so that is the whole interface. A real port and the
simulator both satisfy it, which is what lets every test in this package run
with no hardware attached.
"""
from __future__ import annotations

import time
from typing import List, Protocol


class Transport(Protocol):
    """Anything the driver can talk frames over."""

    name: str

    def write(self, data: bytes) -> None: ...

    def read_available(self) -> bytes:
        """Bytes received since the last call. Returns b"" when idle."""
        ...

    def close(self) -> None: ...


class SerialTransport:
    """A real USB serial port, via pyserial."""

    def __init__(self, port: str, baud: int, *, settle: float = 0.1) -> None:
        try:
            import serial
        except ImportError as exc:  # pragma: no cover - environment dependent
            raise RuntimeError(
                "pyserial is required to talk to real hardware:  pip install pyserial\n"
                "(the simulator backend needs no dependencies — see --simulate)"
            ) from exc

        self.name = port
        self._port = serial.Serial(
            port=port,
            baudrate=baud,
            bytesize=serial.EIGHTBITS,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE,
            timeout=0.1,
            write_timeout=2.0,
        )
        # The CH340-class bridge in these units needs both lines asserted and a
        # moment to settle, or the first frame goes out while the far end is
        # still coming up and is silently lost.
        self._port.rts = True
        self._port.dtr = True
        time.sleep(settle)
        self._port.reset_input_buffer()
        self._port.reset_output_buffer()

    def write(self, data: bytes) -> None:
        self._port.write(data)
        self._port.flush()

    def read_available(self) -> bytes:
        waiting = self._port.in_waiting
        return self._port.read(waiting) if waiting else b""

    def close(self) -> None:
        if self._port.is_open:
            self._port.close()


class LoopbackTransport:
    """
    Wires the driver straight to a `simulator.SimulatedSupply`.

    Requests are handed to the simulator as they are written; its replies queue
    up here until read. No threads and no clock of its own — the simulator is
    advanced by the driver's own polling, so tests are deterministic.
    """

    def __init__(self, device, *, name: str = "simulated") -> None:
        self.name = name
        self._device = device
        self._rx = bytearray()
        self._closed = False

    def write(self, data: bytes) -> None:
        if self._closed:
            raise RuntimeError("transport is closed")
        self._rx.extend(self._device.feed(data))

    def read_available(self) -> bytes:
        self._rx.extend(self._device.poll())
        out, self._rx = bytes(self._rx), bytearray()
        return out

    def close(self) -> None:
        self._closed = True


def find_ports() -> List[str]:
    """
    Candidate serial ports, likeliest first.

    The IPS3608 presents as a generic USB-serial bridge with no distinguishing
    VID/PID string, so this can only rank — it cannot identify. `psu_sweep
    probe` opens each candidate and asks, which is the only reliable test.
    """
    try:
        from serial.tools import list_ports
    except ImportError:
        return []

    def rank(port) -> tuple:
        text = f"{port.device} {port.description} {port.manufacturer or ''}".lower()
        usb_serial = any(k in text for k in ("ch340", "ch910", "cp210", "ftdi", "usb"))
        return (0 if usb_serial else 1, port.device)

    return [p.device for p in sorted(list_ports.comports(), key=rank)]
