import sqlite3
import datetime

def query_db():
    conn = sqlite3.connect("subscribers.db")
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM subscribers ORDER BY username ASC limit 100")
    rows = cursor.fetchall()

    # Get column names from the cursor description
    column_names = [description[0] for description in cursor.description]

    for row in rows:
        for i, value in enumerate(row):
            print(f"{column_names[i]}: {value}", end=", ")
        print()

    conn.close()

if __name__ == "__main__":
    query_db()
