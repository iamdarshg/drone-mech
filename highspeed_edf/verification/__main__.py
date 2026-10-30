"""Cross-repository acceptance entry point for drone-mech issue #14."""
from __future__ import annotations

import argparse
import html
import json
import os
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

HERE = Path(__file__).resolve().parent
MECH = HERE.parents[1]
ARM = MECH.parent / "drone-arm"
EVIDENCE = HERE / "evidence"
PROFILE_MAP = {"cad-smoke": "cad", "native-aero": "native-aero", "fsi": "fsi",
               "integration": "all", "cad-material": "cad", "cad-manufacture": "cad"}
CUSTOM_MODE = {"cad-material": "materials", "cad-manufacture": "manufacture"}
CORE_PROFILES = {"smoke", "cad", "pcb", "software", "thermal", "power", "aero", "fsi", "all", "native-aero", "native-fsi"}


def _native_check(profile: str) -> dict:
    mode = CUSTOM_MODE[profile]
    out = EVIDENCE / f"{profile}.json"
    generator = MECH / "highspeed_edf/phase15/optimization/phase15_generate_geometry.py"
    csv = MECH / "highspeed_edf/deliverables/phase15_geometry/reports/mass_cg.csv"
    geometry = MECH / "highspeed_edf/deliverables/phase15_geometry"
    executable = os.environ.get("CADQUERY_PYTHON", sys.executable)
    command = [executable, "-m", "highspeed_edf.verification.native_adapters", "--mode", mode,
               "--geometry-dir", str(geometry), "--generator", str(generator), "--mass-csv", str(csv), "--output", str(out)]
    env = dict(os.environ); env["PYTHONPATH"] = str(MECH) + os.pathsep + str(ARM) + os.pathsep + env.get("PYTHONPATH", "")
    probe = subprocess.run([executable, "-c", "import cadquery, importlib.metadata"], capture_output=True, text=True, env=env)
    if probe.returncode:
        return {"id": "MECH-MATERIAL-001" if mode == "materials" else "MECH-MANUFACTURE-001",
                "status": "BLOCKED", "command": command, "errors": [f"CadQuery unavailable (exit {probe.returncode}): {probe.stderr.strip()}"],
                "artifact_paths": [], "artifact_sha256": None}
    run = subprocess.run(command, capture_output=True, text=True, env=env)
    if not out.is_file():
        return {"id": "MECH-MATERIAL-001" if mode == "materials" else "MECH-MANUFACTURE-001",
                "status": "FAIL" if run.returncode else "BLOCKED", "command": command,
                "errors": [f"native adapter emitted no evidence (exit {run.returncode}): {run.stderr.strip()}"],
                "artifact_paths": [], "artifact_sha256": None}
    data = json.loads(out.read_text())
    import hashlib
    return {"id": "MECH-MATERIAL-001" if mode == "materials" else "MECH-MANUFACTURE-001",
            "status": data.get("status", "BLOCKED"), "measured": data,
            "command": command, "errors": data.get("errors", []),
            "artifact_paths": [str(out)], "artifact_sha256": hashlib.sha256(out.read_bytes()).hexdigest(),
            "tool_versions": data.get("tool_versions", {})}


def _render(report: dict, json_path=None, junit_path=None, html_path=None):
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    blob = json.dumps(report, indent=2, sort_keys=True, allow_nan=False) + "\n"
    dest = Path(json_path) if json_path else EVIDENCE / "last_run.json"
    dest.parent.mkdir(parents=True, exist_ok=True); dest.write_text(blob)
    rows = report["results"]
    if junit_path:
        suite = ET.Element("testsuite", tests=str(len(rows)), failures=str(sum(x["status"] == "FAIL" for x in rows)),
                           skipped=str(sum(x["status"] in ("BLOCKED", "NOT_RUN", "NOT_APPLICABLE") for x in rows)))
        for row in rows:
            case = ET.SubElement(suite, "testcase", classname="engineering_acceptance", name=row["id"])
            if row["status"] == "FAIL": ET.SubElement(case, "failure", message="FAIL").text = "; ".join(row.get("errors", []))
            elif row["status"] in ("BLOCKED", "NOT_RUN", "NOT_APPLICABLE"): ET.SubElement(case, "skipped", message=row["status"]).text = "; ".join(row.get("errors", []))
        p = Path(junit_path); p.parent.mkdir(parents=True, exist_ok=True); p.write_bytes(ET.tostring(suite, encoding="utf-8", xml_declaration=True))
    if html_path:
        table = "".join("<tr>" + "".join("<td>" + html.escape(json.dumps(row.get(k), sort_keys=True) if isinstance(row.get(k), (dict, list)) else str(row.get(k, ""))) + "</td>" for k in ("id", "status", "measured", "errors", "artifact_paths", "artifact_sha256")) + "</tr>" for row in rows)
        p = Path(html_path); p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("<!doctype html><meta charset='utf-8'><title>Mech acceptance</title><h1>Issue 14 native acceptance</h1><p>Not a manufacturing release or flight approval.</p><table><thead><tr><th>ID</th><th>Status</th><th>Measured</th><th>Errors</th><th>Evidence</th><th>SHA-256</th></tr></thead><tbody>"+table+"</tbody></table>")
    return str(dest)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="python -m highspeed_edf.verification")
    sub = parser.add_subparsers(dest="command", required=True)
    run = sub.add_parser("run"); run.add_argument("--profile", required=True); run.add_argument("--config", type=Path, default=ARM / "engineering_acceptance/config.yaml")
    run.add_argument("--json"); run.add_argument("--junit"); run.add_argument("--html")
    report = sub.add_parser("report"); report.add_argument("--json"); report.add_argument("--junit"); report.add_argument("--html")
    args = parser.parse_args(argv)
    if ARM.is_dir(): sys.path.insert(0, str(ARM))
    from engineering_acceptance.core import run as run_acceptance, latest_run
    if args.command == "report":
        latest=EVIDENCE/"last_run.json"
        if latest.is_file():
            report_data=json.loads(latest.read_text())
        else:
            rows=latest_run()
            if not rows: print("no acceptance run exists",file=sys.stderr); return 2
            report_data={"profile":rows[-1].get("profile"),"results":rows,"checks_attempted":len(rows),"notice":"Not a manufacturing release or flight approval."}
        print(_render(report_data,args.json,args.junit,args.html)); return 0
    profile=args.profile
    if profile not in PROFILE_MAP and profile not in CORE_PROFILES:
        parser.error("profile must be one of cad-smoke, native-aero, fsi, integration, cad-material, cad-manufacture or a registered core profile")
    core_profile=PROFILE_MAP.get(profile,profile)
    core=run_acceptance(core_profile,args.config)
    if profile in CUSTOM_MODE: core["results"].append(_native_check(profile))
    counts={s:sum(x["status"]==s for x in core["results"]) for s in ("PASS","FAIL","BLOCKED","NOT_RUN","NOT_APPLICABLE")}
    core.update(profile=profile,counts=counts,checks_attempted=len(core["results"]))
    print("wrote",_render(core,args.json,args.junit,args.html))
    for row in core["results"]:
        print(f"{row['status']:16} {row['id']}: {'; '.join(row.get('errors',[]))}")
    return 1 if any(x["status"] in ("FAIL","BLOCKED","NOT_RUN") for x in core["results"] if x.get("blocking",True)) else 0

if __name__ == "__main__": raise SystemExit(main())
