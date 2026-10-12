# -*- encoding: utf-8 -*-
##############################################################################
#
# ERP Heritage
# Copyright (C) 2026 (https://www.erpheritage.com.au/)
#
##############################################################################
"""
res.partner extension: pending approvals smart counter.

Surfaces "this partner has N approval requests in flight" on the partner
form. The number is computed (no storage, recomputed on form load) so a
new request appearing immediately reflects in the counter.

Why this lives here and not in res.partner core: each suite module
contributes its own smart-button counter for the metric it owns,
keeping coupling minimal. A buyer opening a vendor form sees:

  * Pending approvals  (from this module)
  * Active collections  (from eh_account_collections)
  * Open cheques  (from eh_account_pdc)
  * Overdue AR/AP  (from eh_account_credit_limit)
  * ...

Each card is one click into a filtered list of the underlying records.
"""

from odoo import _, api, fields, models
from odoo.addons.eh_account_base.tools.orm_compat import read_group_compat
from odoo.release import version_info


class ResPartner(models.Model):
    _inherit = 'res.partner'

    eh_pending_approval_count = fields.Integer(
        compute='_compute_eh_pending_approval_count',
        groups='eh_account_base.group_eh_user',
        help=(
            "Open approval requests on invoices/bills for this "
            "partner. Pending and in_review states count; approved, "
            "rejected, withdrawn and archived do not."
        ),
    )

    @api.depends_context('uid', 'allowed_company_ids')
    def _compute_eh_pending_approval_count(self):
        for partner in self:
            partner.eh_pending_approval_count = 0
        if (
            not self
            or not self.env.user.has_group('eh_account_base.group_eh_user')
        ):
            return
        Request = self.env['eh.approval.request']
        domain = [
            ('move_id.partner_id', 'in', self.ids),
            ('move_id.company_id', 'in', self.env.companies.ids),
            ('state', 'in', ('pending', 'in_review')),
        ]
        if version_info[0] >= 19:
            # Odoo 19 supports relation-path grouping. This keeps the result
            # bounded by visible partners even when they own many requests.
            groups = read_group_compat(
                Request,
                domain,
                groupby=['move_id.partner_id'],
                aggregates=['__count'],
            )
            counts = {
                partner.id: count for partner, count in groups if partner
            }
        else:
            # Older series reject relation-path grouping. Group by the stored
            # direct move FK, then prefetch move -> partner in one query.
            groups = read_group_compat(
                Request,
                domain,
                groupby=['move_id'],
                aggregates=['__count'],
            )
            counts_by_move = {
                move.id: count for move, count in groups if move
            }
            moves = self.env['account.move'].browse(counts_by_move)
            counts = {}
            for move in moves:
                partner_id = move.partner_id.id
                if partner_id:
                    counts[partner_id] = (
                        counts.get(partner_id, 0) + counts_by_move[move.id]
                    )
        for partner in self:
            partner.eh_pending_approval_count = counts.get(partner.id, 0)

    def _compute_application_statistics_hook(self):
        statistics = super()._compute_application_statistics_hook()
        if (
            not self
            or not self.env.user.has_group('eh_account_base.group_eh_user')
        ):
            return statistics
        for partner in self.filtered('eh_pending_approval_count'):
            statistics[partner.id].append({
                'iconClass': 'fa-hourglass-half',
                'value': partner.eh_pending_approval_count,
                'label': _('Pending Approvals'),
                'tagClass': 'o_tag_color_3',
                'actionMethod': 'action_view_eh_pending_approvals',
            })
        return statistics

    def action_view_eh_pending_approvals(self):
        """Open the approval-request list filtered to this partner."""
        self.ensure_one()
        self._eh_check_access('read')
        return {
            'type': 'ir.actions.act_window',
            'name': 'Pending approvals',
            'res_model': 'eh.approval.request',
            'view_mode': 'list,form',
            'views': [(False, 'list'), (False, 'form')],
            'domain': [
                ('move_id.partner_id', '=', self.id),
                ('move_id.company_id', 'in', self.env.companies.ids),
                ('state', 'in', ('pending', 'in_review')),
            ],
            'context': {'default_move_id': False},
        }
