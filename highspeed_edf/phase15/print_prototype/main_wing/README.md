# Phase 15 wing segmentation prototype

These 15 STEP pieces are experimental planar partitions of the existing wing
sectors, not print-ready or flight-ready parts. They contain no joining features,
spar design, clearances, material selection, slicer settings, or structural
validation. The source revision and source/output SHA-256 hashes are recorded in
`segmentation_manifest.json`; the source revision identifies the CAD inputs,
not the current repository head.

Each exported piece was reimported as a valid solid and its axis-aligned extents
are below 180 mm. This establishes an envelope screen only: bed adhesion,
support, orientation, wall thickness, printing, assembly, and strength remain
unverified. The partition volume check does not claim a fused reconstruction.

Regenerate from the repository root with Python, CadQuery 2.7.0, OCP 7.8.1.1,
and Matplotlib 3.10.8:

```sh
python highspeed_edf/phase15/optimization/phase15_wing_print_segmentation.py
```
