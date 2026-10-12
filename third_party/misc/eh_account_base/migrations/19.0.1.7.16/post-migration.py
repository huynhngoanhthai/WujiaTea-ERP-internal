# -*- encoding: utf-8 -*-
"""Move report freshness counters off the business-critical company row.

The old stored ``res_company.eh_move_version`` made every report-visible
write take a row lock on ``res_company``.  Posting and unrelated company
configuration therefore serialized on the same row.  The new private tables
separate per-company ledger epochs from one global presentation epoch.

Existing cached executions must never collide with the new counter space.
Seed the global epoch above the greatest legacy per-company value: for any
unchanged company scope, ``company_count * new_global`` is then strictly
greater than the former sum of legacy counters.
"""

import logging


_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        return

    cr.execute(
        """
        SELECT EXISTS (
            SELECT 1
              FROM pg_attribute
             WHERE attrelid = 'res_company'::regclass
               AND attname = 'eh_move_version'
               AND attnum > 0
               AND NOT attisdropped
        )
        """
    )
    has_legacy_column = cr.fetchone()[0]
    if has_legacy_column:
        cr.execute(
            "SELECT COALESCE(MAX(eh_move_version), 0) + 1 FROM res_company"
        )
        baseline = int(cr.fetchone()[0])
    else:
        baseline = 1

    cr.execute(
        """
        INSERT INTO eh_account_report_global_version (id, version)
        VALUES (1, %s)
        ON CONFLICT (id) DO UPDATE
           SET version = GREATEST(
               eh_account_report_global_version.version,
               EXCLUDED.version
           )
        RETURNING version
        """,
        (baseline,),
    )
    seeded = cr.fetchone()[0]
    _logger.info(
        "Seeded isolated accounting-report global epoch at %s (legacy "
        "company counter baseline %s).",
        seeded,
        baseline,
    )
