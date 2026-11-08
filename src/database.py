import sqlite3
from pathlib import Path
from .config import DB_PATH

SCHEMA = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS pipeline_runs (
    run_id TEXT PRIMARY KEY,
    pipeline_name TEXT NOT NULL,
    start_time TEXT NOT NULL,
    end_time TEXT,
    status TEXT NOT NULL,
    total_input_rows INTEGER DEFAULT 0,
    total_output_rows INTEGER DEFAULT 0,
    total_rejected_rows INTEGER DEFAULT 0,
    error_message TEXT,
    duration_seconds REAL
);

CREATE TABLE IF NOT EXISTS source_files (
    source_file_id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL,
    file_name TEXT NOT NULL,
    file_path TEXT NOT NULL,
    file_hash TEXT NOT NULL,
    input_row_count INTEGER,
    file_status TEXT,
    error_message TEXT,
    FOREIGN KEY(run_id) REFERENCES pipeline_runs(run_id),
    UNIQUE(run_id, source_file_id)
);

CREATE TABLE IF NOT EXISTS transformation_logs (
    transformation_id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL,
    transformation_name TEXT NOT NULL,
    description TEXT,
    rows_affected INTEGER DEFAULT 0,
    execution_time_seconds REAL,
    input_source_file_ids TEXT,
    output_artifact_id TEXT,
    transformation_version TEXT NOT NULL DEFAULT '1',
    FOREIGN KEY(run_id) REFERENCES pipeline_runs(run_id),
    UNIQUE(run_id, transformation_id),
    FOREIGN KEY(run_id, output_artifact_id) REFERENCES output_artifacts(run_id, output_artifact_id)
);

CREATE TABLE IF NOT EXISTS data_quality_issues (
    issue_id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL,
    source_file TEXT NOT NULL,
    source_record_id TEXT,
    source_record_number INTEGER,
    source_file_id INTEGER,
    diagnostic_record TEXT,
    issue_type TEXT NOT NULL,
    issue_description TEXT NOT NULL,
    raw_record TEXT,
    FOREIGN KEY(run_id) REFERENCES pipeline_runs(run_id),
    FOREIGN KEY(run_id, source_file_id) REFERENCES source_files(run_id, source_file_id)
);

CREATE TABLE IF NOT EXISTS data_lineage (
    lineage_id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL,
    source_file_id INTEGER NOT NULL,
    output_location TEXT NOT NULL,
    output_table TEXT NOT NULL,
    output_row_count INTEGER NOT NULL,
    output_hash TEXT,
    output_artifact_id TEXT,
    dependency_role TEXT NOT NULL DEFAULT 'PRIMARY_SOURCE',
    FOREIGN KEY(run_id) REFERENCES pipeline_runs(run_id),
    FOREIGN KEY(run_id, source_file_id) REFERENCES source_files(run_id, source_file_id),
    FOREIGN KEY(run_id, output_artifact_id) REFERENCES output_artifacts(run_id, output_artifact_id)
);

CREATE TABLE IF NOT EXISTS output_artifacts (
    output_artifact_id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL,
    output_location TEXT NOT NULL,
    output_table TEXT NOT NULL,
    output_row_count INTEGER NOT NULL,
    output_hash TEXT,
    FOREIGN KEY(run_id) REFERENCES pipeline_runs(run_id),
    UNIQUE(run_id, output_artifact_id)
);

CREATE TABLE IF NOT EXISTS transformation_inputs (
    transformation_id INTEGER NOT NULL,
    run_id TEXT NOT NULL,
    source_file_id INTEGER NOT NULL,
    dependency_role TEXT NOT NULL,
    PRIMARY KEY(transformation_id, source_file_id, dependency_role),
    FOREIGN KEY(run_id, transformation_id) REFERENCES transformation_logs(run_id, transformation_id),
    FOREIGN KEY(run_id, source_file_id) REFERENCES source_files(run_id, source_file_id)
);

CREATE TABLE IF NOT EXISTS reconciliation_checks (
    check_id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL,
    check_name TEXT NOT NULL,
    status TEXT NOT NULL,
    expected_value TEXT,
    actual_value TEXT,
    details TEXT,
    FOREIGN KEY(run_id) REFERENCES pipeline_runs(run_id)
);

CREATE TABLE IF NOT EXISTS customers (
    customer_id TEXT PRIMARY KEY,
    customer_name TEXT NOT NULL,
    city TEXT NOT NULL,
    source_file TEXT,
    run_id TEXT
);

CREATE TABLE IF NOT EXISTS products (
    product_id TEXT PRIMARY KEY,
    product_name TEXT NOT NULL,
    unit_price REAL NOT NULL CHECK(unit_price >= 0),
    source_file TEXT,
    run_id TEXT,
    CHECK(typeof(unit_price) = 'real')
);

CREATE TABLE IF NOT EXISTS orders (
    order_id TEXT PRIMARY KEY,
    customer_id TEXT NOT NULL,
    product_id TEXT NOT NULL,
    quantity INTEGER NOT NULL CHECK(quantity > 0),
    order_date TEXT NOT NULL,
    total_amount REAL NOT NULL,
    source_file TEXT,
    run_id TEXT,
    CHECK(typeof(quantity) = 'integer'),
    CHECK(typeof(total_amount) = 'real'),
    FOREIGN KEY(customer_id) REFERENCES customers(customer_id),
    FOREIGN KEY(product_id) REFERENCES products(product_id)
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_source_files_run_id
    ON source_files(run_id, source_file_id);
CREATE UNIQUE INDEX IF NOT EXISTS uq_output_artifacts_run_id
    ON output_artifacts(run_id, output_artifact_id);
CREATE UNIQUE INDEX IF NOT EXISTS uq_transformations_run_id
    ON transformation_logs(run_id, transformation_id);
"""

def get_connection(db_path=DB_PATH):
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.row_factory = sqlite3.Row
    return conn

def initialize_database(db_path=DB_PATH):
    with get_connection(db_path) as conn:
        conn.executescript(SCHEMA)
        # Additive migrations keep existing student databases usable.
        migrations = {
            "source_files": {"error_message": "TEXT"},
            "data_quality_issues": {"source_record_number": "INTEGER", "source_file_id": "INTEGER REFERENCES source_files(source_file_id)", "diagnostic_record": "TEXT"},
            "data_lineage": {
                "output_artifact_id": "TEXT",
                "dependency_role": "TEXT NOT NULL DEFAULT 'PRIMARY_SOURCE'",
            },
            "transformation_logs": {
                "input_source_file_ids": "TEXT",
                "output_artifact_id": "TEXT",
                "transformation_version": "TEXT NOT NULL DEFAULT '1'",
            },
        }
        for table, columns in migrations.items():
            existing = {row["name"] for row in conn.execute(f"PRAGMA table_info({table})")}
            for column, definition in columns.items():
                if column not in existing:
                    conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")
