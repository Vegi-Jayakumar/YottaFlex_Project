# DataFlow Pipeline Architecture & Lineage

## Implemented flow
1. Discover required CSVs, hash each discovered file, and register its `DISCOVERED` audit row before parsing. Files move to `READ` with a parsed data-row count, or `FAILED` with a parser error. Missing required files fail the run without a fabricated file row.
2. Read CSV columns as strings to preserve identifiers. Required columns are enforced and unexpected extra columns are rejected. Keys are trimmed, checked against the generator's `C######`, `P####`, and `O#######` formats, then duplicate checked on the canonical key (first occurrence wins; later occurrences are rejected).
3. Validate source rows and references. Raw JSON payloads are captured before coercion. Every issue gets a source record number; `total_rejected_rows` counts distinct source rows, while `data_quality_issues` stores each issue.
4. Write accepted business data to run-specific processed CSVs and upsert SQLite tables. Dimension loads and the order load each have their own transaction, so a later failure can leave earlier completed tables published. This is a complete input snapshot for validation, not an incremental event stream; older reruns can overwrite newer values with the same key.
5. Store each output once in `output_artifacts`; `data_lineage` links source files to artifacts with `PRIMARY_SOURCE`, `PRICE_LOOKUP`, and `REFERENCE_VALIDATION` roles. Orders link to orders.csv, products.csv, and customers.csv; product pricing is recorded alongside the `enrich_orders` transformation.
6. Persist reconciliation checks and run status. The per-run audit report is written atomically; a required report failure changes the run to `FAILED` while retaining the business outcome only in logs/outputs and the error detail in the run row.

## Known boundaries
The implementation is a local single-process demonstration. Multi-table business publication is not atomic. Audit rows are durable independently, but the run does not automatically roll back earlier table commits after a later stage fails. Retry by rerunning the full same snapshot; upserts are safe for business keys but do not provide event-time conflict protection. No claim of staging isolation or crash-proof recovery is made.

## Examples
An accepted order CSV has `order_id,customer_id,product_id,quantity,order_date,total_amount`. `total_amount` is quantity multiplied by the product's finite, non-negative `unit_price`, rounded to two decimals.

Reject issue types include `MISSING_KEY`, `INVALID_ID_FORMAT`, `DUPLICATE_KEY`, `MISSING_REQUIRED_VALUE`, `INVALID_PRICE`, `INVALID_QUANTITY`, `INVALID_DATE`, and `INVALID_REFERENCE`. A source row can have multiple issue rows but appears once in the quarantine artifact's issue records and once in the run rejected-row count.

## Trade-offs
Pandas and SQLite keep the example portable and easy to inspect. The design favors clear local auditability over concurrent writers, atomic cross-table publication, or large distributed workloads. Extra columns are rejected under schema version 1 so a changed input cannot silently lose fields.
