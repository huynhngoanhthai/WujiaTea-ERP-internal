from odoo import fields, models


class WujiaNotificationType(models.Model):
    """Master data — loại thông báo (Khẩn, Thông báo, Khuyến mãi, ...).

    Đóng vai `wujia.announcement.category` trong BA spec phần F §6."""

    _name = 'wujia.notification.type'
    _description = 'Wujia Notification Type'
    _order = 'sequence, code'

    name = fields.Char(string='Type name', required=True, translate=True)
    code = fields.Char(string='Type code', required=True)
    description = fields.Text(string='Description')
    bg_color = fields.Char(string='Background colour', default='#1f4180')
    text_color = fields.Char(string='Text colour', default='#ffffff')
    icon = fields.Char(string='Icon (FontAwesome)', default='fa-bell')
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    notification_count = fields.Integer(
        string='Notification count', compute='_compute_notification_count',
    )

    _uniq_code = models.Constraint(
        'unique(code)',
        'The notification type code must be unique.',
    )

    def _compute_notification_count(self):
        """1 read_group cho cả recordset — tránh N query khi mở danh sách loại."""
        counts = {}
        if self.ids:
            counts = {
                type_.id: count
                for type_, count in self.env['wujia.notification'].sudo()._read_group(
                    [('type_id', 'in', self.ids)],
                    groupby=['type_id'], aggregates=['__count'],
                )
            }
        for rec in self:
            rec.notification_count = counts.get(rec.id, 0)

    def action_view_notifications(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': self.name,
            'res_model': 'wujia.notification',
            'view_mode': 'list,form',
            'domain': [('type_id', '=', self.id)],
            'context': {'default_type_id': self.id},
        }
