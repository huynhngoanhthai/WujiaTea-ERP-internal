import psycopg2

class MockCursor:
    pass

# We don't have postgres running, but psycopg2 can mogrify without DB if we have a connection.
# Actually mogrify needs a connection.
