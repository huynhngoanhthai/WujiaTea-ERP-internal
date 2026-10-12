# -*- coding: utf-8 -*-
import math
import re
import base64
from datetime import datetime
from enum import Enum
from odoo import http, fields, _
# pyrefly: ignore [missing-import]
from odoo.http import request

from odoo.addons.wujia_portal_base.controllers.portal import get_active_franchise_ids_filter


class RemediationState(str, Enum):
    NEED_REMEDIATION = 'need_remediation'
    REMEDIATED = 'remediated'
    DONE = 'done'


def _parse_date(date_str):
    if not date_str:
        return ''
    date_str = str(date_str).strip()
    if '/' in date_str:
        parts = date_str.split('/')
        if len(parts) == 3:
            return f"{parts[2]}-{parts[1].zfill(2)}-{parts[0].zfill(2)}"
    return date_str


def _clean_content(text):
    if not text:
        return ''
    text = str(text).strip()
    text = re.sub(r'^\[[\d\.]+\]\s*', '', text)
    return text


class WujiaPortalInspectionController(http.Controller):

    def _get_inspection_list_values(self, tab='all', date_from=None, date_to=None, search=None, page=1):
        """Shared logic for building inspection list template values."""
        try:
            page = int(page)
            if page < 1:
                page = 1
        except (ValueError, TypeError):
            page = 1

        limit = 5
        franchise_ids = get_active_franchise_ids_filter()

        if tab == 'need_remediation':
            inspection_domain = [('state', '=', 'need_remediation')]
        elif tab == 'done':
            inspection_domain = [('state', '=', 'done')]
        else:
            inspection_domain = [('state', 'in', ('need_remediation', 'done'))]

        # fail-closed: không thuộc cửa hàng nào ⇒ domain rỗng ⇒ không thấy phiếu nào
        inspection_domain.append(('franchise_id', 'in', list(franchise_ids or ())))

        parsed_date_from = _parse_date(date_from)
        parsed_date_to = _parse_date(date_to)

        if parsed_date_from:
            inspection_domain.append(('planned_date', '>=', parsed_date_from))
        if parsed_date_to:
            inspection_domain.append(('planned_date', '<=', parsed_date_to))

        if search:
            q = search.strip()
            inspection_domain.extend([
                '|', '|',
                ('name', 'ilike', q),
                ('franchise_id.name', 'ilike', q),
                ('franchise_id.code', 'ilike', q),
            ])

        InspectionModel = request.env['wujia.franchise.inspection'].sudo()
        total_count = InspectionModel.search_count(inspection_domain)
        total_pages = math.ceil(total_count / limit) if total_count > 0 else 1
        if page > total_pages:
            page = total_pages

        offset = (page - 1) * limit
        inspections = InspectionModel.search(
            inspection_domain, order='planned_date desc, id desc', limit=limit, offset=offset
        )

        inspection_items = []
        for insp in inspections:
            criteria_lines = insp.line_ids.filtered(lambda l: l.display_type == 'line')
            failed_lines = criteria_lines.filtered(lambda l: not l.is_pass or l.result == 'fail')
            unanswered_failed_lines = failed_lines.filtered(lambda l: not l.remediation_image and not l.remediation_note)
            first_unanswered_id = unanswered_failed_lines[0].id if unanswered_failed_lines else (failed_lines[0].id if failed_lines else False)
            grade_name = insp.grade_id.name if insp.grade_id else ''
            if not grade_name and insp.total_score is not False and insp.total_score is not None:
                all_grades = request.env['wujia.franchise.inspection.grade'].sudo().search([], order='min_score desc')
                for g in all_grades:
                    if g.min_score <= (insp.total_score or 0.0) <= g.max_score:
                        grade_name = g.name
                        break

            grade_label = ""
            if grade_name and grade_name != 'N/A':
                grade_str = str(grade_name).strip()
                if not grade_str.startswith('Loại') and not grade_str.startswith('Hạng'):
                    grade_label = f"Loại {grade_str}"
                else:
                    grade_label = grade_str

            state_label = 'Hoàn thành'
            badge_bg = '#dcfce7'
            badge_color = '#15803d'
            progress_color = '#22c55e'

            if insp.state == 'need_remediation':
                state_label = 'Chờ phản hồi'
                badge_bg = '#fef3c7'
                badge_color = '#d97706'
                progress_color = '#f59e0b'

            title_str = insp.name or "Khảo sát"
            if not title_str or title_str == "Khảo sát cửa hàng nhượng quyền" or title_str.startswith("Khảo sát cửa hàng nhượng quyền"):
                if insp.planned_date:
                    try:
                        d_str = fields.Date.from_string(insp.planned_date).strftime('%d/%m/%Y')
                        title_str = f"Lần {d_str}"
                    except Exception:
                        title_str = f"Lần {insp.planned_date}"
                else:
                    title_str = "Khảo sát cửa hàng"

            planned_date_formatted = ""
            if insp.planned_date:
                try:
                    planned_date_formatted = fields.Date.from_string(insp.planned_date).strftime('%d/%m/%Y')
                except Exception:
                    planned_date_formatted = str(insp.planned_date)

            item_data = {
                'id': insp.id,
                'name': insp.name or f"#AUD-{insp.id}",
                'code_badge': f"#{insp.name}" if insp.name else f"#AUD-{insp.id}",
                'title': title_str,
                'display_name': insp.name or title_str,
                'franchise_name': insp.franchise_id.display_name if insp.franchise_id else 'Cửa hàng',
                'planned_date': planned_date_formatted or 'N/A',
                'inspector_name': insp.inspector_user_id.name if insp.inspector_user_id else 'N/A',
                'state': insp.state,
                'state_label': state_label,
                'badge_bg': badge_bg,
                'badge_color': badge_color,
                'progress_color': progress_color,
                'total_score': int(insp.total_score or 0),
                'grade_name': grade_name,
                'grade_label': grade_label,
                'total_criteria': len(criteria_lines),
                'pass_count': len(criteria_lines) - len(failed_lines),
                'failed_count': len(failed_lines),
                'remediation_url': f"/portal/inspection/remediation/{first_unanswered_id}" if (insp.state == 'need_remediation' and first_unanswered_id) else False,
                'detail_url': f"/portal/inspection/detail/{insp.id}",
            }
            inspection_items.append(item_data)

        return {
            '_inspection_active': True,
            'active_tab': tab if tab in ('all', 'need_remediation', 'done') else 'all',
            'date_from': date_from or '',
            'date_to': date_to or '',
            'search_q': search or '',
            'inspection_items': inspection_items,
            'page': page,
            'total_pages': total_pages,
            'total_count': total_count,
            'page_range': list(range(1, total_pages + 1)),
        }

    @http.route(['/portal/inspection'], type='http', auth='user', website=True)
    def portal_inspection_list(self, tab='all', date_from=None, date_to=None, search=None, page=1, **kwargs):
        values = self._get_inspection_list_values(tab, date_from, date_to, search, page)
        return request.render('wujia_portal_inspection.portal_inspection_main', values)

    @http.route(['/portal/inspection/ajax'], type='http', auth='user', website=True)
    def portal_inspection_list_ajax(self, tab='all', date_from=None, date_to=None, search=None, page=1, **kwargs):
        """Return only the content fragment as JSON for SPA-like navigation."""
        values = self._get_inspection_list_values(tab, date_from, date_to, search, page)
        html = request.env['ir.qweb']._render('wujia_portal_inspection.portal_inspection_list_content', values)
        return request.make_json_response({
            'html': str(html),
            'active_tab': values['active_tab'],
            'search_q': values['search_q'],
            'page': values['page'],
            'total_pages': values['total_pages'],
        })

    @http.route(['/portal/inspection/detail/<int:inspection_id>'], type='http', auth='user', website=True)
    def portal_inspection_detail(self, inspection_id=None, **kwargs):
        if not inspection_id:
            return request.redirect('/portal/inspection')

        insp = request.env['wujia.franchise.inspection'].sudo().browse(int(inspection_id))
        if not insp.exists() or insp.state not in ('need_remediation', 'done'):
            return request.redirect('/portal/inspection')

        franchise_ids = get_active_franchise_ids_filter()
        if insp.franchise_id.id not in (franchise_ids or ()):
            return request.redirect('/portal/inspection')

        criteria_lines = insp.line_ids.filtered(lambda l: l.display_type == 'line')
        failed_lines = criteria_lines.filtered(lambda l: not l.is_pass or l.result == 'fail')
        unanswered_failed_lines = failed_lines.filtered(
            lambda l: (
                l.remediation_state == 'need_remediation'
                or (not l.remediation_image and not l.remediation_note and l.remediation_state not in ('remediated', 'done'))
            )
        )
        first_unanswered_id = unanswered_failed_lines[0].id if unanswered_failed_lines else (failed_lines[0].id if failed_lines else False)

        grade_name = insp.grade_id.name if insp.grade_id else 'B+'

        sections = []
        current_sec = None
        sec_counter = 1

        for line in insp.line_ids:
            if line.display_type == 'section':
                cat_rec = line.category_id or (line.template_line_id.category_id if line.template_line_id else False)
                sec_text = (line.content_snapshot or '').lower()
                is_sec_severe = bool(cat_rec and getattr(cat_rec, 'is_severe', False)) or (cat_rec and 'nghiêm trọng' in (cat_rec.name or '').lower()) or ('nghiêm trọng' in sec_text) or ('vi phạm' in sec_text and 'nghiêm trọng' in sec_text)

                sec_title = f"DANH MỤC {sec_counter}"
                current_sec = {
                    'id': f"sec_target_{sec_counter}",
                    'title': sec_title,
                    'subtitle': _clean_content(line.content_snapshot or ''),
                    'is_severe': is_sec_severe,
                    'current_score': 0,
                    'max_score': 0,
                    'fail_count': 0,
                    'total_deducted': 0,
                    'lines': []
                }
                sections.append(current_sec)
                sec_counter += 1

            elif line.display_type == 'line':
                is_pass = line.is_pass or line.result == 'pass'
                cat_rec = line.category_id or (line.template_line_id.category_id if line.template_line_id else False)
                line_text = (line.content_snapshot or '').lower()
                is_severe = bool(cat_rec and getattr(cat_rec, 'is_severe', False)) or (cat_rec and 'nghiêm trọng' in (cat_rec.name or '').lower()) or ('nghiêm trọng' in line_text)

                code_str = ''
                if line.template_line_id and getattr(line.template_line_id, 'criterion_code', False):
                    code_str = line.template_line_id.criterion_code
                elif line.sequence:
                    code_str = f"{line.sequence:02d}" if isinstance(line.sequence, int) else f"{line.sequence}"

                raw_content = line.content_snapshot or (line.template_line_id.content if line.template_line_id else '')
                cleaned_content = _clean_content(raw_content)
                deduction = line.deduction_score_snapshot or (line.template_line_id.deduction_score if line.template_line_id else 0.0)

                line_item = {
                    'id': line.id,
                    'code': code_str,
                    'content': cleaned_content,
                    'is_pass': is_pass,
                    'deduction': deduction,
                    'is_severe': is_severe,
                    'note': line.note or '',
                    'remediation_note': line.remediation_note or '',
                    'evidence_image_url': f"/web/image/wujia.franchise.inspection.line/{line.id}/evidence_image" if line.evidence_image else False,
                    'remediation_state': line.remediation_state or 'need_remediation',
                    'remediation_image_url': f"/web/image/wujia.franchise.inspection.line/{line.id}/remediation_image" if line.remediation_image else False,
                    'criterion_type_snapshot': line.criterion_type_snapshot or '',
                }

                if current_sec is None:
                    current_sec = {
                        'id': f"sec_target_{sec_counter}",
                        'title': f"DANH MỤC {sec_counter}",
                        'subtitle': 'Tiêu chí kiểm tra',
                        'is_severe': False,
                        'current_score': 0,
                        'max_score': 0,
                        'fail_count': 0,
                        'total_deducted': 0,
                        'lines': []
                    }
                    sections.append(current_sec)
                    sec_counter += 1

                current_sec['lines'].append(line_item)
                line_weight = 4 if not deduction else int(deduction)
                current_sec['max_score'] += line_weight
                if is_pass:
                    current_sec['current_score'] += line_weight
                else:
                    current_sec['fail_count'] += 1
                    current_sec['total_deducted'] += line_weight

        category_summaries = []
        for sec in sections:
            if sec['is_severe']:
                val_str = str(sec['fail_count'])
            else:
                val_str = f"{sec['current_score']}/{sec['max_score']}"
            category_summaries.append({
                'name': sec['title'],
                'val_str': val_str,
                'is_severe': sec['is_severe'],
                'target_sec': sec['id']
            })

        final_sections = [s for s in sections if s.get('lines')]

        planned_date_fmt = ""
        if insp.planned_date:
            try:
                planned_date_fmt = fields.Date.from_string(insp.planned_date).strftime('%d/%m/%Y')
            except Exception:
                planned_date_fmt = str(insp.planned_date)

        values = {
            '_inspection_active': True,
            'insp': insp,
            'inspection_id': insp.id,
            'franchise_code': insp.franchise_id.code if (insp.franchise_id and insp.franchise_id.code) else 'HN_ST042',
            'planned_date': planned_date_fmt or '15/05/2024',
            'total_score': int(insp.total_score or 85),
            'max_score': 100,
            'grade_name': grade_name,
            'category_summaries': category_summaries,
            'sections': final_sections,
            'unanswered_count': len(unanswered_failed_lines),
            'first_remediation_url': f"/portal/inspection/remediation/{first_unanswered_id}" if (insp.state == 'need_remediation' and first_unanswered_id) else False,
        }
        return request.render('wujia_portal_inspection.portal_inspection_detail', values)

    @http.route(['/portal/inspection/remediation/<int:line_id>', '/portal/remediation/<int:line_id>', '/portal/remediation'], type='http', auth='user', website=True)
    def portal_inspection_remediation(self, line_id=None, **kwargs):
        if not line_id:
            return request.redirect('/portal/inspection')

        LineModel = request.env['wujia.franchise.inspection.line'].sudo()
        line = LineModel.browse(int(line_id))
        if not line.exists():
            return request.redirect('/portal/inspection')

        insp = line.inspection_id
        if not insp.exists():
            return request.redirect('/portal/inspection')

        franchise_ids = get_active_franchise_ids_filter()
        if insp.franchise_id.id not in (franchise_ids or ()):
            return request.redirect('/portal/inspection')

        cat_rec = line.category_id or (line.template_line_id.category_id if line.template_line_id else False)
        cat_name = cat_rec.name if cat_rec else 'DANH MỤC TIÊU CHÍ'
        cat_name = _clean_content(cat_name)

        code_str = ''
        if line.template_line_id and getattr(line.template_line_id, 'criterion_code', False):
            code_str = line.template_line_id.criterion_code
        elif line.sequence:
            code_str = f"{line.sequence}."

        criterion_name = _clean_content(line.content_snapshot or (line.template_line_id.content if line.template_line_id else ''))

        planned_date_fmt = ""
        if insp.create_date:
            try:
                local_dt = fields.Datetime.context_timestamp(request.env.user, insp.create_date)
                planned_date_fmt = local_dt.strftime('%H:%M - %d/%m/%Y')
            except Exception:
                planned_date_fmt = str(insp.planned_date)

        values = {
            '_inspection_active': True,
            'line': line,
            'insp': insp,
            'category_name': cat_name,
            'line_code': code_str,
            'criterion_name': criterion_name,
            'admin_note': line.note or '',
            'planned_date': planned_date_fmt or '10:15 - 15/05/2024',
            'evidence_image_url': f"/web/image/wujia.franchise.inspection.line/{line.id}/evidence_image" if line.evidence_image else False,
            'back_url': f"/portal/inspection/detail/{insp.id}",
        }
        return request.render('wujia_portal_inspection.portal_inspection_remediation_form', values)

    @http.route(['/portal/inspection/remediation/submit', '/portal/remediation/submit'], type='http', auth='user', methods=['POST'], csrf=True, website=True)
    def portal_inspection_remediation_submit(self, line_id=None, remediation_note=None, remediation_image=None, **kwargs):
        if not line_id and request.params.get('line_id'):
            line_id = request.params.get('line_id')
        if not remediation_note and request.params.get('remediation_note'):
            remediation_note = request.params.get('remediation_note')
        if not remediation_image and request.httprequest.files.get('remediation_image'):
            remediation_image = request.httprequest.files.get('remediation_image')

        if not line_id:
            return request.make_json_response({'status': 'error', 'message': 'Thiếu ID tiêu chí.'})

        LineModel = request.env['wujia.franchise.inspection.line'].sudo()
        line = LineModel.browse(int(line_id))
        if not line.exists():
            return request.make_json_response({'status': 'error', 'message': 'Tiêu chí không tồn tại.'})

        write_vals = {}
        store_note = str(remediation_note).strip() if remediation_note else ''
        if store_note:
            write_vals['remediation_note'] = store_note

        has_new_image = False
        if remediation_image:
            if isinstance(remediation_image, bytes):
                write_vals['remediation_image'] = base64.b64encode(remediation_image).decode('utf-8')
                has_new_image = True
            elif isinstance(remediation_image, str) and ',' in remediation_image:
                write_vals['remediation_image'] = remediation_image.split(',')[1]
                has_new_image = True
            elif isinstance(remediation_image, str) and len(remediation_image) > 10:
                write_vals['remediation_image'] = remediation_image
                has_new_image = True
            elif getattr(remediation_image, 'read', None):
                img_data = remediation_image.read()
                if img_data:
                    write_vals['remediation_image'] = base64.b64encode(img_data).decode('utf-8')
                    has_new_image = True

        has_image = has_new_image or bool(line.remediation_image)
        has_note = bool(store_note) or bool(line.remediation_note)
        require_ev = line.require_evidence_if_fail_snapshot or line.require_evidence_if_fail

        if require_ev and not has_image:
            return request.make_json_response({'status': 'error', 'message': 'Tiêu chí này yêu cầu bắt buộc phải có ảnh minh chứng.'})

        if not has_image and not has_note:
            return request.make_json_response({'status': 'error', 'message': 'Vui lòng nhập ghi chú khắc phục hoặc tải lên ảnh minh chứng trước khi gửi.'})

        write_vals['remediation_state'] = RemediationState.REMEDIATED.value
        try:
            line.write(write_vals)
        except Exception as e:
            import logging
            _logger = logging.getLogger(__name__)
            _logger.error('portal_remediation_submit write error: %s', e)
            return request.make_json_response({'status': 'error', 'message': str(e)})

        insp = line.inspection_id
        cat_rec = line.category_id or (line.template_line_id.category_id if line.template_line_id else False)
        cat_name = cat_rec.name if cat_rec else 'Quy chuẩn'

        submit_time = datetime.now().strftime('%H:%M - %d/%m/%Y')

        return request.make_json_response({
            'status': 'success',
            'message': 'Đã gửi phản hồi khắc phục thành công!',
            'line_id': line.id,
            'inspection_id': insp.id,
            'franchise_code': insp.franchise_id.code if (insp.franchise_id and insp.franchise_id.code) else 'HN_ST042',
            'category_name': cat_name,
            'submit_time': submit_time,
            'detail_url': f"/portal/inspection/detail/{insp.id}",
        })
