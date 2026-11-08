import sqlite3
import math
import numpy as np
import pandas as pd
from .database import get_connection

TABLE_COLUMNS = {
    "customers": ["customer_id", "customer_name", "city"],
    "products": ["product_id", "product_name", "unit_price"],
    "orders": ["order_id", "customer_id", "product_id", "quantity",
               "order_date", "total_amount"],
}

def normalize_sqlite_scalar(value):
    """Convert pandas/NumPy scalars to SQLite-native values at the bind boundary."""
    if value is None or value is pd.NA or value is pd.NaT:
        return None
    if isinstance(value, np.generic):
        value = value.item()
    if value is None:
        return None
    if isinstance(value, float) and math.isnan(value):
        return None
    if isinstance(value, (bool, int, float, str, bytes)):
        return value
    # pandas may expose scalar missing values from extension arrays.
    try:
        missing = pd.isna(value)
        if isinstance(missing, (bool, np.bool_)) and missing:
            return None
    except (TypeError, ValueError):
        pass
    if hasattr(value, "item"):
        native = value.item()
        if native is not value:
            return normalize_sqlite_scalar(native)
    return value

def upsert_dataframe(df, table, run_id, source_file, db_path):
    """Upsert records by stable business key inside a transaction."""
    if df.empty:
        return 0

    columns = TABLE_COLUMNS[table]
    key = columns[0]
    insert_cols = columns + ["source_file", "run_id"]
    placeholders = ", ".join(["?"] * len(insert_cols))
    updates = ", ".join(
        f"{col}=excluded.{col}" for col in columns[1:] + ["source_file", "run_id"]
    )
    sql = (
        f"INSERT INTO {table} ({', '.join(insert_cols)}) "
        f"VALUES ({placeholders}) "
        f"ON CONFLICT({key}) DO UPDATE SET {updates}"
    )

    records = []
    for row in df[columns].itertuples(index=False, name=None):
        normalized = tuple(normalize_sqlite_scalar(value) for value in row)
        if table == "orders" and type(normalized[3]) is not int:
            raise TypeError(f"orders.quantity must bind as Python int, got {type(normalized[3]).__name__}")
        records.append(normalized + (source_file, run_id))

    with get_connection(db_path) as conn:
        conn.executemany(sql, records)
    return len(records)

def check_references(orders, customers, products):
    """Return order rows with missing customer or product references."""
    bad_customer = ~orders["customer_id"].isin(customers["customer_id"])
    bad_product = ~orders["product_id"].isin(products["product_id"])
    return orders.loc[bad_customer | bad_product].copy()
