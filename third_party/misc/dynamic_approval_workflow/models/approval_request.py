# Copyright 2026 Abdalrahman Shahrour
import logging
from datetime import date, timedelta

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError

_logger = logging.getLogger(__name__)


class ApprovalRequest(models.Model):
    """One approval request created per document / workflow pair.

    Lifecycle:
    ``pending_approval``  →  approve all stages  →  ``approved``
    ``pending_approval``  →  reject              →  ``rejected``
    ``pending_approval``  →  return              →  ``returned``
    ``returned``          →  resubmit            →  ``pending_approval`` (new request)
    """

    _name = "approval.request"
    _description = "Approval Request"
    _order = "create_date desc, id desc"
    _rec_name = "name"
    _inherit = ["mail.thread", "mail.activity.mixin"]

    # ------------------------------------------------------------------
    # Fields
    # ------------------------------------------------------------------

    name = fields.Char(
        string="Reference",
        required=True,
        copy=False,
        readonly=True,
        default=lambda self: _("New"),
        index=True,
    )
    config_id = fields.Many2one(
        comodel_name="approval.workflow.config",
        string="Workflow",
        required=True,
        ondelete="restrict",
        index=True,
        readonly=True,
    )
    res_model = fields.Char(
        string="Document Model",
        required=True,
        index=True,
        readonly=True,
    )
    res_id = fields.Integer(
        string="Document ID",
        required=True,
        index=True,
        readonly=True,
    )
    res_name = fields.Char(
        string="Document",
        readonly=True,
        help="Display name of the source document at submission time.",
    )
    state = fields.Selection(
        selection=[
            ("pending_approval", "Pending Approval"),
            ("approved", "Approved"),
            ("rejected", "Rejected"),
            ("returned", "Returned"),
        ],
        string="Status",
        default="pending_approval",
        required=True,
        tracking=True,
        index=True,
    )
    current_stage_id = fields.Many2one(
        comodel_name="approval.workflow.stage",
        string="Current Stage",
        index=True,
        readonly=True,
    )
    current_approver_ids = fields.Many2many(
        comodel_name="res.users",
        relation="approval_request_current_approver_rel",
        column1="request_id",
        column2="user_id",
        string="Current Approvers",
        readonly=True,
        help="Users who can act on the current stage.",
    )
    line_ids = fields.One2many(
        comodel_name="approval.request.line",
        inverse_name="request_id",
        string="Approval History",
        readonly=True,
    )
    requester_id = fields.Many2one(
        comodel_name="res.users",
        string="Requested By",
        default=lambda self: self.env.user,
        required=True,
        index=True,
        readonly=True,
    )
    deadline = fields.Date(
        string="Deadline",
        compute="_compute_deadline",
        store=True,
        index=True,
    )
    company_id = fields.Many2one(
        comodel_name="res.company",
        string="Company",
        related="config_id.company_id",
        store=True,
        index=True,
    )
    is_current_approver = fields.Boolean(
        string="I Am Current Approver",
        compute="_compute_is_current_approver",
        help="True when the current user can approve/reject this request.",
    )

    # ------------------------------------------------------------------
    # Compute methods
    # ------------------------------------------------------------------

    @api.depends("config_id.escalation_days", "create_date")
    def _compute_deadline(self):
        for request in self:
            if request.create_date and request.config_id.escalation_days:
                request.deadline = request.create_date.date() + timedelta(
                    days=request.config_id.escalation_days
                )
            else:
                request.deadline = False

    def _compute_is_current_approver(self):
        uid = self.env.uid
        is_manager = self.env.user.has_group(
            "dynamic_approval_workflow.group_approval_manager"
        )
        for request in self:
            request.is_current_approver = (
                is_manager or uid in request.current_approver_ids.ids
            )

    # ------------------------------------------------------------------
    # ORM overrides
    # ------------------------------------------------------------------

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("name", _("New")) == _("New"):
                vals["name"] = (
                    self.env["ir.sequence"].next_by_code("approval.request") or _("New")
                )
        return super().create(vals_list)

    # ------------------------------------------------------------------
    # Factory — called by ApprovalMixin.action_submit_for_approval
    # ------------------------------------------------------------------

    @api.model
    def _create_from_record(self, record, config):
        """Create a new :class:`ApprovalRequest` for *record* using *config*.

        :param record: single source document record
        :param config: :class:`ApprovalWorkflowConfig` to apply
        :returns: newly created :class:`ApprovalRequest`
        """
        first_stage = config.stage_ids.sorted("sequence")[:1]
        request = self.create(
            {
                "config_id": config.id,
                "res_model": record._name,
                "res_id": record.id,
                "res_name": record.display_name,
                "requester_id": self.env.uid,
                "state": "pending_approval",
            }
        )
        request._set_current_stage(first_stage, source_record=record)
        # Post a note on the source document's chatter (if it has mail.thread)
        if hasattr(record, "message_post"):
            record.message_post(
                body=_(
                    "Approval request <b>%(ref)s</b> created for workflow "
                    "<b>%(wf)s</b>."
                )
                % {"ref": request.name, "wf": config.name},
                subtype_xmlid="mail.mt_note",
            )
        return request

    # ------------------------------------------------------------------
    # Stage management helpers
    # ------------------------------------------------------------------

    def _set_current_stage(self, stage, source_record=None):
        """Move *self* to *stage*, resolve approvers, send notifications."""
        self.ensure_one()
        approvers = self._resolve_approvers(stage, source_record=source_record)
        self.write(
            {
                "current_stage_id": stage.id,
                "current_approver_ids": [(6, 0, approvers.ids)],
            }
        )
        self._notify_approvers(approvers)

    def _resolve_approvers(self, stage, source_record=None):
        """Return a ``res.users`` recordset of approvers for *stage*.

        Falls back to an empty recordset and logs a warning when resolution
        fails (e.g. the dynamic field does not exist or is empty).
        """
        self.ensure_one()
        if stage.approver_type == "user":
            return stage.approver_id
        if stage.approver_type == "group":
            return stage.group_id.user_ids
        if stage.approver_type == "field":
            record = source_record
            if record is None and self.res_model and self.res_id:
                try:
                    record = self.env[self.res_model].browse(self.res_id)
                except Exception:
                    record = None
            if record is not None and record.exists() and stage.field_name:
                try:
                    field_value = record[stage.field_name]
                    if (
                        hasattr(field_value, "_name")
                        and field_value._name == "res.users"
                    ):
                        return field_value
                except Exception as exc:
                    _logger.warning(
                        "Cannot resolve approver field '%s' on %s(%s): %s",
                        stage.field_name,
                        self.res_model,
                        self.res_id,
                        exc,
                    )
        _logger.warning(
            "Approval request %s — no approvers resolved for stage '%s'.",
            self.name,
            stage.name,
        )
        return self.env["res.users"]

    def _notify_approvers(self, approvers):
        """Send the 'new request' email to each *approvers* user."""
        self.ensure_one()
        if not approvers:
            return
        template = self.env.ref(
            "dynamic_approval_workflow.email_template_approval_request",
            raise_if_not_found=False,
        )
        if not template:
            return
        for approver in approvers:
            try:
                template.with_context(approver_name=approver.name).send_mail(
                    self.id,
                    email_values={"email_to": approver.email or ""},
                    force_send=False,
                )
            except Exception as exc:
                _logger.warning(
                    "Could not send approval notification to %s: %s",
                    approver.email,
                    exc,
                )

    # ------------------------------------------------------------------
    # Approval actions
    # ------------------------------------------------------------------

    def action_approve(self):
        """Approve the current stage.

        If more stages exist, advances to the next one; otherwise marks the
        request *approved* and updates the source document.
        """
        self.ensure_one()
        self._check_approver_access()
        self.env["approval.request.line"].create(
            {
                "request_id": self.id,
                "stage_id": self.current_stage_id.id,
                "approver_id": self.env.uid,
                "action": "approved",
                "date": fields.Datetime.now(),
            }
        )
        all_stages = self.config_id.stage_ids.sorted("sequence")
        stage_ids = all_stages.ids
        try:
            current_index = stage_ids.index(self.current_stage_id.id)
        except ValueError:
            current_index = -1
        next_stages = all_stages.filtered(
            lambda s: stage_ids.index(s.id) > current_index
        )
        if next_stages:
            next_stage = next_stages[0]
            prev_stage_name = self.current_stage_id.name
            self._set_current_stage(next_stage)
            self.message_post(
                body=_(
                    "Stage <b>%(prev)s</b> approved by %(user)s. "
                    "Advanced to stage <b>%(next)s</b>."
                )
                % {
                    "prev": prev_stage_name,
                    "user": self.env.user.name,
                    "next": next_stage.name,
                },
                subtype_xmlid="mail.mt_note",
            )
        else:
            self.write(
                {
                    "state": "approved",
                    "current_approver_ids": [(5, 0, 0)],
                }
            )
            self._update_source_state("approved")
            self.message_post(
                body=_(
                    "All stages approved by %(user)s. Document is now "
                    "<b>Approved</b>."
                )
                % {"user": self.env.user.name},
                subtype_xmlid="mail.mt_note",
            )

    def action_reject(self):
        """Open the wizard to enter a rejection reason."""
        self.ensure_one()
        self._check_approver_access()
        return self._open_action_wizard("rejected")

    def action_return(self):
        """Open the wizard to enter a return reason."""
        self.ensure_one()
        self._check_approver_access()
        return self._open_action_wizard("returned")

    def _open_action_wizard(self, action):
        return {
            "type": "ir.actions.act_window",
            "name": _("Provide a Reason"),
            "res_model": "approval.action.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_request_id": self.id,
                "default_action": action,
            },
        }

    # Called by the wizard -----------------------------------------------

    def _do_reject(self, reason=""):
        """Persist a rejection and update states."""
        self.ensure_one()
        self.env["approval.request.line"].create(
            {
                "request_id": self.id,
                "stage_id": self.current_stage_id.id,
                "approver_id": self.env.uid,
                "action": "rejected",
                "reason": reason,
                "date": fields.Datetime.now(),
            }
        )
        self.write({"state": "rejected", "current_approver_ids": [(5, 0, 0)]})
        self._update_source_state("rejected")
        self.message_post(
            body=_("Request <b>rejected</b> by %(user)s.  Reason: %(reason)s")
            % {
                "user": self.env.user.name,
                "reason": reason or _("(no reason provided)"),
            },
            subtype_xmlid="mail.mt_note",
        )

    def _do_return(self, reason=""):
        """Persist a return-to-requester and update states."""
        self.ensure_one()
        self.env["approval.request.line"].create(
            {
                "request_id": self.id,
                "stage_id": self.current_stage_id.id,
                "approver_id": self.env.uid,
                "action": "returned",
                "reason": reason,
                "date": fields.Datetime.now(),
            }
        )
        self.write({"state": "returned", "current_approver_ids": [(5, 0, 0)]})
        self._update_source_state("returned")
        self.message_post(
            body=_(
                "Request <b>returned</b> to requester by %(user)s.  "
                "Reason: %(reason)s"
            )
            % {
                "user": self.env.user.name,
                "reason": reason or _("(no reason provided)"),
            },
            subtype_xmlid="mail.mt_note",
        )

    # ------------------------------------------------------------------
    # Access guard
    # ------------------------------------------------------------------

    def _check_approver_access(self):
        """Raise if the current user cannot act on this request."""
        self.ensure_one()
        if self.state != "pending_approval":
            raise UserError(
                _('This request is not in "Pending Approval" state.')
            )
        if not self.is_current_approver:
            raise AccessError(
                _(
                    "You are not authorised to approve or reject this request. "
                    "Current approvers: %(approvers)s"
                )
                % {
                    "approvers": ", ".join(
                        self.current_approver_ids.mapped("name")
                    )
                    or _("(none)")
                }
            )

    # ------------------------------------------------------------------
    # Source-document helpers
    # ------------------------------------------------------------------

    def _get_source_record(self):
        """Browse and return the source document, or ``None``."""
        self.ensure_one()
        if self.res_model and self.res_id:
            try:
                record = self.env[self.res_model].browse(self.res_id)
                if record.exists():
                    return record
            except Exception:
                pass
        return None

    def _update_source_state(self, new_state):
        """Write *new_state* to ``approval_state`` on the source document."""
        self.ensure_one()
        record = self._get_source_record()
        if record and hasattr(record, "approval_state"):
            record.write({"approval_state": new_state})

    def action_open_document(self):
        """Navigate directly to the source document."""
        self.ensure_one()
        if not self.res_model or not self.res_id:
            raise UserError(_("No source document linked to this request."))
        return {
            "type": "ir.actions.act_window",
            "res_model": self.res_model,
            "res_id": self.res_id,
            "view_mode": "form",
            "target": "current",
        }

    # ------------------------------------------------------------------
    # Cron — escalation
    # ------------------------------------------------------------------

    @api.model
    def _cron_escalate_pending_requests(self):
        """Notify escalation users for overdue pending requests.

        Called by the nightly cron defined in ``data/approval_cron.xml``.
        """
        today = date.today()
        overdue = self.search(
            [("state", "=", "pending_approval"), ("deadline", "<", today)]
        )
        for request in overdue:
            escalation_user = request.current_stage_id.escalation_user_id
            partner_ids = (
                escalation_user.partner_id.ids if escalation_user else []
            )
            body = _(
                "⚠️ This approval request has exceeded its deadline "
                "(%(deadline)s) and requires urgent attention."
            ) % {"deadline": request.deadline}
            if escalation_user:
                body += _(
                    "  Escalated to <b>%(user)s</b>."
                ) % {"user": escalation_user.name}
            request.message_post(
                body=body,
                partner_ids=partner_ids,
                subtype_xmlid="mail.mt_note",
            )
        _logger.info(
            "Approval escalation cron: %d overdue request(s) processed.",
            len(overdue),
        )

    # ------------------------------------------------------------------
    # Server-action entry point (used from ir.actions.server)
    # ------------------------------------------------------------------

    @api.model
    def action_server_submit_approval(self):
        """Entry point for the pre-built automated-action server action.

        When called from ``ir.actions.server`` the ``active_model`` /
        ``active_ids`` context variables identify the target records.
        """
        model_name = self.env.context.get("active_model")
        rec_ids = self.env.context.get("active_ids", [])
        if not model_name or not rec_ids:
            raise UserError(
                _("No records identified in context (active_model / active_ids).")
            )
        records = self.env[model_name].browse(rec_ids)
        records.action_submit_for_approval()
