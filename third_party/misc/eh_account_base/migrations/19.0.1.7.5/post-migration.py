# -*- encoding: utf-8 -*-
"""Quarantine reversal graphs created before sealed-reversal ownership.

Version 1.7.4 introduced a trustworthy seal stamp, but core ``_reverse_moves``
could still copy a protected original into an unsealed, editable reversal.
Never infer that such historical rows are trustworthy from a plausible shape.
If any edge in a protected reversal graph is unsealed, unposted, cross-scope,
non-opposite, or duplicated, quarantine the whole connected graph while
preserving every move, line, and reversal link.
"""

import logging


_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        return
    cr.execute(
        """
        SELECT attname
          FROM pg_attribute
         WHERE attrelid = 'account_move_line'::regclass
           AND attnum > 0
           AND NOT attisdropped
        """
    )
    line_columns = {row[0] for row in cr.fetchall()}
    cr.execute(
        """
        SELECT attname
          FROM pg_attribute
         WHERE attrelid = 'account_move'::regclass
           AND attnum > 0
           AND NOT attisdropped
        """
    )
    move_columns = {row[0] for row in cr.fetchall()}
    # These tax-report dimensions were added in later Odoo series. Missing
    # columns mean the older ledger has no such dimension, not that upgrade
    # should fail before it can quarantine an unsafe reversal graph.
    extra_tax_data = (
        "COALESCE(line.extra_tax_data, '{}'::jsonb)"
        if 'extra_tax_data' in line_columns
        else "'{}'::jsonb"
    )
    deductible_amount = (
        "COALESCE(line.deductible_amount, 100.0)"
        if 'deductible_amount' in line_columns
        else "100.0"
    )
    is_storno = (
        "COALESCE(line.is_storno, FALSE)"
        if 'is_storno' in line_columns
        else (
            "COALESCE(line_move.is_storno, FALSE)"
            if 'is_storno' in move_columns else "FALSE"
        )
    )
    tax_base_sum = (
        "CASE WHEN line.move_id = child.id THEN -line.tax_base_amount "
        "ELSE line.tax_base_amount END"
        if 'tax_tag_invert' in line_columns
        else "line.tax_base_amount"
    )
    query = """
        WITH RECURSIVE protected_graph(id) AS (
            SELECT id
              FROM account_move
             WHERE eh_sealed = TRUE
                OR eh_legacy_unverified_seal = TRUE
            UNION
            SELECT neighbour.id
              FROM protected_graph graph
              JOIN LATERAL (
                    SELECT child.id
                      FROM account_move child
                     WHERE child.reversed_entry_id = graph.id
                    UNION
                    SELECT parent.id
                      FROM account_move current_move
                      JOIN account_move parent
                        ON parent.id = current_move.reversed_entry_id
                     WHERE current_move.id = graph.id
              ) neighbour ON TRUE
        ),
        graph_edges AS (
            SELECT parent.id AS parent_id,
                   child.id AS child_id
              FROM account_move child
              JOIN account_move parent
                ON parent.id = child.reversed_entry_id
             WHERE parent.id IN (SELECT id FROM protected_graph)
                OR child.id IN (SELECT id FROM protected_graph)
        ),
        protected_line_evidence AS (
            SELECT line.move_id,
                   line.account_id,
                   COALESCE(line.currency_id, 0) AS currency_id,
                   COALESCE(line.partner_id, 0) AS partner_id,
                   COALESCE(
                       line.analytic_distribution,
                       '{}'::jsonb
                   ) AS analytic_distribution,
                   ARRAY(
                       SELECT relation.account_tax_id
                         FROM account_move_line_account_tax_rel relation
                        WHERE relation.account_move_line_id = line.id
                       ORDER BY relation.account_tax_id
                   ) AS tax_ids,
                   ARRAY(
                       SELECT relation.account_account_tag_id
                         FROM account_account_tag_account_move_line_rel relation
                        WHERE relation.account_move_line_id = line.id
                        ORDER BY relation.account_account_tag_id
                   ) AS tax_tag_ids,
                   COALESCE(line.tax_line_id, 0) AS tax_line_id,
                   COALESCE(repartition.repartition_type, '')
                       AS tax_repartition_type,
                   COALESCE(repartition.factor_percent, 0.0)
                       AS tax_repartition_factor,
                   COALESCE(line.group_tax_id, 0) AS group_tax_id,
                   COALESCE(line.tax_group_id, 0) AS tax_group_id,
                   __EXTRA_TAX_DATA__ AS extra_tax_data,
                   COALESCE(line.product_id, 0) AS product_id,
                   COALESCE(line.product_uom_id, 0) AS product_uom_id,
                   COALESCE(line.display_type, '') AS display_type,
                   line.quantity,
                   line.price_unit,
                   line.discount,
                   __DEDUCTIBLE_AMOUNT__ AS deductible_amount,
                   __IS_STORNO__ AS is_storno,
                   company.account_storno,
                   line.balance,
                   line.amount_currency,
                   line.tax_base_amount
              FROM account_move_line line
              JOIN account_move line_move ON line_move.id = line.move_id
              JOIN res_company company ON company.id = line.company_id
         LEFT JOIN account_tax_repartition_line repartition
                ON repartition.id = line.tax_repartition_line_id
             WHERE line.move_id IN (SELECT id FROM protected_graph)
        ),
        graph_reach(start_id, id) AS (
            SELECT parent_id, child_id FROM graph_edges
            UNION
            SELECT reach.start_id, edge.child_id
              FROM graph_reach reach
              JOIN graph_edges edge ON edge.parent_id = reach.id
        ),
        cycle_seeds AS (
            SELECT start_id AS id
              FROM graph_reach
             WHERE start_id = id
        ),
        bad_edges AS (
            SELECT edge.parent_id, edge.child_id
              FROM graph_edges edge
              JOIN account_move parent ON parent.id = edge.parent_id
              JOIN account_move child ON child.id = edge.child_id
             WHERE parent.state != 'posted'
                OR child.state != 'posted'
                OR parent.eh_sealed IS NOT TRUE
                OR parent.eh_legacy_unverified_seal IS TRUE
                OR child.eh_sealed IS NOT TRUE
                OR child.eh_legacy_unverified_seal IS TRUE
                OR child.company_id IS DISTINCT FROM parent.company_id
                OR child.journal_id IS DISTINCT FROM parent.journal_id
                OR child.currency_id IS DISTINCT FROM parent.currency_id
                OR child.partner_id IS DISTINCT FROM parent.partner_id
                OR child.move_type IS DISTINCT FROM CASE parent.move_type
                    WHEN 'entry' THEN 'entry'
                    WHEN 'out_invoice' THEN 'out_refund'
                    WHEN 'out_refund' THEN 'out_invoice'
                    WHEN 'in_invoice' THEN 'in_refund'
                    WHEN 'in_refund' THEN 'in_invoice'
                    WHEN 'out_receipt' THEN 'out_refund'
                    WHEN 'in_receipt' THEN 'in_refund'
                    ELSE NULL
                END
                OR NOT EXISTS (
                    SELECT 1 FROM account_move_line parent_line
                     WHERE parent_line.move_id = parent.id
                )
                OR NOT EXISTS (
                    SELECT 1 FROM account_move_line child_line
                     WHERE child_line.move_id = child.id
                )
                OR EXISTS (
                    SELECT 1
                      FROM protected_line_evidence line
                     WHERE line.move_id IN (parent.id, child.id)
                     GROUP BY line.account_id,
                              line.currency_id,
                              line.partner_id,
                              line.analytic_distribution,
                              line.tax_ids,
                              line.tax_tag_ids,
                              line.tax_line_id,
                              line.tax_repartition_type,
                              line.tax_repartition_factor,
                              line.group_tax_id,
                              line.tax_group_id,
                              line.extra_tax_data,
                              line.product_id,
                              line.product_uom_id,
                              line.display_type,
                              line.quantity,
                              line.price_unit,
                              line.discount,
                              line.deductible_amount,
                              CASE
                                  WHEN line.move_id = child.id
                                   AND line.account_storno
                                  THEN NOT line.is_storno
                                  ELSE line.is_storno
                              END
                     HAVING ABS(SUM(line.balance)) > 0.000001
                        OR ABS(SUM(line.amount_currency)) > 0.000001
                        OR ABS(SUM(__TAX_BASE_SUM__)) > 0.000001
                )
        ),
        duplicate_parents AS (
            SELECT parent_id
              FROM graph_edges
             GROUP BY parent_id
            HAVING COUNT(*) != 1
        ),
        bad_seeds(id) AS (
            SELECT parent_id FROM bad_edges
            UNION
            SELECT child_id FROM bad_edges
            UNION
            SELECT parent_id FROM duplicate_parents
            UNION
            SELECT edge.child_id
              FROM graph_edges edge
              JOIN duplicate_parents duplicate
                ON duplicate.parent_id = edge.parent_id
            UNION
            SELECT id FROM cycle_seeds
        ),
        quarantine(id) AS (
            SELECT id FROM bad_seeds
            UNION
            SELECT neighbour.id
              FROM quarantine graph
              JOIN LATERAL (
                    SELECT child.id
                      FROM account_move child
                     WHERE child.reversed_entry_id = graph.id
                    UNION
                    SELECT parent.id
                      FROM account_move current_move
                      JOIN account_move parent
                        ON parent.id = current_move.reversed_entry_id
                     WHERE current_move.id = graph.id
              ) neighbour ON TRUE
        )
        UPDATE account_move move
           SET eh_sealed = FALSE,
               eh_legacy_unverified_seal = TRUE
         WHERE move.id IN (SELECT id FROM quarantine)
           AND (
                move.eh_sealed IS DISTINCT FROM FALSE
                OR move.eh_legacy_unverified_seal IS DISTINCT FROM TRUE
           )
    """
    cr.execute(
        query.replace('__EXTRA_TAX_DATA__', extra_tax_data)
        .replace('__DEDUCTIBLE_AMOUNT__', deductible_amount)
        .replace('__IS_STORNO__', is_storno)
        .replace('__TAX_BASE_SUM__', tax_base_sum)
    )
    _logger.warning(
        "Quarantined %s account.move row(s) in incomplete or ambiguous "
        "legacy sealed-reversal graphs; all moves, lines, and links were "
        "preserved.",
        cr.rowcount,
    )
