"""Framing, checksums and state decoding. No hardware, no pyserial."""
import struct
import unittest

from psu_sweep import protocol as pr


class TestEncoding(unittest.TestCase):
    def test_documented_example(self):
        # The one worked example in the community protocol notes: setting
        # 5.0 V must produce this exact frame, checksum 0xA4.
        self.assertEqual(
            pr.set_voltage(5.0).hex(" "),
            "f1 b0 c0 04 00 00 a0 40 a4",
        )

    def test_checksum_excludes_cmd_type(self):
        a = pr.encode(pr.CmdType.READ, 0x42, b"\x01")
        b = pr.encode(pr.CmdType.WRITE_BYTE, 0x42, b"\x01")
        self.assertEqual(a[-1], b[-1])

    def test_output_frames(self):
        self.assertEqual(pr.set_output(True)[-2], 1)
        self.assertEqual(pr.set_output(False)[-2], 0)

    def test_payload_length_is_bounded(self):
        with self.assertRaises(pr.ProtocolError):
            pr.encode(pr.CmdType.READ, 0x00, b"\x00" * 256)

    def test_baud_must_be_supported(self):
        with self.assertRaises(pr.ProtocolError):
            pr.set_baud(4800)


def response(register, data, cmd_type=pr.CmdType.READ):
    """A device-to-host frame carrying `data`."""
    frame = bytearray(pr.encode(cmd_type, register, data))
    frame[0] = pr.HEADER_RESPONSE
    return bytes(frame)


class TestParsing(unittest.TestCase):
    def test_round_trip(self):
        buffer = bytearray(response(pr.Reg.SET_VOLTAGE, struct.pack("<f", 14.9)))
        frames = list(pr.parse_frames(buffer))
        self.assertEqual(len(frames), 1)
        self.assertAlmostEqual(frames[0].as_float(), 14.9, places=4)
        self.assertEqual(len(buffer), 0)

    def test_partial_frame_is_left_in_the_buffer(self):
        whole = response(pr.Reg.TEMPERATURE, struct.pack("<f", 31.0))
        buffer = bytearray(whole[:-1])
        self.assertEqual(list(pr.parse_frames(buffer)), [])
        buffer.extend(whole[-1:])
        self.assertEqual(len(list(pr.parse_frames(buffer))), 1)

    def test_resynchronises_after_garbage(self):
        buffer = bytearray(b"\x11\x22\x33" + response(pr.Reg.TEMPERATURE, struct.pack("<f", 31.0)))
        frames = list(pr.parse_frames(buffer))
        self.assertEqual(len(frames), 1)
        self.assertAlmostEqual(frames[0].as_float(), 31.0, places=4)

    def test_bad_checksum_is_dropped_and_the_next_frame_survives(self):
        good = response(pr.Reg.TEMPERATURE, struct.pack("<f", 31.0))
        bad = bytearray(good)
        bad[-1] ^= 0xFF
        buffer = bytearray(bytes(bad) + good)
        frames = list(pr.parse_frames(buffer))
        self.assertEqual(len(frames), 1)

    def test_two_frames_in_one_read(self):
        buffer = bytearray(
            response(pr.Reg.TEMPERATURE, struct.pack("<f", 31.0))
            + response(pr.Reg.SET_VOLTAGE, struct.pack("<f", 12.0))
        )
        self.assertEqual(len(list(pr.parse_frames(buffer))), 2)


class TestState(unittest.TestCase):
    def test_all_dump_round_trips(self):
        source = pr.DeviceState(
            input_voltage=232.0, set_voltage=14.9, set_current=0.1,
            output_voltage=14.87, output_current=0.021, output_power=0.312,
            temperature=28.5, max_voltage=36.0, max_current=8.0,
            output_enabled=True, mode=int(pr.Mode.CC), protection=int(pr.Protection.OK),
            presets=[(5.0, 1.0), (12.0, 2.0)],
        )
        buffer = bytearray(response(pr.Reg.ALL, pr.encode_all(source)))
        decoded = pr.DeviceState()
        for frame in pr.parse_frames(buffer):
            pr.apply(frame, decoded)

        for field in ("set_voltage", "output_voltage", "output_current", "temperature",
                      "max_voltage", "max_current"):
            self.assertAlmostEqual(getattr(decoded, field), getattr(source, field), places=3,
                                   msg=field)
        self.assertTrue(decoded.output_enabled)
        self.assertEqual(decoded.mode_label, "CC")
        self.assertEqual(decoded.presets[:2], [(5.0, 1.0), (12.0, 2.0)])

    def test_output_flag_polarity_matches_the_documented_convention(self):
        payload = pr.encode_all(pr.DeviceState(output_enabled=True))
        offset = dict((name, off) for name, off, _ in pr.ALL_LAYOUT)["_output_flag"]
        self.assertEqual(payload[offset], 0 if pr.OUTPUT_FLAG_ACTIVE_LOW else 1)

    def test_nan_readings_do_not_poison_state(self):
        state = pr.DeviceState(output_voltage=14.9)
        pr.apply(pr.Frame(pr.CmdType.READ, pr.Reg.SET_VOLTAGE,
                          struct.pack("<f", float("nan"))), state)
        self.assertEqual(state.set_voltage, 0.0)

    def test_unknown_register_is_recorded_not_swallowed(self):
        state = pr.DeviceState()
        pr.apply(pr.Frame(pr.CmdType.READ, 0x5A, b"\x00"), state)
        self.assertIn(0x5A, state.unknown_registers)

    def test_protection_and_mode_labels(self):
        self.assertEqual(pr.DeviceState(protection=2).protection_label, "OCP")
        self.assertTrue(pr.DeviceState(protection=2).in_protection)
        self.assertEqual(pr.DeviceState(protection=99).protection_label, "?99")


if __name__ == "__main__":
    unittest.main()
