# DataFlow Data Dictionary

## Entities & Schemas

### 1. Customers (`customers.csv` -> `customers` table)
* `customer_id`: TEXT (Primary Key). Format: `C######` (e.g., `C000001`). Preserved as string with leading zeros.
* `customer_name`: TEXT. Full name of the customer.
* `city`: TEXT. City of residence.

### 2. Products (`products.csv` -> `products` table)
* `product_id`: TEXT (Primary Key). Format: `P###` (e.g., `P001`).
* `product_name`: TEXT. Name of the item.
* `unit_price`: REAL. Price per unit. Must be finite (`> 0`, `np.isfinite`).

### 3. Orders (`orders.csv` -> `orders` table)
* `order_id`: TEXT (Primary Key). Unique transaction/order identifier.
* `customer_id`: TEXT (Foreign Key -> `customers.customer_id`).
* `product_id`: TEXT (Foreign Key -> `products.product_id`).
* `quantity`: INTEGER. Number of units purchased. Must be positive (`> 0`).
* `order_date`: TEXT. ISO-8601 date string (`YYYY-MM-DD`).
* `total_amount`: REAL. Calculated as `quantity * unit_price`, rounded to 2 decimal places.
