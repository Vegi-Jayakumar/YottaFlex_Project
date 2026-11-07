from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = BASE_DIR / "data"
RAW_DIR = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"
QUARANTINE_DIR = DATA_DIR / "quarantine"
DB_PATH = BASE_DIR / "dataflow_audit.db"
LOG_DIR = BASE_DIR / "logs"
LOG_PATH = LOG_DIR / "pipeline.log"

REQUIRED_COLUMNS = {
    "customers": ["customer_id", "customer_name", "city"],
    "products": ["product_id", "product_name", "unit_price"],
    "orders": ["order_id", "customer_id", "product_id", "quantity", "order_date"],
}
