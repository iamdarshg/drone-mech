from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[2] / "phase15" / "optimization" / "phase15_wing_load_stress_gate.py"
SPEC = importlib.util.spec_from_file_location("phase15_wing_load_stress_gate", SCRIPT)
assert SPEC and SPEC.loader
gate = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(gate)


class WingLoadStressGateTests(unittest.TestCase):
    def test_load_demand_and_safety_factor_scaling(self) -> None:
        result = gate.calculate()
        self.assertAlmostEqual(result["inputs"]["dynamicPressurePa"], 18180.0)
        cases = result["loadCases"]
        self.assertAlmostEqual(cases[0]["rootBendingMomentNm"], 3.9409816433)
        self.assertAlmostEqual(cases[2]["rootBendingMomentNm"], 3 * cases[0]["rootBendingMomentNm"])
        sensitivity = cases[0]["requiredSectionModulusSensitivity"]
        self.assertAlmostEqual(sensitivity[0]["requiredSectionModulusMm3"], 78.819632866)
        self.assertEqual(sensitivity[0]["status"], "ILLUSTRATIVE_ONLY; no sourced laminate allowable")

    def test_gate_cannot_claim_structural_acceptance(self) -> None:
        result = gate.calculate()
        self.assertIn("BLOCKED", result["status"])
        self.assertIn("no actual stress", result["gate"])
        self.assertEqual(result["inputs"]["loadFactorCasesG"], [1.0, 2.0, 3.0])
        self.assertTrue(all(len(source["sha256"]) == 64 for source in result["sources"]))
        self.assertEqual(len(result["sources"]), 8)
        self.assertIn("issue4_material_matrix_stockfix_ff670.md", result["materialsAuditEvidence"]["report"])

    def test_changed_pinned_input_fails_closed(self) -> None:
        relative_path, _ = next(iter(gate.PINNED_SOURCE_SHA256.items()))
        with self.assertRaisesRegex(gate.SourceIntegrityError, "pinned source drift"):
            gate.verify_source(gate.REPO / relative_path, relative_path, "0" * 64)


if __name__ == "__main__":
    unittest.main()
