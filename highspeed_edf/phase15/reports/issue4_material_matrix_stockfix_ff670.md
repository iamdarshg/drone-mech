# Issue 4 material inventory source revalidation

This is current-source evidence for the Phase-15 stock-nest candidate at `ff670b80b2b3ce925b03d14a91329bb7940e73d7`. The generator pin is SHA-256 `53353da1c6f46d8cd9df7431209946869c0984908b269fb94d01f25a1cfabd47`; the mass/CG CSV remains byte-identical to its historical source SHA-256 `f5fe8171121c9c5ee5777ec81504b89da62a465d9a4bd0e04be03e40dd547498`. The generator's material density register was parsed from the updated source and is unchanged by the stock-nest correction.

The revalidated inventory is **BLOCKED**, with 74 of 74 mass rows mapped and no source/material mapping errors. It remains blocked because the source set has no supplier/product identity, laminate layup or coupon allowables, temperature and adhesive qualification, measured masses, or manufacturing process traveler. This report is separate from historical pre-correction source evidence; no physical materials qualification is claimed.

Full machine-readable results are in [`issue4_material_matrix_stockfix_ff670.json`](issue4_material_matrix_stockfix_ff670.json). The manifest pin and exact source hashes are recorded in that JSON.
