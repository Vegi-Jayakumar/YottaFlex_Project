# Data Dictionary

Schema version 1. CSV fields are read as strings, validated, then converted where needed. Missing required columns and unexpected extra columns fail validation.

## Business tables

| Table | Fields |
|---|---|
| `customers` | `customer_id` TEXT PK (`C` + six digits, required); `customer_name` TEXT NOT NULL; `city` TEXT NOT NULL; `source_file` and `run_id` TEXT provenance fields. |
| `products` | `product_id` TEXT PK (`P` + four digits, required); `product_name` TEXT NOT NULL; `unit_price` finite SQLite REAL, >= 0 (zero allowed); `source_file` and `run_id` TEXT provenance fields. |
| `orders` | `order_id` TEXT PK (`O` + seven digits, required); `customer_id` and `product_id` TEXT NOT NULL FKs; `quantity` SQLite INTEGER > 0; `order_date` TEXT `YYYY-MM-DD`; `total_amount` SQLite REAL, quantity × unit price rounded to 2 decimals; `source_file` and `run_id` TEXT provenance fields. |

IDs are canonicalized by trimming whitespace before format, duplicate, and reference checks. The first canonical duplicate is kept; later rows are rejected. Output business tables retain only listed business fields and provenance.

## Audit and lineage tables

| Table | Grain and important fields |
|---|---|
| `pipeline_runs` | One execution: UUID `run_id` PK, `pipeline_name`, UTC ISO-8601 `start_time` / `end_time`, `status`, input/output/distinct-rejected counts, `error_message`, duration. |
| `source_files` | One expected or discovered source per run: integer `source_file_id` PK, `run_id` FK, `file_name`, `file_path`, SHA-256 `file_hash`, nullable parsed `input_row_count`, `file_status`, `error_message`. |
| `transformation_logs` | One logged transformation per run: `transformation_id`, `run_id`, name/version, rows and elapsed seconds, optional output artifact and JSON source ID list. |
| `transformation_inputs` | One transformation-to-source edge: `transformation_id`, `run_id`, `source_file_id`, `dependency_role`; composite FKs enforce same-run relationships. |
| `data_quality_issues` | One issue: `run_id`, `source_file_id`, `source_file`, `source_record_number`, type/description, original `raw_record` JSON, normalized `diagnostic_record` JSON. Multiple issues can refer to one source row. |
| `output_artifacts` | One output per run: UUID `output_artifact_id`, `run_id`, location, table, row count, SHA-256. Count artifacts once. |
| `data_lineage` | One source-to-artifact edge: `run_id`, `source_file_id`, `output_artifact_id`, dependency role, repeated artifact row count/hash. New edges have same-run composite FKs. |
| `reconciliation_checks` | One invariant per run: `run_id`, `check_name`, PASS/FAIL, expected/actual value, details. |

`source_file_id` is an internal database surrogate, not a portable business ID. `run_id` is a fresh UUID per attempt and each output gets a UUID artifact ID; this keeps reruns independently auditable. Business IDs are deterministic for generated inputs. Times use UTC ISO-8601 with `+00:00`; `order_date` is a date, not a timestamp.

Run rejected-row counts count distinct `(source_file_id, source_record_number)` pairs. Quarantine CSVs and `data_quality_issues` are issue-grain, so one row with two errors produces two issue records. A NULL parsed row count means no count was obtained; zero means a file parsed with no data rows.
