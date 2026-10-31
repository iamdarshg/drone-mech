# Fuselage shell segmentation prototype

This isolated prototype splits the endpoint-relief 42.6 mm shell candidate into
ten STEP/BREP compounds: five axial bands, each divided at X=0 into port and
starboard pieces. The four transverse cuts are at Z = −240, −128, 0, and
136 mm. They do not use the source generator's internal frame stations at
Z = −100 and +100 mm.

Every piece round-trips through CadQuery/OCP STEP and BREP import and fits the
project's A1 mini profile envelope (180 × 180 × 180 mm) in source XYZ
orientation. The ten files contain twenty solids total. Piece files can contain
multiple disconnected solids; they are CAD compounds, not completed joined
parts. Segmented assembly STEP/BREP round trips preserve the 640 mm bounds.
The sum of piece STEP volumes differs from the endpoint source STEP by
0.892 mm³ (about 1.2 ppm); the manifest records the comparison and tolerance.

The source evidence documents a 640 mm shell master, 1.2 mm shell wall, a
186 mm nominal body width, source frame stations at ±100 mm, and sealed
scarf/flange joints. It does not define the added centerline division or the
four cuts used here. No retention, alignment, sealing, or structural joint
geometry is modeled. The inherited endpoint-relief source also contains four
disconnected regions (two duct-side walls, a lower section, and a separated
upper section); segmentation preserves these gaps. The native views show the
round-tripped assembly in its original station coordinates.

These are geometric envelope checks only. No slicer orientation/slice, support
review, print test, material/process validation, joint design, structural
analysis, or aircraft assembly check is included. The 42.6 mm candidate
inherits a +0.2 mm duct bore diameter change from the source shell and remains
unreviewed for local wall/interface consequences.

The prototype generator is
`highspeed_edf/phase15/optimization/phase15_segment_fuselage_shell_prototype.py`.
The render helper is
`highspeed_edf/phase15/optimization/phase15_render_shell_segmentation_prototype.py`.
`segmentation_manifest.json` and `native_views/native_views_manifest.json`
record input/output hashes, runtime versions, dimensions, round trips, and
view hashes.
