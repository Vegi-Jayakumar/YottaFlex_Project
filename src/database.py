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
    input_row_count INTEGER DEFAULT 0,
    file_status TEXT,
    FOREIGN KEY(run_id) REFERENCES pipeline_runs(run_id)
);

CREATE TABLE IF NOT EXISTS transformation_logs (
    transformation_id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL,
    transformation_name TEXT NOT NULL,
    description TEXT,
    rows_affected INTEGER DEFAULT 0,
    execution_time_seconds REAL,
    FOREIGN KEY(run_id) REFERENCES pipeline_runs(run_id)
);

CREATE TABLE IF NOT EXISTS data_quality_issues (
    issue_id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL,
    source_file TEXT NOT NULL,
    source_record_id TEXT,
    issue_type TEXT NOT NULL,
    issue_description TEXT NOT NULL,
    raw_record TEXT,
    FOREIGN KEY(run_id) REFERENCES pipeline_runs(run_id)
);

CREATE TABLE IF NOT EXISTS data_lineage (
    lineage_id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL,
    source_file_id INTEGER NOT NULL,
    output_location TEXT NOT NULL,
    output_table TEXT NOT NULL,
    output_row_count INTEGER NOT NULL,
    output_hash TEXT,
    FOREIGN KEY(run_id) REFERENCES pipeline_runs(run_id),
    FOREIGN KEY(source_file_id) REFERENCES source_files(source_file_id)
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
    run_id TEXT
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
    FOREIGN KEY(customer_id) REFERENCES customers(customer_id),
    FOREIGN KEY(product_id) REFERENCES products(product_id)
);
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
