import re

prepared = "SELECT * FROM t WHERE date >= '%START_DATE%' AND user_id = {uid} AND c = '{company_id}' AND d = %END_DATE%"

params = {
    'start_date': '2020-01-01',
    'end_date': '2020-12-31',
    'uid': 1,
    'user_id': 1,
    'company_id': 1,
}
replacements_keys = ['start_date', 'end_date', 'uid', 'user_id', 'company_id']
for key in replacements_keys:
    # Replace with quotes first
    prepared = re.sub(r"['\"]\{" + key + r"\}['\"]", f"%({key})s", prepared, flags=re.IGNORECASE)
    prepared = re.sub(r"['\"]%" + key + r"%['\"]", f"%({key})s", prepared, flags=re.IGNORECASE)
    # Replace without quotes
    prepared = re.sub(r"\{" + key + r"\}", f"%({key})s", prepared, flags=re.IGNORECASE)
    prepared = re.sub(r"%" + key + r"%", f"%({key})s", prepared, flags=re.IGNORECASE)

print(prepared)
