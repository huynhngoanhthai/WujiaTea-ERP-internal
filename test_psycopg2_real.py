import psycopg2

conn = psycopg2.connect(database="postgres", user="postgres")
cur = conn.cursor()

# Test 1: No params
try:
    cur.execute("SELECT 1 WHERE 'test' LIKE '%test%'")
    print("No params: OK", cur.fetchall())
except Exception as e:
    print("No params error:", e)
    conn.rollback()

# Test 2: With params, no escaped %
try:
    cur.execute("SELECT 1 WHERE 'test' LIKE '%test%' AND 1 = %(val)s", {'val': 1})
    print("With params no escape: OK", cur.fetchall())
except Exception as e:
    print("With params no escape error:", e)
    conn.rollback()

# Test 3: With params, escaped %
try:
    cur.execute("SELECT 1 WHERE 'test' LIKE '%%test%%' AND 1 = %(val)s", {'val': 1})
    print("With params escaped: OK", cur.fetchall())
except Exception as e:
    print("With params escaped error:", e)
    conn.rollback()

conn.close()
