# DataFlow Pipeline Architecture & Lineage

## Implemented flow
1. Discover CSVs, hash each existing file, and register its `DISCOVERED` audit row before parsing. Files move to `READ` with a parsed data-row count, or `FAILED` with a parser error. A missing required file gets an expected-source audit row with `MISSING` status and no fabricated hash or row count.
2. Read CSV columns as strings to preserve identifiers. Required columns are enforced and unexpected extra columns are rejected. Keys are trimmed, checked against the generator's `C######`, `P####`, and `O#######` formats, then duplicate checked on the canonical key (first occurrence wins; later occurrences are rejected).
3. Validate source rows and references. Original raw JSON payloads and canonical/parsed diagnostic JSON are carried separately. Every issue gets the immutable source file ID and source record number; `total_rejected_rows` counts distinct source rows, while quarantine CSVs and `data_quality_issues` are issue-grain, so one rejected row with two issues appears twice there.
4. Write accepted business data to run-specific processed CSVs and upsert SQLite tables. Dimension loads and the order load each have their own transaction, so a later failure can leave earlier completed tables published. This is a complete input snapshot for validation, not an incremental event stream; older reruns can overwrite newer values with the same key.
5. Normalize every pandas/NumPy scalar to a native Python value at the SQLite binding boundary. SQLite checks enforce integer quantity and REAL product price/order total storage on newly created databases.
6. Store each output once in `output_artifacts`; same-run composite foreign keys link source files, artifacts, and lineage rows. `transformation_inputs` provides same-run input edges for transformations. Orders link to orders.csv, products.csv, and customers.csv; product pricing is recorded alongside the versioned `enrich_orders` transformation.
7. Persist reconciliation checks for SQLite storage classes, per-order SQL arithmetic, output hashes, keys, counts, foreign keys, and same-run audit relationships. The per-run audit report is written atomically; a required report failure changes the run to `FAILED` while retaining the business outcome only in logs/outputs and the error detail in the run row.

## Known boundaries
The implementation is a local single-process demonstration. Multi-table business publication is not atomic. Audit rows are durable independently, but the run does not automatically roll back earlier table commits after a later stage fails. Retry by rerunning the full same snapshot; upserts are safe for business keys but do not provide event-time conflict protection. No claim of staging isolation or crash-proof recovery is made.

## Examples
An accepted order CSV has `order_id,customer_id,product_id,quantity,order_date,total_amount`. `total_amount` is quantity multiplied by the product's finite, non-negative `unit_price`, rounded to two decimals.

Reject issue types include `MISSING_KEY`, `INVALID_ID_FORMAT`, `DUPLICATE_KEY`, `MISSING_REQUIRED_VALUE`, `INVALID_PRICE`, `INVALID_QUANTITY`, `INVALID_DATE`, and `INVALID_REFERENCE`. A source row can have multiple issue rows in the issue-grain quarantine artifact but appears once in the run rejected-row count.

## Trade-offs
Pandas and SQLite keep the example portable and easy to inspect. The design favors clear local auditability over concurrent writers, atomic cross-table publication, or large distributed workloads. Extra columns are rejected under schema version 1 so a changed input cannot silently lose fields.
