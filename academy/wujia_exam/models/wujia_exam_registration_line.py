import base64
import binascii
import re

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError
from odoo.tools.image import image_process

PHONE_RE = re.compile(r'^(0|\+84)[0-9]{8,10}$')
MAX_PHOTO_BYTES = 5 * 1024 * 1024
PHOTO_MIMES = ('image/jpeg', 'image/jpg', 'image/png')

RESULT_STATE = [
    ('pending', 'No result yet'),
    ('passed', 'Passed'),
    ('failed', 'Failed'),
]


class WujiaExamRegistrationLine(models.Model):
    """1 nhân sự dự thi trong 1 phiếu đăng ký (nhập tay, free-text)."""

    _name = 'wujia.exam.registration.line'
    _description = 'Wujia Exam Registration Line'
    _order = 'registration_id, sequence, id'

    registration_id = fields.Many2one(
        'wujia.exam.registration', string='Registration',
        required=True, ondelete='cascade', index=True,
    )
    sequence = fields.Integer(default=10)
    session_id = fields.Many2one(
        related='registration_id.session_id', store=True, index=True,
    )
    franchise_id = fields.Many2one(
        related='registration_id.franchise_id', store=True, index=True,
    )
    employee_name = fields.Char(string='Candidate full name', required=True)
    phone = fields.Char(string='Phone number', required=True)
    birth_year = fields.Integer(string='Year of birth')
    job_position = fields.Char(string='Job position')
    image_1920 = fields.Image(
        string='Candidate photo', max_width=1920, max_height=1920,
    )
    photo_state = fields.Char(
        string='Photo', compute='_compute_photo_state',
        help='Reads "No photo" when the candidate has no picture yet.',
    )
    result = fields.Selection(
        RESULT_STATE, string='Result', default='pending', required=True,
        index=True, tracking=True,
    )
    result_note = fields.Text(string='Result note')
    result_entered_by_id = fields.Many2one(
        'res.users', string='Result entered by', readonly=True,
    )
    result_entered_date = fields.Datetime(string='Result entry date', readonly=True)

    @api.depends('image_1920')
    def _compute_photo_state(self):
        for rec in self:
            rec.photo_state = _("Uploaded") if rec.image_1920 else _("No photo")

    @api.constrains('phone')
    def _check_phone(self):
        for rec in self:
            if rec.phone and not PHONE_RE.match(rec.phone.strip()):
                raise ValidationError(_(
                    "Phone number '%s' is invalid (e.g. 0901234567).", rec.phone))

    @api.constrains('birth_year')
    def _check_birth_year(self):
        current = fields.Date.context_today(self).year
        for rec in self:
            if rec.birth_year and not (1900 <= rec.birth_year <= current):
                raise ValidationError(_(
                    "Year of birth must be between 1900 and %s.", current))

    # ------------------------------------------------------------ portal intake
    @api.model
    def _portal_scope_domain(self, franchise_id):
        return [('franchise_id', '=', franchise_id)]

    @api.model
    def _portal_prepare_vals(self, p):
        """1 người dự thi gửi từ kênh portal → vals line; sai thì ValidationError thân thiện."""
        name = (p.get('employee_name') or '').strip()
        phone = (p.get('phone') or '').strip()
        if not name or not phone:
            raise ValidationError(_(
                "Each participant needs a full name and a phone number."))
        # WJ-EXAM-001 — chặn ngay lúc nhận thay vì đợi constraint lúc flush.
        if not PHONE_RE.match(phone):
            raise ValidationError(_(
                "Phone number '%s' is invalid (e.g. 0901234567).", phone))
        vals = {
            'employee_name': name, 'phone': phone,
            'job_position': (p.get('job_position') or '').strip() or False,
        }
        by = (p.get('birth_year') or '').strip() if isinstance(
            p.get('birth_year'), str) else p.get('birth_year')
        if by:
            try:
                vals['birth_year'] = int(by)
            except (TypeError, ValueError):
                raise ValidationError(_("Year of birth '%s' is invalid.", by))
        photo = p.get('photo')
        if photo:
            vals['image_1920'] = self._portal_clean_photo(photo)
        return vals

    @api.model
    def _portal_clean_photo(self, raw):
        """data-URL/base64 ảnh → base64 str hợp lệ (guard MIME + dung lượng)."""
        data = raw
        if raw.startswith('data:'):
            try:
                head, data = raw.split(',', 1)
            except ValueError:
                raise ValidationError(_(
                    "The staff photo has an invalid format or exceeds the allowed size."))
            mime = head[5:].split(';', 1)[0].lower()
            if mime and mime not in PHOTO_MIMES:
                raise ValidationError(_(
                    "The staff photo has an invalid format or exceeds the allowed size."))
        try:
            decoded = base64.b64decode(data, validate=True)
        except (binascii.Error, ValueError):
            raise ValidationError(_(
                "The staff photo has an invalid format or exceeds the allowed size."))
        if len(decoded) > MAX_PHOTO_BYTES:
            raise ValidationError(_(
                "The staff photo exceeds the allowed size (max 5 MB)."))
        # Chạy đúng pipeline mà fields.Image dùng lúc write (resize ≤1920). Ảnh
        # hỏng/cắt cụt sẽ ném ở đây → trả message thân thiện thay vì 500 khi flush.
        try:
            image_process(decoded, size=(1920, 1920))
        except Exception:
            raise ValidationError(_(
                "The staff photo is invalid or corrupted. Please choose another photo."))
        return data

    def write(self, vals):
        if 'result' in vals:
            vals.setdefault('result_entered_by_id', self.env.uid)
            vals.setdefault('result_entered_date', fields.Datetime.now())
        return super().write(vals)

    @api.ondelete(at_uninstall=False)
    def _unlink_guard(self):
        for rec in self:
            if rec.session_id.results_published:
                raise ValidationError(_(
                    "A participant cannot be removed after the exam results have been published."))
            if len(rec.registration_id.line_ids) <= 1 and \
                    rec.registration_id.state in ('submitted', 'confirmed'):
                raise ValidationError(_(
                    "A registration must keep at least 1 participant."))
