# IAS700/IAS900 transonic solver diagnosis

## Evidence and likely numerical trigger

The original IAS700 `rhoPimpleFoam` input used `PIMPLE` with two outer correctors but omitted the `transonic yes` formulation. At 700 IAS the case Mach number is about 0.676; at 900 IAS it is about 0.862. The original IAS700 run developed a localized thermodynamic excursion before the time-step collapse: a native checkpoint at `3.2270672e-5 s` had `p=13 Pa..225 kPa`, `T=209..796 K`, `rho=5.7e-5..2.88 kg/m3`, and `|U|` up to 340 m/s against a 222 m/s freestream. The local extrema were near the inboard leading-edge region. At the end of the baseline log, the mean Courant number was only `1.53e-6` while maxCo was 0.4 and deltaT had fallen to `1.97e-10 s`; the controller was being driven by an extreme local flux state, not the domain-average flow.

This evidence points to an unstable high-subsonic pressure/thermodynamic solution as the immediate cause of the collapse. The missing transonic pressure treatment is the strongest tested solver-level trigger: enabling it with an asymmetric pressure solver prevented the same IAS700 collapse over a 75-second bounded run and kept deltaT near `4e-7 s` through `6.54e-5 s`. This is evidence of a major improvement, not proof that the missing switch alone caused the original failure. The modified solution still has large local gradients and has not converged.

A steady IAS700 test confirmed that the transonic pressure equation is asymmetric: retaining the baseline PCG solver caused OpenFOAM to reject the setup (`Unknown asymmetric matrix solver type PCG`). Switching to PBiCGStab/DILU allowed iteration to proceed, but the run still ended in a thermodynamic floating-point exception at iteration 26. A separate heavily damped/upwind steady test failed even earlier. Neither steady attempt converged.

## Boundary and mesh audit

The five named patches are present with the expected physical labels: inlet, outlet, farfield, fsi, and rootWall. The inlet uses fixed velocity and static temperature with zero-gradient pressure; the outlet fixes static pressure and uses pressure-inlet/outlet velocity; farfield uses freestream velocity and freestream pressure; the wing uses a stationary no-slip wall; the inboard cut is a symmetry plane. The CAS conversion reference differs from the case static pressure by only 8 Pa, too little to explain the observed failure.

The boundary audit ruled out missing or unnamed surface patches. It did not establish that the external domain is large enough: the farfield is about one chord from the wing in the vertical direction, the inlet is about one chord upstream, and the outlet is three chords downstream. The inboard symmetry plane is at x=80.33 mm on a swept/tapered wing sector, not at the aircraft centerline. These are material model limitations for high-subsonic external aerodynamics.

The native mesh passes `checkMesh`, but it is a coarse tetrahedral mesh with 34,166 cells, maximum non-orthogonality 82.87 degrees and 50 faces above 70 degrees. The earlier 2x target-size experiment produced 258,681 cells but did not converge; that mesh also had mixed quality changes and did not expand the farfield. A later credible solution still needs a larger farfield domain, controlled leading/trailing-edge and shock refinement, near-wall layers appropriate to the turbulence model, and mesh/timestep sensitivity.

## Current outcome

The transonic PIMPLE results have a mixed history: the original 75 s cases had duplicate correction entries and used effective value 1; the cleaned 3-correction restart from those checkpoints failed thermodynamically. A separate fresh-from-zero 3-correction pair is under a bounded native run, with status and results recorded in `experiments/pimple_transonic_10min_fresh/`. None of these runs establishes independent mesh or time-step convergence. The cases remain bounded transient tests only. The run logs, case dictionaries, source pins, checkpoint mass fluxes, and pressure-only load calculations are under `experiments/pimple_transonic/`. The raw baseline logs and existing mesh evidence remain in `raw/logs/` and `experiments/mesh_refine2x/`.

No convergence, final CL/CD, design ranking, full-aircraft aerodynamics, rotating EDF behavior, or aeroelastic result is claimed. The wing-sector pressure loads are transient, omit viscous stress, and exclude a physically loaded inboard cut surface. Candidate status remains unpromoted.

The two steady IAS700 tuning checks also failed. The transonic steady attempt used the matching asymmetric pressure solver but still hit a thermodynamic floating-point exception at iteration 26. A more heavily damped upwind attempt failed at iteration 5. This rules out presenting the pressure-formulation change as a converged steady fix.

The matrix-type check is preserved at `experiments/transonic_ias700/pcg_rejected/rhoSimpleFoam_PCG_rejected.log`: with `transonic yes`, OpenFOAM 1912 rejects PCG because the pressure matrix is asymmetric. The compatible PBiCGStab/DILU steady case then ran but diverged thermodynamically; this distinction is why the transient formulation test changes both `PIMPLE transonic` and the pressure solver.
