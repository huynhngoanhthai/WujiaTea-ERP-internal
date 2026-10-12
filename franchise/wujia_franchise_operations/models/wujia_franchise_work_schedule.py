# -*- coding: utf-8 -*-
from datetime import datetime, timedelta
import pytz

from odoo import api, fields, models, tools, _
from odoo.exceptions import ValidationError


class WujiaFranchiseWorkSchedule(models.Model):
    _name = 'wujia.franchise.work.schedule'
    _description = 'Franchise Store Work Schedule'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'work_date desc, planned_start desc, id desc'

    def _auto_init(self):
        super()._auto_init()
        # Composite Index 1: Store calendar query by Store + Date + State
        tools.create_index(
            self._cr,
            'idx_work_schedule_store_date_state',
            self._table,
            ['franchise_id', 'work_date desc', 'state'],
        )
        # Composite Index 2: Employee personal roster query by Employee + Date
        tools.create_index(
            self._cr,
            'idx_work_schedule_emp_date',
            self._table,
            ['employee_id', 'work_date desc'],
        )


    name = fields.Char(
        string='Schedule Name',
        compute='_compute_name',
        store=True,
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
    assignment_id = fields.Many2one(
        'wujia.franchise.employee.assignment',
        string='Employee Assignment',
        required=True,
        domain="[('franchise_id', '=', franchise_id), ('state', 'in', ('working', 'scheduled'))]",
        ondelete='cascade',
    )
    employee_id = fields.Many2one(
        'wujia.franchise.employee',
        string='Employee',
        related='assignment_id.employee_id',
        store=True,
        index=True,
        readonly=True,
    )
    work_date = fields.Date(
        string='Work Date',
        required=True,
        default=fields.Date.context_today,
        index=True,
    )
    shift_template_id = fields.Many2one(
        'wujia.franchise.shift.template',
        string='Shift Template',
        required=True,
        domain="['|', ('franchise_id', '=', False), ('franchise_id', '=', franchise_id)]",
        ondelete='restrict',
    )
    planned_start = fields.Datetime(
        string='Planned Start',
        required=True,
        tracking=True,
        help='Snapshot of shift start time in UTC.',
    )
    planned_end = fields.Datetime(
        string='Planned End',
        required=True,
        tracking=True,
        help='Snapshot of shift end time in UTC.',
    )
    planned_hours = fields.Float(
        string='Planned Hours',
        required=True,
        digits=(16, 2),
        tracking=True,
        help='Snapshot of planned work hours.',
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

    @api.depends('work_date', 'employee_id.name', 'shift_template_id.name')
    def _compute_name(self):
        for rec in self:
            date_str = rec.work_date.strftime('%Y-%m-%d') if rec.work_date else ''
            emp_name = rec.employee_id.name if rec.employee_id else ''
            shift_name = rec.shift_template_id.name if rec.shift_template_id else ''
            rec.name = f"[{date_str}] {emp_name} - {shift_name}"

    def _calculate_planned_times(self, vals):
        work_date = vals.get('work_date')
        shift_id = vals.get('shift_template_id')
        if not shift_id or not work_date:
            return vals

        shift = self.env['wujia.franchise.shift.template'].browse(shift_id)
        if not shift.exists():
            return vals

        if isinstance(work_date, str):
            work_date = fields.Date.from_string(work_date)

        tz_name = self.env.user.tz or 'Asia/Ho_Chi_Minh'
        user_tz = pytz.timezone(tz_name)

        start_hour = int(shift.start_time)
        start_min = int(round((shift.start_time - start_hour) * 60))
        end_hour = int(shift.end_time)
        end_min = int(round((shift.end_time - end_hour) * 60))

        dt_start_naive = datetime.combine(work_date, datetime.min.time()) + timedelta(hours=start_hour, minutes=start_min)
        if shift.end_time > shift.start_time:
            dt_end_naive = datetime.combine(work_date, datetime.min.time()) + timedelta(hours=end_hour, minutes=end_min)
        else:
            dt_end_naive = datetime.combine(work_date + timedelta(days=1), datetime.min.time()) + timedelta(hours=end_hour, minutes=end_min)

        dt_start_tz = user_tz.localize(dt_start_naive, is_dst=None)
        dt_end_tz = user_tz.localize(dt_end_naive, is_dst=None)

        if 'planned_start' not in vals or not vals.get('planned_start'):
            vals['planned_start'] = dt_start_tz.astimezone(pytz.utc).replace(tzinfo=None)
        if 'planned_end' not in vals or not vals.get('planned_end'):
            vals['planned_end'] = dt_end_tz.astimezone(pytz.utc).replace(tzinfo=None)
        if 'planned_hours' not in vals or not vals.get('planned_hours'):
            vals['planned_hours'] = shift.planned_hours
        return vals

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            self._calculate_planned_times(vals)
        return super().create(vals_list)

    @api.onchange('work_date', 'shift_template_id', 'franchise_id')
    def _onchange_calculate_planned_times(self):
        """Auto-calculate planned_start, planned_end, planned_hours in User's timezone snapshot."""
        if not self.work_date or not self.shift_template_id:
            return

        tz_name = self.env.user.tz or 'Asia/Ho_Chi_Minh'
        user_tz = pytz.timezone(tz_name)
        shift = self.shift_template_id

        # Convert work_date to local naive datetime at 00:00
        start_hour = int(shift.start_time)
        start_min = int(round((shift.start_time - start_hour) * 60))

        end_hour = int(shift.end_time)
        end_min = int(round((shift.end_time - end_hour) * 60))

        dt_start_naive = datetime.combine(self.work_date, datetime.min.time()) + timedelta(hours=start_hour, minutes=start_min)

        if shift.end_time > shift.start_time:
            dt_end_naive = datetime.combine(self.work_date, datetime.min.time()) + timedelta(hours=end_hour, minutes=end_min)
        else:
            # Overnight shift -> end date is next day
            dt_end_naive = datetime.combine(self.work_date + timedelta(days=1), datetime.min.time()) + timedelta(hours=end_hour, minutes=end_min)

        dt_start_tz = user_tz.localize(dt_start_naive, is_dst=None)
        dt_end_tz = user_tz.localize(dt_end_naive, is_dst=None)

        self.planned_start = dt_start_tz.astimezone(pytz.utc).replace(tzinfo=None)
        self.planned_end = dt_end_tz.astimezone(pytz.utc).replace(tzinfo=None)
        self.planned_hours = shift.planned_hours

    @api.constrains('assignment_id', 'franchise_id')
    def _check_assignment_match_store(self):
        for rec in self:
            if rec.assignment_id.franchise_id != rec.franchise_id:
                raise ValidationError(_(
                    "Assignment '%s' belongs to store '%s', which does not match the selected store '%s' on the schedule.",
                    rec.assignment_id.display_name,
                    rec.assignment_id.franchise_id.display_name,
                    rec.franchise_id.display_name,
                ))

    @api.constrains('shift_template_id', 'franchise_id')
    def _check_shift_template_store(self):
        for rec in self:
            shift = rec.shift_template_id
            if shift.franchise_id and shift.franchise_id != rec.franchise_id:
                raise ValidationError(_(
                    "Shift template '%s' is restricted to store '%s' and cannot be applied to store '%s'.",
                    shift.name,
                    shift.franchise_id.display_name,
                    rec.franchise_id.display_name,
                ))

    @api.constrains('assignment_id', 'planned_start', 'planned_end', 'state')
    def _check_overlapping_schedules(self):
        for rec in self:
            if rec.state == 'cancelled':
                continue
            if not rec.planned_start or not rec.planned_end:
                continue

            domain = [
                ('assignment_id', '=', rec.assignment_id.id),
                ('state', 'in', ('draft', 'confirmed')),
                ('id', '!=', rec.id),
            ]
            overlapping = self.search(domain)
            for other in overlapping:
                if max(rec.planned_start, other.planned_start) < min(rec.planned_end, other.planned_end):
                    raise ValidationError(_(
                        "Employee '%s' has an overlapping work shift at store '%s' (%s - %s).",
                        rec.employee_id.name,
                        rec.franchise_id.display_name,
                        other.name,
                        other.planned_start.strftime('%Y-%m-%d %H:%M'),
                    ))

    def action_confirm(self):
        for rec in self:
            if rec.state == 'cancelled':
                raise ValidationError(_("Cannot confirm a cancelled work schedule."))
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

    @api.model
    def action_get_work_schedules(self):
        """Action method to open work schedules with default store filter (smallest ID active store) and this week filter."""
        action = self.env.ref('wujia_franchise_operations.action_wujia_franchise_work_schedule').read()[0]
        first_store = self.env['wujia.franchise.management'].search([('active', '=', True)], order='id asc', limit=1)
        today = fields.Date.today()
        start_of_week = today - timedelta(days=today.weekday())
        end_of_week = start_of_week + timedelta(days=6)

        ctx = dict(self.env.context or {})
        ctx['search_default_filter_this_week'] = 1
        if first_store:
            ctx['search_default_franchise_id'] = first_store.id
        action['context'] = ctx
        action['domain'] = [
            ('work_date', '>=', start_of_week),
            ('work_date', '<=', end_of_week),
        ]
        return action
