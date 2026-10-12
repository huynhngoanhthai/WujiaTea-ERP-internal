from datetime import timedelta

from odoo import _, fields, http
from odoo.http import request
from odoo.tools.translate import LazyTranslate
from odoo.addons.portal.controllers.portal import CustomerPortal
from odoo.addons.wujia_portal_layout.controllers.utils import safe_local_path
from odoo.addons.wujia_portal_base.controllers.utils import (
    PAGE_SIZE_OPTIONS,
    build_pager,
    fmt_local_dt,
    get_upcoming_batches,
    parse_page_size,
    portal_money,
    portal_order_badge,
    return_status_label,
)
from odoo.addons.wujia_portal_base.models.wujia_franchise_member import ROLE_LABELS


STORE_ADMIN_ROLES = ('owner', 'manager')

_lt = LazyTranslate(__name__)

# Nhãn portal của wujia.franchise.management.status — câu gốc EN, tiếng Việt ở i18n/vi_VN.po
# (J-V2; trước đó pin cứng tiếng Việt). Key phải khớp Selection `status` trong
# wujia_franchise/models/wujia_franchise_management.py.
FRANCHISE_STATUS_LABELS = {
    'draft': _lt('Draft'),
    'active': _lt('Enabled'),
    'locked': _lt('Locked'),
    'closed': _lt('Closed'),
    'expired': _lt('Expired'),
}

ACTIVE_FRANCHISE_COOKIE = 'wujia_active_franchise_id'
ACTIVE_FRANCHISE_COOKIE_MAX_AGE = 30 * 24 * 3600  # 30 ngày

# Số bản ghi MỌI block preview của Home hiển thị (WJ-HOME-006). Một hằng cho cả
# 5 nguồn để không lệch nhau lần nữa; danh sách đầy đủ nằm sau "Xem tất cả".
HOME_PREVIEW_LIMIT = 2

MEMBER_PAGE_SIZE = 10


# ----------------------------------------------------------------------
# Module-level helpers — các controller portal_* khác import dùng chung.
# Cache vào `request._wujia_active_fid_cache` để 1 request chỉ tính 1 lần.
# ----------------------------------------------------------------------

def _read_active_franchise_cookie():
    raw = request.httprequest.cookies.get(ACTIVE_FRANCHISE_COOKIE)
    try:
        return int(raw) if raw else False
    except (TypeError, ValueError):
        return False


def get_active_franchise_id():
    """Trả franchise_id user đang chọn (đã validate). False nếu chưa hợp lệ.

    Cache trong request lifetime — tránh tính nhiều lần / request."""
    cached = getattr(request, '_wujia_active_fid_cache', None)
    if cached is not None:
        return cached if cached >= 0 else False

    accessible = request.env.user._get_accessible_franchise_ids()  # ormcached
    cookie_id = _read_active_franchise_cookie()
    if cookie_id and cookie_id not in accessible:
        # Cookie của cửa hàng đã mất quyền mà giữ lại sẽ che modal chọn cửa hàng.
        request.future_response.set_cookie(
            ACTIVE_FRANCHISE_COOKIE, '', max_age=0, expires=0, samesite='Lax')
    if cookie_id and cookie_id in accessible:
        result = cookie_id
    elif len(accessible) == 1:
        # Single-franchise: auto-pick — không cần modal.
        result = accessible[0]
    else:
        result = False

    request._wujia_active_fid_cache = result if result else -1
    return result


def get_current_store_ids():
    """`()` hoặc `(fid,)` — không bao giờ nhiều cửa hàng; rỗng ⇒ màn hiện khối nhắc chọn."""
    active = get_active_franchise_id()
    return (active,) if active else ()


def get_store_scope_state():
    """'ok' · 'need_pick' (nhiều cửa hàng, chưa chọn) · 'no_store' (chưa được gán)."""
    if get_active_franchise_id():
        return 'ok'
    return 'need_pick' if request.env.user._get_accessible_franchise_ids() else 'no_store'


def get_active_franchise_ids_filter():
    """DEPRECATED — chưa chọn trả MỌI cửa hàng; chỉ còn cho Khảo sát (docs/handover-inspection-scope.md)."""
    active = get_active_franchise_id()
    if active:
        return (active,)
    return request.env.user._get_accessible_franchise_ids()


def get_current_store_role():
    """Role của user tại cửa hàng đang chọn; False nếu chưa chọn."""
    cached = getattr(request, '_wujia_active_role_cache', None)
    if cached is not None:
        return cached
    fid = get_active_franchise_id()
    role = next((m.role for m in request.env.user._get_active_franchise_memberships()
                 if m.franchise_id.id == fid), False) if fid else False
    request._wujia_active_role_cache = role
    return role


def is_current_store_admin():
    return get_current_store_role() in STORE_ADMIN_ROLES


def render_no_permission(title, message):
    return request.render('wujia_portal_base.portal_no_permission',
                          {'np_title': title, 'np_message': message}, status=403)


def _float_to_hhmm(value):
    """Convert float giờ 10.5 → '10:30'. Tolerates None/invalid → '—'.

    Bản local trong wujia_portal_base — KHÔNG import từ wujia_portal_sale
    (base không phụ thuộc sale, tránh reverse dependency)."""
    try:
        v = float(value or 0.0) % 24.0
    except (TypeError, ValueError):
        return '—'
    h = int(v)
    m = int(round((v - h) * 60))
    if m == 60:
        h, m = (h + 1) % 24, 0
    return f'{h:02d}:{m:02d}'


class WujiaPortal(CustomerPortal):

    # ==================================================================
    # /portal — Dashboard (PC mockup V4 · mobile Figma Sprint 10)
    # ==================================================================
    @http.route(['/portal'], type='http', auth='user', website=False, sitemap=False)
    def portal_home(self, **kw):
        franchise_ids = get_current_store_ids()
        store_scope = get_store_scope_state()
        accessible_ids = request.env.user._get_accessible_franchise_ids()
        values = self._dashboard_values(franchise_ids)

        # ---- Cửa hàng + role + khung giờ: hero mobile (Figma Sprint 10) VÀ hàng đầu PC (V4, G3a) ----
        active_fid = get_active_franchise_id()
        Franchise = request.env['wujia.franchise.management'].sudo()
        active_franchise = Franchise.browse(active_fid).exists() if active_fid else Franchise.browse()
        active_role = get_current_store_role()
        # Currency mà cửa hàng thực sự đặt hàng bằng — CÙNG nguồn với giỏ và SO
        # (bảng giá của partner cửa hàng), không có bảng giá thì rơi về công ty.
        store_currency = (
            active_franchise.partner_id.property_product_pricelist.currency_id
            if active_franchise and active_franchise.partner_id else False
        ) or request.env.company.currency_id

        # ---- Sprint 17: 3 màn dashboard (Figma 2474:2) gộp về Home (dedupe).
        #      BA còn review. recent_orders/latest_returns/active_franchise đã có
        #      sẵn ở _dashboard_values — chỉ bổ sung batch + articles + hotline. ----
        franchise_ids_list = list(franchise_ids) if franchise_ids else []
        upcoming = (
            get_upcoming_batches(franchise_ids_list, limit=HOME_PREVIEW_LIMIT)
            if franchise_ids_list else {'items': [], 'undelivered_count': 0}
        )
        # Knowledge — base KHÔNG depend wujia_knowledge → guard registry
        # (cùng pattern _safe_count/_safe_list; KHÔNG thêm depends, tránh coupling).
        Article = request.env.get('wujia.knowledge.article')
        articles = []
        if Article is not None and hasattr(Article, '_portal_visible_domain'):
            articles = Article.sudo().search(
                Article._portal_visible_domain(),
                order='publish_date desc, id desc', limit=HOME_PREVIEW_LIMIT,
            )

        values.update({
            # Sprint 17 dashboard-merge keys (mobile home d-lg-none)
            'm_upcoming_batches': upcoming['items'],
            'm_undelivered_count': upcoming['undelivered_count'],
            'wj_order_badge': portal_order_badge,
            'wj_return_status': return_status_label,
            'articles': articles,
            'm_hotline': request.env.company.sudo().phone or '',
            'title': _('Home - Portal'),
            'lang': request.env.lang or 'en',
            'role_labels': ROLE_LABELS,
            'store_scope': store_scope,
            # Cho modal store-picker render điều kiện — theo lựa chọn ĐÃ validate, không theo
            # cookie thô (cookie của cửa hàng đã mất quyền từng làm Home không bật picker).
            'must_pick_franchise': store_scope == 'need_pick',
            'all_accessible_franchises': request.env['wujia.franchise.management']
                .sudo().browse(list(accessible_ids)) if accessible_ids
                else request.env['wujia.franchise.management'].browse(),
            'active_franchise_id': active_fid,
            # dùng chung hero mobile + hàng đầu PC (G3a) — một nguồn cho hai kênh
            'active_franchise': active_franchise,
            'active_role': active_role,
            # Nhân viên không nhận số liệu tài chính; chưa chọn cửa hàng ⇒ ô "—" như cũ.
            'show_debt_kpi': not active_fid or active_role in STORE_ADMIN_ROLES,
            'order_window': self._order_window_view(active_franchise),
            # Format tiền dùng chung — ký hiệu theo currency của đơn, không hardcode.
            'money': portal_money,
            'company_currency_symbol': request.env.company.currency_id.symbol or '',
            'company_currency_decimals': request.env.company.currency_id.decimal_places or 0,
            # Các con số GỘP TỪ ĐƠN (top sản phẩm, tổng tiền chuyến giao) mang currency
            # của ĐƠN chứ không phải của công ty. Lấy đúng nguồn mà giỏ và SO dùng —
            # bảng giá của cửa hàng — nếu không thì UAT (đơn USD, công ty VND) hiện số
            # USD mà dán ký hiệu ₫, đúng kiểu lỗi WJ-ORD-025 vừa sửa.
            'store_currency_symbol': store_currency.symbol or '',
            'store_currency_decimals': store_currency.decimal_places or 0,
        })
        return request.render('wujia_portal_base.portal_home_page', values)

    def _order_window_view(self, franchise=None):
        """Trạng thái khung giờ cho Home — cùng một kết quả với chặn submit (giờ địa phương cửa hàng).

        state: 'always' (tắt giới hạn) · 'open' (+ to_hhmm, remaining_hhmm, progress_pct) ·
        'closed' (+ from_hhmm) · 'tz_missing' (cửa hàng chưa có múi giờ ⇒ không đặt được).
        """
        Settings = request.env['res.config.settings'].sudo()
        # ADR-027: L3a cấm thêm depend `wujia_order_window`. Module tắt ⇒ coi như không đặt khung giờ.
        if not (hasattr(Settings, '_is_within_order_window') and hasattr(Settings, '_next_order_window')):
            return {'state': 'always'}
        allowed, window = Settings._is_within_order_window(franchise=franchise or None)
        if window.get('tz_missing'):
            return {'state': 'tz_missing'}
        if not window.get('enabled', True):
            return {'state': 'always'}

        tz_label = window.get('tz_label') or ''
        opened = window.get('open_window')
        if allowed and opened:
            f = float(opened['from'] or 0.0) % 24.0
            t = float(opened['to'] or 0.0) % 24.0
            span = (t - f) % 24.0 or 24.0  # độ dài khung (xử lý qua nửa đêm)
            elapsed = (window['now'] - f) % 24.0
            return {
                'state': 'open',
                'to_hhmm': _float_to_hhmm(t),
                'remaining_hhmm': _float_to_hhmm(max(0.0, span - elapsed)),
                'progress_pct': max(0, min(100, round(elapsed / span * 100))),
                'tz_label': tz_label,
            }
        nxt = Settings._next_order_window(franchise=franchise or None) or {}
        return {
            'state': 'closed',
            'from_hhmm': _float_to_hhmm(nxt.get('from', window.get('from') or 0.0)),
            'tz_label': tz_label,
        }

    def _dashboard_values(self, franchise_ids):
        """Pre-compute dashboard. 1 batched query / metric — KHÔNG ORM trong template loop."""
        SO = request.env['sale.order'].sudo()
        today = fields.Datetime.now()
        last_30d = today - timedelta(days=30)

        # ---- 4 KPI (Đơn hàng · Thông báo · Đổi trả; Công nợ do wujia_portal_debt) ----
        # G3a/142: bỏ "Đơn chờ xử lý" + bảng top sản phẩm (không có trong mockup V4)
        # ⇒ Home bớt 1 count + 2 _read_group. Top SP vẫn ở trang Báo cáo.
        unread_count = self._safe_count(
            'wujia.notification', 'unread_count', franchise_ids
        )
        recent_orders_count = SO.search_count([
            ('franchise_id', 'in', franchise_ids),
            ('date_order', '>=', last_30d),
            ('state', '!=', 'cancel'),
        ]) if franchise_ids else 0
        return_requests_count = self._safe_count(
            'wujia.return.request', 'open_count', franchise_ids
        )

        # ---- block list — mọi block cùng HOME_PREVIEW_LIMIT (WJ-HOME-006) ----
        latest_notifications = self._safe_list(
            'wujia.notification', franchise_ids, limit=HOME_PREVIEW_LIMIT,
        )
        recent_orders = SO.search([
            ('franchise_id', 'in', franchise_ids),
            ('state', '!=', 'cancel'),
        ], order='date_order desc', limit=HOME_PREVIEW_LIMIT) if franchise_ids else SO.browse()
        latest_returns = self._safe_list(
            'wujia.return.request', franchise_ids, limit=HOME_PREVIEW_LIMIT,
        )

        return {
            'unread_count': unread_count,
            'recent_orders_count': recent_orders_count,
            'return_requests_count': return_requests_count,
            'latest_notifications': latest_notifications,
            'recent_orders': recent_orders,
            'latest_returns': latest_returns,
            'franchise_ids': franchise_ids,
            'wj_dt': fmt_local_dt,
        }

    def _safe_count(self, model_name, kind, franchise_ids):
        if not franchise_ids:
            return 0
        Model = request.env.get(model_name)
        if Model is None:
            return 0
        Model = Model.sudo()
        if kind == 'unread_count' and hasattr(Model, '_portal_unread_count'):
            # Cùng luật với badge chuông: còn hiệu lực, chưa đọc tại cửa hàng đang chọn.
            return Model._portal_unread_count(
                request.env.user, franchise_ids, get_active_franchise_id())
        if kind == 'open_count' and hasattr(Model, '_portal_open_domain'):
            # Cùng luật với /portal/return: BA không tính nháp.
            return Model.search_count(Model._portal_open_domain(franchise_ids))
        return 0

    def _safe_list(self, model_name, franchise_ids, limit=5):
        if not franchise_ids:
            return []
        Model = request.env.get(model_name)
        if Model is None:
            return []
        Model = Model.sudo()
        if model_name == 'wujia.notification' and hasattr(Model, '_portal_effective_domain'):
            # Cùng luật với popup chuông: không hiện bài hẹn giờ / hết hiệu lực.
            return Model.search(Model._portal_effective_domain(franchise_ids),
                                order='is_pinned desc, published_date desc', limit=limit)
        if model_name == 'wujia.return.request' and hasattr(Model, '_portal_recent_domain'):
            # BA: danh sách gần đây bỏ phiếu đã huỷ / từ chối.
            return Model.search(Model._portal_recent_domain(franchise_ids),
                                order='request_date desc', limit=limit)
        return []

    # ==================================================================
    # Active-franchise (store picker) — cookie-based, no DB hit
    # Module-level helpers: get_active_franchise_id(), get_current_store_ids(),
    #     get_store_scope_state(), get_current_store_role(), is_current_store_admin()
    #     (get_active_franchise_ids_filter() DEPRECATED — chỉ còn cho Khảo sát).
    # ==================================================================
    @http.route(['/portal/franchise/switch'], type='http', auth='user',
                methods=['POST'], website=False, csrf=True, sitemap=False)
    def portal_franchise_switch(self, franchise_id=None, redirect='/portal', **kw):
        """Set cookie active franchise. Validate user có quyền trước khi set."""
        accessible = request.env.user._get_accessible_franchise_ids()
        try:
            fid = int(franchise_id)
        except (TypeError, ValueError):
            return request.redirect('/portal')
        if fid not in accessible:
            return request.redirect('/portal')

        target = safe_local_path(redirect)
        response = request.redirect(target)
        response.set_cookie(
            ACTIVE_FRANCHISE_COOKIE,
            str(fid),
            max_age=ACTIVE_FRANCHISE_COOKIE_MAX_AGE,
            samesite='Lax',
            httponly=False,  # JS có thể đọc tên cửa hàng đang active
        )
        return response

    @http.route(['/portal/franchise/clear'], type='http', auth='user',
                methods=['POST'], website=False, csrf=True, sitemap=False)
    def portal_franchise_clear(self, **kw):
        response = request.redirect('/portal')
        response.delete_cookie(ACTIVE_FRANCHISE_COOKIE)
        return response

    # ==================================================================
    # Counter for /my homepage card (Odoo standard portal)
    # ==================================================================
    def _prepare_home_portal_values(self, counters):
        values = super()._prepare_home_portal_values(counters)
        if 'franchise_count' in counters:
            values['franchise_count'] = len(
                request.env.user._get_active_franchise_memberships()
            )
        return values

    # ==================================================================
    # Franchise profile (đầy đủ thông tin nhượng quyền — BA spec mục 10)
    # ==================================================================
    @http.route(['/portal/franchises/<int:franchise_id>/profile'],
                type='http', auth='user', sitemap=False)
    def wujia_portal_franchise_profile(self, franchise_id, **kw):
        membership = self._get_membership_or_redirect(franchise_id)
        if isinstance(membership, http.Response):
            return membership
        membership_sudo = membership.sudo()
        return request.render(
            'wujia_portal_base.portal_franchise_profile_full', {
                'title': _('Store profile'),
                'franchise': membership_sudo.franchise_id,
                'membership': membership_sudo,
                'role_labels': ROLE_LABELS,
                'status_labels': FRANCHISE_STATUS_LABELS,
            },
        )

    # ==================================================================
    # /my/franchises  + /portal/franchises (Vuexy layout mirror)
    # ==================================================================
    @http.route(['/my/franchises'], type='http', auth='user', website=True)
    def portal_my_franchises(self, **kw):
        memberships = request.env.user._get_active_franchise_memberships().sudo()
        return request.render('wujia_portal_base.portal_my_franchises', {
            'page_name': 'franchises',
            'memberships': memberships,
            'role_labels': ROLE_LABELS,
        })

    @http.route(['/portal/franchises'], type='http', auth='user', sitemap=False)
    def wujia_portal_franchises(self, **kw):
        memberships = request.env.user._get_active_franchise_memberships().sudo()
        return request.render('wujia_portal_base.portal_franchises_list', {
            'memberships': memberships,
            'role_labels': ROLE_LABELS,
        })

    @http.route(['/portal/franchises/<int:franchise_id>'],
                type='http', auth='user', sitemap=False)
    def wujia_portal_franchise_detail(self, franchise_id, **kw):
        membership = self._get_membership_or_redirect(franchise_id)
        if isinstance(membership, http.Response):
            return request.redirect('/portal/franchises')
        membership_sudo = membership.sudo()
        members = self._members_if_admin(membership_sudo)
        return request.render('wujia_portal_base.portal_franchise_detail', {
            'franchise': membership_sudo.franchise_id,
            'membership': membership_sudo,
            'members': members,
            'role_labels': ROLE_LABELS,
        })

    @http.route(['/my/franchises/<int:franchise_id>'],
                type='http', auth='user', website=True)
    def portal_my_franchise_detail(self, franchise_id, **kw):
        membership = self._get_membership_or_redirect(franchise_id)
        if isinstance(membership, http.Response):
            return membership
        membership_sudo = membership.sudo()
        members = self._members_if_admin(membership_sudo)
        return request.render('wujia_portal_base.portal_my_franchise_detail', {
            'page_name': 'franchise_detail',
            'franchise': membership_sudo.franchise_id,
            'membership': membership_sudo,
            'members': members,
            'role_labels': ROLE_LABELS,
        })

    @http.route(['/my/franchises/<int:franchise_id>/members'],
                type='jsonrpc', auth='user')
    def portal_franchise_members_json(self, franchise_id, **kw):
        membership = request.env['wujia.franchise.member'].sudo().search([
            ('user_id', '=', request.env.user.id),
            ('franchise_id', '=', franchise_id),
            ('is_currently_valid', '=', True),
        ], limit=1)
        if membership.role not in STORE_ADMIN_ROLES:
            return {'error': 'forbidden'}
        members = self._members_if_admin(membership)
        return {
            'members': [{
                'id': m.id,
                'user_name': m.user_id.name,
                'role': m.role,
                'role_label': m._portal_role_label(),
                'is_primary_owner': m.is_primary_owner,
                'date_from': m.date_from.isoformat() if m.date_from else None,
                'date_to': m.date_to.isoformat() if m.date_to else None,
            } for m in members],
        }

    # ==================================================================
    # Franchise Information menu (BA spec Section A — readonly snapshot
    # của cửa hàng + user tab + thông tin nhượng quyền cho cửa hàng đang
    # active. Không cho sửa — chức năng cập nhật đã có module
    # wujia_portal_info_request.)
    # ==================================================================
    @http.route(['/portal/franchise-information'], type='http', auth='user',
                website=False, sitemap=False)
    def portal_franchise_information(self, **kw):
        fid = get_active_franchise_id()
        if not fid:
            return request.redirect('/portal')
        membership = self._get_membership_or_redirect(fid)
        if isinstance(membership, http.Response):
            return membership
        membership_sudo = membership.sudo()
        franchise = membership_sudo.franchise_id
        # Hard gate per BA: portal_locked or status != 'active' → block
        if franchise.portal_locked or franchise.status != 'active':
            return request.render('wujia_portal_base.portal_franchise_information_locked', {
                'title': _('Store profile'),
                'franchise': franchise,
            })
        is_owner_manager = membership_sudo.role in STORE_ADMIN_ROLES
        Member = request.env['wujia.franchise.member'].sudo()
        members, pgn = Member.browse(), None
        if is_owner_manager:
            mdomain = [('franchise_id', '=', fid), ('is_currently_valid', '=', True)]
            pgn = build_pager(Member.search_count(mdomain), kw.get('page', 1),
                              parse_page_size(kw.get('page_size'), MEMBER_PAGE_SIZE),
                              path='/portal/franchise-information',
                              item_label=_lt('members'),
                              page_size_options=PAGE_SIZE_OPTIONS)
            members = Member.search(mdomain, limit=pgn['page_size'],
                                    offset=pgn['offset'], order='role, id')
        return request.render('wujia_portal_base.portal_franchise_information', {
            'title': _('Store profile'),
            'page_name': 'franchise_information',
            'franchise': franchise,
            'membership': membership_sudo,
            'members': members,
            'pgn': pgn,
            'is_owner_manager': is_owner_manager,
            'role_labels': ROLE_LABELS,
            'status_labels': FRANCHISE_STATUS_LABELS,
        })

    # ==================================================================
    # Backwards-compat redirects: /my/branches → /my/franchises
    # ==================================================================
    @http.route(['/my/branches'], type='http', auth='user', sitemap=False)
    def _redirect_my_branches(self, **kw):
        return request.redirect('/my/franchises', code=301)

    @http.route(['/my/branches/<int:branch_id>'], type='http', auth='user', sitemap=False)
    def _redirect_my_branch_detail(self, branch_id, **kw):
        return request.redirect(f'/my/franchises/{branch_id}', code=301)

    @http.route(['/portal/branches'], type='http', auth='user', sitemap=False)
    def _redirect_portal_branches(self, **kw):
        return request.redirect('/portal/franchises', code=301)

    @http.route(['/portal/branches/<int:branch_id>'],
                type='http', auth='user', sitemap=False)
    def _redirect_portal_branch_detail(self, branch_id, **kw):
        return request.redirect(f'/portal/franchises/{branch_id}', code=301)

    # ==================================================================
    # Helpers
    # ==================================================================
    def _members_if_admin(self, membership):
        if membership.role not in STORE_ADMIN_ROLES:
            return request.env['wujia.franchise.member'].sudo().browse()
        return request.env['wujia.franchise.member'].sudo().search([
            ('franchise_id', '=', membership.franchise_id.id),
            ('is_currently_valid', '=', True),
        ])

    def _get_membership_or_redirect(self, franchise_id):
        membership = request.env['wujia.franchise.member'].search([
            ('user_id', '=', request.env.user.id),
            ('franchise_id', '=', franchise_id),
            ('is_currently_valid', '=', True),
        ], limit=1)
        if not membership:
            return request.redirect('/my/franchises')
        return membership
