# Copyright 2026 Abdalrahman Shahrour
import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.tools.safe_eval import safe_eval

_logger = logging.getLogger(__name__)


class ApprovalMixin(models.AbstractModel):
    """Mixin that adds multi-stage approval capabilities to any Odoo model.

    Usage in a custom module::

        class MyModel(models.Model):
            _name = 'my.model'
            _inherit = ['my.model', 'approval.mixin', 'mail.thread',
                        'mail.activity.mixin']

    The mixin adds:
    - ``approval_state`` field (Selection) tracking the approval lifecycle.
    - ``approval_request_count`` smart-button counter.
    - ``action_submit_for_approval()`` — triggers workflow creation.
    - ``action_view_approval_requests()`` — opens linked requests.

    The source model **must** also inherit ``mail.thread`` for chatter
    integration to work.
    """

    _name = "approval.mixin"
    _description = "Approval Workflow Mixin"

    approval_state = fields.Selection(
        selection=[
            ("draft", "Draft"),
            ("pending_approval", "Pending Approval"),
            ("approved", "Approved"),
            ("rejected", "Rejected"),
            ("returned", "Returned"),
        ],
        string="Approval Status",
        default="draft",
        tracking=True,
        copy=False,
        index=True,
        help="Current state in the approval lifecycle.",
    )
    approval_request_count = fields.Integer(
        string="Approval Requests",
        compute="_compute_approval_request_count",
    )

    # ------------------------------------------------------------------
    # Compute helpers
    # ------------------------------------------------------------------

    def _compute_approval_request_count(self):
        Request = self.env["approval.request"]
        for record in self:
            record.approval_request_count = Request.search_count(
                [("res_model", "=", record._name), ("res_id", "=", record.id)]
            )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_approval_config(self):
        """Return the first matching ``approval.workflow.config`` for *self*.

        Configs are evaluated in *sequence* order; the first one whose
        optional domain filter matches the record wins.
        """
        self.ensure_one()
        configs = self.env["approval.workflow.config"].search(
            [("model_id.model", "=", self._name), ("active", "=", True)],
            order="sequence asc, id asc",
        )
        for config in configs:
            if config.domain:
                try:
                    domain = safe_eval(config.domain)
                    if self.filtered_domain(domain):
                        return config
                except Exception as exc:
                    _logger.warning(
                        "Approval config %s has an invalid domain: %s",
                        config.name,
                        exc,
                    )
                    continue
            else:
                return config
        return self.env["approval.workflow.config"]

    # ------------------------------------------------------------------
    # Public actions
    # ------------------------------------------------------------------

    def action_submit_for_approval(self):
        """Submit record(s) for approval.

        Raises :class:`~odoo.exceptions.UserError` when:
        - The record is not in ``draft`` or ``returned`` state.
        - No active workflow config exists for the model.
        - The matching config has no stages defined.
        """
        for record in self:
            if record.approval_state not in ("draft", "returned"):
                raise UserError(
                    _(
                        'Only records in "Draft" or "Returned" state can be '
                        "submitted for approval."
                    )
                )
            config = record._get_approval_config()
            if not config:
                raise UserError(
                    _('No active approval workflow is configured for model "%s".')
                    % record._name
                )
            if not config.stage_ids:
                raise UserError(
                    _('The approval workflow "%s" has no stages defined.') % config.name
                )
            self.env["approval.request"]._create_from_record(record, config)
            record.write({"approval_state": "pending_approval"})

    def action_view_approval_requests(self):
        """Smart button: open all approval requests linked to this record."""
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Approval Requests"),
            "res_model": "approval.request",
            "view_mode": "list,form",
            "domain": [
                ("res_model", "=", self._name),
                ("res_id", "=", self.id),
            ],
            "context": {
                "default_res_model": self._name,
                "default_res_id": self.id,
            },
        }
