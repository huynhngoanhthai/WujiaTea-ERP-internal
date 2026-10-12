from datetime import datetime, timedelta

import pytz

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

DEFAULT_TZ = 'Asia/Ho_Chi_Minh'


class WujiaExamSession(models.Model):
    """Kỳ thi — 1 lần tổ chức của 1 khóa thi tại 1 ca giờ, có sức chứa."""

    _name = 'wujia.exam.session'
    _description = 'Wujia Exam Session'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'exam_date desc, id desc'

    name = fields.Char(
        string='Session code', required=True, copy=False,
        readonly=True, default=lambda self: _('New'), tracking=True,
    )
    course_id = fields.Many2one(
        'wujia.exam.course', string='Exam course', required=True,
        domain="[('state', '=', 'published')]",
        ondelete='restrict', index=True, tracking=True,
    )
    exam_date = fields.Date(string='Exam date', required=True, index=True, tracking=True)
    time_slot_id = fields.Many2one(
        'wujia.exam.time.slot', string='Time slot', required=True,
        ondelete='restrict', tracking=True,
    )
    start_datetime = fields.Datetime(
        string='Start', compute='_compute_datetimes', store=True,
    )
    end_datetime = fields.Datetime(
        string='End', compute='_compute_datetimes', store=True,
    )
    location = fields.Char(string='Location')
    capacity = fields.Integer(string='Capacity (people)', default=20, tracking=True)
    max_participants_per_registration = fields.Integer(
        string='Maximum candidates per registration', default=4,
    )
    registration_deadline = fields.Datetime(string='Registration deadline', tracking=True)
    registration_ids = fields.One2many(
        'wujia.exam.registration', 'session_id', string='Registration',
    )
    line_ids = fields.One2many(
        'wujia.exam.registration.line', 'session_id', string='Candidates',
        help='Every candidate of this session — enter the results directly here.',
    )
    registration_count = fields.Integer(
        string='Registration count', compute='_compute_participant_counts',
    )
    reserved_participant_count = fields.Integer(
        string='Seats booked', compute='_compute_participant_counts', store=True,
    )
    available_participant_count = fields.Integer(
        string='Seats left', compute='_compute_participant_counts', store=True,
    )
    state = fields.Selection(
        [('draft', 'Draft'), ('open', 'Open registration'), ('closed', 'Close registration'),
         ('done', 'Exam finished'), ('cancelled', 'Cancelled')],
        string='Status', default='draft', required=True, index=True,
        tracking=True,
    )
    results_published = fields.Boolean(
        string='Results published', readonly=True, copy=False, tracking=True,
    )
    results_published_by_id = fields.Many2one(
        'res.users', string='Results published by', readonly=True, copy=False,
    )
    results_published_date = fields.Datetime(
        string='Result publication date', readonly=True, copy=False,
    )
    cancellation_reason = fields.Text(string='Cancellation reason')
    note = fields.Text(string='Notes')

    _check_capacity_positive = models.Constraint(
        'CHECK(capacity >= 1)', 'Capacity must be ≥ 1.',
    )

    # ------------------------------------------------------------ computes
    @api.depends('exam_date', 'time_slot_id.time_from', 'time_slot_id.time_to')
    def _compute_datetimes(self):
        tz = pytz.timezone(self.env.user.tz or DEFAULT_TZ)
        for rec in self:
            if not rec.exam_date or not rec.time_slot_id:
                rec.start_datetime = rec.end_datetime = False
                continue
            rec.start_datetime = rec._local_to_utc(tz, rec.time_slot_id.time_from)
            rec.end_datetime = rec._local_to_utc(tz, rec.time_slot_id.time_to)

    def _local_to_utc(self, tz, float_hour):
        hour = int(float_hour)
        minute = int(round((float_hour - hour) * 60))
        if hour >= 24:
            hour, minute = 23, 59
        naive = datetime(self.exam_date.year, self.exam_date.month,
                         self.exam_date.day, hour, minute)
        return tz.localize(naive).astimezone(pytz.utc).replace(tzinfo=None)

    @api.depends('capacity', 'registration_ids.state',
                 'registration_ids.participant_count')
    def _compute_participant_counts(self):
        reserved = {}
        counts = {}
        if self.ids:
            groups = self.env['wujia.exam.registration']._read_group(
                domain=[('session_id', 'in', self.ids),
                        ('state', 'in', ('submitted', 'confirmed'))],
                groupby=['session_id'],
                aggregates=['participant_count:sum', '__count'],
            )
            for sess, part_sum, cnt in groups:
                reserved[sess.id] = part_sum or 0
                counts[sess.id] = cnt
        for rec in self:
            rec.reserved_participant_count = reserved.get(rec.id, 0)
            rec.available_participant_count = (
                rec.capacity - rec.reserved_participant_count)
            rec.registration_count = counts.get(rec.id, 0)

    # ------------------------------------------------------------ defaults
    @api.onchange('course_id')
    def _onchange_course(self):
        if self.course_id:
            self.max_participants_per_registration = (
                self.course_id.max_participants_per_registration)
            slots = self.course_id.time_slot_ids
            if slots and self.time_slot_id not in slots:
                self.time_slot_id = slots[:1]
            return {'domain': {'time_slot_id': [('id', 'in', slots.ids)]}}

    @api.onchange('exam_date', 'time_slot_id', 'course_id')
    def _onchange_deadline(self):
        if self.exam_date and self.time_slot_id and not self.registration_deadline:
            lead = self.course_id.registration_lead_days or 0
            tz = pytz.timezone(self.env.user.tz or DEFAULT_TZ)
            start = self._local_to_utc(tz, self.time_slot_id.time_from)
            self.registration_deadline = start - timedelta(days=lead)

    # ------------------------------------------------------------ booking rules
    def _effective_max_per_registration(self):
        """Giới hạn người / phiếu — NGUỒN DUY NHẤT cho hướng dẫn, quota, validate.

        Ca thi cấu hình riêng được thì ưu tiên, để trống mới lấy của khóa (WJ-EXAM-007
        sinh ra vì UI từng chép tay số 4 = default của field).
        """
        self.ensure_one()
        return (self.max_participants_per_registration
                or self.course_id.max_participants_per_registration)

    def _portal_in_deadline(self, now):
        """Đang mở đăng ký và chưa quá hạn (chưa xét còn chỗ)."""
        self.ensure_one()
        return (self.state == 'open'
                and (not self.registration_deadline or now <= self.registration_deadline))

    def _portal_is_selectable(self, now):
        self.ensure_one()
        return self._portal_in_deadline(now) and self.available_participant_count > 0

    def _portal_slot_status(self, now):
        """Vì sao chọn / không chọn được: ``closed`` · ``expired`` · ``full`` · ``open``."""
        self.ensure_one()
        if self.state != 'open':
            return 'closed'
        if self.registration_deadline and now > self.registration_deadline:
            return 'expired'
        if self.available_participant_count <= 0:
            return 'full'
        return 'open'

    # ------------------------------------------------------------ constraints
    @api.constrains('time_slot_id', 'course_id')
    def _check_slot_in_course(self):
        for rec in self:
            if rec.time_slot_id and rec.course_id and \
                    rec.time_slot_id not in rec.course_id.time_slot_ids:
                raise ValidationError(_(
                    "The time slot must be one of the time slots of exam course '%s'.",
                    rec.course_id.name))

    @api.constrains('capacity', 'reserved_participant_count')
    def _check_capacity_ge_reserved(self):
        for rec in self:
            if rec.capacity < rec.reserved_participant_count:
                raise ValidationError(_(
                    "Capacity (%s) cannot be lower than the number of reserved seats (%s).",
                    rec.capacity, rec.reserved_participant_count))

    @api.constrains('registration_deadline', 'start_datetime')
    def _check_deadline(self):
        for rec in self:
            if rec.registration_deadline and rec.start_datetime and \
                    rec.registration_deadline > rec.start_datetime:
                raise ValidationError(_(
                    "The registration deadline cannot be after the exam start time."))

    # ------------------------------------------------------------ sequence
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('name') or vals['name'] == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code(
                    'wujia.exam.session') or _('New')
        return super().create(vals_list)

    # ------------------------------------------------------------ workflow
    def action_open(self):
        for rec in self:
            if rec.state != 'draft':
                raise ValidationError(_("Registration can only be opened for exam sessions in Draft state."))
            rec.state = 'open'
            rec.message_post(body=_("The exam session is now open for registration."))

    def action_close(self):
        for rec in self:
            if rec.state != 'open':
                raise ValidationError(_("Only exam sessions open for registration can be closed."))
            rec.state = 'closed'
            rec.message_post(body=_("The exam session is now closed for registration."))

    def action_mark_done(self):
        for rec in self:
            if rec.state not in ('open', 'closed'):
                raise ValidationError(_("Only exam sessions that are open or closed for registration can be completed."))
            rec.state = 'done'
            rec.message_post(body=_("The exam session has been completed."))

    def action_cancel(self):
        for rec in self:
            if rec.state in ('done', 'cancelled'):
                raise ValidationError(_("This exam session cannot be cancelled."))
            if not rec.cancellation_reason:
                raise ValidationError(_("Enter a cancellation reason before cancelling the exam session."))
            rec.state = 'cancelled'
            rec.message_post(body=_("Exam session cancelled: %s", rec.cancellation_reason))

    def action_publish_results(self):
        for rec in self:
            if rec.state not in ('closed', 'done'):
                raise ValidationError(_(
                    "Results can only be published once the exam session is closed for registration / completed."))
            pending_reg = rec.registration_ids.filtered(
                lambda r: r.state == 'submitted')
            if pending_reg:
                raise ValidationError(_(
                    "%s registrations are still awaiting approval — handle them before publishing.",
                    len(pending_reg)))
            confirmed_lines = rec.registration_ids.filtered(
                lambda r: r.state == 'confirmed').mapped('line_ids')
            if any(line.result == 'pending' for line in confirmed_lines):
                raise ValidationError(_(
                    "Some participants have no result yet (Pass/Fail)."))
            rec.write({
                'results_published': True,
                'results_published_by_id': self.env.uid,
                'results_published_date': fields.Datetime.now(),
            })
            rec.message_post(body=_("The exam results have been published."))
