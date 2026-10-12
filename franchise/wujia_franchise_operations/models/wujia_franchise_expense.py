# -*- coding: utf-8 -*-
from odoo import api, fields, models, tools, _
from odoo.exceptions import ValidationError


class WujiaFranchiseExpense(models.Model):
    _name = 'wujia.franchise.expense'
    _description = 'Franchise Store Operating Expense'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'expense_date desc, id desc'

    def _auto_init(self):
        super()._auto_init()
        # Composite Index for Expense Audit (Store + Category + Date)
        tools.create_index(
            self._cr,
            'idx_franchise_expense_store_cat_date',
            self._table,
            ['franchise_id', 'category_id', 'expense_date desc'],
        )


    name = fields.Char(
        string='Expense Number',
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
    expense_date = fields.Date(
        string='Expense Date',
        required=True,
        default=fields.Date.context_today,
        tracking=True,
        index=True,
    )
    category_id = fields.Many2one(
        'wujia.franchise.expense.category',
        string='Category',
        required=True,
        domain="[('active', '=', True)]",
        ondelete='restrict',
        tracking=True,
    )
    amount = fields.Monetary(
        string='Amount',
        required=True,
        default=0.0,
        currency_field='currency_id',
        tracking=True,
    )
    currency_id = fields.Many2one(
        'res.currency',
        string='Currency',
        required=True,
        default=lambda self: self.env.company.currency_id.id,
    )
    description = fields.Text(
        string='Description',
        required=True,
        help='Detailed description of the expense reason and receipt details.',
    )
    attachment_ids = fields.Many2many(
        'ir.attachment',
        string='Receipt Attachments',
        help='Scan or photo of bills, invoices, receipts.',
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
        ('name_unique', 'unique(name)', 'Expense Number must be unique!'),
    ]

    @api.constrains('amount')
    def _check_amount_positive(self):
        for rec in self:
            if rec.amount < 0:
                raise ValidationError(_("Expense amount (%s) cannot be negative.", rec.amount))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code('wujia.franchise.expense') or _('New')
        return super().create(vals_list)

    def action_confirm(self):
        for rec in self:
            if rec.state == 'cancelled':
                raise ValidationError(_("Cannot confirm a cancelled expense record."))
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
