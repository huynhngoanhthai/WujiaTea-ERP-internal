# -*- encoding: utf-8 -*-
##############################################################################
#
# ERP Heritage
# Copyright (C) 2026 (https://www.erpheritage.com.au/)
#
##############################################################################
"""
eh.approval.log: per-step audit row.

Append-only by design (inherited from eh.audit.mixin). The request's
transitions create rows here; nothing else writes. Auditors and
operators query by request_id to get the full lineage of who acted,
when, and what they said.
"""

from odoo import _, api, fields, models
from odoo.exceptions import AccessError


_ACTION_SELECTION = [
    ('submitted', "Submitted"),
    ('approved', "Approved"),
    ('rejected', "Rejected"),
    ('withdrawn', "Withdrawn"),
    ('restarted', "Restarted"),
    ('reset', "Reset (re-approval triggered)"),
    ('escalated', "Escalated"),
    ('completed', "Completed"),
    ('delegated', "Delegated"),
    ('force_approved', "Force approved"),
    ('snapshot_anchored', "Authorization snapshot anchored"),
    ('invalidated', "Invalidated by configuration change"),
]


class EhApprovalLog(models.Model):
    _name = 'eh.approval.log'
    _description = "Approval log entry"
    _inherit = ['eh.audit.mixin']
    _eh_audit_writable_fields = ()

    _eh_audit_unlink_message = (
        "Approval log rows cannot be deleted. Reject the request "
        "instead if the action should be voided."
    )

    request_id = fields.Many2one(
        'eh.approval.request', required=True,
        ondelete='restrict', index=True,
    )
    cycle = fields.Integer(required=True, default=1, index=True)
    action = fields.Selection(
        _ACTION_SELECTION, required=True,
    )
    step = fields.Integer(
        help="Approval step at which this action took place.",
    )
    authorization_snapshot = fields.Json(
        readonly=True, copy=False,
        help=(
            "Immutable authorization and transaction-basis snapshot for the "
            "cycle opened by this submitted/reset log row."
        ),
    )
    authorization_snapshot_hash = fields.Char(
        readonly=True, copy=False, index=True,
    )

    @api.model_create_multi
    def create(self, vals_list):
        if not self.env.su:
            raise AccessError(_(
                "Approval log rows are created only by workflow actions."
            ))
        return super().create(vals_list)
