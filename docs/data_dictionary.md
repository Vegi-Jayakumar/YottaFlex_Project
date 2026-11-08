# DataFlow Data Dictionary

Schema version: **1**. CSV inputs are read as strings; required business fields are validated before conversion. Extra columns fail validation rather than being discarded.

## Business tables

| Table | Fields and constraints |
|---|---|
| `customers` | `customer_id` TEXT PK, required `C` plus six digits; `customer_name` TEXT NOT NULL; `city` TEXT NOT NULL. |
| `products` | `product_id` TEXT PK, required `P` plus four digits; `product_name` TEXT NOT NULL; `unit_price` REAL NOT NULL, finite and >= 0. Zero is permitted. |
| `orders` | `order_id` TEXT PK, required `O` plus seven digits; `customer_id`, `product_id` TEXT NOT NULL and FK to dimensions; `quantity` INTEGER > 0; `order_date` normalized to `YYYY-MM-DD`; `total_amount` REAL = quantity × unit price, rounded to 2 decimals. |

The published tables do not retain extra source columns. Input IDs are preserved as strings, whitespace is trimmed before key checks, and invalid formats are rejected. Duplicate canonical IDs use a deterministic first-row-wins policy; subsequent rows are rejected, even if their payload is identical.

## Audit and lineage entities

| Entity | Grain / fields |
|---|---|
| `pipeline_runs` | One execution: status (`RUNNING`, `SUCCESS`, `PARTIAL_SUCCESS`, `FAILED`), input/output/rejected counts, error, timing. Rejected count is distinct source rows; issue count is queried separately. |
| `source_files` | One discovered or required file per run: name, path, SHA-256 (empty only for absent files), nullable parsed input row count, `DISCOVERED`/`READ`/`FAILED`/`MISSING`, error detail. Null row count means parsing did not produce a count; zero means a parsed header-only file. |
| `transformation_logs` | One logged transformation per run, including `enrich_orders`, row count, elapsed seconds, input source IDs, output artifact ID and version. |
| `data_quality_issues` | One detected issue: source file ID and name, source record number, type, description, JSON raw fields captured before coercion. Multiple issues may refer to one source row. |
| `output_artifacts` | One run-specific output artifact: location, output table, row count and SHA-256. Count each artifact once. |
| `data_lineage` | One source-file-to-artifact dependency edge with role (`PRIMARY_SOURCE`, `PRICE_LOOKUP`, `REFERENCE_VALIDATION`). Edge row counts repeat artifact totals and must not be summed; sum `output_artifacts` instead. |
| `reconciliation_checks` | One named run invariant with PASS/FAIL, expected and actual values, details. |

## Rejected row examples
`INVALID_QUANTITY`: `{"order_id":"O0000001","quantity":"-1",...}`. `INVALID_DATE`: raw date text is retained (for example `"bad"`) even though the parsed value is invalid. `INVALID_REFERENCE`: the original source record number and raw fields are retained after key validation. The quarantine CSV is run-specific and records issue detail; the run metric counts distinct source rows.
