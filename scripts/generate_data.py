import argparse
from pathlib import Path
import numpy as np
import pandas as pd

def generate(output_dir, rows=1000, seed=42):
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(seed)

    n_customers = max(10, min(rows, rows // 5 or 10))
    n_products = max(5, min(100, rows // 20 or 5))

    customers = pd.DataFrame({
        "customer_id": [f"C{i:06d}" for i in range(1, n_customers + 1)],
        "customer_name": [f"Customer {i}" for i in range(1, n_customers + 1)],
        "city": rng.choice(["Hyderabad", "Chennai", "Bengaluru", "Mumbai"], n_customers),
    })
    products = pd.DataFrame({
        "product_id": [f"P{i:04d}" for i in range(1, n_products + 1)],
        "product_name": [f"Product {i}" for i in range(1, n_products + 1)],
        "unit_price": rng.uniform(100, 50000, n_products).round(2),
    })
    orders = pd.DataFrame({
        "order_id": [f"O{i:07d}" for i in range(1, rows + 1)],
        "customer_id": rng.choice(customers["customer_id"], rows),
        "product_id": rng.choice(products["product_id"], rows),
        "quantity": rng.integers(1, 6, rows),
        "order_date": pd.to_datetime("2026-01-01") +
                      pd.to_timedelta(rng.integers(0, 300, rows), unit="D"),
    })
    orders["order_date"] = orders["order_date"].dt.strftime("%Y-%m-%d")

    # Add a small, reproducible set of invalid records when enough rows exist.
    if rows >= 20:
        orders.loc[0, "quantity"] = -2
        orders.loc[1, "customer_id"] = "C_UNKNOWN"
        orders.loc[2, "order_date"] = "not-a-date"
        orders.loc[3, "order_id"] = orders.loc[4, "order_id"]  # duplicate key
        orders.loc[5, "customer_id"] = np.nan

    customers.to_csv(output_dir / "customers.csv", index=False)
    products.to_csv(output_dir / "products.csv", index=False)
    orders.to_csv(output_dir / "orders.csv", index=False)
    print(f"Generated {rows} orders in {output_dir}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", default="data/raw")
    parser.add_argument("--rows", type=int, default=1000)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    generate(args.output_dir, args.rows, args.seed)
