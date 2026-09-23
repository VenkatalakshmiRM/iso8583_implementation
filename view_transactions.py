"""Print the server's SQLite transaction history as a readable table."""
import os
import sqlite3

DB_PATH = os.path.join(os.path.dirname(__file__), "transactions.db")


def main():
    if not os.path.exists(DB_PATH):
        print("No transaction database yet. Start server.py and run client.py first.")
        return
    with sqlite3.connect(DB_PATH) as db:
        rows = db.execute("""SELECT id, timestamp, mti, stan, card_number, amount,
                             response_code, status FROM transactions ORDER BY id""").fetchall()
    headers = ("ID", "Timestamp", "MTI", "STAN", "Card", "Amount", "DE39", "Status")
    rendered = [["" if value is None else str(value) for value in row] for row in rows]
    widths = [max(len(headers[i]), *(len(row[i]) for row in rendered)) if rendered else len(headers[i])
              for i in range(len(headers))]
    fmt = " | ".join("{:" + str(width) + "}" for width in widths)
    print(fmt.format(*headers))
    print("-+-".join("-" * width for width in widths))
    for row in rendered:
        print(fmt.format(*row))
    if not rendered:
        print("(no transactions recorded)")


if __name__ == "__main__":
    main()
