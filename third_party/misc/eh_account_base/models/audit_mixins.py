# -*- encoding: utf-8 -*-
##############################################################################
#
# ERP Heritage
# Copyright (C) 2026 (https://www.erpheritage.com.au/)
#
##############################################################################
"""
Shared mixins for the ERP Heritage accounting suite.

eh.audit.mixin
    The append-only audit-row behaviour that every per-action log model
    in the suite repeated by hand: an actor field defaulting to the
    current user, a free-form comment that stays writable, a frozen
    create timestamp, a write guard that blocks edits to anything but
    the configured writable fields, and an unlink guard that refuses
    deletion outright. Concrete logs inherit this and add only their own
    domain columns (the move, the request, the action selection, etc.).

eh.cron.batch.mixin
    The per-record savepoint loop that every resilient cron repeated by
    hand: process each record in its own savepoint so one record's
    failure rolls back only that record and never aborts the whole
    batch, log the failure, and carry on. Returns the failures so the
    caller can park records or report counts.
"""

import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError


_logger = logging.getLogger(__name__)


class EhAuditMixin(models.AbstractModel):
    _name = 'eh.audit.mixin'
    _description = "Append-only audit row"
    _order = 'create_date desc, id desc'

    # Fields a concrete log lets change after the row exists. Everything
    # else is frozen once created. Override (as a tuple) to widen, e.g.
    # a reviewer model that keeps a 'resolution' field editable.
    _eh_audit_writable_fields = ('comment',)
    # Message raised when something tries to delete an audit row.
    # Override per model to point the operator at the right corrective
    # action instead of the generic line.
    _eh_audit_unlink_message = (
        "Audit log rows cannot be deleted; they are an immutable trail. "
        "Reverse or void the underlying action instead."
    )

    user_id = fields.Many2one(
        'res.users', required=True, index=True,
        default=lambda self: self.env.user,
        string="Actor",
        help="User who performed the action this row records.",
    )
    comment = fields.Text(
        help=(
            "Free-form note. The only field that stays writable after "
            "the row is created."
        ),
    )
    create_date = fields.Datetime(readonly=True)

    def write(self, vals):
        forbidden = set(vals) - set(self._eh_audit_writable_fields)
        if forbidden:
            raise UserError(_(
                "%(model)s rows are append-only. Fields blocked: "
                "%(fields)s",
                model=self._description,
                fields=', '.join(sorted(forbidden)),
            ))
        return super().write(vals)

    @api.ondelete(at_uninstall=False)
    def _eh_audit_block_unlink(self):
        raise UserError(self._eh_audit_unlink_message)


class EhCronBatchMixin(models.AbstractModel):
    _name = 'eh.cron.batch.mixin'
    _description = "Per-record savepoint batch helper"

    def _eh_for_each_savepoint(self, records, func, on_error=None,
                               log_label=None):
        """Run func(record) on each record inside its own savepoint.

        A single record's failure rolls back only that record's writes
        and never aborts the rest of the batch: without the per-record
        savepoint, one exception leaves the cursor in an aborted state
        and every later record in the run fails too.

        :param records: recordset to iterate.
        :param func: callable taking one record. Its work is what the
            savepoint isolates.
        :param on_error: optional callable(record, exception) run AFTER
            the savepoint rolled back, in the live transaction, e.g. to
            park the failing record with the captured error. An error
            raised by on_error is logged and swallowed so it cannot,
            in turn, abort the batch.
        :param log_label: short label for the warning line; defaults to
            the model description.
        :returns: list of (record_id, exception) for the records that
            failed, in iteration order.
        """
        label = log_label or self._description or self._name
        failures = []
        for record in records:
            try:
                with self.env.cr.savepoint():
                    func(record)
            except Exception as exc:  # noqa: BLE001
                _logger.warning(
                    "%s: batch step failed for %s: %s",
                    label, record.display_name, exc,
                )
                failures.append((record.id, exc))
                if on_error is not None:
                    try:
                        with self.env.cr.savepoint():
                            on_error(record, exc)
                    except Exception as exc2:  # noqa: BLE001
                        _logger.error(
                            "%s: error handler also failed for %s: %s",
                            label, record.display_name, exc2,
                        )
        return failures
