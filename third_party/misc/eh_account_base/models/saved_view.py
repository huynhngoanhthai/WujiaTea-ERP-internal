# -*- encoding: utf-8 -*-
##############################################################################
#
# ERP Heritage
# Copyright (C) 2026 (https://www.erpheritage.com.au/)
#
##############################################################################
"""
Saved filter views for dynamic reports.

A user picks dimensions and date settings on the OWL viewer, names them,
and reuses the named bundle on the next render. Visibility is per user
by default; a sharing toggle promotes the view to company-wide so a
finance team can publish a "month-end pack" to every member.

The options field stores the OWL viewer's `state.options` block as JSON.
The OWL viewer reads it back verbatim into state on load. Schema drift
between viewer revisions does not corrupt the stored bundle: unknown
keys are ignored on load and missing keys fall back to defaults.
"""

import json

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError


def _reject_non_json_constant(value):
    """Make Python's permissive JSON decoder obey the JSON specification."""
    raise ValueError("non-finite JSON constant: %s" % value)


class EhReportSavedView(models.Model):
    _name = 'eh.account.report.saved_view'
    _description = "Saved filter view for a dynamic report"
    _order = 'shared desc, name'
    _rec_name = 'name'

    name = fields.Char(required=True)
    report_code = fields.Char(required=True, index=True)
    user_id = fields.Many2one(
        'res.users',
        default=lambda self: self.env.user,
        ondelete='set null',
        index=True,
        readonly=True,
        help=(
            "Owner of the view. Shared definitions survive owner removal "
            "with an empty owner; private definitions then become visible "
            "only to administrators until reviewed or reassigned."
        ),
    )
    company_id = fields.Many2one(
        'res.company',
        default=lambda self: self.env.company,
        index=True,
        readonly=True,
    )
    options_json = fields.Text(
        required=True,
        help="JSON-encoded options dict as captured from the OWL viewer.",
    )
    shared = fields.Boolean(
        default=False,
        help=(
            "When True, the view is visible to every user in the company "
            "with access to the report. The owner remains the only user "
            "who can edit or delete."
        ),
    )
    notes = fields.Char()

    _unique_per_user_code = models.Constraint(
        'unique(user_id, report_code, name)',
        'A user cannot save two views with the same name on the same report.',
    )

    @api.constrains('options_json')
    def _check_options_json(self):
        for rec in self:
            if not rec.options_json:
                raise ValidationError(_("options_json must not be empty."))
            try:
                payload = json.loads(
                    rec.options_json,
                    parse_constant=_reject_non_json_constant,
                )
            except ValueError as exc:
                raise ValidationError(_(
                    "options_json must be valid JSON (got %s).",
                ) % exc)
            if not isinstance(payload, dict):
                raise ValidationError(_("options_json must encode a dict."))

    @api.model_create_multi
    def create(self, vals_list):
        """Stamp the caller as owner and freeze the company boundary.

        Data loading and explicitly trusted server code may use ``sudo`` to
        preserve a supplied owner/company.  An ordinary RPC caller cannot
        manufacture a row owned by somebody else (or place it in another
        company) and then exploit the shared-read rule.
        """
        secured_vals_list = []
        for incoming_vals in vals_list:
            vals = dict(incoming_vals)
            if not self.env.su:
                if (
                    'user_id' in vals
                    and (vals.get('user_id') or False) != self.env.uid
                ):
                    raise AccessError(_(
                        "A saved view can only be created for the current "
                        "user."
                    ))
                if (
                    'company_id' in vals
                    and (vals.get('company_id') or False)
                    != self.env.company.id
                ):
                    raise AccessError(_(
                        "A saved view can only be created in the current "
                        "company."
                    ))
                vals['user_id'] = self.env.uid
                vals['company_id'] = self.env.company.id
            else:
                vals.setdefault('user_id', self.env.uid)
                vals.setdefault('company_id', self.env.company.id)
            secured_vals_list.append(vals)
        return super().create(secured_vals_list)

    def _check_owner_mutation(self):
        """Reject mutations of shared rows by their non-owner readers."""
        if self.env.su:
            return
        foreign = self.filtered(lambda rec: rec.user_id.id != self.env.uid)
        if foreign:
            raise AccessError(_(
                "Only the owner can modify or delete a saved view."
            ))

    def write(self, vals):
        self._check_owner_mutation()
        for rec in self:
            if (
                'user_id' in vals
                and (vals.get('user_id') or False) != rec.user_id.id
            ):
                raise AccessError(_("A saved view's owner is immutable."))
            if (
                'company_id' in vals
                and (vals.get('company_id') or False) != rec.company_id.id
            ):
                raise AccessError(_("A saved view's company is immutable."))
        return super().write(vals)

    def unlink(self):
        self._check_owner_mutation()
        return super().unlink()

    @api.model
    def list_for(self, report_code):
        """Return saved views the current user can see for the report.

        Includes the user's own views plus any view shared in the active
        company. Result is a list of dicts keyed by id, name, shared,
        owned (whether the active user is the owner).
        """
        domain = [
            ('report_code', '=', report_code),
            '|',
            ('user_id', '=', self.env.user.id),
            '&',
            ('shared', '=', True),
            ('company_id', 'in', list(
                self.env.context.get(
                    'allowed_company_ids', [self.env.company.id],
                ),
            )),
        ]
        records = self.search(domain, order='shared desc, name')
        return [{
            'id': r.id,
            'name': r.name,
            'shared': r.shared,
            'owned': r.user_id.id == self.env.user.id,
            'notes': r.notes or '',
        } for r in records]

    @api.model
    def save_view(self, name, report_code, options, shared=False, notes=None):
        """Upsert a saved view. The (user, report_code, name) tuple is
        unique, so saving the same name overwrites the prior bundle.

        Returns the persisted record id.
        """
        if not isinstance(options, dict):
            raise UserError(_("Saved view options must be a JSON object."))
        try:
            encoded_options = json.dumps(
                options,
                sort_keys=True,
                allow_nan=False,
            )
        except (TypeError, ValueError) as exc:
            raise UserError(_(
                "Saved view options must be JSON serialisable."
            )) from exc
        existing = self.search([
            ('user_id', '=', self.env.user.id),
            ('report_code', '=', report_code),
            ('name', '=', name),
        ], limit=1)
        vals = {
            'name': name,
            'report_code': report_code,
            'options_json': encoded_options,
            'shared': bool(shared),
            'notes': notes or False,
        }
        if existing:
            existing.write(vals)
            return existing.id
        return self.create(vals).id

    def load_options(self):
        """Return the parsed options dict for the OWL viewer."""
        self.ensure_one()
        try:
            payload = json.loads(
                self.options_json,
                parse_constant=_reject_non_json_constant,
            )
        except (TypeError, ValueError) as exc:
            raise UserError(_(
                "Saved view '%s' contains malformed JSON options.",
                self.name,
            )) from exc
        if not isinstance(payload, dict):
            raise UserError(_(
                "Saved view '%s' options must be a JSON object.",
                self.name,
            ))
        return payload
