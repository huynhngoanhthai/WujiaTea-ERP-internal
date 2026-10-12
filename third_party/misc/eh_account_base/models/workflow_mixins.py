# -*- encoding: utf-8 -*-
##############################################################################
#
# ERP Heritage
# Copyright (C) 2026 (https://www.erpheritage.com.au/)
#
##############################################################################
"""
Shared workflow / posting mixins for the ERP Heritage accounting suite.

These close three systemic defect classes that were each re-solved (wrongly,
and with drift) across the sub-ledger modules:

eh.workflow.guard
    A state machine that is protected only by a ``readonly`` widget and a
    write() guard that blocks leaving a frozen state is NOT protected: a
    draft record's state is not frozen, so any user can RPC
    ``write({'state': 'posted'})`` straight past ``action_post`` and its
    checks and journal entry. This mixin blocks EVERY non-superuser write to
    a guarded field. Record actions prove provenance through the capability
    helpers below, which validate access before elevating the exact recordset.

eh.post.once
    Nothing stopped the same source record/period being posted by two
    different runs, so variances, eliminations and reclasses could be
    double-booked. This mixin gives a one-line idempotency assertion:
    refuse to post a source already consumed by another posted record.

eh.gl.reversal
    Reversal entries were created but never re-sealed, so the frozen-figure
    guarantee held on the original move but was breakable on the reversal.
    This mixin reverses a sealed move AND re-seals the reversal.
"""

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError
from odoo.tools import SQL


class EhWorkflowGuard(models.AbstractModel):
    """Block direct RPC/ORM writes to workflow-critical fields.

    Concrete models add ``'eh.workflow.guard'`` to ``_inherit`` and declare
    ``_eh_guarded_fields``. Every state-changing action must wrap its write
    with :meth:`_eh_workflow_write` or start with
    ``self = self._eh_workflow_action()``. Both helpers check the original
    actor's access before elevating the exact recordset.
    """

    _name = 'eh.workflow.guard'
    _description = "Workflow state-write guard"

    # Fields that may only change through the record's own actions, never a
    # direct write. Override per model (as a tuple) to widen, e.g.
    # ('state', 'current_step', 'submitted_amount').
    _eh_guarded_fields = ('state',)
    # Fields stripped from a non-superuser CREATE (a record must not be born
    # in a guarded state). Defaults to _eh_guarded_fields. A model whose
    # write-guard covers identity fields that ARE legitimately set at create
    # (e.g. a request's move_id/policy_id/rule_id) narrows this to just the
    # state-machine fields so creation still works while repointing-by-write
    # stays blocked.
    _eh_create_guarded_fields = None

    @api.model
    def default_get(self, fields_list):
        """Ignore RPC/ir.default attempts to seed workflow evidence."""
        defaults = super().default_get(fields_list)
        if self.env.su:
            return defaults
        guarded = set(
            self._eh_create_guarded_fields
            if self._eh_create_guarded_fields is not None
            else self._eh_guarded_fields
        ).intersection(fields_list)
        for field_name in guarded:
            field = self._fields.get(field_name)
            if field and field.default:
                defaults[field_name] = field.default(self)
            else:
                defaults.pop(field_name, None)
        return defaults

    @api.model_create_multi
    def create(self, vals_list):
        # Close the create-side bypass: a low-privilege user must not be able
        # to make a record BORN in a guarded state (e.g.
        # create({'state': 'approved'}) to skip the whole workflow). A plain
        # non-superuser create gets its guarded fields stripped so the model
        # default applies; the record then starts at its initial state and can
        # only advance through the sanctioned actions (which run under sudo).
        #
        # SECURITY: provenance is proven by env.su, NOT a context flag. Odoo
        # passes client-supplied context straight into call_kw, so any context
        # sentinel (the old 'eh_workflow_action' key) is forgeable by the
        # client and provides no real protection.
        if not self.env.su:
            guarded = set(self._eh_create_guarded_fields
                          if self._eh_create_guarded_fields is not None
                          else self._eh_guarded_fields)
            vals_list = [
                {k: v for k, v in (vals or {}).items() if k not in guarded}
                for vals in vals_list
            ]
            guarded_defaults = {'default_%s' % name for name in guarded}
            create_context = {
                key: value for key, value in self.env.context.items()
                if key not in guarded_defaults
            }
            create_self = self.with_context(create_context)
            return super(EhWorkflowGuard, create_self).create(vals_list)
        return super().create(vals_list)

    def write(self, vals):
        # Guarded (state/workflow) fields may only be written by the record's
        # own actions, which run under sudo (env.su). A direct non-superuser
        # write is refused. Provenance is env.su, not a context flag, for the
        # forgeability reason documented on create().
        if not self.env.su:
            blocked = set(vals) & set(self._eh_guarded_fields)
            if blocked:
                raise AccessError(_(
                    "%(model)s: fields %(fields)s can only change through "
                    "the record's own actions, not a direct write. Use the "
                    "provided buttons/methods.",
                    model=self._description,
                    fields=', '.join(sorted(blocked)),
                ))
        return super().write(vals)

    def _eh_workflow_write(self, vals):
        """Write guarded fields after proving caller may mutate records.

        Public workflow methods can call this helper directly. Elevating
        before checking the original recordset would let a caller guess an
        id hidden by a company rule and mutate it as superuser. Internal
        calls from an already elevated sanctioned action remain valid.
        """
        if not self.env.su:
            self._eh_check_access('write')
        return self.sudo().write(vals)

    def _eh_workflow_action(self):
        """Return an su recordset for a state-changing action.

        Use at the top of an action:  ``self = self._eh_workflow_action()``
        so subsequent ``rec.state = ...`` assignments (and any helper the
        recordset calls) write past the guard. Original caller's write ACL
        and record rules are checked before elevation. ``sudo`` then only
        proves the guarded write is server-initiated and keeps real env.user
        for audit stamps.
        """
        if not self.env.su:
            self._eh_check_access('write')
        return self.sudo()


class EhPostOnce(models.AbstractModel):
    """Idempotency helper: a source may be booked to the ledger only once."""

    _name = 'eh.post.once'
    _description = "Post-once idempotency helper"

    @api.model
    def _eh_lock_post_once_sources(self, source_field, source_ids):
        """Serialize one posting action for each source id.

        Transaction advisory locks cover the gap between duplicate check and
        final state write.  Keys include model, action field, and target, but
        deliberately not actor: two different users posting the same target
        must contend on the same lock.
        """
        lock_names = tuple(
            "%s:post-once:%s:%d" % (self._name, source_field, source_id)
            for source_id in sorted({int(i) for i in source_ids})
        )
        for lock_name in lock_names:
            self.env.cr.execute(
                "SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))",
                [lock_name],
            )
        return lock_names

    def _eh_assert_source_unposted(self, source_field, posted_states=('posted',),
                                   state_field='state'):
        """Refuse if another posted record already consumed the same source.

        :param source_field: name of the x2many/x2one field carrying the
            source records this run posts (e.g. 'actual_ids').
        :param posted_states: states that count as already-booked.
        :param state_field: the state field name on this model.
        """
        self.ensure_one()
        source = self[source_field]
        source_ids = source.ids if hasattr(source, 'ids') else [source.id]
        if not source_ids:
            return
        self._eh_lock_post_once_sources(source_field, source_ids)
        # Lock authoritative source rows as well. This prevents a concurrent
        # source mutation from changing posting inputs after idempotency was
        # proven. Identifier composition is SQL-safe and the ids are already
        # normalized integers above.
        source = source.sudo()
        source.flush_recordset()
        self.env.cr.execute(
            SQL(
                "SELECT id FROM %s WHERE id IN %s ORDER BY id FOR UPDATE",
                SQL.identifier(source._table),
                tuple(sorted({int(i) for i in source_ids})),
            )
        )
        dup = self.sudo().with_context(active_test=False).search([
            (state_field, 'in', list(posted_states)),
            ('id', '!=', self.id),
            (source_field, 'in', source_ids),
        ], limit=5)
        if dup:
            raise UserError(_(
                "The source records were already booked by another posting. "
                "A period/source can only be posted once; reverse the "
                "existing posting first."
            ))


class EhGlReversal(models.AbstractModel):
    """Reverse a sealed journal entry AND re-seal the reversal.

    eh_account_base seals posted moves (eh_sealed) so their figures freeze.
    Reversals must be sealed too, or the frozen-figure guarantee is
    breakable on the reversal side.
    """

    _name = 'eh.gl.reversal'
    _description = "GL reversal + re-seal helper"

    def _eh_seal_reversal(self, reversal_moves):
        """Seal already-created reversal move(s) so they are as immutable as
        the sealed entry they unwind.

        Drop-in for adopters that keep their own ``_reverse_moves`` call: it
        adds the seal (closing the "reversal side stays editable" gap) without
        changing the reversal's own dating / cancel / reconciliation
        semantics. Idempotent; a no-op on moves that lack eh_sealed or are
        already sealed.
        """
        if not reversal_moves:
            return reversal_moves
        for reversal in reversal_moves:
            if not reversal.reversed_entry_id:
                raise UserError(_(
                    "A sealed reversal must retain its exact original-entry "
                    "link."
                ))
            reversal._eh_validate_verified_reversal(
                reversal.reversed_entry_id,
            )
        sealable = reversal_moves.filtered(
            lambda m: 'eh_sealed' in m._fields and not m.eh_sealed)
        if sealable:
            sealable._eh_stamp_verified_seal()
        return reversal_moves

    def _eh_reverse_sealed_move(self, move, date=None, ref=None, cancel=True):
        """Reverse a (possibly sealed) move and seal the reversal.

        Returns the reversal move(s). ``cancel=True`` posts the reversal and
        reconciles it flat against the original.
        """
        if not move:
            return move.browse()
        reversal = move._eh_reverse_with_verified_capability([{
            'date': date or fields.Date.context_today(self),
            'ref': ref or _("Reversal of %s", move.name or move.display_name),
        }], cancel=cancel)
        return self._eh_seal_reversal(reversal)
