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

    # Escaping '%' for pyformat
    # But ONLY if the engine expects pyformat. Odoo local DB expects pyformat.

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

    # What if we use a safe query builder or just parameterize using named parameters?
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
