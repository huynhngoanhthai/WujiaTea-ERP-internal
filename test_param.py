import re

query = "SELECT * FROM t WHERE name LIKE '%test%' AND date >= '%START_DATE%' AND u = {uid} AND c = '{company_id}'"

# 1. Escape all %
query = query.replace('%', '%%')

# 2. Replace placeholders with %(param)s
# Note that '%START_DATE%' became '%%START_DATE%%'
replacements_map = {
    '{start_date}': 'start_date',
    '{end_date}': 'end_date',
    '{uid}': 'uid',
    '{user_id}': 'uid',
    '{company_id}': 'company_id',
    '%%START_DATE%%': 'start_date',
    '%%END_DATE%%': 'end_date',
    '%%UID%%': 'uid',
    '%%USER_ID%%': 'uid',
    '%%COMPANY_ID%%': 'company_id',
}

for key, param_name in replacements_map.items():
    # Replace with surrounding quotes
    query = re.sub(r"['\"]" + re.escape(key) + r"['\"]", f"%({param_name})s", query, flags=re.IGNORECASE)
    # Replace without quotes
    query = re.sub(re.escape(key), f"%({param_name})s", query, flags=re.IGNORECASE)

print(query)
