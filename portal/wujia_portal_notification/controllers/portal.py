from datetime import datetime

from werkzeug.exceptions import Forbidden, NotFound

from odoo import http
from odoo.http import request
from odoo.tools.translate import LazyTranslate

from odoo.addons.wujia_portal_base.controllers.portal import (
    get_active_franchise_id,
    get_current_store_ids,
    get_store_scope_state,
)
from odoo.addons.wujia_portal_base.controllers.utils import (
    build_pager,
    date_range_error,
    fmt_local_dt,
    local_day_range_utc,
    portal_tz,
)

_lt = LazyTranslate(__name__)

# BA FINAL: popup 5, view list mặc định 10 record/trang (FE gửi limit trong danh sách cho phép).
PAGE_SIZE = 10
ALLOWED_LIMITS = (10, 20, 50)
POPUP_LIMIT = 5

# Bảng mã lỗi (BA controller mapping — dễ hiểu cho user portal, không lộ lỗi kỹ thuật).
# `_lt` ⇒ dịch theo ngôn ngữ người xem trong `_err` (J-V7).
ERROR_MESSAGES = {
    'SESSION_EXPIRED': _lt('Your session has expired. Please log in again.'),
    'STORE_NOT_SELECTED': _lt('Please select a store first.'),
    'STORE_ACCESS_DENIED': _lt('You do not have permission to act on this store.'),
    'INVALID_FILTER': _lt('Invalid filter. Please check again.'),
    'INVALID_PAGE_SIZE': _lt('Invalid number of records per page.'),
    'ANNOUNCEMENT_NOT_AVAILABLE': _lt('The notification does not exist, has been withdrawn or you do not have permission to view it.'),
    'MARK_READ_FAILED': _lt('Could not update the read status. Please try again.'),
    'ATTACHMENT_NOT_AVAILABLE': _lt('The document does not exist or you do not have permission to download it.'),
}

# PC desktop — type code → (tone css, feather icon); priority → (nhãn, badge css) theo keys BA.
PC_TYPE_TONE = {
    'URG': ('wj-pc-noti-type--red', 'icon-alert-triangle'),
    'GEN': ('wj-pc-noti-type--cyan', 'icon-bell'),
    'PROMO': ('wj-pc-noti-type--amber', 'icon-gift'),
    'SYS': ('wj-pc-noti-type--violet', 'icon-settings'),
    'OTH': ('wj-pc-noti-type--green', 'icon-info'),
}
# Nhãn mức độ portal (`_lt`, vi_VN = "Thông thường / Quan trọng / Cần làm"); dịch lúc render
# bằng `_priority_labels` / `_pc_priority_tags` (J-V7).
# Key phải khớp PRIORITY_SELECTION trong wujia_notification/models/wujia_notification.py.
PORTAL_PRIORITY_LABELS = {
    'normal': _lt('Regular'),
    'important': _lt('Important'),
    'urgent': _lt('Action required'),
}
PC_PRIORITY_TAGS = {
    'urgent': (PORTAL_PRIORITY_LABELS['urgent'], 'wj-pc-badge--done'),
    'important': (PORTAL_PRIORITY_LABELS['important'], 'wj-pc-badge--transit'),
    'normal': (PORTAL_PRIORITY_LABELS['normal'], 'wj-pc-badge--confirmed'),
}
VALID_PRIORITIES = ('normal', 'important', 'urgent')


def _error_message(code):
    """Câu lỗi theo mã, dịch theo ngôn ngữ user; mã lạ ⇒ trả nguyên mã."""
    msg = ERROR_MESSAGES.get(code)
    return request.env._(msg) if msg else code


def _priority_labels():
    """{priority: nhãn đã dịch} — dùng cho popup chuông (JSON)."""
    return {key: request.env._(label) for key, label in PORTAL_PRIORITY_LABELS.items()}


def _pc_priority_tags():
    """PC_PRIORITY_TAGS với nhãn đã dịch theo ngôn ngữ người xem."""
    return {key: (request.env._(label), css) for key, (label, css) in PC_PRIORITY_TAGS.items()}


def _err(code, **extra):
    """Payload lỗi JSON — cùng shape với wujia_portal_sale để FE portal xử lý đồng nhất."""
    res = {'success': False, 'error': code, 'message': _error_message(code)}
    res.update(extra)
    return res


def _parse_date(value):
    """'YYYY-MM-DD' (HTML date input) → date, hoặc None."""
    if not value:
        return None
    try:
        return datetime.strptime(value, '%Y-%m-%d').date()
    except (TypeError, ValueError):
        return None


def _parse_int(value, default=None):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _noti():
    return request.env['wujia.notification'].sudo()


class WujiaPortalNotification(http.Controller):

    # ---- read status: toàn hệ theo user, chỉ định theo user + cửa hàng (luật ở model) ----
    def _read_ids(self, noti_ids, franchise_id):
        return _noti()._portal_read_ids(request.env.user, noti_ids, franchise_id)

    def _unread_count(self, franchise_ids, franchise_id):
        return _noti()._portal_unread_count(request.env.user, franchise_ids, franchise_id)

    def _empty_list_values(self, date_from, date_to, filter_error, keyword, tab,
                           read_status, priority, type_id, limit):
        """Ctx danh sách rỗng — dùng khi bộ lọc không hợp lệ nên không chạy query."""
        lim = _parse_int(limit) or PAGE_SIZE
        if lim not in ALLOWED_LIMITS:
            lim = PAGE_SIZE
        if read_status not in ('all', 'read', 'unread'):
            read_status = 'all'
        return {
            'notifications': request.env['wujia.notification'].browse(),
            'read_ids': [],
            'types': request.env['wujia.notification.type'].sudo().search(
                [('active', '=', True)], order='sequence'),
            'pgn': build_pager(0, 1, lim, path='/portal/notification',
                               item_label=_lt('notifications'),
                               page_size_options=ALLOWED_LIMITS,
                               size_param='limit'),
            'type_id': _parse_int(type_id), 'keyword': keyword, 'tab': tab,
            'total': 0,
            'cnt_unread': self._unread_count(get_current_store_ids(),
                                             get_active_franchise_id()),
            'unread': '1' if read_status == 'unread' else '',
            'read_status': read_status, 'filter_error': filter_error,
            'date_from': date_from, 'date_to': date_to, 'priority': priority,
            'page_size': lim,
            'PC_TYPE_TONE': PC_TYPE_TONE, 'PC_PRIORITY_TAGS': _pc_priority_tags(),
            'wj_dt': fmt_local_dt, 'store_scope': get_store_scope_state(),
        }

    def _notification_list_values(self, page=1, type_id=None, keyword='',
                                  tab='recent', unread=None, read_status=None,
                                  date_from='', date_to='', priority='',
                                  limit=None, **kw):
        """Context danh sách thông báo — dùng chung cho trang đầy đủ và fragment AJAX."""
        franchise_ids = get_current_store_ids()
        active_fid = get_active_franchise_id()
        Noti = _noti()

        # Trạng thái đọc canonical {all,read,unread}; back-compat ?unread=1.
        if read_status not in ('all', 'read', 'unread'):
            read_status = 'unread' if unread else 'all'

        # List = lịch sử (gồm cả hết hiệu lực); badge "Đã hết hiệu lực" phân biệt.
        domain = Noti._portal_history_domain(franchise_ids)

        # Lọc theo ngày gửi. Ngày ngược: KHÔNG bỏ lọc rồi chạy tiếp — làm vậy màn
        # trả về TOÀN BỘ thông báo, khác hẳn khoảng người dùng đang thấy trong ô.
        # Chặn query, giữ chữ đã gõ, báo tại thanh lọc (chuẩn chung).
        df, dt = _parse_date(date_from), _parse_date(date_to)
        filter_error = date_range_error(df, dt)
        if filter_error:
            return self._empty_list_values(date_from, date_to, filter_error,
                                           keyword, tab, read_status, priority,
                                           type_id, limit)
        # Ngày người dùng chọn là giờ địa phương, cột published_date là UTC (WJ-NOTI-001).
        utc_from, utc_to = local_day_range_utc(df, dt, portal_tz())
        if utc_from:
            domain.append(('published_date', '>=', utc_from))
        if utc_to:
            domain.append(('published_date', '<=', utc_to))

        tid = _parse_int(type_id)
        if tid:
            domain.append(('type_id', '=', tid))
        if keyword:
            domain += ['|', '|',
                       ('name', 'ilike', keyword),
                       ('dispatch_number', 'ilike', keyword),
                       ('summary', 'ilike', keyword)]
        if priority in VALID_PRIORITIES:
            domain.append(('priority', '=', priority))

        # Lọc đã đọc / chưa đọc — "Chưa đọc" dùng CHUNG luật với chuông/Home (WJ-NOTI-001):
        # còn hiệu lực + chưa có dấu đúng phạm vi; hết hạn chỉ còn ở lịch sử.
        user = request.env.user
        if read_status == 'read':
            domain += Noti._portal_read_domain(user, active_fid)
        elif read_status == 'unread':
            domain += Noti._portal_unread_domain(user, franchise_ids, active_fid)

        # Page size — chỉ nhận giá trị cho phép, else default.
        lim = _parse_int(limit) or PAGE_SIZE
        if lim not in ALLOWED_LIMITS:
            lim = PAGE_SIZE
        page = max(1, _parse_int(page) or 1)
        offset = (page - 1) * lim

        total = Noti.search_count(domain)
        notifications = Noti.search(domain, limit=lim, offset=offset,
                                    order='is_pinned desc, published_date desc')

        read_ids = self._read_ids(notifications.ids, active_fid)
        cnt_unread = self._unread_count(franchise_ids, active_fid)

        types = request.env['wujia.notification.type'].sudo().search(
            [('active', '=', True)], order='sequence')
        pgn = build_pager(total, page, lim, path='/portal/notification',
                          item_label=_lt('notifications'),
                          page_size_options=ALLOWED_LIMITS, size_param='limit')
        return {
            'notifications': notifications,
            'read_ids': read_ids, 'types': types, 'pgn': pgn,
            'type_id': tid, 'keyword': keyword, 'tab': tab,
            'total': total, 'cnt_unread': cnt_unread,
            'unread': '1' if read_status == 'unread' else '',
            'read_status': read_status, 'filter_error': '',
            'date_from': date_from, 'date_to': date_to, 'priority': priority,
            'page_size': lim,
            'PC_TYPE_TONE': PC_TYPE_TONE, 'PC_PRIORITY_TAGS': _pc_priority_tags(),
            'wj_dt': fmt_local_dt, 'store_scope': get_store_scope_state(),
        }

    @http.route(['/portal/notification'], type='http', auth='user', sitemap=False)
    def portal_notification_list(self, **kw):
        return request.render('wujia_portal_notification.portal_notification_list',
                              self._notification_list_values(**kw))

    @http.route(['/portal/notification/results'], type='http', auth='user', sitemap=False)
    def portal_notification_results(self, **kw):
        """Fragment các khối kết quả cho lọc AJAX — cùng context, bỏ shell portal."""
        return request.render('wujia_portal_notification.portal_notification_results',
                              self._notification_list_values(**kw))

    @http.route(['/portal/notification/<int:notification_id>'],
                type='http', auth='user', sitemap=False)
    def portal_notification_detail(self, notification_id, **kw):
        franchise_ids = get_current_store_ids()
        active_fid = get_active_franchise_id()
        Noti = _noti()
        # History domain → cho phép mở lại thông báo đã hết hiệu lực từ lịch sử.
        noti = Noti.search(
            [('id', '=', notification_id)] + Noti._portal_history_domain(franchise_ids), limit=1)
        if not noti:
            return request.redirect('/portal/notification')
        # Chưa chọn cửa hàng: chỉ mở được bài toàn hệ — vẫn ghi đã đọc theo user (WJ-NOTI-001).
        request.env['wujia.notification.read'].sudo()._mark_read(
            request.env.user, active_fid, noti, opened=True, touch=True)
        return request.render('wujia_portal_notification.portal_notification_detail', {
            'noti': noti,
            'PC_TYPE_TONE': PC_TYPE_TONE, 'PC_PRIORITY_TAGS': _pc_priority_tags(),
            'wj_dt': fmt_local_dt,
        })

    @http.route(['/portal/notification/recent'], type='json',
                auth='user', methods=['POST', 'GET'])
    def portal_notification_recent(self, **kw):
        """Popup chuông header — 5 thông báo CÒN HIỆU LỰC gần nhất + đếm chưa đọc.
        Perf: 1 search(limit=5) + 1 read-lookup + đếm effective; chỉ chạy khi user mở popup."""
        franchise_ids = get_current_store_ids()
        active_fid = get_active_franchise_id()
        Noti = _noti()
        eff = Noti._portal_effective_domain(franchise_ids)
        recent = Noti.search(eff, limit=POPUP_LIMIT, order='is_pinned desc, published_date desc')
        read_ids = self._read_ids(recent.ids, active_fid)
        total_unread = self._unread_count(franchise_ids, active_fid)
        total_eff = Noti.search_count(eff)
        priority_labels = _priority_labels()

        items = [{
            'id': n.id,
            'name': n.name,
            'dispatch_number': n.dispatch_number or '',
            'date': fmt_local_dt(n.published_date, '%d/%m/%Y %H:%M'),
            'type_code': n.type_id.code or 'GEN',
            'type_name': n.type_id.name or '',
            'priority': n.priority or 'normal',
            'priority_label': priority_labels.get(n.priority or 'normal', ''),
            'has_file': bool(n.attachment_ids),
            'is_read': n.id in read_ids,
            'url': '/portal/notification/%s' % n.id,
        } for n in recent]
        return {'notifications': items, 'total_unread': total_unread, 'total': total_eff}

    @http.route(['/portal/notification/mark-all-read'], type='json',
                auth='user', methods=['POST'])
    def portal_notification_mark_all_read(self, **kw):
        """BA row 6 — đánh dấu TẤT CẢ thông báo chưa đọc (cùng luật chuông). Chưa chọn cửa hàng ⇒
        chỉ toàn hệ còn hiệu lực; có cửa hàng ⇒ thêm thông báo của cửa hàng đó (WJ-NOTI-001).
        Không nhận ids/filter. Không set last_open_date (chưa thực sự mở nội dung)."""
        franchise_ids = get_current_store_ids()
        active_fid = get_active_franchise_id()
        user = request.env.user
        Noti = _noti()
        unread = Noti.search(Noti._portal_unread_domain(user, franchise_ids, active_fid))
        created = request.env['wujia.notification.read'].sudo()._mark_read(user, active_fid, unread)
        return {'success': True, 'updated_count': created,
                'unread_count': self._unread_count(franchise_ids, active_fid)}

    @http.route(['/portal/notification/mark-read'], type='json',
                auth='user', methods=['POST'])
    def portal_notification_mark_read(self, notification_ids=None, **kw):
        """Bulk mark-read theo ids (back-compat). Idempotent; phạm vi dấu theo L2 `_mark_read`."""
        if not notification_ids:
            return {'success': True, 'created': 0}
        try:
            ids = [int(i) for i in notification_ids]
        except (TypeError, ValueError):
            return {'error': 'invalid_ids'}
        franchise_ids = get_current_store_ids()
        active_fid = get_active_franchise_id()
        Noti = _noti()
        accessible = Noti.search([('id', 'in', ids)] + Noti._portal_history_domain(franchise_ids))
        created = request.env['wujia.notification.read'].sudo()._mark_read(
            request.env.user, active_fid, accessible, opened=True)
        return {'success': True, 'created': created}

    @http.route(['/portal/notification/unread-count'], type='json',
                auth='user', methods=['POST', 'GET'])
    def portal_notification_unread_count(self, **kw):
        """Badge realtime — cùng luật `_portal_unread_domain` với Home / hộp chuông / lọc Chưa đọc."""
        franchise_ids = get_current_store_ids()
        active_fid = get_active_franchise_id()
        return {'count': self._unread_count(franchise_ids, active_fid)}

    @http.route(['/portal/notification/<int:notification_id>/attachment/<int:attachment_id>'],
                type='http', auth='user', sitemap=False)
    def portal_notification_attachment(self, notification_id, attachment_id, **kw):
        """BA row 7 — tải file đính kèm CÓ kiểm quyền: thông báo phải accessible + attachment
        phải thuộc đúng thông báo (đóng IDOR /web/content/ir.attachment/<id>)."""
        franchise_ids = get_current_store_ids()
        Noti = _noti()
        noti = Noti.search(
            [('id', '=', notification_id)] + Noti._portal_history_domain(franchise_ids), limit=1)
        if not noti:
            raise NotFound()
        att = noti._portal_get_attachment(attachment_id)
        if not att:
            raise Forbidden()
        return request.env['ir.binary']._get_stream_from(att).get_response(
            as_attachment=True,
        )
