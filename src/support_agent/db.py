"""Read-only database queries that the support agent is allowed to use."""
import sqlite3
from pathlib import Path

# src/support_agent/db.py -> go up 3 levels to the project folder
DB_PATH = Path(__file__).resolve().parents[2] / "data" / "shop.db"


def _connect():
    """Open the database in READ-ONLY mode, so nothing can be changed or deleted."""
    con = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)    #?mode=ro":open the database in read-only mode; safety layer (together with agent being able to call only those two functions)
    con.row_factory = sqlite3.Row      # rows behave like dictionaries: row["status"]
    return con


def get_order(order_id: str, email: str) -> dict:
    """Return one order with its items, only if it belongs to the customer with this email."""
    con = _connect()
    order = con.execute(
        """
        SELECT o.order_id, o.order_date, o.status, o.shipping_method,
               o.tracking_number, o.estimated_delivery, o.delivered_on,
               o.refund_issued_on, o.total_eur, c.name AS customer_name
        FROM orders o
        JOIN customers c ON o.customer_id = c.customer_id
        WHERE o.order_id = ? AND lower(c.email) = lower(?) 
        """,                                        # The query only finds the order if both match, so there is no way to get the order without the right email.
        (order_id.strip().upper(), email.strip()),  # Tolerant input
    ).fetchone()

    if order is None:
        con.close()
        return {"error": "No order found with this order number and email address."}

    items = con.execute(
        """
        SELECT p.name AS product, p.category, i.quantity,
               i.unit_price_eur, p.warranty_months
        FROM order_items i
        JOIN products p ON i.product_id = p.product_id
        WHERE i.order_id = ?
        """,
        (order["order_id"],),
    ).fetchall()
    con.close()

    result = dict(order)
    result["items"] = [dict(row) for row in items]
    return result


def list_customer_orders(email: str) -> dict:
    """Return a short overview of all orders for the customer with this email."""
    con = _connect()
    rows = con.execute(
        """
        SELECT o.order_id, o.order_date, o.status, o.total_eur
        FROM orders o
        JOIN customers c ON o.customer_id = c.customer_id
        WHERE lower(c.email) = lower(?)
        ORDER BY o.order_date DESC
        """,
        (email.strip(),),
    ).fetchall()
    con.close()

    if not rows:
        return {"error": "No customer found with this email address."}
    return {"orders": [dict(row) for row in rows]}


if __name__ == "__main__":
    from pprint import pprint
    print("--- Emma's order, correct email ---")
    pprint(get_order("ORD-1001", "emma.devries@example.com"))
    print("\n--- Emma's order, WRONG email (Lucas) ---")
    pprint(get_order("ORD-1001", "lucas.jansen@example.com"))
    print("\n--- Daan's orders ---")
    pprint(list_customer_orders("daan.visser@example.com"))