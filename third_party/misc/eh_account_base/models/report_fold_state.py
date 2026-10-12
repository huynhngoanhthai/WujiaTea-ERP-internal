# -*- encoding: utf-8 -*-
##############################################################################
#
# ERP Heritage
# Copyright (C) 2026 (https://www.erpheritage.com.au/)
#
##############################################################################
"""
eh.account.report.fold.state: per-user collapse / expand state for
hierarchical dynamic reports.

When a user expands or collapses a group line on a dynamic report,
the OWL viewer persists the choice here so the next render starts
from the same shape. Without persistence, every reload re-expands
every group (the default behaviour) and the user has to re-collapse
the irrelevant subtrees on every refresh.

One row per (user, report code, line id). The line id is the same
identifier the handler emits (e.g. 'section-assets-group-12_47'),
so the renderer can look up the saved state without round-tripping
through a separate identifier mapping.

The model is small on purpose. Sites with thousands of users running
dozens of reports will accumulate at most ~thousands of rows; SQL
constraints keep the (user, report_code, line_id) tuple unique and
the user_id index makes the renderer's per-user lookup O(1).
"""

from odoo import api, fields, models


class EhAccountReportFoldState(models.Model):
    _name = 'eh.account.report.fold.state'
    _description = "Per-user fold state for dynamic reports"
    _order = 'user_id, report_code, line_id'

    user_id = fields.Many2one(
        'res.users', required=True, ondelete='cascade', index=True,
        default=lambda self: self.env.user,
    )
    report_code = fields.Char(
        required=True, index=True,
        help=(
            "Report code that emitted the line, e.g. 'balance_sheet' "
            "or 'profit_and_loss'. Matches the code on "
            "eh.account.dynamic.report."
        ),
    )
    line_id = fields.Char(
        required=True, index=True,
        help=(
            "Unique identifier the handler emitted for the line, e.g. "
            "'section-assets-group-12_47'. Stable across reloads "
            "because it derives from chart-of-accounts ids."
        ),
    )
    is_unfolded = fields.Boolean(
        default=True,
        help=(
            "True when the user has the line expanded; false when "
            "collapsed. Default True so a freshly-encountered line "
            "starts expanded (matching the OWL viewer's first-render "
            "behaviour)."
        ),
    )

    _unique_state = models.Constraint(
        'unique(user_id, report_code, line_id)',
        'Only one fold state per (user, report, line).',
    )

    @api.model
    def get_for_user(self, report_code):
        """Return {line_id: is_unfolded} for current user + report.

        Used by the OWL viewer at mount time to seed the initial
        expand / collapse state. An empty dict means "no preferences
        recorded yet"; the viewer falls back to its default
        (everything expanded).

        Lazy-leaf rule: the viewer MUST NOT auto-restore a saved expansion
        for a lazy account leaf. Re-expanding every account on reload would
        fan out to one fetch per account and materialise every journal item
        (the big-data invariant forbids this). Lazy leaves therefore always
        start collapsed; the viewer's hydrate path skips any line whose
        payload flag `lazy` is true even if a row exists here. Persisting a
        lazy-leaf toggle is harmless (the key is an arbitrary string) but is
        never replayed on load.
        """
        rows = self.search_read(
            [
                ('user_id', '=', self.env.user.id),
                ('report_code', '=', report_code),
            ],
            ['line_id', 'is_unfolded'],
        )
        return {r['line_id']: r['is_unfolded'] for r in rows}

    @api.model
    def set_for_user(self, report_code, line_id, is_unfolded):
        """Upsert one fold-state row for current user.

        Called by the OWL viewer when the user clicks a fold caret.
        Idempotent: re-calling with the same values is a no-op write.
        """
        existing = self.search([
            ('user_id', '=', self.env.user.id),
            ('report_code', '=', report_code),
            ('line_id', '=', line_id),
        ], limit=1)
        if existing:
            if existing.is_unfolded != bool(is_unfolded):
                existing.is_unfolded = bool(is_unfolded)
            return existing
        return self.create({
            'user_id': self.env.user.id,
            'report_code': report_code,
            'line_id': line_id,
            'is_unfolded': bool(is_unfolded),
        })

    @api.model
    def reset_for_user(self, report_code):
        """Drop every saved fold-state row for current user + report.

        Used by the "Reset folding" action on the report viewer.
        """
        # ``unlink`` on an empty recordset is intentionally a no-op in the
        # ORM and therefore does not consult ACLs.  Check the model right up
        # front so a read-only auditor cannot turn the reset RPC into a
        # write-capability probe merely because no preferences exist yet.
        self.check_access_rights('unlink')
        self.search([
            ('user_id', '=', self.env.user.id),
            ('report_code', '=', report_code),
        ]).unlink()
