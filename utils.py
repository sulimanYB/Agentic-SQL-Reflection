import random
import sqlite3
from html import escape
from typing import Any

import pandas as pd
from IPython.display import HTML, display


def create_transactions_db(
    db_name: str = "products.db",
    n_products: int = 100,
    n_txns_per_product: int = 50,
) -> None:
    """Create a SQLite database with simulated product transaction events."""
    conn = sqlite3.connect(db_name)
    cur = conn.cursor()

    # Recreate the table on each run
    cur.execute("DROP TABLE IF EXISTS transactions")

    # Event-sourced transactions table
    cur.execute("""
    CREATE TABLE transactions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        product_id INTEGER NOT NULL,
        product_name TEXT NOT NULL,
        brand TEXT NOT NULL,
        category TEXT NOT NULL,
        color TEXT NOT NULL,

        action TEXT NOT NULL,            -- 'insert' | 'restock' | 'sale' | 'price_update'
        qty_delta INTEGER DEFAULT 0,     -- + for restock/insert, - for sale
        unit_price REAL,                 -- price at the time of the event (NULL for non-price events)
        notes TEXT,                      -- optional
        ts DATETIME DEFAULT CURRENT_TIMESTAMP
    )
    """)

    brands = ["Nike", "Adidas", "Puma", "Reebok", "New Balance"]
    categories = ["shoes", "hoodie", "t-shirt", "hat", "backpack"]
    colors = ["black", "white", "red", "blue", "green"]

    rng = random.Random(42)
    product_catalog = []
    for pid in range(1, n_products + 1):
        brand = rng.choice(brands)
        category = rng.choice(categories)
        name = f"{brand} {category}"
        color = rng.choice(colors)
        base_price = round(rng.uniform(20.0, 150.0), 2)
        product_catalog.append((pid, name, brand, category, color, base_price))

    # Seed events per product
    for pid, name, brand, category, color, base_price in product_catalog:
        # Initial insert (with opening stock and price)
        initial_stock = rng.randint(5, 50)
        cur.execute("""
            INSERT INTO transactions (
                product_id, product_name, brand, category, color,
                action, qty_delta, unit_price, notes
            ) VALUES (?, ?, ?, ?, ?, 'insert', ?, ?, ?)
        """, (pid, name, brand, category, color, initial_stock, base_price,
              f"Initial insert with stock={initial_stock}, price={base_price}"))

        current_price = base_price

        # Follow-up events
        for _ in range(n_txns_per_product - 1):
            event_type = rng.choices(
                ["restock", "sale", "price_update"],
                weights=[0.25, 0.6, 0.15],
                k=1
            )[0]

            if event_type == "restock":
                qty = rng.randint(1, 25)
                cur.execute("""
                    INSERT INTO transactions (
                        product_id, product_name, brand, category, color,
                        action, qty_delta, unit_price, notes
                    ) VALUES (?, ?, ?, ?, ?, 'restock', ?, NULL, ?)
                """, (pid, name, brand, category, color, qty,
                      f"Restock +{qty} units"))

            elif event_type == "sale":
                qty = -rng.randint(1, 10)  # negative
                cur.execute("""
                    INSERT INTO transactions (
                        product_id, product_name, brand, category, color,
                        action, qty_delta, unit_price, notes
                    ) VALUES (?, ?, ?, ?, ?, 'sale', ?, ?, ?)
                """, (pid, name, brand, category, color, qty, current_price,
                      f"Sale {-qty} units at {current_price}"))

            else:  # price_update
                delta = round(rng.uniform(-5.0, 5.0), 2)
                current_price = max(1.0, round(current_price + delta, 2))
                cur.execute("""
                    INSERT INTO transactions (
                        product_id, product_name, brand, category, color,
                        action, qty_delta, unit_price, notes
                    ) VALUES (?, ?, ?, ?, ?, 'price_update', 0, ?, ?)
                """, (pid, name, brand, category, color, current_price,
                      f"Price update to {current_price}"))

    conn.commit()
    conn.close()

    print(f"SQLite database '{db_name}' created with a single 'transactions' table (event-sourced).")


def get_schema(db_path: str) -> str:
    """Return the schema of the transactions table."""

    with sqlite3.connect(db_path) as conn:
        rows = conn.execute("PRAGMA table_info(transactions)").fetchall()

    columns = "\n".join(f"{row[1]} ({row[2]})" for row in rows)
    return f"Table name: transactions\n{columns}"


def execute_sql(query: str, db_path: str) -> pd.DataFrame:
    """Execute a SQL query and return its results as a DataFrame."""

    query = query.strip().removeprefix("```sql").removesuffix("```").strip()

    conn = sqlite3.connect(db_path)

    try:
        return pd.read_sql_query(query, conn)
    except Exception as e:
        return pd.DataFrame({"error": [str(e)]})
    finally:
        conn.close()


def print_html(content: Any, title: str | None = None) -> None:
    """Display text or pandas data in a formatted notebook output."""

    if isinstance(content, pd.DataFrame):
        rendered = content.to_html(index=False, escape=True)
    elif isinstance(content, pd.Series):
        rendered = content.to_frame().to_html(escape=True)
    else:
        rendered = f"<pre>{escape(str(content))}</pre>"

    heading = f"<h4>{escape(title)}</h4>" if title else ""

    display(HTML(heading + rendered))