import re

with open('custom/dynamic_dashboard_ai_nexgen/models/dashboard_item.py', 'r') as f:
    content = f.read()

print("Calls to _execute_sql_query:")
for m in re.finditer(r"[^\n]*_execute_sql_query[^\n]*", content):
    print(m.group(0).strip())
