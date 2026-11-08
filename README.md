# DataFlow – ETL Pipeline Audit & Lineage

A local, reproducible Python ETL project demonstrating ingestion, schema and business-rule validation, quarantine, transformations, SQLite publishing, run auditing, and source-to-output lineage.

## Requirements
- Python 3.10+
- Install dependencies: `pip install -r requirements.txt`

## Generate sample data
From the project root:

```bash
python -m scripts.generate_data --rows 1000 --seed 42
```

For a larger run:

```bash
python -m scripts.generate_data --rows 100000 --seed 42
```

## Run pipeline

```bash
python -m src.main
```

Or specify paths:

```bash
python -m src.main --raw-dir data/raw --db-path dataflow_audit.db
```

All output locations can be set independently with `--processed-dir`,
`--quarantine-dir`, `--report-path`, and `--log-path`. Without `--report-path`,
the run writes a separate audit extract beside the selected database.

## Run tests

```bash
pytest tests/ -v
```

## Main outputs
- `dataflow_audit.db`: target business tables and audit metadata
- `data/processed/`: run-specific processed CSV outputs
- `data/quarantine/`: rejected record details
- `logs/pipeline.log`: operational log
- `reports/<run_id>_audit_report.csv`: run-specific source-to-output audit extract

## Data model and grain
- `customers`: one row per `customer_id`
- `products`: one row per `product_id`
- `orders`: one row per `order_id`
- `pipeline_runs`: one row per pipeline execution
- `source_files`: one row per source file per run
- `transformation_logs`: one row per logged transformation per run
- `transformation_inputs`: same-run transformation-to-source dependency edges
- `data_quality_issues`: one row per detected issue
- `output_artifacts`: one row per run output, counted once
- `data_lineage`: one row per source-file-to-output dependency edge, with role
- `reconciliation_checks`: persisted PASS/FAIL invariant results

## Business rules
- IDs must follow the generator formats (`C######`, `P####`, `O#######`); fields are read as strings and canonicalized by trimming.
- Business keys must be present and unique within each source file. The first canonical duplicate wins; later rows are rejected.
- Product price must be non-negative.
- Product price and order total must be stored as SQLite REAL; quantity must be stored as SQLite INTEGER. Bound pandas/NumPy scalars are normalized at the loading boundary.
- Order quantity must be a positive integer.
- Order date must parse as a date.
- Orders must reference known customers and products.
- Invalid records are logged with their source record number and raw payload.
- Extra input columns are rejected under schema version 1. Product price may be zero and must be finite.

## Idempotency and limitations
Business tables use stable primary keys and SQLite upserts, so rerunning the same input does not create duplicate business keys. Each execution still creates a separate run record and output snapshot. This starter implementation updates an existing business row when the same key is reprocessed; production systems should add source versioning or event-time conflict rules to prevent older data overwriting newer data.

The project is a local single-process demonstration. A retry replays the complete three-file snapshot; business keys upsert, so it is safe from duplicate keys but older snapshots can overwrite newer values. The three business table loads use separate transactions, so a later failure can leave earlier tables committed. Cross-table atomic publication and event-time conflict protection are not implemented. Per-run audit report writes use a temporary file and atomic replacement; a report failure marks the run failed.

## Naming conventions
- `snake_case` for tables, columns, functions, and files
- `run_id` identifies one execution
- ISO-8601 UTC timestamps for run start/end
- `source_file` records input provenance
