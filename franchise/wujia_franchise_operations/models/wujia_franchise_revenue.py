# -*- coding: utf-8 -*-
from odoo import api, fields, models, tools, _
from odoo.exceptions import ValidationError


class WujiaFranchiseRevenue(models.Model):
    _name = 'wujia.franchise.revenue'
    _description = 'Franchise Store Daily Declared Revenue'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'business_date desc, id desc'

    def _auto_init(self):
        super()._auto_init()
        tools.create_index(
            self._cr,
            'idx_wujia_revenue_store_date_state',
            self._table,
            ['franchise_id', 'business_date desc', 'state'],
        )


    name = fields.Char(
        string='Revenue Record Number',
        required=True,
        readonly=True,
        copy=False,
        default=lambda self: _('New'),
        index=True,
    )
    franchise_id = fields.Many2one(
        'wujia.franchise.management',
        string='Franchise Store',
        required=True,
        tracking=True,
        index=True,
        ondelete='cascade',
    )
    business_date = fields.Date(
        string='Business Date',
        required=True,
        default=fields.Date.context_today,
        tracking=True,
        index=True,
        help='Original retail business date for the revenue declaration.',
    )
    amount = fields.Monetary(
        string='Declared Revenue',
        required=True,
        default=0.0,
        currency_field='currency_id',
        tracking=True,
        help='Total retail revenue declared for this business date. 0.0 is valid (store closed/no sales).',
    )
    currency_id = fields.Many2one(
        'res.currency',
        string='Currency',
        required=True,
        default=lambda self: self.env.company.currency_id.id,
    )
    source = fields.Selection([
        ('manual', 'Manual'),
        ('import', 'Import (Excel/CSV)'),
    ], string='Entry Source', required=True, default='manual', tracking=True)

    import_file = fields.Binary(
        string='Revenue File',
        tracking=True,
        help='Upload Excel (.xlsx, .xls) or CSV (.csv) file for revenue declaration.',
    )
    import_file_name = fields.Char(string='File Name')

    source_reference = fields.Char(
        string='Source Reference',
        help='Reference file name or import session ID for audit trail.',
    )
    state = fields.Selection([
        ('draft', 'Draft'),
        ('confirmed', 'Confirmed'),
        ('cancelled', 'Cancelled'),
    ], string='Status', required=True, default='draft', tracking=True, index=True)

    confirmed_by_id = fields.Many2one(
        'res.users',
        string='Confirmed By',
        readonly=True,
    )
    confirmed_date = fields.Datetime(
        string='Confirmed Date',
        readonly=True,
    )
    note = fields.Text(string='Note')
    active = fields.Boolean(default=True)

    _sql_constraints = [
        ('name_unique', 'unique(name)', 'Revenue Record Number must be unique!'),
    ]

    @api.constrains('amount')
    def _check_amount_non_negative(self):
        for rec in self:
            if rec.amount < 0:
                raise ValidationError(_("Declared revenue amount (%s) cannot be negative.", rec.amount))

    @api.constrains('franchise_id', 'business_date', 'state')
    def _check_unique_daily_revenue(self):
        """Idempotent constraint: Each franchise store can have only ONE non-cancelled revenue record per business_date."""
        for rec in self:
            if rec.state == 'cancelled':
                continue
            duplicate = self.search([
                ('franchise_id', '=', rec.franchise_id.id),
                ('business_date', '=', rec.business_date),
                ('state', 'in', ('draft', 'confirmed')),
                ('id', '!=', rec.id),
            ], limit=1)
            if duplicate:
                raise ValidationError(_(
                    "Store '%s' already has a revenue record for date %s (%s). "
                    "Each store can only declare one revenue record per business date.",
                    rec.franchise_id.display_name,
                    rec.business_date,
                    duplicate.name,
                ))

    @api.constrains('source', 'import_file')
    def _check_import_file_required(self):
        for rec in self:
            if rec.source == 'import' and not rec.import_file:
                raise ValidationError(_("Please upload a revenue file when entry source is 'Import (Excel/CSV)'."))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code('wujia.franchise.revenue') or _('New')
        return super().create(vals_list)

    def action_confirm(self):
        for rec in self:
            if rec.state == 'cancelled':
                raise ValidationError(_("Cannot confirm a cancelled revenue record."))
            rec.write({
                'state': 'confirmed',
                'confirmed_by_id': self.env.user.id,
                'confirmed_date': fields.Datetime.now(),
            })

    def action_cancel(self):
        for rec in self:
            rec.write({'state': 'cancelled'})

    def action_draft(self):
        for rec in self:
            rec.write({
                'state': 'draft',
                'confirmed_by_id': False,
                'confirmed_date': False,
            })

    def action_open_compute_wizard(self):
        self.ensure_one()
        if not self.import_file:
            raise ValidationError(_("Please upload a revenue file before calculating revenue."))
        return {
            'name': _("Auto Calculate Revenue from File"),
            'type': 'ir.actions.act_window',
            'res_model': 'wujia.franchise.revenue.compute.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_revenue_id': self.id,
            },
        }
