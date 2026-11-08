import pandas as pd
import pytest
from src.validation import validate_entity

def test_valid_customer_passes():
    df = pd.DataFrame([{
        "customer_id": "C000001", "customer_name": "A", "city": "Hyderabad"
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
        "order_id": "O0000001", "customer_id": "C000001", "product_id": "P0001",
        "quantity": -1, "order_date": "2026-01-01"
    }])
    valid, rejects = validate_entity(df, "orders", "orders.csv")
    assert valid.empty
    assert any(x["issue_type"] == "INVALID_QUANTITY" for x in rejects)

def test_one_row_can_have_two_issues_but_one_provenance_number():
    df = pd.DataFrame([{"order_id":"O0000001", "customer_id":"C000001",
                        "product_id":"P0001", "quantity":-1, "order_date":"bad"}])
    valid, rejects = validate_entity(df, "orders", "orders.csv")
    assert valid.empty
    assert {x["issue_type"] for x in rejects} == {"INVALID_QUANTITY", "INVALID_DATE"}
    assert {x["source_record_number"] for x in rejects} == {1}
    assert all('"order_date": "bad"' in x["raw_record"] for x in rejects)

def test_nonfinite_price_rejected_and_zero_allowed():
    df = pd.DataFrame([{"product_id":"P0001", "product_name":"Zero", "unit_price":"0"},
                       {"product_id":"P0002", "product_name":"Bad", "unit_price":"inf"}])
    valid, rejects = validate_entity(df, "products", "products.csv")
    assert valid["product_id"].tolist() == ["P0001"]
    assert rejects[0]["issue_type"] == "INVALID_PRICE"

def test_missing_schema_column_raises():
    df = pd.DataFrame([{"customer_id": "C1"}])
    with pytest.raises(ValueError):
        validate_entity(df, "customers", "customers.csv")
