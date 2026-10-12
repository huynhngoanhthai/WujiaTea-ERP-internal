import functools
import logging
import time
from urllib.parse import urlencode, urlsplit

from werkzeug.exceptions import TooManyRequests

from odoo import _
from odoo.http import request
from odoo.tools.translate import LazyTranslate

_logger = logging.getLogger(__name__)
_lt = LazyTranslate(__name__)


def safe_local_path(url, host=None, default='/portal'):
    """Chỉ trả path nội bộ (chặn open redirect: //host, \\host, scheme lạ)."""
    url = (url or '').strip()
    if not url or '\\' in url or any(ord(c) < 32 for c in url):
        return default
    parts = urlsplit(url)
    if parts.scheme or parts.netloc:
        if parts.scheme not in ('http', 'https') or not host or parts.netloc != host:
            return default
    path = parts.path
    if not path.startswith('/') or path.startswith('//'):
        return default
    return path + ('?' + parts.query if parts.query else '')


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
# Pager (CMP-PGNT-001)
# ---------------------------------------------------------------------------

ELLIPSIS = '…'


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
