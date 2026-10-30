#!/bin/bash
# Download the pinned Debian packages and extract them without root.
set -euo pipefail
ROOT="${OPENFOAM_ROOT:?Set OPENFOAM_ROOT to a writable extraction directory}"
mkdir -p "$ROOT/packages"
BASE=https://snapshot.debian.org/archive/debian/20260925T181338Z/pool/main/o/openfoam
curl -fL "$BASE/libopenfoam_1912.200626-3+b1_amd64.deb" -o "$ROOT/packages/libopenfoam.deb"
curl -fL "$BASE/openfoam_1912.200626-3+b1_amd64.deb" -o "$ROOT/packages/openfoam.deb"
echo '3ee623d08b2eb38caa06aa1bf608f7df83ef858d79fe010a70be70089a046ce6  '"$ROOT/packages/libopenfoam.deb" | sha256sum -c -
echo '79959979587cae196dc92024e97501dc244768e1a36d75858776cb1fd49d386c  '"$ROOT/packages/openfoam.deb" | sha256sum -c -
dpkg-deb -x "$ROOT/packages/libopenfoam.deb" "$ROOT"
dpkg-deb -x "$ROOT/packages/openfoam.deb" "$ROOT"
