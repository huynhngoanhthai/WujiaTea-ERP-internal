from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.tools.translate import LazyTranslate

_lt = LazyTranslate(__name__)

try:
    from psycopg2 import errors as pg_errors
    LockNotAvailable = pg_errors.LockNotAvailable
except Exception:  # pragma: no cover
    LockNotAvailable = Exception



class ExamPortalError(ValidationError):
    """Đầu vào kênh portal bị từ chối trước khi tạo phiếu — ``kind`` = mã lỗi kênh trả về
    (``not_found`` / ``validation``); lỗi lúc tạo phiếu vẫn là ValidationError/UserError thường."""

    def __init__(self, message, kind='validation'):
        super().__init__(message)
        self.kind = kind


REG_STATE = [
    ('submitted', 'Submitted'),
    ('confirmed', 'Approved'),
    ('rejected', 'Rejected'),
    ('cancelled', 'Cancelled'),
]

# Nhãn trạng thái phiếu trên portal — một nguồn cho PC + mobile.
PORTAL_STATE_LABELS = {
    'submitted': _lt('Awaiting confirmation'),
    'confirmed': _lt('Registered'),
    'rejected': _lt('Rejected'),
    'cancelled': _lt('Cancelled'),
}


class WujiaExamRegistration(models.Model):
    """Phiếu đăng ký thi của 1 cửa hàng cho 1 kỳ thi — nhiều nhân sự / phiếu.

    Sprint M: rework từ skeleton (user×schedule) sang phiếu-đa-nhân-sự gắn
    session. Giữ `_name` để portal (demo) không lỗi bind.
    """

    _name = 'wujia.exam.registration'
    _description = 'Wujia Exam Registration'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'request_date desc, id desc'

    name = fields.Char(
        string='Registration code', required=True, copy=False,
        readonly=True, default=lambda self: _('New'), tracking=True,
    )
    session_id = fields.Many2one(
        'wujia.exam.session', string='Exam session', required=True,
        ondelete='restrict', index=True, tracking=True,
    )
    course_id = fields.Many2one(
        'wujia.exam.course', string='Exam course',
        related='session_id.course_id', store=True, index=True,
    )
    franchise_id = fields.Many2one(
        'wujia.franchise.management', string='Store', required=True,
        default=lambda self: self._default_franchise(),
        ondelete='restrict', index=True, tracking=True,
    )
    requester_user_id = fields.Many2one(
        'res.users', string='Registered by',
        default=lambda self: self.env.user, readonly=True, index=True,
    )
    member_id = fields.Many2one(
        'wujia.franchise.member', string='Responsible member',
        domain="[('franchise_id', '=', franchise_id)]",
        ondelete='set null',
        help='Optional — the store member the registration is filed under.',
    )
    request_date = fields.Datetime(
        string='Registration date', default=fields.Datetime.now, readonly=True,
    )
    line_ids = fields.One2many(
        'wujia.exam.registration.line', 'registration_id',
        string='Candidate list',
    )
    participant_count = fields.Integer(
        string='Candidate count', compute='_compute_participant_count', store=True,
    )
    state = fields.Selection(
        REG_STATE, string='Status', default='submitted',
        required=True, index=True, tracking=True,
    )
    confirmed_by_id = fields.Many2one('res.users', string='Approved by', readonly=True)
    confirmed_date = fields.Datetime(string='Approval date', readonly=True)
    rejected_by_id = fields.Many2one('res.users', string='Rejected by', readonly=True)
    rejected_date = fields.Datetime(string='Rejection date', readonly=True)
    cancelled_by_id = fields.Many2one('res.users', string='Cancelled by', readonly=True)
    cancelled_date = fields.Datetime(string='Cancellation date', readonly=True)
    reject_reason = fields.Text(string='Rejection reason', tracking=True)
    cancellation_reason = fields.Text(string='Cancellation reason', tracking=True)
    note = fields.Text(string='Notes')

    @api.model
    def _default_franchise(self):
        fids = self.env.user._get_accessible_franchise_ids()
        return fids[0] if fids else False

    @api.depends('line_ids')
    def _compute_participant_count(self):
        for rec in self:
            rec.participant_count = len(rec.line_ids)

    # ------------------------------------------------------------ constraints
    @api.constrains('line_ids', 'state', 'session_id')
    def _check_participant_bounds(self):
        for rec in self.filtered(lambda r: r.state in ('submitted', 'confirmed')):
            n = len(rec.line_ids)
            if n < 1:
                raise ValidationError(_(
                    "Registration '%s' needs at least 1 participant.", rec.name))
            max_p = rec.session_id._effective_max_per_registration() or 0
            if max_p and n > max_p:
                raise ValidationError(_(
                    "Registration '%s': at most %s participants per registration.", rec.name, max_p))

    # ------------------------------------------------------------ capacity lock
    def _lock_and_check_capacity(self):
        """Khóa row kỳ thi (NOWAIT) + đếm lại giữ-chỗ trong transaction.

        Chống 2 phiếu submit đồng thời vượt sức chứa (perf 1500 user: 1 lock +
        1 read_group, không loop per-record).
        """
        sessions = self.mapped('session_id')
        if not sessions:
            return
        try:
            self.env.cr.execute(
                "SELECT id FROM wujia_exam_session WHERE id IN %s FOR UPDATE NOWAIT",
                (tuple(sessions.ids),),
            )
        except LockNotAvailable:
            raise UserError(_(
                "Another registration for this exam session is being processed, please try again."))
        # Recount reserved participants per session (submitted + confirmed).
        sessions.invalidate_recordset(
            ['reserved_participant_count', 'available_participant_count'])
        for sess in sessions:
            if sess.reserved_participant_count > sess.capacity:
                raise ValidationError(_(
                    "Exam session '%s' is fully booked (capacity %s, reserved %s).",
                    sess.name, sess.capacity, sess.reserved_participant_count))

    def _check_booking_allowed(self):
        for rec in self:
            sess = rec.session_id
            if sess.state != 'open':
                raise ValidationError(_(
                    "Exam session '%s' is not open for registration.", sess.name))
            if sess.registration_deadline and \
                    fields.Datetime.now() > sess.registration_deadline:
                raise ValidationError(_(
                    "Exam session '%s' is past its registration deadline.", sess.name))

    # ------------------------------------------------------------ sequence
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('name') or vals['name'] == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code(
                    'wujia.exam.registration') or _('New')
        records = super().create(vals_list)
        booking = records.filtered(lambda r: r.state == 'submitted')
        booking._check_booking_allowed()
        booking._lock_and_check_capacity()
        return records

    def write(self, vals):
        res = super().write(vals)
        if {'line_ids', 'session_id', 'state'} & set(vals):
            self.filtered(
                lambda r: r.state in ('submitted', 'confirmed'))._lock_and_check_capacity()
        return res

    # ------------------------------------------------------------ portal
    @api.model
    def _portal_scope_domain(self, franchise_id):
        return [('franchise_id', '=', franchise_id)]

    def _portal_has_result(self):
        """Có kết quả — thông tin riêng, không thay trạng thái phiếu."""
        self.ensure_one()
        return self.state == 'confirmed' and self.session_id.results_published

    def _portal_result_counts(self):
        """(số Đạt, số Không đạt) của phiếu — chỉ có nghĩa khi kỳ thi đã công bố."""
        self.ensure_one()
        results = self.line_ids.mapped('result')
        return results.count('passed'), results.count('failed')

    @api.model
    def register_from_portal(self, session_id, franchise_id, user, participants, note=None):
        """Cửa hàng tự đăng ký thi — kiểm đầu vào, dựng thí sinh, tạo phiếu trong 1 savepoint.

        Đầu vào sai ⇒ ExamPortalError (``kind``); phiếu không tạo được (hết chỗ, quá hạn,
        kỳ thi đóng…) ⇒ ValidationError/UserError của create, đã rollback sạch.
        """
        session = self.env['wujia.exam.session'].sudo().browse(session_id).exists()
        if not session or session.course_id.state != 'published':
            raise ExamPortalError(_('The time slot has changed or is no longer available.'
                                    ' Please choose the exam schedule again.'), kind='not_found')
        parts = participants or []
        max_p = session._effective_max_per_registration()
        if not parts:
            raise ExamPortalError(_('At least 1 participant is required.'))
        if max_p and len(parts) > max_p:
            raise ExamPortalError(_('At most %d people per registration.', max_p))
        Line = self.env['wujia.exam.registration.line']
        try:
            line_cmds = [(0, 0, Line._portal_prepare_vals(p)) for p in parts]
        except ValidationError as e:
            raise ExamPortalError(e.args[0] if e.args else str(e))
        member = self.env['wujia.franchise.member'].sudo()
        try:
            member = member.find_active_membership(user.id, franchise_id)
        except Exception:  # pragma: no cover — helper vắng thì bỏ qua
            member = member.browse()
        # Savepoint + flush: constraint sức chứa của session là @api.constrains → chỉ
        # raise lúc flush; để tới flush cuối request thì thành 500 và (nguy hiểm hơn)
        # commit phiếu vượt chỗ. Ép flush ở đây, savepoint đảm bảo rollback sạch.
        with self.env.cr.savepoint():
            reg = self.sudo().create({
                'session_id': session.id,
                'franchise_id': franchise_id,
                'requester_user_id': user.id,
                'member_id': member.id if member else False,
                'note': (note or '').strip() or False,
                'line_ids': line_cmds,
            })
            self.env.flush_all()
        return reg

    # ------------------------------------------------------------ workflow
    def action_confirm(self):
        for rec in self:
            if rec.state != 'submitted':
                raise ValidationError(_("Only registrations in Submitted state can be approved."))
            rec.write({
                'state': 'confirmed',
                'confirmed_by_id': self.env.uid,
                'confirmed_date': fields.Datetime.now(),
            })
            rec.message_post(body=_("The registration has been approved."))

    def action_reject(self):
        for rec in self:
            if rec.state not in ('submitted', 'confirmed'):
                raise ValidationError(_("This registration cannot be rejected."))
            if not rec.reject_reason:
                raise ValidationError(_("Enter a rejection reason before rejecting."))
            rec.write({
                'state': 'rejected',
                'rejected_by_id': self.env.uid,
                'rejected_date': fields.Datetime.now(),
            })
            rec.message_post(body=_("Registration rejected: %s", rec.reject_reason))

    def action_cancel(self):
        for rec in self:
            if rec.state in ('rejected', 'cancelled'):
                raise ValidationError(_("This registration cannot be cancelled."))
            if rec.session_id.results_published:
                raise ValidationError(_(
                    "A registration cannot be cancelled after the exam results have been published."))
            if not rec.cancellation_reason:
                raise ValidationError(_("Enter a cancellation reason before cancelling the registration."))
            rec.write({
                'state': 'cancelled',
                'cancelled_by_id': self.env.uid,
                'cancelled_date': fields.Datetime.now(),
            })
            rec.message_post(body=_("The registration has been cancelled: %s",
                                    rec.cancellation_reason))
