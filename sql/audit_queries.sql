-- Recent pipeline runs
SELECT run_id, pipeline_name, start_time, end_time, status,
       total_input_rows, total_output_rows, total_rejected_rows,
       duration_seconds
FROM pipeline_runs
ORDER BY start_time DESC;

-- Source-to-output lineage
SELECT r.run_id, s.file_name, s.input_row_count,
       l.output_location, l.output_table, l.output_row_count
FROM pipeline_runs r
JOIN source_files s ON s.run_id = r.run_id
JOIN data_lineage l
  ON l.run_id = r.run_id
 AND l.source_file_id = s.source_file_id;

-- Rejected records
SELECT run_id, source_file, source_record_id,
       issue_type, issue_description
FROM data_quality_issues
ORDER BY issue_id DESC;

-- Failed runs
SELECT run_id, start_time, end_time, error_message
FROM pipeline_runs
WHERE status = 'FAILED';
