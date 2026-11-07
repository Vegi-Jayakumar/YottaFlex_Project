from datetime import datetime, timezone
from time import perf_counter
from .database import get_connection

def utc_now():
    return datetime.now(timezone.utc).isoformat()

def start_run(run_id, db_path, pipeline_name="retail_etl"):
    with get_connection(db_path) as conn:
        conn.execute(
            """INSERT INTO pipeline_runs
               (run_id, pipeline_name, start_time, status)
               VALUES (?, ?, ?, 'RUNNING')""",
            (run_id, pipeline_name, utc_now()),
        )

def finish_run(run_id, db_path, status, input_rows, output_rows,
               rejected_rows, start_clock, error_message=None):
    duration = round(perf_counter() - start_clock, 4)
    with get_connection(db_path) as conn:
        conn.execute(
            """UPDATE pipeline_runs
               SET end_time=?, status=?, total_input_rows=?,
                   total_output_rows=?, total_rejected_rows=?,
                   error_message=?, duration_seconds=?
               WHERE run_id=?""",
            (utc_now(), status, input_rows, output_rows, rejected_rows,
             error_message, duration, run_id),
        )

def log_source_file(run_id, db_path, file_name, file_path, file_hash,
                    row_count, status="READ"):
    with get_connection(db_path) as conn:
        cur = conn.execute(
            """INSERT INTO source_files
               (run_id, file_name, file_path, file_hash,
                input_row_count, file_status)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (run_id, file_name, file_path, file_hash, row_count, status),
        )
        return cur.lastrowid

def log_transformation(run_id, db_path, name, description,
                       rows_affected, elapsed_seconds):
    with get_connection(db_path) as conn:
        conn.execute(
            """INSERT INTO transformation_logs
               (run_id, transformation_name, description,
                rows_affected, execution_time_seconds)
               VALUES (?, ?, ?, ?, ?)""",
            (run_id, name, description, rows_affected, elapsed_seconds),
        )

def log_issue(run_id, db_path, source_file, record_id,
              issue_type, description, raw_record):
    with get_connection(db_path) as conn:
        conn.execute(
            """INSERT INTO data_quality_issues
               (run_id, source_file, source_record_id, issue_type,
                issue_description, raw_record)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (run_id, source_file, str(record_id) if record_id is not None else None,
             issue_type, description, raw_record),
        )

def log_lineage(run_id, db_path, source_file_id, output_location,
                output_table, row_count, output_hash):
    with get_connection(db_path) as conn:
        conn.execute(
            """INSERT INTO data_lineage
               (run_id, source_file_id, output_location, output_table,
                output_row_count, output_hash)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (run_id, source_file_id, str(output_location),
             output_table, row_count, output_hash),
        )
