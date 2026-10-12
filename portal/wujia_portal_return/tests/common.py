"""Tiện ích test dùng chung của portal đổi trả."""
from odoo.addons.wujia_return.tests.common import load_vi as _load_vi

# Khung + Home + nghiệp vụ + màn: test portal assert chữ của cả 4 .po.
RETURN_PORTAL_MODULES = ('wujia_portal_layout', 'wujia_portal_base', 'wujia_return', 'wujia_portal_return')


def load_vi(env, modules=RETURN_PORTAL_MODULES):
    """Bật vi_VN + nạp .po của `modules`; trả env `lang=vi_VN` (J-V6)."""
    return _load_vi(env, modules)
