import sqlite3

# using sqlite3 with named placeholders
conn = sqlite3.connect(':memory:')
conn.execute("CREATE TABLE users (id INTEGER, name TEXT)")
conn.execute("INSERT INTO users VALUES (1, 'Alice')")

# test unused params
try:
    cur = conn.cursor()
    # sqlite3 named placeholders are :name
    cur.execute("SELECT * FROM users WHERE id = 1", {'uid': 1})
    print("sqlite3: SUCCESS")
except Exception as e:
    print(f"sqlite3: {e}")
