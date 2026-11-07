import time
import pandas as pd

def transform_entity(df, entity):
    """Apply deterministic, vectorized standardization."""
    started = time.perf_counter()
    result = df.copy()

    for col in result.select_dtypes(include=["object", "string"]).columns:
        result[col] = result[col].astype("string").str.strip()

    if entity == "products":
        result["unit_price"] = pd.to_numeric(result["unit_price"]).round(2)

    elapsed = time.perf_counter() - started
    return result, elapsed

def enrich_orders(orders, products):
    """Add unit price and total amount using product reference data."""
    result = orders.merge(
        products[["product_id", "unit_price"]],
        on="product_id",
        how="left",
        validate="many_to_one",
    )
    result["total_amount"] = (result["quantity"] * result["unit_price"]).round(2)
    return result
