import argparse
import logging
import time
import uuid
from pathlib import Path
import pandas as pd

from .config import RAW_DIR, PROCESSED_DIR, QUARANTINE_DIR, DB_PATH, LOG_DIR, LOG_PATH
from .database import initialize_database
from .ingestion import discover_csv_files, read_csv, sha256_file
from .audit_logger import (
    start_run, finish_run, log_source_file, log_transformation,
    log_issue, log_lineage,
)
from .validation import validate_entity
from .transformation import transform_entity, enrich_orders
from .loading import upsert_dataframe, check_references
from .reconciliation import export_audit_report

def configure_logging():
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        filename=LOG_PATH, level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )

def run_pipeline(raw_dir=RAW_DIR, db_path=DB_PATH):
    initialize_database(db_path)
    configure_logging()
    run_id = str(uuid.uuid4())
    start_clock = time.perf_counter()
    input_rows = output_rows = rejected_rows = 0
    status = "SUCCESS"
    error_message = None

    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    QUARANTINE_DIR.mkdir(parents=True, exist_ok=True)

    start_run(run_id, db_path)
    logging.info("Starting run_id=%s", run_id)

    try:
        frames = {}
        source_ids = {}
        entity_files = {p.stem: p for p in discover_csv_files(raw_dir)}

        for entity in ("customers", "products", "orders"):
            if entity not in entity_files:
                raise FileNotFoundError(f"Required input file not found: {entity}.csv")

            path = entity_files[entity]
            df = read_csv(path)
            input_rows += len(df)
            source_ids[entity] = log_source_file(
                run_id, db_path, path.name, str(path.resolve()),
                sha256_file(path), len(df)
            )

            valid, rejects = validate_entity(df, entity, path.name)
            rejected_rows += len(rejects)

            for issue in rejects:
                log_issue(
                    run_id, db_path, path.name, issue["source_record_id"],
                    issue["issue_type"], issue["issue_description"], issue["raw_record"]
                )

            reject_path = QUARANTINE_DIR / f"{run_id}_{entity}_rejects.csv"
            if rejects:
                pd.DataFrame(rejects).to_csv(reject_path, index=False)

            transformed, elapsed = transform_entity(valid, entity)
            log_transformation(
                run_id, db_path, f"standardize_{entity}",
                "Trim text and normalize entity values",
                len(transformed), elapsed
            )
            frames[entity] = transformed

        # Validate cross-entity references before publishing orders.
        bad_orders = check_references(
            frames["orders"], frames["customers"], frames["products"]
        )
        if not bad_orders.empty:
            rejected_rows += len(bad_orders)
            for row in bad_orders.to_dict("records"):
                reason = []
                if row["customer_id"] not in set(frames["customers"]["customer_id"]):
                    reason.append("unknown customer_id")
                if row["product_id"] not in set(frames["products"]["product_id"]):
                    reason.append("unknown product_id")
                log_issue(
                    run_id, db_path, entity_files["orders"].name, row["order_id"],
                    "INVALID_REFERENCE", ", ".join(reason), str(row)
                )
            frames["orders"] = frames["orders"].loc[
                ~frames["orders"]["order_id"].isin(bad_orders["order_id"])
            ].copy()

        # Load dimensions before facts to satisfy foreign keys.
        for entity in ("customers", "products"):
            count = upsert_dataframe(
                frames[entity], entity, run_id,
                entity_files[entity].name, db_path
            )
            output_rows += count
            out_path = PROCESSED_DIR / f"{run_id}_{entity}.csv"
            frames[entity].to_csv(out_path, index=False)
            log_lineage(
                run_id, db_path, source_ids[entity], out_path,
                entity, count, sha256_file(out_path)
            )

        enriched_orders = enrich_orders(frames["orders"], frames["products"])
        enriched_orders = enriched_orders.drop(columns=["unit_price"])
        count = upsert_dataframe(
            enriched_orders, "orders", run_id,
            entity_files["orders"].name, db_path
        )
        output_rows += count
        out_path = PROCESSED_DIR / f"{run_id}_orders.csv"
        enriched_orders.to_csv(out_path, index=False)
        log_lineage(
            run_id, db_path, source_ids["orders"], out_path,
            "orders", count, sha256_file(out_path)
        )

        if rejected_rows > 0:
            status = "PARTIAL_SUCCESS"
        logging.info("Completed run_id=%s status=%s", run_id, status)

    except Exception as exc:
        status = "FAILED"
        error_message = f"{type(exc).__name__}: {exc}"
        logging.exception("Pipeline failed run_id=%s", run_id)
        raise
    finally:
        finish_run(
            run_id, db_path, status, input_rows, output_rows,
            rejected_rows, start_clock, error_message
        )
        report_dir = Path(__file__).resolve().parents[1] / "reports"
        report_dir.mkdir(parents=True, exist_ok=True)
        export_audit_report(db_path, report_dir / "audit_report.csv")
    return run_id

def main():
    parser = argparse.ArgumentParser(description="Run the DataFlow ETL pipeline")
    parser.add_argument("--raw-dir", type=Path, default=RAW_DIR)
    parser.add_argument("--db-path", type=Path, default=DB_PATH)
    args = parser.parse_args()
    run_id = run_pipeline(args.raw_dir, args.db_path)
    print(f"Pipeline completed. run_id={run_id}")

if __name__ == "__main__":
    main()
