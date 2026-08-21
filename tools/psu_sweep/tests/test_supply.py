"""Driver behaviour against the simulator: limits, confirmation, safe exit."""
import unittest

from psu_sweep import profiles
from psu_sweep.simulator import SimulatedSupply
from psu_sweep.supply import (IPS3608, Limits, LimitError, ProtectionTripped,
                              SupplyError, connect_simulated)
from psu_sweep.transport import LoopbackTransport

BENCH = Limits(0.0, 36.0, 8.0, "test bench")


class TestLimits(unittest.TestCase):
    def test_over_voltage_is_refused_before_anything_is_sent(self):
        device = SimulatedSupply()
        psu = IPS3608(LoopbackTransport(device), profiles.SHUNT_AMP_AUX).open()
        sent = len(device.received)
        with self.assertRaises(LimitError):
            psu.set_voltage(16.0)
        self.assertEqual(len(device.received), sent, "a refused setpoint must not reach the wire")
        psu.close()

    def test_under_voltage_is_refused_too(self):
        with connect_simulated(profiles.SHUNT_AMP_AUX) as psu:
            with self.assertRaises(LimitError):
                psu.set_voltage(12.0)

    def test_the_rationale_is_quoted_in_the_error(self):
        with connect_simulated(profiles.SHUNT_AMP_AUX) as psu:
            with self.assertRaises(LimitError) as caught:
                psu.set_voltage(20.0)
        self.assertIn("Rel1", str(caught.exception))

    def test_current_limit_is_bounded(self):
        with connect_simulated(profiles.SHUNT_AMP_AUX) as psu:
            with self.assertRaises(LimitError):
                psu.set_current(2.0)


class TestDriver(unittest.TestCase):
    def test_setpoints_take_and_read_back(self):
        with connect_simulated(BENCH) as psu:
            psu.set_current(1.5)
            psu.set_voltage(15.0)
            state = psu.refresh()
            self.assertAlmostEqual(state.set_voltage, 15.0, places=3)
            self.assertAlmostEqual(state.set_current, 1.5, places=3)

    def test_output_reaches_the_setpoint(self):
        with connect_simulated(BENCH, tau=0.0) as psu:
            psu.set_current(1.0)
            psu.set_voltage(15.0)
            psu.set_output(True)
            reading = psu.measure(samples=4, interval=0.01)
            self.assertAlmostEqual(reading.voltage, 15.0, delta=0.05)
            self.assertTrue(reading.output_enabled)
            self.assertEqual(reading.mode, "CV")

    def test_current_limit_forces_cc(self):
        # 15 V into 750 ohms wants 20 mA; allow 10 and the supply must fold back.
        with connect_simulated(BENCH, tau=0.0) as psu:
            psu.set_current(0.010)
            psu.set_voltage(15.0)
            psu.set_output(True)
            reading = psu.measure(samples=3, interval=0.01)
            self.assertEqual(reading.mode, "CC")
            self.assertLess(reading.voltage, 15.0)

    def test_averaging_reports_the_spread(self):
        with connect_simulated(BENCH, tau=0.0, noise_v=0.05) as psu:
            psu.set_current(1.0)
            psu.set_voltage(12.0)
            psu.set_output(True)
            reading = psu.measure(samples=6, interval=0.01)
            self.assertEqual(reading.samples, 6)
            self.assertGreater(reading.voltage_spread, 0.0)

    def test_a_deaf_supply_raises_rather_than_hanging(self):
        with self.assertRaises(SupplyError):
            connect_simulated(BENCH, deaf=True, timeout=0.2).open()

    def test_context_manager_switches_the_output_off_on_the_way_out(self):
        device = SimulatedSupply(tau=0.0)
        psu = IPS3608(LoopbackTransport(device), BENCH)
        with psu:
            psu.set_current(1.0)
            psu.set_voltage(12.0)
            psu.set_output(True)
            self.assertTrue(psu.refresh().output_enabled)
        self.assertFalse(device.state.output_enabled)

    def test_output_is_switched_off_even_when_the_body_raises(self):
        device = SimulatedSupply(tau=0.0)
        psu = IPS3608(LoopbackTransport(device), BENCH)
        with self.assertRaises(ZeroDivisionError):
            with psu:
                psu.set_current(1.0)
                psu.set_voltage(12.0)
                psu.set_output(True)
                raise ZeroDivisionError("something went wrong mid-sweep")
        self.assertFalse(device.state.output_enabled)

    def test_a_trip_is_reported_as_a_trip_not_as_a_lost_frame(self):
        device = SimulatedSupply(tau=0.0)
        device.state.ovp = 10.0
        psu = IPS3608(LoopbackTransport(device), BENCH, write_retries=1, timeout=0.3)
        with psu:
            psu.set_current(1.0)
            psu.set_voltage(12.0)
            with self.assertRaises(ProtectionTripped) as caught:
                psu.set_output(True)
            self.assertEqual(psu.state.protection_label, "OVP")
        self.assertIn("OVP", str(caught.exception))


if __name__ == "__main__":
    unittest.main()
