#!/usr/bin/env python3
"""Reconstruct the sensible-enthalpy internal field from saved rhoCentralFoam T.

rhoCentralFoam did not write `h` at the guarded checkpoint.  This utility
preserves T as native output and emits h_from_T as an explicitly derived
cross-check using the case's constant Cp=1004.685 J/(kg K); it does not
represent an independently written solver field.
"""
from pathlib import Path
import gzip
import re

HERE = Path(__file__).resolve().parent
CP = 1004.685
src = HERE / "checkpoint_2.6249203e-06" / "T.gz"
out = HERE / "checkpoint_2.6249203e-06" / "h_from_T.gz"
text = gzip.decompress(src.read_bytes()).decode("ascii")
m = re.search(r"internalField\s+nonuniform\s+List<scalar>\s+(\d+)\s*\((.*?)\)\s*;", text, re.S)
if not m:
    raise SystemExit("could not parse native T internalField")
count = int(m.group(1))
values = [float(x) for x in re.findall(r"[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?", m.group(2))]
if len(values) != count:
    raise SystemExit(f"temperature count mismatch: declared {count}, parsed {len(values)}")
enthalpy = [CP * t for t in values]
payload = (
    "FoamFile\n{ version 2.0; format ascii; class volScalarField; "
    'location "2.6249203e-06"; object h_from_T; }\n'
    "dimensions [0 2 -2 0 0 0 0];\n"
    f"internalField nonuniform List<scalar>\n{count}\n(\n"
    + "\n".join(f"{x:.12g}" for x in enthalpy)
    + "\n)\n;\n"
)
out.write_bytes(gzip.compress(payload.encode("ascii"), compresslevel=9, mtime=0))
print(f"wrote {out.name}: {count} cells; h = {CP} * T; min/max {min(enthalpy):.9f}/{max(enthalpy):.9f} J/kg")
