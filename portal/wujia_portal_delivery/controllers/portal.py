import logging
from datetime import datetime, timedelta
from urllib.parse import urlencode

from werkzeug.exceptions import NotFound

from odoo import _lt, http
from odoo.http import request

from odoo.addons.wujia_portal_base.controllers.portal import (
    get_current_store_ids, get_store_scope_state,
)
from odoo.addons.wujia_portal_base.controllers.utils import (
    PAGE_SIZE_OPTIONS,
    batch_franchise_domain, build_pager, date_range_error, departure_label,
    departure_value, format_order_names,
    group_counts, local_day_range_utc, own_pickings, parse_page_size, portal_tz,
    to_local_dt,
    status_badge,
)

_logger = logging.getLogger(__name__)


def _ics_escape(text):
    if not text:
        return ''
    return (str(text)
            .replace('\\', '\\\\').replace(';', '\\;')
            .replace(',', '\\,').replace('\n', '\\n'))


def _ics_dt(dt):
    if not dt:
        return None
    if isinstance(dt, datetime):
        return dt.strftime('%Y%m%dT%H%M%SZ')
    return dt.strftime('%Y%m%d')


PAGE_SIZE = 20

# Batch badge (label, class modifier) theo delivery_batch_status.
# E2 CMP-SB-001: PC và mobile dùng CHUNG variant, hết hai họ .wujia-mdelivery-badge--*
# và .wj-pc-badge--dlv-*. Variant theo ĐÚNG bậc BA ghi ("Chuẩn bị giao" = processing).
# Nhãn `_lt` dịch lúc render (`_batch_badge`) theo ngôn ngữ người xem; variant ghim cứng, không tra theo nhãn.
MOBILE_BATCH_BADGE = {
    'draft': (_lt('Delivering soon'), status_badge('processing')),
    'assigned': (_lt('Delivering soon'), status_badge('processing')),
    'loading': (_lt('Delivering soon'), status_badge('processing')),
    'delivering': (_lt('Delivering'), status_badge('processing')),
    'done': (_lt('Delivered'), status_badge('success')),
    'cancelled': (_lt('Cancelled'), status_badge('danger')),
}
PC_BATCH_BADGE = MOBILE_BATCH_BADGE  # một nguồn cho cả hai khổ

# Chip lọc (Tất cả/Sắp giao/Đang giao/Đã giao) → nhóm delivery_batch_status.
BATCH_STATUS_GROUP = {
    'soon': ['draft', 'assigned', 'loading'],
    'going': ['delivering'],
    'done': ['done'],
}


def _batch_badge(status):
    """(nhãn đã dịch, class badge) của 1 chuyến; trạng thái lạ ⇒ in thô + neutral."""
    meta = MOBILE_BATCH_BADGE.get(status)
    if not meta:
        return status or '—', status_badge('neutral')
    label, modifier = meta
    return request.env._(label), modifier


def _chip_counts(Batch, base_domain):
    """Đếm chuyến theo nhóm cho chips card-head — 1 `_read_group`, xem `group_counts`."""
    return group_counts(Batch, base_domain, 'delivery_batch_status', BATCH_STATUS_GROUP)


def _hhmm(dt, tz):
    dt = to_local_dt(dt, tz)
    return dt.strftime('%H:%M') if dt else '--'


def _parse_date(value):
    """'YYYY-MM-DD' (input type=date) → date, hoặc None."""
    if not value:
        return None
    try:
        return datetime.strptime(value, '%Y-%m-%d').date()
    except (TypeError, ValueError):
        return None


def _short_departure(dt, tz):
    """'29/06 · 07:30' — Figma 4731 list card."""
    dt = to_local_dt(dt, tz)
    if not dt:
        return '—'
    return '%s · %s' % (dt.strftime('%d/%m'), dt.strftime('%H:%M'))


def _full_departure(dt, tz):
    """'29/06/2026 · 07:30' — Figma 4731 detail."""
    dt = to_local_dt(dt, tz)
    if not dt:
        return '—'
    return dt.strftime('%d/%m/%Y · %H:%M')


def _related_orders(pickings):
    """Chuỗi 'SO…, SO… +N' — đơn liên quan trong chuyến (mobile)."""
    names = []
    for so in pickings.mapped('sale_id'):
        if so.name and so.name not in names:
            names.append(so.name)
    return format_order_names(names)


class WujiaPortalDelivery(http.Controller):

    def _delivery_list_values(self, page=1, bs='', date_from='', date_to='', q='',
                              page_size=None, **kw):
        """Context danh sách chuyến — dùng chung cho trang đầy đủ và fragment AJAX."""
        franchise_ids = get_current_store_ids()
        if not franchise_ids:
            return {
                'no_franchise': True, 'store_scope': get_store_scope_state(),
                'batches': [], 'view_state': 'empty',
                'pgn': None, 'chip_counts': {},
                'date_from': '', 'date_to': '', 'bs': '', 'q': '',
                'chip_qs': '', 'filter_error': '',
            }

        try:
            page = max(1, int(page))
        except (TypeError, ValueError):
            page = 1
        size = parse_page_size(page_size, PAGE_SIZE)
        offset = (page - 1) * size
        q = (q or '').strip()
        tz = portal_tz()

        # Ngày ngược: không chạy query, giữ nguyên 2 ô đã nhập, báo TẠI thanh lọc.
        # Nếu cứ chạy thì domain vô nghiệm ⇒ empty state "chưa có chuyến nào",
        # người dùng tưởng hết dữ liệu (cùng lỗi WJ-PH-007 bên Lịch sử đặt hàng).
        filter_error = date_range_error(date_from, date_to)
        if filter_error:
            return {
                'no_franchise': False, 'batches': [], 'view_state': 'empty',
                'pgn': None, 'chip_counts': {},
                'date_from': date_from, 'date_to': date_to, 'bs': bs, 'q': q,
                'chip_qs': '', 'filter_error': filter_error,
            }

        # Batch-centric (1 thẻ = 1 chuyến xe) — nuôi cả desktop (Figma 4766) + mobile (4731).
        batches, pgn, chip_counts, view_state = [], None, {}, 'list'
        try:
            Batch = request.env['stock.picking.batch'].sudo()
            base_domain = batch_franchise_domain(franchise_ids)
            # Ngày người dùng chọn là giờ địa phương, planned_departure lưu UTC → phải quy đổi,
            # không thì lọc lệch nửa ngày ở 2 biên (cùng lỗi WJ-PH-002 bên Lịch sử đặt hàng).
            utc_from, utc_to = local_day_range_utc(
                _parse_date(date_from), _parse_date(date_to), tz)
            if utc_from:
                base_domain.append(('planned_departure', '>=', utc_from))
            if utc_to:
                base_domain.append(('planned_departure', '<=', utc_to))
            # WJ-DELIVERY-006: chip đếm trên CHÍNH tập đã lọc (franchise + ngày +
            # keyword). Bỏ `bs` để chọn 1 chip không làm 0 hết các chip còn lại.
            kw_domain = ['|', ('name', 'ilike', q),
                              ('picking_ids.sale_id.name', 'ilike', q)] if q else []
            chip_counts = _chip_counts(Batch, base_domain + kw_domain)

            bdomain = list(base_domain) + kw_domain
            if bs in BATCH_STATUS_GROUP:
                bdomain.append(('delivery_batch_status', 'in', BATCH_STATUS_GROUP[bs]))
            total = Batch.search_count(bdomain)
            recs = Batch.search(bdomain, limit=size, offset=offset,
                                order='planned_departure desc, id desc')
            for b in recs:
                own = own_pickings(b, franchise_ids)
                label, modifier = _batch_badge(b.delivery_batch_status)
                v = b.vehicle_id
                vehicle_str = ('%s · %s' % (v.name, v.driver_name)) if v and v.driver_name else (v.name if v else '—')
                upd = b.actual_departure or b.write_date
                dep, is_actual = departure_value(b)
                batches.append({
                    # Keys mobile (S24) — KHÔNG đổi:
                    'id': b.id, 'name': b.name or '—',
                    'label': label, 'modifier': modifier,
                    'departure': _short_departure(dep, tz),
                    'departure_label': departure_label(is_actual),
                    'departure_actual': is_actual,
                    'orders': _related_orders(own),
                    # Keys PC desktop:
                    'pc_label': label, 'pc_modifier': modifier,
                    'departure_full': _full_departure(dep, tz),
                    'vehicle': vehicle_str,
                    'plate': (v.license_plate if v and v.license_plate else '—'),
                    'updated': _hhmm(upd, tz),
                })
            pgn = build_pager(total, page, size, path='/portal/delivery',
                              item_label=_lt('trips'),
                              page_size_options=PAGE_SIZE_OPTIONS)
            if not batches:
                view_state = 'empty'
        except Exception:
            _logger.exception('Wujia portal delivery — batch list failed')
            view_state = 'error'

        # QA preview: ?_preview=loading|error|empty|list (drive cả desktop + mobile).
        preview = kw.get('_preview')
        if preview in ('loading', 'error', 'empty', 'list'):
            view_state = preview

        # Đuôi querystring cho link chip (giữ q + ngày). Encode ở đây thay vì nối
        # chuỗi trong QWeb — từ khoá có '&' hay dấu cách sẽ làm vỡ link.
        extra = {k: v for k, v in (
            ('q', q), ('date_from', date_from), ('date_to', date_to)) if v}
        return {
            'no_franchise': False,
            'batches': batches, 'view_state': view_state, 'pgn': pgn,
            'chip_counts': chip_counts,
            'date_from': date_from, 'date_to': date_to, 'bs': bs, 'q': q,
            'chip_qs': ('&' + urlencode(extra)) if extra else '',
            'filter_error': '',
        }

    @http.route(['/portal/delivery'], type='http', auth='user', sitemap=False)
    def portal_delivery_list(self, **kw):
        return request.render('wujia_portal_delivery.portal_delivery_tracking',
                              self._delivery_list_values(**kw))

    @http.route(['/portal/delivery/results'], type='http', auth='user', sitemap=False)
    def portal_delivery_results(self, **kw):
        """Fragment 3 khối kết quả (chips + list + pager) cho lọc AJAX.

        Cùng một context với trang đầy đủ — chỉ bỏ shell portal (navbar/sidebar/
        chuông) vốn không đổi khi lọc, nên bấm chip không phải dựng lại cả trang.
        """
        return request.render('wujia_portal_delivery.portal_delivery_results',
                              self._delivery_list_values(**kw))

    @http.route(['/portal/delivery/<int:batch_id>'], type='http', auth='user', sitemap=False)
    def portal_delivery_detail(self, batch_id, **kw):
        franchise_ids = get_current_store_ids()
        if not franchise_ids:
            return request.redirect('/portal/delivery')
        Batch = request.env['stock.picking.batch'].sudo()
        batch = Batch.search([
            ('id', '=', batch_id),
            ('picking_ids.franchise_id', 'in', list(franchise_ids)),
        ], limit=1)
        if not batch:
            return request.redirect('/portal/delivery')
        pickings = own_pickings(batch, franchise_ids)

        # Mobile (Figma 4731 detail): gom sản phẩm trong chuyến theo product → SL + ĐVT.
        products, seen = [], {}
        for mv in pickings.mapped('move_ids'):
            prod = mv.product_id
            if not prod:
                continue
            row = seen.get(prod.id)
            if row is None:
                row = {
                    'name': prod.display_name or prod.name or '—',
                    'qty': 0.0,
                    'uom': mv.product_uom.name if mv.product_uom else (prod.uom_id.name or ''),
                }
                seen[prod.id] = row
                products.append(row)
            row['qty'] += mv.product_uom_qty or 0.0

        label, modifier = _batch_badge(batch.delivery_batch_status)
        updated = batch.actual_departure or batch.write_date
        tz = portal_tz()

        # PC desktop (Figma 4766:1091): timeline 3 bước + SO chips + kho xuất + tên CH.
        status = batch.delivery_batch_status or ''
        tl_steps = (
            'done' if (batch.actual_departure or status in ('delivering', 'done')) else 'inactive',
            'active' if status == 'delivering' else ('done' if status == 'done' else 'inactive'),
            'done' if status == 'done' else 'inactive',
        )
        tl_times = (
            _hhmm(batch.actual_departure or (batch.planned_departure if status in ('delivering', 'done') else None), tz),
            _hhmm(batch.write_date if status in ('delivering', 'done') else None, tz),
            _hhmm(batch.write_date if status == 'done' else None, tz),
        )
        so_names = []
        for p in pickings:
            if p.sale_id and p.sale_id.name and p.sale_id.name not in so_names:
                so_names.append(p.sale_id.name)
        src_location = '—'
        if pickings and pickings[0].location_id:
            loc = pickings[0].location_id
            src_location = loc.complete_name or loc.name or '—'
        fr = (pickings[:1].mapped('franchise_id')
              or pickings[:1].mapped('sale_id.franchise_id'))[:1]
        store_label = (('[%s] ' % fr.code) if fr and fr.code else '') + (fr.name if fr else '') or '—'
        dep, is_actual = departure_value(batch)
        dep_str, dep_label = _full_departure(dep, tz), departure_label(is_actual)

        return request.render('wujia_portal_delivery.portal_delivery_detail', {
            'batch': batch, 'own_pickings': pickings,
            'products': products,
            # Mobile (S24):
            'm_badge': (label, modifier),
            'm_departure_full': dep_str,
            'm_departure_label': dep_label,
            'm_updated': _full_departure(updated, tz),
            'm_orders': _related_orders(pickings),
            # PC desktop:
            'pc_badge': (label, modifier),
            'pc_departure': dep_str,
            'pc_departure_label': dep_label,
            'pc_updated': _full_departure(updated, tz),
            'pc_orders': _related_orders(pickings),
            'so_names': so_names,
            'tl_steps': tl_steps,
            'tl_times': tl_times,
            'src_location': src_location,
            'store_label': store_label,
        })

    @http.route(['/portal/delivery/<int:batch_id>.ics'], type='http',
                auth='user', sitemap=False)
    def portal_delivery_ics(self, batch_id, **kw):
        """Export lịch giao hàng dạng ICS — import vào Google/Outlook calendar."""
        franchise_ids = get_current_store_ids()
        if not franchise_ids:
            raise NotFound()
        Batch = request.env['stock.picking.batch'].sudo()
        batch = Batch.search([
            ('id', '=', batch_id),
            ('picking_ids.franchise_id', 'in', list(franchise_ids)),
        ], limit=1)
        if not batch:
            raise NotFound()
        dt_start = batch.scheduled_date or datetime.now()
        dt_end = dt_start + timedelta(hours=2)
        pickings = own_pickings(batch, franchise_ids)
        env = request.env
        summary = env._('Delivery %s', batch.name or batch.id)
        description_parts = [env._('Batch: %s', batch.name or batch.id)]
        for p in pickings:
            description_parts.append(f'- {p.name}: {p.origin or ""}')
        description = '\n'.join(description_parts)
        location = ', '.join(
            sorted({p.franchise_id.name for p in pickings if p.franchise_id})
        )
        ics = (
            'BEGIN:VCALENDAR\r\n'
            'VERSION:2.0\r\n'
            'PRODID:-//WujiaTea//Portal Delivery//VI\r\n'
            'CALSCALE:GREGORIAN\r\n'
            'METHOD:PUBLISH\r\n'
            'BEGIN:VEVENT\r\n'
            f'UID:wujia-delivery-{batch.id}@wujiatea\r\n'
            f'DTSTAMP:{_ics_dt(datetime.utcnow())}\r\n'
            f'DTSTART:{_ics_dt(dt_start)}\r\n'
            f'DTEND:{_ics_dt(dt_end)}\r\n'
            f'SUMMARY:{_ics_escape(summary)}\r\n'
            f'DESCRIPTION:{_ics_escape(description)}\r\n'
            f'LOCATION:{_ics_escape(location)}\r\n'
            'STATUS:CONFIRMED\r\n'
            'END:VEVENT\r\n'
            'END:VCALENDAR\r\n'
        )
        filename = f'delivery-{batch.id}.ics'
        return request.make_response(
            ics,
            headers=[
                ('Content-Type', 'text/calendar; charset=utf-8'),
                ('Content-Disposition', f'attachment; filename="{filename}"'),
                ('Cache-Control', 'private, no-cache'),
            ],
        )
