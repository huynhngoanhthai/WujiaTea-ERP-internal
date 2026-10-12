import re

def _prepare_sql_query(query):
    start_s = '2024-01-01'
    end_s = '2024-12-31'
    uid = '1'
    company_id = '1'

    prepared = query

    params = {
        'start_date': start_s,
        'end_date': end_s,
        'uid': int(uid) if uid.isdigit() else uid,
        'user_id': int(uid) if uid.isdigit() else uid,
        'company_id': int(company_id) if company_id.isdigit() else company_id,
    }

    # First, handle the string formatting placeholders in a safe way without %s syntax
    # Since we don't want to refactor all callers of _execute_sql_query to pass params if they are not using _prepare_sql_query
    pass
