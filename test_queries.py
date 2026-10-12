import re

class MockEnv:
    class cr:
        @staticmethod
        def execute(query, params=None):
            print(f"Executing: {query}")
            print(f"With params: {params}")
            # Ensure query executes without formatting error in pyformat
            if params:
                formatted = query % params
                print(f"Formatted: {formatted}")
            else:
                print(f"No params provided")
            print("---")

class MockItem:
    def __init__(self):
        self.sql_row_limit = 5000
        self.env = MockEnv()
        self.env.uid = 1
        self.env.company = type('Company', (), {'id': 1})()

    def _validate_sql_query(self, query):
        return query

    # Copy of the fixed method
    def _prepare_sql_query(self, query, kwargs=None):
        kwargs = kwargs or {}
        prepared = self._validate_sql_query(query)

        # Mocking date logic just for tests
        start_date = '2024-01-01'
        end_date = '2024-12-31'
        start_s = start_date
        end_s = end_date
        uid = str(self.env.uid)
        company_id = str(self.env.company.id)

        prepared = prepared.replace('%', '%%')

        params = {
            'start_date': start_s,
            'end_date': end_s,
            'uid': int(uid) if uid.isdigit() else uid,
            'company_id': int(company_id) if company_id.isdigit() else company_id,
        }

        replacements_map = {
            '{start_date}': 'start_date', '{end_date}': 'end_date',
            '{uid}': 'uid', '{user_id}': 'uid', '{company_id}': 'company_id',
            '%%START_DATE%%': 'start_date', '%%END_DATE%%': 'end_date',
            '%%UID%%': 'uid', '%%USER_ID%%': 'uid', '%%COMPANY_ID%%': 'company_id',
        }
        for key, param_name in replacements_map.items():
            pattern_with_quotes = r"['\"]" + re.escape(key) + r"['\"]"
            prepared = re.sub(pattern_with_quotes, f"%({param_name})s", prepared, flags=re.IGNORECASE)
            pattern_without = re.escape(key)
            prepared = re.sub(pattern_without, f"%({param_name})s", prepared, flags=re.IGNORECASE)

        limit = max(1, int(self.sql_row_limit or 5000))
        if not re.search(r'\bLIMIT\s+\d+', prepared, re.IGNORECASE):
            prepared = f"{prepared} LIMIT {limit}"
        return prepared, limit, params


item = MockItem()

queries = [
    "SELECT * FROM res_users WHERE id = {uid}",
    "SELECT * FROM account_move WHERE date >= '{start_date}' AND name LIKE '%test%'",
    "SELECT * FROM hr_employee WHERE company_id = %COMPANY_ID%",
    "SELECT * FROM hr_employee WHERE name LIKE '%John%' LIMIT 10",
]

for q in queries:
    p, l, params = item._prepare_sql_query(q)
    MockEnv.cr.execute(p, params)
