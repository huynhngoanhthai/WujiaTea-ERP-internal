import re

with open('custom/dynamic_dashboard_ai_nexgen/models/dashboard_item.py', 'r') as f:
    content = f.read()

matches = re.finditer(r"def (\w+)\(", content)
for m in matches:
    print(m.group(1))
