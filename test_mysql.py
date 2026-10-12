try:
    import mysql.connector
    print("mysql.connector parameter style:", mysql.connector.paramstyle)
except ImportError:
    print("mysql.connector not found")
