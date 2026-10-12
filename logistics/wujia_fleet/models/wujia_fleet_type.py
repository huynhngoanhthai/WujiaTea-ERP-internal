from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class WujiaFleetType(models.Model):
    _name = 'wujia.fleet.type'
    _description = 'Wujia Fleet Type'
    _order = 'sequence, payload_capacity_ton, name'

    name = fields.Char(
        string='Vehicle type name',
        required=True,
        translate=True,
        help='e.g. "1.9T truck", "17T refrigerated truck".',
    )
    code = fields.Char(string='Vehicle type code', index=True)
    sequence = fields.Integer(default=10)
    vehicle_category = fields.Selection(
        [
            ('truck', 'Truck'),
            ('pickup', 'Pickup'),
            ('van', 'Van'),
            ('other', 'Other'),
        ],
        string='Vehicle group',
        required=True,
        default='truck',
    )
    payload_capacity_ton = fields.Float(
        string='Payload (tons)',
        required=True,
        default=0.0,
        digits=(10, 2),
    )
    max_payload_kg = fields.Float(
        string='Maximum payload (kg)',
        compute='_compute_max_payload_kg',
        store=True,
        digits='Stock Weight',
        help="= payload_capacity_ton × 1000. Used to compare against planned_weight for the batch overload warning.",
    )
    description = fields.Text(string='Description')

    _code_uniq = models.Constraint(
        'UNIQUE (code)',
        'Vehicle type code must be unique.',
    )

    @api.depends('payload_capacity_ton')
    def _compute_max_payload_kg(self):
        for rec in self:
            rec.max_payload_kg = (rec.payload_capacity_ton or 0.0) * 1000.0

    @api.constrains('payload_capacity_ton')
    def _check_payload(self):
        for rec in self:
            if rec.payload_capacity_ton < 0:
                raise ValidationError(_("Capacity must be >= 0."))
