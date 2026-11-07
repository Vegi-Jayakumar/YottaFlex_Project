import pandas as pd
import pytest
from src.validation import validate_entity

def test_valid_customer_passes():
    df = pd.DataFrame([{
        "customer_id": "C1", "customer_name": "A", "city": "Hyderabad"
    }])
    valid, rejects = validate_entity(df, "customers", "customers.csv")
    assert len(valid) == 1
    assert rejects == []

def test_missing_customer_id_is_rejected():
    df = pd.DataFrame([{
        "customer_id": None, "customer_name": "A", "city": "Hyderabad"
    }])
    valid, rejects = validate_entity(df, "customers", "customers.csv")
    assert valid.empty
    assert rejects[0]["issue_type"] == "MISSING_KEY"

def test_negative_order_quantity_is_rejected():
    df = pd.DataFrame([{
        "order_id": "O1", "customer_id": "C1", "product_id": "P1",
        "quantity": -1, "order_date": "2026-01-01"
    }])
    valid, rejects = validate_entity(df, "orders", "orders.csv")
    assert valid.empty
    assert any(x["issue_type"] == "INVALID_QUANTITY" for x in rejects)

def test_missing_schema_column_raises():
    df = pd.DataFrame([{"customer_id": "C1"}])
    with pytest.raises(ValueError):
        validate_entity(df, "customers", "customers.csv")
