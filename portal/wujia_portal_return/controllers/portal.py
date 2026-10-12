"""Wujia portal — Return Request controller (single-product, BA spec K + Task STT3).

Routes:
- GET  /portal/return                              list (filter state/date/q)
- GET, POST /portal/return/new                     form + submit (no draft)
- GET  /portal/return/<int>                        detail
- GET  /portal/return/<int>/attachment/<int>       download attachment
"""
import json
import logging
from datetime import datetime

from werkzeug.exceptions import Forbidden, NotFound

from odoo import _lt, http
from odoo.exceptions import ValidationError
from odoo.http import request
from odoo.tools.mimetypes import guess_mimetype

from odoo.addons.wujia_return.models.wujia_return_request import (
    IMAGE_MIME, MAX_IMAGE_MB, MAX_IMAGES, MAX_TOTAL_MB, MAX_VIDEO_MB, MAX_VIDEOS,
    MIN_IMAGES_BEFORE_SEND as MIN_IMAGES, ORDER_WINDOW_DAYS, VIDEO_MIME,
)
from odoo.addons.wujia_portal_base.controllers.portal import (
    get_current_store_ids, get_store_scope_state,
)
from odoo.addons.wujia_portal_base.controllers.utils import (
    PAGE_SIZE_OPTIONS,
    RETURN_STATUS_LABELS,
    attach_files_to_record,
    build_pager,
    date_range_error,
    fmt_local_dt,
    local_day_range_utc,
    parse_page_size,
    portal_tz,
    return_status_label as state_label,
    status_badge,
    status_badge_for,
)

_logger = logging.getLogger(__name__)

PAGE_SIZE = 20

# Phương án xử lý HQ chốt khi duyệt.
RESOLUTION_LABELS = {
    'exchange': _lt('Exchange'),
    'return': _lt('Return'),
    'compensation': _lt('Compensation'),
    'refuse': _lt('Rejected'),
}

# Tình trạng bù hàng (label + badge class) — hiển thị tiến độ bù cho cửa hàng.
COMPENSATION_STATUS_LABELS = {k: (v, status_badge_for(v)) for k, v in {
    'none': _lt('Not processed'),
    'allocated': _lt('Replacement ordered'),
    'partial': _lt('Partially compensated'),
    'done': _lt('Fully compensated'),
}.items()}


# Bộ lọc trạng thái (UAT-BH-006): cùng nhãn với badge trên card — khoá = `_portal_status_key()`.
FILTER_OPTIONS = [(key, label) for key, (label, _cls) in RETURN_STATUS_LABELS.items()]

# Option rỗng của dropdown lọc — một nguồn cho PC + mobile (mobile chỉ có aria-label).
FILTER_ALL_LABEL = _lt('— All statuses —')


def _translated(labels):
    """{key: (nhãn, badge)} với nhãn `_lt` dịch theo ngôn ngữ người xem (không `str(lazy)`)."""
    return {k: (request.env._(label), cls) for k, (label, cls) in labels.items()}


class WujiaPortalReturn(http.Controller):

    @http.route(['/portal/return'], type='http', auth='user', sitemap=False)
    def portal_return_list(self, page=1, state='', date_from='', date_to='', q='',
                           page_size=None, notice='', **kw):
        franchise_ids = get_current_store_ids()
        if not franchise_ids:
            return request.render('wujia_portal_return.portal_return_list',
                                  self._list_ctx(no_franchise=True, store_scope=get_store_scope_state()))

        Model = request.env['wujia.return.request'].sudo()
        domain = Model._portal_scope_domain(franchise_ids) + Model._portal_status_domain(state)
        q = (q or '').strip()
        if q:
            # Action 2: mã yêu cầu · mã đơn · chuyến · tên/mã sản phẩm.
            domain += ['|', '|', '|', '|',
                       ('name', 'ilike', q),
                       ('sale_order_id.name', 'ilike', q),
                       ('batch_id.name', 'ilike', q),
                       ('product_id.name', 'ilike', q),
                       ('product_id.default_code', 'ilike', q)]

        df, dt_ = self._parse_date(date_from), self._parse_date(date_to)
        # Sai định dạng = hỏng cả URL, giữ banner đầu trang như cũ.
        if (date_from and not df) or (date_to and not dt_):
            return request.render('wujia_portal_return.portal_return_list',
                                  self._list_ctx(notice='bad_filter', state=state, q=q,
                                                 date_from=date_from, date_to=date_to))
        # Ngày ngược = lỗi của chính ô lọc ⇒ báo TẠI thanh lọc, cùng khuôn 5 màn kia.
        filter_error = date_range_error(df, dt_)
        if filter_error:
            return request.render('wujia_portal_return.portal_return_list',
                                  self._list_ctx(state=state, q=q, date_from=date_from,
                                                 date_to=date_to,
                                                 filter_error=filter_error))
        # Khoảng ngày theo giờ địa phương (Odoo lưu naive UTC → lệch −7h nếu so thẳng).
        utc_from, utc_to = local_day_range_utc(df, dt_, portal_tz())
        if utc_from:
            domain.append(('request_date', '>=', utc_from))
        if utc_to:
            domain.append(('request_date', '<=', utc_to))

        page = self._parse_int(page, 1, minimum=1)
        size = parse_page_size(page_size, PAGE_SIZE)
        total = Model.search_count(domain)
        pgn = build_pager(total, page, size, path='/portal/return',
                          item_label=_lt('requests'),
                          page_size_options=PAGE_SIZE_OPTIONS)
        page = pgn['page']
        returns = Model.search(domain, limit=size, offset=(page - 1) * size,
                               order='request_date desc')
        return request.render('wujia_portal_return.portal_return_list', self._list_ctx(
            returns=returns, pgn=pgn, state=state, date_from=date_from,
            date_to=date_to, q=q, notice=notice, total=total,
        ))

    @http.route(['/portal/return/new'], type='http', auth='user',
                methods=['GET', 'POST'], sitemap=False, csrf=True)
    def portal_return_new(self, **post):
        franchise_ids = get_current_store_ids()
        if not franchise_ids:
            return request.redirect('/portal/return')

        if request.httprequest.method != 'POST':
            return self._render_form()

        images = self._files('images')
        video = self._files('video')
        try:
            rr = request.env['wujia.return.request'].create_from_portal(
                post, franchise_ids,
                images=[self._sniff(f) for f in images], videos=[self._sniff(f) for f in video],
                attach=lambda rr: self._attach_evidence(rr, images, video))
        except ValidationError as e:
            return self._render_form(error=str(e), prefill=post)
        except Exception:                          # noqa: BLE001 — không lộ traceback ra portal
            _logger.exception('Return request create failed')
            return self._render_form(
                error=request.env._("Could not submit the request. Please check the information and try again."),
                prefill=post)
        return request.redirect(f'/portal/return/{rr.id}?message=created')

    @http.route(['/portal/return/<int:request_id>'], type='http',
                auth='user', sitemap=False)
    def portal_return_detail(self, request_id, **kw):
        franchise_ids = get_current_store_ids()
        if not franchise_ids:
            return request.redirect('/portal/return')
        rr = self._scoped(request_id, franchise_ids)
        if not rr:
            # Không phân biệt "không có" với "của cửa hàng khác" (chống dò ID).
            return request.redirect('/portal/return?notice=not_found')
        return request.render('wujia_portal_return.portal_return_detail', {
            'rr': rr,
            'wj_state_label': state_label,
            'comp': self._build_compensation_ctx(rr),
            'wj_dt': fmt_local_dt,
            'message': kw.get('message'),
        })

    @http.route(['/portal/return/<int:request_id>/attachment/<int:att_id>'],
                type='http', auth='user', sitemap=False)
    def portal_return_attachment_download(self, request_id, att_id, **kw):
        """Stream attachment — ACL: chỉ user truy cập franchise của RR."""
        franchise_ids = get_current_store_ids()
        if not franchise_ids:
            raise Forbidden()
        rr = self._scoped(request_id, franchise_ids)
        if not rr:
            raise NotFound()
        allowed = set(rr.image_attachment_ids.ids) | set(rr.video_attachment_ids.ids)
        if att_id not in allowed:
            raise Forbidden()
        att = request.env['ir.attachment'].sudo().browse(att_id).exists()
        if not att:
            raise NotFound()
        return request.env['ir.binary']._get_stream_from(att).get_response(
            as_attachment=False,
        )

    # ============================================================== helpers
    @staticmethod
    def _parse_int(value, default, minimum=None, maximum=None):
        try:
            value = int(value)
        except (TypeError, ValueError):
            return default
        if minimum is not None:
            value = max(minimum, value)
        if maximum is not None:
            value = min(maximum, value)
        return value

    @staticmethod
    def _parse_date(value):
        try:
            return datetime.strptime(value, '%Y-%m-%d').date() if value else None
        except (TypeError, ValueError):
            return None

    def _list_ctx(self, **kw):
        ctx = {
            'no_franchise': False, 'returns': [], 'pgn': None, 'total': 0,
            'wj_state_label': state_label,
            'comp_status_labels': _translated(COMPENSATION_STATUS_LABELS),
            'filter_options': [(key, request.env._(label)) for key, label in FILTER_OPTIONS],
            'filter_all_label': request.env._(FILTER_ALL_LABEL),
            'state': '', 'date_from': '', 'date_to': '', 'q': '', 'notice': '',
            'filter_error': '',
            'wj_dt': fmt_local_dt,
        }
        ctx.update(kw)
        return ctx

    @staticmethod
    def _scoped(request_id, franchise_ids):
        Model = request.env['wujia.return.request'].sudo()
        return Model.search(Model._portal_scope_domain(franchise_ids) + [('id', '=', request_id)], limit=1)

    @staticmethod
    def _files(field):
        return [f for f in request.httprequest.files.getlist(field) if f and f.filename]

    @staticmethod
    def _file_size(f):
        f.stream.seek(0, 2)
        size = f.stream.tell()
        f.stream.seek(0)
        return size

    @staticmethod
    def _real_mime(f):
        """MIME đọc từ NỘI DUNG file.

        ⚠️ `guess_mimetype` của Odoo không có chữ ký video (và `python-magic`
        không được cài) ⇒ mp4/mov ra `application/octet-stream`. Tự đọc hộp
        `ftyp` của ISO-BMFF: byte 4–8 là 'ftyp', 8–12 là brand.
        """
        head = f.stream.read(4096)
        f.stream.seek(0)
        if head[4:8] == b'ftyp':
            brand = head[8:12]
            return 'video/quicktime' if brand == b'qt  ' else 'video/mp4'
        return guess_mimetype(head)

    def _sniff(self, f):
        """(dung lượng, MIME thật) cho luật minh chứng của model.

        Ghi đè header client bằng MIME thật: attachment lưu đúng loại, và
        `attach_files_to_record` (kiểm theo header) không loại nhầm .mov mà
        trình duyệt gửi kèm 'application/octet-stream'.
        """
        real = self._real_mime(f)
        f.headers['Content-Type'] = real
        return self._file_size(f), real

    def _attach_evidence(self, rr, images, video):
        """Tạo attachment sau khi model đã kiểm — tái dùng helper chung của portal."""
        vals = {}
        if images:
            atts = attach_files_to_record(
                rr, images, allowed_mime=IMAGE_MIME,
                max_size_mb=MAX_IMAGE_MB, max_count=MAX_IMAGES)
            vals['image_attachment_ids'] = [(4, a.id) for a in atts]
        if video:
            atts = attach_files_to_record(
                rr, video, allowed_mime=VIDEO_MIME,
                max_size_mb=MAX_VIDEO_MB, max_count=MAX_VIDEOS)
            vals['video_attachment_ids'] = [(4, a.id) for a in atts]
        if vals:
            rr.write(vals)

    def _build_compensation_ctx(self, rr):
        """Context tiến độ bù cho cửa hàng (read-only); None khi HQ chưa chốt phương án."""
        view = rr._portal_compensation_view()
        if view is None:
            return None
        resolution = RESOLUTION_LABELS.get(rr.resolution_type)
        ctx = dict(view, resolution_label=request.env._(resolution) if resolution else rr.resolution_type)
        if not ctx['is_compensation']:
            return ctx
        ctx.update({
            'approved_uom': rr.approved_uom_id.name or '',
            'product_label': rr.compensation_product_id.display_name or '—',
            'status': _translated(COMPENSATION_STATUS_LABELS).get(
                rr.compensation_status,
                (rr.compensation_status or '—', status_badge('neutral'))),
            'approval_note': rr.approval_note or '',
            'orders': [
                {
                    'name': so.name,
                    'state_label': dict(so._fields['state']._description_selection(
                        request.env)).get(so.state, so.state),
                    'delivery_label': self._so_delivery_label(so),
                }
                for so in rr.compensation_so_ids
            ],
        })
        return ctx

    def _so_delivery_label(self, so):
        """Nhãn tiến độ giao của 1 đơn bù (đếm phiếu giao done/tổng)."""
        if so.state == 'cancel':
            return request.env._('Compensation order cancelled')
        if 'picking_ids' not in so._fields:
            return ''
        pickings = so.picking_ids
        total = len(pickings)
        if not total:
            return request.env._('No delivery slip yet')
        done = len(pickings.filtered(lambda p: p.state == 'done'))
        if done == 0:
            return request.env._('Not delivered')
        if done >= total:
            return request.env._('Fully delivered')
        return request.env._('Delivered %d/%d slips') % (done, total)

    def _render_form(self, error=None, prefill=None):
        franchise_ids = get_current_store_ids()
        franchises = request.env['wujia.franchise.management'].sudo().browse(
            franchise_ids)
        orders = request.env['sale.order'].sudo().search(
            request.env['wujia.return.request']._portal_eligible_order_domain(franchise_ids),
            order='wj_delivery_done_date desc')
        issue_types = request.env['wujia.return.issue.type'].sudo().search(
            [('active', '=', True)])
        # Map order_id -> [{id, label}] cho cascade select sản phẩm.
        order_lines = {
            o.id: [{
                'id': line.id,
                'label': '%s (%s %s)' % (
                    line.product_id.display_name,
                    ('{:,.0f}'.format(line.product_uom_qty or 0)),
                    line.product_uom_id.name or ''),
            } for line in o.order_line if line.product_id]
            for o in orders
        }
        return request.render('wujia_portal_return.portal_return_form', {
            'franchises': franchises, 'orders': orders,
            'order_lines_json': json.dumps(order_lines),
            'issue_types': issue_types,
            'error': error, 'values': prefill or {},
            'window_days': ORDER_WINDOW_DAYS,
            'min_images': MIN_IMAGES, 'max_images': MAX_IMAGES,
            'max_total_mb': MAX_TOTAL_MB, 'max_video_mb': MAX_VIDEO_MB,
            'wj_dt': fmt_local_dt,
            'today': datetime.now(),
        })
