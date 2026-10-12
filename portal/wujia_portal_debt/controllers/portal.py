"""Route portal Công nợ & thanh toán (Figma WJ_Debt_*_MVP_v31, node 5013:*).

Shape controller dựng sẵn theo `3. Controller` CT-050…CT-055 của BA; nguồn số liệu
đi qua `wujia.portal.debt` (xem docstring model — UI-only, chốt 2026-07-31).

Guard: chưa chọn cửa hàng → render empty state, KHÔNG 500. Cùng pattern
`wujia_portal_notification/controllers/portal.py`.
"""

from datetime import datetime

from odoo import _, http
from odoo.http import request
from odoo.tools.translate import LazyTranslate

from odoo.addons.wujia_portal_base.controllers.portal import (
    get_active_franchise_id,
    is_current_store_admin,
    render_no_permission,
)
from odoo.addons.wujia_portal_base.controllers.utils import (
    build_pager, parse_page_size, portal_money,
)

from ..models.wujia_portal_debt import (
    INVOICE_BADGE, INVOICE_PREVIEW, STATE_BADGE, translated_badges,
)

_lt = LazyTranslate(__name__)


def _debt_access(franchise_id):
    """(allowed, denied_response). Chưa chọn cửa hàng → route render empty-state như cũ."""
    if franchise_id and not is_current_store_admin():
        return False, render_no_permission(
            _('Debts'),
            _("You do not have permission to view this store's debts and payments."))
    return True, None


def _money_fn(symbol, decimals=0):
    """Trả hàm format 1 tham số cho template (`vnd(amount)` — giữ nguyên cách gọi cũ).

    Ký hiệu bind theo currency của dữ liệu công nợ thay vì hardcode 'đ' (cụm D).
    Format số giữ y hệt: '12.650.000 đ'."""
    return lambda amount: portal_money(amount, symbol, decimals)


def _parse_date(value):
    """'YYYY-MM-DD' (input type=date) → date, hoặc None nếu rỗng/sai định dạng."""
    if not value:
        return None
    try:
        return datetime.strptime(value, '%Y-%m-%d').date()
    except (TypeError, ValueError):
        return None


# Số dòng/trang bảng PC (Figma "10 / trang"). Chỉ dùng cho khối desktop —
# mobile giữ nguyên cơ chế preview 2 + ?all=1.
_PC_PAGE_SIZE = 10
_PC_PAGE_SIZES = (10, 20, 50)


def _pc_paginate(items, page, page_size=None, *, path, item_label):
    """Slice phân trang cho bảng PC (STT10). Trả (slice, pgn) với `pgn` là dict chuẩn
    của `build_pager` — cùng một nguồn với mọi pager portal khác (CMP-PGNT-001).

    Công nợ tính trên list đã dựng sẵn trong RAM (không phải search ORM) nên chỉ mượn
    phần phép toán + dựng URL của `build_pager` rồi tự cắt lát.
    """
    size = parse_page_size(page_size, _PC_PAGE_SIZE, _PC_PAGE_SIZES)
    pgn = build_pager(len(items), page, size, path=path, item_label=item_label,
                      page_size_options=_PC_PAGE_SIZES, size_param='page_size')
    return items[pgn['offset']:pgn['offset'] + pgn['page_size']], pgn


def _store_label(franchise_id):
    """Nhãn cửa hàng hiện tại cho pill 'Cửa hàng' (readonly) — '[H000] Tên cửa hàng'.
    display_name đã store sẵn dạng '[code] name' (wujia_franchise)."""
    if not franchise_id:
        return ''
    franchise = request.env['wujia.franchise.management'].sudo().browse(franchise_id).exists()
    return franchise.display_name or ''


class WujiaPortalDebt(http.Controller):

    @http.route(['/portal/debt'], type='http', auth='user', sitemap=False)
    def portal_debt(self, week=None, all=None, page=None, page_size=None,
                    notice=None, **kw):
        """Overview — Mobile: 4 biến thể theo `state`. PC (STT10): 5 biến thể
        (empty tách 'empty_week'/'no_debt' theo rule 10c/10d) + bảng phân trang + modal QR."""
        franchise_id = get_active_franchise_id()
        allowed, denied = _debt_access(franchise_id)
        if not allowed:
            return denied
        debt = request.env['wujia.portal.debt']
        summary = debt.get_summary(franchise_id, week=week)
        # Mobile (giữ nguyên): mặc định 2 hoá đơn + note "Hiển thị 2/4 hóa đơn"; `?all=1` bung hết.
        show_all = str(all or '') in ('1', 'true', 'True')
        invoices = summary['invoices'] if show_all else summary['invoices'][:INVOICE_PREVIEW]
        # PC: state 5 nhánh + bảng phân trang riêng (10/trang) trên toàn bộ hoá đơn tuần.
        pc_state = summary['state']
        if pc_state == 'empty':
            pc_state = debt._empty_substate(franchise_id)
        pc_invoices, pgn = _pc_paginate(summary['invoices'], page, page_size,
                                        path='/portal/debt', item_label=_lt('invoices'))
        # Modal QR: chỉ dựng dữ liệu chuyển khoản khi còn số phải trả (CTA hiện).
        bank = (debt.get_bank_info(franchise_id, summary['remaining'], summary['week_number'])
                if summary['remaining'] > 0 else None)
        return request.render('wujia_portal_debt.portal_debt_overview', {
            'summary': summary,
            'invoices': invoices,
            'show_all': show_all,
            'hidden_count': max(0, summary['invoice_count'] - len(invoices)),
            'no_store': not franchise_id,
            'STATE_BADGE': translated_badges(request.env, STATE_BADGE),
            'INVOICE_BADGE': translated_badges(request.env, INVOICE_BADGE),
            'vnd': _money_fn(summary['currency_symbol'], summary['currency_decimals']),
            # PC extras — khối desktop mới, mobile block không tham chiếu:
            'pc_state': pc_state,
            'pc_invoices': pc_invoices,
            'pgn': pgn,
            'store_label': _store_label(franchise_id),
            'bank': bank,
            'active_tab': 'debt',
            'notice': notice if notice == 'no_due' else '',
        })

    @http.route(['/portal/debt/payment-history'], type='http', auth='user', sitemap=False)
    def portal_debt_payment_history(self, month=None, date_from=None, date_to=None,
                                    q=None, page=None, page_size=None, **kw):
        """Màn 06 — các khoản Ngô Gia đã xác nhận trong kỳ. Ô tìm kiếm (`q`) chỉ PC;
        phân trang dùng chung PC + mobile. `history['totals']` = tổng TOÀN kỳ đã lọc,
        tách theo từng loại tiền (WJ-DEBT-004)."""
        franchise_id = get_active_franchise_id()
        allowed, denied = _debt_access(franchise_id)
        if not allowed:
            return denied
        history = request.env['wujia.portal.debt'].get_payments(
            franchise_id, month=month,
            date_from=_parse_date(date_from), date_to=_parse_date(date_to),
            keyword=q)
        payments, pgn = _pc_paginate(history['payments'], page, page_size,
                                     path='/portal/debt/payment-history',
                                     item_label=_lt('transactions'))
        return request.render('wujia_portal_debt.portal_debt_payment_history', {
            'history': history,
            'no_store': not franchise_id,
            'vnd': _money_fn(history['currency_symbol'], history['currency_decimals']),
            'payments': payments,
            'pgn': pgn,
            'q': q or '',
            'store_label': _store_label(franchise_id),
            'active_tab': 'history',
        })

    @http.route(['/portal/debt/pay'], type='http', auth='user', sitemap=False)
    def portal_debt_pay(self, week=None, **kw):
        """Màn 07 — QR + thông tin chuyển khoản (STK thật; ảnh QR defer, chờ BA chốt)."""
        franchise_id = get_active_franchise_id()
        allowed, denied = _debt_access(franchise_id)
        if not allowed:
            return denied
        debt = request.env['wujia.portal.debt']
        summary = debt.get_summary(franchise_id, week=week)
        # Hết nợ (hoặc dư có) thì không có gì để chuyển khoản — về trang công nợ kèm
        # thông báo thay vì in số âm/QR (WJ-DEBT-007).
        if summary['remaining'] <= 0:
            return request.redirect(
                '/portal/debt?week=%s&notice=no_due' % summary['week_key'])
        bank = debt.get_bank_info(
            franchise_id, summary['remaining'], summary['week_number'])
        return request.render('wujia_portal_debt.portal_debt_pay', {
            'summary': summary,
            'bank': bank,
            'no_store': not franchise_id,
            'vnd': _money_fn(summary['currency_symbol'], summary['currency_decimals']),
        })
