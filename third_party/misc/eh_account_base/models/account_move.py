# -*- encoding: utf-8 -*-
##############################################################################
#
# ERP Heritage
# Copyright (C) 2026 (https://www.erpheritage.com.au/)
#
##############################################################################
"""
account.move extension: bump the per company move version counter on state
changes. Drives reporting cache invalidation.

Hooks the write() method rather than _post() so every state transition
(post, draft, cancel) participates uniformly. Posting is implemented via
write({'state': 'posted'}) under the hood, so this single hook covers all
transitions without missing edge cases.

account.move.line extension: a posted move can still have its lines edited
in an unlocked period (the framework only blocks this when a period lock
covers the line date). Such an edit changes report figures without any
state transition, so the state-only hook above would let the reporting
cache serve a stale payload. The line write() hook below bumps the counter
whenever a financially-material field (amount, account, or date) changes on
a line whose parent move is posted, and only then, so unrelated writes
(analytic tags, narration, reconciliation bookkeeping) do not over-bump.

Adding a new line to, or removing an existing line from, an already-posted
move likewise changes report figures with no state transition. The line
create() and unlink() hooks below bump the counter whenever the affected
line belongs to a posted move, and only then, so building up a draft entry
before action_post does not over-bump.
"""

import json

from odoo import _, api, Command, fields, models
from odoo.exceptions import AccessError, UserError

# Fields whose value feeds report figures. A change to any of these on a
# posted move's line must invalidate the reporting cache.
_EH_MATERIAL_LINE_FIELDS = frozenset({
    'debit',
    'credit',
    'balance',
    'amount_currency',
    'account_id',
    'date',
    'date_maturity',
    'partner_id',
    'journal_id',
    'currency_id',
    'name',
    'ref',
    'analytic_distribution',
    'move_id',
    'quantity',
    'price_unit',
    'discount',
    'tax_ids',
    'tax_tag_ids',
    'product_id',
    'display_type',
    'tax_repartition_line_id',
    'tax_line_id',
    'group_tax_id',
    'tax_group_id',
    'extra_tax_data',
    'tax_base_amount',
    'amount_residual',
    'amount_residual_currency',
    'reconciled',
    'price_subtotal',
    'price_total',
    'product_uom_id',
    'is_storno',
    'deductible_amount',
    # Stored projections of the parent move are report/source anchors too.
    # They are server-owned below, but still belong in the invalidation set
    # for the private accounting-engine corridor.
    'company_id',
    'company_currency_id',
    'move_name',
    'parent_state',
    'invoice_date',
    'payment_id',
    'statement_line_id',
    'statement_id',
})

# Odoo's ``readonly`` flag is a client hint, not ORM authorization.  These
# stored related fields mirror authoritative account.move/origin rows and are
# used by financial domains.  A raw line write could otherwise persist a
# different projection (for example parent_state='posted' on a draft move).
# Core recomputation writes protected field caches directly; sanctioned
# accounting flows can carry the unforgeable engine capability.
_EH_SERVER_OWNED_LINE_PROJECTION_FIELDS = frozenset({
    'journal_id',
    'company_id',
    'company_currency_id',
    'move_name',
    'parent_state',
    'date',
    'invoice_date',
    'ref',
    'payment_id',
    'statement_line_id',
    'statement_id',
})

_EH_MATERIAL_MOVE_FIELDS = frozenset({
    'date', 'name', 'ref', 'partner_id', 'journal_id', 'company_id',
    'currency_id', 'move_type',
    # Authoritative parents of stored account.move.line origin projections.
    # ``origin_payment_id`` is 18+; older series use ``payment_id``.
    'origin_payment_id', 'payment_id', 'statement_line_id',
    'invoice_date', 'invoice_date_due',
    'line_ids', 'invoice_line_ids',
    'amount_untaxed', 'amount_tax', 'amount_total', 'amount_residual',
    'amount_untaxed_signed', 'amount_untaxed_in_currency_signed',
    'amount_tax_signed', 'amount_total_signed',
    'amount_total_in_currency_signed', 'amount_residual_signed',
    'payment_state',
})

# Once a move is sealed, every stored value is evidence by default. There is
# no raw-write exception: narrowly sanctioned accounting, delivery, portal,
# and follow-up workflows carry in-process object capabilities instead.
_EH_SEALED_MOVE_STORED_ALLOWLIST = frozenset()
_EH_SEALED_LINE_STORED_ALLOWLIST = frozenset()
# These legal-document façade fields are computed/non-stored on Odoo 19, but
# accepting them through ``write`` would still expose an inverse or silently
# imply that a caller can substitute the served invoice PDF. Refuse them
# explicitly rather than relying only on the stored-field fail-closed rule.
_EH_SEALED_MOVE_EXPLICIT_GUARD_FIELDS = frozenset({
    'invoice_pdf_report_id',
    'invoice_pdf_report_file',
})
# These values are credentials or delivery/legal-document evidence once an EH
# move is frozen. Ordinary unsealed invoices retain the standard Odoo lifecycle
# (sale auto-send and Peppol cancellation write these fields directly). The
# seal-stamping helper independently refuses any dirty pre-seeded evidence, so
# an ordinary draft can never carry caller-chosen values into a trusted seal.
_EH_SERVER_OWNED_MOVE_FIELDS = frozenset({
    'access_token',
    'is_move_sent',
    'sending_data',
    'send_and_print_values',
    'invoice_pdf_report_id',
    'invoice_pdf_report_file',
})
# Bearer credentials and the legal-PDF facade are never client-owned, even
# before an EH seal. Core reaches them through the portal/send capability
# wrappers below. By contrast, delivery queue/status fields are ordinary Odoo
# lifecycle inputs while unsealed and become immutable only once frozen.
_EH_ALWAYS_SERVER_OWNED_MOVE_FIELDS = frozenset({
    'access_token',
    'invoice_pdf_report_id',
    'invoice_pdf_report_file',
})
_EH_SERVER_OWNED_MOVE_PROJECTION_FIELDS = frozenset({
    'commercial_partner_id',
})

_EH_ALLOW_SEAL = 'eh_seal_internal'
_EH_SEAL_CAPABILITY = object()
_EH_POST_SEALED = 'eh_post_sealed_internal'
_EH_POST_SEALED_CAPABILITY = object()
_EH_REVERSE_SEALED = 'eh_reverse_sealed_internal'
_EH_REVERSE_SEALED_CAPABILITY = object()
_EH_REVERSE_LEGACY = 'eh_reverse_legacy_quarantine_internal'
_EH_REVERSE_LEGACY_CAPABILITY = object()
_EH_ACCOUNT_ENGINE = 'eh_account_engine_internal'
_EH_ACCOUNT_ENGINE_CAPABILITY = object()
_EH_SECURE_HASH = 'eh_secure_hash_internal'
_EH_SECURE_HASH_CAPABILITY = object()
_EH_COMMERCIAL_PROJECTION_REFRESH = 'eh_commercial_projection_refresh'
_EH_COMMERCIAL_PROJECTION_REFRESH_CAPABILITY = object()
_EH_SEALED_METADATA = 'eh_sealed_metadata_internal'
_EH_SEALED_METADATA_CAPABILITY = object()
_EH_CHATTER = 'eh_sealed_chatter_internal'
_EH_CHATTER_CAPABILITY = object()
_EH_READONLY_CHATTER = 'eh_sealed_readonly_chatter_internal'
_EH_READONLY_CHATTER_CAPABILITY = object()
_EH_REVERSE_MOVE_TYPES = {
    'entry': 'entry',
    'out_invoice': 'out_refund',
    'out_refund': 'out_invoice',
    'in_invoice': 'in_refund',
    'in_refund': 'in_invoice',
    'out_receipt': 'out_refund',
    'in_receipt': 'in_refund',
}


def _eh_optional_commercial_projection_dependencies(model):
    """Stored-compute inputs contributed by optional accounting modules.

    ``hr_expense`` changes shape across supported Odoo series: 19 links
    expenses directly through ``expense_ids`` while 16--18 link a sheet whose
    expense lines carry ``payment_mode``.  A callable dependency is resolved
    only after the registry is assembled, so Base can participate when the
    optional module is installed without declaring a hard dependency on it.
    """
    dependencies = []
    expense_field = model._fields.get('expense_ids')
    if expense_field:
        expense_model = model.env[expense_field.comodel_name]
        if 'payment_mode' in expense_model._fields:
            dependencies.append('expense_ids.payment_mode')

    sheet_field = model._fields.get('expense_sheet_id')
    if sheet_field:
        sheet_model = model.env[sheet_field.comodel_name]
        expense_lines_field = sheet_model._fields.get('expense_line_ids')
        if expense_lines_field:
            expense_model = model.env[expense_lines_field.comodel_name]
            if 'payment_mode' in expense_model._fields:
                dependencies.append(
                    'expense_sheet_id.expense_line_ids.payment_mode'
                )
    return tuple(dependencies)


class AccountMove(models.Model):
    _inherit = 'account.move'

    def _eh_selection_label(self, field_name):
        """Return active-language label for one selection field value."""
        self.ensure_one()
        field = self._fields.get(field_name)
        if not field or field.type != 'selection':
            return ''
        definition = self.fields_get([field_name]).get(field_name, {})
        return dict(definition.get('selection') or ()).get(
            self[field_name], '',
        )

    @api.depends(_eh_optional_commercial_projection_dependencies)
    def _compute_commercial_partner_id(self):
        """Track optional inputs read by installed commercial-root computes."""
        return super()._compute_commercial_partner_id()

    @api.model
    def default_get(self, fields_list):
        """Ignore caller/ir.default values for server-owned evidence."""
        defaults = super().default_get(fields_list)
        protected = (
            _EH_SERVER_OWNED_MOVE_FIELDS
            | _EH_SERVER_OWNED_MOVE_PROJECTION_FIELDS
            | {'eh_sealed', 'eh_legacy_unverified_seal',
               'reversed_entry_id'}
        ).intersection(fields_list)
        for field_name in protected:
            defaults[field_name] = False
        return defaults

    eh_sealed = fields.Boolean(
        default=False, copy=False, index=True,
        help="Set by an ERP Heritage sub-ledger when this journal entry is the "
             "posted GL counterpart of a frozen figure (a provision, revenue "
             "contract, asset, tax run, and so on). A sealed posted entry "
             "cannot be reset to draft or have its figures edited in place; it "
             "is unwound only by reversing the source record, which posts a "
             "reversing entry and preserves the audit trail.")
    eh_legacy_unverified_seal = fields.Boolean(
        string="Legacy Unverified Seal",
        default=False,
        readonly=True,
        copy=False,
        index=True,
        help=(
            "Set only by an upgrade when a legacy eh_sealed value predates "
            "durable server provenance. The journal entry remains frozen, "
            "but eh_sealed is cleared so no source workflow can accept the "
            "legacy value as verified accounting evidence."
        ),
    )

    def _eh_frozen_by_seal(self):
        """Moves frozen by verified or quarantined legacy seal evidence."""
        return self.filtered(
            lambda move: (
                move.eh_sealed or move.eh_legacy_unverified_seal
            )
        )

    def _eh_guard_sealed(self, action):
        if (
            self.env.context.get(_EH_ACCOUNT_ENGINE)
            is _EH_ACCOUNT_ENGINE_CAPABILITY
        ):
            return
        if (
            self.env.context.get(_EH_REVERSE_SEALED)
            is _EH_REVERSE_SEALED_CAPABILITY
            or self.env.context.get(_EH_REVERSE_LEGACY)
            is _EH_REVERSE_LEGACY_CAPABILITY
        ):
            return
        if (
            self.env.context.get(_EH_SEALED_METADATA)
            is _EH_SEALED_METADATA_CAPABILITY
        ):
            return
        legacy = self.filtered('eh_legacy_unverified_seal')
        if legacy:
            raise UserError(_(
                "Journal entry %(names)s carries an unverified legacy seal "
                "and is quarantined. It cannot be %(action)s or promoted to "
                "verified evidence; preserve it and correct it through a new, "
                "reviewed entry.",
                names=', '.join(move.name or '/' for move in legacy),
                action=action,
            ))
        if (
            self.env.context.get(_EH_POST_SEALED)
            is _EH_POST_SEALED_CAPABILITY
        ):
            return
        sealed = self.filtered('eh_sealed')
        if sealed:
            raise UserError(_(
                "Journal entry %(names)s is the counterpart of an ERP "
                "Heritage sub-ledger figure and cannot be %(action)s directly. "
                "Reverse the source record instead: it posts a reversing entry "
                "and re-opens the figure, preserving the audit trail.",
                names=', '.join(move.name or '/' for move in sealed),
                action=action))

    def button_draft(self):
        self._eh_guard_sealed(_("reset to draft"))
        guarded = self.with_context(**{
            _EH_SEALED_METADATA: _EH_SEALED_METADATA_CAPABILITY,
        })
        return super(AccountMove, guarded).button_draft()

    def button_cancel(self):
        self._eh_guard_sealed(_("cancelled"))
        return super().button_cancel()

    def action_eh_reverse_legacy_quarantine(self):
        """Open the manager-only reviewed correction flow for one legacy row."""
        self.ensure_one()
        if not self.env.user.has_group(
                'eh_account_base.group_eh_manager'):
            raise AccessError(_(
                "Only an ERP Heritage Accounting Manager can reverse a "
                "legacy-quarantined journal entry."
            ))
        self._eh_check_access('read')
        if (
            self.state != 'posted'
            or self.eh_sealed
            or not self.eh_legacy_unverified_seal
        ):
            raise UserError(_(
                "This action is available only for a posted legacy-"
                "quarantined journal entry."
            ))
        if self.env['account.move'].sudo().search_count([
            ('reversed_entry_id', '=', self.id),
        ], limit=1):
            raise UserError(_(
                "This quarantined entry already has a counter-entry."
            ))
        return {
            'type': 'ir.actions.act_window',
            'name': _("Reverse Legacy-Quarantined Entry"),
            'res_model': 'eh.account.legacy.seal.reversal',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_move_id': self.id,
                'default_date': fields.Date.context_today(self),
            },
        }

    def action_post(self):
        """Permit only the real posting method to finalise verified drafts.

        A verified seal freezes a generated draft immediately. Core posting
        must still calculate and write its journal lines; an object capability
        that cannot arrive through RPC distinguishes those nested writes from
        raw state/line edits. Legacy-unverified drafts remain quarantined and
        cannot be posted.
        """
        legacy = self.filtered('eh_legacy_unverified_seal')
        if legacy:
            legacy._eh_guard_sealed(_("posted"))
        if self.filtered('eh_sealed'):
            guarded = self.with_context(**{
                _EH_POST_SEALED: _EH_POST_SEALED_CAPABILITY,
            })
            return super(AccountMove, guarded).action_post()
        return super().action_post()

    def _portal_ensure_token(self):
        """Mint portal bearer tokens only through an unforgeable corridor."""
        if self.filtered('eh_legacy_unverified_seal'):
            raise UserError(_(
                "An unverified legacy journal entry cannot mint a portal "
                "access token. Create a new reviewed source document."
            ))
        guarded = self.with_context(**{
            _EH_SEALED_METADATA: _EH_SEALED_METADATA_CAPABILITY,
        })
        return super(AccountMove, guarded)._portal_ensure_token()

    def _message_set_main_attachment_id(
        self, attachments=None, *args, attachment_ids=None, **kwargs
    ):
        """Require a pre-existing capability for a sealed main attachment.

        Public ``ir.attachment.register_as_main_attachment`` reaches this
        private hook for both ``force=True`` and ``force=False``. It must not
        be able to replace or pre-seed a sealed invoice's legal attachment.
        Chatter and invoice-send entry points add the object capability before
        reaching this method. ``*args``/``**kwargs`` deliberately preserve the
        core signature: Odoo 16--17 pass only attachment ids, while 18--19 add
        ``force`` and ``filter_xml``.
        """
        if attachments is None:
            attachments = attachment_ids
        force = kwargs.get('force', args[0] if args else False)
        has_main_attachment_capability = (
            self.env.context.get(_EH_SEALED_METADATA)
            is _EH_SEALED_METADATA_CAPABILITY
            or self.env.context.get(_EH_CHATTER)
            is _EH_CHATTER_CAPABILITY
        )
        if self._eh_frozen_by_seal() and not has_main_attachment_capability:
            if (
                self.env.context.get(_EH_READONLY_CHATTER)
                is _EH_READONLY_CHATTER_CAPABILITY
            ):
                return
            # The mail upload controller creates the attachment under sudo,
            # then invokes this hook with force=False after its own target and
            # ownership checks. Preserve that standard auto-main behaviour,
            # but never let sudo alone replace an existing main attachment.
            if not force and self.env.su:
                try:
                    self.sudo(False)._eh_check_access('write')
                except AccessError:
                    # Read-only mail actors may attach evidence but cannot
                    # choose or freeze the document's main attachment.
                    return
                guarded = self.with_context(**{
                    _EH_SEALED_METADATA: _EH_SEALED_METADATA_CAPABILITY,
                })
                return super(
                    AccountMove, guarded,
                )._message_set_main_attachment_id(
                    attachments, *args, **kwargs,
                )
            # register_as_main_attachment suppresses AccessError by design;
            # a business error keeps this security refusal visible to callers.
            raise UserError(_(
                "The main attachment of a sealed journal entry is "
                "server-owned and cannot be replaced directly."
            ))
        return super()._message_set_main_attachment_id(
            attachments, *args, **kwargs,
        )

    def message_post(self, **kwargs):
        """Carry main-attachment authority only through checked chatter."""
        self.ensure_one()
        attachment_ids = kwargs.get('attachment_ids') or []
        if self._eh_frozen_by_seal() and attachment_ids and all(
            isinstance(attachment_id, int)
            for attachment_id in attachment_ids
        ):
            attachments = self.env['ir.attachment'].browse(
                attachment_ids,
            ).exists()
            attachments.sudo(False)._eh_check_access('read')
            smuggled_legal_pdf = attachments.filtered(
                lambda attachment: (
                    attachment.res_field == 'invoice_pdf_report_file'
                    and (
                        attachment.res_model != self._name
                        or attachment.res_id != self.id
                    )
                )
            )
            if smuggled_legal_pdf:
                raise AccessError(_(
                    "A pending attachment cannot be promoted to a sealed "
                    "invoice's legal PDF through chatter."
                ))
        chatter_context = {}
        if self._eh_frozen_by_seal():
            try:
                self.sudo(False)._eh_check_access('write')
            except AccessError:
                chatter_context[_EH_READONLY_CHATTER] = (
                    _EH_READONLY_CHATTER_CAPABILITY
                )
            else:
                chatter_context[_EH_CHATTER] = _EH_CHATTER_CAPABILITY
        guarded = self.with_context(**chatter_context)
        message = super(AccountMove, guarded).message_post(**kwargs)
        clean_context = dict(message.env.context)
        clean_context.pop(_EH_CHATTER, None)
        clean_context.pop(_EH_READONLY_CHATTER, None)
        clean_context.pop(_EH_SEALED_METADATA, None)
        return message.with_context(clean_context)

    def _inverse_no_followup(self):
        """Let the invoice-level follow-up control update its stored lines.

        ``account.move.no_followup`` is the public, ACL-checked control that
        core exposes on an invoice. Its inverse writes the stored journal-line
        value. Carry the accounting-engine capability only through that exact
        inverse so a direct line ``write({'no_followup': ...})`` remains
        forbidden on sealed evidence.
        """
        guarded = self.with_context(**{
            _EH_ACCOUNT_ENGINE: _EH_ACCOUNT_ENGINE_CAPABILITY,
        })
        return super(AccountMove, guarded)._inverse_no_followup()

    @api.model
    def _eh_sanitise_commercial_projection_on_create(self, vals):
        """Accept only value computed by installed account extensions.

        ``commercial_partner_id`` is a stored compute, but core creators may
        redundantly supply its exact value.  ``hr_expense`` also overrides
        the compute for employee-paid expenses.  Recompute on an in-memory
        move carrying only the declared inputs, compare, then remove the
        redundant value so normal ORM computation remains authoritative.
        """
        if 'commercial_partner_id' not in vals:
            return dict(vals)
        clean_vals = dict(vals)
        supplied_id = clean_vals.pop('commercial_partner_id') or False
        if not supplied_id:
            return clean_vals
        if (
            self.env.context.get(_EH_ACCOUNT_ENGINE)
            is _EH_ACCOUNT_ENGINE_CAPABILITY
        ):
            return dict(vals)
        compute_field_names = [
            field_name
            for field_name in (
                'partner_id', 'company_id', 'journal_id', 'move_type',
                'expense_ids', 'expense_sheet_id',
            )
            if field_name in self._fields
        ]
        compute_inputs = self.default_get(compute_field_names)
        compute_inputs.update({
            field_name: clean_vals[field_name]
            for field_name in compute_field_names
            if field_name in clean_vals
        })
        probe = self.new(compute_inputs)
        expected_id = probe.commercial_partner_id.id or False
        if int(supplied_id) != expected_id:
            raise AccessError(_(
                "Journal-entry commercial projections are server-owned; "
                "the supplied commercial entity does not match the value "
                "computed from the move's authoritative inputs."
            ))
        return clean_vals

    @api.model_create_multi
    def create(self, vals_list):
        """Bump version when a move is created already in posted state.

        Common case is unaffected (moves are created in draft and posted via
        action_post, which goes through write()). This override exists for the
        rare paths that create directly with state='posted', so the cache stays
        consistent.
        """
        default_values = {
            field_name: self.env.context.get('default_%s' % field_name)
            for field_name in (
                _EH_SERVER_OWNED_MOVE_FIELDS
                | _EH_SERVER_OWNED_MOVE_PROJECTION_FIELDS
                | {'eh_sealed', 'eh_legacy_unverified_seal',
                   'reversed_entry_id'}
            )
            if 'default_%s' % field_name in self.env.context
        }
        vals_list = [
            self._eh_sanitise_commercial_projection_on_create(vals)
            for vals in vals_list
        ]
        guarded_vals_list = list(vals_list)
        if default_values:
            guarded_vals_list.append(default_values)
        for vals in guarded_vals_list:
            # Delegated-inheritance creators (notably bank statement lines)
            # forward every inherited field, including harmless
            # ``eh_sealed=False``. Only a truthy seal is privileged.
            if vals.get('eh_legacy_unverified_seal'):
                raise AccessError(_(
                    "The legacy-unverified seal is upgrade-owned and cannot "
                    "be supplied directly."
                ))
            if vals.get('eh_sealed') and not (
                self.env.su
                and self.env.context.get(_EH_ALLOW_SEAL)
                is _EH_SEAL_CAPABILITY
            ):
                raise AccessError(_(
                    "The sub-ledger journal-entry seal is server-owned and "
                    "cannot be supplied directly."
                ))
            server_owned = {
                field_name
                for field_name in _EH_SERVER_OWNED_MOVE_FIELDS
                if vals.get(field_name)
            }
            always_server_owned = (
                server_owned & _EH_ALWAYS_SERVER_OWNED_MOVE_FIELDS
            )
            if (
                (
                    always_server_owned
                    or server_owned and (
                        vals.get('eh_sealed')
                        or vals.get('eh_legacy_unverified_seal')
                    )
                )
                and not (
                    self.env.context.get(_EH_SEALED_METADATA)
                    is _EH_SEALED_METADATA_CAPABILITY
                )
            ):
                raise AccessError(_(
                    "Portal, sending, and legal-PDF evidence is "
                    "server-owned and cannot be supplied directly: %s",
                    ', '.join(sorted(server_owned)),
                ))
            projection_owned = (
                _EH_SERVER_OWNED_MOVE_PROJECTION_FIELDS.intersection(vals)
            )
            if projection_owned and not (
                self.env.context.get(_EH_ACCOUNT_ENGINE)
                is _EH_ACCOUNT_ENGINE_CAPABILITY
            ):
                raise AccessError(_(
                    "Journal-entry commercial projections are server-owned "
                    "and cannot be supplied directly: %s",
                    ', '.join(sorted(projection_owned)),
                ))
            self._eh_guard_reversed_entry_values(vals)
        protected_defaults = {
            'default_%s' % field_name
            for field_name in (
                _EH_SERVER_OWNED_MOVE_FIELDS
                | _EH_SERVER_OWNED_MOVE_PROJECTION_FIELDS
                | {'eh_sealed', 'eh_legacy_unverified_seal',
                   'reversed_entry_id'}
            )
        }
        create_context = {
            key: value for key, value in self.env.context.items()
            if key not in protected_defaults
        }
        create_self = self.with_context(create_context)
        moves = super(AccountMove, create_self).create(vals_list)
        posted = moves.filtered(lambda m: m.state == 'posted')
        if posted:
            company_ids = set(posted.mapped('company_id.id'))
            if company_ids:
                self.env['res.company'].sudo()._eh_bump_move_version(company_ids)
        return moves

    @api.model
    @api.private
    def _eh_create_sealed(self, vals):
        """Create through normal actor ACLs, then stamp server-owned seal."""
        # The stamp is part of creation's security boundary.  If validation
        # or stamping fails and an internal caller catches the exception, no
        # unsealed draft may survive for that caller to commit accidentally.
        with self.env.cr.savepoint():
            vals = dict(vals or {})
            if vals.pop('eh_sealed', True) is not True:
                raise UserError(_(
                    "A sealed move helper requires eh_sealed=True."
                ))
            create_model = self.sudo(False)
            if vals.get('reversed_entry_id'):
                original = create_model.browse(
                    vals['reversed_entry_id']
                ).exists()
                if not original:
                    raise UserError(_(
                        "A sealed reversal must point to an existing original "
                        "journal entry."
                    ))
                original._eh_check_access('read')
                original.flush_recordset()
                self.env.cr.execute(
                    "SELECT id FROM account_move WHERE id = %s FOR UPDATE",
                    (original.id,),
                )
                original.invalidate_recordset([
                    'state', 'eh_sealed', 'eh_legacy_unverified_seal',
                ])
                if (
                    original.state != 'posted'
                    or not original.eh_sealed
                    or original.eh_legacy_unverified_seal
                ):
                    raise UserError(_(
                        "A sealed reversal can only unwind a currently "
                        "verified sealed journal entry."
                    ))
                if self.env['account.move'].sudo().search_count([
                    ('reversed_entry_id', '=', original.id),
                ], limit=1):
                    raise UserError(_(
                        "The protected original already has a reversal; a "
                        "second counter-entry would make its audit trail "
                        "ambiguous."
                    ))
                create_model = create_model.with_context(**{
                    _EH_REVERSE_SEALED: _EH_REVERSE_SEALED_CAPABILITY,
                })
            # Source workflows often elevate their own recordset so they can
            # stamp server-owned state/evidence fields.  That elevation must
            # not leak into account.move creation: otherwise a raw
            # foreign-company journal/account id turns the source action into
            # a confused deputy. sudo(False) restores the actor boundary.
            move = create_model.create(vals)
            move._eh_stamp_verified_seal()
            if vals.get('reversed_entry_id'):
                clean_context = dict(move.env.context)
                clean_context.pop(_EH_REVERSE_SEALED, None)
                move = move.with_context(clean_context)
            return move

    def _eh_guard_reversed_entry_values(self, vals):
        """Reject raw mutation of reversal provenance for protected moves.

        Ordinary Odoo credit notes remain unaffected.  The guard becomes
        active whenever either side of the link is verified sealed or carries
        a quarantined legacy seal.  The only bypass is an in-process object
        capability, which cannot be forged through an RPC context.
        """
        if 'reversed_entry_id' not in vals:
            return
        if (
            self.env.context.get(_EH_REVERSE_SEALED)
            is _EH_REVERSE_SEALED_CAPABILITY
            or self.env.context.get(_EH_REVERSE_LEGACY)
            is _EH_REVERSE_LEGACY_CAPABILITY
        ):
            return
        original = self.browse(vals.get('reversed_entry_id')).exists()
        if original and not self.env.su:
            original._eh_check_access('read')
        current_originals = self.mapped('reversed_entry_id') if self else self
        lock_ids = sorted(set(
            self.ids + original.ids + current_originals.ids
        ))
        if lock_ids:
            (self | original | current_originals).flush_recordset()
            self.env.cr.execute(
                "SELECT id FROM account_move WHERE id IN %s "
                "ORDER BY id FOR UPDATE",
                (tuple(lock_ids),),
            )
            (self | original | current_originals).invalidate_recordset([
                'eh_sealed', 'eh_legacy_unverified_seal',
                'reversed_entry_id',
            ])
            original = self.browse(vals.get('reversed_entry_id')).exists()
            current_originals = (
                self.mapped('reversed_entry_id') if self else self
            )
        protected = (
            self._eh_frozen_by_seal()
            | original._eh_frozen_by_seal()
            | current_originals._eh_frozen_by_seal()
        )
        if protected:
            raise AccessError(_(
                "Reversal provenance for sealed or legacy-quarantined "
                "journal entries is server-owned and cannot be edited "
                "directly."
            ))

    @api.private
    def _eh_validate_verified_reversal(
        self, original, allow_legacy_original=False,
    ):
        """Prove that ``self`` is a balanced opposite of ``original``.

        Lines may be regrouped, but only inside the same reporting dimension.
        Partner, analytic, tax, product, and display classifications are part
        of the evidence: netting only by account/currency would let a forged
        reversal cancel the trial balance while moving figures between the
        partner, analytic, or tax ledgers.
        """
        self.ensure_one()
        original.ensure_one()
        verified_original = bool(
            original.eh_sealed
            and not original.eh_legacy_unverified_seal
        )
        reviewed_legacy_original = bool(
            allow_legacy_original
            and original.eh_legacy_unverified_seal
            and not original.eh_sealed
        )
        if (
            original.state != 'posted'
            or not (verified_original or reviewed_legacy_original)
            or self.reversed_entry_id != original
            or self.company_id != original.company_id
            or self.journal_id != original.journal_id
            or self.currency_id != original.currency_id
            or self.partner_id != original.partner_id
            or self.move_type != _EH_REVERSE_MOVE_TYPES.get(
                original.move_type,
            )
            or not original.line_ids
            or not self.line_ids
        ):
            raise UserError(_(
                "The reversal failed verified source, company, journal, or "
                "currency provenance validation."
            ))

        def _totals(move, normalise_reversal=False):
            totals = {}
            for line in move.line_ids:
                repartition = line.tax_repartition_line_id
                key = (
                    line.account_id.id,
                    line.currency_id.id,
                    line.partner_id.id,
                    json.dumps(
                        line.analytic_distribution or {},
                        sort_keys=True,
                        separators=(',', ':'),
                    ),
                    tuple(sorted(line.tax_ids.ids)),
                    tuple(sorted(line.tax_tag_ids.ids)),
                    line.tax_line_id.id,
                    repartition.repartition_type or '',
                    repartition.factor_percent if repartition else 0.0,
                    line.group_tax_id.id,
                    line.tax_group_id.id,
                    json.dumps(
                        getattr(line, 'extra_tax_data', None) or {},
                        sort_keys=True,
                        separators=(',', ':'),
                    ),
                    line.product_id.id,
                    line.product_uom_id.id,
                    line.display_type or '',
                    line.quantity,
                    line.price_unit,
                    line.discount,
                    getattr(line, 'deductible_amount', 100.0),
                    (
                        not line.is_storno
                        if normalise_reversal
                        and line.company_id.account_storno
                        else line.is_storno
                    ),
                )
                balance, amount_currency, tax_base = totals.get(
                    key, (0.0, 0.0, 0.0),
                )
                line_tax_base = line.tax_base_amount
                if (
                    normalise_reversal
                    and 'tax_tag_invert' in line._fields
                ):
                    line_tax_base = -line_tax_base
                totals[key] = (
                    balance + line.balance,
                    amount_currency + line.amount_currency,
                    tax_base + line_tax_base,
                )
            return totals

        source_totals = _totals(original)
        reversal_totals = _totals(self, normalise_reversal=True)
        for dimension in set(source_totals) | set(reversal_totals):
            source_balance, source_amount, source_tax_base = source_totals.get(
                dimension, (0.0, 0.0, 0.0),
            )
            reversal_balance, reversal_amount, reversal_tax_base = (
                reversal_totals.get(dimension, (0.0, 0.0, 0.0))
            )
            currency = (
                self.env['res.currency'].browse(dimension[1])
                or original.company_currency_id
            )
            if (
                not original.company_currency_id.is_zero(
                    source_balance + reversal_balance
                )
                or not currency.is_zero(source_amount + reversal_amount)
                or not original.company_currency_id.is_zero(
                    source_tax_base + reversal_tax_base
                )
            ):
                raise UserError(_(
                    "The reversal does not exactly offset the original "
                    "journal entry by account, currency, and reporting "
                    "dimension."
                ))
        return self

    @api.private
    def _eh_align_verified_cash_rounding_accounts(self, original):
        """Keep an exact reversal on the original cash-rounding account.

        Core deliberately chooses the configured profit or loss account from
        the *new document's* rounding sign.  A refund therefore picks the
        opposite configuration leg even though its rounding amount is the
        exact inverse of the source.  That is sensible for a standalone
        credit note, but a verified evidence reversal must offset the source
        by account as well as by amount.  Narrowly realign only uniquely
        matched generated rounding legs; the full dimension validator still
        runs immediately afterwards and fails closed on every other drift.
        """
        self.ensure_one()
        original.ensure_one()
        source_lines = original.line_ids.filtered(
            lambda line: line.display_type == 'rounding'
        )
        reversal_lines = self.line_ids.filtered(
            lambda line: line.display_type == 'rounding'
        )
        if not source_lines or len(source_lines) != len(reversal_lines):
            return self

        unmatched = reversal_lines
        for source_line in source_lines:
            line_currency = (
                source_line.currency_id or original.company_currency_id
            )
            candidates = unmatched.filtered(lambda line: (
                line.currency_id == source_line.currency_id
                and line.partner_id == source_line.partner_id
                and line.tax_repartition_line_id
                == source_line.tax_repartition_line_id
                and set(line.tax_ids.ids) == set(source_line.tax_ids.ids)
                and set(line.tax_tag_ids.ids) == set(source_line.tax_tag_ids.ids)
                and original.company_currency_id.is_zero(
                    line.balance + source_line.balance
                )
                and line_currency.is_zero(
                    line.amount_currency + source_line.amount_currency
                )
            ))
            if len(candidates) != 1:
                continue
            reversal_line = candidates
            unmatched -= reversal_line
            if reversal_line.account_id != source_line.account_id:
                reversal_line.account_id = source_line.account_id
        return self

    @api.private
    def _eh_align_verified_storno_dimensions(self, original):
        """Normalise protected reversals on pre-19 storno engines.

        Odoo 19 flips ``is_storno`` while copying a reversal; earlier
        supported series copy the flag unchanged.  Do the missing flip only
        when the source/reversal line sets pair exactly by every other
        audited dimension and by inverse booked amounts.  Ambiguous pairs are
        left untouched so the validator below rejects them.
        """
        self.ensure_one()
        original.ensure_one()
        if (
            'account_storno' not in original.company_id._fields
            or not original.company_id.account_storno
            or 'is_storno' not in self.env['account.move.line']._fields
        ):
            return self

        def _dimension_key(line):
            repartition = line.tax_repartition_line_id
            return (
                line.account_id.id,
                line.currency_id.id,
                line.partner_id.id,
                json.dumps(
                    line.analytic_distribution or {},
                    sort_keys=True,
                    separators=(',', ':'),
                ),
                tuple(sorted(line.tax_ids.ids)),
                tuple(sorted(line.tax_tag_ids.ids)),
                line.tax_line_id.id,
                repartition.repartition_type or '',
                repartition.factor_percent if repartition else 0.0,
                line.group_tax_id.id,
                line.tax_group_id.id,
                json.dumps(
                    getattr(line, 'extra_tax_data', None) or {},
                    sort_keys=True,
                    separators=(',', ':'),
                ),
                line.product_id.id,
                line.product_uom_id.id,
                line.display_type or '',
                line.quantity,
                line.price_unit,
                line.discount,
                getattr(line, 'deductible_amount', 100.0),
            )

        unmatched = self.line_ids
        for source_line in original.line_ids.sorted('id'):
            line_currency = (
                source_line.currency_id or original.company_currency_id
            )
            candidates = unmatched.filtered(lambda line: (
                _dimension_key(line) == _dimension_key(source_line)
                and original.company_currency_id.is_zero(
                    line.balance + source_line.balance
                )
                and line_currency.is_zero(
                    line.amount_currency + source_line.amount_currency
                )
            ))
            if len(candidates) != 1:
                continue
            reversal_line = candidates
            unmatched -= reversal_line
            expected_storno = not source_line.is_storno
            if reversal_line.is_storno != expected_storno:
                reversal_line.is_storno = expected_storno
        return self

    @api.private
    def _eh_has_verified_reversal_capability(self):
        """Whether this call carries Base's unforgeable reversal authority.

        Optional sub-ledgers can use this predicate to harmonise their own
        direct-reversal guards with the verified sealed-reversal corridor.
        The capability object stays private to Base; an RPC context value can
        never make this return true.
        """
        return (
            self.env.context.get(_EH_REVERSE_SEALED)
            is _EH_REVERSE_SEALED_CAPABILITY
            or self.env.context.get(_EH_REVERSE_LEGACY)
            is _EH_REVERSE_LEGACY_CAPABILITY
        )

    @api.private
    def _eh_has_sealed_mutation_capability(self):
        """Whether Base sanctioned nested accounting-engine mutation."""
        return any((
            self.env.context.get(_EH_ACCOUNT_ENGINE)
            is _EH_ACCOUNT_ENGINE_CAPABILITY,
            self.env.context.get(_EH_POST_SEALED)
            is _EH_POST_SEALED_CAPABILITY,
            self.env.context.get(_EH_REVERSE_SEALED)
            is _EH_REVERSE_SEALED_CAPABILITY,
            self.env.context.get(_EH_REVERSE_LEGACY)
            is _EH_REVERSE_LEGACY_CAPABILITY,
            self.env.context.get(_EH_SECURE_HASH)
            is _EH_SECURE_HASH_CAPABILITY,
        ))

    @api.private
    def _eh_has_account_engine_capability(self):
        """Whether Base owns this exact nested accounting-engine write."""
        return (
            self.env.context.get(_EH_ACCOUNT_ENGINE)
            is _EH_ACCOUNT_ENGINE_CAPABILITY
        )

    @api.private
    def _eh_reversal_moves(self):
        """Return core reversal children across Odoo 16-19 schemas."""
        field_name = (
            'reversal_move_ids'
            if 'reversal_move_ids' in self._fields
            else 'reversal_move_id'
        )
        return self.mapped(field_name)

    @api.private
    def _eh_has_secure_hash_capability(self):
        """Whether core Secure Entries owns this exact hash write."""
        return (
            self.env.context.get(_EH_SECURE_HASH)
            is _EH_SECURE_HASH_CAPABILITY
        )

    def _hash_moves(self, **kwargs):
        """Let core append its immutable hash to verified sealed entries.

        Hashing is itself an evidence-strengthening mutation.  Carry a
        process-local capability through core's chain search/write so suite
        seals do not mistake it for an RPC attempt to forge the hash.
        """
        guarded = self.with_context(**{
            _EH_SECURE_HASH: _EH_SECURE_HASH_CAPABILITY,
        })
        parent = super(AccountMove, guarded)
        parent_hash = getattr(parent, '_hash_moves', None)
        if parent_hash:
            return parent_hash(**kwargs)

        # Odoo 16/17 hash only during the state='posted' write and expose no
        # historical hash action. Reproduce that core algorithm for an
        # already-posted, explicitly selected set: journal secure sequence,
        # deterministic order, then core's own _get_new_hash().
        historical = guarded.filtered(
            lambda move: move.state == 'posted'
            and not (move.secure_sequence_number or move.inalterable_hash)
        ).sorted(lambda move: (
            move.journal_id.id, move.date, move.ref or '', move.id,
        ))
        historical.flush_recordset()
        for move in historical:
            if not move.journal_id.secure_sequence_id:
                move.journal_id.sudo()._create_secure_sequence([
                    'secure_sequence_id',
                ])
            new_number = move.journal_id.secure_sequence_id.next_by_id()
            super(AccountMove, move).write({
                'secure_sequence_number': new_number,
                'inalterable_hash': move._get_new_hash(new_number),
            })
        return None

    @api.private
    def _eh_reverse_with_verified_capability(
        self, default_values_list=None, cancel=False,
    ):
        """Reverse verified sealed moves through an unforgeable capability."""
        if not self:
            return self.browse()
        # Core creates the counter-entry before our shape validation and seal.
        # Keep that sequence helper-atomic even when an internal caller catches
        # a late validation/stamp exception.
        with self.env.cr.savepoint():
            actor_moves = self.sudo(False)
            actor_moves._eh_check_access('read')
            actor_moves.flush_recordset()
            self.env.cr.execute(
                "SELECT id FROM account_move WHERE id IN %s "
                "ORDER BY id FOR UPDATE",
                (tuple(sorted(actor_moves.ids)),),
            )
            actor_moves.invalidate_recordset([
                'state', 'eh_sealed', 'eh_legacy_unverified_seal',
            ])
            invalid = actor_moves.filtered(
                lambda move: (
                    move.state != 'posted'
                    or not move.eh_sealed
                    or move.eh_legacy_unverified_seal
                )
            )
            if invalid:
                raise UserError(_(
                    "Only currently verified sealed entries can use the "
                    "sanctioned sealed-reversal workflow."
                ))
            existing = self.env['account.move'].sudo().search([
                ('reversed_entry_id', 'in', actor_moves.ids),
            ], limit=1)
            if existing:
                raise UserError(_(
                    "A protected journal entry already has a reversal. Review "
                    "that immutable reversal trail instead of creating a "
                    "second counter-entry."
                ))
            if (
                default_values_list is not None
                and len(default_values_list) != len(actor_moves)
            ):
                raise UserError(_(
                    "A sealed reversal requires exactly one set of reversal "
                    "values for each original entry."
                ))
            guarded = actor_moves.with_context(**{
                _EH_REVERSE_SEALED: _EH_REVERSE_SEALED_CAPABILITY,
            })
            return guarded._reverse_moves(
                default_values_list=default_values_list,
                cancel=cancel,
            )

    @api.private
    def _eh_reverse_reviewed_legacy_quarantine(
        self, default_values_list,
    ):
        """Post an exact manager-reviewed counter-entry for legacy evidence.

        The uncertain original stays immutable and quarantined forever. The
        newly generated opposite is current server evidence, is posted in the
        same savepoint, and is sealed only after dimensional equality is
        proved. This is a correction flow, never an unquarantine or rewrite.
        """
        if not self:
            return self.browse()
        if not self.env.user.has_group(
                'eh_account_base.group_eh_manager'):
            raise AccessError(_(
                "Only an ERP Heritage Accounting Manager can reverse a "
                "legacy-quarantined journal entry."
            ))
        if (
            not default_values_list
            or len(default_values_list) != len(self)
            or any(not values.get('ref') for values in default_values_list)
        ):
            raise UserError(_(
                "A reviewed legacy reversal requires one documented reason "
                "for each quarantined journal entry."
            ))
        today = fields.Date.context_today(self)
        if any(
            fields.Date.to_date(values.get('date')) > today
            for values in default_values_list
            if values.get('date')
        ):
            raise UserError(_(
                "A reviewed legacy reversal cannot be future-dated because "
                "the counter-entry must post atomically with the review."
            ))

        with self.env.cr.savepoint():
            actor_moves = self.sudo(False)
            actor_moves._eh_check_access('read')
            actor_moves.flush_recordset()
            self.env.cr.execute(
                "SELECT id FROM account_move WHERE id IN %s "
                "ORDER BY id FOR UPDATE",
                (tuple(sorted(actor_moves.ids)),),
            )
            actor_moves.invalidate_recordset([
                'state', 'eh_sealed', 'eh_legacy_unverified_seal',
            ])
            invalid = actor_moves.filtered(lambda move: (
                move.state != 'posted'
                or move.eh_sealed
                or not move.eh_legacy_unverified_seal
            ))
            if invalid:
                raise UserError(_(
                    "Only posted legacy-quarantined journal entries can use "
                    "the reviewed correction workflow."
                ))
            existing = self.env['account.move'].sudo().search([
                ('reversed_entry_id', 'in', actor_moves.ids),
            ], limit=1)
            if existing:
                raise UserError(_(
                    "The quarantined journal entry already has a counter-entry; "
                    "review that immutable trail instead of duplicating it."
                ))
            guarded = actor_moves.with_context(**{
                _EH_REVERSE_LEGACY: _EH_REVERSE_LEGACY_CAPABILITY,
            })
            reversals = guarded._reverse_moves(
                default_values_list=default_values_list,
                cancel=False,
            )
            reviewed_reversals = reversals.with_context(**{
                _EH_REVERSE_LEGACY: _EH_REVERSE_LEGACY_CAPABILITY,
            })
            reviewed_reversals._eh_post_verified_reversal()
            clean_context = dict(reviewed_reversals.env.context)
            clean_context.pop(_EH_REVERSE_LEGACY, None)
            return reviewed_reversals.with_context(clean_context)

    @api.private
    def _eh_post_verified_reversal(self):
        """Post sealed draft reversals without core late auto-reconcile.

        Suite workflows use ``cancel=False`` because many sub-ledger entries
        contain intentionally non-reconcilable P&L legs. Core nevertheless
        tries to reconcile a draft carrying ``reversed_entry_id`` when it is
        posted later. Clear and restore the immutable link atomically so the
        requested counter-entry semantics and durable provenance both hold.
        """
        with self.env.cr.savepoint():
            allow_legacy_original = (
                self.env.context.get(_EH_REVERSE_LEGACY)
                is _EH_REVERSE_LEGACY_CAPABILITY
            )
            for reversal in self:
                original = reversal.reversed_entry_id
                lock_ids = sorted(set(reversal.ids + original.ids))
                if lock_ids:
                    (reversal | original).flush_recordset()
                    self.env.cr.execute(
                        "SELECT id FROM account_move WHERE id IN %s "
                        "ORDER BY id FOR UPDATE",
                        (tuple(lock_ids),),
                    )
                    (reversal | original).invalidate_recordset([
                        'state', 'eh_sealed',
                        'eh_legacy_unverified_seal', 'reversed_entry_id',
                    ])
                    original = reversal.reversed_entry_id
                if (
                    reversal.state != 'draft'
                    or not reversal.eh_sealed
                    or reversal.eh_legacy_unverified_seal
                    or not original
                ):
                    raise UserError(_(
                        "Only a verified sealed draft reversal can use the "
                        "controlled reversal-posting workflow."
                    ))
                sibling = self.env['account.move'].sudo().search([
                    ('reversed_entry_id', '=', original.id),
                    ('id', '!=', reversal.id),
                ], limit=1)
                if sibling:
                    raise UserError(_(
                        "The protected original has more than one reversal; "
                        "quarantine and review the ambiguous reversal graph."
                    ))
                reversal._eh_validate_verified_reversal(
                    original,
                    allow_legacy_original=allow_legacy_original,
                )
                reversal._eh_set_reversed_entry(False)
                reversal.action_post()
                reversal._eh_set_reversed_entry(original)
                reversal._eh_validate_verified_reversal(
                    original,
                    allow_legacy_original=allow_legacy_original,
                )
        return self

    def _reverse_moves(self, default_values_list=None, cancel=False):
        """Block core/wizard reversal of protected GL evidence.

        Every suite workflow must enter through
        :meth:`_eh_reverse_with_verified_capability`.  Sealing happens here,
        in the same transaction as core reversal creation, so no editable or
        unlinked reversal can escape even when a caller forgets a second
        helper call.
        """
        protected = self._eh_frozen_by_seal()
        verified_authorised = (
            self.env.context.get(_EH_REVERSE_SEALED)
            is _EH_REVERSE_SEALED_CAPABILITY
        )
        legacy_authorised = (
            self.env.context.get(_EH_REVERSE_LEGACY)
            is _EH_REVERSE_LEGACY_CAPABILITY
        )
        authorised = verified_authorised or legacy_authorised
        if protected and not authorised:
            raise UserError(_(
                "A sealed or legacy-quarantined journal entry cannot be "
                "reversed directly. Reverse its owning ERP Heritage source "
                "record instead."
            ))
        reversals = super()._reverse_moves(
            default_values_list=default_values_list,
            cancel=cancel,
        )
        if protected:
            if len(reversals) != len(self):
                raise UserError(_(
                    "The protected reversal did not produce exactly one "
                    "counter-entry per original journal entry."
                ))
            sealed_reversals = self.env['account.move']
            for original, reversal in zip(self, reversals):
                if original in protected:
                    reversal._eh_align_verified_cash_rounding_accounts(
                        original,
                    )
                    reversal._eh_align_verified_storno_dimensions(original)
                    reversal._eh_validate_verified_reversal(
                        original,
                        allow_legacy_original=legacy_authorised,
                    )
                    sealed_reversals |= reversal
            sealed_reversals._eh_stamp_verified_seal()
        if authorised:
            # Do not leak the capability on the returned recordset.  A caller
            # may use the result normally, but every later provenance change
            # must re-enter a narrow private helper.
            clean_context = dict(reversals.env.context)
            clean_context.pop(_EH_REVERSE_SEALED, None)
            clean_context.pop(_EH_REVERSE_LEGACY, None)
            reversals = reversals.with_context(clean_context)
        return reversals

    @api.private
    def _eh_set_reversed_entry(self, original=False):
        """Set/clear a protected reversal link for a sanctioned workflow.

        A few aggregate workflows must temporarily clear the link before
        posting because core otherwise auto-reconciles non-reconcilable P&L
        legs.  They restore it in the same transaction through this helper.
        """
        self._eh_check_access('write')
        original = (
            self.env['account.move'].browse(
                original.id if hasattr(original, 'id') else original
            ).exists()
            if original
            else self.env['account.move']
        )
        if original:
            original._eh_check_access('read')
            verified_original = bool(
                original.eh_sealed
                and not original.eh_legacy_unverified_seal
            )
            reviewed_legacy_original = bool(
                self.env.context.get(_EH_REVERSE_LEGACY)
                is _EH_REVERSE_LEGACY_CAPABILITY
                and original.eh_legacy_unverified_seal
                and not original.eh_sealed
            )
            if not (verified_original or reviewed_legacy_original):
                raise UserError(_(
                    "A protected reversal link requires a verified sealed "
                    "original or an explicitly reviewed legacy quarantine."
                ))
        guarded = self.sudo().with_context(**{
            _EH_REVERSE_SEALED: _EH_REVERSE_SEALED_CAPABILITY,
        })
        result = guarded.write({
            'reversed_entry_id': original.id if original else False,
        })
        if original:
            guarded._eh_validate_verified_reversal(
                original,
                allow_legacy_original=reviewed_legacy_original,
            )
        return result

    @api.private
    def _eh_stamp_verified_seal(self):
        """Stamp only current, server-produced evidence as verified.

        An upgrade-quarantined move can never be blessed by this helper. A
        reviewed correction must create a new move, keeping the legacy row and
        its uncertainty immutable.
        """
        if self.filtered('eh_legacy_unverified_seal'):
            raise UserError(_(
                "An unverified legacy seal cannot be promoted to verified "
                "evidence. Create a new reviewed journal entry instead."
            ))
        allow_legacy_original = (
            self.env.context.get(_EH_REVERSE_LEGACY)
            is _EH_REVERSE_LEGACY_CAPABILITY
        )
        for reversal in self.filtered('reversed_entry_id'):
            reversal._eh_validate_verified_reversal(
                reversal.reversed_entry_id,
                allow_legacy_original=allow_legacy_original,
            )
        unsealed = self.filtered(lambda move: not move.eh_sealed)
        if unsealed:
            unsealed.flush_recordset()
            self.env.cr.execute(
                "SELECT id FROM account_move WHERE id IN %s "
                "ORDER BY id FOR UPDATE",
                (tuple(sorted(unsealed.ids)),),
            )
            unsealed.invalidate_recordset([
                'eh_sealed', 'eh_legacy_unverified_seal',
            ])
            if unsealed.filtered('eh_legacy_unverified_seal'):
                raise UserError(_(
                    "An unverified legacy seal cannot be promoted to "
                    "verified evidence."
                ))
            unsealed = unsealed.filtered(lambda move: not move.eh_sealed)
            dirty_delivery_evidence = unsealed.filtered(
                lambda move: (
                    bool(move.access_token)
                    or bool(move.is_move_sent)
                    or bool(getattr(move, 'sending_data', None))
                    or bool(getattr(move, 'send_and_print_values', None))
                    or bool(getattr(move, 'invoice_pdf_report_id', None))
                )
            )
            if dirty_delivery_evidence:
                raise UserError(_(
                    "Journal entry %(moves)s carries pre-existing portal, "
                    "sending, or legal-PDF state and cannot be stamped as "
                    "verified evidence. Regenerate external-delivery "
                    "evidence only after a clean seal.",
                    moves=', '.join(
                        move.display_name
                        for move in dirty_delivery_evidence
                    ),
                ))
            if unsealed and self.env['account.move'].sudo().search_count([
                ('reversed_entry_id', 'in', unsealed.ids),
            ], limit=1):
                raise UserError(_(
                    "A journal entry that already has a reversal cannot be "
                    "newly stamped as verified source evidence. Review and "
                    "quarantine the existing reversal graph instead."
                ))
            unsealed.sudo().with_context(**{
                _EH_ALLOW_SEAL: _EH_SEAL_CAPABILITY,
                # Odoo 16/17 may finish dynamic invoice-line synchronisation
                # inside this write after seal value is already applied.
                _EH_ACCOUNT_ENGINE: _EH_ACCOUNT_ENGINE_CAPABILITY,
            }).write({'eh_sealed': True})
        return self

    @api.private
    def _eh_write_sealed_metadata(self, vals, allowed_fields):
        """Write a caller-declared, server-owned metadata field subset.

        This is the narrow corridor for post-seal delivery/integration audit
        state.  ``@api.private`` keeps it off RPC, the exact object capability
        cannot be forged in a client context, and the original actor's write
        access/record rules are proved before any caller-owned ``sudo`` is
        retained for readonly server fields.
        """
        vals = dict(vals or {})
        if self.filtered('eh_legacy_unverified_seal'):
            raise UserError(_(
                "Unverified legacy journal entries cannot enter an external "
                "delivery or integration evidence workflow."
            ))
        allowed_fields = frozenset(allowed_fields or ())
        unexpected = set(vals).difference(allowed_fields)
        if not vals or unexpected:
            raise AccessError(_(
                "The sealed metadata helper received fields outside its "
                "declared server-owned scope: %(fields)s",
                fields=', '.join(sorted(unexpected)) or _('none'),
            ))
        missing = set(vals).difference(self._fields)
        if missing:
            raise AccessError(_(
                "Unknown sealed metadata fields: %s",
                ', '.join(sorted(missing)),
            ))
        self.sudo(False)._eh_check_access('write')
        guarded = self.with_context(**{
            _EH_SEALED_METADATA: _EH_SEALED_METADATA_CAPABILITY,
            # Odoo 16/17 enter dynamic invoice-line synchronisation for every
            # account.move.write, including metadata-only changes.
            _EH_ACCOUNT_ENGINE: _EH_ACCOUNT_ENGINE_CAPABILITY,
        })
        return guarded.write(vals)

    @api.private
    def _eh_message_post_sealed_metadata(self, **kwargs):
        """Post integration chatter while allowing main-attachment metadata."""
        self.sudo(False)._eh_check_access('write')
        guarded = self.with_context(**{
            _EH_SEALED_METADATA: _EH_SEALED_METADATA_CAPABILITY,
        })
        return guarded.message_post(**kwargs)

    @api.private
    def _eh_refresh_commercial_projection(self):
        """Persist installed-MRO commercial roots after partner reparenting.

        Odoo 18/19 deliberately sudo-update related journal entries while a
        partner is reparented.  The generic core scalar is not authoritative
        for every extension (``hr_expense`` has an own-account exception), so
        recompute on each real move and persist groups sharing the same
        server-derived value.  Caller can enter only through Base's
        unforgeable partner-write capability.
        """
        if (
            self.env.context.get(_EH_COMMERCIAL_PROJECTION_REFRESH)
            is not _EH_COMMERCIAL_PROJECTION_REFRESH_CAPABILITY
        ):
            raise AccessError(_(
                "Commercial projections can only be refreshed by the "
                "authoritative partner hierarchy engine."
            ))
        self.mapped('partner_id').invalidate_recordset([
            'commercial_partner_id',
        ])
        # Invoke the installed compute through the field engine. Calling the
        # method directly on persisted rows makes each assignment enter
        # ``write``; the narrow refresh guard would then call this helper
        # again and recurse. ``compute_value`` protects the computed field
        # while still executing the complete installed MRO (including
        # ``hr_expense``), leaving the authoritative values in cache for the
        # explicit persistence below.
        self._fields['commercial_partner_id'].compute_value(self)
        grouped = {}
        for move in self:
            expected_id = move.commercial_partner_id.id or False
            grouped.setdefault(expected_id, self.env['account.move'])
            grouped[expected_id] |= move
        for expected_id, moves in grouped.items():
            guarded_moves = moves.with_context(**{
                _EH_ACCOUNT_ENGINE: _EH_ACCOUNT_ENGINE_CAPABILITY,
                # Odoo 18/19 otherwise classifies this server-derived stored-
                # compute persistence as an interactive invoice modification.
                'skip_is_manually_modified': True,
                # This write persists one already-computed header projection;
                # invoice tax/payment-term synchronisation must not touch AMLs.
                'skip_invoice_sync': True,
            })
            super(AccountMove, guarded_moves).write({
                'commercial_partner_id': expected_id,
            })
        self.invalidate_recordset(['commercial_partner_id'])
        return True

    def write(self, vals):
        secure_hash_write = (
            self._eh_has_secure_hash_capability()
            and bool(vals)
            and set(vals).issubset({
                'inalterable_hash', 'secure_sequence_number',
            })
            and (
                'inalterable_hash' not in vals
                or bool(vals['inalterable_hash'])
            )
            and (
                'secure_sequence_number' not in vals
                or isinstance(vals['secure_sequence_number'], int)
                and vals['secure_sequence_number'] > 0
            )
        )
        projection_owned = (
            _EH_SERVER_OWNED_MOVE_PROJECTION_FIELDS.intersection(vals)
        )
        if projection_owned and (
            self.env.context.get(_EH_COMMERCIAL_PROJECTION_REFRESH)
            is _EH_COMMERCIAL_PROJECTION_REFRESH_CAPABILITY
        ):
            if set(vals) != {'commercial_partner_id'}:
                raise AccessError(_(
                    "Partner hierarchy refresh cannot change unrelated "
                    "journal-entry fields."
                ))
            return self._eh_refresh_commercial_projection()
        if projection_owned and not (
            self.env.context.get(_EH_ACCOUNT_ENGINE)
            is _EH_ACCOUNT_ENGINE_CAPABILITY
        ):
            raise AccessError(_(
                "Journal-entry commercial projections are server-owned and "
                "cannot be edited directly: %s",
                ', '.join(sorted(projection_owned)),
            ))
        server_owned = _EH_SERVER_OWNED_MOVE_FIELDS.intersection(vals)
        protected_server_owned = (
            server_owned & _EH_ALWAYS_SERVER_OWNED_MOVE_FIELDS
        )
        if self._eh_frozen_by_seal():
            protected_server_owned |= server_owned
        if (
            protected_server_owned
            and not (
                self.env.context.get(_EH_SEALED_METADATA)
                is _EH_SEALED_METADATA_CAPABILITY
            )
        ):
            raise AccessError(_(
                "Portal, sending, and legal-PDF evidence is server-owned "
                "and cannot be edited directly: %s",
                ', '.join(sorted(protected_server_owned)),
            ))
        if 'eh_legacy_unverified_seal' in vals:
            raise AccessError(_(
                "The legacy-unverified seal is immutable and upgrade-owned."
            ))
        if 'eh_sealed' in vals:
            sealing = bool(vals['eh_sealed'])
            if sealing and self.filtered('eh_legacy_unverified_seal'):
                raise UserError(_(
                    "An unverified legacy seal is immutable and cannot be "
                    "promoted to verified evidence."
                ))
            allowed = (
                self.env.su
                and (
                    (
                        sealing
                        and self.env.context.get(_EH_ALLOW_SEAL)
                        is _EH_SEAL_CAPABILITY
                    )
                )
            )
            if not allowed:
                raise AccessError(_(
                    "The sub-ledger journal-entry seal is server-owned and "
                    "cannot be edited directly."
                ))
        self._eh_guard_reversed_entry_values(vals)
        protected_stored_fields = {
            field_name
            for field_name in vals
            if field_name in self._fields
            and self._fields[field_name].store
            and field_name not in _EH_SEALED_MOVE_STORED_ALLOWLIST
        }
        protected_stored_fields.update(
            _EH_SEALED_MOVE_EXPLICIT_GUARD_FIELDS.intersection(vals)
        )
        # A sealed entry is fail-closed for stored evidence. This catches new
        # core/module fields automatically instead of relying on a finite list
        # of known financial outputs. Legitimate engine/metadata mutations use
        # an in-process object capability; no RPC-writable field is exempt.
        if 'state' in vals:
            self._eh_guard_sealed(_("changed state"))
        chatter_main_attachment_only = (
            self.env.context.get(_EH_CHATTER)
            is _EH_CHATTER_CAPABILITY
            and protected_stored_fields.issubset({
                'message_main_attachment_id',
            })
        )
        if (
            protected_stored_fields.difference({'state'})
            and not chatter_main_attachment_only
            and not secure_hash_write
        ):
            self._eh_guard_sealed(_("edited"))
        # Snapshot the prior state per id so we only bump the move
        # version counter when state actually changes. The previous
        # implementation bumped on every write that *included* state in
        # vals, even when the new value matched the old, which produced
        # spurious cache invalidation during routine recomputes.
        material_company_ids = set()
        if self and _EH_MATERIAL_MOVE_FIELDS.intersection(vals):
            material_company_ids = set(
                self.filtered(lambda move: move.state == 'posted').mapped(
                    'company_id.id'
                )
            )
        if 'state' in vals and self:
            new_state = vals['state']
            changed_ids = [m.id for m in self if m.state != new_state]
        else:
            changed_ids = []
        # Odoo 16/17 run dynamic invoice-line synchronisation after every
        # account.move write, including a server-owned metadata-only update.
        # Carry the accounting-engine object capability only when the caller
        # already holds the unforgeable sealed-metadata capability; this lets
        # core restore its own line projections without opening an RPC path.
        core_self = self
        if (
            self.env.context.get(_EH_SEALED_METADATA)
            is _EH_SEALED_METADATA_CAPABILITY
            and self.env.context.get(_EH_ACCOUNT_ENGINE)
            is not _EH_ACCOUNT_ENGINE_CAPABILITY
        ):
            core_self = self.with_context(**{
                _EH_ACCOUNT_ENGINE: _EH_ACCOUNT_ENGINE_CAPABILITY,
            })
        result = super(AccountMove, core_self).write(vals)
        if changed_ids:
            changed = self.browse(changed_ids)
            company_ids = set(changed.mapped('company_id.id'))
            if company_ids:
                self.env['res.company'].sudo()._eh_bump_move_version(company_ids)
        if material_company_ids:
            material_company_ids.update(self.mapped('company_id.id'))
            self.env['res.company'].sudo()._eh_bump_move_version(
                material_company_ids,
            )
        return result

    def unlink(self):
        # A client can forge Odoo's ``force_delete`` context flag. Keep the
        # suite seal independent of that flag, and invalidate cached reports
        # even when an unsealed posted move is legitimately force-deleted.
        self._eh_guard_sealed(_("deleted"))
        posted_company_ids = set(
            self.filtered(lambda move: move.state == 'posted').mapped(
                'company_id.id'
            )
        )
        result = super().unlink()
        if posted_company_ids:
            self.env['res.company'].sudo()._eh_bump_move_version(
                posted_company_ids,
            )
        return result


class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    def _eh_analytic_distribution_display(self):
        """Resolve analytic distribution ids into names and percentages."""
        self.ensure_one()
        distribution = self.analytic_distribution or {}
        if not isinstance(distribution, dict):
            return ''
        ids = set()
        parsed = []
        for raw_key, percentage in distribution.items():
            key_ids = []
            for token in str(raw_key).split(','):
                try:
                    analytic_id = int(token.strip())
                except (TypeError, ValueError):
                    continue
                ids.add(analytic_id)
                key_ids.append(analytic_id)
            if key_ids:
                parsed.append((key_ids, percentage))
        AnalyticAccount = self.env['account.analytic.account']
        accounts = AnalyticAccount.browse()
        if AnalyticAccount.check_access_rights(
                'read', raise_exception=False):
            # Search applies record rules, unlike a raw browse/exists probe.
            # Hidden analytic ids therefore render as unavailable instead of
            # leaking a name or aborting the whole journal PDF.
            accounts = AnalyticAccount.search([
                ('id', 'in', sorted(ids)),
            ])
        names = {account.id: account.display_name for account in accounts}
        labels = []
        for key_ids, percentage in parsed:
            key_names = [
                names.get(analytic_id, _("Unavailable analytic"))
                for analytic_id in key_ids
            ]
            try:
                numeric = float(percentage)
                percentage_label = "%g%%" % numeric
            except (TypeError, ValueError):
                percentage_label = _("invalid percentage")
            labels.append(" + ".join(key_names) + ": " + percentage_label)
        return ", ".join(labels)

    @api.model
    def default_get(self, fields_list):
        """Drop context/ir.default attempts to seed parent projections."""
        defaults = super().default_get(fields_list)
        if not (
            self.env.context.get(_EH_ACCOUNT_ENGINE)
            is _EH_ACCOUNT_ENGINE_CAPABILITY
        ):
            for field_name in (
                _EH_SERVER_OWNED_LINE_PROJECTION_FIELDS.intersection(
                    fields_list,
                )
            ):
                defaults.pop(field_name, None)
        return defaults

    @api.model
    def _eh_guard_server_owned_projection_values(self, vals):
        protected = _EH_SERVER_OWNED_LINE_PROJECTION_FIELDS.intersection(vals)
        if not protected:
            return
        if (
            self.env.context.get(_EH_ACCOUNT_ENGINE)
            is _EH_ACCOUNT_ENGINE_CAPABILITY
        ):
            return
        raise AccessError(_(
            "Journal-item parent/origin projections are server-owned and "
            "cannot be supplied or edited directly: %(fields)s",
            fields=', '.join(sorted(protected)),
        ))

    @api.model
    def _eh_authoritative_projection_value(self, move, field_name):
        """Return primitive value derived from authoritative parent/origin."""
        if field_name == 'move_name':
            return move.name or False
        if field_name == 'parent_state':
            return move.state or False
        if field_name == 'statement_id':
            statement_line = getattr(move, 'statement_line_id', False)
            statement = (
                getattr(statement_line, 'statement_id', False)
                if statement_line else False
            )
            return statement.id if statement else False
        source_name = {
            'payment_id': (
                'origin_payment_id'
                if 'origin_payment_id' in move._fields else 'payment_id'
            ),
        }.get(field_name, field_name)
        value = getattr(move, source_name, False)
        if getattr(value, '_name', False):
            return value.id or False
        return value or False

    @api.model
    def _eh_projection_values_equal(self, field_name, supplied, expected):
        field = self._fields.get(field_name)
        if field and field.type == 'many2one':
            supplied = getattr(supplied, 'id', supplied) or False
            expected = getattr(expected, 'id', expected) or False
            try:
                supplied = int(supplied) if supplied else False
                expected = int(expected) if expected else False
            except (TypeError, ValueError):
                return False
        elif field and field.type == 'date':
            supplied = fields.Date.to_date(supplied) if supplied else False
            expected = fields.Date.to_date(expected) if expected else False
        elif field and field.type in ('char', 'text', 'selection'):
            supplied = supplied or False
            expected = expected or False
        return supplied == expected

    @api.model
    def _eh_sanitise_projection_create_values(self, vals, move):
        """Accept core's exact redundant projections; discard before create.

        Odoo cash-rounding and other engine paths explicitly include exact
        company/date projections in new line values.  Rejecting key presence
        breaks those standard workflows.  Exact values are harmless and are
        removed so stored related fields always compute from their parent;
        any mismatch remains a forgery and fails closed.
        """
        protected = _EH_SERVER_OWNED_LINE_PROJECTION_FIELDS.intersection(vals)
        if not protected or (
            self.env.context.get(_EH_ACCOUNT_ENGINE)
            is _EH_ACCOUNT_ENGINE_CAPABILITY
        ):
            return vals
        if not move:
            self._eh_guard_server_owned_projection_values(vals)
        clean = dict(vals)
        mismatched = []
        for field_name in protected:
            expected = self._eh_authoritative_projection_value(
                move, field_name,
            )
            if not self._eh_projection_values_equal(
                field_name, vals[field_name], expected,
            ):
                mismatched.append(field_name)
            else:
                clean.pop(field_name, None)
        if mismatched:
            raise AccessError(_(
                "Journal-item parent/origin projections do not match their "
                "authoritative journal entry: %(fields)s",
                fields=', '.join(sorted(mismatched)),
            ))
        return clean

    def _eh_sanitise_projection_write_values(self, vals, destination=False):
        """Strip exact engine projections; reject any persisted mismatch."""
        protected = _EH_SERVER_OWNED_LINE_PROJECTION_FIELDS.intersection(vals)
        if not protected or (
            self.env.context.get(_EH_ACCOUNT_ENGINE)
            is _EH_ACCOUNT_ENGINE_CAPABILITY
        ):
            return vals
        if not self:
            self._eh_guard_server_owned_projection_values(vals)
        mismatched = set()
        for line in self:
            move = destination or line.move_id
            for field_name in protected:
                expected = self._eh_authoritative_projection_value(
                    move, field_name,
                )
                if not self._eh_projection_values_equal(
                    field_name, vals[field_name], expected,
                ):
                    mismatched.add(field_name)
        if mismatched:
            raise AccessError(_(
                "Journal-item parent/origin projections do not match their "
                "authoritative journal entry: %(fields)s",
                fields=', '.join(sorted(mismatched)),
            ))
        return {
            field_name: value
            for field_name, value in vals.items()
            if field_name not in protected
        }

    @api.model_create_multi
    def create(self, vals_list):
        # Adding a line to an already-posted move (in an unlocked period)
        # changes report figures with no state transition, so the write()
        # hook alone would let the reporting cache serve a stale payload.
        # Bump the version for every newly created line whose parent move is
        # already posted. Lines on draft moves (the common case: entry built
        # up before action_post) do not bump, so we do not over-bump.
        default_move_id = self.env.context.get('default_move_id')
        effective_move_ids = [
            vals.get('move_id') or default_move_id
            for vals in vals_list
        ]
        vals_list = [
            (
                dict(vals, move_id=int(move_id))
                if move_id and not vals.get('move_id') else vals
            )
            for vals, move_id in zip(vals_list, effective_move_ids)
        ]
        target_move_ids = {
            int(move_id) for move_id in effective_move_ids if move_id
        }
        target_moves = self.env['account.move']
        if target_move_ids:
            target_moves = self.env['account.move'].browse(
                sorted(target_move_ids)
            ).exists()
            if not self.env.su:
                target_moves._eh_check_access('write')
            target_moves._eh_guard_sealed(_("edited"))
        target_by_id = {move.id: move for move in target_moves}
        vals_list = [
            self._eh_sanitise_projection_create_values(
                vals,
                target_by_id.get(int(move_id)) if move_id else False,
            )
            for vals, move_id in zip(vals_list, effective_move_ids)
        ]
        protected_defaults = {
            'default_%s' % field_name
            for field_name in _EH_SERVER_OWNED_LINE_PROJECTION_FIELDS
        }
        create_context = {
            key: value for key, value in self.env.context.items()
            if key not in protected_defaults
        }
        create_self = self.with_context(create_context)
        lines = super(AccountMoveLine, create_self).create(vals_list)
        posted = lines.filtered(lambda line: line.move_id.state == 'posted')
        # A new line added to a SEALED posted move would move the figure.
        lines._eh_guard_sealed_lines()
        bump_company_ids = set(posted.mapped('company_id.id'))
        if bump_company_ids:
            self.env['res.company'].sudo()._eh_bump_move_version(
                bump_company_ids)
        return lines

    def unlink(self):
        # Removing a line from a SEALED posted move would move the figure.
        self._eh_guard_sealed_lines()
        # Removing a line from an already-posted move (in an unlocked period)
        # changes report figures with no state transition. Snapshot the
        # affected companies before the delete, since the records are gone
        # after super().unlink(). Only posted moves bump, so removing lines
        # from a draft move does not over-bump.
        posted = self.filtered(lambda line: line.move_id.state == 'posted')
        bump_company_ids = set(posted.mapped('company_id.id'))
        result = super().unlink()
        if bump_company_ids:
            self.env['res.company'].sudo()._eh_bump_move_version(
                bump_company_ids)
        return result

    def _eh_guard_sealed_lines(self):
        if (
            self.env.context.get(_EH_ACCOUNT_ENGINE)
            is _EH_ACCOUNT_ENGINE_CAPABILITY
        ):
            return
        if (
            self.env.context.get(_EH_REVERSE_SEALED)
            is _EH_REVERSE_SEALED_CAPABILITY
        ):
            return
        legacy = self.filtered(
            lambda line: line.move_id.eh_legacy_unverified_seal
        )
        if legacy:
            legacy.mapped('move_id')._eh_guard_sealed(_("edited"))
        if (
            self.env.context.get(_EH_POST_SEALED)
            is _EH_POST_SEALED_CAPABILITY
        ):
            return
        sealed = self.filtered(
            lambda line: line.move_id.eh_sealed)
        if sealed:
            raise UserError(_(
                "The figures on journal entry %s are frozen: it is the posted "
                "counterpart of an ERP Heritage sub-ledger figure. Reverse the "
                "source record to change them.",
                ', '.join(
                    line.move_id.name or '/' for line in sealed
                )))

    def reconcile(self):
        """Let core reconciliation refresh sealed residual outputs safely."""
        guarded = self.with_context(**{
            _EH_ACCOUNT_ENGINE: _EH_ACCOUNT_ENGINE_CAPABILITY,
        })
        result = super(AccountMoveLine, guarded).reconcile()

        def clean_result(item):
            if isinstance(item, models.BaseModel):
                clean_context = dict(item.env.context)
                clean_context.pop(_EH_ACCOUNT_ENGINE, None)
                return item.with_context(clean_context)
            if isinstance(item, list):
                return [clean_result(child) for child in item]
            if isinstance(item, tuple):
                return tuple(clean_result(child) for child in item)
            if isinstance(item, dict):
                return {
                    clean_result(key): clean_result(value)
                    for key, value in item.items()
                }
            if isinstance(item, set):
                return {clean_result(child) for child in item}
            return item

        return clean_result(result)

    def _reconcile_plan_with_sync(self, plan_list, all_amls):
        """Authorize every standard private reconciliation-plan engine.

        Odoo 17+ reconciliation widgets and bank-matching engines can call the
        private plan API without entering ``reconcile()``.  Carry the same
        unforgeable engine capability there so core may update sealed residual
        and full/partial-reconcile evidence, then remove it from recordsets
        written back into caller-owned plan dictionaries.
        """
        guarded_self = self.with_context(**{
            _EH_ACCOUNT_ENGINE: _EH_ACCOUNT_ENGINE_CAPABILITY,
        })
        guarded_amls = all_amls.with_context(**{
            _EH_ACCOUNT_ENGINE: _EH_ACCOUNT_ENGINE_CAPABILITY,
        })
        try:
            return super(
                AccountMoveLine, guarded_self,
            )._reconcile_plan_with_sync(plan_list, guarded_amls)
        finally:
            clean_context = dict(self.env.context)
            clean_context.pop(_EH_ACCOUNT_ENGINE, None)
            for plan in plan_list:
                partials = plan.get('partials')
                if getattr(partials, '_name', None):
                    plan['partials'] = self.env[partials._name].with_context(
                        clean_context,
                    ).browse(partials.ids)

    def remove_move_reconcile(self):
        """Let core unreconciliation refresh sealed residual outputs safely."""
        guarded = self.with_context(**{
            _EH_ACCOUNT_ENGINE: _EH_ACCOUNT_ENGINE_CAPABILITY,
        })
        return super(AccountMoveLine, guarded).remove_move_reconcile()


    def write(self, vals):
        destination = False
        if vals.get('move_id'):
            destination = self.env['account.move'].browse(
                int(vals['move_id'])
            ).exists()
            if not self.env.su:
                destination._eh_check_access('write')
            destination._eh_guard_sealed(_("edited"))
        vals = self._eh_sanitise_projection_write_values(
            vals, destination=destination,
        )
        # Editing a financially-material field on a line of a SEALED posted
        # move would desync the sub-ledger figure from its GL entry; refuse it.
        protected_stored_fields = {
            field_name
            for field_name in vals
            if field_name in self._fields
            and self._fields[field_name].store
            and field_name not in _EH_SEALED_LINE_STORED_ALLOWLIST
        }
        if protected_stored_fields:
            self._eh_guard_sealed_lines()
        # Only a change to a financially-material field on a line belonging
        # to a posted move affects report figures. Snapshot the affected
        # companies before the write so a change to the line's account (and
        # therefore, on some series, to the derived company) is captured
        # against the company the figures were reported under.
        bump_company_ids = set()
        if self and _EH_MATERIAL_LINE_FIELDS.intersection(vals):
            posted = self.filtered(lambda line: line.move_id.state == 'posted')
            bump_company_ids = set(posted.mapped('company_id.id'))
        core_self = self
        allowlisted_only = (
            bool(vals)
            and set(vals).issubset(_EH_SEALED_LINE_STORED_ALLOWLIST)
        )
        if allowlisted_only:
            # Before 18.0, the follow-up ``blocked`` toggle enters core's
            # dynamic invoice synchronisation. Permit only that exact
            # allow-listed operational write to carry the engine capability;
            # arbitrary line fields remain frozen above.
            core_self = self.with_context(**{
                _EH_ACCOUNT_ENGINE: _EH_ACCOUNT_ENGINE_CAPABILITY,
            })
        result = super(AccountMoveLine, core_self).write(vals)
        if self and _EH_MATERIAL_LINE_FIELDS.intersection(vals):
            # ``move_id`` is material too. A line can be re-parented by
            # internal accounting flows, so capture the destination after
            # the write as well as the source captured above. Otherwise a
            # draft -> posted re-parent would change a published ledger
            # without moving that destination company's freshness counter.
            destination_posted = self.filtered(
                lambda line: line.move_id.state == 'posted'
            )
            bump_company_ids.update(
                destination_posted.mapped('company_id.id')
            )
        if bump_company_ids:
            self.env['res.company'].sudo()._eh_bump_move_version(
                bump_company_ids)
        return result


class AccountPartialReconcile(models.Model):
    _inherit = 'account.partial.reconcile'

    # Reconciliation changes no material line field and performs no move state
    # transition, yet it changes cash-basis recognition (income/expense
    # recognised in proportion to the matched amount as of a date) and aging.
    # Those figures key on the per-company eh_move_version counter, so
    # reconciling / un-reconciling must bump it or cash-basis and aged reports
    # serve stale cached numbers until an unrelated move posts.

    @api.model
    def _eh_reconcile_lines_from_values(self, vals_list=None):
        """Resolve existing and prospective lines without elevating access."""
        lines = self.env['account.move.line']
        if self:
            actor_partials = self.sudo(False)
            actor_partials._eh_check_access('read')
            lines |= (
                actor_partials.mapped('debit_move_id')
                | actor_partials.mapped('credit_move_id')
            )
        line_ids = {
            int(vals[field_name])
            for vals in (vals_list or [])
            for field_name in ('debit_move_id', 'credit_move_id')
            if vals.get(field_name)
        }
        if line_ids:
            prospective = self.env['account.move.line'].browse(
                sorted(line_ids),
            )
            prospective.sudo(False)._eh_check_access('read')
            lines |= prospective.exists()
        return lines

    def _eh_guard_low_level_reconcile(self, vals_list=None):
        """Require the line reconciliation engine for frozen journal items.

        ``account.partial.reconcile`` has normal user CRUD ACLs and its core
        create/unlink methods update residual and matching outputs partly by
        SQL.  Consequently the journal-line ``write`` guard cannot distinguish
        a direct RPC mutation from a real ``account.move.line.reconcile`` by
        itself.  Only the latter enters with the exact object capability.
        """
        if (
            self.env.context.get(_EH_ACCOUNT_ENGINE)
            is _EH_ACCOUNT_ENGINE_CAPABILITY
        ):
            return
        lines = self._eh_reconcile_lines_from_values(vals_list)
        frozen_moves = lines.mapped('move_id')._eh_frozen_by_seal()
        if frozen_moves:
            raise UserError(_(
                "Reconciliation evidence for sealed or legacy-quarantined "
                "journal entries can only be changed through the standard "
                "reconcile or unreconcile workflow."
            ))

    @api.model_create_multi
    def create(self, vals_list):
        self._eh_guard_low_level_reconcile(vals_list)
        recs = super().create(vals_list)
        companies = recs.company_id
        if companies:
            self.env['res.company'].sudo()._eh_bump_move_version(companies.ids)
        return recs

    def unlink(self):
        self._eh_guard_low_level_reconcile()
        company_ids = set(self.mapped('company_id.id'))
        result = super().unlink()
        if company_ids:
            self.env['res.company'].sudo()._eh_bump_move_version(company_ids)
        return result

    def write(self, vals):
        self._eh_guard_low_level_reconcile([vals])
        material_fields = {
            'debit_move_id', 'credit_move_id', 'full_reconcile_id',
            'exchange_move_id', 'amount', 'debit_amount_currency',
            'credit_amount_currency', 'company_id', 'max_date',
        }
        company_ids = set()
        if material_fields.intersection(vals):
            company_ids.update(self.mapped('company_id.id'))
        result = super().write(vals)
        if material_fields.intersection(vals):
            company_ids.update(self.mapped('company_id.id'))
        if company_ids:
            self.env['res.company'].sudo()._eh_bump_move_version(company_ids)
        return result


class AccountFullReconcile(models.Model):
    _inherit = 'account.full.reconcile'

    @api.model
    def _eh_linked_ids_from_commands(self, commands):
        """Return ids referenced by relational commands without executing."""
        ids = set()
        for command in commands or ():
            operation = command[0]
            if operation in (
                Command.UPDATE,
                Command.DELETE,
                Command.UNLINK,
                Command.LINK,
            ) and command[1]:
                ids.add(int(command[1]))
            elif operation == Command.SET:
                ids.update(int(record_id) for record_id in command[2])
        return ids

    def _eh_full_reconcile_lines_from_values(self, vals_list=None):
        lines = self.env['account.move.line']
        partials = self.env['account.partial.reconcile']
        if self:
            actor_fulls = self.sudo(False)
            actor_fulls._eh_check_access('read')
            lines |= actor_fulls.mapped('reconciled_line_ids')
            partials |= actor_fulls.mapped('partial_reconcile_ids')
        line_ids = set()
        partial_ids = set()
        for vals in vals_list or ():
            line_ids.update(self._eh_linked_ids_from_commands(
                vals.get('reconciled_line_ids'),
            ))
            partial_ids.update(self._eh_linked_ids_from_commands(
                vals.get('partial_reconcile_ids'),
            ))
        if line_ids:
            prospective_lines = self.env['account.move.line'].browse(
                sorted(line_ids),
            )
            prospective_lines.sudo(False)._eh_check_access('read')
            lines |= prospective_lines.exists()
        if partial_ids:
            prospective_partials = self.env[
                'account.partial.reconcile'
            ].browse(sorted(partial_ids))
            prospective_partials.sudo(False)._eh_check_access('read')
            partials |= prospective_partials.exists()
        if partials:
            lines |= partials.mapped('debit_move_id')
            lines |= partials.mapped('credit_move_id')
        return lines

    def _eh_guard_low_level_full_reconcile(self, vals_list=None):
        if (
            self.env.context.get(_EH_ACCOUNT_ENGINE)
            is _EH_ACCOUNT_ENGINE_CAPABILITY
        ):
            return
        lines = self._eh_full_reconcile_lines_from_values(vals_list)
        if lines.mapped('move_id')._eh_frozen_by_seal():
            raise UserError(_(
                "Full-reconciliation evidence for sealed or "
                "legacy-quarantined journal entries can only be changed "
                "through the standard reconcile or unreconcile workflow."
            ))

    @api.model_create_multi
    def create(self, vals_list):
        self._eh_guard_low_level_full_reconcile(vals_list)
        return super().create(vals_list)

    def write(self, vals):
        self._eh_guard_low_level_full_reconcile([vals])
        return super().write(vals)

    def unlink(self):
        self._eh_guard_low_level_full_reconcile()
        return super().unlink()


class AccountPaymentRegister(models.TransientModel):
    _inherit = 'account.payment.register'

    def _reconcile_payments(self, to_process, edit_mode=False):
        """Carry the engine capability on the source journal items too.

        Core builds ``to_process`` before entering this hook, so those line
        recordsets retain their original context even when the wizard itself
        is guarded. In particular, core writes ``matched_payment_ids`` through
        ``lines.move_id`` after reconciliation. Re-contextualise only the
        records consumed by this private payment-engine step.
        """
        guarded_to_process = []
        for values in to_process:
            guarded_values = dict(values)
            guarded_values['to_reconcile'] = values[
                'to_reconcile'
            ].with_context(**{
                _EH_ACCOUNT_ENGINE: _EH_ACCOUNT_ENGINE_CAPABILITY,
            })
            guarded_to_process.append(guarded_values)
        guarded = self.with_context(**{
            _EH_ACCOUNT_ENGINE: _EH_ACCOUNT_ENGINE_CAPABILITY,
        })
        return super(AccountPaymentRegister, guarded)._reconcile_payments(
            guarded_to_process,
            edit_mode=edit_mode,
        )

    def _create_payments(self):
        """Keep core payment-link/residual writes inside the engine corridor."""
        guarded = self.with_context(**{
            _EH_ACCOUNT_ENGINE: _EH_ACCOUNT_ENGINE_CAPABILITY,
        })
        payments = super(AccountPaymentRegister, guarded)._create_payments()
        if not payments:
            return payments
        clean_context = dict(payments.env.context)
        clean_context.pop(_EH_ACCOUNT_ENGINE, None)
        return payments.with_context(clean_context)


class AccountMoveSend(models.AbstractModel):
    _inherit = 'account.move.send'

    @api.model
    def _generate_and_send_invoices(
        self, moves, from_cron=False, allow_raising=True,
        allow_fallback_pdf=False, **custom_settings,
    ):
        if moves.filtered('eh_legacy_unverified_seal'):
            raise UserError(_(
                "Unverified legacy journal entries cannot be sent or used "
                "to generate trusted invoice documents. Create a new "
                "reviewed source document."
            ))
        metadata_context = {
            _EH_SEALED_METADATA: _EH_SEALED_METADATA_CAPABILITY,
        }
        guarded_moves = moves.with_context(**metadata_context)
        guarded = self.with_context(**metadata_context)
        attachments = super(
            AccountMoveSend, guarded,
        )._generate_and_send_invoices(
            guarded_moves,
            from_cron=from_cron,
            allow_raising=allow_raising,
            allow_fallback_pdf=allow_fallback_pdf,
            **custom_settings,
        )
        clean_context = dict(attachments.env.context)
        clean_context.pop(_EH_SEALED_METADATA, None)
        return attachments.with_context(clean_context)


class AccountMoveSendBatchWizard(models.TransientModel):
    _inherit = 'account.move.send.batch.wizard'

    def action_send_and_print(
        self, force_synchronous=False, allow_fallback_pdf=False,
    ):
        if self.move_ids.filtered('eh_legacy_unverified_seal'):
            raise UserError(_(
                "Unverified legacy journal entries cannot enter the invoice "
                "sending workflow."
            ))
        guarded = self.with_context(**{
            _EH_SEALED_METADATA: _EH_SEALED_METADATA_CAPABILITY,
        })
        return super(AccountMoveSendBatchWizard, guarded).action_send_and_print(
            force_synchronous=force_synchronous,
            allow_fallback_pdf=allow_fallback_pdf,
        )


class IrAttachment(models.Model):
    _inherit = 'ir.attachment'

    eh_legacy_unverified_legal_pdf = fields.Boolean(
        string="Legacy Unverified Legal PDF",
        default=False,
        readonly=True,
        copy=False,
        index=True,
        help=(
            "Set by an upgrade when a historical account.move legal-PDF "
            "binding predates server-owned delivery evidence. The bytes and "
            "move link are retained immutably for audit, but the attachment "
            "is detached from the legal-PDF facade."
        ),
    )

    def register_as_main_attachment(self, force=True):
        """Protect frozen move main pointers on every supported mail API.

        Odoo 16/17 assign ``message_main_attachment_id`` directly from this
        method and never call the newer record hook.  Restore the original
        controller actor before granting a narrow metadata capability; a
        read-only chatter actor may upload evidence but cannot select it as
        main, while public force=True replacement stays forbidden.
        """
        self.ensure_one()
        if (
            self.env.context.get(_EH_SEALED_METADATA)
            is _EH_SEALED_METADATA_CAPABILITY
        ):
            return super().register_as_main_attachment(force=force)
        if self.res_model != 'account.move' or not self.res_id:
            return super().register_as_main_attachment(force=force)
        actor_attachment = self.sudo(False)
        actor_attachment._eh_check_access('read')
        target = self.env['account.move'].sudo(False).browse(
            self.res_id,
        )
        try:
            target._eh_check_access('write')
        except AccessError:
            return
        if not target.sudo()._eh_frozen_by_seal():
            return super().register_as_main_attachment(force=force)
        current_main = target.sudo().message_main_attachment_id
        if current_main and current_main != self:
            raise UserError(_(
                "The main attachment of a sealed journal entry is "
                "server-owned and cannot be replaced directly."
            ))
        if force:
            raise UserError(_(
                "The main attachment of a sealed journal entry is "
                "server-owned and cannot be replaced directly."
            ))
        guarded = self.with_context(**{
            _EH_SEALED_METADATA: _EH_SEALED_METADATA_CAPABILITY,
        })
        return super(IrAttachment, guarded).register_as_main_attachment(
            force=False,
        )

    def _eh_has_protected_sealed_move_owner(self, destination_vals=None):
        """Whether current/effective ownership is sealed legal evidence."""
        destination_vals = destination_vals or {}
        Move = self.env['account.move'].sudo()

        if self and self.sudo().filtered(
            'eh_legacy_unverified_legal_pdf'
        ):
            return True

        # A current main attachment remains protected even if its own res_model
        # metadata is absent or is being re-pointed by this write.
        if self and Move.search_count([
            ('message_main_attachment_id', 'in', self.ids),
            '|',
            ('eh_sealed', '=', True),
            ('eh_legacy_unverified_seal', '=', True),
        ], limit=1):
            return True

        targets = []
        records = self or self.browse()
        if records:
            for attachment in records.sudo():
                res_model = destination_vals.get(
                    'res_model', attachment.res_model,
                )
                res_id = destination_vals.get('res_id', attachment.res_id)
                res_field = destination_vals.get(
                    'res_field', attachment.res_field,
                )
                if (
                    res_model == 'account.move'
                    and res_id
                    and res_field == 'invoice_pdf_report_file'
                ):
                    targets.append(int(res_id))
        else:
            if (
                destination_vals.get('res_model') == 'account.move'
                and destination_vals.get('res_id')
                and destination_vals.get('res_field')
                == 'invoice_pdf_report_file'
            ):
                targets.append(int(destination_vals['res_id']))
        if not targets:
            return False
        # The legal-PDF attachment namespace is server-owned before posting
        # too. Deny every syntactically valid account.move target uniformly,
        # without sudo-looking up the attacker-supplied id; hidden and
        # nonexistent move ids therefore expose the same result.
        return True

    def _eh_guard_sealed_move_attachment(self, action, destination_vals=None):
        if self and self.sudo().filtered(
            'eh_legacy_unverified_legal_pdf'
        ):
            raise AccessError(_(
                "A quarantined legacy legal-PDF attachment is immutable and "
                "cannot be %(action)s.",
                action=action,
            ))
        if (
            self.env.context.get(_EH_SEALED_METADATA)
            is _EH_SEALED_METADATA_CAPABILITY
        ):
            return
        if (
            (self and self._eh_has_protected_sealed_move_owner())
            or (
                destination_vals
                and self._eh_has_protected_sealed_move_owner(
                    destination_vals,
                )
            )
        ):
            raise AccessError(_(
                "A sealed journal entry's legal or main attachment cannot "
                "be %(action)s directly.",
                action=action,
            ))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('eh_legacy_unverified_legal_pdf'):
                raise AccessError(_(
                    "The legacy legal-PDF quarantine marker is "
                    "upgrade-owned and cannot be supplied directly."
                ))
            self._eh_guard_sealed_move_attachment(
                _("created"),
                destination_vals=vals,
            )
        return super().create(vals_list)

    def write(self, vals):
        if 'eh_legacy_unverified_legal_pdf' in vals:
            raise AccessError(_(
                "The legacy legal-PDF quarantine marker is immutable and "
                "upgrade-owned."
            ))
        self._eh_guard_sealed_move_attachment(
            _("edited"),
            destination_vals=vals,
        )
        return super().write(vals)

    def unlink(self):
        self._eh_guard_sealed_move_attachment(_("deleted"))
        return super().unlink()
