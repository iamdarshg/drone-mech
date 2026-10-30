"""Cross-repository acceptance entry point for drone-mech issue #14."""
from __future__ import annotations

import argparse
import hashlib
import html
import json
import os
import shlex
import subprocess
import sys
from datetime import datetime, timezone
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


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _git_head(path: Path) -> str:
    result=subprocess.run(["git","-C",str(path),"rev-parse","HEAD"],capture_output=True,text=True,check=True)
    return result.stdout.strip()


def _native_check(profile: str, run_id: str, config: dict) -> dict:
    mode = CUSTOM_MODE[profile]
    out = EVIDENCE / "runs" / run_id / f"{profile}.json"
    def artifact(key, default):
        item=config.get("source_artifacts",{}).get(key)
        if not item: return default
        base=MECH if item.get("repo")=="drone-mech" else ARM
        return (base/item["path"]).resolve()
    generator = artifact("geometry_generator", MECH / "highspeed_edf/phase15/optimization/phase15_generate_geometry.py")
    csv = artifact("mass_properties", MECH / "highspeed_edf/deliverables/phase15_geometry/reports/mass_cg.csv")
    geometry_rel=config.get("cad",{}).get("step_root",{})
    if isinstance(geometry_rel,dict): geometry_rel=geometry_rel.get("value")
    geometry = MECH / geometry_rel if geometry_rel else MECH / "highspeed_edf/deliverables/phase15_geometry"
    if geometry.name=="step": geometry=geometry.parent
    executable = os.environ.get("CADQUERY_PYTHON", sys.executable)
    command = [executable, "-m", "highspeed_edf.verification.native_adapters", "--mode", mode,
               "--geometry-dir", str(geometry), "--generator", str(generator), "--mass-csv", str(csv), "--output", str(out)]
    if mode=="manufacture":
        stock=artifact("stock_nests",geometry/"stock_nests")
        command += ["--stock-dir",str(stock)]
    env = dict(os.environ); env["PYTHONPATH"] = str(MECH) + os.pathsep + str(ARM) + os.pathsep + env.get("PYTHONPATH", "")
    probe = subprocess.run([executable, "-c", "import cadquery, importlib.metadata"], capture_output=True, text=True, env=env)
    if probe.returncode:
        return {"id": "MECH-MATERIAL-001" if mode == "materials" else "MECH-MANUFACTURE-001",
                "status": "BLOCKED", "command": command, "errors": [f"CadQuery unavailable (exit {probe.returncode}): {probe.stderr.strip()}"],
                "exit_code": probe.returncode, "tool_versions": {}, "artifact_paths": [], "artifact_sha256": None}
    run = subprocess.run(command, capture_output=True, text=True, env=env)
    if not out.is_file():
        return {"id": "MECH-MATERIAL-001" if mode == "materials" else "MECH-MANUFACTURE-001",
                "status": "FAIL" if run.returncode else "BLOCKED", "command": command,
                "errors": [f"native adapter emitted no evidence (exit {run.returncode}): {run.stderr.strip()}"],
                "exit_code": run.returncode, "tool_versions": {}, "artifact_paths": [], "artifact_sha256": None}
    data = json.loads(out.read_text())
    import hashlib
    return {"id": "MECH-MATERIAL-001" if mode == "materials" else "MECH-MANUFACTURE-001",
            "status": data.get("status", "BLOCKED"), "measured": data,
            "command": command, "errors": data.get("errors", []),
            "exit_code": run.returncode, "exact_command": shlex.join([str(x) for x in command]),
            "artifact_paths": [str(out)], "artifact_sha256": hashlib.sha256(out.read_bytes()).hexdigest(),
            "tool_versions": data.get("tool_versions", {})}


def _record_mechanical_check(profile: str, row: dict, core: dict, config_path: Path) -> dict:
    """Bind non-core mechanical checks to the core run without editing its ledger."""
    run_id=core["run_id"]
    core_manifest_path=ARM/core["manifest_path"]
    core_manifest_sha=_sha(core_manifest_path)
    catalog=HERE/"catalog.json"
    source_paths=[HERE/"__main__.py",HERE/"native_adapters.py",catalog,config_path]
    if profile=="cad-material":
        source_paths += [MECH/"highspeed_edf/phase15/optimization/phase15_generate_geometry.py",
                         MECH/"highspeed_edf/deliverables/phase15_geometry/reports/mass_cg.csv"]
    else:
        source_paths += sorted((MECH/"highspeed_edf/deliverables/phase15_geometry/stock_nests").glob("*.step"))
    source_hashes={str(p):_sha(p) for p in source_paths if p.is_file()}
    row.update({"run_id":run_id,"core_manifest_path":str(core_manifest_path),
                "core_manifest_sha256":core_manifest_sha,"mechanical_catalog_sha256":_sha(catalog),
                "mechanical_source_hashes":source_hashes,"drone_mech_sha":_git_head(MECH),
                "drone_arm_sha":_git_head(ARM),"system":"twin_electric_ducted_fan_aircraft",
                "severity":"P0","applicability":"cad_material" if profile=="cad-material" else "cad_manufacture",
                "blocking":True})
    entry={"schema_version":1,"run_id":run_id,"profile":profile,"check_id":row["id"],
           "status":row["status"],"timestamp_utc":datetime.now(timezone.utc).isoformat(),
           "drone_mech_sha":row["drone_mech_sha"],"drone_arm_sha":row["drone_arm_sha"],
           "test_definition_sha256":row["mechanical_catalog_sha256"],
           "core_manifest_path":str(core_manifest_path),"core_manifest_sha256":core_manifest_sha,
           "source_hashes":source_hashes,"tool_versions":row.get("tool_versions",{}),
           "command":row.get("command"),"exact_command":row.get("exact_command"),
           "exit_code":row.get("exit_code"),"artifact_paths":row.get("artifact_paths",[]),
           "artifact_sha256":row.get("artifact_sha256"),"errors":row.get("errors",[])}
    ledger=EVIDENCE/"mechanical_evidence.jsonl"; ledger.parent.mkdir(parents=True,exist_ok=True)
    previous=None
    if ledger.is_file() and ledger.stat().st_size:
        previous=json.loads(ledger.read_text().splitlines()[-1]).get("record_sha256")
    entry["previous_record_sha256"]=previous
    canonical=json.dumps(entry,sort_keys=True,separators=(",",":"),allow_nan=False)
    entry["record_sha256"]=hashlib.sha256(canonical.encode()).hexdigest()
    manifest=EVIDENCE/"runs"/run_id/"mechanical_manifest.json"; manifest.parent.mkdir(parents=True,exist_ok=True)
    with manifest.open("x",encoding="utf-8") as f:f.write(json.dumps(entry,indent=2,sort_keys=True,allow_nan=False)+"\n")
    with ledger.open("a",encoding="utf-8") as f:f.write(json.dumps(entry,sort_keys=True,allow_nan=False)+"\n")
    row["mechanical_manifest_path"]=str(manifest)
    row["mechanical_manifest_sha256"]=_sha(manifest)
    return row


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
    run = sub.add_parser("run"); run.add_argument("--profile", required=True); run.add_argument("--config", type=Path, default=ARM / "engineering_acceptance/aircraft_system.yaml")
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
    if profile in CUSTOM_MODE:
        import yaml
        config=yaml.safe_load(args.config.read_text())
        custom=_native_check(profile,core["run_id"],config)
        core["results"].append(_record_mechanical_check(profile,custom,core,args.config))
        core["release_critical_total"] = core.get("release_critical_total",0) + 1
        core["release_critical_pass"] = core.get("release_critical_pass",0) + int(custom["status"]=="PASS")
    counts={s:sum(x["status"]==s for x in core["results"]) for s in ("PASS","FAIL","BLOCKED","NOT_RUN","NOT_APPLICABLE")}
    core.update(profile=profile,counts=counts,checks_attempted=len(core["results"]))
    print("wrote",_render(core,args.json,args.junit,args.html))
    for row in core["results"]:
        print(f"{row['status']:16} {row['id']}: {'; '.join(row.get('errors',[]))}")
    return 1 if any(x["status"] in ("FAIL","BLOCKED","NOT_RUN") for x in core["results"] if x.get("blocking",True)) else 0

if __name__ == "__main__": raise SystemExit(main())
