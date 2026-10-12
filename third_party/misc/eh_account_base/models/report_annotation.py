# -*- encoding: utf-8 -*-
##############################################################################
#
# ERP Heritage
# Copyright (C) 2026 (https://www.erpheritage.com.au/)
#
##############################################################################
"""
eh.account.report.annotation: a note pinned to a cell or row of a
dynamic financial report.

Annotations attach by (report_code, line_id, expression_label): the
orchestrator injects them into the rendered payload after the figures
are computed, so a note follows its line wherever the report is run and
is never baked into the cached result. expression_label empty annotates
the whole row; set it to a column label (e.g. 'amount') to annotate a
single cell.
"""

from odoo import _, api, fields, models
from odoo.exceptions import AccessError


class EhAccountReportAnnotation(models.Model):
    _name = 'eh.account.report.annotation'
    _description = "Dynamic report annotation"
    _order = 'create_date desc, id desc'

    report_code = fields.Char(required=True, index=True)
    line_id = fields.Char(
        required=True, index=True,
        help="Id of the report line the note attaches to "
             "(e.g. 'account-5', 'net_profit').",
    )
    expression_label = fields.Char(
        help="Column label to pin the note to a single cell; empty "
             "annotates the whole row.",
    )
    text = fields.Text(required=True)
    company_id = fields.Many2one(
        'res.company', required=True, index=True,
        default=lambda self: self.env.company,
    )

    @api.model_create_multi
    def create(self, vals_list):
        # create_uid/create_date are the evidentiary author stamp.  They are
        # server-owned even for managers and sudo callers; importing a note
        # must never allow the author to be manufactured through ORM vals.
        for vals in vals_list:
            if {'create_uid', 'create_date'} & set(vals):
                raise AccessError(_(
                    "An annotation's author and creation date are "
                    "server-managed."
                ))
        return super().create(vals_list)

    def write(self, vals):
        if {'create_uid', 'create_date'} & set(vals):
            raise AccessError(_(
                "An annotation's author and creation date are immutable."
            ))
        if (
            not self.env.su
            and not self.env.user.has_group(
                'eh_account_base.group_eh_manager'
            )
        ):
            raise AccessError(_(
                "Annotations are append-only for accounting users; only "
                "an accounting manager can correct one."
            ))
        return super().write(vals)

    def unlink(self):
        if (
            not self.env.su
            and not self.env.user.has_group(
                'eh_account_base.group_eh_manager'
            )
        ):
            raise AccessError(_(
                "Only an accounting manager can delete an annotation."
            ))
        return super().unlink()
