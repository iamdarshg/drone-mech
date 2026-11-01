# A1 mini slicer subset: wing and fuselage shell

This is a reproducible **software-only slice review** of two exact, hash-pinned STEP parts. OrcaSlicer 2.4.2 completed both jobs using the repository's saved A1 mini 0.4 mm nozzle, 0.20 mm Standard, Bambu PLA Basic and Textured PEI profile. The physical printer configuration and chosen material/plate have not been confirmed. These G-code files are evidence of slicer execution, not production files or approval to print.

## Inputs and results

| Part | Exact STEP source SHA-256 | Converted STL bounds (mm) | Slice outcome |
|---|---|---:|---|
| `wing_left_sector_x1_z1` | `569157a7ad28a5942300d0cf818770f2e48c7a08fc240d316e3ce59135399f42` | 89.835 × 37.739 × 123.185 | Success; 615 layers; 2h 17m model / 2h 23m total estimate; no slicer warning |
| `fuselage_shell_segment_01_port` | `3bc7a9ca1cb37417d5feac6b926354317e2f41e588442fa25e766f813efed667` | 105.892 × 90.220 × 120.000 | Success; 529 layers; 2h 52m model / 2h 58m total estimate; **floating cantilever warning** |

Both slicer inputs were generated directly from the STEP source using FreeCAD 1.0.0 `MeshPart.meshFromShape` (linear deflection 0.05 mm, angular deflection 0.1 rad, relative false). The source-to-mesh hashes, solid count, triangle count, unit note and bounds are recorded in `step_mesh_conversion.json`. STL has no unit metadata; mm are inherited from STEP. Slicer reported all selected-part extents within the A1 mini profile's 180 mm cube. This is a bounding-box comparison only, not a verified print orientation or physical clearance test.

The inherited process uses 0.20 mm layers, two wall loops, 15% infill and a 5 mm brim. Neither G-code contains support feature markers; the fuselage warning remains unresolved. `slice_subset_results.json` records the actual per-part CLI result, warning, orientation candidate, layer count, times, profile hashes, output hashes and validation status. G-code hashes:

- Wing: `ce7081ffb382aed562c756bca393bf02f5078acfe1a34b665724612d8d5008fa`
- Fuselage shell: `729387510d76729c30d9c765aba808c82aeecb25969c8c6f6f76d2e6432d29da`

## Reproducing and checking

The execution used the official OrcaSlicer v2.4.2 Linux AppImage (SHA-256 `d12fb8c8eac1aecd2dfb6377acd48f994f8fa439ed5292fa532dd82880f029fd`) and Debian 13 packages from the pinned snapshot URL and exact versions/hashes in `runtime_lock.json`. Runtime libraries were extracted into a private `/tmp` prefix; no host packages were installed. The executable used was `squashfs-root/bin/orca-slicer` from the extracted AppImage. The original invocations and raw logs are preserved in `slice_subset_results.json` and `*_slicer.log`; each job loaded the three repository profile files whose SHA-256 values are listed in the result JSON, then used `--orient 1 --arrange 1 --slice 0`.

To re-check committed evidence without running CAD software or altering expected results:

```sh
python3 highspeed_edf/phase15/reports/print_subset_slice/verify_slice_evidence.py
```

For regeneration, first install/use FreeCAD 1.0.0 with the `MeshPart` module and OrcaSlicer 2.4.2 with the pinned runtime. Run `export_selected_step_to_stl.FCMacro` from the repository root, then repeat the recorded per-part CLI commands. Compare regenerated hashes and the retained warnings to the committed outputs; do not overwrite or waive a mismatch. G-code previews/logs are intentionally retained for independent inspection.

## Boundaries

No physical printer was used. Adhesion, orientation, support strategy, layer strength, shell integrity, assembly fit, material suitability, dimensional tolerance, thermal behavior and flight loads remain unverified. In particular, the slicer's fuselage floating-cantilever warning is an open defect. Neither part nor aircraft is declared build-ready, fabrication-ready or flight-ready. Do not send these G-code files to a printer as a release.
