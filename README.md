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

## Run tests

```bash
pytest tests/ -v
```

## Main outputs
- `dataflow_audit.db`: target business tables and audit metadata
- `data/processed/`: run-specific processed CSV outputs
- `data/quarantine/`: rejected record details
- `logs/pipeline.log`: operational log
- `reports/audit_report.csv`: source-to-output audit extract

## Data model and grain
- `customers`: one row per `customer_id`
- `products`: one row per `product_id`
- `orders`: one row per `order_id`
- `pipeline_runs`: one row per pipeline execution
- `source_files`: one row per source file per run
- `transformation_logs`: one row per logged transformation per run
- `data_quality_issues`: one row per detected issue
- `data_lineage`: one row per source-file-to-output relationship

## Business rules
- Business keys must be present and unique within each source file.
- Product price must be non-negative.
- Order quantity must be a positive integer.
- Order date must parse as a date.
- Orders must reference known customers and products.
- Invalid records are logged with their source record number and raw payload.

## Idempotency and limitations
Business tables use stable primary keys and SQLite upserts, so rerunning the same input does not create duplicate business keys. Each execution still creates a separate run record and output snapshot. This starter implementation updates an existing business row when the same key is reprocessed; production systems should add source versioning or event-time conflict rules to prevent older data overwriting newer data.

The project is a local single-process demonstration. For production, consider atomic staging-and-publish transactions, stronger schema contracts, structured retry policies, access controls, and a server database.

## Naming conventions
- `snake_case` for tables, columns, functions, and files
- `run_id` identifies one execution
- ISO-8601 UTC timestamps for run start/end
- `source_file` records input provenance
