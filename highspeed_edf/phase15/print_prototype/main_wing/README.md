# Phase 15 wing segmentation prototype

These 15 STEP pieces are experimental planar partitions of the existing wing
sectors, not print-ready or flight-ready parts. They contain no joining features,
spar design, clearances, material selection, slicer settings, or structural
validation. The source revision and source/output SHA-256 hashes are recorded in
`segmentation_manifest.json`; the source revision identifies the CAD inputs,
not the current repository head.

Each exported piece was reimported as a valid solid and its axis-aligned extents
are below 180 mm. One segment also has a successful OrcaSlicer 2.4.2 software
slice under provisional A1 mini and Bambu PLA Basic profile assumptions. The
slice does not qualify adhesion, orientation suitability, supports, accuracy,
printing, assembly, or strength. The partition volume check does not claim a
fused reconstruction.

The software screen and one STEP-to-STL exchange export are documented in
[`manufacturing-software-screen.md`](manufacturing-software-screen.md). A software
slice was completed for one segment; no physical print or CAM path generation
was performed.

Regenerate from the repository root with Python, CadQuery 2.7.0, OCP 7.8.1.1,
and Matplotlib 3.10.8:

```sh
python highspeed_edf/phase15/optimization/phase15_wing_print_segmentation.py
```
