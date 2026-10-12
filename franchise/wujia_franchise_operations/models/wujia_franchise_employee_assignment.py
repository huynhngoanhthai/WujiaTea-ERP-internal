# -*- coding: utf-8 -*-
from odoo import api, fields, models, tools, _
from odoo.exceptions import ValidationError


class WujiaFranchiseEmployeeAssignment(models.Model):
    _name = 'wujia.franchise.employee.assignment'
    _description = 'Franchise Employee Store Assignment'
    _order = 'date_from desc, id desc'

    def _auto_init(self):
        super()._auto_init()
        # Composite Index for Primary Active Employee Assignment
        tools.create_index(
            self._cr,
            'idx_emp_assignment_emp_store_primary',
            self._table,
            ['employee_id', 'is_primary', 'state'],
        )


    employee_id = fields.Many2one(
        'wujia.franchise.employee',
        string='Employee',
        required=True,
        ondelete='cascade',
        index=True,
    )
    franchise_id = fields.Many2one(
        'wujia.franchise.management',
        string='Franchise Store',
        required=True,
        ondelete='cascade',
        index=True,
    )
    job_position = fields.Selection([
        ('staff', 'Staff / Barista'),
        ('shift_leader', 'Shift Leader'),
        ('store_manager', 'Store Manager'),
    ], string='Job Position', required=True, default='staff', index=True, help='Store job position.')
    date_from = fields.Date(
        string='Start Date',
        required=True,
        default=fields.Date.context_today,
    )
    date_to = fields.Date(
        string='End Date',
        help='Leave empty if currently active.',
    )
    state = fields.Selection([
        ('scheduled', 'Scheduled'),
        ('working', 'Working'),
        ('suspended', 'Suspended'),
        ('ended', 'Ended'),
    ], string='Status', compute='_compute_state', store=True, readonly=False, required=True, default='scheduled', index=True)

    is_primary = fields.Boolean(
        string='Primary Assignment',
        default=False,
        help='Marks the primary franchise store for this employee. Maximum 1 active primary assignment per employee.',
    )
    note = fields.Text(string='Note')
    active = fields.Boolean(default=True)

    @api.model_create_multi
    def create(self, vals_list):
        today = fields.Date.context_today(self)
        for vals in vals_list:
            if 'state' not in vals or not vals.get('state'):
                date_from = vals.get('date_from')
                date_to = vals.get('date_to')
                if isinstance(date_from, str):
                    date_from = fields.Date.from_string(date_from)
                if isinstance(date_to, str):
                    date_to = fields.Date.from_string(date_to)

                if not date_from or date_from > today:
                    vals['state'] = 'scheduled'
                elif date_to and date_to < today:
                    vals['state'] = 'ended'
                else:
                    vals['state'] = 'working'
        return super().create(vals_list)

    @api.depends('date_from', 'date_to')
    def _compute_state(self):
        today = fields.Date.context_today(self)
        for rec in self:
            if rec.state == 'suspended':
                continue
            if not rec.date_from:
                rec.state = 'scheduled'
            elif rec.date_from > today:
                rec.state = 'scheduled'
            elif rec.date_to and rec.date_to < today:
                rec.state = 'ended'
            else:
                rec.state = 'working'

    @api.constrains('date_from', 'date_to')
    def _check_dates(self):
        for rec in self:
            if rec.date_to and rec.date_to < rec.date_from:
                raise ValidationError(_("End Date (%s) cannot be earlier than Start Date (%s).", rec.date_to, rec.date_from))

    @api.constrains('employee_id', 'is_primary', 'state')
    def _check_unique_primary_assignment(self):
        for rec in self:
            if rec.is_primary and rec.state in ('working', 'scheduled'):
                other_primary = self.search([
                    ('employee_id', '=', rec.employee_id.id),
                    ('is_primary', '=', True),
                    ('state', 'in', ('working', 'scheduled')),
                    ('id', '!=', rec.id),
                ], limit=1)
                if other_primary:
                    raise ValidationError(_(
                        "Employee '%s' already has an active or upcoming primary store assignment (%s). "
                        "An employee can only have one primary assignment (is_primary = True) active or upcoming at a time.",
                        rec.employee_id.name,
                        other_primary.franchise_id.display_name,
                    ))

    @api.constrains('employee_id', 'franchise_id', 'date_from', 'date_to', 'state')
    def _check_overlapping_assignments(self):
        for rec in self:
            if rec.state == 'ended':
                continue
            domain = [
                ('employee_id', '=', rec.employee_id.id),
                ('franchise_id', '=', rec.franchise_id.id),
                ('state', '!=', 'ended'),
                ('id', '!=', rec.id),
            ]
            overlapping = self.search(domain)
            for other in overlapping:
                # Overlap check for date ranges
                rec_end = rec.date_to or fields.Date.from_string('9999-12-31')
                other_end = other.date_to or fields.Date.from_string('9999-12-31')
                if max(rec.date_from, other.date_from) <= min(rec_end, other_end):
                    raise ValidationError(_(
                        "Employee '%s' already has an overlapping assignment at store '%s' (%s - %s).",
                        rec.employee_id.name,
                        rec.franchise_id.display_name,
                        other.date_from,
                        other.date_to or 'Present',
                    ))

    def name_get(self):
        result = []
        for rec in self:
            name = f"{rec.employee_id.name} @ {rec.franchise_id.code or rec.franchise_id.name}"
            result.append((rec.id, name))
        return result

    @api.depends('employee_id.name', 'franchise_id.display_name')
    def _compute_display_name(self):
        for rec in self:
            emp_name = rec.employee_id.name if rec.employee_id else ''
            store_name = rec.franchise_id.code or rec.franchise_id.name if rec.franchise_id else ''
            rec.display_name = f"{emp_name} @ {store_name}"
