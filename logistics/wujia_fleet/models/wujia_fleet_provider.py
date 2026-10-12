import re

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


EMAIL_RE = re.compile(r'^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$')


class WujiaFleetProvider(models.Model):
    _name = 'wujia.fleet.provider'
    _description = 'Wujia Fleet Provider'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'name'

    name = fields.Char(
        string='Carrier name',
        required=True,
        tracking=True,
        help='Carrier name, e.g. "Nguyen Dung Transport Co., Ltd".',
    )
    code = fields.Char(
        string='Carrier code',
        tracking=True,
        index=True,
        help='Short code used for lookup, e.g. NDUNG, AHOO.',
    )
    partner_id = fields.Many2one(
        'res.partner',
        string='Partner',
        ondelete='restrict',
        tracking=True,
        help="Link to the Odoo contact / vendor when the carrier is a supplier and a PO has to be issued.",
    )
    provider_type = fields.Selection(
        [
            ('company', 'Company-owned'),
            ('outsource', 'Outsourced'),
        ],
        string='Carrier type',
        required=True,
        default='outsource',
        tracking=True,
        index=True,
    )
    description = fields.Text(string='Description')
    contact_name = fields.Char(string='Contact person')
    phone = fields.Char(string='Phone')
    email = fields.Char(string='Email')

    vehicle_ids = fields.One2many(
        'wujia.fleet.management',
        'provider_id',
        string='Vehicles',
    )
    vehicle_count = fields.Integer(
        string='Vehicle count',
        compute='_compute_vehicle_count',
        store=True,
        compute_sudo=True,
    )

    active = fields.Boolean(default=True)

    _code_uniq = models.Constraint(
        'UNIQUE (code)',
        'Fleet code must be unique.',
    )

    @api.depends('vehicle_ids.active')
    def _compute_vehicle_count(self):
        for rec in self:
            rec.vehicle_count = len(rec.vehicle_ids.filtered('active'))

    @api.constrains('email')
    def _check_email_format(self):
        for rec in self:
            if rec.email and not EMAIL_RE.match(rec.email):
                raise ValidationError(_("Email '%s' has an invalid format.", rec.email))

    def action_view_vehicles(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Vehicles of %s', self.name),
            'res_model': 'wujia.fleet.management',
            'view_mode': 'list,kanban,form',
            'domain': [('provider_id', '=', self.id)],
            'context': {'default_provider_id': self.id},
        }
