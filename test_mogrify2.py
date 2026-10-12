import psycopg2

conn = psycopg2.connect(database="postgres", user="postgres")
cur = conn.cursor()
