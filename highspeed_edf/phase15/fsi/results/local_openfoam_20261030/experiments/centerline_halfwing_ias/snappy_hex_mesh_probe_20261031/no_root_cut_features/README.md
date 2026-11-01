# No-root-cut feature filter: strict mesh failure

This record pins the completed `snappyHexMesh` result from
`/workspace/snappy-rootcap-fine-20261031/no_root_cut_features`. Snappy completed
without errors with 1,492,067 cells. The filter removed 462 feature edges whose
two endpoints both lie on x=0; 1,040 edges remained. `filter_proof.txt` records
the edge-selection proof and digest.

The standalone OpenFOAM 1912 check used the retained mesh at `constant/`, all
topology and geometry checks, and the unchanged quality limits from the
snappy dictionary:

```sh
checkMesh -case no_root_cut_features -constant -allTopology -allGeometry -meshQuality
```

The exact quality dictionary and native output are retained here. The check
reported a minimum cell determinant of `5.09575e-18` (one cell below `0.001`)
and 32,414 concave cells. It ended with `Failed 2 mesh checks.` The executable
returned status 0 despite that failure text, so the mesh gate is failed based
on the reported checks. Other reported metrics include maximum non-orthogonality
57.9195 degrees and maximum skewness 2.71728. The failed determinant and concave
cell checks block the solver run. No solver was launched, and visual wall
fidelity was not assessed.

The thresholds are unchanged: max non-orthogonality 65 degrees, internal and
boundary skewness 4/20, max concavity 80 degrees, min volume `1e-13`, min tet
quality `1e-9`, min area `1e-15`, min twist 0.05, min determinant 0.001, min face
weight 0.05, and min volume ratio 0.01. Snappy's configured cell cap remained
1,200,000; its completed output contained 1,492,067 cells.

Input hashes:

- `blockMeshDict`: `382b29b6503c0b14291f2baff335b60d36f8d7f8667e216e49f4d7c8c9dcbeef`
- `snappyHexMeshDict`: `e3a69e1fdcadd23f9684883e19023922aac0ecd98c300c7ad0a3ad390911b1f7`
- `surfaceFeatureExtractDict`: `05ef2c42893a833fcc9ebb3209fc2e98f0bfd3f28e4ce569815e97d91c0dd96d`
- source `halfwing.stl`: `edafbbf4046c1756ec63caf65f1c3ab485f631131600fbc4968717a41967fcc0`
- filtered `halfwing.eMesh`: `585b2e448a8cf7e0e379bab55943cc95ba25a45cd86e6df025d93efd24574b2b`
- final mesh `points`: `708b78f8b1a7462ee7f621a0c9046ac7dfbcdc30496776f1bb526a884d17ee05`
- final mesh `faces`: `f8a4f4e2f94447c81ab33b08c986718950636c28823bc0ab6407742abb26cc3b`
- final mesh `owner`: `ff7d102df71184bd883c1eaae744e7b87ad352362620663908681009b6bb8185`
- final mesh `neighbour`: `0687b51e4f3ea2e9af8028546689dd6d248053b329af458ca507a4cc35ada144`

This is a failed exploratory mesh probe, not CFD or design evidence.
