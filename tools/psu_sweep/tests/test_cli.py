"""Command line: argument handling and the paths that refuse to energise."""
import contextlib
import io
import re
import unittest

from psu_sweep import cli


def run_cli(*argv):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = cli.main(list(argv))
    return code, out.getvalue(), err.getvalue()


class TestArguments(unittest.TestCase):
    def test_explicit_points_override_start_stop_step(self):
        args = cli.build_parser().parse_args(
            ["sweep", "--points", "13,14.9,15.6", "--start", "1", "--stop", "2"])
        self.assertEqual(cli.sweep_points(args), [13.0, 14.9, 15.6])

    def test_sweep_defaults_to_the_board_envelope(self):
        args = cli.build_parser().parse_args(["sweep"])
        points = cli.sweep_points(args)
        self.assertEqual((points[0], points[-1]), (13.0, 15.6))

    def test_list_prints_the_points_without_touching_a_supply(self):
        code, out, _ = run_cli("sweep", "--list", "--step", "0.5")
        self.assertEqual(code, 0)
        self.assertIn("13.000 V", out)
        self.assertIn("+12 V rail unregulated", out)


class TestRefusals(unittest.TestCase):
    def test_no_port_and_no_simulate_is_an_error_not_a_guess(self):
        code, _, err = run_cli("status")
        self.assertEqual(code, 1)
        self.assertIn("--port", err)

    def test_a_setpoint_outside_the_envelope_exits_two(self):
        code, _, err = run_cli("--simulate", "set", "--volts", "20")
        self.assertEqual(code, 2)
        self.assertIn("outside", err)

    def test_bench_profile_allows_what_the_board_profile_refuses(self):
        code, out, _ = run_cli("--simulate", "--profile", "bench", "set", "--volts", "20")
        self.assertEqual(code, 0)
        self.assertIn("20.000 V", out)


class TestSimulatedRun(unittest.TestCase):
    def test_a_short_sweep_runs_end_to_end(self):
        code, out, _ = run_cli("--simulate", "sweep", "--points", "13,15,15.6",
                               "--dwell", "0", "--samples", "1", "--sample-interval", "0")
        self.assertEqual(code, 0)
        rows = [line for line in out.splitlines() if re.match(r"\s+\d+\s+1[35]\.", line)]
        self.assertEqual(len(rows), 3)
        self.assertIn("+12 V rail unregulated", out)

    def test_status_reports_the_simulated_supply(self):
        code, out, _ = run_cli("--simulate", "status")
        self.assertEqual(code, 0)
        self.assertIn("setpoint", out)
        self.assertIn("protection", out)


if __name__ == "__main__":
    unittest.main()
