# -*- coding: utf-8 -*-
"""Repair pre-control stored projections from authoritative parent rows.

``readonly=True`` never prevented ORM/RPC writes to stored related fields.
Before 1.7.8 a caller could therefore persist, for example,
``account_move_line.parent_state='posted'`` while its move remained draft, or
point a contact's ``commercial_partner_id`` at an unrelated company.  Repair
is deterministic: no client-supplied projection is promoted, and all rows/FKs
remain present.

Column probes keep generated 16/17/18 migrations safe where later origin
fields do not exist.
"""

import logging


_logger = logging.getLogger(__name__)


def _column_exists(cr, table, column):
    cr.execute(
        "SELECT 1 FROM information_schema.columns "
        "WHERE table_schema = current_schema() "
        "AND table_name = %s AND column_name = %s",
        (table, column),
    )
    return bool(cr.fetchone())


def _table_exists(cr, table):
    cr.execute("SELECT to_regclass(%s)", (table,))
    row = cr.fetchone()
    return bool(row and row[0])


def _module_active(cr, module_name):
    if not (
        _table_exists(cr, 'ir_module_module')
        and _column_exists(cr, 'ir_module_module', 'name')
        and _column_exists(cr, 'ir_module_module', 'state')
    ):
        return False
    cr.execute(
        "SELECT 1 FROM ir_module_module WHERE name = %s "
        "AND state IN ('installed', 'to upgrade', 'to install')",
        (module_name,),
    )
    return bool(cr.fetchone())


def _repair_move_line_projection(cr, target_column, source_column):
    if not (
        _column_exists(cr, 'account_move_line', target_column)
        and _column_exists(cr, 'account_move', source_column)
    ):
        return set(), 0
    if target_column == 'company_id':
        cr.execute(
            f"SELECT l.company_id, m.company_id "
            f"FROM account_move_line l "
            f"JOIN account_move m ON m.id = l.move_id "
            f"WHERE l.company_id IS DISTINCT FROM m.company_id"
        )
        company_ids = {
            company_id
            for row in cr.fetchall() for company_id in row if company_id
        }
    else:
        cr.execute(
            f"SELECT DISTINCT m.company_id "
            f"FROM account_move_line l "
            f"JOIN account_move m ON m.id = l.move_id "
            f"WHERE l.{target_column} IS DISTINCT FROM m.{source_column}"
        )
        company_ids = {row[0] for row in cr.fetchall() if row[0]}
    cr.execute(
        f"UPDATE account_move_line l SET {target_column} = m.{source_column} "
        f"FROM account_move m WHERE m.id = l.move_id "
        f"AND l.{target_column} IS DISTINCT FROM m.{source_column}"
    )
    return company_ids, cr.rowcount


def _repair_statement_projection(cr):
    required = (
        _table_exists(cr, 'account_bank_statement_line')
        and _column_exists(cr, 'account_move_line', 'statement_id')
        and _column_exists(cr, 'account_move', 'statement_line_id')
        and _column_exists(
            cr, 'account_bank_statement_line', 'statement_id',
        )
    )
    if not required:
        return set(), 0
    cr.execute(
        "SELECT DISTINCT m.company_id "
        "FROM account_move_line l "
        "JOIN account_move m ON m.id = l.move_id "
        "LEFT JOIN account_bank_statement_line s "
        "ON s.id = m.statement_line_id "
        "WHERE l.statement_id IS DISTINCT FROM s.statement_id"
    )
    company_ids = {row[0] for row in cr.fetchall() if row[0]}
    cr.execute(
        "UPDATE account_move_line l SET statement_id = s.statement_id "
        "FROM account_move m "
        "LEFT JOIN account_bank_statement_line s "
        "ON s.id = m.statement_line_id "
        "WHERE m.id = l.move_id "
        "AND l.statement_id IS DISTINCT FROM s.statement_id"
    )
    return company_ids, cr.rowcount


def _repair_company_currency_projection(cr):
    required = all((
        _column_exists(
            cr, 'account_move_line', 'company_currency_id',
        ),
        _column_exists(cr, 'account_move', 'company_id'),
        _column_exists(cr, 'res_company', 'currency_id'),
    ))
    if not required:
        return set(), 0
    cr.execute("""
        SELECT DISTINCT move.company_id
          FROM account_move_line AS line
          JOIN account_move AS move ON move.id = line.move_id
          JOIN res_company AS company ON company.id = move.company_id
         WHERE line.company_currency_id
               IS DISTINCT FROM company.currency_id
    """)
    company_ids = {row[0] for row in cr.fetchall() if row[0]}
    cr.execute("""
        UPDATE account_move_line AS line
           SET company_currency_id = company.currency_id
          FROM account_move AS move
          JOIN res_company AS company ON company.id = move.company_id
         WHERE move.id = line.move_id
           AND line.company_currency_id
               IS DISTINCT FROM company.currency_id
    """)
    return company_ids, cr.rowcount


def _repair_commercial_partner_projection(cr):
    if not all(
        _column_exists(cr, 'res_partner', column)
        for column in (
            'id', 'parent_id', 'is_company', 'name', 'company_name',
            'commercial_partner_id', 'commercial_company_name',
        )
    ):
        return 0
    cr.execute("""
        WITH RECURSIVE commercial_root(id, root_id, path) AS (
            SELECT p.id, p.id, ARRAY[p.id]
              FROM res_partner p
             WHERE p.is_company OR p.parent_id IS NULL
            UNION ALL
            SELECT child.id, root.root_id, root.path || child.id
              FROM commercial_root root
              JOIN res_partner child ON child.parent_id = root.id
             WHERE NOT child.is_company
               AND NOT child.id = ANY(root.path)
        ), changed AS (
            UPDATE res_partner p
               SET commercial_partner_id = root.root_id
              FROM commercial_root root
             WHERE p.id = root.id
               AND p.commercial_partner_id IS DISTINCT FROM root.root_id
            RETURNING p.id
        )
        SELECT COUNT(*) FROM changed
    """)
    changed = cr.fetchone()[0]
    # Invalid legacy parent cycles have no authoritative root.  Isolate them
    # to self rather than retaining an attacker-chosen cross-entity pointer.
    cr.execute("""
        WITH RECURSIVE commercial_root(id, root_id, path) AS (
            SELECT p.id, p.id, ARRAY[p.id]
              FROM res_partner p
             WHERE p.is_company OR p.parent_id IS NULL
            UNION ALL
            SELECT child.id, root.root_id, root.path || child.id
              FROM commercial_root root
              JOIN res_partner child ON child.parent_id = root.id
             WHERE NOT child.is_company
               AND NOT child.id = ANY(root.path)
        )
        UPDATE res_partner p
           SET commercial_partner_id = p.id
         WHERE NOT EXISTS (
                   SELECT 1 FROM commercial_root root WHERE root.id = p.id
               )
           AND p.commercial_partner_id IS DISTINCT FROM p.id
    """)
    changed += cr.rowcount
    cr.execute("""
        UPDATE res_partner p
           SET commercial_company_name = CASE
                   WHEN root.is_company THEN root.name
                   ELSE p.company_name
               END
          FROM res_partner root
         WHERE root.id = p.commercial_partner_id
           AND p.commercial_company_name IS DISTINCT FROM CASE
                   WHEN root.is_company THEN root.name
                   ELSE p.company_name
               END
    """)
    changed += cr.rowcount
    return changed


def _repair_move_commercial_partner_projection(cr):
    required = all((
        _column_exists(cr, 'account_move', 'partner_id'),
        _column_exists(cr, 'account_move', 'commercial_partner_id'),
        _column_exists(cr, 'account_move', 'company_id'),
        _column_exists(cr, 'res_partner', 'commercial_partner_id'),
        _column_exists(cr, 'res_company', 'partner_id'),
    ))
    if not required:
        return set(), 0
    own_expense = "FALSE"
    if (
        _module_active(cr, 'hr_expense')
        and _table_exists(cr, 'hr_expense')
        and _column_exists(cr, 'hr_expense', 'payment_mode')
    ):
        # Odoo 19 links expenses straight to account.move.  Odoo 17/18
        # stores move.expense_sheet_id; Odoo 16 stores the reverse
        # hr_expense_sheet.account_move_id link.  Pick the first current
        # schema shape and ignore stale tables left by an uninstalled module.
        if _column_exists(cr, 'hr_expense', 'account_move_id'):
            own_expense = (
                "EXISTS (SELECT 1 FROM hr_expense AS expense "
                "WHERE expense.account_move_id = move.id "
                "AND expense.payment_mode = 'own_account')"
            )
        elif (
            _column_exists(cr, 'account_move', 'expense_sheet_id')
            and _column_exists(cr, 'hr_expense', 'sheet_id')
        ):
            own_expense = (
                "EXISTS (SELECT 1 FROM hr_expense AS expense "
                "WHERE expense.sheet_id = move.expense_sheet_id "
                "AND expense.payment_mode = 'own_account')"
            )
        elif (
            _table_exists(cr, 'hr_expense_sheet')
            and _column_exists(cr, 'hr_expense_sheet', 'account_move_id')
            and _column_exists(cr, 'hr_expense', 'sheet_id')
        ):
            own_expense = (
                "EXISTS (SELECT 1 FROM hr_expense AS expense "
                "JOIN hr_expense_sheet AS sheet "
                "ON sheet.id = expense.sheet_id "
                "WHERE sheet.account_move_id = move.id "
                "AND expense.payment_mode = 'own_account')"
            )
    authoritative = (
        "(SELECT CASE WHEN " + own_expense + " "
        "AND partner.commercial_partner_id IS NOT DISTINCT FROM "
        "company.partner_id THEN move.partner_id "
        "ELSE partner.commercial_partner_id END "
        "FROM res_company AS company "
        "LEFT JOIN res_partner AS partner ON partner.id = move.partner_id "
        "WHERE company.id = move.company_id)"
    )
    cr.execute(
        "SELECT DISTINCT move.company_id FROM account_move AS move "
        f"WHERE move.commercial_partner_id IS DISTINCT FROM {authoritative}"
    )
    company_ids = {row[0] for row in cr.fetchall() if row[0]}
    cr.execute(
        "UPDATE account_move AS move "
        f"SET commercial_partner_id = {authoritative} "
        f"WHERE move.commercial_partner_id IS DISTINCT FROM {authoritative}"
    )
    return company_ids, cr.rowcount


def _bump_report_versions(cr, company_ids):
    """Invalidate repaired scopes without locking ``res_company`` rows."""
    ids = sorted({int(company_id) for company_id in company_ids})
    if not ids:
        return
    if _table_exists(cr, 'eh_account_report_company_version'):
        cr.execute(
            "INSERT INTO eh_account_report_company_version "
            "(company_id, version) "
            "SELECT company.id, 1 FROM res_company AS company "
            "WHERE company.id = ANY(%s) "
            "ON CONFLICT (company_id) DO UPDATE SET version = "
            "eh_account_report_company_version.version + 1",
            (ids,),
        )
    elif _column_exists(cr, 'res_company', 'eh_move_version'):
        # Compatibility for a generated target running this historical
        # migration without the later isolated-counter schema.
        cr.execute(
            "UPDATE res_company "
            "SET eh_move_version = eh_move_version + 1 "
            "WHERE id = ANY(%s)",
            (ids,),
        )


def migrate(cr, version):
    del version
    changed_companies = set()
    changed_lines = 0
    projection_pairs = [
        ('journal_id', 'journal_id'),
        ('company_id', 'company_id'),
        ('move_name', 'name'),
        ('parent_state', 'state'),
        ('date', 'date'),
        ('invoice_date', 'invoice_date'),
        ('ref', 'ref'),
        ('statement_line_id', 'statement_line_id'),
    ]
    payment_source = (
        'origin_payment_id'
        if _column_exists(cr, 'account_move', 'origin_payment_id')
        else 'payment_id'
    )
    projection_pairs.append(('payment_id', payment_source))
    for target_column, source_column in projection_pairs:
        company_ids, count = _repair_move_line_projection(
            cr, target_column, source_column,
        )
        changed_companies.update(company_ids)
        changed_lines += count
    company_ids, count = _repair_company_currency_projection(cr)
    changed_companies.update(company_ids)
    changed_lines += count
    company_ids, count = _repair_statement_projection(cr)
    changed_companies.update(company_ids)
    changed_lines += count

    changed_partners = _repair_commercial_partner_projection(cr)
    if changed_partners:
        # Commercial roots can feed reports in every allowed company.
        cr.execute("SELECT id FROM res_company")
        changed_companies.update(row[0] for row in cr.fetchall())
    company_ids, changed_moves = _repair_move_commercial_partner_projection(cr)
    changed_companies.update(company_ids)
    _bump_report_versions(cr, changed_companies)
    _logger.warning(
        "ERP Heritage 1.7.8 repaired %s stored journal-item projections, "
        "%s stored partner projections, and %s stored move commercial "
        "projections; no row was deleted",
        changed_lines,
        changed_partners,
        changed_moves,
    )
