import pandas as pd
from src.transformation import enrich_orders, transform_entity

def test_product_transform_rounds_price_and_trims():
    df = pd.DataFrame([{"product_id": "P1", "product_name": " Mouse ",
                        "unit_price": 12.356}])
    result, _ = transform_entity(df, "products")
    assert result.loc[0, "product_name"] == "Mouse"
    assert result.loc[0, "unit_price"] == 12.36

def test_order_total_amount():
    orders = pd.DataFrame([{
        "order_id": "O1", "customer_id": "C1", "product_id": "P1",
        "quantity": 2, "order_date": "2026-01-01"
    }])
    products = pd.DataFrame([{"product_id": "P1", "unit_price": 50.0}])
    result = enrich_orders(orders, products)
    assert result.loc[0, "total_amount"] == 100.0
