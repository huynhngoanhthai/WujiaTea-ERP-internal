from odoo import fields, models


class WujiaSupportCategory(models.Model):
    _name = 'wujia.support.category'
    _description = 'Wujia Support Category'
    _order = 'sequence, name'

    name = fields.Char(string='Name', required=True, translate=True)
    code = fields.Char(string='Code', help='Short slug, e.g. order, delivery.')
    description = fields.Text(string='Description', translate=True)
    default_assigned_user_id = fields.Many2one(
        'res.users', string='Default assignee',
        domain="[('share', '=', False)]",
    )
    default_assigned_team_id = fields.Many2one(
        'crm.team', string='Default team',
    )
    sequence = fields.Integer(string='Sequence', default=10)
    active = fields.Boolean(string='Active', default=True)

    _sql_constraints = [
        ('uniq_name', 'unique(name)', 'Category name must be unique.'),
        ('uniq_code', 'unique(code)', 'Category code must be unique.'),
    ]
