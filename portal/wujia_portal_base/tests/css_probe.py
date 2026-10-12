"""Helper đọc CSS/view của module khác — dùng chung cho các guard quét nhiều màn.

Tách ra từ `wujia_portal_layout/tests` ở F5b: khung không giữ công cụ soi màn nghiệp
vụ nữa, còn `portal_debt`/`portal_exam` thì import lại chỗ này thay vì chép ba bản.
"""
import os
import re

from lxml import etree

from odoo.addons.wujia_portal_layout.tests.src_paths import src, src_modules, src_rel, src_walk  # noqa: F401

CSS_DIR = src('wujia_portal_layout', 'static', 'assets', 'css')


def _css(name):
    with open(os.path.join(CSS_DIR, name), encoding='utf-8') as fh:
        return fh.read()


def _mod_css(module, name):
    with open(src(module, 'static', 'src', 'css', name), encoding='utf-8') as fh:
        return fh.read()


def _strip_comments(css):
    return re.sub(r'/\*.*?\*/', '', css, flags=re.S)


def _rule(css, selector):
    """Thân của rule ở TẦNG GỐC (ngoài mọi @media) — bẫy D4a: gộp @media vào là
    đọc ra số của bản mobile."""
    css = _strip_comments(css)
    depth, i, out = 0, 0, None
    while i < len(css):
        c = css[i]
        if c == '{':
            depth += 1
        elif c == '}':
            depth -= 1
        elif depth == 0 and css.startswith(selector, i):
            after = css[i + len(selector)]
            if after in ' ,{\n':
                j = css.index('{', i)
                if css[i:j].strip() == selector:
                    out = css[j + 1:css.index('}', j)]
                    break
        i += 1
    return out


def _rule_in_media(css, selector):
    """Thân của rule nằm TRONG @media. `_rule()` cố ý chỉ đọc tầng gốc (bẫy D4a)
    nên gọi thẳng cho mknow/mnoti trả None ⇒ guard chứng-minh-rỗng (D5e)."""
    css = _strip_comments(css)
    depth, i, out = 0, 0, None
    while i < len(css):
        c = css[i]
        if c == '{':
            depth += 1
        elif c == '}':
            depth -= 1
        elif depth == 1 and css.startswith(selector, i):
            after = css[i + len(selector)]
            if after in ' ,{\n':
                j = css.index('{', i)
                if css[i:j].strip() == selector:
                    out = css[j + 1:css.index('}', j)]
                    break
        i += 1
    return out


def _chu_the(selector_part):
    """Compound CUỐI của một selector — phần thực sự bị style. Bỏ pseudo-element
    (::before) vì đó là con sinh ra, không phải chính hàng."""
    if '::' in selector_part:
        return ''
    return re.split(r'[ >+~]+', selector_part.strip())[-1]


def _view(module, filename):
    """Đọc dạng BYTES: file view có khai báo encoding, lxml từ chối chuỗi unicode."""
    with open(src(module, 'views', filename), 'rb') as fh:
        return etree.fromstring(fh.read())
