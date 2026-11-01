#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/../../../.." && pwd)"
cd "$ROOT"
LOG="$SCRIPT_DIR/execution.log"
{
  echo "Buildability subset run $(date -u +%Y-%m-%dT%H:%M:%SZ)"
  freecadcmd --version 2>&1 | sed 's/[[:space:]]*$//'
  echo "[1/5] Import all 25 wing/fuselage STEP parts, compare tessellated extents"
  QT_QPA_PLATFORM=offscreen freecadcmd highspeed_edf/phase15/reports/cam_buildability_screen/build_cad_extent_screen.FCMacro
  echo "[2/5] Reopen and verify the 6 mm rotor FreeCAD Path job"
  QT_QPA_PLATFORM=offscreen freecadcmd highspeed_edf/phase15/reports/cam_6mm_stock_probe/verify_saved_job.FCMacro
  echo "[3/5] Reopen and verify the 6 mm stator FreeCAD Path job"
  QT_QPA_PLATFORM=offscreen freecadcmd highspeed_edf/phase15/reports/cam_6mm_stator_probe/verify_saved_job.FCMacro
  echo "[4/5] Check the retained planar toolpath envelopes"
  python highspeed_edf/phase15/reports/cam_6mm_stock_probe/stock_envelope_check.py
  python highspeed_edf/phase15/reports/cam_6mm_stator_probe/stock_envelope_check.py
  echo "[5/5] Verify source pins and reach arithmetic"
  python highspeed_edf/phase15/reports/cam_buildability_screen/check_buildability_screen.py
  echo "All software-only checks passed; no machine or printer was operated."
} >"$LOG" 2>&1
cat "$LOG"
