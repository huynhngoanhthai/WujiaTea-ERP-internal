from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


PRICELIST_STATE = [
    ('draft', 'Draft'),
    ('active', 'In effect'),
    ('expired', 'Expired'),
    ('archived', 'Archived'),
]


class WujiaFleetPricelist(models.Model):
    _name = 'wujia.fleet.pricelist'
    _description = 'Wujia Fleet Pricelist'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'sequence, date_from desc, id desc'

    name = fields.Char(string='Pricelist name', required=True, tracking=True)
    code = fields.Char(string='Pricelist code', index=True)
    sequence = fields.Integer(
        string='Priority',
        default=10,
        help='A lower number means higher priority when several pricelists match.',
    )

    fleet_type_id = fields.Many2one(
        'wujia.fleet.type',
        string='Vehicle type',
        required=True,
        ondelete='restrict',
        tracking=True,
        index=True,
    )
    provider_id = fields.Many2one(
        'wujia.fleet.provider',
        string='Carrier',
        ondelete='restrict',
        tracking=True,
        index=True,
        help='Leave empty to apply to every carrier of this vehicle type.',
    )
    trip_scope = fields.Selection(
        [
            ('city', 'Inner city'),
            ('interprovince', 'Intercity'),
            ('other', 'Other'),
        ],
        string='Coverage',
        default='interprovince',
    )

    default_drop_fee = fields.Monetary(
        string='Default drop fee',
        currency_field='currency_id',
        default=0.0,
        help='Drop fee applied when the price line does not define its own.',
    )
    currency_id = fields.Many2one(
        'res.currency',
        string='Currency',
        required=True,
        default=lambda self: self.env.company.currency_id,
    )

    date_from = fields.Date(
        string='Valid from',
        required=True,
        default=fields.Date.context_today,
        tracking=True,
        index=True,
    )
    date_to = fields.Date(string='Valid until', tracking=True, index=True)

    line_ids = fields.One2many(
        'wujia.fleet.pricelist.line',
        'pricelist_id',
        string='Price lines',
        copy=True,
    )

    state = fields.Selection(
        PRICELIST_STATE,
        string='Status',
        required=True,
        default='draft',
        tracking=True,
        index=True,
    )
    active = fields.Boolean(default=True)
    note = fields.Text(string='Notes')

    _code_uniq = models.Constraint(
        'UNIQUE (code)',
        'Pricelist code must be unique.',
    )

    @api.constrains('date_from', 'date_to')
    def _check_dates(self):
        for rec in self:
            if rec.date_from and rec.date_to and rec.date_to < rec.date_from:
                raise ValidationError(_("Valid to must be >= valid from."))

    def action_activate(self):
        for rec in self:
            rec.state = 'active'

    def action_archive_pricelist(self):
        for rec in self:
            rec.state = 'archived'

    def action_set_draft(self):
        for rec in self:
            rec.state = 'draft'

    @api.model
    def _cron_expire_pricelists(self):
        """Chuyển state='active' → 'expired' khi date_to < today."""
        today = fields.Date.context_today(self)
        expired = self.search([
            ('state', '=', 'active'),
            ('date_to', '!=', False),
            ('date_to', '<', today),
        ])
        if expired:
            expired.write({'state': 'expired'})
