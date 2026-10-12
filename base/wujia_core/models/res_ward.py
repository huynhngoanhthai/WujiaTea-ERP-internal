from odoo import fields, models


class ResWard(models.Model):
    _name = 'res.ward'
    _description = 'Ward'
    _order = 'state_id, name'
    _rec_name = 'name'

    name = fields.Char(string='Ward name', required=True)
    code = fields.Char(string='Ward code', required=True, help='Administrative code, e.g. 27001.')
    state_id = fields.Many2one(
        'res.country.state',
        string='Province',
        required=True,
        ondelete='restrict',
        index=True,
    )
    country_id = fields.Many2one(
        'res.country',
        string='Country',
        related='state_id.country_id',
        store=True,
        readonly=True,
    )
    active = fields.Boolean(default=True)

    _code_state_uniq = models.Constraint(
        'UNIQUE (state_id, code)',
        'Ward code must be unique within each province.',
    )
