# -*- encoding: utf-8 -*-
##############################################################################
#
# ERP Heritage
# Copyright (C) 2026 (https://www.erpheritage.com.au/)
#
##############################################################################
"""
account.account extension for reporting-cache freshness.

Renaming an account, changing its type or code, or moving it between account
groups all change report output (labels, classification, subtotals) without
posting a journal entry. The reporting cache keys on the per-company
eh_move_version counter, so those edits must bump it or a cached report keeps
serving figures/labels computed under the old account metadata until an
unrelated move posts.
"""

from odoo import models


class AccountAccount(models.Model):
    _inherit = 'account.account'

    # Fields whose change alters report presentation or classification.
    _EH_FIGURE_FIELDS = frozenset({
        'code', 'code_store', 'code_mapping_ids', 'name', 'account_type',
        'group_id', 'tag_ids', 'reconcile', 'company_ids', 'company_id',
    })

    def _eh_owning_company_ids(self):
        # Chart records can be visible to a branch-scoped accountant through
        # the account ``parent_of`` rule while res.company rules hide the root
        # (or another shared owner) from relational-field reads. Ownership is
        # an invalidation authority input, not caller-visible presentation, so
        # derive it under sudo before expanding the affected subtrees.
        authoritative_accounts = self.sudo()
        if 'company_ids' in self._fields:
            owner_ids = set(authoritative_accounts.mapped('company_ids.id'))
        else:
            owner_ids = set(authoritative_accounts.mapped('company_id.id'))
        if not owner_ids:
            return set()
        # Odoo 18/19 chart records owned by a root company are valid in every
        # descendant branch.  Report SQL resolves their code in that branch's
        # root context, so root metadata changes invalidate the full subtree,
        # not only the exact owner row.
        return set(self.env['res.company'].sudo().with_context(
            active_test=False,
        ).search([
            ('id', 'child_of', tuple(sorted(owner_ids))),
        ]).ids)

    def write(self, vals):
        company_ids = (
            self._eh_owning_company_ids()
            if self._EH_FIGURE_FIELDS.intersection(vals) else set()
        )
        res = super().write(vals)
        if self and self._EH_FIGURE_FIELDS.intersection(vals):
            # Cover both sides of a company-scope rehome without making
            # unrelated source ledgers stale when only a dedicated
            # consolidation-chart account changes.
            company_ids.update(self._eh_owning_company_ids())
            self.env['res.company'].sudo()._eh_bump_move_version(company_ids)
        return res
