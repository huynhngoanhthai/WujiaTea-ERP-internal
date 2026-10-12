# -*- coding: utf-8 -*-
from odoo import api, fields, models, _


class WujiaFranchiseEmployee(models.Model):
    _name = 'wujia.franchise.employee'
    _description = 'Franchise Employee Profile'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'code desc, id desc'

    code = fields.Char(
        string='Employee Code',
        required=True,
        readonly=True,
        copy=False,
        default=lambda self: _('New'),
        index=True,
        help='Unique employee code generated across the franchise chain.',
    )
    name = fields.Char(
        string='Employee Name',
        required=True,
        tracking=True,
        help='Full name of the franchise store employee.',
    )
    phone = fields.Char(
        string='Phone',
        tracking=True,
    )
    email = fields.Char(
        string='Email',
        tracking=True,
    )
    image_1920 = fields.Image(
        string='Image',
        max_width=1920,
        max_height=1920,
    )
    assignment_ids = fields.One2many(
        'wujia.franchise.employee.assignment',
        'employee_id',
        string='Store Assignments',
    )
    active_assignment_ids = fields.One2many(
        'wujia.franchise.employee.assignment',
        'employee_id',
        string='Active Assignments',
        domain=[('state', '=', 'working')],
    )
    primary_franchise_id = fields.Many2one(
        'wujia.franchise.management',
        string='Primary Store',
        compute='_compute_primary_franchise_id',
        store=True,
    )
    note = fields.Text(string='Note')
    active = fields.Boolean(default=True)

    _sql_constraints = [
        ('code_unique', 'unique(code)', 'Employee Code must be unique across the system!'),
    ]

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('code', _('New')) == _('New'):
                vals['code'] = self.env['ir.sequence'].next_by_code('wujia.franchise.employee') or _('New')
        return super().create(vals_list)

    @api.depends('assignment_ids.is_primary', 'assignment_ids.state', 'assignment_ids.franchise_id')
    def _compute_primary_franchise_id(self):
        for emp in self:
            primary = emp.assignment_ids.filtered(lambda a: a.is_primary and a.state == 'working')
            emp.primary_franchise_id = primary[:1].franchise_id if primary else False
