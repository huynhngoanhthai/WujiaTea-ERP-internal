# -*- coding: utf-8 -*-
import calendar
from datetime import datetime, date
from dateutil.relativedelta import relativedelta
from enum import Enum
import json
import logging
import random
import re

import pandas as pd

from odoo import api, fields, models, _
# pyrefly: ignore [missing-import]
from odoo.exceptions import ValidationError, UserError
import re
# pyrefly: ignore [missing-import]
from markupsafe import Markup

from .posapp_client import PosAppClient
from odoo.addons.wujia_franchise_inspection.controllers.main import get_survey_translations
from .google_drive_client import GoogleDriveClient

_logger = logging.getLogger(__name__)


class RemediationState(str, Enum):
    NEED_REMEDIATION = 'need_remediation'
    REMEDIATED = 'remediated'
    DONE = 'done' 


class WujiaFranchiseInspection(models.Model):

    def _check_and_update_done_state(self):
        for rec in self:
            if rec.state == 'need_remediation':
                criteria_lines = rec.line_ids.filtered(lambda l: l.display_type == 'line' and not l.is_pass)
                # Phiếu chỉ hoàn thành nếu TẤT CẢ các dòng không đạt đều ở trạng thái DONE
                if not criteria_lines or all(l.remediation_state == RemediationState.DONE.value for l in criteria_lines):
                    rec.write({'state': 'done'})

    _name = 'wujia.franchise.inspection'
    _description = 'Franchise Store Inspection Sheet'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'id desc'

    def _get_report_base_filename(self):
        self.ensure_one()
        store_name = self.franchise_id.name or self.name or 'Store'
        plan_date = self.planned_date.strftime('%d-%m-%Y') if self.planned_date else fields.Date.today().strftime('%d-%m-%Y')
        return f"Franchise Inspection Report [{store_name}] [{plan_date}]"

    _sql_constraints = [
        ('name_uniq', 'unique(name)', 'The inspection name must be unique!'),
    ]

    name = fields.Char(string='Inspection Name', required=True, copy=False, tracking=True)

    submit_date = fields.Date(
        string='Submission Date',
        tracking=True,
    )
    confirm_date = fields.Date(
        string='Confirmation Date',
        tracking=True,
    )

    state = fields.Selection([
        ('draft', 'Draft'),
        ('in_progress', 'In Progress'),
        ('need_remediation', 'Need Remediation'),
        ('done', 'Done'),
        ('cancel', 'Cancelled')
    ], string='Status', default='draft', tracking=True)

    planned_date = fields.Date(
        string='Planned Date',
        tracking=True,
    )

    checklist_score = fields.Float(
        string='Checklist Score',
        compute='_compute_checklist_score',
        store=True,
        readonly=True,
        default=95.0,
        tracking=True,
    )

    exam_score = fields.Float(
        string='Staff Exam Score',
        compute='_compute_exam_score',
        store=True,
        aggregator='avg',
        tracking=True,
        help='Score calculated from blank fill-in exam questions.',
    )

    total_score = fields.Float(
        string='Total Score',
        compute='_compute_total_score',
        store=True,
        aggregator='avg',
        tracking=True,
        help='Total Score = Checklist Score + Staff Exam Score.',
    )

    grade_id = fields.Many2one(
        'wujia.franchise.inspection.grade',
        string='Grade',
        compute='_compute_grade',
        store=True,
        readonly=True,
        tracking=True,
    )
    
    next_due_date = fields.Date(
        string='Next Inspection Date',
        tracking=True,
    )

    next_schedule_id = fields.Many2one(
        'wujia.supervision.schedule',
        string='Next Supervision Schedule',
        ondelete='set null',
    )

    test_employee_name = fields.Char(
        string='Tested Employee',
        help='Store employee taking the exam (not required to be a system user).',
    )

    tenure = fields.Char(
        string='Tenure',
        help='Working tenure of the tested employee (e.g. 1 year, 6 months, 2 years).',
    )
    # Video Fields (Google Drive Storage)
    video = fields.Binary(
        string='Evidence Video',
        attachment=False,
        help='Select video file to automatically upload to Google Drive (not stored on server).',
    )
    video_filename = fields.Char(
        string='Video File Name',
        copy=False,
    )
    video_url = fields.Char(
        string='Google Drive Video URL',
        copy=False,
        tracking=True,
        help='Direct URL to view the inspection video on Google Drive.',
    )
    video_drive_file_id = fields.Char(
        string='Google Drive File ID',
        copy=False,
    )
    video_upload_state = fields.Selection([
        ('not_uploaded', 'No Video'),
        ('uploading', 'Uploading to Drive...'),
        ('uploaded', 'Uploaded to Google Drive'),
        ('error', 'Google Drive Upload Error')
    ], string='Video Status', default='not_uploaded', copy=False, tracking=True)

    is_google_drive_enabled = fields.Boolean(
        string='Is Google Drive Enabled',
        compute='_compute_is_google_drive_enabled',
    )

    def _is_google_drive_video_enabled(self):
        """Kiểm tra cấu hình hệ thống xem tính năng Google Drive Video có đang được kích hoạt không."""
        return self.env['ir.config_parameter'].sudo().get_param(
            'wujia_franchise_inspection.use_google_drive_video', 'False'
        ).lower() in ('true', '1', 't', 'yes')

    def _compute_is_google_drive_enabled(self):
        enabled = self._is_google_drive_video_enabled()
        for rec in self:
            rec.is_google_drive_enabled = enabled

    # Online Signature Fields
    signature_image = fields.Binary(
        string='Store Representative Signature',
        attachment=True,
        copy=False,
    )
    signature_date = fields.Datetime(
        string='Signature Date',
        copy=False,
    )
    inspector_signature_image = fields.Binary(
        string='Inspector Signature',
        attachment=True,
        copy=False,
    )

    # GPS / Geolocation Fields
    latitude = fields.Float(
        string='Latitude',
        digits=(10, 7),
        copy=False,
        tracking=True,
        help='Latitude coordinate of inspection',
    )
    longitude = fields.Float(
        string='Longitude',
        digits=(10, 7),
        copy=False,
        tracking=True,
        help='Longitude coordinate of inspection',
    )
    checkin_time = fields.Datetime(
        string='Check-in Time',
        copy=False,
        tracking=True,
        help='GPS location record time',
    )
    checkin_address = fields.Char(
        string='GPS Location',
        copy=False,
        tracking=True,
        help='GPS coordinates and accuracy information',
    )
    google_maps_url = fields.Char(
        string='Google Maps URL',
        compute='_compute_google_maps_url',
        help='Link to open inspection location on Google Maps',
    )

    @api.depends('latitude', 'longitude')
    def _compute_google_maps_url(self):
        for rec in self:
            if rec.latitude or rec.longitude:
                rec.google_maps_url = f"https://www.google.com/maps?q={rec.latitude},{rec.longitude}"
            else:
                rec.google_maps_url = False

    def action_open_google_maps(self):
        """Mở vị trí tọa độ GPS trên Google Maps."""
        self.ensure_one()
        if not (self.latitude or self.longitude):
            raise UserError(_('GPS coordinates are missing! Please click "Get GPS Location" first.'))
        return {
            'type': 'ir.actions.act_url',
            'url': f"https://www.google.com/maps?q={self.latitude},{self.longitude}",
            'target': 'new',
        }

    def action_update_gps_location(self, latitude, longitude, address=None):
        """Lưu trực tiếp tọa độ GPS vào CSDL."""
        self.ensure_one()
        vals = {
            'latitude': float(latitude),
            'longitude': float(longitude),
            'checkin_time': fields.Datetime.now(),
        }
        if address:
            vals['checkin_address'] = address
        self.write(vals)
        return True

    def _upload_video_to_google_drive(self, video_data, filename=None):
        """
        Uploads inspection video to Google Drive under 'wujia media/<store_code>/ks<YYYYMMDD>.mp4'.
        """
        self.ensure_one()

        store_code = self.franchise_id.code or self.franchise_id.name or 'UNKNOWN'
        store_code = re.sub(r'[^\w\-\.]', '_', str(store_code).strip())

        insp_date = self.planned_date or self.submit_date or fields.Date.today()
        date_str = insp_date.strftime('%Y%m%d')

        client = GoogleDriveClient()
        try:
            res = client.upload_inspection_video(
                video_data=video_data,
                store_code=store_code,
                date_str=date_str,
                original_filename=filename or self.video_filename
            )
            return {
                'video_url': res.get('webViewLink'),
                'video_drive_file_id': res.get('id'),
                'video_upload_state': 'uploaded',
                'video': False,
            }
        except Exception as e:
            _logger.error("Failed to upload video to Google Drive for inspection %s: %s", self.name, str(e))
            return {
                'video_upload_state': 'error',
                'video': False,
            }

    def action_open_drive_video(self):
        """Mở link xem video trực tiếp trên Google Drive trong tab mới."""
        self.ensure_one()
        if not self.video_url:
            raise UserError(_("This inspection survey does not have a Google Drive video link yet!"))
        return {
            'type': 'ir.actions.act_url',
            'url': self.video_url,
            'target': 'new',
        }

    def action_reupload_video_prompt(self):
        """Xóa link video hiện tại để cho phép người dùng chọn và tải lên video mới."""
        self.ensure_one()
        self.write({
            'video_url': False,
            'video_drive_file_id': False,
            'video_upload_state': 'not_uploaded',
            'video': False,
            'video_filename': False,
        })
        return True

    # RELATION 

    schedule_id = fields.Many2one(
        'wujia.supervision.schedule',
        string='Supervision Schedule',
        required=True,
        ondelete='cascade',
        tracking=True,
    )
    
    template_id = fields.Many2one(
        'wujia.franchise.inspection.template',
        string='Inspection Template',
        required=True,
        ondelete='restrict',
        tracking=True,
    )

    franchise_id = fields.Many2one(
        'wujia.franchise.management',
        string='Franchise Store',
        required=True,
        ondelete='restrict',
        tracking=True,
    )

    inspector_user_id = fields.Many2one(
        'res.users',
        string='Inspector',
        required=True,
        ondelete='restrict',
        default=lambda self: self.env.user,
        tracking=True,
    )

    previous_inspection_id = fields.Many2one(
        'wujia.franchise.inspection',
        string='Previous Inspection',
        compute='_compute_previous_inspection_id',
        store=True,
        ondelete='set null',
        readonly=True
    )

    store_appearance_issues = fields.Text(
        string='Store Appearance Issues & Key Remediations',
        tracking=True,
        help='Store poor appearance description & key deficiencies to be improved',
    )
    previous_store_appearance_issues = fields.Text(
        string='Previous Inspection Notes',
        compute='_compute_previous_store_appearance_issues',
        readonly=True,
        help='Store appearance issues and key remediations from previous inspection',
    )

    @api.depends('previous_inspection_id', 'previous_inspection_id.store_appearance_issues', 'franchise_id', 'planned_date')
    def _compute_previous_store_appearance_issues(self):
        for rec in self:
            if rec.previous_inspection_id and rec.previous_inspection_id.store_appearance_issues:
                rec.previous_store_appearance_issues = rec.previous_inspection_id.store_appearance_issues
            elif rec.franchise_id:
                domain = [
                    ('franchise_id', '=', rec.franchise_id.id),
                    ('store_appearance_issues', '!=', False),
                    ('store_appearance_issues', '!=', ''),
                ]
                current_id = rec._origin.id if rec._origin else (rec.id if isinstance(rec.id, int) else False)
                if current_id:
                    domain.append(('id', '!=', current_id))
                if rec.planned_date:
                    domain.append(('planned_date', '<=', rec.planned_date))
                prev = self.search(domain, order='planned_date desc, id desc', limit=1)
                rec.previous_store_appearance_issues = prev.store_appearance_issues if prev else False
            else:
                rec.previous_store_appearance_issues = False

    line_ids = fields.One2many(
        'wujia.franchise.inspection.line',
        'inspection_id',
        string='Inspection Details',
        copy=False,
    )

    exam_line_ids = fields.One2many(
        'wujia.franchise.inspection.exam.line',
        'inspection_id',
        string='Staff Exam Lines',
        copy=False,
    )

    report_line_ids = fields.One2many(
        'wujia.franchise.inspection.report.line',
        'inspection_id',
        string='Revenue Report Lines',
        copy=False,
    )

    attendance_line_ids = fields.One2many(
        'wujia.franchise.inspection.attendance.line',
        'inspection_id',
        string='Staff Attendance',
        domain=[('line_type', '=', 'attendance')],
        copy=False,
        help='List of employees present during inspection.',
    )

    passed_member_ids = fields.Many2many(
        'wujia.franchise.member',
        string='Passed Staff',
        compute='_compute_passed_member_ids',
        help='List of certified passed employees belonging to the store.',
    )

    present_count = fields.Integer(
        string='Present Staff',
        compute='_compute_present_count',
        store=True,
        help='Number of employees present at the store.',
    )

    passed_count = fields.Integer(
        string='Passed Staff Count',
        compute='_compute_passed_stats',
        store=False,
        help='Total number of passed employees.',
    )

    is_exam_submitted = fields.Boolean(
        string='Exam Submitted',
        default=False,
        copy=False,
    )

    exam_submit_date = fields.Datetime(
        string='Exam Submitted Date',
        copy=False,
    )

    inspection_chart_data = fields.Text(
        string='Inspection Chart Data',
        compute='_compute_inspection_chart_data',
    )

    @api.depends('attendance_line_ids.is_present')
    def _compute_present_count(self):
        for rec in self:
            rec.present_count = len(rec.attendance_line_ids.filtered('is_present'))

    @api.depends('franchise_id')
    def _compute_passed_member_ids(self):
        for rec in self:
            if rec.franchise_id:
                rec.passed_member_ids = self.env['wujia.franchise.member'].search([
                    ('franchise_id', '=', rec.franchise_id.id),
                    ('active', '=', True),
                    ('is_working', '=', True),
                    ('is_pass', '=', True),
                ])
            else:
                rec.passed_member_ids = False

    @api.depends('franchise_id', 'passed_member_ids')
    def _compute_passed_stats(self):
        for rec in self:
            rec.passed_count = len(rec.passed_member_ids)

    def _get_user_configured_signature(self, user):
        """Lấy chữ ký mẫu nếu hệ thống có module sign hoặc user đã cấu hình chữ ký."""
        if not user:
            return False
        # 1. Chữ ký cấu hình trực tiếp trong hồ sơ User
        if hasattr(user, 'inspection_signature') and user.inspection_signature:
            return user.inspection_signature
        # 2. Module sign (Odoo Enterprise) lưu ở user.sign_signature
        if hasattr(user, 'sign_signature') and user.sign_signature:
            return user.sign_signature
        # 2. Hoặc lưu ở user.digital_signature
        if hasattr(user, 'digital_signature') and user.digital_signature:
            return user.digital_signature
        # 3. Hoặc kiểm tra partner_id.signature nếu có dạng binary
        partner = getattr(user, 'partner_id', None)
        if partner and hasattr(partner, 'signature') and partner.signature:
            val = partner.signature
            if isinstance(val, bytes) or (isinstance(val, str) and not val.startswith('<')):
                return val
        return False

    @api.model
    def default_get(self, fields_list):
        res = super(WujiaFranchiseInspection, self).default_get(fields_list)
        if ('inspector_signature_image' in fields_list or not fields_list) and not res.get('inspector_signature_image'):
            sig = self._get_user_configured_signature(self.env.user)
            if sig:
                res['inspector_signature_image'] = sig
        franchise_id = res.get('franchise_id') or self.env.context.get('default_franchise_id')
        if franchise_id:
            members = self.env['wujia.franchise.member'].search([
                ('franchise_id', '=', franchise_id),
                ('active', '=', True),
                ('is_working', '=', True),
            ])
            att_commands = []
            seq = 10
            for m in members:
                user = m.user_id
                phone = getattr(user, 'phone', '') or getattr(m, 'phone', '') or ''
                line_vals = {
                    'sequence': seq,
                    'line_type': 'attendance',
                    'member_id': m.id,
                    'employee_name': user.name if user else (m.display_name or ''),
                    'role': m.role or 'staff',
                    'phone': phone,
                    'is_present': True,
                    'is_pass': m.is_pass,
                }
                att_commands.append(fields.Command.create(line_vals))
                seq += 10
            if 'attendance_line_ids' in fields_list or not fields_list:
                res['attendance_line_ids'] = att_commands
        return res

    @api.onchange('franchise_id')
    def _onchange_franchise_id_populate_attendance(self):
        """Tự động tải danh sách thành viên active của cửa hàng vào bảng điểm danh."""
        if self.franchise_id:
            self._compute_previous_inspection_id()
            if self.previous_inspection_id and self.line_ids:
                self._onchange_previous_inspection_id()
            members = self.env['wujia.franchise.member'].search([
                ('franchise_id', '=', self.franchise_id.id),
                ('active', '=', True),
                ('is_working', '=', True),
            ])
            att_commands = [fields.Command.clear()]
            seq = 10
            for m in members:
                user = m.user_id
                phone = getattr(user, 'phone', '') or getattr(m, 'phone', '') or ''
                att_commands.append(fields.Command.create({
                    'sequence': seq,
                    'line_type': 'attendance',
                    'member_id': m.id,
                    'employee_name': user.name if user else (m.display_name or ''),
                    'role': m.role or 'staff',
                    'phone': phone,
                    'is_present': True,
                    'is_pass': m.is_pass,
                }))
                seq += 10
            self.attendance_line_ids = att_commands
        else:
            self.attendance_line_ids = [fields.Command.clear()]

    @api.depends('franchise_id', 'template_id', 'total_score', 'state')
    def _compute_inspection_chart_data(self):
        for rec in self:
            if not rec.franchise_id or not rec.template_id:
                rec.inspection_chart_data = json.dumps({
                    'title': _("Supervision Score History (Last 10 Rounds)"),
                    'single_label': _("Score per Round"),
                    'avg_label': _("Average Score"),
                    'no_data_title': _("No Historical Data Yet!"),
                    'no_data_desc': _("Please select a Supervision Template or this store has no completed/remediation inspection sheets yet."),
                })
                continue
            
            # Lấy 10 phiếu giám sát gần nhất của cửa hàng này theo đúng Mẫu khảo sát (template_id)
            inspections = self.env['wujia.franchise.inspection'].search([
                ('franchise_id', '=', rec.franchise_id.id),
                ('template_id', '=', rec.template_id.id),
                ('state', 'in', ['done', 'need_remediation']),
                ('planned_date', '!=', False)
            ], order='planned_date desc, id desc', limit=10)
            
            # Sắp xếp theo thứ tự thời gian tăng dần từ cũ -> mới để vẽ biểu đồ
            inspections = inspections.sorted(key=lambda r: (r.planned_date, r.id))
            
            labels = []
            scores = []
            grades = []
            display_scores = []
            avg_scores = []
            
            if inspections:
                total_sum = sum(ins.total_score for ins in inspections)
                overall_avg = total_sum / len(inspections)
                
                for ins in inspections:
                    date_str = ins.planned_date.strftime('%d/%m/%Y') if ins.planned_date else ''
                    labels.append(date_str)
                    scores.append(ins.total_score)
                    grade_name = (ins.grade_id.name if ins.grade_id else '').strip()
                    grades.append(grade_name)

                    score_val = ins.total_score
                    score_str = f"{int(score_val)}" if score_val.is_integer() else f"{score_val:.1f}"
                    display_text = f"{score_str} ({grade_name})" if grade_name else score_str
                    display_scores.append(display_text)
                    avg_scores.append(round(overall_avg, 2))
            
            rec.inspection_chart_data = json.dumps({
                'labels': labels,
                'scores': scores,
                'grades': grades,
                'display_scores': display_scores,
                'avg_scores': avg_scores,
                'title': _("Supervision Score History (Last 10 Rounds)"),
                'single_label': _("Score per Round"),
                'avg_label': _("Average Score"),
                'no_data_title': _("No Historical Data Yet!"),
                'no_data_desc': _("Please select a Supervision Template or this store has no completed/remediation inspection sheets yet."),
            })

    @api.constrains('planned_date', 'franchise_id', 'state')
    def _check_inspection_constraints(self):
        today = fields.Date.context_today(self)
        for rec in self:
            if rec.state == 'cancel':
                continue
            if rec.planned_date and rec.planned_date > today:
                raise ValidationError(_(
                    "Cannot create or save inspection survey for a future date (%s)!\n"
                    "Inspection date has not arrived yet (Today: %s). You can create a Supervision Schedule in advance."
                ) % (rec.planned_date.strftime('%d/%m/%Y'), today.strftime('%d/%m/%Y')))
            
            if rec.franchise_id and rec.planned_date:
                duplicate = self.search([
                    ('franchise_id', '=', rec.franchise_id.id),
                    ('planned_date', '=', rec.planned_date),
                    ('state', '!=', 'cancel'),
                    ('id', '!=', rec.id)
                ], limit=1)
                if duplicate:
                    raise ValidationError(_(
                        "On the same date (%s), each store '%s' is only allowed to have at most 1 inspection survey!\n"
                        "An inspection survey (%s) already exists for this date."
                    ) % (rec.planned_date.strftime('%d/%m/%Y'), rec.franchise_id.name, duplicate.name))


    @api.model
    def _generate_inspection_name(self, franchise_id, schedule_id=None, seq_number=None):
        """
        Hàm sinh mã phiếu khảo sát dạng 'PGS-[mã cửa hàng]-[stt 4 chữ số]'.
        Nếu tạo từ Lịch giám sát (schedule_id), tên phiếu sẽ khớp 100% với mã lịch giám sát (thay LGS thành PGS).
        """
        if schedule_id:
            schedule = schedule_id if isinstance(schedule_id, models.Model) else self.env['wujia.supervision.schedule'].browse(schedule_id)
            if schedule.exists() and schedule.name:
                if schedule.name.startswith('LGS-'):
                    return schedule.name.replace('LGS-', 'PGS-', 1)
                return f"PGS-{schedule.name}"
        if not franchise_id:
            return 'PGS-STORE-0001'
        store = franchise_id if isinstance(franchise_id, models.Model) else self.env['wujia.franchise.management'].browse(franchise_id)
        if not store.exists():
            return 'PGS-STORE-0001'

        store_code = (store.code or store.name or 'STORE').strip().replace(' ', '_')

        if seq_number is None:
            seq_number = self.search_count([('franchise_id', '=', store.id)]) + 1

        candidate_name = f"PGS-{store_code}-{seq_number:04d}"

        # Kiểm tra trùng lặp: Nếu đã tồn tại candidate_name trong DB -> Gọi ĐỆ QUY tăng seq_number + 1
        if self.search_count([('name', '=', candidate_name)]):
            return self._generate_inspection_name(store, schedule_id=schedule_id, seq_number=seq_number + 1)

        return candidate_name

    @api.onchange('schedule_id', 'franchise_id')
    def _onchange_schedule_or_franchise_set_name(self):
        if self.schedule_id:
            self.name = self._generate_inspection_name(self.franchise_id, schedule_id=self.schedule_id)
        elif self.franchise_id:
            if not self.name or self.name.startswith('PGS-') or self.name.startswith('Khảo sát') or self.name == 'New':
                self.name = self._generate_inspection_name(self.franchise_id)

    @api.model_create_multi
    def create(self, vals_list):
        use_drive = self._is_google_drive_video_enabled()
        video_uploads = {}
        for idx, vals in enumerate(vals_list):
            if use_drive and vals.get('video'):
                video_uploads[idx] = (vals.pop('video'), vals.get('video_filename'))
            franchise_id = vals.get('franchise_id')
            schedule_id = vals.get('schedule_id')
            current_name = vals.get('name')
            # Tự động nạp chữ ký cấu hình của user nếu có, không có thì thôi
            if not vals.get('inspector_signature_image'):
                user_id = vals.get('confirmed_user_id')
                user = self.env['res.users'].browse(user_id) if user_id else self.env.user
                sig = self._get_user_configured_signature(user)
                if sig:
                    vals['inspector_signature_image'] = sig

            if not current_name or current_name == 'New' or current_name.startswith('Khảo sát') or not current_name.startswith('PGS-'):
                if schedule_id:
                    vals['name'] = self._generate_inspection_name(franchise_id, schedule_id=schedule_id)
                elif franchise_id:
                    vals['name'] = self._generate_inspection_name(franchise_id)
                elif not current_name:
                    count = self.search_count([]) + 1
                    vals['name'] = f"PGS-STORE-{count:04d}"

            # Tự động nạp line_ids từ template nếu chưa có trong vals
            template_id_val = vals.get('template_id')
            if template_id_val and ('line_ids' not in vals or not vals.get('line_ids')):
                tpl_rec = self.env['wujia.franchise.inspection.template'].browse(template_id_val)
                if tpl_rec:
                    lines_data = []
                    for t_line in tpl_rec.line_ids:
                        if t_line.display_type == 'section':
                            cat_name = t_line.category_id.name if t_line.category_id else (t_line.content or 'Section')
                            lines_data.append((0, 0, {
                                'sequence': t_line.sequence,
                                'display_type': 'section',
                                'template_line_id': t_line.id,
                                'category_id': t_line.category_id.id if t_line.category_id else False,
                                'content_snapshot': cat_name,
                            }))
                        else:
                            lines_data.append((0, 0, {
                                'sequence': t_line.sequence,
                                'display_type': 'line',
                                'template_line_id': t_line.id,
                                'category_id': t_line.category_id.id if t_line.category_id else False,
                                'content_snapshot': t_line.content or '',
                                'deduction_score_snapshot': t_line.deduction_score or 0.0,
                                'criterion_type_snapshot': t_line.criterion_type or 'normal',
                                'require_note_if_fail_snapshot': t_line.require_note_if_fail,
                                'require_evidence_if_fail_snapshot': t_line.require_evidence_if_fail,
                                'is_pass': True,
                                'result': 'pass',
                            }))
                    if lines_data:
                        vals['line_ids'] = lines_data

            # Tự động tạo 5 câu hỏi ngẫu nhiên cho bài kiểm tra nếu chưa có
            if 'exam_line_ids' not in vals or not vals.get('exam_line_ids'):
                exam_lines = self._generate_random_exam_lines()
                if exam_lines:
                    vals['exam_line_ids'] = exam_lines

            # Tự động nạp attendance_line_ids nếu chưa có trong vals
            if franchise_id and ('attendance_line_ids' not in vals or not vals.get('attendance_line_ids')):
                members = self.env['wujia.franchise.member'].search([
                    ('franchise_id', '=', franchise_id),
                    ('active', '=', True),
                    ('is_working', '=', True),
                ])
                att_lines = []
                seq = 10
                for m in members:
                    user = m.user_id
                    phone = getattr(user, 'phone', '') or getattr(m, 'phone', '') or ''
                    line_vals = {
                        'sequence': seq,
                        'line_type': 'attendance',
                        'member_id': m.id,
                        'employee_name': user.name if user else (m.display_name or ''),
                        'role': m.role or 'staff',
                        'phone': phone,
                        'is_present': True,
                        'is_pass': m.is_pass,
                    }
                    att_lines.append((0, 0, line_vals))
                    seq += 10
                if att_lines:
                    vals['attendance_line_ids'] = att_lines

        records = super(WujiaFranchiseInspection, self).create(vals_list)
        for idx, rec in enumerate(records):
            if idx in video_uploads:
                v_data, v_fname = video_uploads[idx]
                rec.sudo().write({'video_upload_state': 'uploading', 'video': False})
                rec._async_upload_video_to_google_drive(v_data, v_fname)
        records.mapped('franchise_id').sudo()._compute_latest_inspection_info()
        return records

   
    @api.depends('line_ids.is_pass', 'line_ids.result', 'line_ids.deduction_score_snapshot', 'line_ids.display_type')
    def _compute_checklist_score(self):
        """
        Mặc định điểm checklist là 95 điểm.
        Cứ mỗi tiêu chí Không đạt (is_pass == False hoặc result == 'fail'),
        sẽ bị trừ số điểm tương ứng (deduction_score_snapshot).
        Bỏ qua các dòng Section Header (display_type == 'section').
        """
        for rec in self:
            criteria_lines = rec.line_ids.filtered(lambda l: l.display_type == 'line')
            if not criteria_lines:
                if rec.template_id:
                    rec.checklist_score = rec.template_id.checklist_max_score
                else:
                    rec.checklist_score = 95.0
            else:
                total_deduction = sum(
                    line.deduction_score_snapshot
                    for line in criteria_lines
                    if not line.is_pass
                )
                rec.checklist_score = rec.template_id.checklist_max_score - total_deduction

    @api.onchange('template_id', 'franchise_id')
    def _onchange_template_id(self):
        """
        Tự động sao chép các dòng tiêu chí (bao gồm dòng Section) từ Mẫu khảo sát được chọn
        sang phiếu khảo sát theo đúng thứ tự đã cấu hình trong Template.
        Tự động tra cứu kết quả đợt khảo sát trước (nếu có).
        """
        if self.template_id:
            lines = []

            # Tra cứu phiếu khảo sát trước (cùng cửa hàng)
            self._compute_previous_inspection_id()
            prev_insp = self.previous_inspection_id

            for t_line in self.template_id.line_ids:
                code_raw = (t_line.criterion_code or '').strip()
                sub_code = code_raw.split('.', 1)[1].strip() if '.' in code_raw else ''

                if t_line.display_type == 'section':
                    cat_name = t_line.category_id.name if t_line.category_id else (t_line.content or _("Section"))
                    if sub_code:
                        section_content = f"[{sub_code}] {cat_name}"
                    else:
                        section_content = cat_name

                    lines.append((0, 0, {
                        'sequence': t_line.sequence,
                        'display_type': 'section',
                        'template_line_id': t_line.id,
                        'category_id': t_line.category_id.id if t_line.category_id else False,
                        'content_snapshot': section_content,
                    }))
                else:
                    prev_l_id = False
                    prev_res = False
                    prev_ded = 0.0

                    cnt = (t_line.content or '').strip()
                    if code_raw and cnt.startswith(code_raw):
                        cnt = cnt[len(code_raw):].lstrip('. :-')
                    elif '.' in cnt[:10] and cnt[:10].split('.', 1)[0].replace('.', '').isdigit():
                        cnt = cnt.split('.', 1)[1].strip()

                    if sub_code:
                        content_str = f"[{sub_code}] {cnt}" if cnt else f"[{sub_code}]"
                    else:
                        content_str = cnt

                    if prev_insp:
                        target_tid = t_line.id
                        match_lines = [
                            l for l in prev_insp.line_ids
                            if l.display_type == 'line' and l.template_line_id and l.template_line_id.id == target_tid
                        ]
                        if match_lines:
                            prev_l = match_lines[0]
                            prev_l_id = prev_l.id
                            prev_res = 'pass' if (prev_l.is_pass or prev_l.result == 'pass') else 'fail'
                            prev_ded = prev_l.deduction_score_snapshot

                    lines.append((0, 0, {
                        'sequence': t_line.sequence,
                        'display_type': 'line',
                        'template_line_id': t_line.id,
                        'category_id': t_line.category_id.id if t_line.category_id else False,
                        'content_snapshot': content_str,
                        'deduction_score_snapshot': t_line.deduction_score or 0.0,
                        'criterion_type_snapshot': t_line.criterion_type or 'normal',
                        'require_note_if_fail_snapshot': t_line.require_note_if_fail,
                        'require_evidence_if_fail_snapshot': t_line.require_evidence_if_fail,
                        'is_pass': True,
                        'result': 'pass',
                        'previous_line_id': prev_l_id,
                        'previous_result': prev_res,
                        'previous_deduction_score': prev_ded,
                    }))

            self.line_ids = [(5, 0, 0)] + lines

            if not self.exam_line_ids:
                exam_lines = self._generate_random_exam_lines()
                if exam_lines:
                    self.exam_line_ids = exam_lines

    @api.onchange('previous_inspection_id')
    def _onchange_previous_inspection_id(self):
        """
        Khi Phiếu khảo sát trước (previous_inspection_id) được cập nhật,
        tự động tra cứu và cập nhật lại Kết quả đợt trước theo đúng ID dòng tiêu chí (template_line_id).
        """
        if self.previous_inspection_id and self.line_ids:
            for line in self.line_ids:
                if line.display_type == 'section':
                    line.previous_line_id = False
                    line.previous_result = False
                    line.previous_deduction_score = 0.0
                    continue
                if line.template_line_id:
                    target_tid = line.template_line_id.id
                    match_lines = [
                        l for l in self.previous_inspection_id.line_ids
                        if l.display_type == 'line' and l.template_line_id and l.template_line_id.id == target_tid
                    ]
                    if match_lines:
                        line.previous_line_id = match_lines[0].id
                        line.previous_result = 'pass' if (match_lines[0].is_pass or match_lines[0].result == 'pass') else 'fail'
                        line.previous_deduction_score = match_lines[0].deduction_score_snapshot
                    else:
                        line.previous_line_id = False
                        line.previous_result = False
                        line.previous_deduction_score = 0.0

    @api.depends('exam_line_ids.point', 'exam_line_ids.is_correct')
    def _compute_exam_score(self):
        """Tự động tính tổng điểm bài kiểm tra từ các câu hỏi trả lời đúng."""
        for rec in self:
            rec.exam_score = sum(line.point for line in rec.exam_line_ids if line.is_correct)
            if rec.template_id:
                rec.exam_score = min(rec.template_id.exam_max_score, rec.exam_score)

    

    @api.onchange('checklist_score', 'exam_score')
    def _onchange_scores_update_total(self):
        """Khi điểm checklist hoặc điểm kiểm tra thay đổi, tự động tính lại tổng điểm và xếp loại lập tức."""
        for rec in self:
            rec.total_score = (rec.checklist_score or 0.0) + (rec.exam_score or 0.0)
            rec._compute_grade()
    
  

    def action_submit_exam(self):
        """
        Nộp bài kiểm tra nhân viên:
        - Yêu cầu phiếu khảo sát phải ở trạng thái 'Đang thực hiện' (in_progress).
        - So sánh đáp án trả lời của nhân viên với đáp án đúng snapshot.
        - Cập nhật điểm từng dòng: Đúng -> 1.0 (hoặc score), Sai/Bỏ trống -> 0.0.
        - Khóa bài làm và tính tổng điểm phiếu khảo sát.
        """
        for rec in self:
            if rec.state != 'in_progress':
                raise UserError(_("The inspection must be 'In Progress' to submit the staff exam!"))

            for line in rec.exam_line_ids:
                line._evaluate_answer()
                score_val = (line.quest_id.score or 1.0) if line.is_correct else 0.0
                line.write({
                    'is_correct': line.is_correct,
                    'point': score_val,
                    'is_locked': True,
                })
            
            rec.write({
                'is_exam_submitted': True,
                'exam_submit_date': fields.Datetime.now(),
            })
            
            rec._compute_exam_score()
            rec._compute_checklist_score()
            rec._compute_total_score()
            rec._compute_grade()
            
        return True

    def action_start(self):
        """Chuyển phiếu khảo sát sang trạng thái Đang thực hiện và đồng bộ Lịch giám sát"""
        for rec in self:
            rec.write({'state': 'in_progress'})
        return True

    def _validate_failed_lines(self):
        """
        Kiểm tra tính hợp lệ của các dòng tiêu chí không đạt (Fail):
        1. require_note_if_fail: nếu True thì phải có note.
        2. require_evidence_if_fail: nếu True thì phải có evidence_image (hình ảnh bằng chứng khi khảo sát).
        """
        for rec in self:
            for line in rec.line_ids:
                if line.display_type == 'line' and not line.is_pass:
                    criterion_name = line.content_snapshot or (line.template_line_id.content if line.template_line_id else _('Criterion'))
                    
                    req_note = line.require_note_if_fail or line.require_note_if_fail_snapshot
                    req_evidence = line.require_evidence_if_fail or line.require_evidence_if_fail_snapshot

                    if req_note and not line.note:
                        raise ValidationError(_(
                            'Criterion "%s" failed and requires a VIOLATION NOTE!\nPlease enter a note before proceeding.'
                        ) % criterion_name)
                    
                    if req_evidence and not line.evidence_image:
                        raise ValidationError(_(
                            'Criterion "%s" failed and requires EVIDENCE IMAGE!\nPlease upload evidence photo before proceeding.'
                        ) % criterion_name)

    def _validate_exam_lines(self):
        """
        Kiểm tra tính hợp lệ của bài kiểm tra kiến thức (exam_line_ids):
        Yêu cầu bài kiểm tra phải được bấm "Nộp bài kiểm tra" (is_exam_submitted = True) trước khi hoàn thành.
        """
        for rec in self:
            if rec.exam_line_ids and not rec.is_exam_submitted:
                raise ValidationError(_(
                    'Staff exam has not been submitted!\n'
                    'Please switch to the "Staff Exam" tab and click "Submit Exam" before completing.'
                ))

    def action_need_remediation(self):
        """Chuyển phiếu khảo sát sang trạng thái Cần khắc phục & cập nhật trạng thái khắc phục cho tất cả tiêu chí"""
        for rec in self:
            rec._validate_failed_lines()
            rec._validate_exam_lines()
            for line in rec.line_ids.filtered(lambda l: l.display_type == 'line'):
                if not line.is_pass or line.result == 'fail':
                    line.write({'remediation_state': RemediationState.NEED_REMEDIATION.value})
                else:
                    line.write({'remediation_state': RemediationState.DONE.value})
            rec.write({'state': 'need_remediation'})
        return True

    def action_done(self):
        """Hoàn thành phiếu khảo sát, tự động lưu Ngày xác nhận và chuyển Lịch giám sát sang Hoàn thành"""
        today = fields.Date.context_today(self)
        for rec in self:
            rec._validate_failed_lines()
            rec._validate_exam_lines()
            failed_lines = rec.line_ids.filtered(lambda l: l.display_type == 'line' and not l.is_pass)
            uncompleted_lines = failed_lines.filtered(lambda l: l.remediation_state != RemediationState.DONE.value)
            if uncompleted_lines:
                raise UserError(_("Cannot complete inspection! There are still %s violation criteria not marked Done.") % len(uncompleted_lines))
            rec.write({
                'state': 'done',
                'confirm_date': rec.confirm_date or today,
            })
        return True

    def action_cancel(self):
        """Hủy phiếu khảo sát và tự động chuyển Lịch giám sát sang Đã hủy"""
        for rec in self:
            rec.write({'state': 'cancel'})
        return True

    def action_draft(self):
        """Đặt lại phiếu khảo sát về trạng thái Nháp và đồng bộ Lịch giám sát"""
        for rec in self:
            rec.write({'state': 'draft'})
        return True

    def action_create_next_schedule(self):
        """
        Tạo hoặc mở Lịch giám sát tiếp theo dựa trên ngày chọn trong 'Lần kiểm tra kế tiếp' (next_due_date).
        """
        self.ensure_one()
        if not self.next_due_date:
            raise ValidationError(_('Please select a date in "Next Inspection Date" before creating a schedule!'))

        if not self.next_schedule_id:
            store_name = self.franchise_id.name or ''
            new_schedule = self.env['wujia.supervision.schedule'].create({
                'name': f"Next Supervision Schedule - {store_name}",
                'store_id': self.franchise_id.id,
                'user_id': self.inspector_user_id.id or self.env.user.id,
                'date': self.next_due_date,
                'state': 'draft',
                'note': f"Schedule automatically created from Inspection Sheet: {self.name}",
            })
            self.next_schedule_id = new_schedule.id

        return {
            'name': _('Next Supervision Schedule'),
            'type': 'ir.actions.act_window',
            'res_model': 'wujia.supervision.schedule',
            'res_id': self.next_schedule_id.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def _fetch_posapp_revenue_data(self):
        """
        Chỉ lấy dữ liệu thống kê doanh thu 3 tháng gần nhất từ PosApp API, KHÔNG lưu trực tiếp vào CSDL.
        Trả về danh sách dict các dòng để giao diện form/web hiển thị và người dùng bấm Lưu mới lưu.
        """
        self.ensure_one()
        if not self.franchise_id or not self.franchise_id.code:
            raise UserError(_("Franchise store has no Store Code configured for PosApp synchronization!"))

        shop_code = (self.franchise_id.code or '').strip()
        ref_date = self.planned_date or fields.Date.context_today(self)

        # Tính 3 tháng gần nhất trước ngày khảo sát
        date_ranges = []
        for i in range(1, 4):
            m_date = ref_date - relativedelta(months=i)
            year = m_date.year
            month = m_date.month
            last_day = calendar.monthrange(year, month)[1]
            date_ranges.append((
                f"{year:04d}-{month:02d}-01",
                f"{year:04d}-{month:02d}-{last_day:02d}"
            ))

        client = PosAppClient()
        try:
            result_groups = client.get_orders_by_date_ranges(
                date_ranges=date_ranges,
                shop_code=shop_code,
                max_workers=min(3, len(date_ranges))
            )
        except Exception as e:
            raise UserError(_("Error connecting to PosApp API: %s") % str(e))

        if not result_groups:
            raise UserError(_("Could not retrieve revenue data from PosApp for store '%s'. Please check your connection or store code!") % shop_code)

        # Sắp xếp các tháng theo thứ tự thời gian tăng dần
        result_groups = sorted(result_groups, key=lambda x: x.get('date', ''))

        lines_data = []
        seq = 10
        for group in result_groups:
            d_str = group.get('date')  # 'YYYY-MM'
            if not d_str:
                continue
            month_date = fields.Date.from_string(f"{d_str}-01")
            total_rev = float(group.get('total_amount', 0.0) or 0.0)
            total_app_amount = float(group.get('total_amount_app', 0.0) or 0.0)
            mini_app_orders = int(group.get('count_amount_mini_app', 0) or 0)

            # Tính phần trăm doanh thu từ app
            pct_app = round((total_app_amount / total_rev) * 100, 2) if total_rev > 0 else 0.0

            # Tính doanh thu trung bình ngày theo số ngày thực tế trong tháng
            period_days = calendar.monthrange(month_date.year, month_date.month)[1]
            rev_avg = round(total_rev / period_days, 2) if period_days > 0 else 0.0

            lines_data.append({
                'sequence': seq,
                'date_month': str(month_date),
                'month_val': month_date.strftime('%m'),
                'year_val': month_date.strftime('%Y'),
                'date_month_str': month_date.strftime('%m/%Y'),
                'revenue': total_rev,
                'revenue_avg': rev_avg,
                'percent_goods': 0.0,
                'total_app_sale': mini_app_orders,
                'percent_app_sale': pct_app,
            })
            seq += 10

        return lines_data

    def action_sync_posapp_revenue(self):
        """
        Lấy số liệu từ PosApp và lưu vào record.
        Trả về False để Odoo Web Client tự động cập nhật dữ liệu bảng One2many tại chỗ mượt mà,
        chỉ cập nhật đúng bảng đó mà không làm chớp/reload lại toàn bộ trang.
        """
        self.ensure_one()
        lines_data = self._fetch_posapp_revenue_data()

        commands = [(5, 0, 0)]
        for ld in lines_data:
            commands.append((0, 0, {
                'sequence': ld['sequence'],
                'date_month': fields.Date.from_string(ld['date_month']),
                'revenue': ld['revenue'],
                'revenue_avg': ld['revenue_avg'],
                'percent_goods': ld['percent_goods'],
                'total_app_sale': ld['total_app_sale'],
                'percent_app_sale': ld['percent_app_sale'],
            }))

        self.write({'report_line_ids': commands})

        # Gửi thông báo popup nhẹ qua Bus (không điều hướng hay chớp trang)
        self.env['bus.bus']._sendone(
            self.env.user.partner_id,
            'simple_notification',
            {
                'title': _('PosApp Sync Successful'),
                'message': _("Successfully loaded %s months of revenue data from PosApp!") % len(lines_data),
                'type': 'success',
                'sticky': False,
            }
        )

        return False

    def action_open_inspection_detail(self):
        """Mở trang Website chuyên dụng để thực hiện khảo sát Checklist độc lập"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_url',
            'url': f'/franchise/inspection/do/{self.id}',
            'target': 'self',
        }

    def write(self, vals):
        use_drive = self._is_google_drive_video_enabled()
        video_data = None
        video_filename = None
        if use_drive and 'video' in vals and vals.get('video'):
            video_data = vals.pop('video')
            video_filename = vals.get('video_filename')

        if 'name' in vals and not self.env.su:
            for rec in self:
                if rec.name and vals['name'] != rec.name:
                    raise ValidationError(_("Cannot change Inspection Name (%s) once created!") % rec.name)

        if vals.get('state') == 'need_remediation':
            for rec in self:
                for line in rec.line_ids.filtered(lambda l: l.display_type == 'line'):
                    if not line.is_pass or line.result == 'fail':
                        if line.remediation_state != RemediationState.REMEDIATED.value and line.remediation_state != RemediationState.DONE.value:
                            line.remediation_state = RemediationState.NEED_REMEDIATION.value
                    else:
                        line.remediation_state = RemediationState.DONE.value

        if vals.get('state') == 'done':
            for rec in self:
                failed_lines = rec.line_ids.filtered(lambda l: l.display_type == 'line' and not l.is_pass)
                uncompleted_lines = failed_lines.filtered(lambda l: l.remediation_state != RemediationState.DONE.value)
                if uncompleted_lines:
                    raise UserError(_("Cannot complete inspection! There are still %s violation criteria not marked Done.") % len(uncompleted_lines))

        if vals.get('state') == 'done' and 'confirm_date' not in vals:
            vals['confirm_date'] = fields.Date.context_today(self)
        res = super().write(vals)
        if 'state' in vals:
            for rec in self:
                if rec.schedule_id:
                    schedule_state_keys = dict(rec.schedule_id._fields['state'].selection)
                    if vals['state'] in schedule_state_keys and rec.schedule_id.state != vals['state']:
                        rec.schedule_id.state = vals['state']
        if any(f in vals for f in ('state', 'total_score', 'grade_id', 'planned_date', 'franchise_id')):
            self.mapped('franchise_id').sudo()._compute_latest_inspection_info()
        if video_data:
            for rec in self:
                rec.sudo().write({'video_upload_state': 'uploading', 'video': False})
                rec._async_upload_video_to_google_drive(video_data, video_filename)
        return res

    def unlink(self):
        stores = self.mapped('franchise_id').sudo()
        res = super().unlink()
        if stores:
            stores._compute_latest_inspection_info()
        return res

    def _generate_random_exam_lines(self):
        """Tự động lấy ngẫu nhiên danh sách câu hỏi từ wujia.franchise.inspection.question sao cho tổng điểm bằng exam_max_score"""
        questions = self.env['wujia.franchise.inspection.question'].search([('active', '=', True)])
        if not questions:
            return []
        
        target_exam_score = self.template_id.exam_max_score if (self.template_id and self.template_id.exam_max_score) else 5.0
        
        all_q = list(questions)
        total_available_score = sum(q.score or 1.0 for q in all_q)
        
        if total_available_score <= target_exam_score:
            selected_questions = all_q
        else:
            random.shuffle(all_q)
            selected_questions = []
            
            def backtrack(idx, current_sum, path):
                if abs(current_sum - target_exam_score) < 0.001:
                    return path
                if idx >= len(all_q) or current_sum > target_exam_score + 0.001:
                    return None
                
                res = backtrack(idx + 1, current_sum + (all_q[idx].score or 1.0), path + [all_q[idx]])
                if res is not None:
                    return res
                
                res = backtrack(idx + 1, current_sum, path)
                if res is not None:
                    return res
                
                return None
            
            found = backtrack(0, 0.0, [])
            if found is not None:
                selected_questions = found
            else:
                current_sum = 0.0
                for q in all_q:
                    score = q.score or 1.0
                    if current_sum + score <= target_exam_score + 0.001:
                        selected_questions.append(q)
                        current_sum += score

        exam_lines = []
        seq = 10
        for q in selected_questions:
            correct_snap = q.correct_answers_text
            if not correct_snap and q.correct_answers:
                if isinstance(q.correct_answers, list):
                    lines = []
                    for item in q.correct_answers:
                        if isinstance(item, list):
                            lines.append('; '.join(str(x) for x in item))
                        elif item:
                            lines.append(str(item))
                    correct_snap = '\n'.join(lines)

            exam_lines.append((0, 0, {
                'sequence': seq,
                'quest_id': q.id,
                'quest_code_snapshot': q.code or f"QUEST-{q.id}",
                'quest_content_snapshot': q.question_text or '',
                'correct_answer_snapshot': correct_snap or '',
                'answer': '',
                'is_correct': False,
                'point': q.score or 1.0,
            }))
            seq += 10
        return exam_lines

    @api.depends('franchise_id', 'planned_date')
    def _compute_previous_inspection_id(self):
        """
        Tự động lấy phiếu khảo sát gần nhất bất kỳ của cùng Cửa hàng (franchise_id).
        """
        for rec in self:
            if not rec.franchise_id:
                rec.previous_inspection_id = False
                continue

            current_id = rec._origin.id if rec._origin else (rec.id if isinstance(rec.id, int) else False)
            base_domain = [
                ('franchise_id', '=', rec.franchise_id.id),
                ('state', '!=', 'cancel'),
            ]
            if current_id:
                base_domain.append(('id', '!=', current_id))

            prev_rec = False
            if rec.planned_date:
                prev_rec = self.search(base_domain + [('planned_date', '<=', rec.planned_date)], order='planned_date desc, id desc', limit=1)
            if not prev_rec:
                prev_rec = self.search(base_domain, order='planned_date desc, id desc', limit=1)

            rec.previous_inspection_id = prev_rec.id if prev_rec else False
    
    confirmed_user_id = fields.Many2one('res.users',
        string='System Confirmer',
        required=True,
        ondelete='restrict',
        default=lambda self: self.env.user
    )
    confirmed_member_id = fields.Many2one('wujia.franchise.member',
        string='Store Manager Confirmer',
        ondelete='restrict',
    )

    @api.onchange('confirmed_user_id')
    def _onchange_confirmed_user_id_signature(self):
        if self.confirmed_user_id:
            sig = self._get_user_configured_signature(self.confirmed_user_id)
            if sig:
                self.inspector_signature_image = sig

    @api.onchange('schedule_id')
    def _onchange_schedule_id(self):
        if self.schedule_id:
            self.planned_date = self.schedule_id.date
            if self.schedule_id.store_id:
                self.franchise_id = self.schedule_id.store_id
                self._onchange_franchise_id_populate_attendance()
            if self.schedule_id.user_id:
                self.inspector_user_id = self.schedule_id.user_id

    @api.onchange('line_ids', 'exam_line_ids')
    def _onchange_lines_update_scores(self):
        """
        Cập nhật REAL-TIME lập tức khi người dùng bật/tắt Đánh giá Đạt hoặc trả lời bài kiểm tra
        ngay trên giao diện form mà chưa cần bấm nút Lưu (Save).
        """
        for rec in self:
            rec._compute_checklist_score()
            rec._compute_exam_score()
            rec.total_score = (rec.checklist_score or 0.0) + (rec.exam_score or 0.0)
            rec._compute_grade()
    
    @api.depends(
        'checklist_score',
        'exam_score',
        'line_ids.is_pass',
        'line_ids.deduction_score_snapshot',
        'line_ids.display_type',
        'exam_line_ids.is_correct',
        'exam_line_ids.point',
        'is_exam_submitted'
    )
    def _compute_total_score(self):
        """
        Tự động chạy khi 'checklist_score', 'exam_score' hoặc các dòng tiêu chí thay đổi.
        Cộng 2 điểm thành phần (checklist_score + exam_score) để tạo thành total_score.
        """
        for rec in self:
            rec.total_score = (rec.checklist_score or 0.0) + (rec.exam_score or 0.0)

    @api.depends(
        'total_score',
        'checklist_score',
        'exam_score',
        'line_ids.is_pass',
        'line_ids.deduction_score_snapshot',
        'exam_line_ids.is_correct'
    )
    def _compute_grade(self):
        """
        Tự động chạy khi 'total_score' thay đổi.
        Tính 'grade_id' dựa trên 'total_score' bằng cách tra cứu model cấu hình.
        """
        GradeModel = self.env['wujia.franchise.inspection.grade'].sudo()
        all_grades = GradeModel.search([], order='min_score desc')
        for rec in self:
            score = rec.total_score or 0.0
            matched_grade = GradeModel
            for grade in all_grades:
                if grade.min_score <= score <= grade.max_score:
                    matched_grade = grade
                    break
            rec.grade_id = matched_grade



    def action_print_pdf(self):
        self.ensure_one()
        action = (self.env.ref('wujia_franchise_inspection.action_report_franchise_inspection', raise_if_not_found=False) or self.env.ref('wujia_franchise.action_report_franchise_inspection')).report_action(self)
        store_code = self.franchise_id.code or self.franchise_id.name or ''
        plan_date = self.planned_date.strftime('%d-%m-%Y') if self.planned_date else ''
        custom_name = f"Franchise Inspection Report [{store_code}] [{plan_date}]"
        action['name'] = custom_name
        action['display_name'] = custom_name
        return action

    def get_all_translations_json(self):
        """Trả về toàn bộ từ điển 3 ngôn ngữ (vi_VN, zh_CN, th_TH) dạng JSON để frontend chuyển đổi tức thì."""
        data = {
            'vi_VN': get_survey_translations('vi_VN'),
            'zh_CN': get_survey_translations('zh_CN'),
            'th_TH': get_survey_translations('th_TH'),
        }
        return json.dumps(data, ensure_ascii=False)

    def get_report_translations(self, lang=None):
        try:
            target_lang = lang or self.env.context.get('lang') or self.env.user.lang or 'vi_VN'
            return get_survey_translations(target_lang)
        except Exception:
            return {}


class WujiaFranchiseInspectionLine(models.Model):

    def action_toggle_remediation_state(self):
        for line in self:
            if line.remediation_state == RemediationState.DONE.value:
                line.write({'remediation_state': RemediationState.NEED_REMEDIATION.value})
            else:
                line.write({'remediation_state': RemediationState.DONE.value})
        return True

    _name = 'wujia.franchise.inspection.line'
    _description = 'Inspection Line Detail'
    _order = 'sequence, id'

    sequence = fields.Integer(string='Sequence', default=10)
    display_type = fields.Selection([
        ('section', 'Section'),
        ('line', 'Line'),
    ], default='line', help="Technical field to group section headers")

    content_snapshot = fields.Text(
        string='Checklist Content',
    )

    deduction_score_snapshot = fields.Float(
        string='Deduction Score',
        default=0.0,
    )

    criterion_type_snapshot = fields.Char(
        string='Criterion Type',
        default='normal',
    )

    is_pass = fields.Boolean(
        string='Passed (Pass)',
        default=True,
    )

    result = fields.Selection(
        selection=[
            ('pass', 'Pass'),
            ('fail', 'Fail')
        ],
        string='Result',
        default='pass',
        required=True,
    )

    note = fields.Text(
        string='Violation Note (Admin)',
    )

    remediation_state = fields.Selection([
        (RemediationState.NEED_REMEDIATION.value, 'Need Remediation'),
        (RemediationState.REMEDIATED.value, 'Remediated'),
        (RemediationState.DONE.value, 'Done'),
    ], string='Remediation Status', tracking=True)

    remediation_note = fields.Text(
        string='Remediation Note (Store)',
        help='Remediation notes / feedback submitted by store via Portal.'
    )

    evidence_image = fields.Binary(
        string='Evidence Photo (Inspection)',
        attachment=True,
        help='Violation evidence photo captured during inspection.'
    )

    remediation_image = fields.Binary(
        string='Remediation Photo',
        attachment=True,
        help='Photo showing results after store completed remediation.'
    )

    require_note_if_fail = fields.Boolean(
        string='Require Note If Fail',
        related='template_line_id.require_note_if_fail',
        readonly=True,
        store=True,
    )

    require_evidence_if_fail = fields.Boolean(
        string='Require Evidence If Fail',
        related='template_line_id.require_evidence_if_fail',
        readonly=True,
        store=True,
    )

    require_note_if_fail_snapshot = fields.Boolean(
        string='Require Note Snapshot',
        default=False,
    )

    require_evidence_if_fail_snapshot = fields.Boolean(
        string='Require Evidence Snapshot',
        default=False,
    )
    
    # RELATION 
    inspection_id = fields.Many2one(
        'wujia.franchise.inspection',
        string='Inspection Sheet',
        required=True,
        ondelete='cascade',
    )

    template_line_id = fields.Many2one(
        'wujia.franchise.inspection.template.line',
        string='Inspection Criterion',
        required=False,
        ondelete='set null',
    )

    template_id = fields.Many2one(
        'wujia.franchise.inspection.template',
        related='inspection_id.template_id',
        string='Inspection Template',
        store=True,
        readonly=True,
    )

    franchise_id = fields.Many2one(
        'wujia.franchise.management',
        related='inspection_id.franchise_id',
        string='Franchise Store',
        store=True,
        readonly=True,
    )

    planned_date = fields.Date(
        related='inspection_id.planned_date',
        string='Inspection Date',
        store=True,
        readonly=True,
    )

    pass_count = fields.Integer(
        string='Pass Count',
        compute='_compute_pass_fail_count',
        store=True,
    )

    fail_count = fields.Integer(
        string='Violation Count',
        compute='_compute_pass_fail_count',
        store=True,
    )

    line_count = fields.Integer(
        string='Inspection Count',
        default=1,
    )

    category_id = fields.Many2one(
        'wujia.franchise.inspection.category',
        string='Section Category',
        ondelete='restrict',
    )

    previous_line_id = fields.Many2one(
        'wujia.franchise.inspection.line',
        string='Previous Line',
        compute='_compute_previous_line_info',
        store=True,
        readonly=True,
    )

    previous_result = fields.Selection(
        selection=[
            ('pass', 'Pass'),
            ('fail', 'Fail')
        ],
        string='Previous Result',
        compute='_compute_previous_line_info',
        store=True,
        readonly=True,
    )

    previous_deduction_score = fields.Float(
        string='Previous Deduction Score',
        compute='_compute_previous_line_info',
        store=True,
        readonly=True,
    )

    previous_inspection_id = fields.Many2one(
        'wujia.franchise.inspection',
        related='inspection_id.previous_inspection_id',
        string='Previous Inspection',
        readonly=True,
    )
    
    content_class = fields.Char(
        string="CSS Class for Content", 
        compute="_compute_content_class",
    )
    
    @api.onchange('is_pass')
    def _onchange_is_pass(self):
        if self.is_pass:
            self.result = 'pass'
        else:
            self.result = 'fail'

    @api.onchange('result')
    def _onchange_result(self):
        if self.result == 'pass':
            self.is_pass = True
        else:
            self.is_pass = False
    
 
    @api.onchange('is_pass', 'result')
    def _onchange_is_pass_remediation_state(self):
        if self.is_pass or self.result == 'pass':
            self.remediation_state = RemediationState.DONE.value
        else:
            if not self.remediation_state or self.remediation_state == RemediationState.DONE.value:
                self.remediation_state = RemediationState.NEED_REMEDIATION.value
    
   

    @api.depends('is_pass', 'result', 'display_type')
    def _compute_pass_fail_count(self):
        for rec in self:
            if rec.display_type == 'line':
                rec.pass_count = 1 if (rec.is_pass or rec.result == 'pass') else 0
                rec.fail_count = 0 if (rec.is_pass or rec.result == 'pass') else 1
                rec.line_count = 1
            else:
                rec.pass_count = 0
                rec.fail_count = 0
                rec.line_count = 0

   

    def action_view_previous_inspection(self):
        """Mở popup Form View xem duy nhất 1 dòng tiêu chí đợt trước (Readonly)"""
        self.ensure_one()
        if not self.previous_line_id:
            raise ValidationError(_('No historical data found for this criterion in previous inspection!'))
        return {
            'name': _('Previous Criterion: %s') % (self.content_snapshot or ''),
            'type': 'ir.actions.act_window',
            'res_model': 'wujia.franchise.inspection.line',
            'res_id': self.previous_line_id.id,
            'view_mode': 'form',
            'target': 'new',
            'context': {'create': False, 'edit': False},
        }

    # 2. Phương thức tính toán class
    @api.depends('display_type')
    def _compute_content_class(self):
        for line in self:
            # Kiểm tra nếu là dòng Section
            if line.display_type == 'section':
                line.content_class = 'text-center fw-bold d-block w-100 py-1'
            else:
                line.content_class = ''

    @api.depends('inspection_id.previous_inspection_id', 'template_line_id')
    def _compute_previous_line_info(self):
        """
        Tự động liên kết dòng tiêu chí đợt trước (previous_line_id) theo đúng ID Mẫu tiêu chí (template_line_id),
        đồng thời lưu trữ luôn Kết quả đợt trước (previous_result) và Điểm trừ đợt trước (previous_deduction_score).
        """
        for rec in self:
            if rec.display_type == 'section':
                rec.previous_line_id = False
                rec.previous_result = False
                rec.previous_deduction_score = 0.0
                continue

            prev_insp = rec.inspection_id.previous_inspection_id if rec.inspection_id else False
            if prev_insp and rec.template_line_id:
                target_tid = rec.template_line_id.id
                match_lines = [
                    l for l in prev_insp.line_ids
                    if l.display_type == 'line' and l.template_line_id and l.template_line_id.id == target_tid
                ]
                if match_lines:
                    prev_l = match_lines[0]
                    rec.previous_line_id = prev_l.id
                    rec.previous_result = 'pass' if (prev_l.is_pass or prev_l.result == 'pass') else 'fail'
                    rec.previous_deduction_score = prev_l.deduction_score_snapshot
                else:
                    rec.previous_line_id = False
                    rec.previous_result = False
                    rec.previous_deduction_score = 0.0
            else:
                rec.previous_line_id = False
                rec.previous_result = False
                rec.previous_deduction_score = 0.0

    @api.onchange('template_line_id')
    def _onchange_template_line_id(self):
        """
        Khi chọn Mẫu tiêu chí (template_line_id), tự động nạp nội dung, điểm trừ,
        loại tiêu chí và danh mục vào các trường snapshot tương ứng.
        """
        if self.template_line_id:
            self.category_id = self.template_line_id.category_id
            self.content_snapshot = self.template_line_id.content
            self.deduction_score_snapshot = self.template_line_id.deduction_score
            self.criterion_type_snapshot = self.template_line_id.criterion_type
            self.require_note_if_fail_snapshot = self.template_line_id.require_note_if_fail
            self.require_evidence_if_fail_snapshot = self.template_line_id.require_evidence_if_fail

    @api.model_create_multi
    def create(self, vals_list):
        """
        Bảo đảm dữ liệu content_snapshot, deduction_score_snapshot, criterion_type_snapshot
        và template_line_id luôn được lưu chính xác và vĩnh viễn vào CSDL khi bấm Lưu (Save).
        """
        for vals in vals_list:
            if vals.get('display_type') == 'section':
                continue

            # Đồng bộ result chuẩn xác theo is_pass
            if 'is_pass' in vals:
                vals['result'] = 'pass' if vals['is_pass'] else 'fail'

            # 1. Tự động phục hồi template_line_id nếu web client truyền null/False
            if not vals.get('template_line_id') and vals.get('content_snapshot'):
                insp = False
                if vals.get('inspection_id'):
                    insp = self.env['wujia.franchise.inspection'].browse(vals['inspection_id'])
                
                if insp and insp.exists() and insp.template_id:
                    t_line = insp.template_id.line_ids.filtered(
                        lambda l: l.content == vals['content_snapshot']
                    )
                    if t_line:
                        vals['template_line_id'] = t_line[0].id

                if not vals.get('template_line_id'):
                    t_line = self.env['wujia.franchise.inspection.template.line'].search([
                        ('content', '=', vals['content_snapshot'])
                    ], limit=1)
                    if t_line:
                        vals['template_line_id'] = t_line.id

            # 2. Điền thông tin snapshot từ template_line_id
            if vals.get('template_line_id'):
                t_line = self.env['wujia.franchise.inspection.template.line'].browse(vals['template_line_id'])
                if t_line.exists():
                    if not vals.get('category_id') and t_line.category_id:
                        vals['category_id'] = t_line.category_id.id
                    if not vals.get('content_snapshot'):
                        vals['content_snapshot'] = t_line.content
                    if 'deduction_score_snapshot' not in vals:
                        vals['deduction_score_snapshot'] = t_line.deduction_score
                    if not vals.get('criterion_type_snapshot'):
                        vals['criterion_type_snapshot'] = t_line.criterion_type
                    if 'require_note_if_fail_snapshot' not in vals:
                        vals['require_note_if_fail_snapshot'] = t_line.require_note_if_fail
                    if 'require_evidence_if_fail_snapshot' not in vals:
                        vals['require_evidence_if_fail_snapshot'] = t_line.require_evidence_if_fail

            # 3. Tự động phục hồi dòng đợt trước (previous_line_id)
            if vals.get('inspection_id') and vals.get('template_line_id') and not vals.get('previous_result'):
                insp = self.env['wujia.franchise.inspection'].browse(vals['inspection_id'])
                if insp.exists() and insp.previous_inspection_id:
                    target_tid = vals['template_line_id']
                    match_l = [
                        l for l in insp.previous_inspection_id.line_ids
                        if l.display_type == 'line' and l.template_line_id and l.template_line_id.id == target_tid
                    ]
                    if match_l:
                        vals['previous_line_id'] = match_l[0].id
                        vals['previous_result'] = 'pass' if match_l[0].is_pass else 'fail'
                        vals['previous_deduction_score'] = match_l[0].deduction_score_snapshot

        return super().create(vals_list)

    def write(self, vals):
        if vals.get('state') == 'need_remediation':
            for rec in self:
                for line in rec.line_ids.filtered(lambda l: l.display_type == 'line'):
                    if not line.is_pass or line.result == 'fail':
                        if line.remediation_state != RemediationState.REMEDIATED.value and line.remediation_state != RemediationState.DONE.value:
                            line.remediation_state = RemediationState.NEED_REMEDIATION.value
                    else:
                        line.remediation_state = RemediationState.DONE.value

        if vals.get('state') == 'done':
            for rec in self:
                failed_lines = rec.line_ids.filtered(lambda l: l.display_type == 'line' and not l.is_pass)
                uncompleted_lines = failed_lines.filtered(lambda l: l.remediation_state != RemediationState.DONE.value)
                if uncompleted_lines:
                    raise UserError(_("Cannot complete inspection! There are still %s violation criteria not marked Done.") % len(uncompleted_lines))

        if 'is_pass' in vals:
            vals['result'] = 'pass' if vals['is_pass'] else 'fail'

        if not vals.get('template_line_id') and vals.get('content_snapshot'):
            t_line = self.env['wujia.franchise.inspection.template.line'].search([
                ('content', '=', vals['content_snapshot'])
            ], limit=1)
            if t_line:
                vals['template_line_id'] = t_line.id

        if 'template_line_id' in vals and vals['template_line_id']:
            t_line = self.env['wujia.franchise.inspection.template.line'].browse(vals['template_line_id'])
            if t_line.exists():
                if 'category_id' not in vals and t_line.category_id:
                    vals['category_id'] = t_line.category_id.id
                if 'content_snapshot' not in vals:
                    vals['content_snapshot'] = t_line.content
                if 'deduction_score_snapshot' not in vals:
                    vals['deduction_score_snapshot'] = t_line.deduction_score
                if 'criterion_type_snapshot' not in vals:
                    vals['criterion_type_snapshot'] = t_line.criterion_type
        return super().write(vals)

    @api.depends('template_line_id', 'content_snapshot', 'display_type')
    def _compute_display_name(self):
        """
        Tự động tính toán tên hiển thị ngắn gọn cho bản ghi.
        Lấy từ template_line_id và content_snapshot.
        """
        for rec in self:
            if rec.display_type == 'section':
                rec.display_name = rec.content_snapshot or _("Criterion Category")
            elif rec.template_line_id:
                code = rec.template_line_id.criterion_code or ''
                rec.display_name = f"[{code}] {rec.content_snapshot or ''}" if code else (rec.content_snapshot or '')
            else:
                rec.display_name = rec.content_snapshot or _("Undefined Criterion")

class WujiaFranchiseInspectionReportLine(models.Model):
    _name = 'wujia.franchise.inspection.report.line'
    _description = 'Inspection Financial Report Line (3 Months)'
    _order = 'sequence, id'

    sequence = fields.Integer(string='Sequence', default=10)

    date_month = fields.Date(
        string='Month (MM/YYYY)',
        required=True,
    )
    
    days_of_month = fields.Integer(
        string='Days in Month',
        compute='_compute_days_of_month',
        store=True,
    )

    revenue = fields.Float(
        string='Revenue',
        required=True,
    )

    revenue_avg = fields.Float(
        string='Daily Average Revenue',
        compute='_compute_revenue_avg',
        store=True,
        readonly=False,
    )

    percent_goods = fields.Float(
        string='Goods Ratio (%)',
    )

    total_app_sale = fields.Integer(
        string='Total Mini App Orders',
    )

    percent_app_sale = fields.Float(
        string='App Orders Ratio (%)',
    )

    # RELATION
    inspection_id = fields.Many2one(
        'wujia.franchise.inspection',
        string='Inspection Sheet',
        required=True,
        ondelete='cascade',
    )

    @api.depends('date_month')
    def _compute_days_of_month(self):
        for rec in self:
            if rec.date_month:
                try:
                    period = pd.Period(rec.date_month)
                    rec.days_of_month = period.days_in_month
                except Exception:
                    rec.days_of_month = 30
            else:
                rec.days_of_month = 0

    @api.depends('revenue', 'days_of_month')
    def _compute_revenue_avg(self):
        for rec in self:
            if rec.days_of_month and rec.days_of_month > 0:
                rec.revenue_avg = round(rec.revenue / rec.days_of_month, 2)
            else:
                rec.revenue_avg = 0.0


    
class WujiaFranchiseInspectionExamLine(models.Model):
    _name = 'wujia.franchise.inspection.exam.line'
    _description = 'Staff Exam Inspection Line'
    _order = 'sequence, id'

    sequence = fields.Integer(
        string='Sequence',
        default=10,
    )

    quest_code_snapshot = fields.Char(
        string='Question Code',
        required=True,
    )

    quest_content_snapshot = fields.Text(
        string='Question Text',
        required=True,
    )

    correct_answer_snapshot = fields.Text(
        string='Correct Answer',
    )
    answer = fields.Text(
        string='Employee Answer',
    )

    is_correct = fields.Boolean(
        string='Is Correct',
        default=False,
    )
    point = fields.Float(
        string='Score',
        default=0.0,
    )

    is_locked = fields.Boolean(
        string='Locked',
        default=False,
    )

    # RELATION
    inspection_id = fields.Many2one(
        'wujia.franchise.inspection',
        string='Inspection Sheet',
        required=True,
        ondelete='cascade',
    )
    quest_id = fields.Many2one(
        'wujia.franchise.inspection.question',
        string='Question',
        required=True,
        ondelete='cascade',
    )

    # DISPLAY
    _point_return = fields.Float(
        string='Score',
        compute='_compute_point',
    )

    @api.depends('is_correct', 'quest_id')
    def _compute_point(self):
        for rec in self:
            if rec.is_correct:
                if rec.quest_id and rec.quest_id.score:
                    rec._point_return = rec.quest_id.score
                else:
                    rec._point_return = 1.0
            else:
                rec._point_return = 0.0

    @api.onchange('answer')
    def _onchange_answer(self):
        """Tự động kiểm tra đáp án trả lời với đáp án đúng trong thư viện câu hỏi"""
        self._evaluate_answer()

    def _evaluate_answer(self):
        """So sánh đáp án trả lời của nhân viên với đáp án đúng snapshot"""
        for rec in self:
            max_score = rec.quest_id.score if (rec.quest_id and rec.quest_id.score) else 1.0
            if not rec.answer:
                rec.is_correct = False
                rec.point = 0.0
                continue
            
            ans_raw = str(rec.answer).strip()
            if not ans_raw:
                rec.is_correct = False
                rec.point = 0.0
                continue

            if '\n' in ans_raw:
                user_lines = [l.strip() for l in ans_raw.splitlines()]
            else:
                user_lines = [l.strip() for l in re.split(r'[\n,;]+', ans_raw)]

            is_right = False

            # 1. Ưu tiên kiểm tra dữ liệu JSON correct_answers từ quest_id
            if rec.quest_id and rec.quest_id.correct_answers:
                val = rec.quest_id.correct_answers
                if isinstance(val, list) and val:
                    if len(val) > 1:
                        if len(user_lines) >= len(val):
                            all_matched = True
                            for idx, target in enumerate(val):
                                target_list = [str(x).strip().lower() for x in (target if isinstance(target, list) else [target])]
                                if idx < len(user_lines):
                                    u_val = user_lines[idx].strip().lower()
                                    matched_item = False
                                    for t in target_list:
                                        if u_val == t:
                                            matched_item = True
                                            break
                                        t_clean = re.sub(r'[^\w\d]', '', t)
                                        u_clean = re.sub(r'[^\w\d]', '', u_val)
                                        if u_clean and u_clean == t_clean:
                                            matched_item = True
                                            break
                                    if not matched_item:
                                        all_matched = False
                                        break
                                else:
                                    all_matched = False
                                    break
                            is_right = all_matched
                    else:
                        target_list = [str(x).strip().lower() for x in (val[0] if isinstance(val[0], list) else val)]
                        u_val = user_lines[0].strip().lower() if user_lines else ans_raw.strip().lower()
                        is_right = any(u_val == t or (re.sub(r'[^\w\d]', '', u_val) == re.sub(r'[^\w\d]', '', t) and re.sub(r'[^\w\d]', '', u_val) != '') for t in target_list)

            # 2. Fallback so sánh với correct_answer_snapshot
            if not is_right and rec.correct_answer_snapshot:
                snap_raw = str(rec.correct_answer_snapshot).strip()
                if '\n' in snap_raw:
                    snap_lines = [l.strip().lower() for l in snap_raw.splitlines()]
                else:
                    snap_lines = [l.strip().lower() for l in re.split(r'[\n,;]+', snap_raw)]

                if len(snap_lines) > 1:
                    if len(user_lines) >= len(snap_lines):
                        all_matched = True
                        for idx, s in enumerate(snap_lines):
                            if idx < len(user_lines):
                                u = user_lines[idx].strip().lower()
                                u_clean = re.sub(r'[^\w\d]', '', u)
                                s_clean = re.sub(r'[^\w\d]', '', s)
                                if u != s and (not u_clean or u_clean != s_clean):
                                    all_matched = False
                                    break
                            else:
                                all_matched = False
                                break
                        is_right = all_matched
                else:
                    u_val = user_lines[0].strip().lower() if user_lines else ans_raw.strip().lower()
                    s_val = snap_lines[0].strip().lower()
                    u_clean = re.sub(r'[^\w\d]', '', u_val)
                    s_clean = re.sub(r'[^\w\d]', '', s_val)
                    is_right = (u_val == s_val or (u_clean and u_clean == s_clean))

            rec.is_correct = is_right
            point_val = max_score if is_right else 0.0
            rec.point = point_val
            if rec.id and isinstance(rec.id, int):
                super(WujiaFranchiseInspectionExamLine, rec).write({
                    'is_correct': is_right,
                    'point': point_val,
                })

    def get_formatted_question_html(self):
        """Điền trực tiếp đáp án của nhân viên vào các ô trống trong nội dung câu hỏi,
        hiển thị dạng gạch chân nét đứt đỏ/xanh tương tự phiếu thi thật."""
     
        self.ensure_one()
        question = self.quest_content_snapshot or ''
        ans_raw = str(self.answer or '').strip()
        is_correct = self.is_correct

        if '\n' in ans_raw:
            user_lines = [l.strip() for l in ans_raw.splitlines() if l.strip()]
        elif ans_raw:
            user_lines = [l.strip() for l in re.split(r'[\n,;]+', ans_raw) if l.strip()]
        else:
            user_lines = []

        ans_idx = [0]

        def replace_blank(match):
            idx = ans_idx[0]
            ans_idx[0] += 1
            if idx < len(user_lines):
                val = user_lines[idx]
                if is_correct:
                    return f'<span style="border-bottom: 2px solid #16a34a; color: #15803d; font-weight: 700; padding: 0 4px; display: inline-block; min-width: 28px; text-align: center;">{val}</span>'
                else:
                    return f'<span style="border-bottom: 2px dashed #ef4444; color: #dc2626; font-weight: 700; padding: 0 4px; display: inline-block; min-width: 28px; text-align: center;">{val}</span>'
            else:
                return '<span style="border-bottom: 2px dashed #ef4444; color: #dc2626; font-weight: 700; padding: 0 6px; display: inline-block; min-width: 28px; text-align: center;">...</span>'

        if re.search(r'_{2,}', question):
            formatted = re.sub(r'_{2,}', replace_blank, question)
        else:
            if user_lines:
                ans_str = ', '.join(user_lines)
                border_col = '#16a34a' if is_correct else '#ef4444'
                text_col = '#15803d' if is_correct else '#dc2626'
                formatted = f'{question} <span style="border-bottom: 2px dashed {border_col}; color: {text_col}; font-weight: 700; padding: 0 4px;">{ans_str}</span>'
            else:
                formatted = f'{question} <span style="border-bottom: 2px dashed #ef4444; color: #dc2626; font-weight: 700; padding: 0 6px;">...</span>'

        return Markup(formatted)


class WujiaFranchiseInspectionAttendanceLine(models.Model):
    _name = 'wujia.franchise.inspection.attendance.line'
    _description = 'Inspection Staff Attendance / Passed Line'
    _order = 'sequence, id'

    sequence = fields.Integer(string='Sequence', default=10)

    line_type = fields.Selection([
        ('attendance', 'Attendance'),
        ('passed', 'Passed Exam'),
    ], string='Line Type', required=True, default='attendance',
        help='Line classification: present attendance or passed certified staff.')

    inspection_id = fields.Many2one(
        'wujia.franchise.inspection',
        string='Inspection Sheet',
        required=True,
        ondelete='cascade',
        index=True,
    )

    member_id = fields.Many2one(
        'wujia.franchise.member',
        string='Store Member',
        ondelete='set null',
        help='Link to store franchise member.',
    )

    employee_name = fields.Char(
        string='Employee Name',
        required=True,
    )

    role = fields.Selection([
        ('owner', 'Owner'),
        ('manager', 'Manager'),
        ('staff', 'Staff'),
    ], string='Role', default='staff')

    phone = fields.Char(string='Phone')

    is_present = fields.Boolean(
        string='Present',
        default=True,
        help='Staff present at the store during inspection.',
    )

    is_pass = fields.Boolean(
        string='Passed Exam',
        default=False,
        help='Staff has passed certification exam.',
    )

    note = fields.Char(string='Note')

    def action_deactivate_member(self):
        """Chuyển nhân viên sang trạng thái Đã nghỉ / Không còn làm việc (is_working=False) và xóa dòng khỏi đợt khảo sát."""
        for line in self:
            if line.member_id:
                line.member_id.write({'is_working': False})
            line.unlink()
        return True

    def action_save_to_member(self):
        """Lưu hoặc tạo mới thông tin thành viên cửa hàng từ dòng điểm danh (nút mũi tên ->)."""
        self.ensure_one()
        if not self.employee_name or not self.employee_name.strip():
            raise ValidationError(_("Please enter Employee Name before saving!"))

        store_id = self.inspection_id.franchise_id.id if self.inspection_id.franchise_id else False
        if not store_id:
            raise ValidationError(_("Please select a Franchise Store first!"))

        if self.member_id:
            # Cập nhật thông tin thành viên hiện tại
            vals = {'role': self.role or 'staff'}
            if self.member_id.user_id:
                user_vals = {}
                if self.employee_name:
                    user_vals['name'] = self.employee_name.strip()
                if self.phone:
                    user_vals['phone'] = self.phone.strip()
                if user_vals:
                    self.member_id.user_id.sudo().write(user_vals)
            self.member_id.sudo().write(vals)
        else:
            # Tìm xem user đã tồn tại theo tên/sđt hoặc tạo mới user + member
            users = self.env['res.users'].sudo().search([('name', '=ilike', self.employee_name.strip())], limit=1)
            if not users:
                # Tạo portal user placeholder
                clean_name = ''.join(e for e in self.employee_name if e.isalnum() or e.isspace()).strip().lower().replace(' ', '.')
                login_candidate = f"{clean_name or 'staff'}.{random.randint(1000, 9999)}@wujiatea.internal"
                portal_group = self.env.ref('base.group_portal', raise_if_not_found=False)
                user_vals = {
                    'name': self.employee_name.strip(),
                    'login': login_candidate,
                    'phone': self.phone or '',
                }
                if portal_group:
                    groups_field = 'groups_id' if 'groups_id' in self.env['res.users']._fields else 'group_ids'
                    user_vals[groups_field] = [(6, 0, [portal_group.id])]
                users = self.env['res.users'].sudo().create(user_vals)
            
            # Check if member already exists in this franchise store
            existing_member = self.env['wujia.franchise.member'].sudo().search([
                ('franchise_id', '=', store_id),
                ('user_id', '=', users.id),
            ], limit=1)
            if existing_member:
                existing_member.write({
                    'role': self.role or 'staff',
                    'is_working': True,
                    'active': True,
                })
                self.write({'member_id': existing_member.id})
            else:
                # Tạo member mới
                new_member = self.env['wujia.franchise.member'].sudo().create({
                    'franchise_id': store_id,
                    'user_id': users.id,
                    'role': self.role or 'staff',
                    'is_pass': self.is_pass,
                    'is_working': True,
                    'active': True,
                })
                self.write({'member_id': new_member.id})

        return True




    def get_report_translations(self, lang=None):
        try:
            target_lang = lang or self.env.context.get('lang') or self.env.user.lang or 'vi_VN'
            return get_survey_translations(target_lang)
        except Exception:
            return {}
