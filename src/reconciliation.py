from .database import get_connection

def audit_relationship_errors(db_path, run_id=None):
    """Validate same-run audit links, including legacy nullable/text-encoded links."""
    errors = []
    scope = " AND d.run_id=?" if run_id else ""
    params = (run_id,) if run_id else ()
    with get_connection(db_path) as conn:
        queries = [
            ("lineage_source", f"SELECT COUNT(*) FROM data_lineage d LEFT JOIN source_files s ON s.source_file_id=d.source_file_id AND s.run_id=d.run_id WHERE s.source_file_id IS NULL{scope}", params),
            ("lineage_artifact", f"SELECT COUNT(*) FROM data_lineage d LEFT JOIN output_artifacts a ON a.output_artifact_id=d.output_artifact_id AND a.run_id=d.run_id WHERE d.output_artifact_id IS NOT NULL AND a.output_artifact_id IS NULL{scope}", params),
            ("transformation_artifact", f"SELECT COUNT(*) FROM transformation_logs t LEFT JOIN output_artifacts a ON a.output_artifact_id=t.output_artifact_id AND a.run_id=t.run_id WHERE t.output_artifact_id IS NOT NULL AND a.output_artifact_id IS NULL{(' AND t.run_id=?' if run_id else '')}", params),
            ("issue_source", f"SELECT COUNT(*) FROM data_quality_issues i LEFT JOIN source_files s ON s.source_file_id=i.source_file_id AND s.run_id=i.run_id WHERE i.source_file_id IS NOT NULL AND s.source_file_id IS NULL{(' AND i.run_id=?' if run_id else '')}", params),
            ("transformation_input_bridge", f"SELECT COUNT(*) FROM transformation_inputs x LEFT JOIN source_files s ON s.source_file_id=x.source_file_id AND s.run_id=x.run_id LEFT JOIN transformation_logs t ON t.transformation_id=x.transformation_id AND t.run_id=x.run_id WHERE (s.source_file_id IS NULL OR t.transformation_id IS NULL){(' AND x.run_id=?' if run_id else '')}", params),
        ]
        for name, sql, query_params in queries:
            count = conn.execute(sql, query_params).fetchone()[0]
            if count: errors.append(f"{name}={count}")
        trans_query = "SELECT run_id, transformation_id, input_source_file_ids FROM transformation_logs" + (" WHERE run_id=?" if run_id else "")
        for row in conn.execute(trans_query, params):
            try:
                inputs = __import__("json").loads(row["input_source_file_ids"] or "[]")
            except (TypeError, ValueError):
                errors.append(f"transformation_input_json_invalid={row['transformation_id']}")
                continue
            for item in inputs:
                source_id = item.get("source_file_id") if isinstance(item, dict) else item
                found = conn.execute("SELECT 1 FROM source_files WHERE source_file_id=? AND run_id=?", (source_id, row["run_id"])).fetchone()
                if not found: errors.append(f"transformation_input_cross_run={row['transformation_id']}:{source_id}")
    return errors

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
