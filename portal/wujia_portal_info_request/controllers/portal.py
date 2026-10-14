"""Wujia portal — Info Update Request controller.

Routes:
- GET  /portal/info-request                            list (filter)
- GET, POST /portal/info-request/new                   create
- GET  /portal/info-request/<int>                      detail
- POST /portal/info-request/<int>/cancel               cancel (form)
- GET  /portal/info-request/<int>/attachment/<int>     tải tệp (theo cửa hàng đang chọn)
- GET  /portal/info-request/franchise/<int>/values     AJAX old_value lookup

Mọi route chỉ cho Owner/Manager tại cửa hàng đang chọn (`_portal_can_request`).
"""
import logging
from urllib.parse import quote

from werkzeug.exceptions import NotFound

from odoo import _, _lt, http
from odoo.exceptions import UserError, ValidationError
from odoo.http import request

from odoo.addons.wujia_portal_base.controllers.portal import (
    get_current_store_ids, get_store_scope_state, render_no_permission,
)
from odoo.addons.wujia_portal_base.controllers.utils import (
    DEFAULT_DOC_MIME,
    PAGE_SIZE_OPTIONS,
    attach_files_to_record,
    build_pager,
    parse_page_size,
    status_badge_for,
)
from odoo.addons.wujia_info_request.models.wujia_info_update_request import REQUEST_TYPE, STATE

_logger = logging.getLogger(__name__)

PAGE_SIZE = 20
MAX_FILES = 6
MAX_FILE_MB = 5


class InfoRequestFormError(ValidationError):
    """Lỗi đầu vào form, ``errors`` = {ô: câu lỗi}."""

    def __init__(self, message, errors):
        super().__init__(message)
        self.errors = dict(errors)

# Nhãn portal của request_type (khác nhãn backend), dịch lúc render. Key khớp REQUEST_TYPE của wujia_info_request.
REQUEST_TYPE_LABELS = {
    'address': _lt('Address'),
    'phone': _lt('Phone number'),
    'email': _lt('Email'),
    'owner_name': _lt('Store owner name'),
    'bank_info': _lt('Bank information'),
    'representative': _lt('Legal representative'),
    'other': _lt('Other'),
}

STATE_LABELS = {k: (v, status_badge_for(v)) for k, v in {
    'draft': _lt('Draft'),
    'submitted': _lt('Submitted'),
    'reviewing': _lt('Viewing'),
    'approved': _lt('Approved'),
    'rejected': _lt('Rejected'),
}.items()}


def _type_labels():
    result = {}
    for code, label in REQUEST_TYPE_LABELS.items():
        result[code] = request.env._(label)
    return result


def _type_options():
    labels = _type_labels()
    return [(code, labels[code]) for code, _label in REQUEST_TYPE]


def _state_labels():
    result = {}
    for key, (label, css) in STATE_LABELS.items():
        result[key] = (request.env._(label), css)
    return result


def _can_request(franchise_ids):
    return request.env['wujia.info.update.request'].sudo()._portal_can_request(franchise_ids)


def _no_permission():
    return render_no_permission(
        _('Information update requests'),
        _("You do not have permission to view this store's information update requests."))


class WujiaPortalInfoRequest(http.Controller):

    @http.route(['/portal/info-request'], type='http', auth='user', sitemap=False)
    def portal_info_request_list(self, page=1, state='', request_type='',
                                 page_size=None, **kw):
        franchise_ids = get_current_store_ids()
        if not franchise_ids:
            return request.render(
                'wujia_portal_info_request.portal_info_request_list',
                {'requests': [], 'pgn': None, 'state_labels': _state_labels(),
                 'no_franchise': True, 'store_scope': get_store_scope_state(),
                 'state': '', 'request_type': '',
                 'request_type_options': _type_options()},
            )
        if not _can_request(franchise_ids):
            return _no_permission()
        Model = request.env['wujia.info.update.request'].sudo()
        domain = Model._portal_scope_domain(franchise_ids)
        if state and state in dict(STATE):
            domain.append(('state', '=', state))
        if request_type and request_type in dict(REQUEST_TYPE):
            domain.append(('request_type', '=', request_type))
        try:
            page = max(1, int(page))
        except (TypeError, ValueError):
            page = 1
        size = parse_page_size(page_size, PAGE_SIZE)
        total = Model.search_count(domain)
        pgn = build_pager(total, page, size, path='/portal/info-request',
                          item_label=_lt('requests'),
                          page_size_options=PAGE_SIZE_OPTIONS)
        recs = Model.search(domain, limit=size, offset=pgn['offset'],
                            order='request_date desc')
        return request.render(
            'wujia_portal_info_request.portal_info_request_list',
            {
                'requests': recs,
                'pgn': pgn,
                'state_labels': _state_labels(),
                'no_franchise': False,
                'state': state, 'request_type': request_type,
                'request_type_options': _type_options(),
            },
        )

    @http.route(['/portal/info-request/new'], type='http', auth='user',
                methods=['GET', 'POST'], sitemap=False, csrf=True)
    def portal_info_request_new(self, **post):
        franchise_ids = get_current_store_ids()
        if not franchise_ids:
            return request.redirect('/portal/info-request')

        if not _can_request(franchise_ids):
            return _no_permission()
        Model = request.env['wujia.info.update.request'].sudo()

        if request.httprequest.method != 'POST':
            return self._render_form()

        # ---------- POST ----------
        try:
            vals, action = self._parse_payload(post, franchise_ids)
        except InfoRequestFormError as e:
            return self._render_form(error=str(e), prefill=post, field_errors=e.errors)

        files = request.httprequest.files.getlist('attachments')
        try:
            rec = Model.create_from_portal(
                vals, submit=action == 'submit',
                attach=lambda r: attach_files_to_record(
                    r, files, allowed_mime=DEFAULT_DOC_MIME, max_size_mb=MAX_FILE_MB, max_count=MAX_FILES),
            )
        except (ValidationError, UserError) as e:
            return self._render_form(error=str(e), prefill=post)
        except Exception:
            _logger.exception('Info request create failed')
            return self._render_form(
                error=_("Could not submit the request. Please check the information and try again."),
                prefill=post)
        return request.redirect(
            f'/portal/info-request/{rec.id}?message=created'
        )

    @http.route(['/portal/info-request/<int:req_id>'], type='http',
                auth='user', sitemap=False)
    def portal_info_request_detail(self, req_id, **kw):
        franchise_ids = get_current_store_ids()
        if not franchise_ids:
            return request.redirect('/portal/info-request')
        if not _can_request(franchise_ids):
            return _no_permission()
        Model = request.env['wujia.info.update.request'].sudo()
        rec = Model.search([('id', '=', req_id)] + Model._portal_scope_domain(franchise_ids), limit=1)
        if not rec:
            return request.redirect('/portal/info-request')
        return request.render(
            'wujia_portal_info_request.portal_info_request_detail',
            {'rec': rec, 'state_labels': _state_labels(),
             'request_type_labels': _type_labels(),
             'message': kw.get('message')},
        )

    @http.route(['/portal/info-request/<int:req_id>/cancel'], type='http',
                auth='user', methods=['POST'], sitemap=False, csrf=True)
    def portal_info_request_cancel(self, req_id, **kw):
        franchise_ids = get_current_store_ids()
        if not franchise_ids:
            return request.redirect('/portal/info-request')
        if not _can_request(franchise_ids):
            return _no_permission()
        Model = request.env['wujia.info.update.request'].sudo()
        rec = Model.search([('id', '=', req_id), ('created_by_user_id', '=', request.env.uid)]
                           + Model._portal_scope_domain(franchise_ids), limit=1)
        if not rec:
            return request.redirect('/portal/info-request')
        try:
            rec.action_cancel()
        except ValidationError as e:
            return request.redirect(
                f'/portal/info-request/{rec.id}?message=' + quote(str(e))
            )
        return request.redirect(
            f'/portal/info-request/{rec.id}?message=cancelled'
        )

    @http.route(['/portal/info-request/<int:req_id>/attachment/<int:att_id>'],
                type='http', auth='user', sitemap=False)
    def portal_info_request_attachment(self, req_id, att_id, **kw):
        franchise_ids = get_current_store_ids()
        if not _can_request(franchise_ids):
            raise NotFound()
        Model = request.env['wujia.info.update.request'].sudo()
        rec = Model.search([('id', '=', req_id)]
                           + Model._portal_scope_domain(franchise_ids), limit=1)
        att = rec.attachment_ids.filtered(lambda a: a.id == att_id)
        if not att:
            raise NotFound()
        return request.env['ir.binary']._get_stream_from(att).get_response(as_attachment=True)

    @http.route(['/portal/info-request/franchise/<int:fid>/values'],
                type='json', auth='user', methods=['POST', 'GET'])
    def portal_info_request_get_current(self, fid, request_type=None,
                                        field_target=None, **kw):
        """AJAX: trả giá trị hiện tại trên franchise theo request_type."""
        franchise_ids = get_current_store_ids()
        if int(fid) not in franchise_ids or not _can_request(franchise_ids):
            return {'error': 'forbidden'}
        franchise = request.env['wujia.franchise.management'].sudo().browse(int(fid))
        if not franchise.exists():
            return {'error': 'not_found'}
        return {'old_value': request.env['wujia.info.update.request'].sudo()._franchise_value(
            franchise, request_type, field_target)}

    # ============================================================== helpers
    def _render_form(self, error=None, prefill=None, field_errors=None):
        franchise_ids = get_current_store_ids()
        franchises = request.env['wujia.franchise.management'].sudo().browse(franchise_ids)
        return request.render(
            'wujia_portal_info_request.portal_info_request_form',
            {
                'franchises': franchises,
                'request_type_options': _type_options(),
                'error': error,
                'field_errors': field_errors or {},
                'values': prefill or {},
                'max_files': MAX_FILES,
                'max_file_mb': MAX_FILE_MB,
            },
        )

    def _parse_payload(self, post, accessible_fids):
        errors = []
        try:
            franchise_id = int(post.get('franchise_id') or 0)
        except (TypeError, ValueError):
            franchise_id = None
            errors.append(('franchise_id', _("Invalid store.")))
        if franchise_id is None:
            pass
        elif not franchise_id:
            errors.append(('franchise_id', _("Please select a store.")))
        elif franchise_id not in set(accessible_fids):
            errors.append(('franchise_id', _("You cannot access this store.")))

        request_type = post.get('request_type') or ''
        if not request_type:
            errors.append(('request_type', _("Please select an information type.")))
        elif request_type not in dict(REQUEST_TYPE):
            errors.append(('request_type', _("Invalid information type.")))

        field_target = (post.get('field_target') or '').strip()
        if request_type == 'other' and not field_target:
            errors.append(('field_target', _("Enter the field name when choosing 'Other'.")))

        new_value = (post.get('new_value') or '').strip()
        if not new_value:
            errors.append(('new_value', _("Please enter the new value.")))
        if errors:
            message = errors[0][1] if len(errors) == 1 else _("Please fill in all required fields.")
            raise InfoRequestFormError(message, errors)

        action = (post.get('action') or 'draft').strip()
        if action not in ('draft', 'submit'):
            action = 'draft'

        priority = post.get('priority') or 'normal'
        if priority not in ('normal', 'urgent'):
            priority = 'normal'

        return {
            'franchise_id': franchise_id,
            'request_type': request_type,
            'field_target': field_target or False,
            'new_value': new_value[:5000],
            'note': (post.get('note') or '').strip()[:2000],
            'priority': priority,
        }, action
