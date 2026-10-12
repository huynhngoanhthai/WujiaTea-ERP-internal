# -*- coding: utf-8 -*-
from odoo import api, fields, models


class WujiaFieldTrackingLine(models.Model):
    _name = 'wujia.field.tracking.line'
    _description = 'Dynamic Field Tracking Line'
    _order = 'is_tracked desc, field_name asc'

    config_id = fields.Many2one(
        'wujia.field.tracking.config',
        string='Tracking Configuration',
        required=True,
        ondelete='cascade',
        index=True,
    )
    field_id = fields.Many2one(
        'ir.model.fields',
        string='Field',
        required=True,
        ondelete='cascade',
    )
    field_name = fields.Char(
        string='Technical Name',
        related='field_id.name',
        store=True,
        index=True,
    )
    field_description = fields.Char(
        string='Field Label',
        related='field_id.field_description',
    )
    ttype = fields.Selection(
        related='field_id.ttype',
        string='Data Type',
    )
    is_tracked = fields.Boolean(
        string='Enable Tracking',
        default=False,
        help='Check to enable chatter tracking for this field.',
    )
    is_code_tracked = fields.Boolean(
        string='Tracked in Python Code',
        readonly=True,
        help='Indicates if this field is already declared with tracking=True in Python source code.',
    )
    sequence = fields.Integer(
        string='Sequence',
        default=10,
    )

    _sql_constraints = [
        ('config_field_unique', 'unique(config_id, field_id)', 'This field is already added to the tracking configuration!')
    ]

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        self.env.registry.clear_cache()
        return records

    def write(self, vals):
        res = super().write(vals)
        if 'is_tracked' in vals:
            self.env.registry.clear_cache()
        return res

    def unlink(self):
        self.env.registry.clear_cache()
        return super().unlink()
