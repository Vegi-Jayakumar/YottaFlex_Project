import sqlite3
from .database import get_connection

TABLE_COLUMNS = {
    "customers": ["customer_id", "customer_name", "city"],
    "products": ["product_id", "product_name", "unit_price"],
    "orders": ["order_id", "customer_id", "product_id", "quantity",
               "order_date", "total_amount"],
}

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
        records.append(tuple(row) + (source_file, run_id))

    with get_connection(db_path) as conn:
        conn.executemany(sql, records)
    return len(records)

def check_references(orders, customers, products):
    """Return order rows with missing customer or product references."""
    bad_customer = ~orders["customer_id"].isin(customers["customer_id"])
    bad_product = ~orders["product_id"].isin(products["product_id"])
    return orders.loc[bad_customer | bad_product].copy()
