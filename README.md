# DataFlow ETL Audit and Lineage

A small Python, pandas, and SQLite pipeline that validates customer, product, and order CSVs; records rejects and run metrics; publishes business tables; and traces outputs to their source files.

## Setup

Use Python 3.10 or newer from the project root:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

Generate deterministic sample inputs and run the pipeline:

```powershell
python -m scripts.generate_data --rows 100000 --seed 42
python -m src.main
```

Run checks with `python -m pytest -q`. To use custom paths:

```powershell
python -m src.main --raw-dir data/raw --db-path dataflow_audit.db `
  --processed-dir data/processed --quarantine-dir data/quarantine `
  --report-path reports/run_audit.csv --log-path logs/pipeline.log
```

The three required inputs are `customers.csv`, `products.csv`, and `orders.csv`. Main outputs are a SQLite database, run-specific processed CSVs, issue-grain quarantine CSVs, a run report, and an operational log. Output directories are created when needed.

## Naming and identifiers

- Tables, columns, Python names, and filenames use lowercase `snake_case`.
- Business keys are stable strings: `customer_id` (`C######`), `product_id` (`P####`), and `order_id` (`O#######`). The generator derives them from row ordinals, so a fixed seed and row count reproduce the same keys. CSV IDs are read as strings to preserve leading zeros.
- `run_id` and `output_artifact_id` are UUIDs unique to an execution/artifact, allowing identical reruns to remain separate audit attempts. `source_file_id` is a database-generated surrogate key scoped to a source-file record; `source_file` stores the input filename on business and issue records. `source_record_number` identifies the row within that source.
- Run timestamps are UTC ISO-8601 strings with an explicit `+00:00` offset. Business `order_date` is a calendar date in `YYYY-MM-DD` form.
- Audit entities carry `run_id`; source-dependent records also carry `source_file_id` or `source_file` as defined in the [data dictionary](docs/data_dictionary.md).

## Data and design notes

See the [data dictionary](docs/data_dictionary.md) for fields and constraints, and [architecture](docs/architecture.md) for the pipeline flow and lineage. Business tables upsert by business key. A retry replays the full three-file snapshot; it can overwrite newer values for the same key. Customer, product, and order loads use separate transactions, so cross-table atomic publication is not provided.
