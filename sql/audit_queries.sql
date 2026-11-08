-- Recent runs and row-level rejection totals
SELECT r.run_id, r.start_time, r.end_time, r.status,
       r.total_input_rows, r.total_output_rows, r.total_rejected_rows,
       (SELECT COUNT(*) FROM data_quality_issues i WHERE i.run_id=r.run_id) AS issue_count,
       r.error_message
FROM pipeline_runs r ORDER BY r.start_time DESC;

-- Query all source dependencies for each output artifact. Do not sum edge row counts.
SELECT a.run_id, a.output_artifact_id, a.output_table, a.output_location,
       a.output_row_count, a.output_hash, s.file_name, s.file_hash,
       l.dependency_role
FROM output_artifacts a
JOIN data_lineage l ON l.output_artifact_id=a.output_artifact_id
JOIN source_files s ON s.source_file_id=l.source_file_id
ORDER BY a.run_id, a.output_table, l.dependency_role;

-- Enrichment evidence and its inputs/output
SELECT run_id, transformation_name, transformation_version,
       input_source_file_ids, output_artifact_id, rows_affected,
       execution_time_seconds
FROM transformation_logs WHERE transformation_name='enrich_orders';

-- Reconciliation failures
SELECT run_id, check_name, expected_value, actual_value, details
FROM reconciliation_checks WHERE status='FAIL';

-- Rejected source records and issue details
SELECT run_id, source_file_id, source_file, source_record_number, source_record_id,
       issue_type, issue_description, raw_record
FROM data_quality_issues ORDER BY issue_id DESC;

-- File discovery/read/parse failures
SELECT run_id, file_name, file_path, file_hash, input_row_count, file_status, error_message
FROM source_files WHERE file_status IN ('DISCOVERED','FAILED','MISSING');
