# -*- encoding: utf-8 -*-

from odoo import _, fields, models
from odoo.exceptions import UserError


class EhApprovalDecisionWizard(models.TransientModel):
    _name = 'eh.approval.decision.wizard'
    _description = "Record approval decision"

    request_id = fields.Many2one(
        'eh.approval.request', required=True, readonly=True,
    )
    decision = fields.Selection(
        [('approve', "Approve"), ('reject', "Reject")],
        required=True, readonly=True,
    )
    comment = fields.Text(
        string="Comment / reason",
        required=True,
        help="Immutable evidence stored with the approval vote and audit log.",
    )

    def action_confirm(self):
        self.ensure_one()
        comment = (self.comment or '').strip()
        if not comment:
            raise UserError(_("Enter a comment or rejection reason."))
        if self.decision == 'approve':
            self.request_id.action_approve(comment=comment)
        elif self.decision == 'reject':
            self.request_id.action_reject(reason=comment)
        else:
            raise UserError(_("Unsupported approval decision."))
        return {'type': 'ir.actions.act_window_close'}
