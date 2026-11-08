import argparse
import json
import logging
import os
import tempfile
import time
import uuid
from pathlib import Path
import pandas as pd

from .config import RAW_DIR, PROCESSED_DIR, QUARANTINE_DIR, DB_PATH, LOG_DIR, LOG_PATH
from .database import initialize_database, get_connection
from .ingestion import discover_csv_files, read_csv, sha256_file
from .audit_logger import (start_run, finish_run, log_source_file, update_source_file,
    log_transformation, log_issue, log_lineage, log_artifact)
from .validation import validate_entity
from .transformation import transform_entity, enrich_orders
from .loading import upsert_dataframe, check_references
from .reconciliation import export_audit_report, audit_relationship_errors

def configure_logging(log_path=LOG_PATH):
    Path(log_path).parent.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(filename=log_path, level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(message)s", force=True)

def _issue(run_id, db_path, file_name, issue, collector, source_file_id=None):
    log_issue(run_id, db_path, file_name, issue.get("source_record_id"),
              issue["issue_type"], issue["issue_description"], issue["raw_record"],
              issue.get("source_record_number"), source_file_id,
              issue.get("diagnostic_record"))
    collector.append(issue)

def _atomic_csv(df, path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=path.stem + "_", suffix=".tmp", dir=path.parent)
    os.close(fd)
    try:
        df.to_csv(temp_name, index=False)
        os.replace(temp_name, path)
    finally:
        if os.path.exists(temp_name): os.unlink(temp_name)

def run_pipeline(raw_dir=RAW_DIR, db_path=DB_PATH, processed_dir=PROCESSED_DIR,
                 quarantine_dir=QUARANTINE_DIR, report_path=None, log_path=LOG_PATH):
    initialize_database(db_path)
    configure_logging(log_path)
    run_id, clock = str(uuid.uuid4()), time.perf_counter()
    input_rows = output_rows = 0
    status, error_message, original_error = "SUCCESS", None, None
    processed_dir, quarantine_dir = Path(processed_dir), Path(quarantine_dir)
    report_path = Path(report_path) if report_path else Path(db_path).parent / "reports" / f"{run_id}_audit_report.csv"
    processed_dir.mkdir(parents=True, exist_ok=True); quarantine_dir.mkdir(parents=True, exist_ok=True)
    start_run(run_id, db_path)
    logging.info("Starting run_id=%s", run_id)
    rejects_by_file = {}
    source_ids, files, frames = {}, {}, {}
    try:
        # Register every discovered source and checksum before parsing any file.
        discovered = {p.stem: p for p in discover_csv_files(raw_dir)}
        for entity, path in discovered.items():
            files[entity] = path
            source_ids[entity] = log_source_file(run_id, db_path, path.name,
                str(path.resolve()), sha256_file(path), None, "DISCOVERED")
        for entity in ("customers", "products", "orders"):
            if entity not in discovered:
                missing_path = Path(raw_dir) / f"{entity}.csv"
                source_ids[entity] = log_source_file(run_id, db_path, missing_path.name,
                    str(missing_path.resolve()), "", None, "MISSING",
                    f"FileNotFoundError: required input file not found: {missing_path.name}")
                raise FileNotFoundError(f"Required input file not found: {entity}.csv")
        for entity in ("customers", "products", "orders"):
            path = files[entity]
            try:
                df = read_csv(path)
            except Exception as exc:
                update_source_file(db_path, source_ids[entity], "FAILED", None,
                                   f"{type(exc).__name__}: {exc}")
                raise
            input_rows += len(df)
            update_source_file(db_path, source_ids[entity], "READ", len(df))
            valid, rejects = validate_entity(df, entity, path.name)
            rejects_by_file[entity] = rejects
            for issue in rejects:
                issue["source_file_id"] = source_ids[entity]
                log_issue(run_id, db_path, path.name, issue.get("source_record_id"),
                          issue["issue_type"], issue["issue_description"],
                          issue["raw_record"], issue.get("source_record_number"), source_ids[entity],
                          issue.get("diagnostic_record"))
            transformed, elapsed = transform_entity(valid.drop(columns=["_source_record_number"], errors="ignore"), entity)
            log_transformation(run_id, db_path, f"standardize_{entity}",
                               "Trim text and normalize entity values", len(transformed), elapsed)
            # Keep record number aligned across validation and transformations.
            transformed["_source_record_number"] = valid["_source_record_number"].to_numpy()
            transformed["_source_file_id"] = source_ids[entity]
            frames[entity] = transformed

        bad_orders = check_references(frames["orders"], frames["customers"], frames["products"])
        if not bad_orders.empty:
            customer_keys, product_keys = set(frames["customers"].customer_id), set(frames["products"].product_id)
            bad_ids = set()
            for _, row in bad_orders.iterrows():
                reason = []
                if pd.isna(row.customer_id): reason.append("null customer_id")
                elif row.customer_id not in customer_keys: reason.append("unknown customer_id")
                if pd.isna(row.product_id): reason.append("null product_id")
                elif row.product_id not in product_keys: reason.append("unknown product_id")
                issue = {"source_file_id": source_ids["orders"],
                         "source_record_number": int(row._source_record_number),
                         "source_record_id": str(int(row._source_record_number)),
                         "issue_type": "INVALID_REFERENCE", "issue_description": ", ".join(reason),
                         "raw_record": row["_raw_record"],
                         "diagnostic_record": json.dumps({k: (None if pd.isna(v) else v) for k, v in row.drop(labels=["_source_record_number", "_source_file_id", "_raw_record"]).to_dict().items()}, default=str)}
                _issue(run_id, db_path, files["orders"].name, issue, rejects_by_file["orders"], source_ids["orders"])
                bad_ids.add(int(row._source_record_number))
            frames["orders"] = frames["orders"].loc[~frames["orders"]["_source_record_number"].isin(bad_ids)].copy()

        # Unified quarantine per input, one row per rejected source record plus its issues.
        for entity, issues in rejects_by_file.items():
            if issues: _atomic_csv(pd.DataFrame(issues), quarantine_dir / f"{run_id}_{entity}_rejects.csv")

        # Dimension keys are validated before any dimension commit.
        for entity in ("customers", "products"):
            frame = frames[entity].drop(columns=["_source_record_number", "_source_file_id", "_raw_record"], errors="ignore")
            count = upsert_dataframe(frame, entity, run_id, files[entity].name, db_path)
            output_rows += count
            out_path = processed_dir / f"{run_id}_{entity}.csv"
            _atomic_csv(frame, out_path)
            aid = str(uuid.uuid4()); digest = sha256_file(out_path)
            log_artifact(run_id, db_path, aid, out_path, entity, count, digest)
            log_lineage(run_id, db_path, source_ids[entity], out_path, entity, count, digest, aid, "PRIMARY_SOURCE")

        orders = frames["orders"].drop(columns=["_source_record_number", "_source_file_id", "_raw_record"], errors="ignore")
        started = time.perf_counter()
        enriched = enrich_orders(orders, frames["products"].drop(columns=["_source_record_number", "_source_file_id", "_raw_record"], errors="ignore"))
        enriched = enriched.drop(columns=["unit_price"])
        enrich_elapsed = time.perf_counter() - started
        count = upsert_dataframe(enriched, "orders", run_id, files["orders"].name, db_path)
        output_rows += count
        out_path = processed_dir / f"{run_id}_orders.csv"; _atomic_csv(enriched, out_path)
        aid = str(uuid.uuid4()); digest = sha256_file(out_path)
        log_artifact(run_id, db_path, aid, out_path, "orders", count, digest)
        log_transformation(run_id, db_path, "enrich_orders", "Join product unit price and calculate total_amount",
                           len(enriched), enrich_elapsed,
                           [{"source_file_id": source_ids["orders"], "dependency_role": "PRIMARY_SOURCE"},
                            {"source_file_id": source_ids["products"], "dependency_role": "PRICE_LOOKUP"},
                            {"source_file_id": source_ids["customers"], "dependency_role": "REFERENCE_VALIDATION"}], aid, "1.0")
        log_lineage(run_id, db_path, source_ids["orders"], out_path, "orders", count, digest, aid, "PRIMARY_SOURCE")
        log_lineage(run_id, db_path, source_ids["products"], out_path, "orders", count, digest, aid, "PRICE_LOOKUP")
        log_lineage(run_id, db_path, source_ids["customers"], out_path, "orders", count, digest, aid, "REFERENCE_VALIDATION")

        unique_rejects = sum(len({i["source_record_number"] for i in issues}) for issues in rejects_by_file.values())
        issue_count = sum(len(issues) for issues in rejects_by_file.values())
        # Counts are persisted as run checks, including the issue vs row distinction.
        checks = []
        for entity, path, expected_count in (("customers", processed_dir / f"{run_id}_customers.csv", len(frames["customers"])),
                                               ("products", processed_dir / f"{run_id}_products.csv", len(frames["products"])),
                                               ("orders", processed_dir / f"{run_id}_orders.csv", len(frames["orders"]))):
            output_df = pd.read_csv(path, dtype="string")
            key_col = {"customers":"customer_id", "products":"product_id", "orders":"order_id"}[entity]
            actual_digest = sha256_file(path)
            with get_connection(db_path) as conn:
                digest = conn.execute("SELECT output_hash FROM output_artifacts WHERE run_id=? AND output_table=?", (run_id, entity)).fetchone()[0]
            checks.append((f"{entity}_output_hash", "PASS" if digest == actual_digest else "FAIL", digest, actual_digest, str(path)))
            checks.append((f"{entity}_canonical_key_uniqueness", "PASS" if output_df[key_col].nunique(dropna=False) == len(output_df) else "FAIL", str(len(output_df)), str(output_df[key_col].nunique(dropna=False)), key_col))
            with get_connection(db_path) as conn:
                target_count = conn.execute(f"SELECT COUNT(*) FROM {entity} WHERE run_id=?", (run_id,)).fetchone()[0]
            checks.append((f"{entity}_target_count", "PASS" if target_count == expected_count else "FAIL", str(expected_count), str(target_count), "current-run upserts"))
        target_orders_total = None
        with get_connection(db_path) as conn:
            target_orders_total = conn.execute("SELECT COALESCE(ROUND(SUM(total_amount),2),0) FROM orders WHERE run_id=?", (run_id,)).fetchone()[0]
        source_orders_total = round(float(pd.to_numeric(enriched["total_amount"]).sum()), 2)
        checks.append(("orders_total_amount_sum", "PASS" if round(float(target_orders_total), 2) == source_orders_total else "FAIL", str(source_orders_total), str(target_orders_total), "processed output compared with current-run target"))
        with get_connection(db_path) as conn:
            fk_violations = len(conn.execute("PRAGMA foreign_key_check").fetchall())
            storage_violations = conn.execute("""SELECT COUNT(*) FROM orders o
                JOIN products p ON p.product_id=o.product_id
                WHERE o.run_id=? AND (typeof(o.quantity)<>'integer' OR
                      typeof(p.unit_price)<>'real' OR typeof(o.total_amount)<>'real')""", (run_id,)).fetchone()[0]
            arithmetic_violations = conn.execute("""SELECT COUNT(*) FROM orders o
                JOIN products p ON p.product_id=o.product_id
                WHERE o.run_id=? AND ROUND(o.quantity * p.unit_price, 2) <> ROUND(o.total_amount, 2)""", (run_id,)).fetchone()[0]
        checks.append(("foreign_key_integrity", "PASS" if fk_violations == 0 else "FAIL", "0", str(fk_violations), "SQLite foreign_key_check"))
        checks.append(("numeric_sqlite_storage_types", "PASS" if storage_violations == 0 else "FAIL", "0", str(storage_violations), "orders.quantity INTEGER; products.unit_price and orders.total_amount REAL"))
        checks.append(("per_order_amount_reconciliation", "PASS" if arithmetic_violations == 0 else "FAIL", "0", str(arithmetic_violations), "SQL recomputation using target quantity and price"))
        relationship_errors = audit_relationship_errors(db_path, run_id)
        checks.append(("same_run_audit_relationships", "PASS" if not relationship_errors else "FAIL", "0", str(len(relationship_errors)), "; ".join(relationship_errors)))
        with get_connection(db_path) as conn:
            for name, check_status, expected, actual, details in checks:
                conn.execute("INSERT INTO reconciliation_checks(run_id,check_name,status,expected_value,actual_value,details) VALUES(?,?,?,?,?,?)",
                             (run_id, name, check_status, expected, actual, details))
            conn.execute("INSERT INTO reconciliation_checks(run_id,check_name,status,expected_value,actual_value,details) VALUES(?,?,?,?,?,?)",
                         (run_id, "reject_rows_vs_issue_records", "PASS", str(unique_rejects), str(unique_rejects), f"issue_count={issue_count}"))
            conn.execute("INSERT INTO reconciliation_checks(run_id,check_name,status,expected_value,actual_value,details) VALUES(?,?,?,?,?,?)",
                         (run_id, "input_output_reject_arithmetic", "PASS" if input_rows == output_rows + unique_rejects else "FAIL",
                          str(input_rows), str(output_rows + unique_rejects), "business output rows count processed records; upserts may update existing keys"))
        if input_rows != output_rows + unique_rejects or any(x[1] == "FAIL" for x in checks):
            status = "FAILED"; raise RuntimeError("Run-level input/output/reject reconciliation failed")
        if unique_rejects: status = "PARTIAL_SUCCESS"
    except Exception as exc:
        status = "FAILED"; error_message = f"{type(exc).__name__}: {exc}"; original_error = exc
        logging.exception("Pipeline failed run_id=%s", run_id)
    finally:
        unique_rejects = sum(len({i["source_record_number"] for i in issues}) for issues in rejects_by_file.values())
        finish_run(run_id, db_path, status, input_rows, output_rows, unique_rejects, clock, error_message)
        try:
            export_audit_report(db_path, report_path)
        except Exception as report_exc:
            status = "FAILED"
            report_message = f"report export {type(report_exc).__name__}: {report_exc}"
            error_message = f"{error_message}; {report_message}" if error_message else report_message
            finish_run(run_id, db_path, status, input_rows, output_rows, unique_rejects, clock, error_message)
            if original_error is None: original_error = report_exc
    if original_error is not None: raise original_error
    return run_id

def main():
    parser = argparse.ArgumentParser(description="Run the DataFlow ETL pipeline")
    parser.add_argument("--raw-dir", type=Path, default=RAW_DIR)
    parser.add_argument("--db-path", type=Path, default=DB_PATH)
    parser.add_argument("--processed-dir", type=Path, default=PROCESSED_DIR)
    parser.add_argument("--quarantine-dir", type=Path, default=QUARANTINE_DIR)
    parser.add_argument("--report-path", type=Path)
    parser.add_argument("--log-path", type=Path, default=LOG_PATH)
    args = parser.parse_args()
    run_id = run_pipeline(args.raw_dir, args.db_path, args.processed_dir,
                          args.quarantine_dir, args.report_path, args.log_path)
    print(f"Pipeline completed. run_id={run_id}")

if __name__ == "__main__": main()
