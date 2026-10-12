from odoo import _, api, fields, models


class ResArea(models.Model):
    _name = 'res.area'
    _description = 'Sales / Operation Area'
    _order = 'sequence, code, name'
    _rec_name = 'name'

    code = fields.Char(string='Area code', required=True, help='e.g. KV-HCM-01.')
    name = fields.Char(string='Area name', required=True, translate=True)
    sequence = fields.Integer(default=10)
    manager_user_id = fields.Many2one(
        'res.users',
        string='Person in charge',
        help='Person responsible for running this area.',
    )
    ward_ids = fields.Many2many(
        'res.ward',
        'res_area_ward_rel',
        'area_id',
        'ward_id',
        string='Wards',
        help='Wards belonging to this area — picked from the res.ward catalog.',
    )
    state_ids = fields.Many2many(
        'res.country.state',
        string='Province',
        compute='_compute_state_ids',
        store=True,
        help='Provinces aggregated from the wards of this area — updated automatically.',
    )
    description = fields.Text(string='Area scope description')
    note = fields.Text(string='Internal note')
    active = fields.Boolean(default=True)

    _code_uniq = models.Constraint(
        'UNIQUE (code)',
        'Area code must be unique.',
    )

    @api.depends('ward_ids.state_id')
    def _compute_state_ids(self):
        for rec in self:
            rec.state_ids = rec.ward_ids.mapped('state_id')

    def action_view_wards(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Wards of %s', self.name),
            'res_model': 'res.ward',
            'view_mode': 'list,form',
            'domain': [('id', 'in', self.ward_ids.ids)],
        }
