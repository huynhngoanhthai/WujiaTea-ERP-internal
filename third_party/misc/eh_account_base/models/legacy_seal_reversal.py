# -*- encoding: utf-8 -*-
##############################################################################
#
# ERP Heritage
# Copyright (C) 2026 (https://www.erpheritage.com.au/)
#
##############################################################################
"""Manager review flow for immutable legacy seal quarantines."""

from odoo import _, fields, models
from odoo.exceptions import AccessError, UserError


class EhAccountLegacySealReversal(models.TransientModel):
    _name = 'eh.account.legacy.seal.reversal'
    _description = "Reverse legacy-quarantined journal entry"

    move_id = fields.Many2one(
        'account.move', required=True, readonly=True, ondelete='cascade',
        domain=[
            ('state', '=', 'posted'),
            ('eh_legacy_unverified_seal', '=', True),
            ('eh_sealed', '=', False),
        ],
    )
    company_id = fields.Many2one(
        related='move_id.company_id', readonly=True,
    )
    date = fields.Date(
        string="Correction Date",
        required=True,
        default=fields.Date.context_today,
    )
    reason = fields.Char(
        required=True,
        help=(
            "Manager review reason stored on the immutable counter-entry. "
            "The legacy original remains quarantined."
        ),
    )

    def action_reverse(self):
        self.ensure_one()
        if not self.env.user.has_group(
                'eh_account_base.group_eh_manager'):
            raise AccessError(_(
                "Only an ERP Heritage Accounting Manager can reverse a "
                "legacy-quarantined journal entry."
            ))
        move = self.move_id.sudo(False).exists()
        if not move:
            raise UserError(_("The quarantined journal entry no longer exists."))
        move._eh_check_access('read')
        reason = (self.reason or '').strip()
        if not reason:
            raise UserError(_("A documented review reason is required."))
        reference = _(
            "Reviewed legacy reversal of %(move)s: %(reason)s",
            move=move.name or '/',
            reason=reason,
        )
        values = {
            'date': self.date,
            'ref': reference,
            'invoice_date_due': self.date,
        }
        if move.is_invoice(include_receipts=True):
            values['invoice_date'] = self.date
        reversal = move._eh_reverse_reviewed_legacy_quarantine([values])
        move.message_post(body=_(
            "Legacy quarantine reviewed and corrected by %(user)s. "
            "Counter-entry: %(entry)s. Reason: %(reason)s",
            user=self.env.user.display_name,
            entry=reversal._get_html_link(),
            reason=reason,
        ))
        return {
            'type': 'ir.actions.act_window',
            'name': _("Reviewed Counter-Entry"),
            'res_model': 'account.move',
            'res_id': reversal.id,
            'view_mode': 'form',
            'target': 'current',
        }
