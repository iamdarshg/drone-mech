import importlib.util
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "optimization" / "phase15_servo_torque_screen.py"
spec = importlib.util.spec_from_file_location("servo_screen", SCRIPT)
servo_screen = importlib.util.module_from_spec(spec)
spec.loader.exec_module(servo_screen)


class ServoTorqueScreenTests(unittest.TestCase):
    def test_hinge_torque_definition_and_linear_sensitivity(self):
        base = servo_screen.hinge_torque(1000.0, 0.01, 0.1, 0.1)
        self.assertAlmostEqual(base, 0.1)
        self.assertAlmostEqual(servo_screen.hinge_torque(1000, 0.01, 0.1, 0.2), 2 * base)

    def test_pinned_inputs_cover_anchor_speeds_and_full_requested_envelope(self):
        rows, summary = servo_screen.generate()
        self.assertIn(900, summary["indicated_speeds_kmh"])
        self.assertEqual(set(summary["phase14_anchor_ias_kmh"]), {50, 100, 150, 200, 500, 650, 700, 720})
        self.assertTrue(set(range(50, 901, 50)).issubset(summary["indicated_speeds_kmh"]))
        self.assertEqual(summary["rows"], len(rows))

    def test_mach_and_vane_velocity_sensitivity_are_explicit(self):
        rows, summary = servo_screen.generate()
        self.assertAlmostEqual(summary["environments"]["primary_design_altitude"]["density_kg_m3"], 0.90913, delta=0.002)
        self.assertGreater(next(r["freestream_mach"] for r in rows if r["indicated_airspeed_kmh"] == 900 and r["environment"] == "primary_design_altitude"), 0.7)
        vane_q = {r["local_velocity_ratio"]: r["local_q_pa"] for r in rows
                  if r["indicated_airspeed_kmh"] == 500 and r["environment"] == "primary_design_altitude" and r["surface"] == "vector_vane_A1" and r["hinge_coefficient_scenario"] == 0.1}
        self.assertAlmostEqual(vane_q[2.0], 4 * vane_q[1.0])
        self.assertAlmostEqual(vane_q[4.0], 16 * vane_q[1.0])

    def test_indicated_speed_conversion_is_consistent_at_both_altitudes(self):
        sea_level = servo_screen.isa_atmosphere(0.0)
        primary = servo_screen.isa_atmosphere(3000.0)
        ias = 900 / 3.6
        sea_mach = servo_screen.cas_to_mach(ias, sea_level[1])
        high_mach = servo_screen.cas_to_mach(ias, primary[1])
        self.assertGreater(high_mach, sea_mach)
        self.assertAlmostEqual(sea_mach, 0.7347, delta=0.001)
        self.assertAlmostEqual(high_mach, 0.8618, delta=0.001)
        self.assertAlmostEqual(900.0, sea_mach * (servo_screen.GAMMA_AIR * servo_screen.R_AIR * sea_level[0]) ** 0.5 * 3.6, delta=0.1)
        with self.assertRaises(ValueError):
            servo_screen.cas_to_mach(1200 / 3.6, primary[1])
        self.assertGreater(primary[2], 0.90)
        self.assertLess(primary[2], 0.92)

    def test_absent_servo_selection_is_reported_as_blocked(self):
        _, summary = servo_screen.generate()
        self.assertIn("BLOCKED", summary["actual_servo_comparison"])
        self.assertIsNone(servo_screen.check_pins()["manufacturer_servo_source"])
        self.assertEqual(summary["actuator_count"], 7)
        self.assertEqual(list(summary["servo_placeholder_envelope_mm"]), [23.0, 12.0, 29.0])


if __name__ == "__main__":
    unittest.main()
