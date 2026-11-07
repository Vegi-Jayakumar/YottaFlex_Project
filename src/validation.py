import json
import pandas as pd
from .config import REQUIRED_COLUMNS

def validate_schema(df, entity):
    required = REQUIRED_COLUMNS[entity]
    missing = [column for column in required if column not in df.columns]
    if missing:
        raise ValueError(f"{entity}: missing required columns: {missing}")

def validate_entity(df, entity, source_file):
    """
    Returns (valid_df, rejects).
    Reject rows are dictionaries with source_record_id, issue_type,
    issue_description and raw_record.
    """
    validate_schema(df, entity)
    data = df.copy()
    rejects = []

    id_col = {
        "customers": "customer_id",
        "products": "product_id",
        "orders": "order_id",
    }[entity]

    # Preserve original row number as traceable source record identifier.
    data["_source_record_id"] = range(1, len(data) + 1)

    for col in REQUIRED_COLUMNS[entity]:
        data[col] = data[col].replace(r"^\s*$", pd.NA, regex=True)

    def reject(index, issue_type, description):
        row = data.loc[index]
        rejects.append({
            "source_record_id": row["_source_record_id"],
            "issue_type": issue_type,
            "issue_description": description,
            "raw_record": json.dumps(row.drop(labels=["_source_record_id"]).to_dict(),
                                     default=str),
        })

    for idx, row in data.iterrows():
        if pd.isna(row[id_col]):
            reject(idx, "MISSING_KEY", f"{id_col} is required")

    data = data.dropna(subset=[id_col])

    duplicate_mask = data[id_col].duplicated(keep="first")
    for idx in data.index[duplicate_mask]:
        reject(idx, "DUPLICATE_KEY", f"Duplicate {id_col}: {data.loc[idx, id_col]}")
    data = data.loc[~duplicate_mask].copy()

    if entity == "customers":
        for idx, row in data.iterrows():
            if pd.isna(row["customer_name"]) or pd.isna(row["city"]):
                reject(idx, "MISSING_REQUIRED_VALUE", "customer_name and city are required")
        data = data.dropna(subset=["customer_name", "city"])

    elif entity == "products":
        data["unit_price"] = pd.to_numeric(data["unit_price"], errors="coerce")
        bad = data["unit_price"].isna() | (data["unit_price"] < 0)
        for idx in data.index[bad]:
            reject(idx, "INVALID_PRICE", "unit_price must be a non-negative number")
        data = data.loc[~bad].copy()
        data["product_name"] = data["product_name"].astype("string").str.strip()
        bad_name = data["product_name"].isna() | (data["product_name"] == "")
        for idx in data.index[bad_name]:
            reject(idx, "MISSING_REQUIRED_VALUE", "product_name is required")
        data = data.loc[~bad_name].copy()

    elif entity == "orders":
        data["quantity"] = pd.to_numeric(data["quantity"], errors="coerce")
        data["order_date"] = pd.to_datetime(data["order_date"], errors="coerce")
        bad_qty = data["quantity"].isna() | (data["quantity"] <= 0) | (data["quantity"] % 1 != 0)
        bad_date = data["order_date"].isna()
        for idx in data.index[bad_qty]:
            reject(idx, "INVALID_QUANTITY", "quantity must be a positive integer")
        for idx in data.index[bad_date]:
            reject(idx, "INVALID_DATE", "order_date must be a valid date")
        data = data.loc[~(bad_qty | bad_date)].copy()
        data["quantity"] = data["quantity"].astype(int)
        data["order_date"] = data["order_date"].dt.strftime("%Y-%m-%d")

    data = data.drop(columns=["_source_record_id"])
    return data.reset_index(drop=True), rejects
