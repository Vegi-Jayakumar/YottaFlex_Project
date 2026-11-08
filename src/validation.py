import json
import re
import numpy as np
import pandas as pd
from .config import REQUIRED_COLUMNS

ID_PATTERNS = {
    "customers": re.compile(r"^C\d{6}$"),
    "products": re.compile(r"^P\d{4}$"),
    "orders": re.compile(r"^O\d{7}$"),
}

def validate_schema(df, entity):
    required = REQUIRED_COLUMNS[entity]
    missing = [column for column in required if column not in df.columns]
    if missing:
        raise ValueError(f"{entity}: missing required columns: {missing}")
    extras = sorted(set(df.columns) - set(required))
    if extras:
        raise ValueError(f"{entity}: unexpected columns: {extras}")

def validate_entity(df, entity, source_file):
    """Return valid rows and issue records with immutable source provenance."""
    validate_schema(df, entity)
    data = df.copy()
    data["_source_record_number"] = np.arange(1, len(data) + 1)
    # Raw values are captured before trimming, numeric conversion, or date parsing.
    raw = {idx: json.dumps(row.to_dict(), ensure_ascii=False, default=str)
           for idx, row in data.drop(columns=["_source_record_number"]).iterrows()}
    data["_raw_record"] = pd.Series(raw)
    rejects = []
    issue_indexes = set()
    id_col = {"customers": "customer_id", "products": "product_id", "orders": "order_id"}[entity]

    for col in REQUIRED_COLUMNS[entity]:
        data[col] = data[col].astype("string").str.strip().replace("", pd.NA)

    def reject(index, issue_type, description):
        rejects.append({"source_record_number": int(data.at[index, "_source_record_number"]),
                        "source_record_id": str(data.at[index, "_source_record_number"]),
                        "issue_type": issue_type, "issue_description": description,
                        "raw_record": raw[index]})
        issue_indexes.add(index)

    missing = data[id_col].isna()
    for idx in data.index[missing]: reject(idx, "MISSING_KEY", f"{id_col} is required")
    bad_format = data[id_col].notna() & ~data[id_col].str.match(ID_PATTERNS[entity])
    for idx in data.index[bad_format]: reject(idx, "INVALID_ID_FORMAT", f"{id_col} does not match the declared format")
    canonical = data[id_col].str.strip()
    dup = canonical.notna() & canonical.duplicated(keep="first")
    for idx in data.index[dup]: reject(idx, "DUPLICATE_KEY", f"Duplicate canonical {id_col}: {canonical.loc[idx]}")
    data[id_col] = canonical

    if entity == "customers":
        bad = data["customer_name"].isna() | data["city"].isna()
        for idx in data.index[bad]: reject(idx, "MISSING_REQUIRED_VALUE", "customer_name and city are required")
    elif entity == "products":
        data["unit_price"] = pd.to_numeric(data["unit_price"], errors="coerce")
        bad = data["unit_price"].isna() | (data["unit_price"] < 0) | ~np.isfinite(data["unit_price"])
        for idx in data.index[bad]: reject(idx, "INVALID_PRICE", "unit_price must be a finite non-negative number")
        bad_name = data["product_name"].isna()
        for idx in data.index[bad_name]: reject(idx, "MISSING_REQUIRED_VALUE", "product_name is required")
    else:
        data["quantity"] = pd.to_numeric(data["quantity"], errors="coerce")
        dates = pd.to_datetime(data["order_date"], errors="coerce")
        bad_qty = data["quantity"].isna() | (data["quantity"] <= 0) | (data["quantity"] % 1 != 0) | ~np.isfinite(data["quantity"])
        bad_date = dates.isna()
        for idx in data.index[bad_qty]: reject(idx, "INVALID_QUANTITY", "quantity must be a positive integer")
        for idx in data.index[bad_date]: reject(idx, "INVALID_DATE", "order_date must be a valid date")
        data["order_date"] = dates.dt.strftime("%Y-%m-%d")
        data["quantity"] = data["quantity"].where(~bad_qty).astype("Int64")

    valid = data.loc[~data.index.isin(issue_indexes)].copy()
    for issue in rejects:
        index = issue_indexes and next(idx for idx in data.index
                                       if int(data.at[idx, "_source_record_number"]) == issue["source_record_number"])
        diagnostics = data.loc[index].drop(labels=["_source_record_number", "_raw_record"]).to_dict()
        issue["diagnostic_record"] = json.dumps(
            {key: (None if pd.isna(value) else value) for key, value in diagnostics.items()},
            ensure_ascii=False, default=str)
    # Internal provenance remains through reference validation and is removed before publication.
    return valid.reset_index(drop=True), rejects
