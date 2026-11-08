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
                    row_count=None, status="DISCOVERED", error_message=None):
    with get_connection(db_path) as conn:
        cur = conn.execute(
            """INSERT INTO source_files
               (run_id, file_name, file_path, file_hash,
                input_row_count, file_status, error_message)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (run_id, file_name, file_path, file_hash, row_count, status, error_message),
        )
        return cur.lastrowid

def update_source_file(db_path, source_file_id, status, row_count=None, error_message=None):
    with get_connection(db_path) as conn:
        conn.execute("UPDATE source_files SET file_status=?, input_row_count=?, error_message=? WHERE source_file_id=?",
                     (status, row_count, error_message, source_file_id))

def log_transformation(run_id, db_path, name, description,
                       rows_affected, elapsed_seconds, input_source_file_ids=None,
                       output_artifact_id=None, version="1"):
    with get_connection(db_path) as conn:
        cur = conn.execute(
            """INSERT INTO transformation_logs
               (run_id, transformation_name, description,
                rows_affected, execution_time_seconds, input_source_file_ids,
                output_artifact_id, transformation_version)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (run_id, name, description, rows_affected, elapsed_seconds,
             __import__("json").dumps(input_source_file_ids or []),
             output_artifact_id, version),
        )
        input_items = input_source_file_ids or []
        for item in input_items:
            source_id = item["source_file_id"] if isinstance(item, dict) else item
            role = item.get("dependency_role", "INPUT") if isinstance(item, dict) else "INPUT"
            conn.execute("INSERT INTO transformation_inputs(transformation_id,run_id,source_file_id,dependency_role) VALUES (?,?,?,?)",
                         (cur.lastrowid, run_id, source_id, role))
        return cur.lastrowid

def log_issue(run_id, db_path, source_file, record_id,
              issue_type, description, raw_record, source_record_number=None,
              source_file_id=None, diagnostic_record=None):
    with get_connection(db_path) as conn:
        conn.execute(
            """INSERT INTO data_quality_issues
               (run_id, source_file, source_record_id, source_record_number, source_file_id, issue_type,
               issue_description, raw_record, diagnostic_record)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (run_id, source_file, str(record_id) if record_id is not None else None,
             source_record_number, source_file_id, issue_type, description, raw_record, diagnostic_record),
        )

def log_lineage(run_id, db_path, source_file_id, output_location,
                output_table, row_count, output_hash, output_artifact_id=None,
                dependency_role="PRIMARY_SOURCE"):
    with get_connection(db_path) as conn:
        conn.execute(
            """INSERT INTO data_lineage
               (run_id, source_file_id, output_location, output_table,
                output_row_count, output_hash, output_artifact_id, dependency_role)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (run_id, source_file_id, str(output_location),
             output_table, row_count, output_hash, output_artifact_id, dependency_role),
        )

def log_artifact(run_id, db_path, artifact_id, location, table, rows, digest):
    with get_connection(db_path) as conn:
        conn.execute("INSERT INTO output_artifacts(output_artifact_id,run_id,output_location,output_table,output_row_count,output_hash) VALUES (?,?,?,?,?,?)",
                     (artifact_id, run_id, str(location), table, rows, digest))
