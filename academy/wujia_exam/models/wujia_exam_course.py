import calendar
from datetime import date, timedelta

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class WujiaExamCourse(models.Model):
    """Khóa thi / chương trình kiểm tra kiến thức (vd Pha chế, Quản lý ca)."""

    _name = 'wujia.exam.course'
    _description = 'Wujia Exam Course'
    _order = 'name, id'

    name = fields.Char(string='Exam course name', required=True)
    code = fields.Char(
        string='Course code', required=True, copy=False,
        readonly=True, default=lambda self: _('New'),
    )
    description = fields.Html(string='Description')
    time_slot_ids = fields.Many2many(
        'wujia.exam.time.slot', 'wujia_exam_course_slot_rel',
        'course_id', 'slot_id', string='Applicable time slots',
    )
    max_participants_per_registration = fields.Integer(
        string='Maximum candidates per registration', default=4,
    )
    registration_lead_days = fields.Integer(
        string='Registration cut-off (days)', default=0,
        help='Number of days before the exam when registration closes.',
    )
    registration_horizon_days = fields.Integer(
        string='Registration window (days)', default=60,
        help='Only exam sessions within this many days from today can be registered.',
    )
    session_ids = fields.One2many(
        'wujia.exam.session', 'course_id', string='Exam session',
    )
    session_count = fields.Integer(
        string='Session count', compute='_compute_session_count',
    )
    state = fields.Selection(
        [('draft', 'Draft'), ('published', 'Published')],
        string='Status', default='draft', required=True, index=True,
    )
    active = fields.Boolean(default=True)

    _uniq_code = models.Constraint(
        'unique(code)', 'Exam course code must be unique.',
    )

    @api.depends('session_ids')
    def _compute_session_count(self):
        data = {}
        if self.ids:
            groups = self.env['wujia.exam.session']._read_group(
                domain=[('course_id', 'in', self.ids)],
                groupby=['course_id'], aggregates=['__count'],
            )
            data = {c.id: n for c, n in groups}
        for rec in self:
            rec.session_count = data.get(rec.id, 0)

    @api.constrains('max_participants_per_registration',
                    'registration_lead_days', 'registration_horizon_days')
    def _check_config(self):
        for rec in self:
            if rec.max_participants_per_registration <= 0:
                raise ValidationError(_("Max participants per registration must be > 0."))
            if rec.registration_lead_days < 0:
                raise ValidationError(_("Registration lead time cannot be negative."))
            if rec.registration_horizon_days <= 0:
                raise ValidationError(_("Registration window (days) must be > 0."))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('code') or vals['code'] == _('New'):
                vals['code'] = self.env['ir.sequence'].next_by_code(
                    'wujia.exam.course') or _('New')
        return super().create(vals_list)

    # ------------------------------------------------------------ booking rules
    def _effective_max_per_registration(self):
        self.ensure_one()
        return self.max_participants_per_registration

    @api.model
    def _portal_published(self):
        """Khóa hiển thị cho cửa hàng chọn khi đăng ký."""
        return self.search([('state', '=', 'published'), ('active', '=', True)],
                           order='name, id')

    def _portal_horizon(self, today):
        self.ensure_one()
        return today + timedelta(days=self.registration_horizon_days)

    def _portal_day_states(self, year, month, today=None, now=None):
        """{ngày trong tháng: ``available`` / ``full`` / ``none``} — lịch đăng ký của khóa."""
        self.ensure_one()
        today = today or fields.Date.context_today(self)
        now = now or fields.Datetime.now()
        horizon = self._portal_horizon(today)
        first = date(year, month, 1)
        last = date(year, month, calendar.monthrange(year, month)[1])
        by_day = {}
        for s in self.env['wujia.exam.session'].search([
            ('course_id', '=', self.id),
            ('exam_date', '>=', first), ('exam_date', '<=', last),
            ('state', '!=', 'cancelled'),
        ]):
            by_day.setdefault(s.exam_date, []).append(s)
        states = {}
        for day in range(1, last.day + 1):
            d = date(year, month, day)
            sessions = by_day.get(d, [])
            if d < today or d > horizon or not sessions:
                states[d] = 'none'
            elif any(s._portal_is_selectable(now) for s in sessions):
                states[d] = 'available'
            # Còn kỳ thi mở / chưa quá hạn nhưng hết chỗ → 'full'.
            elif any(s._portal_in_deadline(now) for s in sessions):
                states[d] = 'full'
            else:
                states[d] = 'none'
        return states

    def _portal_sessions_on(self, day):
        """Kỳ thi (khung giờ) của khóa vào 1 ngày, bỏ kỳ đã hủy."""
        self.ensure_one()
        return self.env['wujia.exam.session'].search([
            ('course_id', '=', self.id), ('exam_date', '=', day),
            ('state', '!=', 'cancelled'),
        ], order='start_datetime, id')

    def _portal_booking_meta(self, today=None, now=None):
        """Số kỳ thi mở trong cửa sổ đăng ký + cờ ``closed`` / ``full``.

        WJ-EXAM-002: 'full' = còn lịch mở, còn hạn, nhưng hết chỗ — khác hẳn 'closed'
        (không còn kỳ thi nào mở/còn hạn). Cả hai đều không cho đăng ký.
        """
        self.ensure_one()
        today = today or fields.Date.context_today(self)
        now = now or fields.Datetime.now()
        upcoming = self.env['wujia.exam.session'].search([
            ('course_id', '=', self.id),
            ('exam_date', '>=', today), ('exam_date', '<=', self._portal_horizon(today)),
            ('state', '=', 'open'),
        ])
        has_open = any(s._portal_is_selectable(now) for s in upcoming)
        return {
            'upcoming_count': len(upcoming),
            'closed': not has_open,
            'full': not has_open and any(s._portal_in_deadline(now) for s in upcoming),
        }

    def action_publish(self):
        for rec in self:
            if not rec.time_slot_ids:
                raise ValidationError(_(
                    "Exam course '%s' needs at least 1 time slot before it can be published.",
                    rec.name))
            if rec.max_participants_per_registration <= 0:
                raise ValidationError(_("Max participants per registration must be > 0."))
            rec.state = 'published'

    def action_reset_to_draft(self):
        self.write({'state': 'draft'})
