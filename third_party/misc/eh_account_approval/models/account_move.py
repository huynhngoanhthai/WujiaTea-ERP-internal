# -*- encoding: utf-8 -*-
##############################################################################
#
# ERP Heritage
# Copyright (C) 2026 (https://www.erpheritage.com.au/)
#
##############################################################################
"""
account.move integration: gate _post() on approval.

When a policy applies to a draft move and no approved approval request
exists, _post raises a UserError naming the policy. The approver
clicks Submit -> approve -> approve... -> approved on the request,
the move can then post.

Material amount changes after submission reset the request via the
detect_material_change/reset_for_re_approval pair on the request
model. The reset flips the state back to in_review at step 0 and
schedules fresh approver activities.
"""

from odoo import _, api, fields, models
from odoo.exceptions import UserError


_EH_APPROVAL_PARENT_WRITE_CONTEXT = 'eh_approval_parent_write_capability'
_EH_APPROVAL_PARENT_WRITE_CAPABILITY = object()


class AccountMove(models.Model):
    _inherit = 'account.move'

    eh_approval_request_ids = fields.One2many(
        'eh.approval.request', 'move_id',
        string="Approval requests",
        copy=False,
    )
    eh_active_approval_request_id = fields.Many2one(
        'eh.approval.request',
        compute='_compute_active_request', store=True,
        help=(
            "The currently-effective approval request for this move. "
            "Empty when no policy applies, no request exists, or the "
            "request was withdrawn / rejected."
        ),
    )
    eh_approval_state = fields.Selection(
        related='eh_active_approval_request_id.state',
        string="Approval state",
        readonly=True, store=False,
    )
    eh_requires_approval = fields.Boolean(
        compute='_compute_requires_approval',
        help=(
            "True when a policy applies to this move and the approval "
            "is not yet complete. Used by the form to surface the "
            "Submit for approval button."
        ),
    )

    @api.depends(
        'eh_approval_request_ids',
        'eh_approval_request_ids.state',
    )
    def _compute_active_request(self):
        for move in self:
            # create_date is False on in-memory NewId records during an
            # onchange; sorting a raw False against datetimes raises
            # TypeError, so fall back to "now" for unsaved rows.
            active = move.eh_approval_request_ids.filtered(
                lambda r: r.state in ('pending', 'in_review', 'approved'),
            ).sorted(
                lambda r: r.create_date or fields.Datetime.now(),
                reverse=True,
            )
            move.eh_active_approval_request_id = active[:1].id

    @api.depends('eh_active_approval_request_id', 'eh_approval_state', 'state')
    def _compute_requires_approval(self):
        for move in self:
            if move.state != 'draft':
                move.eh_requires_approval = False
                continue
            policy = self.env['eh.approval.policy'].find_for_move(move)
            if not policy:
                move.eh_requires_approval = False
                continue
            rule = policy.find_matching_rule(move._eh_amount_for_approval())
            if not rule:
                # Active policy + uncovered amount is a fail-closed
                # configuration gap. Surface the request action, which gives
                # the administrator an explicit band error.
                move.eh_requires_approval = True
                continue
            req = move._eh_server_approval_request()
            move.eh_requires_approval = not (req and req.state == 'approved')

    def _eh_server_approval_request(self):
        """Return server-owned approval evidence after move authorization."""
        self.ensure_one()
        if not self.env.su:
            self._eh_check_access('read')
        return self.sudo().eh_active_approval_request_id

    def _eh_amount_for_approval(self):
        """Return the absolute amount the policy compares against.

        Vendor bills / customer invoices use amount_total; journal
        entries fall back to the sum of debits, which is a sensible
        scalar even for non-invoice moves.
        """
        self.ensure_one()
        if self.move_type in ('in_invoice', 'in_refund', 'out_invoice', 'out_refund'):
            amount = self.amount_total or 0.0
            # Policy thresholds are stated in company currency, but a foreign-
            # currency bill's amount_total is in the document currency. Convert
            # so a 10,000 USD bill on a EUR company routes on its EUR value,
            # not a raw 10,000 compared against EUR bands.
            move_currency = self.currency_id
            company = self.company_id or self.env.company
            company_currency = company.currency_id
            if move_currency and company_currency \
                    and move_currency != company_currency:
                amount = move_currency._convert(
                    amount, company_currency, company,
                    self.invoice_date or self.date
                    or fields.Date.context_today(self),
                )
            return amount
        # Journal entries: debits are already in company currency.
        return sum(self.line_ids.mapped('debit')) or 0.0

    def _eh_approval_entry_origin(self):
        """Classify persisted ``entry`` provenance for policy routing.

        Field names changed across Odoo series (``payment_id`` became
        ``origin_payment_id``), and optional accounting engines add their own
        source fields.  Probe only installed fields.  Specific origins win
        over the broader automatic bucket, so a reversal of a generated move
        remains a reversal for approval purposes.
        """
        self.ensure_one()
        if self.move_type != 'entry':
            return False

        def has_value(field_name):
            return field_name in self._fields and bool(self[field_name])

        if has_value('reversed_entry_id'):
            return 'reversal'
        if has_value('statement_line_id'):
            return 'bank_statement'
        if has_value('origin_payment_id') or has_value('payment_id'):
            return 'payment'

        automatic_links = (
            'tax_cash_basis_rec_id',
            'tax_cash_basis_origin_move_id',
            'auto_post_origin_id',
            'exchange_diff_partial_ids',
            'adjusting_entry_origin_move_ids',
            'asset_id',
            'deferred_original_move_ids',
            'generating_loan_line_id',
            'closing_return_id',
            'transfer_model_id',
        )
        if any(has_value(field_name) for field_name in automatic_links):
            return 'automatic'
        if 'auto_post' in self._fields and self.auto_post != 'no':
            return 'automatic'
        return 'manual'

    # ---- public actions ----

    def _eh_active_approval_moves(self):
        """Return input moves carrying a live request, without ACL leakage."""
        move_ids = tuple(sorted(self.ids))
        if not move_ids:
            return self.browse()
        requests = self.env['eh.approval.request'].sudo().search([
            ('move_id', 'in', move_ids),
            ('state', 'in', ('pending', 'in_review', 'approved')),
        ])
        active_ids = set(requests.mapped('move_id').ids)
        return self.filtered(lambda move: move.id in active_ids)

    def _eh_scoped_approval_targets(self):
        """Return moves/policies that need pessimistic serialization.

        A move is relevant when it has live approval state or currently
        matches an active policy amount band.  Everything else stays on core
        Odoo's normal posting path with no approval row lock.
        """
        active_ids = set(self._eh_active_approval_moves().ids)
        moves = self.browse()
        policies = self.env['eh.approval.policy']
        for move in self:
            policy = self.env['eh.approval.policy'].find_for_move(move)
            rule = (
                policy.find_matching_rule(move._eh_amount_for_approval())
                if policy else False
            )
            if move.id in active_ids or policy:
                moves |= move
                policies |= policy
        return moves, policies

    def _eh_lock_approval_scope(self, policy_ids=()):
        """Lock move -> relevant policies -> live requests.

        Move row is shared serialization root used by request creation,
        posting, mutation resets, and transitions.  Policy rows stabilize
        applicable definitions.  Company rows and unrelated historical
        requests never enter lock set.
        """
        self._eh_check_access('write')
        move_ids = tuple(sorted(self.ids))
        if move_ids:
            self.env.cr.execute(
                "SELECT id FROM account_move WHERE id IN %s "
                "ORDER BY id FOR UPDATE",
                (move_ids,),
            )
            self.invalidate_recordset()
            # Request creation also locks its move first. Once these rows are
            # ours, no new live request can appear while we discover policy
            # dependencies and finish the ordered lock acquisition.
            self.env.cr.execute(
                "SELECT DISTINCT policy_id FROM eh_approval_request "
                "WHERE move_id IN %s "
                "AND state IN ('pending', 'in_review', 'approved')",
                (move_ids,),
            )
            request_policy_ids = {row[0] for row in self.env.cr.fetchall()}
            locked_policy_ids = tuple(sorted(
                request_policy_ids | {
                    int(policy_id) for policy_id in policy_ids if policy_id
                },
            ))
            if locked_policy_ids:
                self.env.cr.execute(
                    "SELECT id FROM eh_approval_policy WHERE id IN %s "
                    "ORDER BY id FOR UPDATE",
                    (locked_policy_ids,),
                )
                self.env['eh.approval.policy'].browse(
                    locked_policy_ids,
                ).invalidate_recordset()
            self.env.cr.execute(
                "SELECT id FROM eh_approval_request WHERE move_id IN %s "
                "AND state IN ('pending', 'in_review', 'approved') "
                "ORDER BY id FOR UPDATE",
                (move_ids,),
            )
            request_ids = tuple(row[0] for row in self.env.cr.fetchall())
            if request_ids:
                self.env['eh.approval.request'].browse(
                    request_ids
                ).invalidate_recordset()
            self.invalidate_recordset([
                'eh_approval_request_ids',
                'eh_active_approval_request_id',
            ])
        return self

    def action_eh_view_approval_request(self):
        """Open the active approval request from a stat button on the
        move form. Returns an act_window that lands on the request
        directly so the user doesn't need to navigate via the menu.
        """
        self.ensure_one()
        if not self.eh_active_approval_request_id:
            return False
        return {
            'type': 'ir.actions.act_window',
            'name': 'Approval request',
            'res_model': 'eh.approval.request',
            'res_id': self.eh_active_approval_request_id.id,
            'view_mode': 'form',
            'views': [(False, 'form')],
        }

    def action_eh_request_approval(self):
        """Create an approval request for this move and submit it.

        If a request already exists in pending or in_review, navigate
        to it. If a prior request was rejected or withdrawn, restart
        it. Otherwise create a fresh request.
        """
        policies = self.env['eh.approval.policy']
        for move in self:
            policy = self.env['eh.approval.policy'].find_for_move(move)
            if not policy:
                raise UserError(_(
                    "No approval policy applies to %s. Configure one "
                    "or post directly.",
                    move.display_name,
                ))
            policies |= policy
        self._eh_lock_approval_scope(policy_ids=policies.ids)
        for move in self:
            policy = self.env['eh.approval.policy'].find_for_move(move)
            if not policy:
                raise UserError(_(
                    "No approval policy applies to %s. Configure one "
                    "or post directly.",
                    move.display_name,
                ))
            amount = move._eh_amount_for_approval()
            rule = policy.find_matching_rule(amount)
            if not rule:
                raise UserError(_(
                    "Policy %(policy)s has no rule covering amount "
                    "%(amt).2f. Adjust the policy's amount bands.",
                    policy=policy.name, amt=amount,
                ))
            existing = move.eh_active_approval_request_id
            if existing and existing.state == 'in_review':
                return existing._eh_open_form_action()
            if existing and existing.state == 'pending':
                existing.action_submit()
                return existing._eh_open_form_action()
            # Create through the actor's ACLs in pending, then let the public
            # submission action re-derive and snapshot every authoritative
            # field under the move/request locks.
            request = self.env['eh.approval.request'].create({
                'move_id': move.id,
                'policy_id': policy.id,
                'rule_id': rule.id,
                'submitted_amount': amount,
            })
            request.action_submit()
            return request._eh_open_form_action()

    def unlink(self):
        """Preserve approval evidence and replace raw FK failures."""
        if not self.env.su:
            self._eh_check_access('unlink')
        historical = self.env['eh.approval.request'].sudo().search([
            ('move_id', 'in', self.ids),
            '|',
            ('state', '!=', 'pending'),
            '|',
            ('log_ids', '!=', False),
            ('vote_ids', '!=', False),
        ], limit=1)
        if historical:
            raise UserError(_(
                "Accounting move %(move)s has approval history %(request)s "
                "and cannot be deleted. Keep the draft as audit evidence, "
                "or withdraw its active request and cancel the move.",
                move=historical.move_id.display_name,
                request=historical.display_name,
            ))
        return super().unlink()

    # ---- post gate ----

    def _post(self, soft=True):
        """Block posting until the approval request is approved.

        Runs BEFORE the upstream _post so the upstream side effects
        (sequence numbering, reconciliation, journal entry validation)
        only fire after approval.
        """
        candidates = self.filtered(lambda move: move.state != 'posted')
        guarded, policies = candidates._eh_scoped_approval_targets()
        if guarded:
            guarded._eh_lock_approval_scope(policy_ids=policies.ids)
        for move in candidates:
            # A post-time mismatch is rejected without claiming to persist a
            # reset: UserError rolls back same-transaction mutations. Ordinary
            # form writes perform the durable reset before this gate.
            move._eh_check_re_approval_after_edit()
            move._eh_check_approval_gate()
        result = super()._post(soft=soft)
        # Mark the approval request archived once the move actually
        # posts so the active list view stops showing it.
        for move in self:
            request = move._eh_server_approval_request()
            if move.state == 'posted' and request:
                request.action_archive()
        return result
    def _eh_check_approval_gate(self):
        self.ensure_one()
        policy = self.env['eh.approval.policy'].find_for_move(self)
        if not policy:
            return
        amount = self._eh_amount_for_approval()
        rule = policy.find_matching_rule(amount)
        if not rule:
            raise UserError(_(
                "Policy %(policy)s has no approval rule covering amount "
                "%(amount).2f. Posting fails closed until its amount bands "
                "are corrected.",
                policy=policy.display_name,
                amount=amount,
            ))
        request = self._eh_server_approval_request()
        if not request:
            raise UserError(_(
                "%(move)s requires approval per policy %(policy)s "
                "before posting. Click 'Request Approval' to start.",
                move=self.display_name, policy=policy.name,
            ))
        if request.state != 'approved':
            raise UserError(_(
                "%(move)s has approval request %(req)s in state "
                "%(state)s. Posting is blocked until the request is "
                "approved.",
                move=self.display_name, req=request.name,
                state=request.state,
            ))
        snapshot = request._eh_snapshot_payload()
        request._eh_assert_current_move_basis()
        if snapshot.get('policy_id') != policy.id:
            raise UserError(_(
                "%s was approved under a different policy snapshot; "
                "re-approval is required.", self.display_name,
            ))
        # Defense in depth: the approved request must have been signed
        # under the rule that matches the CURRENT amount. If the amount
        # was raised into a higher band after approval and the request
        # still points at the weaker (stale) band's rule, the approval
        # does not satisfy the stronger chain the new amount requires.
        # detect_material_change/reset covers most edits, but a band
        # crossing that stays below the re-approval threshold (e.g. a
        # 9,500 bill approved under the one-step rule bumped to 10,400,
        # under the percentage floor yet across the two-step boundary)
        # slips past it - this equality check blocks the mismatch outright.
        if request.rule_id != rule:
            raise UserError(_(
                "%(move)s was approved under rule %(approved)s but its "
                "current amount %(amt).2f now matches rule %(current)s. "
                "The amount changed approval bands after sign-off; "
                "re-approval under the correct rule is required before "
                "posting.",
                move=self.display_name,
                approved=request.rule_id.display_name,
                amt=amount,
                current=rule.display_name,
            ))

    def _eh_check_re_approval_after_edit(self, raise_on_reset=True):
        """If the move's amount changed materially since submission,
        reset the approval and (optionally) block the post until
        re-approval.

        Called from `_post` (with raise_on_reset=True) so an edit-
        and-post flow blocks. Also called from `write` (with
        raise_on_reset=False) so an edit alone resets the approval
        but does not raise mid-write; the next post attempt then sees
        the reset request and blocks via `_eh_check_approval_gate`.
        """
        self.ensure_one()
        if not self.env.su:
            self._eh_check_access('write')
        request = self._eh_server_approval_request()
        if not request:
            return False
        if request.state not in ('in_review', 'approved'):
            return False
        current = self._eh_amount_for_approval()
        policy = self.env['eh.approval.policy'].find_for_move(self)
        current_rule = (
            policy.find_matching_rule(current) if policy else False
        )
        authorization_changed = bool(
            not policy
            or request.policy_id != policy
            or not current_rule
            or request.rule_id != current_rule
        )
        material_changed = request.detect_material_change(current)
        if not authorization_changed and not material_changed:
            return False
        if not policy:
            reason = _(
                "The approval policy used by this request is no longer "
                "active for the move."
            )
        elif not current_rule:
            reason = _(
                "Policy %(policy)s has no amount band covering %(amount).2f.",
                policy=policy.display_name,
                amount=current,
            )
        elif authorization_changed:
            reason = (
            _(
                "Move amount changed approval bands from %(old)s to "
                "%(new)s; re-approval under the current rule is required.",
                old=request.rule_id.display_name,
                new=current_rule.display_name,
            )
            )
        else:
            reason = _(
                "Move amount changed from %(old).2f to %(new).2f after "
                "approval; re-approval required.",
                old=request.submitted_amount,
                new=current,
            )
        if raise_on_reset:
            raise UserError(_(
                "Approval evidence is stale: %(reason)s Save the corrected "
                "draft first so its approval lifecycle can be updated, then "
                "complete the required review before posting.",
                reason=reason,
            ))
        if not policy or not current_rule:
            request.invalidate_for_reconfiguration(reason=reason)
        else:
            request.reset_for_re_approval(reason=reason)
        return True

    def _eh_line_account_signature(self):
        """Return the multiset of line-account ids on this move.

        Used to detect an in-place account redirection: rewriting a
        posting line to a different account at the same debit/credit
        total leaves amount_total untouched, so the amount-based
        material-change check never fires. Comparing this signature
        before and after a write surfaces that redirection so it can be
        treated as a payment-routing change. Sorted so ordering of the
        line commands is irrelevant.
        """
        self.ensure_one()
        # Keep multiplicity.  A recordset ``mapped(...).ids`` de-duplicates
        # accounts, which misses A/B/B -> A/A/B redirections even though one
        # posting line moved to a different destination.
        return tuple(sorted(
            line.account_id.id for line in self.line_ids if line.account_id
        ))

    def _eh_reset_routing_change(self, changed_fields, raise_on_reset=True,
                                 account_redirected=False):
        """Force re-approval when a payment-routing field changed.

        Unlike the amount check, any change to the payee bank account,
        the payment due date, or the destination account of a posting
        line resets the approved request regardless of the amount
        threshold: redirecting a paid bill to another account or
        shifting its due date is a segregation-of-duties break on its
        own. Returns True when a reset was performed.

        `account_redirected` is passed by write() when the set of line
        accounts changed at an unchanged total; it forces the reset even
        though no literal routing field name appears in changed_fields.
        """
        self.ensure_one()
        if not self.env.su:
            self._eh_check_access('write')
        request = self._eh_server_approval_request()
        if not request:
            return False
        if request.state not in ('in_review', 'approved'):
            return False
        touched = sorted(
            set(changed_fields) & set(self._EH_ROUTING_TRIGGER_FIELDS),
        )
        if account_redirected and 'line account' not in touched:
            touched.append('line account')
        if not touched:
            return False
        request.reset_for_re_approval(
            reason=_(
                "Payment-routing field(s) %(fields)s changed after "
                "approval; re-approval required.",
                fields=", ".join(touched),
            ),
        )
        if raise_on_reset:
            raise UserError(_(
                "A payment-routing field (payee bank account or due "
                "date) changed after approval. The request has been "
                "reset; every step must re-sign before posting.",
            ))
        return True

    # Fields that, when changed on a draft move with an approved
    # request attached, should trigger the re-approval check.
    _EH_REAPPROVAL_TRIGGER_FIELDS = (
        'invoice_line_ids', 'line_ids',
        'amount_total', 'amount_untaxed', 'amount_tax',
        'currency_id', 'partner_id', 'company_id', 'move_type',
        'date', 'invoice_date',
        'invoice_date_due', 'partner_bank_id', 'payment_reference',
    )

    # Payment-routing / due-date fields where ANY change after approval
    # must force re-approval regardless of the amount threshold. An
    # approved bill redirected to a different payee bank account, or with
    # its payment due date shifted, is a segregation-of-duties break even
    # when the total is unchanged, so these bypass detect_material_change.
    # Redirecting a posting line to a DIFFERENT account at the same total
    # is the same class of break, but it surfaces only as a change to
    # line_ids/invoice_line_ids (not a field name here), so write()
    # detects it by comparing the line-account signature across the write
    # and passing account_redirected=True into _eh_reset_routing_change.
    _EH_ROUTING_TRIGGER_FIELDS = (
        'partner_id', 'invoice_date_due', 'partner_bank_id',
        'currency_id', 'company_id', 'move_type', 'date', 'invoice_date',
        'payment_reference',
    )

    # Field names on a write() vals that can carry a line-account
    # redirection (rewriting an existing line to a different account at
    # the same total).
    _EH_LINE_CONTAINER_FIELDS = ('line_ids', 'invoice_line_ids')

    def write(self, vals):
        """Re-approval guard on write.

        If any of the trigger fields change on a move that already
        carries an approved request, reset the request silently and
        post a chatter note. The next post attempt will block via
        the standard gate.
        """
        triggered = bool(
            vals and set(vals) & set(self._EH_REAPPROVAL_TRIGGER_FIELDS),
        )
        guarded = self.browse()
        if triggered:
            guarded = self._eh_active_approval_moves()
            if guarded:
                guarded._eh_lock_approval_scope()
        # Snapshot the line-account signature per move BEFORE the write
        # so an in-place account redirection (same total, different
        # destination account) can be detected afterwards. Only bother
        # when the write actually touches a line container and a move in
        # the set carries an approved request.
        pre_signatures = {}
        if vals and set(vals) & set(self._EH_LINE_CONTAINER_FIELDS):
            for move in guarded:
                if move.state != 'draft':
                    continue
                request = move._eh_server_approval_request()
                if request and request.state in ('in_review', 'approved'):
                    pre_signatures[move.id] = move._eh_line_account_signature()
        result = super(AccountMove, self.with_context(**{
            _EH_APPROVAL_PARENT_WRITE_CONTEXT:
                _EH_APPROVAL_PARENT_WRITE_CAPABILITY,
        })).write(vals)
        if not vals:
            return result
        if not triggered:
            return result
        for move in self:
            if move.state != 'draft':
                continue
            request = move._eh_server_approval_request()
            if not request:
                continue
            if request.state not in (
                'in_review', 'approved',
            ):
                continue
            # A line-account redirection at an unchanged total shows up
            # only as a changed line-account signature, not a routing
            # field name, so detect it here and feed it into the routing
            # reset as a first-class SoD break.
            account_redirected = (
                move.id in pre_signatures
                and move._eh_line_account_signature()
                != pre_signatures[move.id]
            )
            # Routing changes reset unconditionally; the amount check
            # then handles material value changes. Skip the amount check
            # when a routing reset already fired to avoid a double reset.
            if move._eh_reset_routing_change(
                set(vals), raise_on_reset=False,
                account_redirected=account_redirected,
            ):
                continue
            move._eh_check_re_approval_after_edit(raise_on_reset=False)
        return result


class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    _EH_APPROVAL_BASIS_FIELDS = frozenset({
        'move_id', 'account_id', 'partner_id', 'currency_id',
        'debit', 'credit', 'amount_currency', 'quantity', 'price_unit',
        'discount', 'tax_ids', 'tax_line_id',
    })

    @api.model
    def _eh_lock_basis_moves(self, moves):
        moves = moves.filtered(lambda move: move and move.state == 'draft')
        guarded = moves._eh_active_approval_moves()
        if guarded:
            guarded._eh_lock_approval_scope()
        return guarded

    @api.model
    def _eh_reset_approval_after_basis_change(self, moves, pre_signatures):
        if (
            self.env.context.get(_EH_APPROVAL_PARENT_WRITE_CONTEXT)
            is _EH_APPROVAL_PARENT_WRITE_CAPABILITY
        ):
            return
        moves = moves.filtered(
            lambda candidate: candidate.state == 'draft',
        )._eh_active_approval_moves()
        for move in moves:
            request = move._eh_server_approval_request()
            if not request or request.state not in ('in_review', 'approved'):
                continue
            redirected = (
                move.id in pre_signatures
                and move._eh_line_account_signature()
                != pre_signatures[move.id]
            )
            if redirected and move._eh_reset_routing_change(
                    {'line_ids'}, raise_on_reset=False,
                    account_redirected=True):
                continue
            move._eh_check_re_approval_after_edit(raise_on_reset=False)

    @api.model_create_multi
    def create(self, vals_list):
        move_ids = {
            int(vals['move_id']) for vals in vals_list if vals.get('move_id')
        }
        moves = self.env['account.move'].browse(sorted(move_ids))
        guarded = self._eh_lock_basis_moves(moves) if move_ids else moves
        pre_signatures = {
            move.id: move._eh_line_account_signature()
            for move in guarded
            if move._eh_server_approval_request()
        }
        lines = super().create(vals_list)
        changed_moves = moves | lines.mapped('move_id')
        self._eh_reset_approval_after_basis_change(
            changed_moves, pre_signatures,
        )
        return lines

    def write(self, vals):
        moves = self.mapped('move_id')
        pre_signatures = {}
        if set(vals).intersection(self._EH_APPROVAL_BASIS_FIELDS):
            if vals.get('move_id'):
                moves |= self.env['account.move'].browse(
                    int(vals['move_id']))
            guarded = self._eh_lock_basis_moves(moves)
            self.invalidate_recordset()
            pre_signatures = {
                move.id: move._eh_line_account_signature()
                for move in guarded
                if move._eh_server_approval_request()
            }
        result = super().write(vals)
        if pre_signatures:
            self._eh_reset_approval_after_basis_change(
                moves | self.mapped('move_id'), pre_signatures,
            )
        return result

    def unlink(self):
        moves = self.mapped('move_id')
        guarded = self._eh_lock_basis_moves(moves)
        pre_signatures = {
            move.id: move._eh_line_account_signature()
            for move in guarded
            if move._eh_server_approval_request()
        }
        self.invalidate_recordset()
        result = super().unlink()
        self._eh_reset_approval_after_basis_change(moves, pre_signatures)
        return result
