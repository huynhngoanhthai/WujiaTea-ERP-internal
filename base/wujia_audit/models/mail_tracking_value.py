# -*- coding: utf-8 -*-
from odoo import api, fields, models


class MailTrackingValue(models.Model):
    _inherit = 'mail.tracking.value'

    author_id = fields.Many2one(
        'res.partner',
        string='Performed By',
        related='mail_message_id.author_id',
        store=True,
        index=True,
        help='Partner/User who performed this modification.',
    )
    date = fields.Datetime(
        string='Date',
        related='mail_message_id.date',
        store=True,
        index=True,
        help='Date and time when this modification was made.',
    )
    record_name = fields.Char(
        string='Target Record',
        related='mail_message_id.record_name',
        store=True,
        help='Name of the modified document or record.',
    )

    @api.model
    def _create_tracking_values(self, initial_value, new_value, col_name, col_info, record):
        """Override to gracefully handle binary/unsupported field types without raising NotImplementedError."""
        if col_info.get('type') == 'binary':
            field = self.env['ir.model.fields']._get(record._name, col_name)
            if not field:
                raise ValueError(f'Unknown field {col_name} on model {record._name}')

            old_str = self.env._('Attached / Signed') if initial_value else self.env._('Empty')
            new_str = self.env._('Attached / Signed') if new_value else self.env._('Empty')
            if initial_value and new_value:
                new_str = self.env._('Updated')

            return {
                'field_id': field.id,
                'old_value_char': old_str,
                'new_value_char': new_str,
            }

        try:
            return super()._create_tracking_values(initial_value, new_value, col_name, col_info, record)
        except NotImplementedError:
            field = self.env['ir.model.fields']._get(record._name, col_name)
            return {
                'field_id': field.id if field else False,
                'old_value_char': str(initial_value)[:128] if initial_value else '',
                'new_value_char': str(new_value)[:128] if new_value else '',
            }
