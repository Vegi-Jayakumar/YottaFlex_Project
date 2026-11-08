from .database import get_connection

def get_run_summary(run_id, db_path):
    with get_connection(db_path) as conn:
        run = conn.execute(
            "SELECT * FROM pipeline_runs WHERE run_id=?", (run_id,)
        ).fetchone()
        issues = conn.execute(
            "SELECT COUNT(*) AS n FROM data_quality_issues WHERE run_id=?",
            (run_id,),
        ).fetchone()["n"]
        lineage = conn.execute(
            "SELECT COALESCE(SUM(output_row_count), 0) AS n "
            "FROM output_artifacts WHERE run_id=?", (run_id,)
        ).fetchone()["n"]
        checks = conn.execute(
            "SELECT check_name, status, expected_value, actual_value, details "
            "FROM reconciliation_checks WHERE run_id=?", (run_id,)
        ).fetchall()
    return {"run": dict(run) if run else None,
            "issue_count": issues, "lineage_output_rows": lineage,
            "checks": [dict(row) for row in checks]}

def export_audit_report(db_path, output_path):
    with get_connection(db_path) as conn:
        rows = conn.execute("""
            SELECT r.run_id, r.pipeline_name, r.start_time, r.end_time,
                   r.status, r.total_input_rows, r.total_output_rows,
                   r.total_rejected_rows, r.duration_seconds, r.error_message,
                   (SELECT GROUP_CONCAT(file_name || ':' || file_status || ':' || COALESCE(input_row_count,'unknown'), ' | ')
                    FROM source_files s WHERE s.run_id=r.run_id) AS source_files,
                   (SELECT GROUP_CONCAT(output_table || ':' || output_row_count || ':' || output_hash, ' | ')
                    FROM output_artifacts a WHERE a.run_id=r.run_id) AS output_artifacts,
                   (SELECT COUNT(*) FROM data_quality_issues i WHERE i.run_id=r.run_id) AS issue_count,
                   (SELECT GROUP_CONCAT(check_name || ':' || status, ' | ')
                    FROM reconciliation_checks c WHERE c.run_id=r.run_id) AS reconciliation
            FROM pipeline_runs r ORDER BY r.start_time DESC
        """).fetchall()
    import os, tempfile
    import pandas as pd
    output_path = __import__("pathlib").Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=output_path.stem + "_", suffix=".tmp", dir=output_path.parent)
    os.close(fd)
    try:
        pd.DataFrame([dict(row) for row in rows]).to_csv(temp_name, index=False)
        os.replace(temp_name, output_path)
    finally:
        if os.path.exists(temp_name): os.unlink(temp_name)
