from urllib.parse import urlsplit


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
