# Fresh three-correction native run commands

These cases start from the original t=0 fields, with no restart history. Each case has exactly one `PIMPLE nNonOrthogonalCorrectors 3` entry; `foamDictionary -entry PIMPLE.nNonOrthogonalCorrectors -value` returned 3 for IAS700 and IAS900. Both `rhoPimpleFoam -dry-run` commands returned 0.

Each native command is capped at 600 wall seconds and writes checkpoints every 100 time steps:

```sh
timeout --signal=INT --kill-after=20s 600s /workspace/openfoam-deb/usr/bin/rhoPimpleFoam -case highspeed_edf/phase15/fsi/results/local_openfoam_20261030/experiments/pimple_transonic_10min_fresh/ias700

timeout --signal=INT --kill-after=20s 600s /workspace/openfoam-deb/usr/bin/rhoPimpleFoam -case highspeed_edf/phase15/fsi/results/local_openfoam_20261030/experiments/pimple_transonic_10min_fresh/ias900
```

The shared tracked mesh is unchanged. Output is written to the sibling `rhoPimpleFoam_ias700_600s.log` and `rhoPimpleFoam_ias900_600s.log` files.
