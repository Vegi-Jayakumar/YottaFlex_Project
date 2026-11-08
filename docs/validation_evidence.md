# Validation Evidence

Executed locally on 8 November 2026 with Python 3.10:

- `python -m pytest -q`: **12 passed**. Pytest emitted an upstream `PytestRemovedIn10Warning`; pandas also emitted expected date-format inference warnings for deliberately invalid date fixtures.
- Generated a fixed-seed 1,000-order sample (`seed=42`) and ran the end-to-end pipeline with isolated database, output, quarantine, report, and log paths. The run completed with a recorded run ID and atomically published its per-run report.
- Integration tests cover one row with two issues, parser failure after pre-parse file registration, source-to-artifact dependency roles, repeat-run audit separation and key stability, and report-export failure status.

These results describe this local checkout and environment. They are functional checks, not a performance benchmark or evidence of cross-table atomic publication.
