#!/usr/bin/env python3
"""Independently recompute full-field bounds from one archived OpenFOAM checkpoint."""
import argparse
import gzip
import json
import math
import re
from pathlib import Path

import numpy as np

ap = argparse.ArgumentParser()
ap.add_argument("checkpoint", type=Path, help="directory of native *.gz fields")
ap.add_argument("--cp", type=float, default=1004.685)
ap.add_argument("--gamma", type=float, default=1.4)
args = ap.parse_args()
number = r"[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?"

def internal(name, comp):
    text = gzip.decompress((args.checkpoint / f"{name}.gz").read_bytes()).decode("ascii")
    m = re.search(r"internalField\s+nonuniform\s+List<\w+>\s+(\d+)\s*\((.*?)\)\s*;", text, re.S)
    if not m:
        raise ValueError(f"could not parse {name} internalField")
    count = int(m.group(1))
    vals = np.asarray([float(v) for v in re.findall(number, m.group(2))], dtype=np.float64)
    if len(vals) != count * comp:
        raise ValueError(f"{name}: got {len(vals)} values for {count} cells x {comp}")
    return vals.reshape((count, comp)) if comp > 1 else vals

T = internal("T", 1)
U = internal("U", 3)
p = internal("p", 1)
rho = internal("rho", 1)
if not (len(T) == len(U) == len(p) == len(rho)):
    raise ValueError("field cell counts do not match")
speed = np.linalg.norm(U, axis=1)
tt = T + speed * speed / (2 * args.cp)
mach = speed / np.sqrt(args.gamma * p / rho)
payload = {
    "checkpoint": args.checkpoint.name,
    "cells": int(len(T)),
    "cp_J_kgK": args.cp,
    "gamma": args.gamma,
    "maxTotalTemperatureK": float(tt.max()),
    "maxTotalTemperatureCell": int(tt.argmax()),
    "maxMach": float(mach.max()),
    "maxMachCell": int(mach.argmax()),
    "maxSpeedMps": float(speed.max()),
    "minTemperatureK": float(T.min()),
    "maxTemperatureK": float(T.max()),
    "minPressurePa": float(p.min()),
    "maxPressurePa": float(p.max()),
    "minDensityKgM3": float(rho.min()),
    "maxDensityKgM3": float(rho.max()),
    "finiteAndPositive": bool(np.isfinite(T).all() and np.isfinite(U).all() and np.isfinite(p).all() and np.isfinite(rho).all() and (p > 0).all() and (rho > 0).all() and (T > 0).all()),
}
print(json.dumps(payload, indent=2))
