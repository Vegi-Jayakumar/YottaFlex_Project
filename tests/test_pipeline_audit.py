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
    assert run == ("PARTIAL_SUCCESS", 4, 3, 1)
    assert issue_count == 2
    assert roles == {"PRIMARY_SOURCE", "PRICE_LOOKUP", "REFERENCE_VALIDATION"}
    assert sources == ("READ", 2)

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
    for attempt in range(2):
        run_pipeline(raw, db, tmp_path / "processed", tmp_path / "quarantine",
                     tmp_path / f"reports" / f"{attempt}.csv", tmp_path / "logs" / "run.log")
    with sqlite3.connect(db) as conn:
        runs = conn.execute("SELECT COUNT(*) FROM pipeline_runs").fetchone()[0]
        customers = conn.execute("SELECT COUNT(*) FROM customers").fetchone()[0]
        products = conn.execute("SELECT COUNT(*) FROM products").fetchone()[0]
        orders = conn.execute("SELECT COUNT(*) FROM orders").fetchone()[0]
        artifacts = conn.execute("SELECT COUNT(*) FROM output_artifacts").fetchone()[0]
    assert (runs, customers, products, orders, artifacts) == (2, 1, 1, 1, 6)

def test_report_failure_marks_run_failed(tmp_path, monkeypatch):
    raw = _inputs(tmp_path); db = tmp_path / "audit.db"
    import src.main as main
    monkeypatch.setattr(main, "export_audit_report", lambda *args: (_ for _ in ()).throw(OSError("controlled report failure")))
    with pytest.raises(OSError, match="controlled report failure"):
        run_pipeline(raw, db, tmp_path / "processed", tmp_path / "quarantine", tmp_path / "reports" / "report.csv", tmp_path / "logs" / "run.log")
    with sqlite3.connect(db) as conn:
        status, error = conn.execute("SELECT status,error_message FROM pipeline_runs").fetchone()
    assert status == "FAILED" and "controlled report failure" in error
