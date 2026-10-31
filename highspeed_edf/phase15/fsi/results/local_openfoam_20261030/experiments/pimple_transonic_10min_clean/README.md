# Cleaned three-correction restart from one-correction snapshots

This experiment copies the interrupted 600 s restart cases, removes the duplicate `nNonOrthogonalCorrectors` entry, and verifies the effective value is 3 with `foamDictionary`. It resumes from the latest persisted checkpoints generated with an effective value of 1. Both corrected restarts then encountered a thermodynamic floating-point exception shortly after resuming (IAS700 at t=1.2078985e-4 s; IAS900 at t=1.0903387e-4 s; exit 136). These inputs and logs are retained to show the mixed-history restart failure.

The fresh-from-zero three-correction pair is in the sibling `pimple_transonic_10min_fresh/` directory. It is the appropriate independent solver-setting run. Neither directory changes the mesh, so neither supports mesh sensitivity conclusions.
