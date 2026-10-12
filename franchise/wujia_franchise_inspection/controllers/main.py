# -*- coding: utf-8 -*-
import json
import base64
import csv
import os
import re
from odoo import http, fields, _
from markupsafe import Markup
# pyrefly: ignore [missing-import]
from odoo.http import request

# Glossary dùng chung toàn repo (repo_root/docs/), cùng nguồn với scripts/sync_translations.py.
# Thiếu file thì t() tự rơi về default — trang khảo sát vẫn chạy.
CSV_PATH = os.path.join(os.path.dirname(__file__), '..', 'data', 'wujia_franchise_export.csv')

_SURVEY_LANG_COL = (('zh', 'CN'), ('cn', 'CN'), ('th', 'TH'), ('vi', 'VN'), ('vn', 'VN'))



def _extract_lang_content(text, lang='zh_TW'):
    if not text:
        return text
    is_zh = any(p in (lang or '').lower() for p in ('zh', 'cn', 'tw'))
    is_vi = any(p in (lang or '').lower() for p in ('vi', 'vn'))
    has_chinese = bool(re.search(r'[一-龥]', text))
    if not has_chinese:
        return text

    # Case 1: Section header with ' / '
    if ' / ' in text:
        parts = text.split(' / ')
        if is_zh:
            zh_parts = [p.strip() for p in parts if re.search(r'[一-龥]', p)]
            if zh_parts:
                return " / ".join(zh_parts)
        elif is_vi:
            vi_parts = [p.strip() for p in parts if not re.search(r'[一-龥]', p)]
            if vi_parts:
                return " / ".join(vi_parts)

    # Case 2: Multiline with \n
    if '\n' in text:
        lines = [l.strip() for l in text.split('\n') if l.strip()]
        if is_zh:
            zh_lines = [l for l in lines if re.search(r'[一-龥]', l)]
            if zh_lines:
                return "\n".join(zh_lines)
        elif is_vi:
            vi_lines = [l for l in lines if not re.search(r'[一-龥]', l)]
            if vi_lines:
                return "\n".join(vi_lines)

    return text


class _SmartTranslationDict(dict):
    def __init__(self, raw_dict):
        super().__init__(raw_dict)
        self._lower_map = {}
        for k, v in raw_dict.items():
            self._lower_map[k.lower()] = v
            self._lower_map[k.lower().replace('&amp;', '&')] = v
            self._lower_map[k.lower().replace('&', '&amp;')] = v

    def get(self, key, default=None):
        if key in self:
            return self[key]
        clean_k = key.replace('&amp;', '&')
        if clean_k in self:
            return self[clean_k]
        low = key.lower()
        if low in self._lower_map:
            return self._lower_map[low]
        low_clean = clean_k.lower()
        if low_clean in self._lower_map:
            return self._lower_map[low_clean]
        return default if default is not None else key

_SURVEY_PO_CACHE = {}

def get_survey_translations(lang):
    """Load UI translations directly from i18n/*.po files."""
    low = (lang or '').lower()
    if any(p in low for p in ('tw', 'hk', 'hant')):
        po_name = 'zh_TW.po'
    elif any(p in low for p in ('zh', 'cn', 'hans')):
        po_name = 'zh_TW.po' if 'tw' in low else 'zh_CN.po'
    elif any(p in low for p in ('th',)):
        po_name = 'th_TH.po'
    elif any(p in low for p in ('vi', 'vn')):
        po_name = 'vi_VN.po'
    else:
        return {}

    if po_name in _SURVEY_PO_CACHE:
        return _SmartTranslationDict(_SURVEY_PO_CACHE[po_name])

    po_path = os.path.join(os.path.dirname(__file__), '..', 'i18n', po_name)
    if not os.path.exists(po_path):
        return {}

    trans = {}
    try:
        with open(po_path, 'r', encoding='utf-8') as f:
            content = f.read()

        import re
        blocks = re.split(r'\n\s*\n', content)
        for b in blocks:
            lines = b.strip().split('\n')
            msgid_lines = []
            msgstr_lines = []
            mode = None
            for line in lines:
                if line.startswith('msgid '):
                    mode = 'msgid'
                    msgid_lines.append(line[6:].strip())
                elif line.startswith('msgstr '):
                    mode = 'msgstr'
                    msgstr_lines.append(line[7:].strip())
                elif line.startswith('"') and mode == 'msgid':
                    msgid_lines.append(line.strip())
                elif line.startswith('"') and mode == 'msgstr':
                    msgstr_lines.append(line.strip())

            def unquote(lst):
                res = ""
                for s in lst:
                    if s.startswith('"') and s.endswith('"'):
                        s = s[1:-1]
                    res += s.replace('\\"', '"').replace('\\n', '\n')
                return res

            msgid = unquote(msgid_lines)
            msgstr = unquote(msgstr_lines)
            if msgid and msgstr:
                trans[msgid] = msgstr

        _SURVEY_PO_CACHE[po_name] = trans
    except Exception:
        pass

    return _SmartTranslationDict(trans)

def _get_store_members_data(inspection):
    if not inspection or not inspection.franchise_id:
        return []
    members = request.env['wujia.franchise.member'].sudo().search([
        ('franchise_id', '=', inspection.franchise_id.id),
        ('active', '=', True),
        ('is_working', '=', True),
    ], order='role, id')
    return [
        {
            'id': m.id,
            'name': m.user_id.name if m.user_id else (m.display_name or ''),
            'role': m.role or 'staff',
            'phone': (m.phone or (m.user_id.phone if m.user_id else '') or '').strip(),
        }
        for m in members
    ]


class WujiaFranchiseInspectionWebController(http.Controller):

    @http.route(['/franchise/inspection/do/<int:inspection_id>'], type='http', auth='user', website=True, sitemap=False)
    def do_inspection_survey(self, inspection_id, **kwargs):
        inspection = request.env['wujia.franchise.inspection'].sudo().browse(int(inspection_id))
            
        if not inspection.exists():
            return request.not_found()
            
        # Allow Admin, Manager, Supervisor, Assigned Inspector, and Internal Users
        user = request.env.user
        is_admin = user.has_group('base.group_system') or user.id in (1, 2)
        if not is_admin and inspection.inspector_user_id and inspection.inspector_user_id.id != user.id:
            if not user.has_group('base.group_user'):
                return request.not_found()

        user_lang = request.env.user.lang or request.context.get('lang') or 'zh_TW'
        trans_map = get_survey_translations(user_lang)

        def _t(key, default=''):
            return trans_map.get(key, default or key)

        lines_rec = inspection.line_ids

        # Kích hoạt prefetch tự động của Odoo ORM cho toàn bộ recordset liên kết (Tránh N+1)
        prev_lines = lines_rec.mapped('previous_line_id')
        prev_inspections = prev_lines.mapped('inspection_id')
        prev_inspections.mapped('inspector_user_id')
        lines_rec.mapped('template_line_id')

        # Build lines data grouped / ordered
        lines = []
        for line in lines_rec:
            prev_line = line.previous_line_id
            prev_info = None
            has_prev_note = False
            prev_note_text = ''
            
            if prev_line:
                p_note = (prev_line.note or '').strip()
                has_prev_note = bool(p_note and p_note not in ('No violation note', 'Chưa có ghi chú', '-'))
                prev_note_text = p_note if has_prev_note else ''
                prev_info = {
                    'inspection_name': prev_line.inspection_id.name if prev_line.inspection_id else '',
                    'planned_date': str(prev_line.inspection_id.planned_date) if (prev_line.inspection_id and prev_line.inspection_id.planned_date) else '',
                    'inspector': prev_line.inspection_id.inspector_user_id.name if (prev_line.inspection_id and prev_line.inspection_id.inspector_user_id) else '---',
                    'is_pass': prev_line.is_pass,
                    'note': prev_note_text,
                    'has_note': has_prev_note,
                    'deduction_score': prev_line.deduction_score_snapshot or 0.0,
                    'has_evidence': bool(prev_line.evidence_image),
                    'evidence_url': f'/web/image/wujia.franchise.inspection.line/{prev_line.id}/evidence_image' if prev_line.evidence_image else '',
                }

            crit_type = line.criterion_type_snapshot or (line.template_line_id.criterion_type if line.template_line_id else 'normal')
            deduction_score = line.deduction_score_snapshot or 0.0
            is_important = (crit_type == 'critical') or (deduction_score >= 5.0)

            line_data = {
                'id': line.id,
                'sequence': line.sequence,
                'display_type': line.display_type,
                'content': _extract_lang_content(line.content_snapshot or '', user_lang),
                'criterion_type': crit_type,
                'is_important': is_important,
                'is_pass': line.is_pass,
                'previous_result': line.previous_result or '',
                'previous_info': prev_info,
                'has_prev_note': has_prev_note,
                'prev_note': prev_note_text,
                'note': line.note or '',
                'has_evidence': bool(line.evidence_image),
                'evidence_image_url': f'/web/image/wujia.franchise.inspection.line/{line.id}/evidence_image' if line.evidence_image else '',
                'require_note': line.require_note_if_fail or line.require_note_if_fail_snapshot,
                'require_evidence': line.require_evidence_if_fail or line.require_evidence_if_fail_snapshot,
                'deduction_score': deduction_score,
            }
            lines.append(line_data)

        # Group lines by section and compute section total/earned scores
        current_section = None
        for l in lines:
            if l.get('display_type') == 'section':
                current_section = l
                l['section_id'] = l['id']
                l['section_total_score'] = 0.0
                l['section_earned_score'] = 0.0
                l['section_total_count'] = 0
                l['section_pass_count'] = 0
            elif current_section:
                l['section_id'] = current_section['id']
                score = float(l.get('deduction_score') or 0.0)
                current_section['section_total_score'] += score
                if l.get('is_pass'):
                    current_section['section_earned_score'] += score
                    current_section['section_pass_count'] += 1
                current_section['section_total_count'] += 1

        for l in lines:
            if l.get('display_type') == 'section':
                tot = l.get('section_total_score', 0.0)
                earned = l.get('section_earned_score', 0.0)
                l['section_total_score_str'] = str(int(tot)) if tot.is_integer() else f"{tot:.1f}"
                l['section_earned_score_str'] = str(int(earned)) if earned.is_integer() else f"{earned:.1f}"

        # Exam lines: Prefetch câu hỏi
        inspection.exam_line_ids.mapped('quest_id')
        exam_lines = [
            {
                'id': el.id,
                'sequence': el.sequence,
                'code': el.quest_code_snapshot or '',
                'question': el.quest_content_snapshot or '',
                'answer': el.answer or '',
                'is_correct': el.is_correct,
                'point': el.point or 0.0,
                'max_score': el.quest_id.score if (el.quest_id and el.quest_id.score) else 1.0,
                'correct_answers': json.dumps(el.quest_id.correct_answers or []) if el.quest_id else '[]',
            }
            for el in inspection.exam_line_ids
        ]

        is_inspection_closed = (inspection.state in ('done', 'cancel'))
        is_exam_submitted = bool(inspection.is_exam_submitted)



        grades_data = [
            {
                'id': g.id,
                'name': g.name,
                'min_score': g.min_score,
                'max_score': g.max_score,
            }
            for g in request.env['wujia.franchise.inspection.grade'].sudo().search([], order='min_score desc')
        ]

        store_members = request.env['wujia.franchise.member'].sudo().search([
            ('franchise_id', '=', inspection.franchise_id.id),
            ('active', '=', True),
            ('is_working', '=', True),
        ], order='role, id')

        attendance_lines = [
            {
                'id': att.id,
                'member_id': att.member_id.id if att.member_id else False,
                'employee_name': att.employee_name or '',
                'role': att.role or 'staff',
                'phone': att.phone or '',
                'is_present': att.is_present,
                'note': att.note or '',
            }
            for att in inspection.attendance_line_ids
        ]

        passed_members = [
            {
                'id': m.id,
                'name': m.user_id.name if m.user_id else '',
                'role': m.role or 'staff',
                'phone': m.phone or '',
            }
            for m in inspection.passed_member_ids
        ]

        values = {
            'inspection': inspection,
            'grades_json': Markup(json.dumps(grades_data, ensure_ascii=False)),
            'lines': lines,
            'exam_lines': exam_lines,
            'checklist_count': len([l for l in lines if l.get('display_type') == 'line']),
            'exam_count': len(exam_lines),
            'max_checklist_score': inspection.template_id.checklist_max_score if inspection.template_id else 95.0,
            'max_exam_score': inspection.template_id.exam_max_score if inspection.template_id else 5.0,
            'is_inspection_closed': is_inspection_closed,
            'is_exam_submitted': is_exam_submitted,
            'test_employee_name': inspection.test_employee_name or '',
            'tenure': inspection.tenure or '',
            'store_appearance_issues': inspection.store_appearance_issues or '',
            'previous_store_appearance_issues': inspection.previous_store_appearance_issues or '',
            'confirmed_user_name': inspection.confirmed_user_id.name if inspection.confirmed_user_id else request.env.user.name,
            'has_signature': bool(inspection.signature_image),
            'signature_image_url': f'/web/image/wujia.franchise.inspection/{inspection.id}/signature_image' if inspection.signature_image else '',
            'signature_date': str(inspection.signature_date) if inspection.signature_date else '',
            'confirmed_member_id': inspection.confirmed_member_id.id if inspection.confirmed_member_id else False,
            'store_members': store_members,
            'attendance_lines': attendance_lines,
            'passed_members': passed_members,
            'months_list': (
                [('01', '01月'), ('02', '02月'), ('03', '03月'), ('04', '04月'), ('05', '05月'), ('06', '06月'), ('07', '07月'), ('08', '08月'), ('09', '09月'), ('10', '10月'), ('11', '11月'), ('12', '12月')]
                if any(x in user_lang.lower() for x in ('zh', 'cn')) else (
                    [('01', 'ม.ค. (01)'), ('02', 'ก.พ. (02)'), ('03', 'มี.ค. (03)'), ('04', 'เม.ย. (04)'), ('05', 'พ.ค. (05)'), ('06', 'มิ.ย. (06)'), ('07', 'ก.ค. (07)'), ('08', 'ส.ค. (08)'), ('09', 'ก.ย. (09)'), ('10', 'ต.ค. (10)'), ('11', 'พ.ย. (11)'), ('12', 'ธ.ค. (12)')]
                    if 'th' in user_lang.lower() else
                    [('01', 'January'), ('02', 'February'), ('03', 'March'), ('04', 'April'), ('05', 'May'), ('06', 'June'), ('07', 'July'), ('08', 'August'), ('09', 'September'), ('10', 'October'), ('11', 'November'), ('12', 'December')]
                )
            ),
            'years_list': [str(y) for y in range(2023, 2031)],
            'report_lines': [
                {
                    'id': rl.id,
                    'date_month': str(rl.date_month) if rl.date_month else '',
                    'month_val': rl.date_month.strftime('%m') if rl.date_month else '01',
                    'year_val': rl.date_month.strftime('%Y') if rl.date_month else '2026',
                    'date_month_val': rl.date_month.strftime('%Y-%m') if rl.date_month else '',
                    'date_month_str': rl.date_month.strftime('%m/%Y') if rl.date_month else '',
                    'revenue': rl.revenue or 0.0,
                    'revenue_avg': rl.revenue_avg or 0.0,
                    'percent_goods': rl.percent_goods or 0.0,
                    'total_app_sale': rl.total_app_sale or 0,
                    'percent_app_sale': rl.percent_app_sale or 0.0,
                }
                for rl in inspection.report_line_ids.sorted(key=lambda r: (r.sequence, r.id))
            ],
            'present_count': inspection.present_count,
            'passed_count': len(passed_members),
            'user_lang': user_lang,
            't': trans_map,
            'tj': Markup(json.dumps(trans_map, ensure_ascii=False)),
            'trans_dict': trans_map,
            'trans': trans_map,
            'trans_json': Markup(json.dumps(trans_map, ensure_ascii=False)),
        }
        template = 'wujia_franchise_inspection.inspection_survey_do_page' if request.env.ref('wujia_franchise_inspection.inspection_survey_do_page', raise_if_not_found=False) else 'wujia_franchise.inspection_survey_do_page'
        return request.render(template, values)

    @http.route(['/franchise/inspection/do/<int:inspection_id>/sync_posapp'], type='json', auth='user', methods=['POST'])
    def sync_posapp_revenue(self, inspection_id, **kwargs):
        inspection = request.env['wujia.franchise.inspection'].sudo().browse(int(inspection_id))
        if not inspection.exists():
            return {'success': False, 'error': 'Inspection sheet does not exist'}
        if inspection.state in ('done', 'cancel'):
            return {'success': False, 'error': 'Inspection sheet is already completed or cancelled!'}
        
        try:
            lines_data = inspection._fetch_posapp_revenue_data()
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
            inspection.write({'report_line_ids': commands})
            return {
                'success': True,
                'report_lines': lines_data,
                'message': 'PosApp revenue synchronized successfully!'
            }
        except Exception as e:
            return {'success': False, 'error': str(e)}

    @http.route(['/franchise/inspection/do/<int:inspection_id>/save'], type='json', auth='user', methods=['POST'])
    def save_inspection_survey(self, inspection_id, lines=None, exam_lines=None, test_employee_name=None, tenure=None, store_appearance_issues=None, confirmed_member_id=None, attendance_lines=None, signature_image=None, report_lines=None, finish=True, **kwargs):
        inspection = request.env['wujia.franchise.inspection'].sudo().browse(int(inspection_id))
        if not inspection.exists():
            return {'success': False, 'error': 'Inspection sheet does not exist'}

        if inspection.state in ('done', 'cancel'):
            return {'success': False, 'error': 'Inspection sheet is already completed or cancelled and cannot be edited!'}

        # 1. Tối ưu cập nhật checklist lines: So sánh qua ORM để chỉ ghi các dòng thực sự thay đổi
        if lines:
            line_map = {l.id: l for l in inspection.line_ids.filtered(lambda x: x.display_type == 'line')}
            for l_data in lines:
                l_id = int(l_data.get('id', 0))
                line = line_map.get(l_id)
                if not line:
                    continue
                new_is_pass = bool(l_data.get('is_pass'))
                new_note = (l_data.get('note', '') or '').strip()
                evidence_b64 = l_data.get('evidence_image')

                vals = {}
                if line.is_pass != new_is_pass:
                    vals['is_pass'] = new_is_pass
                if (line.note or '').strip() != new_note:
                    vals['note'] = new_note
                if evidence_b64 and 'base64,' in evidence_b64:
                    vals['evidence_image'] = evidence_b64.split('base64,')[1]
                elif (evidence_b64 in (False, 'REMOVE', 'CLEAR', '') or evidence_b64 is False) and line.evidence_image:
                    vals['evidence_image'] = False

                if vals:
                    line.write(vals)

        # 2. Tối ưu cập nhật exam lines
        insp_vals = {}
        if not inspection.is_exam_submitted:
            emp_name_clean = (test_employee_name or '').strip()
            if finish:
                if not emp_name_clean:
                    return {'success': False, 'error': 'Please enter staff name before saving!'}

                insp_vals['test_employee_name'] = emp_name_clean
                if tenure is not None:
                    insp_vals['tenure'] = str(tenure).strip() if tenure else ''

                if exam_lines:
                    exam_map = {el.id: el for el in inspection.exam_line_ids}
                    for el_data in exam_lines:
                        el_id = int(el_data.get('id', 0))
                        exam_line = exam_map.get(el_id)
                        if not exam_line:
                            continue
                        ans = (el_data.get('answer', '') or '').strip()
                        exam_line.write({'answer': ans})
                        exam_line._evaluate_answer()

                insp_vals['is_exam_submitted'] = True
            else:
                # Lưu nháp / lưu tạm khi chưa hoàn thành hoặc nhấn nút mũi tên (không bắt buộc và không khóa bài kiểm tra)
                if emp_name_clean:
                    insp_vals['test_employee_name'] = emp_name_clean
                if tenure is not None:
                    insp_vals['tenure'] = str(tenure).strip() if tenure else ''
                if exam_lines:
                    exam_map = {el.id: el for el in inspection.exam_line_ids}
                    for el_data in exam_lines:
                        el_id = int(el_data.get('id', 0))
                        exam_line = exam_map.get(el_id)
                        if not exam_line:
                            continue
                        ans = (el_data.get('answer', '') or '').strip()
                        if (exam_line.answer or '').strip() != ans:
                            exam_line.write({'answer': ans})

        if store_appearance_issues is not None:
            insp_vals['store_appearance_issues'] = store_appearance_issues

        sig_data = signature_image or kwargs.get('signature_image')
        if sig_data and 'base64,' in sig_data:
            insp_vals['signature_image'] = sig_data.split('base64,', 1)[1]
            insp_vals['signature_date'] = fields.Datetime.now()
        elif sig_data == 'CLEAR':
            insp_vals['signature_image'] = False
            insp_vals['signature_date'] = False

        if confirmed_member_id is not None:
            insp_vals['confirmed_member_id'] = int(confirmed_member_id) if confirmed_member_id else False

        # 3. Tối ưu cập nhật attendance lines
        if attendance_lines:
            att_map = {att.id: att for att in inspection.attendance_line_ids}
            for a_item in attendance_lines:
                att_id = int(a_item.get('id', 0))
                att = att_map.get(att_id)
                if not att:
                    continue
                is_present = bool(a_item.get('is_present', True))
                emp_name = (a_item.get('employee_name', '') or '').strip()
                role = a_item.get('role', 'staff')
                phone = (a_item.get('phone', '') or '').strip()
                note = a_item.get('note', '') or False
                att_vals = {}
                if att.is_present != is_present:
                    att_vals['is_present'] = is_present
                if emp_name and att.employee_name != emp_name:
                    att_vals['employee_name'] = emp_name
                if role and att.role != role:
                    att_vals['role'] = role
                if (att.phone or '') != phone:
                    att_vals['phone'] = phone
                if (att.note or False) != note:
                    att_vals['note'] = note
                if att_vals:
                    att.write(att_vals)
                if not att.member_id and (att.employee_name or emp_name):
                    try:
                        att.action_save_to_member()
                    except Exception:
                        pass

        # Cập nhật các dòng báo cáo doanh thu 3 tháng (report_lines)
        if report_lines is not None:
            existing_report_lines = {rl.id: rl for rl in inspection.report_line_ids}
            sent_ids = []
            seq = 10
            for r_data in report_lines:
                r_id = int(r_data.get('id', 0)) if r_data.get('id') else 0
                d_month = r_data.get('date_month') or fields.Date.context_today(inspection)
                vals = {
                    'sequence': seq,
                    'date_month': d_month,
                    'revenue': float(r_data.get('revenue', 0.0) or 0.0),
                    'revenue_avg': float(r_data.get('revenue_avg', 0.0) or 0.0),
                    'percent_goods': float(r_data.get('percent_goods', 0.0) or 0.0),
                    'total_app_sale': int(r_data.get('total_app_sale', 0) or 0),
                    'percent_app_sale': float(r_data.get('percent_app_sale', 0.0) or 0.0),
                }
                seq += 10
                if r_id and r_id in existing_report_lines:
                    existing_report_lines[r_id].write(vals)
                    sent_ids.append(r_id)
                else:
                    vals['inspection_id'] = inspection.id
                    new_rl = request.env['wujia.franchise.inspection.report.line'].sudo().create(vals)
                    sent_ids.append(new_rl.id)
            
            for rl_id, rl_obj in existing_report_lines.items():
                if rl_id not in sent_ids:
                    rl_obj.unlink()

        if insp_vals:
            inspection.write(insp_vals)

        # 4. Tính toán lại điểm số & grade bằng các phương thức ORM
        inspection._compute_checklist_score()
        inspection._compute_exam_score()
        inspection._compute_total_score()
        inspection._compute_grade()

        failed_lines = inspection.line_ids.filtered(lambda l: l.display_type == 'line' and not l.is_pass)
        if failed_lines and inspection.state == 'draft':
            inspection.action_need_remediation()

        exam_results = {
            el.id: {
                'is_correct': el.is_correct,
                'point': el.point,
                'max_score': el.quest_id.score if (el.quest_id and el.quest_id.score) else 1.0,
                'correct_answers': el.quest_id.correct_answers if el.quest_id else [],
            }
            for el in inspection.exam_line_ids
        }

        return {
            'success': True,
            'is_exam_submitted': inspection.is_exam_submitted,
            'checklist_score': inspection.checklist_score,
            'exam_score': inspection.exam_score,
            'total_score': inspection.total_score,
            'grade': inspection.grade_id.name if inspection.grade_id else '',
            'state': inspection.state,
            'exam_results': exam_results,
            'store_members': _get_store_members_data(inspection),
        }

    @http.route(['/franchise/inspection/do/<int:inspection_id>/attendance/add'], type='json', auth='user', methods=['POST'])
    def add_attendance_line(self, inspection_id, employee_name, role='staff', phone='', note='', is_present=True, **kwargs):
        inspection = request.env['wujia.franchise.inspection'].sudo().browse(int(inspection_id))
        if not inspection.exists() or inspection.state in ('done', 'cancel'):
            return {'success': False, 'error': 'Inspection survey is locked or does not exist!'}
        
        emp_name = (employee_name or '').strip()
        if not emp_name:
            return {'success': False, 'error': 'Please enter staff full name!'}
        
        new_line = request.env['wujia.franchise.inspection.attendance.line'].sudo().create({
            'inspection_id': inspection.id,
            'employee_name': emp_name,
            'role': role or 'staff',
            'phone': (phone or '').strip(),
            'note': (note or '').strip(),
            'is_present': bool(is_present),
        })
        try:
            new_line.action_save_to_member()
        except Exception:
            pass
        
        member = new_line.member_id
        member_id = member.id if member else False
        member_name = member.user_id.name if (member and member.user_id) else (member.display_name if member else new_line.employee_name)
        member_role = member.role if member else (new_line.role or 'staff')
        member_phone = (new_line.phone or (member.phone if member else '') or '').strip()
        
        return {
            'success': True,
            'line': {
                'id': new_line.id,
                'member_id': member_id,
                'employee_name': new_line.employee_name,
                'role': new_line.role,
                'phone': new_line.phone or '',
                'is_present': new_line.is_present,
                'note': new_line.note or '',
            },
            'member': {
                'id': member_id,
                'name': member_name,
                'role': member_role,
                'phone': member_phone,
            } if member_id else None,
            'store_members': _get_store_members_data(inspection),
            'present_count': inspection.present_count,
        }

    @http.route(['/franchise/inspection/do/<int:inspection_id>/attendance/save_member'], type='json', auth='user', methods=['POST'])
    def save_attendance_to_member(self, inspection_id, line_id, employee_name=None, role=None, phone=None, **kwargs):
        line = request.env['wujia.franchise.inspection.attendance.line'].sudo().browse(int(line_id))
        if not line.exists() or line.inspection_id.id != int(inspection_id):
            return {'success': False, 'error': 'Attendance line does not exist!'}
        
        if employee_name:
            line.employee_name = employee_name.strip()
        if role:
            line.role = role
        if phone is not None:
            line.phone = phone.strip()
            
        try:
            line.action_save_to_member()
            member = line.member_id
            return {
                'success': True,
                'member_id': member.id if member else False,
                'member': {
                    'id': member.id,
                    'name': member.user_id.name if (member and member.user_id) else (member.display_name if member else line.employee_name),
                    'role': member.role if member else (line.role or 'staff'),
                    'phone': line.phone or (member.phone if member else ''),
                } if member else None,
                'store_members': _get_store_members_data(line.inspection_id),
            }
        except Exception as e:
            return {'success': False, 'error': str(e)}

    @http.route(['/franchise/inspection/do/<int:inspection_id>/attendance/deactivate_member'], type='json', auth='user', methods=['POST'])
    def deactivate_attendance_member(self, inspection_id, line_id, **kwargs):
        line = request.env['wujia.franchise.inspection.attendance.line'].sudo().browse(int(line_id))
        if not line.exists() or line.inspection_id.id != int(inspection_id):
            return {'success': False, 'error': 'Attendance line does not exist!'}
        
        member_id = line.member_id.id if line.member_id else False
        try:
            inspection = line.inspection_id
            line.action_deactivate_member()
            return {
                'success': True,
                'member_id': member_id,
                'store_members': _get_store_members_data(inspection),
                'present_count': inspection.present_count,
            }
        except Exception as e:
            return {'success': False, 'error': str(e)}

    @http.route(['/franchise/inspection/do/<int:inspection_id>/attendance/delete_line'], type='json', auth='user', methods=['POST'])
    def delete_attendance_line(self, inspection_id, line_id, **kwargs):
        line = request.env['wujia.franchise.inspection.attendance.line'].sudo().browse(int(line_id))
        if not line.exists() or line.inspection_id.id != int(inspection_id):
            return {'success': False, 'error': 'Attendance line does not exist!'}
        
        inspection = line.inspection_id
        line.unlink()
        return {'success': True, 'present_count': inspection.present_count}


