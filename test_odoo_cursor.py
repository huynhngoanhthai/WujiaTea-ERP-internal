import sys
import psycopg2

class FakeCursor:
    def execute(self, query, params=None):
        if params is not None:
            # Simulate what psycopg2 does with mogrify
            print(f"Executing with params: query='{query}', params={params}")
            # If query has raw `%`, psycopg2 fails unless it's `%%` or part of `%(param)s`.
            try:
                # Basic check: Python % formatting
                query % params
                print("Python % formatting succeeded")
            except Exception as e:
                print("Python % formatting error:", e)
        else:
            print(f"Executing without params: query='{query}'")

cur = FakeCursor()
cur.execute("SELECT 1 WHERE 'test' LIKE '%test%'", {})
cur.execute("SELECT 1 WHERE 'test' LIKE '%%test%%'", {})
