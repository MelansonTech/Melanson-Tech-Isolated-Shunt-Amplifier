"""Sweep engine: point generation, settling, abort paths, CSV shape."""
import io
import unittest

from psu_sweep import profiles
from psu_sweep.simulator import SimulatedSupply
from psu_sweep.supply import IPS3608, Limits, ProtectionTripped
from psu_sweep.sweep import SweepPlan, run, steps, write_csv
from psu_sweep.transport import LoopbackTransport

BENCH = Limits(0.0, 36.0, 8.0, "test bench")
FAST = dict(dwell=0.0, samples=2, sample_interval=0.0, settle_timeout=2.0)


def supply(**kwargs) -> IPS3608:
    kwargs.setdefault("tau", 0.0)
    return IPS3608(LoopbackTransport(SimulatedSupply(**kwargs)), BENCH)


class TestSteps(unittest.TestCase):
    def test_endpoint_is_included_despite_float_error(self):
        points = steps(13.0, 15.6, 0.1)
        self.assertEqual(points[0], 13.0)
        self.assertEqual(points[-1], 15.6)
        self.assertEqual(len(points), 27)

    def test_the_regulation_knee_lands_on_a_step(self):
        self.assertIn(profiles.REGULATION_KNEE, profiles.default_points())

    def test_descending_sweeps_stay_descending(self):
        self.assertEqual(steps(15.0, 14.0, 0.5), [15.0, 14.5, 14.0])

    def test_ragged_step_still_reaches_the_stop(self):
        self.assertEqual(steps(13.0, 14.0, 0.3)[-1], 14.0)

    def test_step_must_be_positive(self):
        with self.assertRaises(ValueError):
            steps(13.0, 15.0, 0.0)


class TestRun(unittest.TestCase):
    def test_every_point_is_visited_and_recorded(self):
        with supply() as psu:
            rows = run(psu, SweepPlan(points=[12.0, 13.0, 14.0], current_limit=1.0, **FAST))
        self.assertEqual([row.requested_v for row in rows], [12.0, 13.0, 14.0])
        self.assertTrue(all(row.settled for row in rows))
        for row in rows:
            self.assertAlmostEqual(row.measured_v, row.requested_v, delta=0.05)

    def test_reported_setpoint_tracks_the_request(self):
        with supply() as psu:
            rows = run(psu, SweepPlan(points=[12.0, 14.0], current_limit=1.0, **FAST))
        for row in rows:
            self.assertAlmostEqual(row.set_v, row.requested_v, places=3)

    def test_bidirectional_retraces_without_repeating_the_turning_point(self):
        with supply() as psu:
            rows = run(psu, SweepPlan(points=[12.0, 13.0, 14.0], current_limit=1.0,
                                      bidirectional=True, **FAST))
        self.assertEqual([row.requested_v for row in rows], [12.0, 13.0, 14.0, 13.0, 12.0])

    def test_output_is_off_when_the_sweep_ends(self):
        device = SimulatedSupply(tau=0.0)
        psu = IPS3608(LoopbackTransport(device), BENCH)
        with psu:
            run(psu, SweepPlan(points=[12.0, 13.0], current_limit=1.0, **FAST))
            self.assertFalse(device.state.output_enabled)

    def test_output_is_off_after_an_aborted_sweep(self):
        device = SimulatedSupply(tau=0.0)
        psu = IPS3608(LoopbackTransport(device), BENCH)

        def explode(point, _psu):
            raise RuntimeError("hook failed")

        with psu:
            with self.assertRaises(RuntimeError):
                run(psu, SweepPlan(points=[12.0, 13.0], current_limit=1.0, **FAST), hook=explode)
            self.assertFalse(device.state.output_enabled)

    def test_a_trip_aborts_rather_than_recording_fiction(self):
        device = SimulatedSupply(tau=0.0)
        device.state.ovp = 13.5
        psu = IPS3608(LoopbackTransport(device), BENCH, write_retries=1, timeout=0.3)
        with psu:
            with self.assertRaises(ProtectionTripped):
                run(psu, SweepPlan(points=[12.0, 13.0, 14.0, 15.0], current_limit=1.0, **FAST))

    def test_unreachable_setpoint_is_flagged_not_silently_accepted(self):
        # A 10 mA limit into 750 ohms cannot reach 15 V, so the point never
        # settles — it must be recorded as such, and in CC.
        with supply() as psu:
            rows = run(psu, SweepPlan(points=[15.0], current_limit=0.010,
                                      dwell=0.0, samples=1, sample_interval=0.0,
                                      settle_timeout=0.3))
        self.assertFalse(rows[0].settled)
        self.assertEqual(rows[0].mode, "CC")

    def test_notes_come_from_the_board_profile(self):
        with supply() as psu:
            rows = run(psu, SweepPlan(points=[13.0, 15.0], current_limit=1.0,
                                      note_for=profiles.annotate, **FAST))
        self.assertEqual(rows[0].note, "+12 V rail unregulated")
        self.assertEqual(rows[1].note, "")

    def test_hook_columns_reach_the_csv(self):
        with supply() as psu:
            rows = run(psu, SweepPlan(points=[12.0, 13.0], current_limit=1.0, **FAST),
                       hook=lambda point, _psu: {"vout_mv": point.index * 100})
        buffer = io.StringIO()
        write_csv(rows, buffer, meta={"note": "unit test"})
        text = buffer.getvalue()
        header = [line for line in text.splitlines() if not line.startswith("#")][0]
        self.assertTrue(header.endswith("vout_mv"))
        self.assertIn("# note     unit test", text)

    def test_csv_carries_the_run_parameters_as_comments(self):
        with supply() as psu:
            rows = run(psu, SweepPlan(points=[12.0], current_limit=1.0, **FAST))
        buffer = io.StringIO()
        write_csv(rows, buffer)
        comments = [line for line in buffer.getvalue().splitlines() if line.startswith("#")]
        self.assertTrue(any("supply sweep" in line for line in comments))
        self.assertTrue(any("command" in line for line in comments))

    def test_empty_plan_does_nothing_at_all(self):
        device = SimulatedSupply(tau=0.0)
        psu = IPS3608(LoopbackTransport(device), BENCH)
        with psu:
            self.assertEqual(run(psu, SweepPlan(points=[], current_limit=1.0, **FAST)), [])
            self.assertFalse(device.state.output_enabled)


if __name__ == "__main__":
    unittest.main()
