# -*- coding: utf-8 -*-
from odoo import api, fields, models, tools, _
from odoo.exceptions import UserError


class WujiaFieldTrackingConfig(models.Model):
    _name = 'wujia.field.tracking.config'
    _description = 'Dynamic Field Tracking Configuration'
    _rec_name = 'model_name'
    _order = 'model_name'

    model_id = fields.Many2one(
        'ir.model',
        string='Model',
        required=True,
        ondelete='cascade',
        domain=[('is_mail_thread', '=', True)],
        index=True,
        help='Select a model that inherits from mail.thread and supports chatter tracking.',
    )
    model_name = fields.Char(
        string='Model Technical Name',
        related='model_id.model',
        store=True,
        index=True,
    )
    active = fields.Boolean(
        string='Active',
        default=True,
        help='Enable or disable tracking rules for this model.',
    )
    line_ids = fields.One2many(
        'wujia.field.tracking.line',
        'config_id',
        string='Tracked Fields Configuration',
        copy=True,
    )
    tracked_count = fields.Integer(
        string='Tracked Fields Count',
        compute='_compute_tracked_count',
        store=True,
    )


    _sql_constraints = [
        ('model_id_unique', 'unique(model_id)', 'Tracking configuration for this model already exists!')
    ]

    @api.depends('line_ids.is_tracked')
    def _compute_tracked_count(self):
        for rec in self:
            rec.tracked_count = len(rec.line_ids.filtered(lambda l: l.is_tracked))

    UNSUPPORTED_TRACKING_TTYPES = ['binary', 'reference', 'json']

    def action_fetch_model_fields(self):
        """Fetch all eligible fields from ir.model.fields for the selected model, excluding binary/unsupported types."""
        self.ensure_one()
        if not self.model_id:
            raise UserError(_("Please select a model first!"))

        # Remove any legacy lines with unsupported field types (e.g. binary, signatures, files)
        unsupported_lines = self.line_ids.filtered(lambda l: l.ttype in self.UNSUPPORTED_TRACKING_TTYPES)
        if unsupported_lines:
            unsupported_lines.unlink()

        existing_field_ids = self.line_ids.mapped('field_id.id')
        fields_to_add = self.env['ir.model.fields'].search([
            ('model_id', '=', self.model_id.id),
            ('name', 'not in', ['id', 'create_uid', 'create_date', 'write_uid', 'write_date', '__last_update']),
            ('ttype', 'not in', self.UNSUPPORTED_TRACKING_TTYPES),
            ('id', 'not in', existing_field_ids),
        ])

        new_lines = []
        model_pool = self.env.get(self.model_name)
        for field in fields_to_add:
            is_code_tracked = False
            if model_pool and field.name in model_pool._fields:
                field_obj = model_pool._fields[field.name]
                is_code_tracked = bool(getattr(field_obj, 'tracking', False))

            new_lines.append((0, 0, {
                'field_id': field.id,
                'is_tracked': is_code_tracked,
                'is_code_tracked': is_code_tracked,
            }))

        if new_lines:
            self.write({'line_ids': new_lines})
        self._clear_tracking_cache()
        return True

    def action_enable_all_tracking(self):
        """Enable tracking for all fields in the list."""
        self.ensure_one()
        self.line_ids.write({'is_tracked': True})
        self._clear_tracking_cache()
        return True

    def action_disable_all_tracking(self):
        """Disable tracking for all fields in the list."""
        self.ensure_one()
        self.line_ids.write({'is_tracked': False})
        self._clear_tracking_cache()
        return True

    @tools.ormcache('model_name')
    def _get_tracked_fields_cache(self, model_name):
        """Retrieve active tracked field names from DB with high-performance RAM caching."""
        config = self.sudo().search([
            ('model_name', '=', model_name),
            ('active', '=', True)
        ], limit=1)
        if not config:
            return set()
        return set(
            config.line_ids.filtered(
                lambda l: l.is_tracked and l.ttype not in ['binary', 'reference', 'json']
            ).mapped('field_name')
        )

    def _clear_tracking_cache(self):
        self.env.registry.clear_cache()

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records._clear_tracking_cache()
        return records

    def write(self, vals):
        res = super().write(vals)
        self._clear_tracking_cache()
        return res

    def unlink(self):
        self._clear_tracking_cache()
        return super().unlink()
