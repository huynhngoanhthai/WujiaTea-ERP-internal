# Copyright 2026 Abdalrahman Shahrour
from odoo import api, fields, models


class ApprovalRequestLine(models.Model):
    """Immutable audit trail entry for one approver action on one stage.

    Lines are created automatically by
    :meth:`~approval_request.ApprovalRequest.action_approve`,
    :meth:`~approval_request.ApprovalRequest._do_reject`, and
    :meth:`~approval_request.ApprovalRequest._do_return`.
    They must not be modified or deleted by users.
    """

    _name = "approval.request.line"
    _description = "Approval Request History Line"
    _order = "date asc, id asc"

    request_id = fields.Many2one(
        comodel_name="approval.request",
        string="Approval Request",
        required=True,
        ondelete="cascade",
        index=True,
    )
    stage_id = fields.Many2one(
        comodel_name="approval.workflow.stage",
        string="Stage",
        ondelete="set null",
        readonly=True,
    )
    approver_id = fields.Many2one(
        comodel_name="res.users",
        string="Acted By",
        required=True,
        readonly=True,
    )
    action = fields.Selection(
        selection=[
            ("approved", "Approved"),
            ("rejected", "Rejected"),
            ("returned", "Returned"),
        ],
        string="Action",
        required=True,
        readonly=True,
    )
    reason = fields.Text(
        string="Reason / Comment",
        readonly=True,
    )
    date = fields.Datetime(
        string="Date",
        default=fields.Datetime.now,
        required=True,
        readonly=True,
    )

    @api.model_create_multi
    def create(self, vals_list):
        return super().create(vals_list)
