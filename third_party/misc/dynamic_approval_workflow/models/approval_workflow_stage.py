# Copyright 2026 Abdalrahman Shahrour
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class ApprovalWorkflowStage(models.Model):
    """One stage within an :class:`ApprovalWorkflowConfig`.

    Stages are processed in ascending *sequence* order.  For each stage the
    engine resolves one or more approver users via one of three strategies:

    ``user``
        A single, hard-coded :model:`res.users` record.

    ``group``
        All members of a :model:`res.groups` group (optionally requiring *all*
        members to approve via ``require_all_group_members``).

    ``field``
        The value of a Many2one(res.users) field on the source document (e.g.
        ``user_id``, ``responsible_id``).  The field name is resolved at
        runtime when the request is created.
    """

    _name = "approval.workflow.stage"
    _description = "Approval Workflow Stage"
    _order = "config_id, sequence asc, id asc"

    config_id = fields.Many2one(
        comodel_name="approval.workflow.config",
        string="Workflow Config",
        required=True,
        ondelete="cascade",
        index=True,
    )
    sequence = fields.Integer(string="Sequence", default=10)
    name = fields.Char(
        string="Stage Name",
        required=True,
        translate=True,
    )
    approver_type = fields.Selection(
        selection=[
            ("user", "Specific User"),
            ("group", "User Group"),
            ("field", "Dynamic Field"),
        ],
        string="Approver Type",
        required=True,
        default="user",
        help=(
            "How the approver(s) for this stage are determined:\n"
            "• Specific User — a fixed user you choose below.\n"
            "• User Group — all (or any) members of a security group.\n"
            "• Dynamic Field — a Many2one(res.users) field on the document."
        ),
    )
    approver_id = fields.Many2one(
        comodel_name="res.users",
        string="Approver",
        help="Used when Approver Type is 'Specific User'.",
    )
    group_id = fields.Many2one(
        comodel_name="res.groups",
        string="Approver Group",
        help="Used when Approver Type is 'User Group'.",
    )
    field_name = fields.Char(
        string="Approver Field",
        help=(
            "Technical name of a Many2one(res.users) field on the source "
            "model.  Example: user_id  |  responsible_id  |  reviewer_id"
        ),
    )
    require_all_group_members = fields.Boolean(
        string="Require All Group Members",
        default=False,
        help=(
            "When enabled and Approver Type is 'User Group', every member "
            "of the group must approve before the stage is considered done. "
            "(Currently implemented as 'any member can approve' when False.)"
        ),
    )
    escalation_user_id = fields.Many2one(
        comodel_name="res.users",
        string="Escalation User",
        help=(
            "User who receives a chatter notification when the request "
            "exceeds the workflow's escalation deadline at this stage."
        ),
    )

    # ------------------------------------------------------------------
    # Constraints
    # ------------------------------------------------------------------

    @api.constrains("approver_type", "approver_id", "group_id", "field_name")
    def _check_approver_config(self):
        for stage in self:
            if stage.approver_type == "user" and not stage.approver_id:
                raise ValidationError(
                    _('Stage "%s": a specific approver user is required.') % stage.name
                )
            if stage.approver_type == "group" and not stage.group_id:
                raise ValidationError(
                    _('Stage "%s": an approver group is required.') % stage.name
                )
            if stage.approver_type == "field" and not stage.field_name:
                raise ValidationError(
                    _('Stage "%s": a field name is required.') % stage.name
                )

    @api.model_create_multi
    def create(self, vals_list):
        return super().create(vals_list)
