# Copyright 2026 Abdalrahman Shahrour
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError
from odoo.tools.safe_eval import safe_eval


class ApprovalWorkflowConfig(models.Model):
    """Master configuration that binds an approval workflow to an Odoo model.

    One config = one workflow.  Multiple configs can target the same model
    as long as their *domain* filters are mutually exclusive (evaluated in
    *sequence* order — first match wins).
    """

    _name = "approval.workflow.config"
    _description = "Approval Workflow Configuration"
    _order = "sequence asc, name asc"

    name = fields.Char(
        string="Name",
        required=True,
        index=True,
        translate=True,
    )
    sequence = fields.Integer(
        string="Sequence",
        default=10,
        help="Lower sequences are evaluated first when multiple configs "
        "target the same model.",
    )
    active = fields.Boolean(default=True)
    model_id = fields.Many2one(
        comodel_name="ir.model",
        string="Model",
        required=True,
        ondelete="cascade",
        index=True,
        help="The Odoo model this workflow applies to.",
    )
    model_name = fields.Char(
        related="model_id.model",
        store=True,
        readonly=True,
        string="Technical Model Name",
    )
    domain = fields.Char(
        string="Filter Domain",
        default="[]",
        help=(
            "Optional Odoo domain to restrict which records this workflow "
            "applies to.  Leave as '[]' (or empty) to match all records of "
            "the selected model.  Example: [('amount_total', '>=', 1000)]"
        ),
    )
    stage_ids = fields.One2many(
        comodel_name="approval.workflow.stage",
        inverse_name="config_id",
        string="Approval Stages",
        copy=True,
    )
    stage_count = fields.Integer(
        compute="_compute_stage_count",
        string="Stages",
        store=True,
    )
    escalation_days = fields.Integer(
        string="Escalation After (Days)",
        default=7,
        help=(
            "Number of calendar days after which a still-pending approval "
            "request is considered overdue and the escalation user is notified."
        ),
    )
    company_id = fields.Many2one(
        comodel_name="res.company",
        string="Company",
        default=lambda self: self.env.company,
        index=True,
    )
    note = fields.Html(string="Internal Notes")
    request_count = fields.Integer(
        compute="_compute_request_count",
        string="Requests",
    )

    # ------------------------------------------------------------------
    # Computes
    # ------------------------------------------------------------------

    @api.depends("stage_ids")
    def _compute_stage_count(self):
        for config in self:
            config.stage_count = len(config.stage_ids)

    def _compute_request_count(self):
        Request = self.env["approval.request"]
        for config in self:
            config.request_count = Request.search_count(
                [("config_id", "=", config.id)]
            )

    # ------------------------------------------------------------------
    # Constraints
    # ------------------------------------------------------------------

    @api.constrains("domain")
    def _check_domain(self):
        for config in self:
            if config.domain:
                try:
                    safe_eval(config.domain)
                except Exception as exc:
                    raise ValidationError(
                        _("Invalid domain expression: %s") % str(exc)
                    ) from exc

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def action_view_requests(self):
        """Smart button: open approval requests for this configuration."""
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Approval Requests — %s") % self.name,
            "res_model": "approval.request",
            "view_mode": "kanban,list,form",
            "domain": [("config_id", "=", self.id)],
            "context": {"default_config_id": self.id},
        }

    @api.model_create_multi
    def create(self, vals_list):
        return super().create(vals_list)
