# -*- coding: utf-8 -*-
from odoo import api, fields, models, _


class WujiaFranchiseExpenseCategory(models.Model):
    _name = 'wujia.franchise.expense.category'
    _description = 'Franchise Operating Expense Category'
    _order = 'sequence asc, id desc'

    name = fields.Char(
        string='Category Name',
        required=True,
        help='Operating expense category name (e.g. Electricity Expense, Water Expense, Ice Purchase).',
    )
    code = fields.Char(
        string='Category Code',
        required=True,
        index=True,
        help='Unique code (e.g. ELEC, WATER, ICE, REPAIR).',
    )
    expense_type = fields.Selection([
        ('operating', 'General Operating'),
        ('personnel', 'Local Personnel'),
        ('receiving', 'Logistics / Receiving'),
        ('other', 'Other'),
    ], string='Expense Type', required=True, default='operating', index=True)
    sequence = fields.Integer(default=10)
    description = fields.Text(string='Description')
    active = fields.Boolean(default=True)

    _sql_constraints = [
        ('code_unique', 'unique(code)', 'Expense Category Code must be unique!'),
    ]
