"""LTspice plumbing for the precision DAC board simulations.

Runs LTspice in batch mode, reads its binary .raw files, and turns waveforms
into the numbers the design is judged on: settling time to +/-1 LSB, loop gain
and phase margin (Tian's double-injection method), integrated output noise.
"""
from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
LTSPICE = Path(os.environ.get(
    "LTSPICE", Path(os.environ.get("LOCALAPPDATA", "")) / "Programs/ADI/LTspice/LTspice.exe"))

LSB = 20.0 / 65536          # 305.2 uV on the +/-10 V span


# --------------------------------------------------------------------------- running

def run_ltspice(cir: Path, timeout: float = 1800) -> str:
    """Run one netlist in batch mode; return its log text, raising on a failed run."""
    cir = Path(cir)
    for stale in (cir.with_suffix(".raw"), cir.with_suffix(".log")):
        stale.unlink(missing_ok=True)
    subprocess.run([str(LTSPICE), "-b", cir.name], cwd=cir.parent, timeout=timeout, check=False)
    log_path = cir.with_suffix(".log")
    if not log_path.exists():
        raise RuntimeError(f"LTspice wrote no log for {cir.name}")
    raw = log_path.read_bytes()
    log = raw.decode("utf-16-le" if raw[1:2] == b"\x00" else "latin-1", errors="replace")
    if not cir.with_suffix(".raw").exists():
        raise RuntimeError(f"LTspice produced no .raw for {cir.name}:\n{log}")
    for bad in ("Error", "error:", "singular matrix", "Time step too small", "Simulation Failed"):
        if bad in log:
            raise RuntimeError(f"LTspice reported '{bad}' for {cir.name}:\n{log}")
    return log


# --------------------------------------------------------------------------- .raw reader

@dataclass
class Raw:
    names: list[str]
    data: np.ndarray            # points x variables (complex for AC)
    flags: set[str]

    def _col(self, name: str) -> int:
        low = [n.lower() for n in self.names]
        try:
            return low.index(name.lower())
        except ValueError:
            raise KeyError(f"{name} not in raw file; have {self.names}") from None

    def _sweep(self) -> np.ndarray:
        x = self.data[:, 0].real
        # LTspice flags some transient points with a negative time; only time gets abs()
        return np.abs(x) if self.names[0].lower() == "time" else x

    def runs(self) -> list[np.ndarray]:
        """Row indices of each .step run: a run ends where the sweep reverses direction."""
        d = np.diff(self._sweep())
        nz = d[d != 0]
        if len(nz) == 0:
            return [np.arange(len(self.data))]
        cuts = np.where(np.sign(d) == -np.sign(nz[0]))[0] + 1
        return np.split(np.arange(len(self.data)), cuts)

    def get(self, name: str, run: int = 0) -> np.ndarray:
        rows = self.runs()[run]
        col = self.data[rows, self._col(name)]
        return col if "complex" in self.flags else col.real

    def x(self, run: int = 0) -> np.ndarray:
        return self._sweep()[self.runs()[run]]


def read_raw(path: Path) -> Raw:
    buf = Path(path).read_bytes()
    enc = "utf-16-le" if buf[1:2] == b"\x00" else "latin-1"
    key = "Binary:\n".encode(enc)
    i = buf.find(key)
    if i < 0:
        raise ValueError(f"{path}: not a binary LTspice .raw file")
    head = buf[:i].decode(enc).replace("\r", "").split("\n")
    body = buf[i + len(key):]

    meta: dict[str, str] = {}
    names: list[str] = []
    for k, line in enumerate(head):
        if line.startswith("Variables:"):
            nv = int(meta["No. Variables"])
            names = [ln.split()[1] for ln in head[k + 1:k + 1 + nv]]
            break
        if ":" in line:
            key_, val = line.split(":", 1)
            meta[key_.strip()] = val.strip()
    nv, npts = int(meta["No. Variables"]), int(meta["No. Points"])
    flags = set(meta.get("Flags", "").lower().split())

    if "complex" in flags:
        dt = np.dtype("<c16")
        need = nv * npts * dt.itemsize
        data = np.frombuffer(body[:need], dtype=dt).reshape(npts, nv)
    elif "double" in flags:
        need = nv * npts * 8
        data = np.frombuffer(body[:need], dtype="<f8").reshape(npts, nv)
    else:                                   # sweep variable double, the rest float32
        rec = np.dtype([("x", "<f8"), ("y", "<f4", (nv - 1,))])
        need = npts * rec.itemsize
        r = np.frombuffer(body[:need], dtype=rec)
        data = np.column_stack([r["x"], r["y"].reshape(npts, nv - 1).astype(float)])
    if len(body) < need:
        raise ValueError(f"{path}: truncated ({len(body)} of {need} data bytes)")
    return Raw(names, data, flags)


# --------------------------------------------------------------------------- measures

def settle_time(t: np.ndarray, v: np.ndarray, t_edge: float, t_end: float,
                tol: float = LSB, final_window: float = 50e-9) -> tuple[float, float]:
    """Time from t_edge until v stays within +/-tol of its final value.

    The final value is the mean over the last final_window before t_end, so a
    static gain or offset error does not count as "unsettled" - that is a DC
    accuracy question, calibrated out on this board. Returns (t_settle, v_final);
    t_settle is nan if v never enters the band.
    """
    m = (t >= t_edge) & (t <= t_end)
    tw, vw = t[m], v[m]
    vf = float(np.mean(vw[tw >= t_end - final_window]))
    out = np.abs(vw - vf) > tol
    if not out.any():
        return 0.0, vf
    k = int(np.nonzero(out)[0][-1])
    if k == len(tw) - 1:
        return float("nan"), vf
    # interpolate the last crossing into the band
    e0, e1 = abs(vw[k] - vf) - tol, abs(vw[k + 1] - vf) - tol
    frac = e0 / (e0 - e1) if e0 != e1 else 0.0
    return float(tw[k] + frac * (tw[k + 1] - tw[k]) - t_edge), vf


def tian_loop_gain(tv_run: tuple[np.ndarray, np.ndarray], ti_run: np.ndarray) -> np.ndarray:
    """Loop gain T(f) from Tian's two injections at one break point.

    Break between the amplifier output node ao and the network node an, with
    a voltage source Vt (+ at an, - at ao) and a current source injecting into an.
      voltage run: Tv = -V(ao)/V(an)
      current run: Ti = I(Vt) / (1 - I(Vt))   (1 A injected; I(Vt) is the share
                                               flowing back into the amplifier)
      T = (Tv*Ti - 1) / (Tv + Ti + 2)
    """
    v_ao, v_an = tv_run
    tv = -v_ao / v_an
    ti = ti_run / (1 - ti_run)
    return (tv * ti - 1) / (tv + ti + 2)


def phase_margin(f: np.ndarray, t: np.ndarray) -> tuple[float, float]:
    """(crossover frequency, phase margin in degrees) of loop gain T."""
    mag = np.abs(t)
    above = mag >= 1
    idx = np.nonzero(above[:-1] & ~above[1:])[0]
    if len(idx) == 0:
        return float("nan"), float("nan")
    k = int(idx[-1])
    lf, lm = np.log10(f[k:k + 2]), np.log10(mag[k:k + 2])
    fc_log = lf[0] + (0 - lm[0]) * (lf[1] - lf[0]) / (lm[1] - lm[0])
    fc = 10 ** fc_log
    ph = np.unwrap(np.angle(t))
    ph_c = np.interp(fc_log, np.log10(f), ph)
    return float(fc), float(180 + np.degrees(ph_c))


def integrated_noise(f: np.ndarray, density: np.ndarray, f_lo: float, f_hi: float) -> float:
    """RMS of a noise density (V/rtHz) integrated over [f_lo, f_hi]."""
    m = (f >= f_lo) & (f <= f_hi)
    return float(np.sqrt(np.trapezoid(density[m] ** 2, f[m])))
