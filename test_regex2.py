import re

prepared = "SELECT * FROM t WHERE d >= '{start_date}' AND d <= '%END_DATE%' AND u = {uid} AND c = '%COMPANY_ID%'"

replacements_map = {
    '{start_date}': '%(start_date)s',
    '{end_date}': '%(end_date)s',
    '{uid}': '%(uid)s',
    '{user_id}': '%(uid)s',
    '{company_id}': '%(company_id)s',
    '%START_DATE%': '%(start_date)s',
    '%END_DATE%': '%(end_date)s',
    '%UID%': '%(uid)s',
    '%USER_ID%': '%(uid)s',
    '%COMPANY_ID%': '%(company_id)s',
}

for key, param_name in replacements_map.items():
    # Remove surrounding quotes if they exist
    prepared = re.sub(r"['\"]" + re.escape(key) + r"['\"]", param_name, prepared, flags=re.IGNORECASE)
    # Also replace it if there are no quotes
    prepared = re.sub(re.escape(key), param_name, prepared, flags=re.IGNORECASE)

print(prepared)
