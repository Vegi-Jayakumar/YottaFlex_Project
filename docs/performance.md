# Performance and Validation Evidence

This project uses pandas and local SQLite. Validation is mixed: some numeric and schema checks use vectorized masks, while issue construction and selected reference diagnostics are row-wise. Audit writes use small SQLite transactions per record; issue logging is not batched.

No benchmark is claimed for this updated implementation. The prior review measured approximately 3 seconds for a 100,000-order demonstration using RAM-backed SQLite, Python 3.12, pandas 2.3.3, and NumPy 2.5.4. That is reference evidence from a separate environment, not a reproducible benchmark of this checkout or ordinary disk storage. For comparable measurement, record Python/library versions, storage type, input sizes, warm/cold state, and repeated wall-clock results.

## Validation evidence
Run `python -m pytest -q` from the project root. The suite covers transformation, numeric boundaries, audit provenance, lineage roles, rejected-row arithmetic, failed parsing, reruns, and report publication failure. Results should be recorded from the actual environment; no timing or pass count is prefilled here.
