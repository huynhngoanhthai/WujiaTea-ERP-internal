# Copyright 2026 Abdalrahman Shahrour
from odoo import _, models
from odoo.exceptions import UserError


class SaleOrder(models.Model):
    _inherit = ["sale.order", "approval.mixin"]

    def action_confirm(self):
        """Require approval before confirming when a sale workflow is configured."""
        for order in self:
            if order.state not in ("draft", "sent"):
                continue

            config = order._get_approval_config()
            if not config:
                continue

            if order.approval_state == "approved":
                continue
            if order.approval_state in ("draft", "returned"):
                raise UserError(
                    _(
                        'Submit the quotation for approval before confirming it. '
                        'Order: "%s".'
                    )
                    % order.display_name
                )
            if order.approval_state == "pending_approval":
                raise UserError(
                    _(
                        'This quotation is still pending approval and cannot be '
                        'confirmed yet. Order: "%s".'
                    )
                    % order.display_name
                )
            if order.approval_state == "rejected":
                raise UserError(
                    _(
                        'This quotation was rejected. Return it to draft/returned, '
                        'edit, and resubmit for approval. Order: "%s".'
                    )
                    % order.display_name
                )

        return super().action_confirm()

    def action_draft(self):
        """Reset approval state when order is moved back to quotation."""
        result = super().action_draft()
        self.filtered(lambda order: order.approval_state != "draft").write(
            {"approval_state": "draft"}
        )
        return result
