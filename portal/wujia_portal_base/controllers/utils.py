"""Shared utilities cho portal controllers.

Reuse-first: mọi module portal_* khác import từ đây thay vì viết lại.
Tối ưu cho 1500 user — ormcache + atomic SQL + streaming attachment.
"""
import base64
import functools
import logging
import time
from datetime import date, datetime, time as dt_time
from urllib.parse import urlencode

import pytz
from werkzeug.exceptions import Forbidden, TooManyRequests
from werkzeug.utils import secure_filename

from odoo import _
from odoo.tools.translate import LazyGettext, LazyTranslate
from odoo.exceptions import ValidationError
from odoo.http import request

_logger = logging.getLogger(__name__)
_lt = LazyTranslate(__name__)


# ---------------------------------------------------------------------------
# Timezone portal
# ---------------------------------------------------------------------------
#
# Odoo lưu Datetime dạng naive UTC. Controller portal trả thẳng ra template =
# người dùng thấy sớm 7 giờ (WJ-PH-002), và lọc theo ngày người dùng chọn (giờ
# địa phương) so với cột UTC = sai biên nửa ngày.
#
# 3 hàm dưới là chỗ duy nhất mọi module portal_* nên dùng để đổi qua lại.
# ---------------------------------------------------------------------------

DEFAULT_PORTAL_TZ = 'Asia/Ho_Chi_Minh'


def portal_tz(env=None):
    """Timezone của user hiện tại. tz rỗng/rác → DEFAULT_PORTAL_TZ, KHÔNG raise.

    Đã có user để tz = 'Asia/Saigon' làm /portal/reports/orders 500 — trang portal
    không được chết vì một ô cấu hình.
    """
    try:
        name = (env or request.env).user.tz
    except Exception:                                   # noqa: BLE001 — env hỏng cũng không nổ trang
        name = None
    try:
        return pytz.timezone(name or DEFAULT_PORTAL_TZ)
    except Exception:                                   # noqa: BLE001 — UnknownTimeZoneError + tz không phải str
        return pytz.timezone(DEFAULT_PORTAL_TZ)


def to_local_dt(dt, tz):
    """Datetime naive UTC (Odoo) → datetime naive giờ địa phương.

    Trả naive để template giữ nguyên `.strftime(...)` — không phải sửa QWeb.
    """
    if not dt:
        return None
    if not isinstance(dt, datetime):                    # Date field → không có giờ để đổi
        return dt
    return pytz.utc.localize(dt).astimezone(tz).replace(tzinfo=None)


def fmt_local_dt(dt, fmt, tz=None):
    """Datetime UTC → chuỗi đã đổi sang giờ địa phương. Template dùng qua biến `wj_dt`."""
    local = to_local_dt(dt, tz or portal_tz())
    return local.strftime(fmt) if local else ''


def local_day_range_utc(date_from, date_to, tz):
    """(date, date) giờ địa phương → (datetime, datetime) naive UTC để đưa vào domain.

    Đảo chiều đúng fields.Datetime.context_timestamp. Mỗi vế None nếu không nhập.
    """
    def _bound(d, t):
        if not d:
            return None
        return tz.localize(datetime.combine(d, t)).astimezone(pytz.utc).replace(tzinfo=None)

    return _bound(date_from, dt_time.min), _bound(date_to, dt_time.max)


# Nguồn DUY NHẤT của thông điệp khoảng ngày ngược — mọi màn dùng chung câu chữ và chỗ hiển thị.
ERR_DATE_RANGE = _lt('From date cannot be later than To date')


def parse_portal_date(value):
    """Chuỗi 'YYYY-MM-DD' của ô lọc → date, sai định dạng hoặc rỗng → None."""
    if not value:
        return None
    try:
        return datetime.strptime(value, '%Y-%m-%d').date()
    except (TypeError, ValueError):
        return None


def date_range_error(date_from, date_to):
    """Thông điệp nếu khoảng ngày ngược, chuỗi rỗng nếu hợp lệ.

    Nhận chuỗi thô của ô lọc HOẶC date đã parse. Chỉ bắt ngày ngược — ngày sai
    định dạng là việc của từng màn (có màn coi là bỏ lọc, có màn báo riêng).
    """
    df = date_from if isinstance(date_from, date) else parse_portal_date(date_from)
    dt = date_to if isinstance(date_to, date) else parse_portal_date(date_to)
    return str(ERR_DATE_RANGE) if (df and dt and df > dt) else ''


# ---------------------------------------------------------------------------
# Rate limit decorator
# ---------------------------------------------------------------------------
#
# Sliding window counter dùng ormcache. Key (ip, endpoint, bucket_seconds // window).
# Khi window expire, bucket key đổi → counter reset tự nhiên.
#
# KHÔNG dùng cache TTL chuẩn — ormcache không có TTL native, dùng bucketing
# theo unix time là hành vi đúng + có cleanup ngầm khi cache evict.
# ---------------------------------------------------------------------------

class _RateLimiter:
    """Lớp wrapper để ormcache có thể decorate method.

    ormcache yêu cầu method trên model — workaround: dùng dict in-memory với
    eviction theo timestamp. Quy mô 1500 user × few endpoints = OK.
    """
    _store = {}  # {(ip, endpoint, bucket): count}
    _last_gc = 0

    @classmethod
    def hit(cls, ip, endpoint, window_sec):
        now = int(time.time())
        bucket = now // window_sec
        key = (ip, endpoint, bucket)
        cls._store[key] = cls._store.get(key, 0) + 1
        # GC mỗi 5 phút — xóa bucket cũ
        if now - cls._last_gc > 300:
            cutoff = bucket - 2
            cls._store = {
                k: v for k, v in cls._store.items() if k[2] >= cutoff
            }
            cls._last_gc = now
        return cls._store[key]


def rate_limit(max_calls, window_sec, key_fn=None):
    """Decorator giới hạn số call / window.

    Args:
        max_calls: số call tối đa cho phép trong window
        window_sec: độ dài window (giây)
        key_fn: callable(request) -> str, default = remote_addr + endpoint

    Raises:
        TooManyRequests (HTTP 429) khi vượt limit.
    """
    def decorator(fn):
        @functools.wraps(fn)
        def wrapper(self, *args, **kwargs):
            ip = (
                request.httprequest.headers.get('X-Forwarded-For', '').split(',')[0].strip()
                or request.httprequest.remote_addr
                or 'unknown'
            )
            endpoint = key_fn(request) if key_fn else fn.__qualname__
            count = _RateLimiter.hit(ip, endpoint, window_sec)
            if count > max_calls:
                _logger.warning(
                    'Rate limit hit: ip=%s endpoint=%s count=%d max=%d',
                    ip, endpoint, count, max_calls,
                )
                raise TooManyRequests(
                    description=_('Too many requests. Please try again later.')
                )
            return fn(self, *args, **kwargs)
        return wrapper
    return decorator


# ---------------------------------------------------------------------------
# File upload helper — shared cho return / support / info_request
# ---------------------------------------------------------------------------

DEFAULT_IMAGE_MIME = ('image/png', 'image/jpeg', 'image/jpg', 'image/webp')
DEFAULT_DOC_MIME = (
    'image/png', 'image/jpeg', 'image/jpg', 'image/webp', 'application/pdf',
)


def attach_files_to_record(
    record, files, allowed_mime=DEFAULT_IMAGE_MIME,
    max_size_mb=5, max_count=10,
):
    """Tạo ir.attachment cho từng file, link tới record.

    Validate count, size, MIME backend (đừng trust client header thuần).
    Sanitize filename qua secure_filename — chống path traversal.

    Args:
        record: recordset đơn (ensure_one).
        files: list FileStorage từ request.httprequest.files.getlist(...).
        allowed_mime: tuple MIME được phép.
        max_size_mb: int, mỗi file tối đa.
        max_count: int, số file tối đa.

    Returns:
        ir.attachment recordset đã tạo.

    Raises:
        ValidationError nếu validation fail.
    """
    record.ensure_one()
    files = [f for f in (files or []) if f and f.filename]
    if not files:
        return request.env['ir.attachment'].browse()
    if len(files) > max_count:
        raise ValidationError(
            _('At most %s files allowed. You sent %s files.') % (max_count, len(files))
        )
    max_bytes = max_size_mb * 1024 * 1024
    Attachment = request.env['ir.attachment'].sudo()
    created = Attachment
    for f in files:
        data = f.read()
        if len(data) > max_bytes:
            raise ValidationError(
                _('File "%s" exceeds %sMB.') % (f.filename, max_size_mb)
            )
        if f.mimetype not in allowed_mime:
            raise ValidationError(
                _('File "%s" has an unsupported format (%s).') % (
                    f.filename, f.mimetype,
                )
            )
        att = Attachment.create({
            'name': secure_filename(f.filename) or 'upload',
            'res_model': record._name,
            'res_id': record.id,
            'datas': base64.b64encode(data),
            'mimetype': f.mimetype,
        })
        created |= att
    return created


# ---------------------------------------------------------------------------
# Pagination helper
# ---------------------------------------------------------------------------

ELLIPSIS = '…'

PAGE_SIZE_OPTIONS = (10, 20, 50)


def parse_page_size(value, default, options=PAGE_SIZE_OPTIONS):
    """Cỡ trang chỉ nhận giá trị có trong ô chọn; rác hoặc thiếu → mặc định route."""
    try:
        size = int(value)
    except (TypeError, ValueError):
        return default
    return size if size in options else default


def build_pager(total, page, page_size, *, path=None, item_label=_lt('records'),
                page_size_options=(), size_param='page_size', extra_drop=()):
    """Nguồn DUY NHẤT của mọi pager portal (CMP-PGNT-001).

    Query-string lấy từ request hiện tại trừ `page` nên bộ lọc/sort/keyword không
    bao giờ rơi khi đổi trang — thay cho 6 cách nối tay trước đây.
    """
    try:
        page_size = max(1, min(int(page_size), 100))
    except (TypeError, ValueError):
        page_size = 20
    try:
        page = max(1, int(page))
    except (TypeError, ValueError):
        page = 1

    total = max(0, int(total or 0))
    total_pages = max(1, (total + page_size - 1) // page_size)
    page = min(page, total_pages)
    offset = (page - 1) * page_size

    base = path or (request.httprequest.path if request else '')
    params = _pager_params(extra_drop)
    numbers = page_numbers(page, total_pages)

    def url(num):
        qs = urlencode(params + [('page', num)])
        return '%s?%s' % (base, qs) if qs else base

    return {
        'page': page,
        'total_pages': total_pages,
        'total_items': total,
        'page_size': page_size,
        'page_size_options': list(page_size_options),
        'size_param': size_param,
        'offset': offset,
        'from_': offset + 1 if total else 0,
        'to': min(offset + page_size, total),
        'numbers': numbers,
        'item_label': str(item_label),
        'urls': {n: url(n) for n in numbers if n != ELLIPSIS},
        'prev_url': url(max(1, page - 1)),
        'next_url': url(min(total_pages, page + 1)),
        'base_url': base,
        'hidden': [(k, v) for k, v in params if k != size_param],
    }


_PAGER_DROP = ('page', 'notice', 'csrf_token')


def _pager_params(extra_drop=()):
    """Param hiện tại (giữ thứ tự, giữ giá trị lặp) trừ page + nhiễu một lần."""
    if not request:
        return []
    drop = set(_PAGER_DROP) | set(extra_drop)
    return [(k, v) for k, v in request.httprequest.args.items(multi=True)
            if k not in drop and v not in ('', None)]


def page_numbers(current, last, edge=1, around=1):
    """Windowed page list cho numbered pager: [1, ELLIPSIS, 4, 5, 6, ELLIPSIS, 20]."""
    if last < 1:
        return []
    keep = set(range(1, edge + 1)) | set(range(last - edge + 1, last + 1))
    keep |= set(range(current - around, current + around + 1))
    pages = sorted(p for p in keep if 1 <= p <= last)
    result, prev = [], 0
    for p in pages:
        if prev and p - prev > 1:
            result.append(ELLIPSIS)
        result.append(p)
        prev = p
    return result


def group_counts(model, domain, field, groups=None, total_key='all'):
    """Đếm bản ghi theo nhóm cho chip lọc — MỘT `_read_group`, không N `search_count`.

    N `search_count` là N lần chạy lại nguyên domain; domain portal thường join qua
    m2o/o2m (picking_ids, batch_id…) nên với 1500 user đây là phần đắt nhất của trang.
    Group-by chạy trên field đã index, gộp lại bằng Python.

    Args:
        groups: {tên chip: [giá trị field]} để gộp nhiều trạng thái vào 1 chip.
                None → mỗi giá trị field là một chip.
    Returns:
        dict {tên chip: số lượng} + total_key = tổng. Chip không có bản ghi vẫn trả 0.
    """
    Model = model if hasattr(model, '_read_group') else request.env[model]
    value_to_group = {v: g for g, values in (groups or {}).items() for v in values}
    counts = {total_key: 0}
    counts.update({g: 0 for g in (groups or {})})
    for value, count in Model._read_group(domain, groupby=[field], aggregates=['__count']):
        counts[total_key] += count
        if groups is None:
            counts[value] = counts.get(value, 0) + count
        else:
            group = value_to_group.get(value)
            if group:
                counts[group] += count
    return counts


# ---------------------------------------------------------------------------
# ACL check — accessible attachment for portal user
# ---------------------------------------------------------------------------

def check_attachment_access(att_id, allowed_models=None):
    """Attachment thuộc record của cửa hàng đang chọn.

    Returns:
        ir.attachment sudo recordset (browsed) nếu OK.

    Raises:
        Forbidden nếu không có quyền.
    """
    Attachment = request.env['ir.attachment'].sudo()
    att = Attachment.browse(int(att_id)).exists()
    if not att:
        raise Forbidden()
    if allowed_models and att.res_model not in allowed_models:
        raise Forbidden()
    # Kiểm tra record gốc có thuộc franchise user có quyền không
    if not att.res_model or not att.res_id:
        raise Forbidden()
    Model = request.env.get(att.res_model)
    if Model is None:
        raise Forbidden()
    record = Model.sudo().browse(att.res_id).exists()
    if not record:
        raise Forbidden()
    from .portal import get_current_store_ids  # import trễ: portal.py đã import utils
    franchise_id = (
        getattr(record, 'franchise_id', False)
        and record.franchise_id.id
    )
    if franchise_id and franchise_id not in get_current_store_ids():
        raise Forbidden()
    return att


# ---------------------------------------------------------------------------
# Mobile dashboard sections — Sprint 16 (Figma mobile_dashboard 2474:2)
# ---------------------------------------------------------------------------
#
# Section "Đơn hàng gần đây" / "Giao hàng sắp tới" lặp trên 2-3 trang mobile
# (/portal/delivery, /portal/debt, /portal/support) → helper chung ở đây
# (cả 3 module đều depends wujia_portal_base). Field franchise_id (wujia_sale)
# và planned_departure (wujia_delivery) KHÔNG thuộc dependency của base →
# guard theo _fields, thiếu module thì trả rỗng thay vì crash.
#
# Label map MOBILE — UI-only, TÁCH map desktop (precedent MOBILE_STATE_BADGES
# Sprint 13). Nhãn theo Figma; nguồn state thật, chỉ nhãn là mobile-riêng.
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# StatusBadge CMP-SB-001 — NGUỒN DUY NHẤT của variant badge trạng thái
# ---------------------------------------------------------------------------
#
# Map NHÃN → variant; PC và mobile dùng chung một class cho cùng trạng thái.
#
# BA giao mapping cho Dev ("Dev cần lập mapping theo trạng thái thực tế từng
# module", ô RỦI RO của spec). Nhãn nào BA đã nêu thì theo ĐÚNG BA, kể cả khi
# "Sắp giao" và "Đang giao" cùng ra processing trên /portal/delivery — BA cho
# phép phân biệt bằng CHỮ ("không truyền đạt trạng thái chỉ bằng màu").

STATUS_BADGE_BASE = 'wj-status-badge'
STATUS_BADGE_VARIANTS = ('neutral', 'info', 'pending', 'processing',
                         'success', 'danger', 'feedback')

# Nhãn hiển thị → variant (J-V2). Khoá map = câu gốc TIẾNG ANH ⇒ màu không đổi theo ngôn ngữ người xem;
# câu tiếng Việt nằm ở i18n/vi_VN.po. Viết `_lt('...')` literal (không sinh từ biến) để nhãn vào .pot.
_STATUS_TERMS_BY_VARIANT = {
    # neutral — chưa bắt đầu / đã khép, không cần chú ý
    'neutral': [
        _lt('Draft'), _lt('Not started'), _lt('Closed'), _lt('Read'), _lt('No longer valid'),
        _lt('Unpublished'), _lt('None yet'), _lt('Not applicable'),
    ],
    # info — mới / đã xác nhận (BA khoá: "Đã xác nhận" phải info)
    'info': [
        _lt('New'), _lt('Confirmed'), _lt('Registered'), _lt('Unread'), _lt('Slots available'),
        _lt('Credit balance'), _lt('Credit note'),
    ],
    # pending — đang chờ một bên khác
    'pending': [
        _lt('Awaiting confirmation'), _lt('Pending'), _lt('Not processed'), _lt('Submitted'),
        _lt('Awaiting approval'), _lt('Awaiting result'), _lt('No result yet'), _lt('Fully booked'),
        _lt('Unpaid'),
    ],
    # processing — đang chạy ("Chuẩn bị giao" là ví dụ BA ghi thẳng ở bậc này)
    'processing': [
        _lt('Preparing delivery'), _lt('Delivering soon'), _lt('Processing'), _lt('Delivering'),
        _lt('Under review'), _lt('Replacement ordered'), _lt('Partially compensated'), _lt('Viewing'),
        _lt('Partially paid'), _lt('Partial'),
    ],
    # success — xong
    'success': [
        _lt('Approved'), _lt('Delivered'), _lt('Delivery completed'), _lt('Finished'), _lt('Done'),
        _lt('Fully compensated'), _lt('Resolved'), _lt('Pass'), _lt('Enabled'), _lt('Published'),
        _lt('Result available'), _lt('Paid'),
    ],
    # danger — hỏng / dừng
    'danger': [
        _lt('Rejected'), _lt('Cancelled'), _lt('Trip cancelled'), _lt('Overdue'), _lt('Failed'),
        _lt('Has overdue'),
    ],
    # feedback — cần người dùng làm gì đó
    'feedback': [
        _lt('Replied'), _lt('Needs more info'), _lt('Awaiting reply'),
    ],
}
STATUS_VARIANT_BY_LABEL = {
    term._source: variant
    for variant, terms in _STATUS_TERMS_BY_VARIANT.items() for term in terms
}


def _status_label_key(label):
    """Khoá EN của một nhãn: `_lt()` ⇒ câu gốc; chuỗi khác giữ nguyên.

    Nhãn ĐÃ DỊCH (vi/th/zh) không tra được ⇒ neutral: caller phải truyền `_lt` (★J-VR bỏ nhánh tra ngược vi_VN.po).
    """
    if isinstance(label, LazyGettext):
        return label._source
    return label


def status_badge(variant):
    """'wj-status-badge--info' — variant lạ rơi về neutral, không bao giờ ra rỗng."""
    if variant not in STATUS_BADGE_VARIANTS:
        variant = 'neutral'
    return '%s--%s' % (STATUS_BADGE_BASE, variant)


def status_badge_for(label, default='neutral'):
    """Class modifier theo NHÃN hiển thị — dùng khi màn chưa có key ngữ nghĩa.

    Nhận `_lt()` hoặc câu gốc EN — KHÔNG nhận nhãn đã dịch (màu phải giống nhau ở mọi ngôn ngữ).
    """
    return status_badge(STATUS_VARIANT_BY_LABEL.get(_status_label_key(label), default))


# ---------------------------------------------------------------------------
# Trạng thái SO trên cổng — NGUỒN DUY NHẤT cho Home (PC + mobile), Lịch sử đặt hàng
# và màn kết quả gửi đơn. WJ-HOME-010: Home từng có bảng riêng (draft → "Nháp") nên
# cùng một đơn hiện hai tên khác nhau. Dời từ wujia_portal_purchase_history về đây vì
# portal_base không được import ngược lên module phụ thuộc nó.
# ---------------------------------------------------------------------------

# state → (label `_lt`, status_type). status_type = key ngữ nghĩa, template map sang badge CSS
# riêng (PC/mobile). WJ-PH-003 (BA 01/10): Lịch sử tra cứu được đơn huỷ ⇒ có 'cancel';
# Home vẫn lọc bỏ đơn huỷ bằng domain riêng.
# State custom thêm về sau rơi về DEFAULT_STATE_META (BA: nhãn an toàn "Đang xử lý").
SALE_STATE_META = {
    'draft': (_lt('Awaiting confirmation'), 'pending'),
    'sent': (_lt('Submitted'), 'sent'),
    'sale': (_lt('Confirmed'), 'confirmed'),
    'cancel': (_lt('Cancelled'), 'cancelled'),
}
DEFAULT_STATE_META = (_lt('Processing'), 'pending')

# WJ-PH-003 — phương án (a) chủ dự án chốt 03/08: cửa hàng chỉ nhìn MỘT cột trạng thái.
# sale.order.state của Odoo 19 chỉ có draft/sent/sale/cancel; "Đang giao"/"Hoàn tất" suy từ
# batch_id.delivery_batch_status và ĐÈ trạng thái đơn khi đơn đã xác nhận.
DELIVERY_OVERRIDE_META = {
    'delivering': (_lt('Delivering'), 'transit'),
    'done': (_lt('Finished'), 'done'),
}
# Trạng thái chuyến KHÔNG đè nhãn đơn (chuyến huỷ/chưa đi không làm đơn đổi trạng thái).
# False = batch cũ chưa có delivery_batch_status — vẫn phải nằm trong nhóm "Đã xác nhận".
DELIVERY_NEUTRAL_STATUSES = ['draft', 'assigned', 'loading', 'cancelled', False]


def portal_order_state_meta(state):
    """(label, status_type) — label đã dịch theo ngôn ngữ request."""
    label, status_type = SALE_STATE_META.get(state, DEFAULT_STATE_META)
    return str(label), status_type


def portal_order_state_badge(state):
    """Class badge theo state SO — tính từ `_lt`, không từ nhãn đã dịch của portal_order_state_meta."""
    return status_badge_for(SALE_STATE_META.get(state, DEFAULT_STATE_META)[0])


def _portal_order_meta(order):
    """(label `_lt`, status_type) — trạng thái giao đè trạng thái đơn khi đơn đã xác nhận.

    delivery_batch_status thuộc wujia_delivery (portal_base không depend) → guard _fields.
    """
    if order.state == 'sale':
        batch = order.batch_id
        if batch and 'delivery_batch_status' in batch._fields:
            override = DELIVERY_OVERRIDE_META.get(batch.delivery_batch_status)
            if override:
                return override
    return SALE_STATE_META.get(order.state, DEFAULT_STATE_META)


def _tr(env, label):
    """Nhãn `_lt` → chuỗi theo ngôn ngữ của env (record của request mang ngôn ngữ user); chuỗi thường giữ nguyên."""
    return env._(label) if isinstance(label, LazyGettext) else label


def portal_order_status(order):
    """(label đã dịch, status_type) hiển thị."""
    label, status_type = _portal_order_meta(order)
    return _tr(order.env, label), status_type


def portal_order_badge(order):
    """(label, class badge) cho template — màu theo NHÃN, cùng cách Lịch sử tô badge."""
    label = _portal_order_meta(order)[0]
    return _tr(order.env, label), status_badge_for(label)

# CMP-SB-001: cả hai bậc giao hàng đều là processing theo ví dụ BA.
MOBILE_BATCH_BADGES = {
    'draft':      (_lt('Preparing delivery'), status_badge('processing')),
    'assigned':   (_lt('Preparing delivery'), status_badge('processing')),
    'loading':    (_lt('Preparing delivery'), status_badge('processing')),
    'delivering': (_lt('Delivering'), status_badge('processing')),
    'done':       (_lt('Delivery completed'), status_badge('success')),
    'cancelled':  (_lt('Trip cancelled'), status_badge('danger')),
}


def mobile_batch_badge(status):
    """(nhãn đã dịch, class badge) của chuyến giao; trạng thái lạ ⇒ "Chuẩn bị giao"."""
    label, cls = MOBILE_BATCH_BADGES.get(status, MOBILE_BATCH_BADGES['draft'])
    return str(label), cls

# Nhãn trạng thái đổi trả — MỘT nguồn cho Home (PC + mobile) và /portal/return (badge + bộ lọc).
# Khoá = `wujia.return.request._portal_status_key()`; một bảng cho cả PC và mobile.
# Dict literal, không dùng tuple ('key', _lt(...)): extractor .pot lấy nhầm khoá thành msgid.
_RETURN_STATUS_TERMS = {
    'draft': _lt('Draft'),
    'submitted': _lt('Submitted'),
    'processing': _lt('Processing'),
    'approved': _lt('Approved'),
    'partial': _lt('Partially compensated'),
    'done': _lt('Finished'),
    'rejected': _lt('Rejected'),
    'cancelled': _lt('Cancelled'),
}
RETURN_STATUS_LABELS = {k: (v, status_badge_for(v)) for k, v in _RETURN_STATUS_TERMS.items()}


def return_status_label(rr):
    """(nhãn, class badge) của một yêu cầu đổi trả."""
    key = rr._portal_status_key() if hasattr(rr, '_portal_status_key') else rr.state
    label, cls = RETURN_STATUS_LABELS.get(key, (key, status_badge('neutral')))
    return _tr(rr.env, label), cls


VI_WEEKDAYS = {0: _lt('Mon'), 1: _lt('Tue'), 2: _lt('Wed'), 3: _lt('Thu'),
               4: _lt('Fri'), 5: _lt('Sat'), 6: _lt('Sun')}


def format_batch_departure(dt, tz=None):
    """'29/05/2026 (Thứ 5) · 08:00' — format ngày giờ batch theo Figma 2474:183."""
    dt = to_local_dt(dt, tz or portal_tz())
    if not dt:
        return '—'
    return '%s (%s) · %s' % (
        dt.strftime('%d/%m/%Y'), str(VI_WEEKDAYS[dt.weekday()]), dt.strftime('%H:%M'),
    )


# --- Batch giao hàng: scope franchise + giờ xuất phát (cụm C5) --------------
# Home và /portal/delivery phải cùng một tập dữ liệu và cùng một quy tắc giờ,
# nên domain/filter/mapping giờ nằm ở đây thay vì chép lại mỗi controller.

UNFINISHED_BATCH_STATUS = ('draft', 'assigned', 'loading', 'delivering')
UNDELIVERED_PICKING_STATE = ('draft', 'waiting', 'confirmed', 'assigned')

DEPARTURE_LABEL_ACTUAL = _lt('Departure (actual)')
DEPARTURE_LABEL_PLANNED = _lt('Departure (planned)')


def batch_franchise_domain(franchise_ids):
    """Batch có picking thuộc franchise — qua picking hoặc qua SO của picking."""
    ids = list(franchise_ids)
    return ['|', ('picking_ids.franchise_id', 'in', ids),
                 ('picking_ids.sale_id.franchise_id', 'in', ids)]


def own_pickings(batch, franchise_ids):
    """Picking của franchise trong batch (batch có thể gom nhiều cửa hàng)."""
    ids = set(franchise_ids)
    return batch.picking_ids.filtered(
        lambda p: (p.franchise_id and p.franchise_id.id in ids)
        or (p.sale_id and p.sale_id.franchise_id and p.sale_id.franchise_id.id in ids)
    )


def departure_value(batch):
    """(datetime, is_actual) — đã xuất phát thì lấy giờ thực tế, chưa thì giờ dự kiến.

    WJ-DELIVERY-007: chỗ DUY NHẤT quyết định portal hiện giờ nào.
    """
    actual = batch.actual_departure if 'actual_departure' in batch._fields else False
    return (actual, True) if actual else (batch.planned_departure, False)


def departure_label(is_actual):
    return str(DEPARTURE_LABEL_ACTUAL if is_actual else DEPARTURE_LABEL_PLANNED)


def format_order_names(names, keep=2):
    """'S00035, S00036 +3' — danh sách mã đơn rút gọn."""
    names = [n for n in names if n]
    if not names:
        return '—'
    text = ', '.join(names[:keep])
    if len(names) > keep:
        text += ' +%d' % (len(names) - keep)
    return text


def get_upcoming_batches(franchise_ids, limit=2):
    """Section "Giao hàng sắp tới" — chỉ chuyến CHƯA hoàn thành của franchise.

    Returns: {'items': [{batch, when, when_label, order_count, order_names, total,
    badge}], 'undelivered_count': tổng đơn chưa giao trên MỌI chuyến chưa xong}.
    """
    Batch = request.env['stock.picking.batch'].sudo()
    if 'planned_departure' not in Batch._fields or not franchise_ids:
        return {'items': [], 'undelivered_count': 0}
    franchise_ids = list(franchise_ids)
    tz = portal_tz()
    # "Từ đầu hôm nay" là mốc giờ địa phương, planned_departure lưu UTC → phải quy đổi.
    start, _unused = local_day_range_utc(date.today(), None, tz)
    batches = Batch.search(
        batch_franchise_domain(franchise_ids) + [
            ('delivery_batch_status', 'in', list(UNFINISHED_BATCH_STATUS)),
            # Chuyến đang bốc/đang chạy, hoặc chưa đặt lịch, vẫn là "chưa giao" dù
            # lịch đã qua hoặc còn trống (WJ-DELIVERY-005). PG xếp NULL cuối ở ASC.
            '|', '|', ('planned_departure', '>=', start),
                      ('planned_departure', '=', False),
                      ('delivery_batch_status', 'in', ['loading', 'delivering']),
        ], order='planned_departure asc', limit=limit)
    items = []
    for batch in batches:
        own = own_pickings(batch, franchise_ids).filtered(
            lambda p: p.state in UNDELIVERED_PICKING_STATE)
        orders = own.mapped('sale_id')
        dep, is_actual = departure_value(batch)
        items.append({
            'batch': batch,
            'when': format_batch_departure(dep, tz),
            'when_label': departure_label(is_actual),
            'order_count': len(orders),
            'order_names': format_order_names(orders.mapped('name')),
            'total': sum(orders.mapped('amount_total')),
            'badge': mobile_batch_badge(batch.delivery_batch_status),
        })
    return {'items': items, 'undelivered_count': count_undelivered_orders(franchise_ids)}


def count_undelivered_orders(franchise_ids):
    """Số đơn (sale.order) chưa giao của franchise trên mọi chuyến chưa hoàn thành.

    1 `_read_group` group-by sale_id — không lặp theo batch (1500 user).
    """
    Picking = request.env['stock.picking'].sudo()
    if not franchise_ids or 'franchise_id' not in Picking._fields:
        return 0
    ids = list(franchise_ids)
    groups = Picking._read_group([
        ('batch_id.delivery_batch_status', 'in', list(UNFINISHED_BATCH_STATUS)),
        ('state', 'in', list(UNDELIVERED_PICKING_STATE)),
        ('sale_id', '!=', False),
        '|', ('franchise_id', 'in', ids), ('sale_id.franchise_id', 'in', ids),
    ], groupby=['sale_id'])
    return len(groups)


# ---------------------------------------------------------------------------
# Tiền tệ & thuế portal — cụm D (WJ-ORD-024 / WJ-ORD-025 / WJ-PH-005)
# ---------------------------------------------------------------------------
#
# Trước sprint này portal tự nhân tay `unit × qty` để ra tiền, còn ký hiệu tiền
# thì nối chuỗi ' đ' cứng trong template → giỏ hiện 48.000 đ, gửi xong SO ra
# 55.200 (thuế 15%), History lại ra 55.200 $. Ba chỗ, ba con số, một gốc.
#
# 3 hàm dưới là chỗ DUY NHẤT mọi module portal_* nên dùng để ra tiền hiển thị.
# Công thức BA chốt 30/07:
#     discounted_unit = price_unit × (1 − discount/100)
#     compute_all(discounted_unit, currency, quantity=1, product, partner)
#     line_total = price_total ; order_total = amount_total
# KHÔNG tạo field lưu mới — đây là số controller tính tại chỗ.
#
# Perf 1500 user: compute_all tính trong RAM, không query. Recordset product /
# partner do caller browse sẵn (batch) → helper không thêm round-trip DB nào.
# ---------------------------------------------------------------------------


def _money_env(*records):
    """env dùng cho tính tiền. Ưu tiên env của record đang xử lý; không có thì
    `request.env`. Nhờ vậy helper chạy được cả ngoài HTTP (test, cron, backend)."""
    for rec in records:
        if rec is not None and getattr(rec, 'env', None) is not None:
            return rec.env
    return request.env


class portal_tax_mapper:  # noqa: N801 — dùng như factory hàm, không phải class API
    """Giải bộ thuế của sản phẩm ĐÚNG như sale.order.line sẽ làm — mirror `_compute_tax_id`.

    Lọc theo company (đi ngược cây company) rồi map qua fiscal position của partner.
    Sai một trong hai bước là giỏ lại lệch với SO — đúng cái bug đang sửa.

    Dựng MỘT lần cho cả giỏ/cả trang rồi gọi cho từng dòng: fiscal position resolve
    1 lần, `map_tax` cache theo bộ thuế gốc (y như dict `cached_taxes` của Odoo).
    Giỏ 30 dòng vì thế vẫn là 1 query, không phải 30 — quan trọng ở mức 1500 user.
    """

    def __init__(self, partner=None, company=None):
        self._env = _money_env(partner, company)
        self._company = company or self._env.company
        self._partner = partner or None
        self._fpos = None
        self._cache = {}

    def _fiscal_position(self):
        if self._fpos is None:
            self._fpos = self._env['account.fiscal.position'].sudo().with_company(
                self._company
            )._get_fiscal_position(self._partner) if self._partner else False
        return self._fpos

    def __call__(self, product):
        if not product:
            return self._env['account.tax'].browse()
        key = tuple(product.taxes_id.ids)
        if key not in self._cache:
            taxes = product.taxes_id._filter_taxes_by_company(self._company)
            fpos = self._fiscal_position()
            self._cache[key] = fpos.map_tax(taxes) if (taxes and fpos) else taxes
        return self._cache[key]


def portal_product_taxes(product, partner=None, company=None):
    """Bộ thuế của 1 sản phẩm — dùng cho chỗ chỉ có đúng một dòng.

    Nhiều dòng thì dựng `portal_tax_mapper` một lần rồi gọi lại, đừng gọi hàm này
    trong vòng lặp (mỗi lần gọi là một lần resolve fiscal position)."""
    return portal_tax_mapper(partner, company)(product)


def _compute_at(taxes, price_unit, discount, currency, qty, product, partner, company):
    """Tiền của `qty` đơn vị — đi ĐÚNG pipeline mà `sale.order.line._compute_amount` đi.

    KHÔNG dùng `compute_all`: nó làm tròn theo dòng, trong khi công ty đặt
    `tax_calculation_rounding_method = round_globally` thì Odoo tính bằng
    `_add_tax_details_in_base_line` + `_round_base_lines_tax_details`. Hai đường lệch
    nhau 1 xu (giá 3,33 · giảm 33% · qty 3 · 7,5% → 7,20 vs 7,19) — mà lệch 1 xu
    giữa giỏ và đơn thì đúng bằng lỗi WJ-ORD-024 đang phải sửa.
    Đi chung pipeline ⇒ khớp ở CẢ hai chế độ làm tròn, không phải chỉnh tay.
    """
    if not qty:
        return {'price_excluded': 0.0, 'price_included': 0.0, 'tax_amount': 0.0}
    env = _money_env(product, partner, taxes) or company.env
    AccountTax = env['account.tax']
    base_line = AccountTax._prepare_base_line_for_taxes_computation(
        None,
        product_id=product or env['product.product'],
        tax_ids=taxes or AccountTax.browse(),
        price_unit=price_unit or 0.0,
        quantity=qty,
        discount=discount or 0.0,
        partner_id=partner or env['res.partner'],
        currency_id=currency,
    )
    AccountTax._add_tax_details_in_base_line(base_line, company)
    AccountTax._round_base_lines_tax_details([base_line], company)
    details = base_line['tax_details']
    excluded = details['total_excluded_currency']
    included = details['total_included_currency']
    return {
        'price_excluded': excluded,
        'price_included': included,
        'tax_amount': included - excluded,
    }


def portal_line_price_vals(product, price_unit, qty, currency, partner=None,
                           discount=0.0, company=None, taxes=None):
    """5 con số của 1 dòng hàng — dùng chung giỏ (cart.line) lẫn lịch sử (SO line).

    HAI phép tính TÁCH BIỆT, đúng như BA chốt 30/07 — và đây là chỗ dễ sai nhất:

    - đơn giá HIỂN THỊ  = compute_all(1 đơn vị)   → con số in ra cho người đọc
    - thành tiền DÒNG   = compute_all(qty đơn vị) → đúng bằng `price_total` của Odoo

    KHÔNG được lấy đơn giá đã làm tròn rồi nhân qty: ở giá 3,33 · giảm 33% · qty 3 ·
    thuế 7,5%, nhân ra 7,20 trong khi đơn thật 7,19 — lệch 1 xu, và lệch 1 xu ở màn
    tiền là đúng cái lỗi WJ-ORD-024 đang sửa. Cũng KHÔNG được chia ngược lại.
    """
    company = company or _money_env(product, partner).company
    currency = currency or company.currency_id
    qty = qty or 0.0
    if taxes is None:
        taxes = portal_product_taxes(product, partner, company)
    unit = _compute_at(taxes, price_unit, discount, currency, 1.0,
                       product, partner, company)
    line = _compute_at(taxes, price_unit, discount, currency, qty,
                       product, partner, company)
    return {
        'unit_price': currency.round(unit['price_excluded']),
        'unit_price_tax_included': currency.round(unit['price_included']),
        'line_total': currency.round(line['price_excluded']),
        'line_total_tax_included': currency.round(line['price_included']),
        'tax_amount': currency.round(line['tax_amount']),
    }


def portal_money(amount, symbol=None, decimals=0):
    """'48.000 đ' — một chỗ duy nhất format tiền cho mọi module portal.

    VND (decimals=0) giữ NGUYÊN format cũ, không đổi một pixel: nhóm nghìn bằng
    dấu chấm. Currency có phần lẻ thì `decimals` = `currency.decimal_places` —
    BA chốt "ký hiệu VÀ rounding theo currency của đơn", nên USD 10,99 phải ra
    '10,99 $' chứ không phải '11 $'.
    """
    decimals = int(decimals or 0)
    text = '{:,.{d}f}'.format(amount or 0, d=decimals)
    if decimals:
        # en_US '10,990.99' → vi '10.990,99': đổi tạm dấu để không giẫm lên nhau.
        text = text.replace(',', '\x00').replace('.', ',').replace('\x00', '.')
    else:
        text = text.replace(',', '.')
    return f'{text} {symbol}' if symbol else text
