# -*- encoding: utf-8 -*-
##############################################################################
#
# ERP Heritage
# Copyright (C) 2026 (https://www.erpheritage.com.au/)
#
##############################################################################
"""
eh.approval.request: per-document approval state.

One request per (move, policy) pair. The request walks the rule's
ordered approver groups one step at a time. The current_step pointer
indexes into the rule's group list; advancement uses an atomic SQL
UPDATE with a stale-step guard so two concurrent approvers cannot
both advance from step N to step N+1.

State machine:

    pending -> in_review -> approved -> archived
                        \\-> rejected
                        \\-> withdrawn -> reopened (via restart)

The approved -> archived transition happens automatically when the
governed account.move posts; archived requests are kept as audit
record but do not show on the active list.
"""

import hashlib
import json
import logging
from datetime import timedelta

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tools import SQL

_logger = logging.getLogger(__name__)

APPROVAL_ENGINE_CTX = 'eh_approval_engine'


class EhApprovalRequest(models.Model):
    _name = 'eh.approval.request'
    _description = "Approval request"
    _inherit = ['mail.thread', 'mail.activity.mixin', 'eh.workflow.guard']
    _order = 'state, create_date desc, id desc'
    _rec_name = 'name'

    # State-machine fields: only the record's own actions (which run as sudo)
    # may change these, in EVERY state. A direct non-superuser RPC write is
    # refused by eh.workflow.guard.write().
    _eh_guarded_fields = (
        'state', 'current_step', 'submitted_at', 'approval_snapshot',
        'approval_snapshot_hash', 'approval_cycle', 'total_steps',
        'last_reminded_at', 'last_escalated_at', 'escalation_level',
        'escalated_to_group_id', 'requested_by_id',
    )
    _eh_create_guarded_fields = (
        'state', 'current_step', 'submitted_at', 'approval_snapshot',
        'approval_snapshot_hash', 'approval_cycle', 'total_steps',
        'last_reminded_at', 'last_escalated_at', 'escalation_level',
        'escalated_to_group_id', 'requested_by_id',
    )

    # Identity / amount fields (the move being approved, the derived policy /
    # rule, and the submitted amount) freeze once the request LEAVES 'pending'.
    # Repointing an already-submitted or approved request onto a different move,
    # or swapping in a weaker rule mid-review, are live exploits and stay
    # blocked (see write() below). While the request is still 'pending' (not
    # yet submitted) these are its OWN editable form fields: the requester or a
    # manager may correct a mis-derived policy/move before submission, so the
    # guard must not freeze them yet. They are NOT stripped on create (the bill
    # flow sets them legitimately), which is why _eh_create_guarded_fields stays
    # narrowed to just the state-machine fields.
    _eh_locked_after_pending_fields = (
        'move_id', 'policy_id', 'rule_id', 'submitted_amount',
        'requested_by_id', 'request_reference', 'request_partner_id',
        'request_date', 'request_note', 'rejection_reason',
    )

    def write(self, vals):
        # Freeze the identity/amount fields once the request has left
        # 'pending'. A submitted or approved request cannot be repointed onto
        # a different move, nor have a weaker rule swapped in, by a direct
        # non-superuser write - that is the original protection and it stays
        # intact here. A still-'pending' request keeps these fields editable so
        # its own form's move/policy/rule pickers (and their onchange-derived
        # amount) work for the normal editors.
        #
        # Provenance is env.su, never a context flag (forgeable): the
        # sanctioned server paths - reset_for_re_approval and the bill-flow
        # create, which run under sudo - are unaffected. The state-machine
        # fields (state/current_step) remain frozen in EVERY state via
        # _eh_guarded_fields and the mixin's write(), reached through super().
        if not self.env.su:
            locked = set(vals) & set(self._eh_locked_after_pending_fields)
            if locked:
                # Serialize ordinary form/RPC edits with submit/approve/post.
                # Checking ``state`` before this lock is a TOCTOU: a pending
                # edit can wait behind submission, then overwrite the frozen
                # identity after the request has entered review.
                self._eh_validate_company_closure()
                references = [
                    self._eh_resolve_reference_values(vals, current=rec)
                    for rec in self
                ]
                self._eh_lock_for_transition(
                    extra_move_ids=[move.id for move, _policy, _rule
                                    in references],
                    extra_policy_ids=[policy.id for _move, policy, _rule
                                      in references],
                )
                self.invalidate_recordset()
                self._eh_validate_company_closure()
                references = [
                    self._eh_resolve_reference_values(vals, current=rec)
                    for rec in self
                ]
            if locked and any(rec.state != 'pending' for rec in self):
                raise AccessError(_(
                    "%(model)s: %(fields)s can only be changed while the "
                    "request is still pending (before submission). A submitted "
                    "or approved request cannot be repointed by a direct "
                    "write; withdraw and restart it, or let a material change "
                    "reset it for re-approval, instead.",
                    model=self._description,
                    fields=', '.join(sorted(locked)),
                ))
        result = super().write(vals)
        if set(vals) & {
            'move_id', 'policy_id', 'rule_id', 'requested_by_id',
        }:
            self._eh_validate_company_closure()
        return result

    @api.model
    def _eh_resolve_reference_values(self, vals, current=None):
        """Validate a proposed request identity as the real caller.

        This helper deliberately runs before any sanctioned elevation and is
        reused after row locking.  A guessed foreign move/policy/rule must not
        become an oracle or a source for an engine-owned snapshot.
        """
        move_id = vals.get('move_id') or (current.move_id.id if current else 0)
        policy_id = (
            vals.get('policy_id')
            or (current.policy_id.id if current else 0)
        )
        rule_id = vals.get('rule_id') or (current.rule_id.id if current else 0)
        if not (move_id and policy_id and rule_id):
            raise UserError(_(
                "An approval request requires a move, policy, and rule."
            ))
        move = self.env['account.move'].browse(int(move_id))
        policy = self.env['eh.approval.policy'].browse(int(policy_id))
        rule = self.env['eh.approval.policy.rule'].browse(int(rule_id))
        if not self.env.su:
            move._eh_check_access('read')
            policy._eh_check_access('read')
            rule._eh_check_access('read')
        if not (move.exists() and policy.exists() and rule.exists()):
            raise UserError(_(
                "The selected approval move, policy, or rule no longer "
                "exists."
            ))
        if (
            not self.env.su
            and move.company_id.id not in self.env.companies.ids
        ):
            raise AccessError(_(
                "An approval request may only govern a move in the caller's "
                "current company context."
            ))
        if not self._eh_policy_company_matches_move(policy, move):
            raise UserError(_(
                "The approval policy must belong to the governed move's "
                "company or its accounting root company."
            ))
        if rule.policy_id != policy:
            raise UserError(_(
                "The approval rule must belong to the request policy."
            ))
        if vals.get('request_partner_id') and not self.env.su:
            self.env['res.partner'].browse(
                int(vals['request_partner_id'])
            )._eh_check_access('read')
        return move, policy, rule

    @api.model
    def _eh_policy_company_matches_move(self, policy, move):
        company = move.company_id
        valid = company
        if 'root_id' in company._fields and company.root_id != company:
            valid |= company.root_id
        return policy.company_id in valid

    @api.constrains('policy_id', 'rule_id')
    def _eh_check_rule_belongs_to_policy(self):
        for rec in self:
            if rec.rule_id and rec.policy_id \
                    and rec.rule_id.policy_id != rec.policy_id:
                raise ValidationError(_(
                    "Rule %(rule)s does not belong to policy %(policy)s; a "
                    "request's rule must come from its own policy.",
                    rule=rec.rule_id.display_name,
                    policy=rec.policy_id.display_name))

    name = fields.Char(
        required=True, copy=False, default='/', tracking=True,
    )
    move_id = fields.Many2one(
        'account.move', required=True,
        ondelete='cascade', index=True,
        copy=False,
    )
    policy_id = fields.Many2one(
        'eh.approval.policy', required=True,
        ondelete='restrict',
    )
    rule_id = fields.Many2one(
        'eh.approval.policy.rule', required=True,
        ondelete='restrict',
        help="The rule whose amount band matched at submission time.",
    )
    company_id = fields.Many2one(
        related='move_id.company_id', store=True, readonly=True,
        index=True,
    )
    currency_id = fields.Many2one(
        'res.currency',
        related='company_id.currency_id', store=True, readonly=True,
        help=(
            "Company currency used for the approval amount. Foreign-currency "
            "moves are converted before routing and snapshotting."
        ),
    )

    state = fields.Selection(
        [
            ('pending', "Pending"),
            ('in_review', "In review"),
            ('approved', "Approved"),
            ('rejected', "Rejected"),
            ('withdrawn', "Withdrawn"),
            ('archived', "Archived"),
        ],
        default='pending', required=True, tracking=True, index=True,
    )

    requested_by_id = fields.Many2one(
        'res.users', required=True,
        default=lambda self: self.env.user,
    )
    submitted_amount = fields.Float(
        digits=(16, 2), readonly=True,
        help="Move amount at submission. Used for re-approval detection.",
    )
    approval_snapshot = fields.Json(
        readonly=True, copy=False,
        help="Canonical server-owned approver authorization captured at "
             "submission time.",
    )
    approval_snapshot_hash = fields.Char(readonly=True, copy=False, index=True)
    approval_cycle = fields.Integer(default=1, readonly=True, copy=False)

    # current_step indexes into the rule's ordered step list
    # (rule_id.step_ids). 0 = first step, len(step_ids) = fully approved.
    current_step = fields.Integer(
        default=0, readonly=True, copy=False, tracking=True,
    )
    total_steps = fields.Integer(readonly=True, copy=False)
    pending_group_id = fields.Many2one(
        'res.groups', compute='_compute_pending_group', store=True,
        help="The group that owns the next signature.",
    )
    pending_group_user_ids = fields.Many2many(
        'res.users', compute='_compute_pending_group', store=True,
        help="Members of the pending group, surfaced for the kanban inbox.",
    )

    log_ids = fields.One2many(
        'eh.approval.log', 'request_id',
        readonly=True,
    )
    vote_ids = fields.One2many(
        'eh.approval.vote', 'request_id',
        readonly=True,
        help="Per-approver decisions, used for N-of-M and required "
             "approver tracking.",
    )

    # ---- rich request payload (optional context for approvers) ----
    request_reference = fields.Char(
        help="Free-form reference shown to approvers (PO number, "
             "contract id, ticket, etc.).",
    )
    request_partner_id = fields.Many2one(
        'res.partner', string="Related partner",
    )
    request_date = fields.Date(
        help="Business date the request concerns (delivery, service "
             "period, etc.); distinct from the submission timestamp.",
    )
    request_note = fields.Text(string="Approver note")

    rejection_reason = fields.Text()

    # ---- SLA / escalation tracking ----
    #
    # The cron compares due_at to fields.Datetime.now() and acts on
    # the diff: a request whose due_at is in the future and whose
    # reminder threshold has elapsed gets a chatter ping; a request
    # past due_at by escalate_after_hours gets escalated to the
    # configured group. last_escalated_at is the idempotency key so
    # the cron does not re-escalate the same request every hour.
    submitted_at = fields.Datetime(
        readonly=True, copy=False,
        help="Stamped when the request first transitions out of pending.",
    )
    due_at = fields.Datetime(
        compute='_compute_due_at', store=True,
        help=(
            "Deadline derived from rule.sla_hours. Empty when the rule "
            "has no SLA target."
        ),
    )
    is_overdue = fields.Boolean(
        compute='_compute_is_overdue',
        search='_search_is_overdue',
        help="True when the request is past its due_at and still open.",
    )
    last_reminded_at = fields.Datetime(
        readonly=True, copy=False,
        help="Stamped when the cron last sent a pre-deadline reminder.",
    )
    last_escalated_at = fields.Datetime(
        readonly=True, copy=False,
        help="Stamped when the cron last escalated the request.",
    )
    escalation_level = fields.Integer(
        default=0, readonly=True, copy=False,
        help=(
            "Number of times the SLA has been breached on this "
            "request. Each escalation pass increments by one."
        ),
    )
    escalated_to_group_id = fields.Many2one(
        'res.groups', readonly=True, copy=False,
        help=(
            "Escalation group currently authorised to sign an open step. "
            "Set only by the SLA engine and cleared on every restart or "
            "re-approval cycle."
        ),
    )
    sla_state = fields.Selection(
        [
            ('na',         "No SLA"),
            ('on_track',   "On track"),
            ('at_risk',    "At risk"),
            ('breached',   "Breached"),
        ],
        compute='_compute_sla_state', store=False,
        help="Lifecycle bucket used by dashboards and the kanban view.",
    )

    @api.depends('approval_snapshot', 'submitted_at', 'state')
    def _compute_due_at(self):
        for rec in self:
            snapshot = rec._eh_snapshot_payload_safe()
            sla = snapshot.get('sla_hours', 0) if snapshot else 0
            anchor = rec.submitted_at or rec.create_date
            if rec.state in ('approved', 'rejected', 'withdrawn', 'archived'):
                rec.due_at = False
            elif sla and anchor:
                rec.due_at = anchor + timedelta(hours=sla)
            else:
                rec.due_at = False

    @api.depends('due_at', 'state')
    def _compute_is_overdue(self):
        now = fields.Datetime.now()
        for rec in self:
            if rec.state in ('approved', 'rejected', 'withdrawn', 'archived'):
                rec.is_overdue = False
                continue
            rec.is_overdue = bool(rec.due_at and rec.due_at < now)

    def _search_is_overdue(self, operator, value):
        # Supports searching for is_overdue=True or False from views and
        # filters; backed by a domain on due_at and the open states.
        if operator not in ('=', '!='):
            raise UserError(_(
                "Unsupported search operator on is_overdue.",
            ))
        positive = bool(value) if operator == '=' else not bool(value)
        now = fields.Datetime.now()
        open_states = ('pending', 'in_review')
        if positive:
            return [
                ('state', 'in', open_states),
                ('due_at', '!=', False),
                ('due_at', '<', now),
            ]
        return [
            '|',
            ('state', 'not in', open_states),
            '|',
            ('due_at', '=', False),
            ('due_at', '>=', now),
        ]

    @api.depends('due_at', 'approval_snapshot', 'state')
    def _compute_sla_state(self):
        now = fields.Datetime.now()
        for rec in self:
            if rec.state in ('approved', 'rejected', 'withdrawn', 'archived'):
                rec.sla_state = 'na'
                continue
            if not rec.due_at:
                rec.sla_state = 'na'
                continue
            if rec.due_at < now:
                rec.sla_state = 'breached'
                continue
            anchor = rec.submitted_at or rec.create_date
            snapshot = rec._eh_snapshot_payload_safe()
            sla_hours = snapshot.get('sla_hours', 0) if snapshot else 0
            if anchor and sla_hours:
                # At-risk threshold = 80% of the SLA window consumed.
                # The constant is intentional: a tighter threshold
                # floods the inbox; a looser one misses the warning.
                consumed = (now - anchor).total_seconds() / 3600.0
                if consumed >= sla_hours * 0.8:
                    rec.sla_state = 'at_risk'
                    continue
            rec.sla_state = 'on_track'

    @api.depends(
        'approval_snapshot', 'current_step', 'state', 'vote_ids',
        'vote_ids.cycle', 'vote_ids.decision', 'escalated_to_group_id',
    )
    def _compute_pending_group(self):
        for rec in self:
            if rec.state in ('approved', 'rejected', 'withdrawn', 'archived'):
                rec.pending_group_id = False
                rec.pending_group_user_ids = False
                continue
            snapshot = rec._eh_snapshot_payload_safe()
            steps = snapshot.get('steps', []) if snapshot else []
            # The set of step indexes still awaiting signature. Sequential
            # mode exposes only the current step; parallel mode exposes
            # every step not yet satisfied. The pending group id is the
            # first such step's group (for the badge), while the user set
            # unions the group members, named approvers, and any injected
            # manager across the open steps.
            open_indexes = rec._eh_open_step_indexes()
            if not open_indexes:
                rec.pending_group_id = False
                rec.pending_group_user_ids = False
                continue
            first_idx = open_indexes[0]
            rec.pending_group_id = (
                rec.escalated_to_group_id.id
                or (
                    steps[first_idx].get('group_id')
                    if first_idx < len(steps) else False
                )
            )
            users = rec.env['res.users'].browse()
            for idx in open_indexes:
                users |= rec._eh_step_eligible_users(idx)
            rec.pending_group_user_ids = users.ids

    @api.model
    def _eh_snapshot_digest(self, payload):
        raw = json.dumps(
            payload, sort_keys=True, separators=(',', ':'), default=str,
        ).encode('utf-8')
        return hashlib.sha256(raw).hexdigest()

    def _eh_build_snapshot(self, policy, rule, amount):
        self.ensure_one()
        move = self.move_id
        steps = []
        for step in rule.step_ids.sorted(lambda row: (row.sequence, row.id)):
            eligible = step.approver_ids.filtered(
                lambda user: self._eh_user_can_access_request(user),
            )
            if step.group_id:
                # Query effective membership from the user side.  Besides
                # including implied groups, this avoids a subtle same-
                # transaction cache trap: after ``user.group_ids`` changes,
                # the inverse ``group.user_ids`` cache can still be stale.
                eligible |= self.env['res.users'].search([
                    ('all_group_ids', 'in', step.group_id.id),
                ]).filtered(lambda user: self._eh_user_can_access_request(user))
                # ``res.users.search`` applies active_test.  Preserve an
                # effective requester membership explicitly as well: this is
                # relevant to trusted inactive/superuser test or migration
                # actors and, more importantly, cannot widen authorization --
                # the requester is added only when their user-side effective
                # group relation proves membership.
                if (
                    self.requested_by_id
                    and step.group_id in self.requested_by_id.all_group_ids
                ):
                    eligible |= self.requested_by_id
            if step.inject_manager:
                eligible |= self._eh_manager_user().filtered(
                    lambda user: self._eh_user_can_access_request(user),
                )
            required_ids = set(step.required_approver_ids.ids)
            eligible_ids = set(eligible.ids)
            missing_required = required_ids - eligible_ids
            minimum = step.approval_minimum or 1
            if missing_required:
                missing = self.env['res.users'].browse(
                    sorted(missing_required),
                )
                raise UserError(_(
                    "Approval step %(step)s cannot start: required "
                    "approver(s) %(users)s are inactive, outside the move "
                    "company, or lack Accounting access.",
                    step=step.sequence,
                    users=', '.join(missing.mapped('display_name')),
                ))
            if len(eligible_ids) < minimum:
                raise UserError(_(
                    "Approval step %(step)s requires %(minimum)s distinct "
                    "approvals but only %(eligible)s active, company-scoped "
                    "Accounting approver(s) are eligible.",
                    step=step.sequence,
                    minimum=minimum,
                    eligible=len(eligible_ids),
                ))
            steps.append({
                'step_id': step.id,
                'sequence': step.sequence,
                'group_id': step.group_id.id or False,
                'eligible_user_ids': sorted(eligible.ids),
                'required_user_ids': sorted(required_ids),
                'approval_minimum': minimum,
            })
        payload = {
            'schema': 'eh-approval-authorization-v2',
            'company_id': move.company_id.id,
            'move_id': move.id,
            'move_type': move.move_type,
            # Transaction basis reviewed by the approvers.  Authorization is
            # meaningless if the payee, bank destination, dates, currency, or
            # posting-account routing can drift while signatures remain live.
            'currency_id': move.currency_id.id or False,
            'partner_id': move.partner_id.id or False,
            'partner_bank_id': move.partner_bank_id.id or False,
            'move_date': fields.Date.to_string(move.date),
            'invoice_date': fields.Date.to_string(move.invoice_date),
            'invoice_date_due': fields.Date.to_string(move.invoice_date_due),
            'payment_reference': move.payment_reference or '',
            'line_account_signature': list(
                move._eh_line_account_signature()),
            'policy_id': policy.id,
            'rule_id': rule.id,
            'submitted_amount': float(amount),
            'approval_mode': rule.approval_mode,
            'allow_self_approval': bool(policy.allow_self_approval),
            're_approval_threshold_pct': float(
                policy.re_approval_threshold_pct or 0.0),
            're_approval_threshold_abs': float(
                policy.re_approval_threshold_abs or 0.0),
            'sla_hours': int(rule.sla_hours or 0),
            'reminder_after_hours': int(rule.reminder_after_hours or 0),
            'escalate_after_hours': int(rule.escalate_after_hours or 0),
            'escalate_to_group_id': rule.escalate_to_group_id.id or False,
            'steps': steps,
        }
        return payload, self._eh_snapshot_digest(payload)

    def _eh_user_can_access_request(self, user):
        """Whether an approver can read accounting request evidence."""
        self.ensure_one()
        if not user.active or self.move_id.company_id not in user.company_ids:
            return False
        return bool(
            user.has_group('account.group_account_invoice')
            or user.has_group('account.group_account_readonly')
        )

    def _eh_snapshot_payload(self, required=True):
        self.ensure_one()
        payload = self.approval_snapshot or {}
        if not payload:
            if required:
                raise UserError(_(
                    "Approval %s has no authorization snapshot; restart and "
                    "submit it again.", self.name,
                ))
            return {}
        if self._eh_snapshot_digest(payload) != self.approval_snapshot_hash:
            raise UserError(_(
                "Approval %s failed its authorization-snapshot integrity "
                "check.", self.name,
            ))
        if (
            payload.get('move_id') != self.move_id.id
            or payload.get('company_id') != self.company_id.id
            or payload.get('move_type') != self.move_id.move_type
            or payload.get('policy_id') != self.policy_id.id
            or payload.get('rule_id') != self.rule_id.id
        ):
            raise UserError(_(
                "Approval %s failed its authorization provenance check.",
                self.name,
            ))
        currency = self.company_id.currency_id
        submitted_delta = currency.round(
            float(payload.get('submitted_amount', 0.0))
            - float(self.submitted_amount or 0.0)
        )
        if not currency.is_zero(submitted_delta):
            raise UserError(_(
                "Approval %s failed its submitted-amount provenance check.",
                self.name,
            ))
        return payload

    def _eh_snapshot_payload_safe(self):
        """Return display-only snapshot data without breaking reads.

        Integrity failures remain fatal in approve/reject/post paths, which
        call ``_eh_snapshot_payload`` directly. Stored and non-stored UI
        computes must degrade to empty/NA values so a corrupt legacy row can
        still be opened and reviewed by a manager.
        """
        self.ensure_one()
        try:
            return self._eh_snapshot_payload(required=False)
        except UserError:
            return {}

    def _eh_assert_current_move_basis(self):
        """Require the governed move to match the signed transaction basis."""
        self.ensure_one()
        payload = self._eh_snapshot_payload()
        if payload.get('schema') != 'eh-approval-authorization-v2':
            raise UserError(_(
                "Approval %s uses a legacy authorization snapshot without "
                "a complete transaction basis. Restart and submit it again.",
                self.name,
            ))
        move = self.move_id
        current = {
            'currency_id': move.currency_id.id or False,
            'partner_id': move.partner_id.id or False,
            'partner_bank_id': move.partner_bank_id.id or False,
            'move_date': fields.Date.to_string(move.date),
            'invoice_date': fields.Date.to_string(move.invoice_date),
            'invoice_date_due': fields.Date.to_string(move.invoice_date_due),
            'payment_reference': move.payment_reference or '',
            'line_account_signature': list(move._eh_line_account_signature()),
        }
        changed = sorted(
            field_name for field_name, value in current.items()
            if payload.get(field_name) != value
        )
        if changed:
            raise UserError(_(
                "Approval %(name)s no longer matches the accounting move's "
                "signed transaction basis (%(fields)s changed). Reset and "
                "submit the request again before approval or posting.",
                name=self.name,
                fields=', '.join(changed),
            ))
        return True

    def _eh_assert_current_authorization_scope(self):
        """Refuse signatures against a stale amount band or policy."""
        self.ensure_one()
        move = self.move_id
        policy = self.env['eh.approval.policy'].find_for_move(move)
        amount = move._eh_amount_for_approval()
        rule = policy.find_matching_rule(amount) if policy else False
        if (
            not policy
            or policy != self.policy_id
            or not rule
            or rule != self.rule_id
            or self.detect_material_change(amount)
        ):
            raise UserError(_(
                "Approval %s no longer matches the move's current policy, "
                "amount, or approval band. Reset and submit it again before "
                "recording another signature.", self.name,
            ))
        return True

    def _eh_validate_company_closure(self):
        if not self.env.su:
            self._eh_check_access('write')
        for request in self:
            move = request.move_id
            if not self.env.su:
                move._eh_check_access('read')
                request.policy_id._eh_check_access('read')
                request.rule_id._eh_check_access('read')
            if move.company_id.id not in self.env.companies.ids and not self.env.su:
                raise AccessError(_(
                    "An approval request may only govern a move in the "
                    "caller's current company context."
                ))
            if not request._eh_policy_company_matches_move(
                request.policy_id, move,
            ):
                raise UserError(_(
                    "The approval policy must belong to the governed move's "
                    "company or its accounting root company."
                ))
            if request.rule_id.policy_id != request.policy_id:
                raise UserError(_(
                    "The approval rule must belong to the request policy."
                ))
        return self

    def _eh_lock_for_transition(self, extra_move_ids=(), extra_policy_ids=()):
        """Lock move -> policy -> request for workflow transitions."""
        move_ids = tuple(sorted(
            set(self.mapped('move_id').ids) | {
                int(move_id) for move_id in extra_move_ids if move_id
            }
        ))
        if move_ids:
            self.env.cr.execute(
                "SELECT id FROM account_move WHERE id IN %s "
                "ORDER BY id FOR UPDATE",
                (move_ids,),
            )
            self.env['account.move'].browse(move_ids).invalidate_recordset()
        policy_ids = tuple(sorted(
            set(self.mapped('policy_id').ids) | {
                int(policy_id) for policy_id in extra_policy_ids if policy_id
            }
        ))
        if policy_ids:
            self.env.cr.execute(
                "SELECT id FROM eh_approval_policy WHERE id IN %s "
                "ORDER BY id FOR UPDATE",
                (policy_ids,),
            )
            self.env['eh.approval.policy'].browse(
                policy_ids,
            ).invalidate_recordset()
        ids = tuple(sorted(self.ids))
        if ids:
            self.env.cr.execute(
                "SELECT id FROM eh_approval_request WHERE id IN %s "
                "ORDER BY id FOR UPDATE",
                (ids,),
            )
            self.invalidate_recordset()
        return self

    def _eh_prepare_transition(self):
        caller = self
        caller._eh_validate_company_closure()
        caller._eh_lock_for_transition()
        caller._eh_validate_company_closure()
        return caller._eh_workflow_action().with_context(
            **{APPROVAL_ENGINE_CTX: True})

    def _eh_assert_no_other_active_request(self):
        """Enforce one live approval lifecycle per governed move.

        Every caller holds the move row first, so the search-and-transition
        decision is race-free without sacrificing historical rejected,
        withdrawn, or archived request rows.
        """
        for request in self:
            duplicate = self.sudo().search_count([
                ('move_id', '=', request.move_id.id),
                ('id', '!=', request.id),
                ('state', 'in', ('pending', 'in_review', 'approved')),
            ])
            if duplicate:
                raise UserError(_(
                    "Move %(move)s already has another active approval "
                    "request.", move=request.move_id.display_name,
                ))
        return self

    # ---- onchange (live form feedback) ----

    @api.onchange('move_id')
    def _onchange_move_id(self):
        """Pre-fill policy + rule + submitted amount when the user
        picks a move on a draft request.

        Without this, the form leaves the user to manually pick the
        right policy/rule for the move's company and amount, even
        though the data is fully derivable from the move. Reactive
        pre-fill turns a 4-click form-fill into a 1-click pick.
        """
        for rec in self:
            if not rec.move_id:
                continue
            policy = self.env['eh.approval.policy'].find_for_move(rec.move_id)
            if policy:
                rec.policy_id = policy
                amount = float(rec.move_id._eh_amount_for_approval())
                rec.submitted_amount = amount
                rule = policy.find_matching_rule(amount)
                if rule:
                    rec.rule_id = rule

    @api.onchange('policy_id')
    def _onchange_policy_id(self):
        """Re-evaluate the rule when the user manually swaps policy.

        Picks the rule that matches the current submitted_amount on
        the new policy; surfaces a warning when no rule matches so the
        user knows the policy/amount combination is not viable.
        """
        for rec in self:
            if not (rec.policy_id and rec.submitted_amount):
                continue
            rule = rec.policy_id.find_matching_rule(rec.submitted_amount)
            rec.rule_id = rule or False
            if not rule:
                return {
                    'warning': {
                        'title': "No matching rule",
                        'message': (
                            "Policy %s has no rule covering amount "
                            "%.2f. Pick a different policy or adjust "
                            "the policy's rule bands." % (
                                rec.policy_id.name, rec.submitted_amount,
                            )
                        ),
                    }
                }

    @api.onchange('submitted_amount')
    def _onchange_submitted_amount(self):
        """Re-pick the rule when the amount crosses a rule band.

        A request that started at 1,500 might match the 'Manager only'
        rule but bumping the amount to 12,000 should switch to the
        'Manager + Director' rule. Without this onchange, the form
        keeps the original rule and the user has no live signal that
        their change crossed a threshold.
        """
        for rec in self:
            if not (rec.policy_id and rec.submitted_amount):
                continue
            rule = rec.policy_id.find_matching_rule(rec.submitted_amount)
            if rule and rule != rec.rule_id:
                rec.rule_id = rule

    # ---- create ----

    @api.model_create_multi
    def create(self, vals_list):
        references = []
        for vals in vals_list:
            if not self.env.su:
                vals.pop('requested_by_id', None)
            references.append(self._eh_resolve_reference_values(vals))
            if vals.get('name', '/') == '/':
                seq = self.env['ir.sequence'].next_by_code(
                    'eh.approval.request',
                ) or '/'
                vals['name'] = seq
        # Move -> policy is the same order used by submission and posting. It
        # closes both direct-create duplication and the create-vs-post window
        # before the request row exists and can itself be locked.
        self._eh_lock_for_transition(
            extra_move_ids=[move.id for move, _policy, _rule in references],
            extra_policy_ids=[policy.id for _move, policy, _rule
                              in references],
        )
        references = [
            self._eh_resolve_reference_values(vals) for vals in vals_list
        ]
        seen_move_ids = set()
        for move, _policy, _rule in references:
            if move.id in seen_move_ids:
                raise UserError(_(
                    "A single create call cannot open two active approval "
                    "requests for the same accounting move."
                ))
            seen_move_ids.add(move.id)
            if move.state != 'draft':
                raise UserError(_(
                    "Only a draft accounting move can receive an approval "
                    "request."
                ))
            active = self.sudo().search_count([
                ('move_id', '=', move.id),
                ('state', 'in', ('pending', 'in_review', 'approved')),
            ])
            if active:
                raise UserError(_(
                    "This accounting move already has an active approval "
                    "request. Open or restart that request instead."
                ))
        records = super().create(vals_list)
        records._eh_validate_company_closure()
        for rec in records:
            rec._eh_schedule_step_activity()
        return records

    # ---- transitions ----

    def action_submit(self):
        """Move the request from 'pending' to 'in_review'.

        Submission is what kicks off the approver activity scheduling.
        Created requests start as 'pending' so a user can attach
        attachments or add a comment before submission; calling
        action_submit advances them.

        submitted_at is stamped here as the SLA anchor; due_at recomputes
        from this on the next read. Re-submission (via reset_for_re_
        approval) resets the anchor so the SLA window restarts cleanly
        when the underlying amount changed.
        """
        caller = self
        caller._eh_validate_company_closure()
        caller._eh_lock_for_transition()
        caller._eh_validate_company_closure()
        derived = {}
        for rec in caller:
            rec._eh_assert_no_other_active_request()
            user = self.env.user
            if (
                rec.requested_by_id != user
                and not user.has_group('eh_account_base.group_eh_manager')
            ):
                raise AccessError(_(
                    "Only the requester or an EH Accounting Manager may "
                    "submit an approval request."
                ))
            if rec.move_id.state != 'draft':
                raise UserError(_(
                    "Only a draft accounting move can be submitted for "
                    "approval."
                ))
            policy = self.env['eh.approval.policy'].find_for_move(rec.move_id)
            if not policy:
                raise UserError(_(
                    "No active approval policy applies to %s.",
                    rec.move_id.display_name,
                ))
            amount = rec.move_id._eh_amount_for_approval()
            rule = policy.find_matching_rule(amount)
            if not rule:
                raise UserError(_(
                    "The active approval policy has no rule for amount %.2f.",
                    amount,
                ))
            derived[rec.id] = (policy.id, rule.id, amount)
        self = caller._eh_workflow_action().with_context(
            **{APPROVAL_ENGINE_CTX: True})
        now = fields.Datetime.now()
        for rec in self:
            if rec.state != 'pending':
                raise UserError(_(
                    "Only pending requests can be submitted; %s is %s.",
                    rec.name, rec.state,
                ))
            policy_id, rule_id, amount = derived[rec.id]
            policy = self.env['eh.approval.policy'].browse(policy_id)
            rule = self.env['eh.approval.policy.rule'].browse(rule_id)
            snapshot, digest = rec._eh_build_snapshot(policy, rule, amount)
            if not snapshot['steps']:
                raise UserError(_(
                    "The matching approval rule has no approver steps."
                ))
            rec.write({
                'policy_id': policy.id,
                'rule_id': rule.id,
                'submitted_amount': amount,
                'approval_snapshot': snapshot,
                'approval_snapshot_hash': digest,
                'total_steps': len(snapshot['steps']),
                'current_step': 0,
                'state': 'in_review',
                'submitted_at': now,
            })
            rec._eh_log(
                'submitted',
                _("Submitted for approval; authorization snapshot %s.")
                % digest,
                snapshot=snapshot,
                snapshot_hash=digest,
            )
            rec._eh_schedule_step_activity()

    def _eh_open_decision_wizard(self, decision):
        self.ensure_one()
        self._eh_validate_company_closure()
        if self.state != 'in_review':
            raise UserError(_(
                "Only an in-review request can record a decision."
            ))
        return {
            'type': 'ir.actions.act_window',
            'name': _("Approval decision"),
            'res_model': 'eh.approval.decision.wizard',
            'view_mode': 'form',
            'views': [(False, 'form')],
            'target': 'new',
            'context': {
                'default_request_id': self.id,
                'default_decision': decision,
            },
        }

    def action_open_approve_wizard(self):
        return self._eh_open_decision_wizard('approve')

    def action_open_reject_wizard(self):
        return self._eh_open_decision_wizard('reject')

    def action_approve(self, comment=None):
        """Record the current user's approval and advance if the
        affected step(s) are now satisfied.

        A step advances only once its minimum number of distinct
        eligible approvals is met and every required approver has
        signed (N-of-M). With the default single-group step and a
        minimum of 1, the first eligible signature advances the step,
        exactly as before. Sequential rules walk one step at a time;
        parallel rules approve when every step is satisfied.
        """
        comment = (comment or '').strip()
        if not comment:
            raise UserError(_(
                "Enter an approval comment before signing this request."
            ))
        self = self._eh_prepare_transition()
        for rec in self:
            rec._eh_check_can_approve(self.env.user)
            rec._eh_record_vote(self.env.user, 'approve', comment)
            rec._eh_log('approved', comment or '')
            rec._eh_evaluate_progress()

    def action_reject(self, reason=None):
        """Reject the request. Terminal: a single eligible rejection
        rejects the whole request regardless of other votes."""
        reason = (reason or '').strip()
        if not reason:
            raise UserError(_(
                "Enter a rejection reason before rejecting this request."
            ))
        self = self._eh_prepare_transition()
        for rec in self:
            rec._eh_check_can_approve(self.env.user)
            rec._eh_record_vote(self.env.user, 'reject', reason)
            rec.write({
                'state': 'rejected',
                'rejection_reason': reason or '',
            })
            rec._eh_log('rejected', reason or '')
            rec.activity_ids.action_feedback(
                feedback=_("Rejected: %s") % (reason or '/'),
            )

    def action_force_approve(self, reason=None):
        """Bypass the remaining chain and approve outright.

        Restricted to EH Accounting Managers. Used when an authorised
        officer needs to clear a request the normal chain cannot
        complete (approver unavailable, deadlock). The override is
        logged for the audit trail.
        """
        self = self._eh_prepare_transition()
        for rec in self:
            if not self.env.user.has_group(
                'eh_account_base.group_eh_manager'
            ):
                raise UserError(_(
                    "Only an EH Accounting Manager can force-approve a "
                    "request."))
            if self.env.user == rec.requested_by_id:
                raise UserError(_(
                    "The requester cannot force-approve their own request. "
                    "Segregation of duties requires a different EH "
                    "Accounting Manager."
                ))
            if rec.state != 'in_review':
                raise UserError(_(
                    "Only in-review requests can be force-approved; %s "
                    "is %s.", rec.name, rec.state))
            rec._eh_snapshot_payload()
            rec._eh_assert_current_move_basis()
            rec._eh_assert_current_authorization_scope()
            rec.current_step = rec.total_steps
            rec.state = 'approved'
            rec._eh_log('force_approved', reason or _("Force approved."))
            rec.activity_ids.action_feedback(feedback=_("Force approved"))

    def action_withdraw(self, reason=None):
        """Withdraw the request. Allowed by the requester or a manager.

        Withdrawn requests can be restarted via action_restart, which
        moves them back to pending and resets the step pointer.
        """
        self = self._eh_prepare_transition()
        for rec in self:
            if rec.state in ('approved', 'rejected', 'archived'):
                raise UserError(_(
                    "Cannot withdraw %s in state %s.",
                    rec.name, rec.state,
                ))
            user = self.env.user
            if (
                rec.requested_by_id != user
                and not user.has_group('eh_account_base.group_eh_manager')
            ):
                raise UserError(_(
                    "Only the requester or an EH Accounting Manager "
                    "can withdraw an approval request.",
                ))
            rec.write({'state': 'withdrawn'})
            rec._eh_log('withdrawn', reason or '')
            rec.activity_ids.action_feedback(
                feedback=_("Withdrawn"),
            )

    def action_restart(self):
        self = self._eh_prepare_transition()
        for rec in self:
            if rec.state not in ('withdrawn', 'rejected'):
                raise UserError(_(
                    "Only withdrawn or rejected requests can be restarted.",
                ))
            user = self.env.user
            if (
                rec.requested_by_id != user
                and not user.has_group('eh_account_base.group_eh_manager')
            ):
                raise AccessError(_(
                    "Only the requester or an EH Accounting Manager may "
                    "restart an approval request."
                ))
            rec._eh_assert_no_other_active_request()
            rec.activity_ids.action_feedback(feedback=_("Restarted"))
            rec.write({
                'state': 'pending',
                'current_step': 0,
                'approval_cycle': (rec.approval_cycle or 1) + 1,
                'approval_snapshot': False,
                'approval_snapshot_hash': False,
                'total_steps': 0,
                'submitted_at': False,
                'rejection_reason': False,
                'last_reminded_at': False,
                'last_escalated_at': False,
                'escalation_level': 0,
                'escalated_to_group_id': False,
            })
            rec._eh_log('restarted', _("Restarted."))

    @api.private
    def action_archive(self):
        self = self._eh_prepare_transition()
        for rec in self:
            if rec.state != 'approved':
                raise UserError(_(
                    "Only approved requests can be archived.",
                ))
            if rec.move_id.state != 'posted':
                raise UserError(_(
                    "An approval request is archived only after its governed "
                    "move is posted."
                ))
            rec.state = 'archived'

    # ---- atomic advance ----

    def _eh_advance_step_atomic(self, expected_step=None):
        """Bump current_step by one if it still equals the in-memory
        value; return True on success, False if a parallel writer
        advanced it first.

        The compare-and-set guard is what makes concurrent approvals
        from two users in the same group safe: only one wins, the
        other gets a clean error and re-evaluates.
        """
        self.ensure_one()
        self.flush_recordset(['current_step', 'state'])
        expected = self.current_step if expected_step is None else expected_step
        self.env.cr.execute(SQL(
            "UPDATE eh_approval_request "
            "SET current_step = current_step + 1 "
            "WHERE id = %s AND current_step = %s "
            "AND state = 'in_review' "
            "RETURNING current_step",
            self.id, expected,
        ))
        row = self.env.cr.fetchone()
        return bool(row)

    # ---- helpers ----

    def _eh_check_can_approve(self, user):
        self.ensure_one()
        snapshot = self._eh_snapshot_payload()
        self._eh_assert_current_move_basis()
        self._eh_assert_current_authorization_scope()
        if self.state != 'in_review':
            raise UserError(_(
                "Request %s is %s; only in-review requests can be "
                "approved or rejected.",
                self.name, self.state,
            ))
        if (
            user == self.requested_by_id
            and not snapshot.get('allow_self_approval')
        ):
            raise UserError(_(
                "You submitted request %s and cannot approve or reject "
                "your own request. Segregation of duties requires a "
                "different approver to sign off.",
                self.name,
            ))
        open_indexes = self._eh_open_step_indexes()
        if not open_indexes:
            raise UserError(_(
                "Request %s has no pending step; nothing to approve.",
                self.name,
            ))
        # Cross-step segregation of duties: a user who already approved an
        # earlier step cannot sign a later one. Each step must be cleared by
        # a person who has not signed a prior step, so one approver who sits
        # in every step group cannot single-handedly walk a multi-step rule.
        signed_before = self._eh_prior_step_approvers()
        eligible_indexes = [
            idx for idx in open_indexes
            if self._eh_user_eligible_for_step(user, idx)
            and not self._eh_user_signed_prior_step(user, idx)
        ]
        if not eligible_indexes:
            if user in signed_before:
                raise UserError(_(
                    "You already approved an earlier step of request %s. "
                    "Segregation of duties requires each step to be signed "
                    "by a different approver.",
                    self.name,
                ))
            raise UserError(_(
                "You are not an eligible approver for the pending "
                "step(s) of request %s.",
                self.name,
            ))

    # ---- multi-approver eligibility / N-of-M helpers ----

    def _eh_open_step_indexes(self):
        """Step indexes still awaiting signature.

        Sequential rules expose only the current step; parallel rules
        expose every step not yet satisfied.
        """
        self.ensure_one()
        snapshot = self._eh_snapshot_payload_safe()
        total = len(snapshot.get('steps', [])) if snapshot else 0
        if self.state != 'in_review' or total == 0:
            return []
        if snapshot.get('approval_mode') == 'parallel':
            return [i for i in range(total)
                    if not self._eh_step_satisfied(i)]
        return [self.current_step] if self.current_step < total else []

    def _eh_manager_user(self):
        """The HR manager (user) of the requester, when HR is installed
        and the chain exists; otherwise an empty recordset."""
        self.ensure_one()
        empty = self.env['res.users'].browse()
        if not self.env.registry.get('hr.employee') or not self.requested_by_id:
            return empty
        employee = self.env['hr.employee'].sudo().search(
            [('user_id', '=', self.requested_by_id.id)], limit=1)
        if employee and employee.parent_id and employee.parent_id.user_id:
            return employee.parent_id.user_id
        return empty

    def _eh_step_eligible_users(self, step_index):
        """Users allowed to sign the given step: named approvers, group
        members, and the injected manager (union). Used for the pending
        approver display; per-user eligibility checks use
        _eh_user_eligible_for_step, which tests group membership from the
        user side (robust for admin / implied memberships)."""
        self.ensure_one()
        snapshot = self._eh_snapshot_payload_safe()
        steps = snapshot.get('steps', []) if snapshot else []
        if step_index < 0 or step_index >= len(steps):
            return self.env['res.users'].browse()
        step = steps[step_index]
        users = self.env['res.users'].browse(
            step.get('eligible_user_ids', []),
        )
        if self.escalated_to_group_id:
            users |= self.env['res.users'].search([
                ('all_group_ids', 'in', self.escalated_to_group_id.id),
            ])
        return users

    def _eh_user_eligible_for_step(self, user, step_index):
        """Whether `user` may sign the given step. Group membership is
        checked from the user side (group in user.group_ids) so it holds
        for the admin user and implied groups, which group.user_ids
        enumeration can miss."""
        self.ensure_one()
        snapshot = self._eh_snapshot_payload(required=False)
        steps = snapshot.get('steps', []) if snapshot else []
        if step_index < 0 or step_index >= len(steps):
            return False
        step = steps[step_index]
        return bool(
            user.id in step.get('eligible_user_ids', [])
            or (
                self.escalated_to_group_id
                and self.escalated_to_group_id in user.all_group_ids
            )
        )

    def _eh_prior_step_approvers(self, before_index=None):
        """Users who approved any step earlier than `before_index`.

        When before_index is None, returns approvers of every step (used to
        report who has already signed). The comparison is by step_index on
        the recorded votes, so it holds for both sequential and parallel
        rules regardless of the order the votes arrived in.
        """
        self.ensure_one()
        votes = self.vote_ids.filtered(
            lambda vote: vote.cycle == self.approval_cycle
            and vote.decision == 'approve')
        if before_index is not None:
            votes = votes.filtered(lambda v: v.step_index < before_index)
        return votes.mapped('user_id')

    def _eh_user_signed_prior_step(self, user, step_index):
        """Whether `user` already approved a step earlier than step_index.

        Enforces cross-step segregation of duties: an approver who cleared
        an earlier step is spent and cannot count toward a later one.
        """
        self.ensure_one()
        return user in self._eh_prior_step_approvers(before_index=step_index)

    def _eh_step_satisfied(self, step_index):
        """True when the step has its minimum distinct eligible approvals
        and every required approver has signed.

        Approvers who signed an earlier step are excluded: cross-step
        segregation of duties means the same person cannot clear two steps,
        so their vote never counts toward a later step's minimum.
        """
        self.ensure_one()
        snapshot = self._eh_snapshot_payload_safe()
        steps = snapshot.get('steps', []) if snapshot else []
        if step_index < 0 or step_index >= len(steps):
            return False
        step = steps[step_index]
        approve_voters = self.vote_ids.filtered(
            lambda v: v.cycle == self.approval_cycle
            and v.step_index == step_index
            and v.decision == 'approve'
        ).mapped('user_id')
        approvers = approve_voters.filtered(
            lambda u: self._eh_user_eligible_for_step(u, step_index)
            and not self._eh_user_signed_prior_step(u, step_index))
        required = self.env['res.users'].browse(
            step.get('required_user_ids', []))
        if required and not all(u in approvers for u in required):
            return False
        return len(approvers) >= (step.get('approval_minimum') or 1)

    def _eh_record_target_indexes(self, user):
        self.ensure_one()
        if self._eh_snapshot_payload().get('approval_mode') == 'parallel':
            return [
                idx for idx in self._eh_open_step_indexes()
                if self._eh_user_eligible_for_step(user, idx)
                and not self._eh_user_signed_prior_step(user, idx)
            ]
        return ([self.current_step]
                if self.current_step < self.total_steps else [])

    def _eh_record_vote(self, user, decision, comment):
        self.ensure_one()
        # Votes are guarded against direct tampering (see eh.approval.vote):
        # the sanctioned path records them in sudo, having already checked
        # the acting user's eligibility in _eh_check_can_approve. This method
        # is not RPC-callable (leading underscore), so the recorded user is
        # always the caller-supplied acting user, never spoofable.
        Vote = self.env['eh.approval.vote'].sudo()
        for idx in self._eh_record_target_indexes(user):
            existing = self.vote_ids.filtered(
                lambda v: v.cycle == self.approval_cycle
                and v.step_index == idx and v.user_id == user)
            if existing:
                if existing.decision != decision:
                    raise UserError(_(
                        "You already recorded a different decision for this "
                        "approval step. Decisions are immutable evidence."
                    ))
                continue
            else:
                Vote.create({
                    'request_id': self.id,
                    'cycle': self.approval_cycle,
                    'step_index': idx,
                    'user_id': user.id,
                    'decision': decision,
                    'comment': comment or '',
                })
        self.invalidate_recordset(['vote_ids'])

    def _eh_evaluate_progress(self):
        """Advance / complete the request after a vote was recorded."""
        self.ensure_one()
        self = self._eh_workflow_action()
        if self._eh_snapshot_payload().get('approval_mode') == 'parallel':
            self.invalidate_recordset(
                ['pending_group_id', 'pending_group_user_ids'])
            if all(self._eh_step_satisfied(i)
                   for i in range(self.total_steps)):
                self.current_step = self.total_steps
                self.state = 'approved'
                self._eh_log('completed', _("All steps approved."))
                self.activity_ids.action_feedback(feedback=_("Approved"))
            else:
                self._eh_clear_completed_activities()
                self._eh_schedule_step_activity()
            return
        # sequential
        if not self._eh_step_satisfied(self.current_step):
            # Step still needs more approvals (N-of-M / required).
            self.invalidate_recordset(['pending_group_user_ids'])
            return
        advanced = self._eh_advance_step_atomic()
        if not advanced:
            self.invalidate_recordset(['current_step'])
            raise UserError(_(
                "Approval step has already advanced. Refresh the "
                "request and re-evaluate; another approver may have "
                "already signed off."))
        self.invalidate_recordset(
            ['current_step', 'pending_group_id', 'pending_group_user_ids'])
        self._compute_pending_group()
        if self.current_step >= self.total_steps:
            self.state = 'approved'
            self._eh_log('completed', _("All steps approved."))
            self.activity_ids.action_feedback(feedback=_("Approved"))
        else:
            self._eh_clear_completed_activities()
            self._eh_schedule_step_activity()

    def _eh_log(self, action, comment, snapshot=None, snapshot_hash=None):
        self.ensure_one()
        vals = {
            'request_id': self.id,
            'cycle': self.approval_cycle,
            'action': action,
            'step': self.current_step,
            'user_id': self.env.user.id,
            'comment': comment or '',
        }
        if snapshot is not None:
            digest = self._eh_snapshot_digest(snapshot)
            if not snapshot_hash or digest != snapshot_hash:
                raise UserError(_(
                    "Approval %s refused to record an invalid authorization "
                    "snapshot in its immutable audit log.", self.name,
                ))
            vals.update({
                'authorization_snapshot': snapshot,
                'authorization_snapshot_hash': snapshot_hash,
            })
        self.env['eh.approval.log'].sudo().create(vals)

    def _eh_schedule_step_activity(self):
        """Schedule a To-Do for every eligible open-step approver."""
        self.ensure_one()
        if self.state != 'in_review':
            return
        open_indexes = self._eh_open_step_indexes()
        if not open_indexes:
            return
        ActType = self.env['mail.activity.type']
        todo = ActType.search([('category', '=', 'default')], limit=1)
        if not todo:
            todo = ActType.search([], limit=1)
        if not todo:
            return
        users = self.env['res.users']
        for index in open_indexes:
            users |= self._eh_step_eligible_users(index)
        for user in users.filtered('active'):
            # Scheduling the reminder must never break the approval
            # transition. Activity assignment posts a notification, which
            # raises if the assignee or company has no configured email
            # address; isolate it in a savepoint so a delivery problem
            # degrades to "no reminder" rather than rolling back the
            # approval that just advanced.
            try:
                with self.env.cr.savepoint():
                    self.activity_schedule(
                        activity_type_id=todo.id,
                        summary=_("Approve: %s") % self.name,
                        user_id=user.id,
                    )
            except Exception as exc:  # noqa: BLE001
                _logger.warning(
                    "Approval %s: could not schedule a reminder activity "
                    "for %s: %s", self.name, user.display_name, exc,
                )

    def _eh_clear_completed_activities(self):
        self.ensure_one()
        # Mark prior step's activities done so the inbox does not
        # accumulate stale items.
        self.activity_ids.action_feedback(
            feedback=_("Step completed; advanced."),
        )

    # ---- material amount change detection ----

    def detect_material_change(self, current_amount):
        """Return True when current_amount differs from submitted_amount
        by more than the policy's re-approval threshold.

        Called by account.move.write to decide whether to reset the
        approval request after an edit.
        """
        self.ensure_one()
        currency = self.company_id.currency_id
        current = currency.round(current_amount or 0.0)
        submitted = currency.round(self.submitted_amount or 0.0)
        delta_abs = currency.round(abs(current - submitted))
        if currency.is_zero(delta_abs):
            return False
        snapshot = self._eh_snapshot_payload(required=False)
        abs_floor = (
            snapshot.get('re_approval_threshold_abs', 0.0)
            if snapshot else self.policy_id.re_approval_threshold_abs
        )
        pct_threshold = (
            snapshot.get('re_approval_threshold_pct', 0.0)
            if snapshot else self.policy_id.re_approval_threshold_pct
        )
        abs_floor = currency.round(abs_floor or 0.0)
        if abs_floor and currency.compare_amounts(delta_abs, abs_floor) < 0:
            return False
        if currency.is_zero(submitted):
            return True
        delta_pct = (delta_abs / abs(submitted)) * 100.0
        return delta_pct > pct_threshold

    @api.private
    def invalidate_for_reconfiguration(self, reason=''):
        """Close stale authorization when no current rule can replace it.

        Historical snapshots, votes, and logs remain immutable. The move edit
        succeeds; posting stays fail-closed until configuration is corrected
        and a fresh request is submitted.
        """
        self = self._eh_prepare_transition()
        for rec in self:
            rec.activity_ids.action_feedback(
                feedback=_("Approval invalidated by configuration change."),
            )
            rec.write({
                'state': 'withdrawn',
                'last_reminded_at': False,
                'last_escalated_at': False,
                'escalation_level': 0,
                'escalated_to_group_id': False,
            })
            rec._eh_log(
                'invalidated',
                reason or _(
                    "Approval invalidated because no current policy rule "
                    "covers the accounting move."
                ),
            )
        return True

    @api.private
    def reset_for_re_approval(self, reason=''):
        """Reset the request after a material amount change."""
        self = self._eh_prepare_transition()
        for rec in self:
            old_digest = rec.approval_snapshot_hash or '/'
            new_amount = rec.move_id._eh_amount_for_approval()
            policy = self.env['eh.approval.policy'].find_for_move(rec.move_id)
            if not policy:
                raise UserError(_(
                    "The move no longer has an active approval policy; "
                    "review the policy configuration before resetting."
                ))
            new_rule = policy.find_matching_rule(new_amount)
            if not new_rule:
                raise UserError(_(
                    "The active approval policy has no rule for the move's "
                    "current amount %.2f.", new_amount,
                ))
            snapshot, digest = rec._eh_build_snapshot(
                policy, new_rule, new_amount)
            if not snapshot['steps']:
                raise UserError(_(
                    "The matching approval rule has no approver steps."
                ))
            # Re-derive the rule for the NEW amount before resetting the
            # state machine. When the amount crosses a band boundary
            # (e.g. 9,000 -> 50,000), the request must switch to the
            # higher band's rule so total_steps/steps reflect the
            # stronger chain (an extra CFO step, say); leaving the stale
            # lower-band rule in place would let a single low-band
            # approval satisfy a request that now needs more signatures.
            # The @api.onchange handlers that re-pick the rule only fire
            # in the request FORM (and act on a readonly amount), so they
            # never run on this server-side reset path invoked from
            # account.move.write/_post - re-select the rule here instead.
            vals = {
                'state': 'in_review',
                'current_step': 0,
                'submitted_amount': new_amount,
                'policy_id': policy.id,
                'rule_id': new_rule.id,
                'approval_cycle': (rec.approval_cycle or 1) + 1,
                'approval_snapshot': snapshot,
                'approval_snapshot_hash': digest,
                'total_steps': len(snapshot['steps']),
                'submitted_at': fields.Datetime.now(),
                'last_reminded_at': False,
                'last_escalated_at': False,
                'escalation_level': 0,
                'escalated_to_group_id': False,
            }
            rec.write(vals)
            rec._eh_log(
                'reset',
                (reason or _(
                    "Material amount change triggered re-approval."
                )) + _(
                    " Prior authorization snapshot: %(old)s; new snapshot: "
                    "%(new)s.", old=old_digest, new=digest,
                ),
                snapshot=snapshot,
                snapshot_hash=digest,
            )
            rec._eh_schedule_step_activity()

    # ---- navigation ----

    def _eh_open_form_action(self):
        """Return an act_window that opens this request in form view.

        Used by the account.move 'Request Approval' button so the
        clicking user lands on the request after creation rather than
        on a system-message dialog.
        """
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'eh.approval.request',
            'res_id': self.id,
            'view_mode': 'form',
            'views': [(False, 'form')],
            'target': 'current',
        }

    # ---- SLA reminder + escalation ----

    def action_send_reminder(self):
        """Manual reminder ping. Posts a chatter note to the current
        approver group; idempotency is left to the operator (the cron
        path uses last_reminded_at).
        """
        self = self._eh_prepare_transition()
        for rec in self:
            user = self.env.user
            if (
                rec.requested_by_id != user
                and not user.has_group('eh_account_base.group_eh_manager')
            ):
                raise AccessError(_(
                    "Only the requester or an EH Accounting Manager may "
                    "send an approval reminder."
                ))
            if rec.state != 'in_review' or not rec._eh_open_step_indexes():
                continue
            rec._eh_post_reminder(manual=True)

    def action_force_escalate(self):
        """Manual escalation. Skips the SLA window check, but still
        respects the rule's escalate_to_group_id; refuses when no
        target group is configured because escalation without a
        destination has no effect.
        """
        if not self.env.user.has_group('eh_account_base.group_eh_manager'):
            raise AccessError(_(
                "Only an EH Accounting Manager may force an escalation."
            ))
        self = self._eh_prepare_transition()
        for rec in self:
            if rec.state != 'in_review':
                continue
            snapshot = rec._eh_snapshot_payload()
            target = self.env['res.groups'].browse(
                snapshot.get('escalate_to_group_id')).exists()
            if not target:
                raise UserError(_(
                    "No escalation group is configured on rule %(name)s. "
                    "Set escalate_to_group_id on the policy rule first.",
                    name=rec.rule_id.name or rec.rule_id.id,
                ))
            rec._eh_escalate_to_group(target, manual=True)

    def _eh_post_reminder(self, manual=False):
        """Post a chatter note tagging members of the pending group.

        The cron path passes manual=False and updates last_reminded_at
        to keep the next pass idempotent. The manual button skips the
        timestamp update so a user can ping repeatedly when needed.
        """
        self.ensure_one()
        users = self.env['res.users']
        for index in self._eh_open_step_indexes():
            users |= self._eh_step_eligible_users(index)
        users = users.filtered('active')
        if not users:
            return
        partner_ids = users.mapped('partner_id').ids
        body = _(
            "Reminder: approval %(name)s for %(amount).2f is awaiting "
            "sign-off by %(group)s. Due %(due)s.",
            name=self.name,
            amount=self.submitted_amount or 0.0,
            group=self._eh_pending_approver_label(users),
            due=fields.Datetime.to_string(self.due_at) if self.due_at else _("(no SLA)"),
        )
        self.message_post(body=body, partner_ids=partner_ids)
        if not manual:
            self._eh_send_reminder_email()
            self.last_reminded_at = fields.Datetime.now()

    def _eh_pending_approver_label(self, users=None):
        self.ensure_one()
        if self.pending_group_id:
            return self.pending_group_id.name
        users = users or self.pending_group_user_ids
        names = users.mapped('display_name')
        return ', '.join(names) if names else _("named approvers")

    def _eh_send_reminder_email(self):
        """Queue shipped reminder template without risking SLA sweep state."""
        self.ensure_one()
        template = self.env.ref(
            'eh_account_approval.email_template_eh_approval_reminder',
            raise_if_not_found=False,
        )
        if not template:
            return False
        try:
            with self.env.cr.savepoint():
                template.sudo().send_mail(
                    self.id, force_send=False, raise_exception=True,
                )
        except Exception as exc:  # noqa: BLE001
            _logger.warning(
                "Approval %s: reminder email could not be queued: %s",
                self.name, exc,
            )
            return False
        return True

    def _eh_escalate_to_group(self, target_group, manual=False):
        """Promote the request to the escalation group.

        Persists a request-local authority override. Members of the target
        group can sign open steps, while the immutable policy snapshot and
        original approver chain remain unchanged. The override is audited and
        cleared on restart or re-approval.
        """
        self.ensure_one()
        users = self.env['res.users'].search([
            ('all_group_ids', 'in', target_group.id),
        ]).filtered('active')
        partner_ids = users.mapped('partner_id').ids
        body = _(
            "Escalation: approval %(name)s breached its SLA by "
            "%(hours).1f hours. Forwarding to %(group)s for "
            "intervention.",
            name=self.name,
            hours=self._eh_sla_breach_hours(),
            group=target_group.name,
        )
        self.message_post(body=body, partner_ids=partner_ids)
        self.write({
            'last_escalated_at': fields.Datetime.now(),
            'escalation_level': (self.escalation_level or 0) + 1,
            'escalated_to_group_id': target_group.id,
        })
        self.invalidate_recordset([
            'pending_group_id', 'pending_group_user_ids',
        ])
        self._eh_log(
            'escalated',
            _("Escalated to %s%s") % (
                target_group.name,
                _(" (manual)") if manual else "",
            ),
        )

    def _eh_sla_breach_hours(self):
        """Hours past due_at; zero when on track or unset."""
        self.ensure_one()
        if not self.due_at:
            return 0.0
        delta = fields.Datetime.now() - self.due_at
        return max(delta.total_seconds() / 3600.0, 0.0)

    @api.model
    def _cron_sla_sweep(self):
        """Hourly sweep over open requests with an SLA window.

        Two passes against a single search:

        1. Reminder pass. Requests whose anchor + reminder_after_hours
           is past now AND whose last_reminded_at is older than the
           reminder threshold (or empty) get a chatter ping. The
           threshold is the rule's reminder_after_hours; we re-ping
           at most once per period.
        2. Escalation pass. Requests whose due_at is past now by at
           least rule.escalate_after_hours AND whose last_escalated_at
           is empty get escalated to rule.escalate_to_group_id when
           one is set. We escalate only once per request to avoid
           a notification storm; subsequent intervention is manual.

        Per-record try/except so a single bad rule (deleted group,
        missing fields) does not block the whole sweep.
        """
        now = fields.Datetime.now()
        candidates = self.search([
            ('state', '=', 'in_review'),
            ('rule_id', '!=', False),
        ])
        for req in candidates:
            try:
                # PostgreSQL errors abort the current transaction until its
                # savepoint rolls back. A Python try/except alone cannot let
                # later requests continue safely.
                with self.env.cr.savepoint():
                    req._eh_sla_step(now)
            except Exception as exc:  # noqa: BLE001
                _logger.warning(
                    "SLA sweep failed for request %s: %s", req.name, exc,
                )

    def _eh_sla_step(self, now):
        """Apply SLA actions for a single request at clock `now`."""
        self.ensure_one()
        self._eh_lock_for_transition()
        self.invalidate_recordset()
        snapshot = self._eh_snapshot_payload(required=False)
        if not snapshot or not (
            snapshot.get('sla_hours')
            or snapshot.get('reminder_after_hours')
        ):
            return
        anchor = self.submitted_at or self.create_date
        if not anchor:
            return

        # ---- reminder pass ----
        rem_hours = snapshot.get('reminder_after_hours') or 0
        if rem_hours and self.state == 'in_review' and self.pending_group_id:
            elapsed_hours = (now - anchor).total_seconds() / 3600.0
            if elapsed_hours >= rem_hours:
                last = self.last_reminded_at
                # Re-ping every reminder_after_hours window.
                if (not last
                        or (now - last).total_seconds() / 3600.0 >= rem_hours):
                    self._eh_post_reminder(manual=False)

        # ---- escalation pass ----
        esc_hours = snapshot.get('escalate_after_hours') or 0
        target_group = self.env['res.groups'].browse(
            snapshot.get('escalate_to_group_id')).exists()
        if (esc_hours and self.due_at and self.due_at < now
                and not self.last_escalated_at):
            breach_hours = (now - self.due_at).total_seconds() / 3600.0
            if breach_hours >= esc_hours:
                if target_group:
                    self._eh_escalate_to_group(target_group, manual=False)
                else:
                    # No target group configured; still log the breach
                    # so the requester sees the miss in chatter.
                    self.message_post(body=_(
                        "SLA breached on %(name)s by %(hours).1f hours. "
                        "No escalation group is configured; manual "
                        "follow-up needed.",
                        name=self.name, hours=breach_hours,
                    ))
                    self.last_escalated_at = now
