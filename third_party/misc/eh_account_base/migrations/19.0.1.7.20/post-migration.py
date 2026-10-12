# -*- encoding: utf-8 -*-
"""Apply legacy upstream partner defaults once during module upgrade."""

from psycopg2 import sql


_REQUIRED_PARTNER_DEFAULTS = (
    ('group_rfq', 'default'),
    ('group_on', 'default'),
)


def migrate(cr, version):
    del version
    for column, default in _REQUIRED_PARTNER_DEFAULTS:
        cr.execute(
            """
            SELECT 1
              FROM information_schema.columns
             WHERE table_name = 'res_partner'
               AND column_name = %s
            """,
            [column],
        )
        if cr.fetchone():
            cr.execute(
                sql.SQL(
                    "ALTER TABLE res_partner "
                    "ALTER COLUMN {column} SET DEFAULT %s"
                ).format(column=sql.Identifier(column)),
                [default],
            )
