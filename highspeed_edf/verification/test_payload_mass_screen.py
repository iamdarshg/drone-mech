import json
import tempfile
import unittest
from pathlib import Path

from highspeed_edf.verification.payload_mass_screen import compute, load_inputs

ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT / "highspeed_edf/phase15/configs/payload_mass_screen_sources.json"


class PayloadMassScreenTests(unittest.TestCase):
    def test_source_pinned_scenarios_and_mass_budget(self):
        manifest, rows = load_inputs(ROOT, MANIFEST)
        result = compute(manifest, rows)
        self.assertEqual(result["evidence_status"], "SCREENING_ONLY_BLOCKED_FOR_INSTALLATION")
        self.assertAlmostEqual(result["baseline_mass_kg"], 6.540621725977449, places=10)
        self.assertAlmostEqual(result["non_payload_mass_kg"], result["baseline_mass_kg"] - 1.0, places=10)
        self.assertEqual(len(result["scenarios"]), 3)
        self.assertAlmostEqual(result["scenarios"][0]["combined_payload_mass_kg"], 0.056)
        self.assertAlmostEqual(result["scenarios"][0]["payload_mass_change_vs_legacy_kg"], -0.944)
        self.assertAlmostEqual(result["scenarios"][-1]["combined_payload_mass_kg"], 1.0)
        self.assertAlmostEqual(result["scenarios"][-1]["total_mass_kg"], result["baseline_mass_kg"])
        self.assertTrue(any("fit" in gate for gate in result["blocked_gates"]))

    def test_stale_source_pin_rejected(self):
        manifest = json.loads(MANIFEST.read_text())
        manifest["baseline"]["mass_csv_sha256"] = "0" * 64
        with tempfile.TemporaryDirectory() as temp:
            temporary_root = Path(temp)
            (temporary_root / "highspeed_edf/deliverables/phase15_geometry/reports").mkdir(parents=True)
            (temporary_root / "highspeed_edf/phase15/optimization").mkdir(parents=True)
            original = ROOT / manifest["baseline"]["mass_csv"]
            target = temporary_root / manifest["baseline"]["mass_csv"]
            target.write_bytes(original.read_bytes())
            generator = ROOT / manifest["baseline"]["generator"]
            (temporary_root / manifest["baseline"]["generator"]).write_bytes(generator.read_bytes())
            manifest_path = temporary_root / "inputs.json"
            manifest_path.write_text(json.dumps(manifest))
            with self.assertRaisesRegex(ValueError, "source pin mismatch"):
                load_inputs(temporary_root, manifest_path)


if __name__ == "__main__":
    unittest.main()
