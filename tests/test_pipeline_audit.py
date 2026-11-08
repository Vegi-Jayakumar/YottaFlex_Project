import json
import sqlite3
import pandas as pd
import pytest

from src.main import run_pipeline

def _inputs(root):
    raw = root / "raw"; raw.mkdir()
    pd.DataFrame([{"customer_id":"C000001","customer_name":"A","city":"X"}]).to_csv(raw / "customers.csv", index=False)
    pd.DataFrame([{"product_id":"P0001","product_name":"Thing","unit_price":4.5}]).to_csv(raw / "products.csv", index=False)
    pd.DataFrame([
        {"order_id":"O0000001","customer_id":"C000001","product_id":"P0001","quantity":-1,"order_date":"bad"},
        {"order_id":"O0000002","customer_id":"C000001","product_id":"P0001","quantity":2,"order_date":"2026-01-01"},
    ]).to_csv(raw / "orders.csv", index=False)
    return raw

def test_run_counts_unique_rejects_and_records_dependency_edges(tmp_path):
    raw = _inputs(tmp_path); db = tmp_path / "audit.db"
    run_id = run_pipeline(raw, db, tmp_path / "processed", tmp_path / "quarantine", tmp_path / "reports" / "report.csv", tmp_path / "logs" / "run.log")
    with sqlite3.connect(db) as conn:
        run = conn.execute("SELECT status,total_input_rows,total_output_rows,total_rejected_rows FROM pipeline_runs WHERE run_id=?", (run_id,)).fetchone()
        issue_count = conn.execute("SELECT count(*) FROM data_quality_issues WHERE run_id=?", (run_id,)).fetchone()[0]
        roles = {x[0] for x in conn.execute("SELECT dependency_role FROM data_lineage WHERE run_id=? AND output_table='orders'", (run_id,))}
        sources = conn.execute("SELECT file_status,input_row_count FROM source_files WHERE run_id=? AND file_name='orders.csv'", (run_id,)).fetchone()
        lineage_count = conn.execute("SELECT COUNT(*) FROM data_lineage WHERE run_id=?", (run_id,)).fetchone()[0]
    assert run == ("PARTIAL_SUCCESS", 4, 3, 1)
    assert issue_count == 2
    assert roles == {"PRIMARY_SOURCE", "PRICE_LOOKUP", "REFERENCE_VALIDATION"}
    assert lineage_count == 5
    assert sources == ("READ", 2)

def test_sqlite_numeric_types_and_per_order_arithmetic(tmp_path):
    raw = tmp_path / "raw"; raw.mkdir()
    pd.DataFrame([{"customer_id":"C000001","customer_name":"A","city":"X"}]).to_csv(raw / "customers.csv", index=False)
    pd.DataFrame([{"product_id":"P0001","product_name":"A","unit_price":"10"},
                  {"product_id":"P0002","product_name":"B","unit_price":"10.0"},
                  {"product_id":"P0003","product_name":"Zero","unit_price":"0"}]).to_csv(raw / "products.csv", index=False)
    pd.DataFrame([{"order_id":f"O{i:07d}","customer_id":"C000001","product_id":f"P{i:04d}","quantity":"2","order_date":"2026-01-02"}
                  for i in range(1,4)]).to_csv(raw / "orders.csv", index=False)
    db = tmp_path / "audit.db"
    run_id = run_pipeline(raw, db, tmp_path / "processed", tmp_path / "quarantine", tmp_path / "reports" / "report.csv", tmp_path / "logs" / "run.log")
    with sqlite3.connect(db) as conn:
        rows = conn.execute("""SELECT typeof(o.quantity), typeof(p.unit_price), typeof(o.total_amount),
             o.quantity, p.unit_price, o.total_amount, ROUND(o.quantity*p.unit_price,2)
             FROM orders o JOIN products p USING(product_id) WHERE o.run_id=? ORDER BY o.order_id""", (run_id,)).fetchall()
        check = conn.execute("SELECT status FROM reconciliation_checks WHERE run_id=? AND check_name='per_order_amount_reconciliation'", (run_id,)).fetchone()[0]
    assert [r[:3] for r in rows] == [("integer","real","real")]*3
    assert [(r[3],r[5],r[6]) for r in rows] == [(2,20.0,20.0),(2,20.0,20.0),(2,0.0,0.0)]
    assert check == "PASS"

def test_reference_reject_preserves_original_payload_and_normalized_diagnostics(tmp_path):
    raw = _inputs(tmp_path)
    pd.DataFrame([{"order_id":"O0000001","customer_id":" C999999 ","product_id":"P0001",
                   "quantity":"02","order_date":"2026-1-2"}]).to_csv(raw / "orders.csv", index=False)
    db = tmp_path / "audit.db"
    run_id = run_pipeline(raw, db, tmp_path / "processed", tmp_path / "quarantine", tmp_path / "reports" / "report.csv", tmp_path / "logs" / "run.log")
    with sqlite3.connect(db) as conn:
        raw_record, diagnostics, source_id = conn.execute("SELECT raw_record,diagnostic_record,source_file_id FROM data_quality_issues WHERE run_id=? AND issue_type='INVALID_REFERENCE'", (run_id,)).fetchone()
        source_name, source_hash = conn.execute("SELECT file_name,file_hash FROM source_files WHERE source_file_id=? AND run_id=?", (source_id,run_id)).fetchone()
    raw_values, normalized = json.loads(raw_record), json.loads(diagnostics)
    assert raw_values["customer_id"] == " C999999 " and raw_values["quantity"] == "02" and raw_values["order_date"] == "2026-1-2"
    assert normalized["customer_id"] == "C999999" and normalized["quantity"] == 2 and normalized["order_date"] == "2026-01-02"
    assert source_name == "orders.csv" and len(source_hash) == 64

def test_malformed_file_is_registered_before_parse(tmp_path):
    raw = _inputs(tmp_path)
    (raw / "orders.csv").write_text('order_id,customer_id,product_id,quantity,order_date\n"unterminated', encoding="utf-8")
    db = tmp_path / "audit.db"
    with pytest.raises(Exception):
        run_pipeline(raw, db, tmp_path / "processed", tmp_path / "quarantine", tmp_path / "reports" / "report.csv", tmp_path / "logs" / "run.log")
    with sqlite3.connect(db) as conn:
        row = conn.execute("SELECT file_status,input_row_count,error_message,file_hash FROM source_files WHERE file_name='orders.csv'").fetchone()
        run = conn.execute("SELECT status FROM pipeline_runs").fetchone()[0]
    assert row[0] == "FAILED" and row[1] is None and row[2] and len(row[3]) == 64
    assert run == "FAILED"

def test_same_snapshot_rerun_keeps_business_keys_and_separate_attempts(tmp_path):
    raw = _inputs(tmp_path); db = tmp_path / "audit.db"
    run_ids = []
    for attempt in range(2):
        run_ids.append(run_pipeline(raw, db, tmp_path / "processed", tmp_path / "quarantine",
                     tmp_path / f"reports" / f"{attempt}.csv", tmp_path / "logs" / "run.log"))
    with sqlite3.connect(db) as conn:
        runs = conn.execute("SELECT COUNT(*) FROM pipeline_runs").fetchone()[0]
        customers = conn.execute("SELECT COUNT(*) FROM customers").fetchone()[0]
        products = conn.execute("SELECT COUNT(*) FROM products").fetchone()[0]
        orders = conn.execute("SELECT COUNT(*) FROM orders").fetchone()[0]
        artifacts = conn.execute("SELECT COUNT(*) FROM output_artifacts").fetchone()[0]
    assert (runs, customers, products, orders, artifacts) == (2, 1, 1, 1, 6)
    with sqlite3.connect(db) as conn:
        conn.execute("PRAGMA foreign_keys=ON")
        source_ids = [x[0] for x in conn.execute("SELECT source_file_id FROM source_files WHERE run_id=?", (run_ids[1],))]
        artifact_id = conn.execute("SELECT output_artifact_id FROM output_artifacts WHERE run_id=? LIMIT 1", (run_ids[0],)).fetchone()[0]
        base = (run_ids[0], source_ids[0], "location", "customers", 1, "hash")
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute("INSERT INTO data_lineage(run_id,source_file_id,output_location,output_table,output_row_count,output_hash,output_artifact_id,dependency_role) VALUES(?,?,?,?,?,?,?,'PRIMARY_SOURCE')", (*base, "NONEXISTENT_ARTIFACT"))
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute("INSERT INTO data_lineage(run_id,source_file_id,output_location,output_table,output_row_count,output_hash,output_artifact_id,dependency_role) VALUES(?,?,?,?,?,?,?,'PRIMARY_SOURCE')", (*base, artifact_id))

def test_report_failure_marks_run_failed(tmp_path, monkeypatch):
    raw = _inputs(tmp_path); db = tmp_path / "audit.db"
    import src.main as main
    monkeypatch.setattr(main, "export_audit_report", lambda *args: (_ for _ in ()).throw(OSError("controlled report failure")))
    with pytest.raises(OSError, match="controlled report failure"):
        run_pipeline(raw, db, tmp_path / "processed", tmp_path / "quarantine", tmp_path / "reports" / "report.csv", tmp_path / "logs" / "run.log")
    with sqlite3.connect(db) as conn:
        status, error = conn.execute("SELECT status,error_message FROM pipeline_runs").fetchone()
    assert status == "FAILED" and "controlled report failure" in error
