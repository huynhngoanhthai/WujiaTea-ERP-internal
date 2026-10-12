"""Báo cáo đặt hàng cho cửa hàng nhượng quyền — BA Phase 1.

Performance design (1500 user):
- 1 _read_group / metric (KHÔNG search loop). 5 query cho cả page.
- Filter date_from/date_to mặc định = năm hiện tại để giới hạn dataset.
- Pre-format số liệu (qty, total, ratio %) ở controller — template chỉ render text.
- Chart data dump ra JSON 1 lần qua data attribute, ApexCharts đọc từ DOM.
- Role check sớm (redirect trước query) — Staff không vào được.
"""
import io
import json
from datetime import date, datetime, timedelta

import xlsxwriter

from odoo import _, _lt, fields, http
from odoo.http import request

from odoo.addons.wujia_portal_base.controllers.portal import (
    get_current_store_ids,
    get_store_scope_state,
    is_current_store_admin,
    render_no_permission,
)
from odoo.addons.wujia_portal_base.controllers.utils import (
    date_range_error, portal_money,
)


# Màu lấy theo design system portal (2 mockup STT12 vẽ đúng bộ này), thay bộ
# bootstrap cũ #6c757d/#28a745/#dc3545 — Acceptance #5 đòi màu trạng thái đồng
# nhất với component portal. Nhãn và khoá state giữ nguyên.
STATE_LABELS = {
    'draft': (_lt('Draft'), '#8A939E'),
    'sent': (_lt('Submitted'), '#20A0BC'),
    'sale': (_lt('Confirmed'), '#16A34A'),
    'done': (_lt('Done'), '#244B87'),
    'cancel': (_lt('Cancelled'), '#EF4444'),
}

EXPORT_HEADERS = [
    _lt('Order code'), _lt('Order date'), _lt('Store'), _lt('Customer'),
    _lt('Status'), _lt('Lines'), _lt('Total amount'),
]


def _state_label(env, state):
    if state not in STATE_LABELS:
        return state or ''
    label = STATE_LABELS[state][0]
    return env._(label)


def _decimal_point(env):
    return env['res.lang']._get_data(code=env.lang).decimal_point or '.'


def _parse_date(value, fallback=None):
    if not value:
        return fallback
    try:
        return datetime.strptime(value, '%Y-%m-%d').date()
    except (TypeError, ValueError):
        return fallback


class WujiaPortalReport(http.Controller):

    def _empty_report_values(self, date_from, date_to, filter_error):
        """Ctx báo cáo rỗng — dùng khi bộ lọc không hợp lệ nên không chạy query."""
        currency = request.env.company.currency_id
        money = lambda amount: portal_money(                    # noqa: E731
            amount, currency.symbol or '', currency.decimal_places)
        return {
            'title': _('Order report'),
            'date_from': date_from, 'date_to': date_to,
            'filter_error': filter_error,
            'money': money, 'currency_symbol': currency.symbol or '',
            'total_orders': 0, 'total_revenue': 0.0,
            'cancel_orders': 0, 'done_orders': 0,
            'top_products': [], 'state_summary': [],
            # Cùng BỘ KHOÁ với nhánh thường, chỉ rỗng — thiếu khoá là JS biểu đồ
            # đọc `undefined` rồi vẽ hỏng im lặng.
            'chart_payload_json': json.dumps({
                'months_label': [], 'months_count': [], 'months_total': [],
                'state_label': [], 'state_count': [], 'state_color': [],
                'currency': request.env.company.currency_id.symbol or '',
                'decimal_point': _decimal_point(request.env),
            }),
        }

    @http.route(['/portal/reports/orders'], type='http', auth='user', sitemap=False)
    def portal_report_orders(self, date_from='', date_to='', **kw):
        franchise_ids = get_current_store_ids()
        store_scope = get_store_scope_state()
        if store_scope == 'no_store':
            return request.redirect('/portal')

        if franchise_ids and not is_current_store_admin():
            return render_no_permission(
                _('Order report'), _("You do not have permission to view this store's reports."))
        if not franchise_ids:
            return request.render('wujia_portal_report.portal_report_orders',
                                  dict(self._empty_report_values(date_from, date_to, ''),
                                       store_scope=store_scope))

        # ---- Date range (default = năm hiện tại) ----
        today = date.today()
        df = _parse_date(date_from, fallback=date(today.year, 1, 1))
        dt = _parse_date(date_to, fallback=today)
        # Ngày ngược: trước đây tự kẹp `dt = df` trong im lặng nên người dùng gõ
        # một khoảng mà màn ra số liệu của ĐÚNG MỘT ngày, không lời giải thích.
        # Nay báo tại thanh lọc, giữ nguyên chữ đã gõ, KPI + biểu đồ về rỗng.
        filter_error = date_range_error(df, dt)
        if filter_error:
            return request.render('wujia_portal_report.portal_report_orders',
                                  self._empty_report_values(
                                      date_from, date_to, filter_error))
        df_dt = datetime.combine(df, datetime.min.time())
        dt_dt = datetime.combine(dt, datetime.max.time())

        SO = request.env['sale.order'].sudo()
        base_domain = [
            ('franchise_id', 'in', list(franchise_ids)),
            ('date_order', '>=', df_dt),
            ('date_order', '<=', dt_dt),
        ]

        # ---- Block 1: 4 KPI cards ----
        # Tổng số đơn (loại cancel) + tổng doanh thu + đơn cancel + đơn done.
        # 1 _read_group group by state — 1 query trả tất cả.
        state_groups = SO._read_group(
            domain=base_domain, groupby=['state'],
            aggregates=['__count', 'amount_total:sum'],
        )
        state_data = {st: {'count': cnt, 'total': tot or 0.0}
                      for st, cnt, tot in state_groups}
        total_orders = sum(d['count'] for st, d in state_data.items() if st != 'cancel')
        total_revenue = sum(d['total'] for st, d in state_data.items() if st != 'cancel')
        cancel_orders = state_data.get('cancel', {}).get('count', 0)
        done_orders = state_data.get('done', {}).get('count', 0)

        # ---- Block 2: Đơn theo 12 tháng gần nhất (bar chart) ----
        # Force window = max(12 tháng gần nhất, date_from). Tránh chart trống.
        chart_from = max(df_dt, datetime.combine(today.replace(day=1), datetime.min.time()) - timedelta(days=365))
        month_groups = SO._read_group(
            domain=[
                ('franchise_id', 'in', list(franchise_ids)),
                ('date_order', '>=', chart_from),
                ('date_order', '<=', dt_dt),
                ('state', '!=', 'cancel'),
            ],
            groupby=['date_order:month'],
            aggregates=['__count', 'amount_total:sum'],
            order='date_order:month asc',
        )
        chart_months = []
        for month_dt, cnt, total in month_groups:
            label = month_dt.strftime('%m/%Y') if month_dt else ''
            chart_months.append({
                'label': label,
                'count': cnt,
                'total': float(total or 0),
            })

        # ---- Block 3: Top 10 sản phẩm ----
        SOL = request.env['sale.order.line'].sudo()
        top_groups = SOL._read_group(
            domain=[
                ('order_id.franchise_id', 'in', list(franchise_ids)),
                ('order_id.date_order', '>=', df_dt),
                ('order_id.date_order', '<=', dt_dt),
                ('order_id.state', 'in', ['sale', 'done']),
            ],
            groupby=['product_id'],
            aggregates=['product_uom_qty:sum', 'price_total:sum'],
            limit=10,
            order='product_uom_qty:sum desc',
        )
        top_products = [{
            'name': product.display_name,
            'qty': qty or 0,
            'uom': product.uom_id.name or '',
            'total': total or 0,
        } for product, qty, total in top_groups]

        # ---- Block 4: Phân bố trạng thái (donut data + table) ----
        state_summary = []
        for st, (_label, color) in STATE_LABELS.items():
            d = state_data.get(st, {'count': 0, 'total': 0})
            state_summary.append({
                'state': st, 'label': _state_label(request.env, st), 'color': color,
                'count': d['count'], 'total': d['total'],
            })
        total_count_all = sum(s['count'] for s in state_summary)
        for s in state_summary:
            s['ratio'] = (s['count'] / total_count_all * 100) if total_count_all else 0

        # ---- Chart JSON cho ApexCharts (qua data-* attribute) ----
        chart_payload = {
            'months_label': [m['label'] for m in chart_months],
            'months_count': [m['count'] for m in chart_months],
            'months_total': [m['total'] for m in chart_months],
            'state_label': [s['label'] for s in state_summary if s['count']],
            'state_count': [s['count'] for s in state_summary if s['count']],
            'state_color': [s['color'] for s in state_summary if s['count']],
            # Nhãn trục tiền của chart cũng phải theo currency công ty, không phải 'đ' cứng.
            'currency': request.env.company.currency_id.symbol or '',
            'decimal_point': _decimal_point(request.env),
        }

        # Ký hiệu + số lẻ theo currency công ty, KHÔNG nối ' ₫' cứng trong template
        # (đúng luật WJ-ORD-025: công ty USD từng hiện số USD kèm ký hiệu ₫).
        currency = request.env.company.currency_id
        money = lambda amount: portal_money(                    # noqa: E731
            amount, currency.symbol or '', currency.decimal_places)

        return request.render('wujia_portal_report.portal_report_orders', {
            'title': _('Order report'),
            'date_from': df.strftime('%Y-%m-%d'),
            'date_to': dt.strftime('%Y-%m-%d'),
            'filter_error': '',
            'money': money,
            'currency_symbol': currency.symbol or '',
            # KPIs
            'total_orders': total_orders,
            'total_revenue': total_revenue,
            'cancel_orders': cancel_orders,
            'done_orders': done_orders,
            # blocks
            'top_products': top_products,
            'state_summary': state_summary,
            'chart_payload_json': json.dumps(chart_payload),
            # role meta
            'store_scope': store_scope,
        })

    @http.route(['/portal/reports/orders/export.xlsx'], type='http',
                auth='user', sitemap=False)
    def portal_report_export_xlsx(self, date_from='', date_to='', **kw):
        """Export báo cáo đặt hàng ra XLSX — 1 sheet KPI + 1 sheet detail."""
        franchise_ids = get_current_store_ids()
        if not franchise_ids:
            # Chưa chọn cửa hàng ⇒ không xuất file gộp; trang báo cáo hiện khối nhắc chọn.
            return request.redirect('/portal/reports/orders')
        if not is_current_store_admin():
            return request.redirect('/portal/reports/orders')

        today = date.today()
        df = _parse_date(date_from, fallback=date(today.year, 1, 1))
        dt = _parse_date(date_to, fallback=today)
        if dt < df:
            dt = df
        df_dt = datetime.combine(df, datetime.min.time())
        dt_dt = datetime.combine(dt, datetime.max.time())

        SO = request.env['sale.order'].sudo()
        orders = SO.search([
            ('franchise_id', 'in', list(franchise_ids)),
            ('date_order', '>=', df_dt),
            ('date_order', '<=', dt_dt),
        ], order='date_order desc')

        buf = io.BytesIO()
        wb = xlsxwriter.Workbook(buf, {'in_memory': True})
        header_fmt = wb.add_format({
            'bold': True, 'bg_color': '#1f4180', 'color': 'white',
            'border': 1,
        })
        money_fmt = wb.add_format({'num_format': '#,##0', 'border': 1})
        date_fmt = wb.add_format({'num_format': 'yyyy-mm-dd hh:mm', 'border': 1})
        cell_fmt = wb.add_format({'border': 1})

        ws = wb.add_worksheet('Orders')
        for c, header in enumerate(EXPORT_HEADERS):
            ws.write(0, c, request.env._(header), header_fmt)
        widths = [16, 18, 24, 24, 14, 10, 16]
        for c, w in enumerate(widths):
            ws.set_column(c, c, w)
        for r, o in enumerate(orders, start=1):
            ws.write(r, 0, o.name or '', cell_fmt)
            if o.date_order:
                ws.write_datetime(r, 1, o.date_order, date_fmt)
            else:
                ws.write(r, 1, '', cell_fmt)
            ws.write(r, 2, o.franchise_id.name or '', cell_fmt)
            ws.write(r, 3, o.partner_id.display_name or '', cell_fmt)
            ws.write(r, 4, _state_label(request.env, o.state), cell_fmt)
            ws.write_number(r, 5, len(o.order_line), cell_fmt)
            ws.write_number(r, 6, float(o.amount_total or 0), money_fmt)

        wb.close()
        buf.seek(0)
        filename = f'report-orders-{df}-{dt}.xlsx'
        return request.make_response(
            buf.read(),
            headers=[
                ('Content-Type',
                 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'),
                ('Content-Disposition', f'attachment; filename="{filename}"'),
                ('Cache-Control', 'private, no-cache'),
            ],
        )
