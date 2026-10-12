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

    replacements_map = {
        '{start_date}': 'start_date',
        '{end_date}': 'end_date',
        '{uid}': 'uid',
        '{user_id}': 'user_id',
        '{company_id}': 'company_id',
        '%START_DATE%': 'start_date',
        '%END_DATE%': 'end_date',
        '%UID%': 'uid',
        '%USER_ID%': 'user_id',
        '%COMPANY_ID%': 'company_id',
    }

    # Instead of replacing % with %%, which messes up psycopg2 %s format,
    # let's just use the %(name)s format for psycopg2.
    # Note that the caller of `_prepare_sql_query` (Odoo `_execute_sql_query`) uses `.execute(query)`.
    # Wait, `cur.execute(query)` uses %(name)s if `params` is dict, but if we don't pass params, it just executes it without parameter substitution if it doesn't find %s. Wait, psycopg2 *always* looks for % if you pass params, but if you don't, it might still fail if there are % characters. Wait, `cr.execute(query, params)` is the right way in Odoo.

    # But if we change `_prepare_sql_query` to return params, we have to change `_execute_sql_query` to take params and pass them to `cur.execute(query, params)`.

    prepared = prepared.replace('%', '%%')

    for key, param_name in replacements_map.items():
        escaped_key = key.replace('%', '%%')
        pattern_with_quotes = r"['\"]" + re.escape(escaped_key) + r"['\"]"
        prepared = re.sub(pattern_with_quotes, f"%({param_name})s", prepared, flags=re.IGNORECASE)
        pattern_without = re.escape(escaped_key)
        prepared = re.sub(pattern_without, f"%({param_name})s", prepared, flags=re.IGNORECASE)

    limit = 5000
    if not re.search(r'\bLIMIT\s+\d+', prepared, re.IGNORECASE):
        prepared = f"{prepared} LIMIT {limit}"

    return prepared, limit, params

print(_prepare_sql_query("SELECT * FROM res_users WHERE id = {uid} AND name LIKE '%test%'"))
print(_prepare_sql_query("SELECT * FROM res_users WHERE date >= '%START_DATE%'"))
