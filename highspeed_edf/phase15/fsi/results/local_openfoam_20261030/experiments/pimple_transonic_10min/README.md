# Interrupted restart with duplicate PIMPLE entry

This directory preserves the exact input and log from the first 600 s restart attempt. It was interrupted after review detected duplicate `nNonOrthogonalCorrectors` entries in the copied `fvSolution`. `foamDictionary` resolves the effective value to 1 (the last entry), so this is an additional one-correction experiment. Its inputs and logs are retained without edits; both solver processes were sent SIGINT and exited 130.

At interruption, IAS700 had reached `t=1.0148727e-4 s`, `deltaT=4.36399e-7 s`, maxCo about 0.397. IAS900 had reached `t=8.79422e-5 s`, `deltaT=3.10989e-7 s`, maxCo about 0.404. These partial continuations were not converged and are superseded by the separate cleaned three-correction continuation.
