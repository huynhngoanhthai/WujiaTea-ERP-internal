import re

def prepare_sql_query(query, kwargs=None):
    start_s = '2020-01-01'
    end_s = '2020-12-31'
    uid = '1'
    company_id = '1'

    # Escape percent signs NOT associated with our placeholders
    # Because psycopg2 uses %s or %(name)s, any other % must be %%

    params = {
        'start_date': start_s,
        'end_date': end_s,
        'uid': int(uid) if uid.isdigit() else uid,
        'user_id': int(uid) if uid.isdigit() else uid,
        'company_id': int(company_id) if company_id.isdigit() else company_id,
    }

    # Before modifying placeholders, we need to escape all '%' characters
    # EXCEPT those that are part of our old placeholders like %START_DATE%
    # Actually, the easiest way is to escape ALL %, and then our placeholders will be %%START_DATE%%
    prepared = query.replace('%', '%%')

    replacements_map = {
        '{start_date}': 'start_date',
        '{end_date}': 'end_date',
        '{uid}': 'uid',
        '{user_id}': 'user_id',
        '{company_id}': 'company_id',
        '%%START_DATE%%': 'start_date',
        '%%END_DATE%%': 'end_date',
        '%%UID%%': 'uid',
        '%%USER_ID%%': 'user_id',
        '%%COMPANY_ID%%': 'company_id',
    }

    for key, param_name in replacements_map.items():
        # If the user used quotes like '%START_DATE%' (now '%%START_DATE%%') or '{uid}'
        # we want to strip the quotes because psycopg2 parameter substitution handles it securely.
        # Match single or double quotes around the placeholder
        pattern_with_quotes = r"['\"]" + re.escape(key) + r"['\"]"
        prepared = re.sub(pattern_with_quotes, f"%({param_name})s", prepared, flags=re.IGNORECASE)

        # Match without quotes
        pattern_without = re.escape(key)
        prepared = re.sub(pattern_without, f"%({param_name})s", prepared, flags=re.IGNORECASE)

    # Finally append limit, wait, limit is appended as LIMIT 5000
    # No need to parameterize limit since it's hardcoded int
    limit = 5000
    if not re.search(r'\bLIMIT\s+\d+', prepared, re.IGNORECASE):
        prepared = f"{prepared} LIMIT {limit}"

    return prepared, limit, params

q1, _, p1 = prepare_sql_query("SELECT * FROM t WHERE name LIKE '%test%' AND date >= '%START_DATE%' AND u = {uid} AND c = '{company_id}'")
print(q1)
print(p1)
