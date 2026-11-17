"""Build data/shop.db: a small, reproducible fake e-commerce database."""
import sqlite3
from pathlib import Path
from datetime import date, timedelta
import random

# Where the database file will live: <project>/data/shop.db
DB_PATH = Path(__file__).resolve().parents[1] / "data" / "shop.db"

# The project's fixed "today", so all test situations stay correct
TODAY = date(2026, 11, 17)

SCHEMA = """
CREATE TABLE customers (
    customer_id INTEGER PRIMARY KEY,
    name        TEXT NOT NULL,
    email       TEXT NOT NULL UNIQUE,
    city        TEXT,
    joined_on   TEXT
);

CREATE TABLE products (
    product_id      INTEGER PRIMARY KEY,
    name            TEXT NOT NULL,
    category        TEXT,
    price_eur       REAL,
    warranty_months INTEGER
);

CREATE TABLE orders (
    order_id           TEXT PRIMARY KEY,
    customer_id        INTEGER REFERENCES customers(customer_id),
    order_date         TEXT,
    status             TEXT CHECK (status IN
                         ('processing', 'shipped', 'delivered', 'cancelled', 'returned')),
    shipping_method    TEXT CHECK (shipping_method IN ('standard', 'express')),
    tracking_number    TEXT,
    estimated_delivery TEXT,
    delivered_on       TEXT,
    refund_issued_on   TEXT,
    total_eur          REAL
);

CREATE TABLE order_items (
    order_id       TEXT REFERENCES orders(order_id),
    product_id     INTEGER REFERENCES products(product_id),
    quantity       INTEGER,
    unit_price_eur REAL
);
"""

# (product_id, name, category, price_eur, warranty_months)
PRODUCTS = [
    (1, "Wireless Headphones", "audio",     129.0, 24),
    (2, "Bluetooth Speaker",   "audio",      79.0, 24),
    (3, "Electric Kettle",     "kitchen",    49.0, 24),
    (4, "Espresso Machine",    "kitchen",   399.0, 24),
    (5, "Running Backpack",    "outdoor",    69.0, 12),
    (6, "Smartwatch",          "wearables", 249.0, 24),
    (7, "Laptop 14-inch",      "computers",1199.0, 24),
    (8, "Yoga Mat",            "sports",     35.0,  6),
]


# The 8 test customers, one per test situation
# (customer_id, name, email, city, joined_on)
TEST_CUSTOMERS = [
    (1, "Emma de Vries", "emma.devries@example.com",  "Utrecht",   "2024-03-02"),
    (2, "Lucas Jansen",  "lucas.jansen@example.com",  "Amsterdam", "2023-11-20"),
    (3, "Sophie Bakker", "sophie.bakker@example.com", "Rotterdam", "2025-01-15"),
    (4, "Daan Visser",   "daan.visser@example.com",   "Hilversum", "2025-06-01"),
    (5, "Julia Smit",    "julia.smit@example.com",    "Eindhoven", "2022-09-09"),
    (6, "Noah Meijer",   "noah.meijer@example.com",   "Utrecht",   "2024-07-30"),
    (7, "Mila Mulder",   "mila.mulder@example.com",   "Amsterdam", "2023-04-12"),
    (8, "Tess Bos",      "tess.bos@example.com",      "Hilversum", "2024-10-05"),
]


PRICES = {p[0]: p[3] for p in PRODUCTS}   # product_id -> price, e.g. {1: 129.0, ...}


def days_ago(n):
    """The date n days before TODAY, as text like '2026-11-07'."""
    return (TODAY - timedelta(days=n)).isoformat()


def add_order(con, order_id, customer_id, status, items, ordered_days_ago,
              delivered_days_ago=None, refund_days_ago=None, method="standard"):
    """Insert one order and its items. All dates are given as 'days before TODAY'."""
    order_date = TODAY - timedelta(days=ordered_days_ago)
    delivery_time = 2 if method == "express" else 5          # promised days to deliver
    estimated = (order_date + timedelta(days=delivery_time)).isoformat()

    delivered = days_ago(delivered_days_ago) if delivered_days_ago is not None else None
    refunded = days_ago(refund_days_ago) if refund_days_ago is not None else None

    # Orders get a tracking number once they've left the warehouse
    tracking = None if status in ("processing", "cancelled") else f"TRK-{order_id[4:]}"

    total = 0.0
    for product_id, quantity in items:
        price = PRICES[product_id]
        con.execute("INSERT INTO order_items VALUES (?, ?, ?, ?)",
                    (order_id, product_id, quantity, price))
        total += price * quantity

    con.execute("INSERT INTO orders VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (order_id, customer_id, order_date.isoformat(), status, method,
                 tracking, estimated, delivered, refunded, round(total, 2)))


def add_test_orders(con):
    """One order per test situation (see the table in the README)."""
    # 1. Emma: delivered 10 days ago -> return allowed
    add_order(con, "ORD-1001", 1, "delivered", [(1, 1)], ordered_days_ago=14, delivered_days_ago=10)
    # 2. Lucas: delivered 45 days ago -> return NOT allowed
    add_order(con, "ORD-1002", 2, "delivered", [(3, 1)], ordered_days_ago=50, delivered_days_ago=45)
    # 3. Sophie: shipped, expected 7 days ago, not arrived -> escalate
    add_order(con, "ORD-1003", 3, "shipped", [(2, 1)], ordered_days_ago=12)
    # 4. Daan: still processing, ordered today -> can be cancelled
    add_order(con, "ORD-1004", 4, "processing", [(5, 1), (8, 1)], ordered_days_ago=0)
    # 5. Julia: espresso machine delivered ~14 months ago -> warranty valid
    add_order(con, "ORD-1005", 5, "delivered", [(4, 1)], ordered_days_ago=430, delivered_days_ago=427)
    # 6. Noah: returned, refund not paid yet -> being processed
    add_order(con, "ORD-1006", 6, "returned", [(6, 1)], ordered_days_ago=30, delivered_days_ago=27)
    # 7. Mila: expensive laptop delivered yesterday -> damage claim, escalate
    add_order(con, "ORD-1007", 7, "delivered", [(7, 1)], ordered_days_ago=3, delivered_days_ago=1,
              method="express")
    # 8. Tess: returned, refund paid 12 days ago
    add_order(con, "ORD-1008", 8, "returned", [(2, 1)], ordered_days_ago=40, delivered_days_ago=36,
              refund_days_ago=12)


FIRST_NAMES = ["Anna", "Bram", "Eva", "Finn", "Lotte", "Milan", "Sara", "Thijs", "Yara", "Jesse"]
LAST_NAMES = ["de Jong", "Peters", "Hendriks", "van Dijk", "Dekker", "Brouwer", "de Wit", "Vos"]
CITIES = ["Amsterdam", "Utrecht", "Rotterdam", "Eindhoven", "Hilversum", "Groningen"]


def add_filler(con, n_customers=32):
    """Random ordinary customers and orders, so the shop looks realistic."""
    order_number = 2001
    for customer_id in range(9, 9 + n_customers):
        first = random.choice(FIRST_NAMES)
        last = random.choice(LAST_NAMES)
        email = f"{first}.{last}{customer_id}@example.com".lower().replace(" ", "")
        con.execute("INSERT INTO customers VALUES (?, ?, ?, ?, ?)",
                    (customer_id, f"{first} {last}", email,
                     random.choice(CITIES), days_ago(random.randint(200, 900))))

        for _ in range(random.randint(1, 3)):       # 1 to 3 orders per customer
            ordered = random.randint(1, 200)        # ordered 1-200 days ago
            if ordered <= 2:
                status, delivered = "processing", None
            elif ordered <= 5:
                status, delivered = "shipped", None
            elif random.random() < 0.05:            # 5% chance
                status, delivered = "cancelled", None
            else:
                status, delivered = "delivered", ordered - random.randint(2, 5)

            product_id = random.choice(list(PRICES))
            add_order(con, f"ORD-{order_number}", customer_id, status,
                      [(product_id, random.randint(1, 2))],
                      ordered_days_ago=ordered, delivered_days_ago=delivered)
            order_number += 1


def main():
    DB_PATH.parent.mkdir(exist_ok=True)   # make sure the data/ folder exists
    DB_PATH.unlink(missing_ok=True)       # delete the old database, start fresh
    con = sqlite3.connect(DB_PATH)        # opens (or creates) the database file
    con.executescript(SCHEMA)             # runs all the CREATE TABLE statements

    con.executemany("INSERT INTO products VALUES (?, ?, ?, ?, ?)", PRODUCTS)    # adds the 8 products
    con.executemany("INSERT INTO customers VALUES (?, ?, ?, ?, ?)", TEST_CUSTOMERS)     # adds the 8 test customers

    add_test_orders(con)                  # adds the 8 test orders
    random.seed(42)                       # makes the filler data reproducible (the same seed gives the same “random” numbers every time, so your database is identical on every run)
    add_filler(con)                       # adds random ordinary customers and orders

    con.commit()                          # saves the changes

    for table in ("customers", "products", "orders", "order_items"):            # print how many rows we have in each table
        n = con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]          # fetchone() returns a tuple like (8,), so we take the first element
        print(f"{table:12s} {n} rows")
    con.close()

if __name__ == "__main__":
    main()