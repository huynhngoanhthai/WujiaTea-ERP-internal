# Copyright 2026 Abdalrahman Shahrour
from odoo import _, api, fields, models
from odoo.exceptions import UserError


class ApprovalActionWizard(models.TransientModel):
    """Wizard that collects a mandatory reason before rejecting or returning
    an approval request.

    Opened automatically by:
    - :meth:`~approval_request.ApprovalRequest.action_reject`
    - :meth:`~approval_request.ApprovalRequest.action_return`
    """

    _name = "approval.action.wizard"
    _description = "Approval Action Wizard"

    request_id = fields.Many2one(
        comodel_name="approval.request",
        string="Approval Request",
        required=True,
        ondelete="cascade",
    )
    action = fields.Selection(
        selection=[
            ("rejected", "Reject"),
            ("returned", "Return to Requester"),
        ],
        string="Action",
        required=True,
        default="rejected",
    )
    reason = fields.Text(
        string="Reason",
        required=True,
        help="Explain why the request is being rejected or returned. "
        "This will be visible to the requester.",
    )
    # Display-only helper fields
    request_name = fields.Char(
        related="request_id.name",
        string="Request",
        readonly=True,
    )
    res_name = fields.Char(
        related="request_id.res_name",
        string="Document",
        readonly=True,
    )
    current_stage_name = fields.Char(
        related="request_id.current_stage_id.name",
        string="Stage",
        readonly=True,
    )

    @api.model_create_multi
    def create(self, vals_list):
        return super().create(vals_list)

    def action_confirm(self):
        """Execute the chosen action on the linked approval request."""
        self.ensure_one()
        if not self.reason or not self.reason.strip():
            raise UserError(_("Please provide a reason before confirming."))
        if self.action == "rejected":
            self.request_id._do_reject(self.reason.strip())
        elif self.action == "returned":
            self.request_id._do_return(self.reason.strip())
        else:
            raise UserError(_("Unknown action: %s") % self.action)
        return {"type": "ir.actions.act_window_close"}
