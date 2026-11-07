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
            "FROM data_lineage WHERE run_id=?", (run_id,)
        ).fetchone()["n"]
    return {"run": dict(run) if run else None,
            "issue_count": issues, "lineage_output_rows": lineage}

def export_audit_report(db_path, output_path):
    with get_connection(db_path) as conn:
        rows = conn.execute("""
            SELECT r.run_id, r.pipeline_name, r.start_time, r.end_time,
                   r.status, r.total_input_rows, r.total_output_rows,
                   r.total_rejected_rows, r.duration_seconds,
                   s.file_name, s.file_path, s.file_hash,
                   l.output_location, l.output_table, l.output_row_count
            FROM pipeline_runs r
            LEFT JOIN source_files s ON s.run_id = r.run_id
            LEFT JOIN data_lineage l
              ON l.run_id = s.run_id AND l.source_file_id = s.source_file_id
            ORDER BY r.start_time DESC
        """).fetchall()
    import pandas as pd
    pd.DataFrame([dict(row) for row in rows]).to_csv(output_path, index=False)
