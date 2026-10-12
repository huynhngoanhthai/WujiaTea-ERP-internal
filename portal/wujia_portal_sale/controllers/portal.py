"""Wujia portal — sale (catalog + giỏ hàng chung theo cửa hàng + submit).

Sprint 30 — theo BA controller mapping FINAL ("Controller Product + Cart"):
- Giỏ = `wujia.portal.cart` DÙNG CHUNG theo store (1 store 1 giỏ, mọi user
  membership hợp lệ thao tác chung, last-write-wins, mutation trả full state).
- Sản phẩm = product.product `is_public_portal` + giá theo pricelist của partner
  cửa hàng (backend là nguồn giá duy nhất — không tin giá FE).
- Step đặt hàng = min_qty; max_qty=0 nghĩa là không giới hạn.
- Submit: SO luôn DRAFT + huỷ draft/sent portal cũ cùng store (nguyên khối) +
  khoá giỏ FOR UPDATE NOWAIT (savepoint — tránh Odoo retry nuốt LockNotAvailable).
- Khung giờ chỉ chặn tại submit; thao tác giỏ ngoài giờ vẫn cho (BA).

Routes:
- GET  /portal/order                        catalog (PC combined + mobile)
- GET  /portal/order/product/<int>          product detail (variant)
- GET  /portal/order/cart                   full cart view
- POST /portal/order/cart/add     (json)    atomic upsert +min_qty
- POST /portal/order/cart/update  (json)    set qty (min/step/max)
- POST /portal/order/cart/remove  (json)    delete line (idempotent)
- GET  /portal/order/cart/count   (json)    badge count
- POST /portal/order/cart/note    (json)    save shared note
- POST /portal/order/submit       (http)    draft SO + cancel old + clear cart
- GET  /portal/order/submitted/<int>        màn kết quả "đặt hàng thành công" (mobile)
- GET  /portal/order/rejected               màn kết quả "ngoài khung giờ" (mobile)
"""
import logging
from collections import defaultdict

from odoo import fields, http
from odoo.http import request
from odoo.tools.translate import LazyTranslate

from odoo.addons.wujia_portal_base.controllers.portal import (
    ACTIVE_FRANCHISE_COOKIE,
    get_active_franchise_id,
)
from odoo.addons.wujia_portal_base.controllers.utils import (
    build_pager,
    parse_page_size,
    portal_line_price_vals,
    portal_money,
    portal_order_state_badge,
    portal_tax_mapper,
    rate_limit,
)
from odoo.addons.wujia_portal_sale.models.wujia_portal_cart import PortalOrderError
# Nhãn trạng thái SO dùng CHUNG với trang Lịch sử đặt hàng — không nhân bản dict
# (draft → 'Chờ xác nhận'); màn kết quả và trang lịch sử phải luôn nói giống nhau.
from odoo.addons.wujia_portal_purchase_history.controllers.portal import _state_meta

_logger = logging.getLogger(__name__)
_lt = LazyTranslate(__name__)


PAGE_SIZE = 24
# Bậc ô "n / trang" của catalog — bội của 24 để lưới sản phẩm không vỡ hàng.
PAGE_SIZE_OPTIONS = (24, 48, 96)

# Bảng mã lỗi BA (chat "Controller Product + Cart" FINAL) + mã legacy còn lưu hành.
ERROR_MESSAGES = {
    'STORE_NOT_SELECTED': _lt("Please select a store before ordering."),
    'STORE_ACCESS_DENIED': _lt("You do not have permission to act for this store."),
    'MEMBERSHIP_INACTIVE': _lt("Your account is no longer active at this store."),
    'ORDER_TIME_NOT_CONFIGURED': _lt("Ordering hours are not configured yet. Please contact {brand}."),
    'ORDER_TIME_CLOSED': _lt("Outside ordering hours. Please submit your order during the allowed time."),
    'STORE_TZ_NOT_CONFIGURED': _lt("The store's timezone is not configured, so ordering is unavailable. Please contact {brand}."),
    'PRODUCT_NOT_AVAILABLE': _lt("This product can no longer be ordered."),
    'MIN_QTY_NOT_CONFIGURED': _lt("The minimum order quantity of this product is not configured. Please contact {brand}."),
    'QTY_BELOW_MIN': _lt("The quantity is below the product's minimum."),
    'QTY_ABOVE_MAX': _lt("The quantity exceeds the product's maximum."),
    'QTY_INVALID_STEP': _lt("The quantity must be in steps of the minimum quantity."),
    'CART_EMPTY': _lt("There are no products in the cart."),
    'CART_LOAD_FAILED': _lt("Could not load the cart. Please try again."),
    'CART_HAS_INVALID_PRODUCT': _lt("Some products in the cart can no longer be ordered. Please check again."),
    'CART_QUANTITY_INVALID': _lt("Some product quantities are invalid. Please check again."),
    'CART_IS_PROCESSING': _lt("The cart is being submitted by another user. Please try again later."),
    'STORE_CUSTOMER_NOT_CONFIGURED': _lt("The store's ordering customer is not configured. Please contact {brand}."),
    'ORDER_CREATE_FAILED': _lt("Could not create the order. Please try again or contact {brand}."),
    'OLD_PORTAL_QUOTATION_CANCEL_FAILED': _lt("Could not complete the order because an old draft order has not been processed. Please try again."),
    'PRODUCT_LIST_UNAVAILABLE': _lt("Could not load the product list. Please try again."),
    'invalid_input': _lt("The submitted data is invalid."),
    # legacy codes (redirect cũ có thể còn bookmark)
    'no_active_franchise': _lt("Please select a store before ordering."),
    'cart_empty': _lt("There are no products in the cart."),
    'branch_locked': _lt("The store is temporarily locked for ordering. Please contact {brand}."),
    'outside_order_window': _lt("Outside ordering hours. Please submit your order during the allowed time."),
    'internal_error': _lt("Something went wrong. Please try again or contact {brand}."),
}

def _error_message(code, default=''):
    """Câu lỗi theo mã — dịch theo ngôn ngữ user rồi mới điền tên thương hiệu (`{brand}`)."""
    msg = ERROR_MESSAGES.get(code)
    return request.env.company._wj_brand_text(request.env._(msg) if msg else default)


# Câu lỗi số lượng theo mã của `product._portal_qty_error` (thêm tên SP + ngưỡng).
QTY_MESSAGES = {
    'QTY_BELOW_MIN': _lt("The minimum quantity of {name} is {limit}."),
    'QTY_INVALID_STEP': _lt("The quantity of {name} must be in steps of {limit}."),
    'QTY_ABOVE_MAX': _lt("The maximum quantity of {name} is {limit}."),
}

SUCCESS_MESSAGES = {
    'order_submitted': _lt("Your order has been submitted."),
}

# Dòng giỏ không hợp lệ (đánh dấu per-line trên cart view — BA row 11).
LINE_INVALID_MESSAGES = {
    'PRODUCT_NOT_AVAILABLE': _lt("Product no longer available to order."),
    'MIN_QTY_NOT_CONFIGURED': _lt("Minimum quantity not configured for this product."),
    'CART_QUANTITY_INVALID': _lt("Invalid quantity (min/step/max)."),
}


# Gán bảng tra ra biến trước khi dịch: trình trích .pot lấy MỌI literal trong lời gọi `_(...)`
# ⇒ `env._(X['KEY'])` đẻ msgid rác "KEY" (bài học J-V3).
def _qty_message(code, name, limit):
    msg = QTY_MESSAGES[code]
    return request.env._(msg).format(name=name, limit=limit)


def _line_invalid_message(code):
    msg = LINE_INVALID_MESSAGES.get(code)
    return request.env._(msg) if msg else ''


def _success_message(code):
    msg = SUCCESS_MESSAGES.get(code)
    return request.env._(msg) if msg else ''


def _float_to_hhmm(value):
    """Convert 10.5 → '10:30'. Tolerates None/invalid → '—'."""
    try:
        v = float(value or 0.0) % 24.0
    except (TypeError, ValueError):
        return '—'
    h = int(v)
    m = int(round((v - h) * 60))
    if m == 60:
        h, m = (h + 1) % 24, 0
    return f'{h:02d}:{m:02d}'


def _window_phrase(from_f, to_f, tz_label):
    """1 khung giờ → chuỗi người đọc kèm múi giờ cửa hàng; khung qua đêm ghi rõ "ngày mai" (WJ-ORD-015)."""
    f, t = _float_to_hhmm(from_f), _float_to_hhmm(to_f)
    try:
        overnight = float(from_f or 0.0) >= float(to_f or 0.0)
    except (TypeError, ValueError):
        overnight = False
    if overnight:
        return request.env._('%(start)s today – %(end)s tomorrow (%(tz)s)', start=f, end=t, tz=tz_label)
    return f'{f} – {t} ({tz_label})'


class WujiaPortalSale(http.Controller):
    """Trang đặt hàng — catalog + giỏ hàng chung theo store + submit tạo SO draft."""

    # ============================================================== helpers
    def _store_gate(self):
        """Resolve current store — trả (fid, error_code).

        get_active_franchise_id() chỉ trả fid nằm trong accessible list
        (build từ membership đang hiệu lực) → fid truthy = membership hợp lệ.
        Phân loại lỗi theo BA row 1 khi không resolve được.
        """
        fid = get_active_franchise_id()
        if fid:
            return fid, None
        raw = request.httprequest.cookies.get(ACTIVE_FRANCHISE_COOKIE)
        try:
            cookie_fid = int(raw) if raw else 0
        except (TypeError, ValueError):
            cookie_fid = 0
        if cookie_fid:
            had_membership = request.env['wujia.franchise.member'].sudo().search_count([
                ('user_id', '=', request.env.uid),
                ('franchise_id', '=', cookie_fid),
            ])
            return False, 'MEMBERSHIP_INACTIVE' if had_membership else 'STORE_ACCESS_DENIED'
        return False, 'STORE_NOT_SELECTED'

    def _err(self, code, **extra):
        res = {'error': code, 'message': _error_message(code, code)}
        res.update(extra)
        return res

    def _get_franchise(self, fid):
        return request.env['wujia.franchise.management'].sudo().browse(fid).exists()

    def _get_store_cart(self, fid, create=False):
        return request.env['wujia.portal.cart'].sudo()._get_for_store(fid, create=create)

    def _qty_err(self, product, error):
        code, limit = error
        if code == 'MIN_QTY_NOT_CONFIGURED':
            return self._err(code)
        return self._err(code, message=_qty_message(code, product.name, limit))

    def _get_store_line(self, line_id, fid):
        """Browse line, verify thuộc giỏ của store hiện tại (guard theo store)."""
        line = request.env['wujia.portal.cart.line'].sudo().browse(line_id).exists()
        if not line or line.cart_id.franchise_id.id != fid:
            return None
        return line

    def _get_pricelist(self, franchise):
        partner = franchise.partner_id if franchise else None
        if partner and partner.property_product_pricelist:
            return partner.property_product_pricelist
        return None

    def _price_products(self, pricelist, products, qty=1):
        """{product_id: đơn giá THÔ} — 1 call batch; fallback giá chuẩn khi chưa có pricelist.

        Giá thô = chưa qua tax engine. Muốn số để HIỂN THỊ thì đi qua
        `_taxed_price_map()` — catalog/chi tiết SP phải cùng con số với giỏ (WJ-ORD-024)."""
        if pricelist and products:
            return pricelist._get_products_price(products, qty)
        return {p.id: p.lst_price for p in products}

    def _taxed_price_map(self, pricelist, products, franchise, qty=1):
        """{product_id: đơn giá ĐÃ GỒM THUẾ} — nguồn giá hiển thị của catalog + chi tiết SP.

        Cùng helper với giỏ và với lịch sử ⇒ 5 màn một con số (cụm D)."""
        raw = self._price_products(pricelist, products, qty)
        currency = self._cart_currency(pricelist)
        company = request.env.company
        partner = franchise.partner_id if franchise else None
        taxes_of = portal_tax_mapper(partner, company)
        return {
            product.id: portal_line_price_vals(
                product, raw.get(product.id, 0.0), 1, currency,
                partner=partner, company=company, taxes=taxes_of(product),
            )['unit_price_tax_included']
            for product in products
        }

    def _cart_currency(self, pricelist):
        """Currency của giỏ = currency sẽ tạo SO.

        Submit truyền `pricelist_id = partner.property_product_pricelist` (cùng partner
        cửa hàng) → SO.currency_id compute ra đúng pricelist này; không pricelist thì
        cả hai phía cùng rơi về company currency. Đã đối chiếu, không có chỗ lệch."""
        return pricelist.currency_id if pricelist else request.env.company.currency_id

    def _price_lines(self, pricelist, lines):
        """{line_id: đơn giá theo qty dòng} — batch theo qty (pricelist có thể theo bậc)."""
        if not pricelist:
            return {line.id: line.product_id.lst_price for line in lines}
        result = {}
        by_qty = defaultdict(list)
        for line in lines:
            by_qty[line.qty or 1].append(line)
        Product = request.env['product.product'].sudo()
        for qty, qty_lines in by_qty.items():
            products = Product.browse([l.product_id.id for l in qty_lines])
            prices = pricelist._get_products_price(products, qty)
            for line in qty_lines:
                result[line.id] = prices.get(line.product_id.id, line.product_id.lst_price)
        return result


    def _cart_state(self, cart, franchise):
        """Full state của giỏ — mọi mutation + cart view dùng chung (BA: FE không tự cộng)."""
        Line = request.env['wujia.portal.cart.line'].sudo()
        lines = cart.line_ids if cart else Line.browse()
        pricelist = self._get_pricelist(franchise)
        unit_prices = self._price_lines(pricelist, lines)
        currency = self._cart_currency(pricelist)
        # Đúng partner sẽ tạo SO → cùng fiscal position → cùng bộ thuế (WJ-ORD-024).
        partner = franchise.partner_id if franchise else None
        company = request.env.company
        taxes_of = portal_tax_mapper(partner, company)
        lines_data = []
        total_qty = 0
        total_amount = 0.0
        total_untaxed = 0.0
        total_tax_included = 0.0
        total_tax_amount = 0.0
        for line in lines:
            product = line.product_id
            unit = unit_prices.get(line.id, 0.0)
            invalid = line._portal_invalid_reason()
            taxed = portal_line_price_vals(
                product, unit, line.qty, currency,
                partner=partner, company=company, taxes=taxes_of(product),
            )
            lines_data.append({
                'line_id': line.id,
                'product_id': product.id,
                'name': product.name,
                'name_chinese': product.name_chinese or '',
                'default_code': product.default_code or '',
                'uom': product.uom_id.name or '—',
                'spec': product.wujia_packaging or '',
                'qty': line.qty,
                'min_qty': product.min_qty,
                'max_qty': product.max_qty,
                # unit_price/subtotal = giá THÔ, giữ nguyên nghĩa cũ vì JS đang dùng
                # (`_cart_state` là nguồn dữ liệu duy nhất của giỏ mobile + panel PC +
                # badge header + route JSON). Số để HIỂN THỊ là 3 key tax-included dưới.
                'unit_price': unit,
                'subtotal': unit * line.qty,
                'unit_price_tax_included': taxed['unit_price_tax_included'],
                'line_total_tax_included': taxed['line_total_tax_included'],
                'tax_amount': taxed['tax_amount'],
                'invalid_reason': invalid,
                'invalid_message': _line_invalid_message(invalid),
            })
            total_qty += line.qty
            total_amount += unit * line.qty
            total_untaxed += taxed['line_total']
            total_tax_included += taxed['line_total_tax_included']
            total_tax_amount += taxed['tax_amount']
        return {
            'cart_id': cart.id if cart else False,
            # WJ-ORD-028: tên cửa hàng cho hộp xác nhận gửi đơn (đọc từ data-* của form gửi).
            'store_name': (franchise.name or '') if franchise else '',
            'note': (cart.note or '') if cart else '',
            'line_count': len(lines_data),
            'total_qty': total_qty,
            'total_amount': total_amount,
            # Tạm tính · Thuế · Tổng thanh toán — 3 key THÊM (không đụng nghĩa key cũ).
            # total_untaxed là base thật sau tax engine, KHÁC total_amount khi thuế
            # price_include: Tạm tính + Thuế = Tổng mới luôn đúng.
            'total_untaxed': currency.round(total_untaxed),
            'total_tax_amount': currency.round(total_tax_amount),
            'total_tax_included': currency.round(total_tax_included),
            'currency': currency.name or 'VND',
            'currency_symbol': currency.symbol or '₫',
            'currency_decimals': currency.decimal_places or 0,
            'lines': lines_data,
            'has_invalid_line': any(l['invalid_reason'] for l in lines_data),
            'updated_at': fields.Datetime.to_string(fields.Datetime.now()),
        }

    def _publish_cart_event(self, fid, state, action):
        """Realtime ADR-006: publish để thiết bị/user khác cùng store nhận biết.

        Channel `wujia.franchise_<id>` đã được authorize theo membership trong
        wujia_portal_base/models/ir_websocket.py. Client subscribe từ WJ-ORD-002
        (portal_cart_sync.js) — `origin` echo lại `client_id` của tab gây ra thay
        đổi để chính tab đó bỏ qua event (nó đã tự refresh sau mutation).
        """
        request.env['bus.bus'].sudo()._sendone(
            f'wujia.franchise_{fid}', 'wujia_cart_changed',
            {
                'franchise_id': fid,
                'action': action,
                'origin': request.params.get('client_id') or None,
                'line_count': state['line_count'],
                'total_qty': state['total_qty'],
                'total_amount': state['total_amount'],
            },
        )

    def _cart_fragments(self, fid, franchise, cart):
        """Realtime reconcile: render lại partial giỏ (PC + mobile) + state gọn.

        Dùng chung QWeb với server-render (1 nguồn, không dựng lại row bằng JS).
        JS swap fragment + cập nhật badge catalog/header theo qty_map."""
        cart_state = self._cart_state(cart, franchise)
        # request cần cho request.csrf_token() trong template submit form.
        values = dict(self._order_window_context(franchise),
                      cart_state=cart_state, request=request,
                      money=portal_money)
        Qweb = request.env['ir.qweb']
        return {
            'pc_html': str(Qweb._render('wujia_portal_sale.pc_cart_panel', values)),
            'mobile_html': str(Qweb._render('wujia_portal_sale.mcart_panel', values)),
            'qty_map': {ln['product_id']: ln['qty'] for ln in cart_state['lines']},
            'line_count': cart_state['line_count'],
            'total_qty': cart_state['total_qty'],
            'total_amount': cart_state['total_amount'],
        }

    @http.route(['/portal/order/cart/fragment'], type='json', auth='user')
    def portal_order_cart_fragment(self, **kw):
        """State + partial giỏ hiện tại cho client reconcile (bus event / sau mutation)."""
        fid, _gate = self._store_gate()
        if not fid:
            return {'error': 'STORE_NOT_SELECTED'}
        franchise = self._get_franchise(fid)
        cart = self._get_store_cart(fid)
        return self._cart_fragments(fid, franchise, cart)

    def _order_window_context(self, franchise):
        """Context khung giờ cho catalog + giỏ (PC + mobile) — cùng kết quả với chặn submit."""
        Settings = request.env['res.config.settings'].sudo()
        allowed, window = Settings._is_within_order_window(franchise=franchise or None)
        raw_windows = window.get('windows') or [{'name': '', 'from': window['from'], 'to': window['to']}]
        tz_label = window.get('tz_label') or ''
        nxt = Settings._next_order_window(franchise=franchise or None) if not allowed else None
        return {
            'order_time_from': _float_to_hhmm(window['from']),
            'order_time_to': _float_to_hhmm(window['to']),
            'order_window_enabled': window['enabled'],
            'order_window_open': allowed,
            'order_window_source': window.get('source', 'global'),
            'order_windows': [
                {'name': w.get('name') or '', 'from': _float_to_hhmm(w['from']), 'to': _float_to_hhmm(w['to'])}
                for w in window.get('windows') or []
            ],
            'order_window_label': ', '.join(_window_phrase(w['from'], w['to'], tz_label) for w in raw_windows),
            'order_window_reopen': _float_to_hhmm(nxt['from'] if nxt else raw_windows[0]['from']),
            'order_window_tz_label': tz_label,
            'order_window_tz_missing': bool(window.get('tz_missing')),
        }

    @staticmethod
    def _is_mobile_flow(post):
        """Form mobile gửi hidden `flow=m` → đi vào màn kết quả riêng (Figma 4963:2).

        PC (pc_cart_panel.xml) KHÔNG gửi field này → giữ nguyên luồng redirect cũ
        đã retest ở Sprint PC-1 (về trang lịch sử / banner tại giỏ)."""
        return (post.get('flow') or '') == 'm'

    def _resolve_messages(self, kw):
        # Chỉ resolve mã đã biết — không reflect chuỗi lạ từ query string ra UI.
        return {
            'error': _error_message(kw.get('error') or ''),
            'message': _success_message(kw.get('message') or ''),
        }

    # ------------------------------------------------------------------ catalog
    def _catalog_values(self, page=1, category_id=None, keyword='', page_size=None,
                        **kw):
        """Context catalog — dùng chung cho trang đầy đủ và fragment AJAX."""
        if not request.env.user._get_accessible_franchise_ids():
            return {
                'money': portal_money,
                'no_franchise': True, 'products': [], 'categories': [],
                'cart': False, 'cart_state': None, 'price_map': {},
                'pgn': None, 'keyword': '', 'category_id': None,
            }
        fid, gate_error = self._store_gate()
        franchise = self._get_franchise(fid) if fid else None

        Product = request.env['product.product'].sudo()
        domain = Product._portal_orderable_domain()
        if keyword:
            # BA row 4: tìm theo tên HOẶC mã sản phẩm.
            domain += ['|', ('name', 'ilike', keyword), ('default_code', 'ilike', keyword)]
        try:
            cat_id = int(category_id) if category_id else None
        except (TypeError, ValueError):
            cat_id = None
        if cat_id:
            domain.append(('public_categ_id', '=', cat_id))

        size = parse_page_size(page_size, PAGE_SIZE, PAGE_SIZE_OPTIONS)
        total = Product.search_count(domain)
        # Một nguồn duy nhất cho số trang + URL trang (CMP-PGNT-001): query-string lấy
        # từ request nên đổi trang giữ nguyên keyword/danh mục.
        pgn = build_pager(total, page, size, path='/portal/order',
                          item_label=_lt('products'), page_size_options=PAGE_SIZE_OPTIONS,
                          size_param='page_size')
        products = Product.search(domain, limit=pgn['page_size'],
                                  offset=pgn['offset'], order='name asc')

        # Chỉ trả danh mục đang có sản phẩm public (BA row 3) — 1 read_group + 1 search.
        cat_groups = Product._read_group(
            Product._portal_orderable_domain(), ['public_categ_id'], [],
        )
        categories = request.env['wujia.product.category'].sudo().search([
            ('id', 'in', [c.id for (c,) in cat_groups]),
        ])

        pricelist = self._get_pricelist(franchise)
        price_map = self._taxed_price_map(pricelist, products, franchise)

        cart = self._get_store_cart(fid) if fid else False
        cart_state = self._cart_state(cart, franchise)

        msgs = self._resolve_messages(kw)
        return {
            'money': portal_money,
            'no_franchise': False,
            'active_franchise_id': fid,
            'products': products,
            'price_map': price_map,
            'categories': categories,
            'cart': cart,
            'cart_state': cart_state,
            'pgn': pgn,
            'product_count': total,
            'keyword': keyword,
            'category_id': cat_id,
            'message': msgs['message'],
            'error': msgs['error'] or (_error_message(gate_error) if gate_error else ''),
            **self._order_window_context(franchise),
        }

    @http.route(['/portal/order'], type='http', auth='user', sitemap=False)
    def portal_order_catalog(self, **kw):
        return request.render('wujia_portal_sale.portal_order_catalog',
                              self._catalog_values(**kw))

    @http.route(['/portal/order/results'], type='http', auth='user', sitemap=False)
    def portal_order_catalog_results(self, **kw):
        """Fragment các khối kết quả cho lọc AJAX — cùng context, bỏ shell portal."""
        return request.render('wujia_portal_sale.portal_order_catalog_results',
                              self._catalog_values(**kw))

    # ----------------------------------------------------------- product detail
    @http.route(['/portal/order/product/<int:product_id>'],
                type='http', auth='user', sitemap=False)
    def portal_order_product_detail(self, product_id, **kw):
        Product = request.env['product.product'].sudo()
        product = Product.browse(int(product_id)).exists()
        if not product or not product._portal_is_orderable():
            # WJ-ORD-017: không im lặng — redirect an toàn về catalog kèm thông
            # báo (không lộ lý do tồn tại/quyền; mã đã whitelist trong catalog).
            return request.redirect('/portal/order?error=PRODUCT_NOT_AVAILABLE')
        related = Product.search(Product._portal_orderable_domain() + [
            ('public_categ_id', '=', product.public_categ_id.id),
            ('id', '!=', product.id),
        ], limit=6, order='name asc')
        fid, _gate_error = self._store_gate()
        franchise = self._get_franchise(fid) if fid else None
        pricelist = self._get_pricelist(franchise)
        price_map = self._taxed_price_map(pricelist, product | related, franchise)
        return request.render('wujia_portal_sale.portal_order_product_detail', {
            'money': portal_money,
            'active_franchise_id': fid,
            'product': product,
            'related': related,
            'price_map': price_map,
            'currency_symbol': self._cart_currency(pricelist).symbol or '',
            'currency_decimals': self._cart_currency(pricelist).decimal_places or 0,
        })

    # ----------------------------------------------------------------- cart view
    @http.route(['/portal/order/cart'], type='http', auth='user', sitemap=False)
    def portal_order_cart_view(self, **kw):
        if not request.env.user._get_accessible_franchise_ids():
            return request.redirect('/portal/order')
        fid, gate_error = self._store_gate()
        franchise = self._get_franchise(fid) if fid else None
        cart = self._get_store_cart(fid) if fid else False
        cart_state = self._cart_state(cart, franchise)
        msgs = self._resolve_messages(kw)
        return request.render('wujia_portal_sale.portal_order_cart', {
            'money': portal_money,
            'active_franchise_id': fid,
            'cart': cart,
            'cart_state': cart_state,
            'message': msgs['message'],
            'error': msgs['error'] or (_error_message(gate_error) if gate_error else ''),
            **self._order_window_context(franchise),
        })

    # ----------------------------------------------------------------- cart add
    @http.route(['/portal/order/cart/add'], type='json', auth='user',
                methods=['POST'])
    @rate_limit(max_calls=60, window_sec=60)
    def portal_cart_add(self, product_id, qty=None, **kw):
        fid, gate_error = self._store_gate()
        if gate_error:
            return self._err(gate_error)
        try:
            product_id = int(product_id)
        except (TypeError, ValueError):
            return self._err('invalid_input')
        product = request.env['product.product'].sudo().browse(product_id).exists()
        if not product or not product._portal_is_orderable():
            return self._err('PRODUCT_NOT_AVAILABLE')
        if product.min_qty <= 0:
            return self._err('MIN_QTY_NOT_CONFIGURED')
        # FE gửi qty tường minh (trang chi tiết) → phải HỢP LỆ TUYỆT ĐỐI, không ép về bước (WJ-ORD-001).
        if qty is None or qty == '':
            increment = product.min_qty
        else:
            try:
                fval = float(qty)
            except (TypeError, ValueError):
                return self._err('invalid_input')
            if fval != int(fval):
                return self._err('QTY_INVALID_STEP',
                                 message=request.env._("The quantity of %s must be a whole number.", product.name))
            increment = int(fval)
            error = product._portal_qty_error(increment)
            if error:
                return self._qty_err(product, error)

        franchise = self._get_franchise(fid)
        cart = self._get_store_cart(fid, create=True)
        if not cart:
            return self._err('CART_LOAD_FAILED')
        line_id, new_qty = request.env['wujia.portal.cart.line'].sudo()._portal_add(
            cart, product, increment)

        state = self._cart_state(cart, franchise)
        self._publish_cart_event(fid, state, 'add')
        res = {
            'success': True,
            'line_id': line_id,
            'qty': new_qty,
            'cart_count': state['line_count'],
            'cart': state,
        }
        if product.max_qty and new_qty >= product.max_qty:
            res['warning'] = 'QTY_ABOVE_MAX'
            res['message'] = _qty_message('QTY_ABOVE_MAX', product.name, product.max_qty)
        return res

    # -------------------------------------------------------------- cart update
    @http.route(['/portal/order/cart/update'], type='json', auth='user',
                methods=['POST'])
    def portal_cart_update_qty(self, line_id, qty, **kw):
        fid, gate_error = self._store_gate()
        if gate_error:
            return self._err(gate_error)
        try:
            line_id = int(line_id)
            qty = max(0, int(qty))
        except (TypeError, ValueError):
            return self._err('invalid_input')
        franchise = self._get_franchise(fid)
        line = self._get_store_line(line_id, fid)
        cart = line.cart_id if line else self._get_store_cart(fid)
        if not line:
            # Idempotent: dòng đã bị user khác xoá → trả state mới, không lỗi.
            state = self._cart_state(cart, franchise)
            return {'success': True, 'removed': True,
                    'cart_count': state['line_count'], 'cart': state}
        product = line.product_id
        if qty == 0:
            line.unlink()
            state = self._cart_state(cart, franchise)
            self._publish_cart_event(fid, state, 'remove')
            return {'success': True, 'removed': True,
                    'cart_count': state['line_count'], 'cart': state}
        error = product._portal_qty_error(qty)
        if error:
            return self._qty_err(product, error)
        line.write({'qty': qty})
        state = self._cart_state(cart, franchise)
        self._publish_cart_event(fid, state, 'update')
        line_state = next((l for l in state['lines'] if l['line_id'] == line.id), None)
        return {'success': True, 'qty': qty,
                'cart_count': state['line_count'],
                'line': line_state, 'cart': state}

    # ---------------------------------------------------------------- cart step
    @http.route(['/portal/order/cart/step'], type='json', auth='user',
                methods=['POST'])
    def portal_cart_step(self, line_id=None, product_id=None, direction=None, **kw):
        """Tăng/giảm ĐÚNG 1 bước NGUYÊN TỬ (WJ-ORD-002 — tránh lost update).

        Client chỉ gửi hướng ('inc'/'dec'); server tự lấy step=min_qty rồi cộng
        delta THẲNG trong SQL (UPDATE khoá dòng → 2 request gần đồng thời áp tuần
        tự, KHÔNG ghi đè tuyệt đối như set qty). qty rơi < min → xoá dòng.
        Không nhận qty/delta tuỳ ý từ client để cấm nhảy bậc.

        WJ-ORD-021: giỏ hàng gửi line_id; DANH SÁCH mobile gửi product_id (row
        không giữ line_id ở DOM, resolve line trong giỏ của store hiện tại)."""
        fid, gate_error = self._store_gate()
        if gate_error:
            return self._err(gate_error)
        if direction == 'inc':
            sign = 1
        elif direction == 'dec':
            sign = -1
        else:
            return self._err('invalid_input')
        franchise = self._get_franchise(fid)
        line = None
        if line_id not in (None, '', 0, '0'):
            try:
                line = self._get_store_line(int(line_id), fid)
            except (TypeError, ValueError):
                return self._err('invalid_input')
        elif product_id not in (None, '', 0, '0'):
            try:
                pid = int(product_id)
            except (TypeError, ValueError):
                return self._err('invalid_input')
            store_cart = self._get_store_cart(fid)
            line = (store_cart.line_ids.filtered(lambda l: l.product_id.id == pid)[:1]
                    if store_cart else None) or None
        else:
            return self._err('invalid_input')
        cart = line.cart_id if line else self._get_store_cart(fid)
        if not line:
            # Idempotent: dòng đã bị user khác xoá → trả state mới, không lỗi.
            state = self._cart_state(cart, franchise)
            return {'success': True, 'removed': True,
                    'cart_count': state['line_count'], 'cart': state}
        product = line.product_id
        if product.min_qty <= 0:
            return self._err('MIN_QTY_NOT_CONFIGURED')
        line_id = line.id
        new_qty, removed = line._portal_step(sign)
        warning = None
        if not removed and sign > 0 and product.max_qty and new_qty >= product.max_qty:
            warning = 'QTY_ABOVE_MAX'
        state = self._cart_state(cart, franchise)
        self._publish_cart_event(fid, state, 'remove' if removed else 'update')
        res = {'success': True, 'removed': removed, 'qty': new_qty,
               'cart_count': state['line_count'], 'cart': state}
        if not removed:
            res['line'] = next((l for l in state['lines'] if l['line_id'] == line_id), None)
        if warning:
            res['warning'] = warning
            res['message'] = _qty_message('QTY_ABOVE_MAX', product.name, product.max_qty)
        return res

    # -------------------------------------------------------------- cart remove
    @http.route(['/portal/order/cart/remove'], type='json', auth='user',
                methods=['POST'])
    def portal_cart_remove(self, line_id, **kw):
        fid, gate_error = self._store_gate()
        if gate_error:
            return self._err(gate_error)
        try:
            line_id = int(line_id)
        except (TypeError, ValueError):
            return self._err('invalid_input')
        franchise = self._get_franchise(fid)
        line = self._get_store_line(line_id, fid)
        cart = line.cart_id if line else self._get_store_cart(fid)
        if line:
            line.unlink()
        state = self._cart_state(cart, franchise)
        self._publish_cart_event(fid, state, 'remove')
        return {'success': True, 'removed': True,
                'cart_count': state['line_count'], 'cart': state}

    # --------------------------------------------------------------- cart count
    @http.route(['/portal/order/cart/count'], type='json', auth='user',
                methods=['GET', 'POST'])
    def portal_cart_count(self, **kw):
        fid, gate_error = self._store_gate()
        if gate_error:
            return {'count': 0, 'line_count': 0, 'total_qty': 0}
        Line = request.env['wujia.portal.cart.line'].sudo()
        groups = Line._read_group(
            [('cart_id.franchise_id', '=', fid)], [], ['__count', 'qty:sum'],
        )
        line_count, total_qty = groups[0] if groups else (0, 0)
        # `count` giữ nguyên cho badge JS cũ = số dòng (SKU) — BA row 10 phân biệt 2 số.
        return {'count': line_count, 'line_count': line_count,
                'total_qty': int(total_qty or 0)}

    # ---------------------------------------------------------------- cart note
    @http.route(['/portal/order/cart/note'], type='json', auth='user',
                methods=['POST'])
    @rate_limit(max_calls=30, window_sec=60)
    def portal_cart_note(self, note='', **kw):
        fid, gate_error = self._store_gate()
        if gate_error:
            return self._err(gate_error)
        cart = self._get_store_cart(fid, create=True)
        if not cart:
            return self._err('CART_LOAD_FAILED')
        # Lưu plain text (render qua t-esc); escape sang Html khi map vào SO note.
        cart.write({'note': (note or '').strip()[:1000]})
        franchise = self._get_franchise(fid)
        state = self._cart_state(cart, franchise)
        self._publish_cart_event(fid, state, 'note')
        return {'success': True, 'note': cart.note or '',
                'updated_at': state['updated_at']}

    # ------------------------------------------------------------ submit order
    @http.route(['/portal/order/submit'], type='http', auth='user',
                methods=['POST'], sitemap=False, csrf=True)
    def portal_order_submit(self, **post):
        fid, gate_error = self._store_gate()
        if gate_error:
            return request.redirect(f'/portal/order/cart?error={gate_error}')
        franchise = self._get_franchise(fid)
        if not franchise:
            return request.redirect('/portal/order/cart?error=STORE_ACCESS_DENIED')
        # Chưa có giỏ ⇒ giỏ ảo (không ghi DB) để model vẫn kiểm khoá cửa hàng trước giỏ rỗng.
        cart = self._get_store_cart(fid) or request.env['wujia.portal.cart'].sudo().new({'franchise_id': fid})
        try:
            order = cart.action_submit_order(note=post.get('portal_note'))
        except PortalOrderError as e:
            if e.code == 'ORDER_TIME_CLOSED':
                return self._submit_time_closed(post)
            if e.code == 'CART_EMPTY':
                # WJ-ORD-028: lần gửi lặp gặp giỏ đã trống ⇒ về đúng đơn vừa tạo, không báo "giỏ trống".
                recent = request.env['wujia.portal.cart'].sudo()._portal_just_submitted_order(
                    fid, request.env.uid)
                if recent:
                    return self._submit_done_redirect(recent, post)
            return request.redirect(f'/portal/order/cart?error={e.code}')
        state = self._cart_state(cart, franchise)
        self._publish_cart_event(fid, state, 'submit')
        return self._submit_done_redirect(order, post)

    def _submit_done_redirect(self, order, post):
        # Mobile → màn "Đặt hàng thành công" (Figma 4963:2 màn 03); PC giữ nguyên
        # redirect sang trang chi tiết đơn như Sprint PC-1.
        if self._is_mobile_flow(post):
            return request.redirect(f'/portal/order/submitted/{order.id}')
        return request.redirect(
            f'/portal/purchase-history/{order.id}?message=order_submitted'
        )

    def _submit_time_closed(self, post):
        """Submit bị chặn vì ngoài khung giờ — mobile có màn riêng, PC giữ banner tại giỏ."""
        if self._is_mobile_flow(post):
            return request.redirect('/portal/order/rejected?reason=ORDER_TIME_CLOSED')
        return request.redirect('/portal/order/cart?error=ORDER_TIME_CLOSED')

    # ------------------------------------------------- kết quả gửi đơn (mobile)
    @http.route(['/portal/order/submitted/<int:order_id>'], type='http', auth='user',
                sitemap=False)
    def portal_order_submitted(self, order_id, **kw):
        """Màn "Đặt hàng thành công" — dữ liệu THẬT từ SO vừa tạo (không phải số Figma).

        Guard scope: chỉ đơn portal của store đang chọn; sai/không có quyền → về catalog
        (không tiết lộ đơn tồn tại hay không)."""
        fid, gate_error = self._store_gate()
        if gate_error:
            return request.redirect(f'/portal/order?error={gate_error}')
        order = request.env['sale.order'].sudo().browse(order_id).exists()
        if not order or not order.is_portal_order or order.franchise_id.id != fid:
            return request.redirect('/portal/order')
        # Đơn đã huỷ không phải "kết quả gửi đơn" — xem ở Lịch sử đặt hàng. Chặn ngay ở guard.
        if order.state == 'cancel':
            return request.redirect('/portal/order')

        label, status_type = _state_meta(order.state)
        # date_order lưu UTC — quy về tz user để "09:32" đúng giờ cửa hàng.
        local_dt = fields.Datetime.context_timestamp(order, order.date_order) if order.date_order else None
        franchise = self._get_franchise(fid)
        return request.render('wujia_portal_sale.portal_order_submitted', {
            'money': portal_money,
            'active_franchise_id': fid,
            'order': order,
            'order_name': order.name,
            'order_date_label': local_dt.strftime('%d/%m/%Y • %H:%M') if local_dt else '—',
            # Ký hiệu theo currency của ĐƠN, không hardcode (WJ-ORD-025). Breakdown
            # Tạm tính/Thuế/Tổng để user đối chiếu đúng cái vừa thấy ở giỏ (WJ-ORD-024).
            'order_amount_label': portal_money(order.amount_total, order.currency_id.symbol,
                                               order.currency_id.decimal_places),
            'order_untaxed_label': portal_money(order.amount_untaxed, order.currency_id.symbol,
                                                order.currency_id.decimal_places),
            'order_tax_label': portal_money(order.amount_tax, order.currency_id.symbol,
                                            order.currency_id.decimal_places),
            'order_has_tax': bool(order.currency_id.compare_amounts(order.amount_tax, 0.0)),
            'order_state_label': label,
            'order_status_type': status_type,
            'order_status_badge': portal_order_state_badge(order.state),  # CMP-SB-001 — màu từ `_lt`, không từ nhãn đã dịch
            **self._order_window_context(franchise),
        })

    @http.route(['/portal/order/rejected'], type='http', auth='user', sitemap=False)
    def portal_order_rejected(self, reason=None, **kw):
        """Màn "Không thể gửi đơn" — hiện chỉ dùng cho ORDER_TIME_CLOSED.

        Mã lỗi khác vẫn về giỏ + banner (user sửa được ngay tại giỏ) — whitelist ở
        đây để không reflect chuỗi lạ từ query string, đúng như `_resolve_messages`."""
        if reason != 'ORDER_TIME_CLOSED':
            code = reason if reason in ERROR_MESSAGES else 'internal_error'
            return request.redirect(f'/portal/order/cart?error={code}')
        fid, gate_error = self._store_gate()
        if gate_error:
            return request.redirect(f'/portal/order?error={gate_error}')
        franchise = self._get_franchise(fid)
        nxt = request.env['res.config.settings'].sudo()._next_order_window(franchise=franchise or None)
        return request.render('wujia_portal_sale.portal_order_rejected', {
            'active_franchise_id': fid,
            'next_window_label': (
                f"{_float_to_hhmm(nxt['from'])} – {_float_to_hhmm(nxt['to'])}" if nxt else '—'
            ),
            'next_window_date_label': (
                (request.env._('Today, %s', nxt['date'].strftime('%d/%m/%Y')) if nxt['is_today']
                 else request.env._('On %s', nxt['date'].strftime('%d/%m/%Y')))
                if nxt else ''
            ),
            'next_window_name': (nxt or {}).get('name') or '',
            **self._order_window_context(franchise),
        })
