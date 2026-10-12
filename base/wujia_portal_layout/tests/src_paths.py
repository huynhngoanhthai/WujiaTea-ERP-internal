"""Đường dẫn source cho các test quét file.

Module nằm ở nhiều thư mục addons (ADR-028), nên không ghép đường dẫn từ thư mục cha
của module đang chạy: hỏi Odoo module nằm ở đâu.
"""
import os

from odoo.modules.module import get_module_path, get_modules

PREFIX = 'wujia_'


def src(*parts):
    """src('wujia_portal_sale', 'views', 'x.xml') hoặc src('wujia_portal_sale/views/x.xml')."""
    parts = [p for part in parts for p in part.split('/')]
    return os.path.join(get_module_path(parts[0]), *parts[1:])


def src_modules():
    """Tên mọi module Wujia của repo này, đã sắp (bỏ module trùng tiền tố ở addons_path ngoài repo)."""
    repo = os.path.dirname(os.path.dirname(get_module_path('wujia_portal_layout'))) + os.sep
    return sorted(m for m in get_modules()
                  if m.startswith(PREFIX) and get_module_path(m).startswith(repo))


def src_walk():
    """os.walk qua mọi module Wujia."""
    for mod in src_modules():
        yield from os.walk(get_module_path(mod))


def src_rel(path):
    """'<module>/<đường dẫn trong module>' của một file hoặc thư mục source."""
    path = os.path.abspath(path)
    root = path if os.path.isdir(path) else os.path.dirname(path)
    while not os.path.isfile(os.path.join(root, '__manifest__.py')):
        parent = os.path.dirname(root)
        if parent == root:
            raise ValueError('%s không nằm trong module nào' % path)
        root = parent
    return os.path.relpath(path, os.path.dirname(root))
