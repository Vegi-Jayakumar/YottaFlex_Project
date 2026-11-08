# Validation Evidence

Executed locally on 8 November 2026 with Python 3.10:

- `python -m pytest -q`: **14 passed**. Pytest emitted an upstream `PytestRemovedIn10Warning`; pandas also emitted expected date-format inference warnings for deliberately invalid date fixtures.
- Generated a fixed-seed 1,000-order sample (`seed=42`) and ran the end-to-end pipeline with isolated database, output, quarantine, report, and log paths. The run completed with a recorded run ID and atomically published its per-run report.
- Generated and processed 100,000 orders (`seed=42`) with 20,000 customers and 100 products. Run `cacf0258-a772-4ff8-b6bf-9bfef6325dd0` finished `PARTIAL_SUCCESS`: 120,100 input rows, 120,095 accepted/output records, five distinct rejected rows, and 99,995 target orders. All 99,995 target quantities reported SQLite `integer` storage; product prices and order totals reported `real`; SQL per-order amount mismatches: 0. The database stored 7,611,847,398.78 as the order total sum. Output hash, key uniqueness, current-run target count, foreign key, audit relationship, and reconciliation checks all passed. Three output artifacts had five lineage dependency edges.
- Initialized a copy of the existing project database using the additive migrations; initialization completed and the legacy audit relationship scan reported zero orphan or cross-run references.
- Integration tests cover one row with two issues, parser failure after pre-parse registration, exact original reference-reject payloads with normalized diagnostics, string/numeric price variants and zero, SQLite numeric storage and per-order arithmetic, same-run artifact/source foreign keys, repeat-run audit separation and key stability, and report-export failure status.

The 100,000-row run took 24.8 seconds on this local Python 3.10 environment; this is execution evidence, not a portable performance benchmark. Results describe this checkout and do not imply cross-table atomic publication.
