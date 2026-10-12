"""F5a — khung kênh KHÔNG được biết route của màn nghiệp vụ (ADR-027 R2/R6).

`scripts/qa/check_layers.py` quét source; test này quét ARCH ĐÃ NẠP trong DB, nên bắt
được cả trường hợp sửa view thẳng trên DB. Danh sách route "của khung" lấy từ chính
`@http.route` của module, không chép tay.
"""
import pathlib
import re

from odoo.modules.module import get_module_path
from odoo.tests import tagged
from odoo.tests.common import TransactionCase

ROUTE_RE = re.compile(r"/portal(?:/[A-Za-z0-9_\-]+)*")
OWN_RE = re.compile(r"@http\.route\(\s*\[?\s*(['\"])(/portal[^'\"]*)\1")


@tagged('post_install', '-at_install', 'wujia_f5')
class TestFrameKnowsNoWujiaRoute(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        root = pathlib.Path(get_module_path('wujia_portal_layout'))
        cls.own = {'/portal'}
        for py in sorted((root / 'controllers').glob('*.py')):
            for _q, route in OWN_RE.findall(py.read_text(encoding='utf-8')):
                cls.own.add(route.split('<')[0].rstrip('/') or '/portal')

    def _foreign_routes(self, arch):
        out = []
        for route in ROUTE_RE.findall(arch):
            route = route.rstrip('/')
            if route == '/portal' or route in self.own:
                continue
            if any(route.startswith(o + '/') for o in self.own if o != '/portal'):
                continue
            out.append(route)
        return sorted(set(out))

    def test_frame_views_have_no_wujia_routes(self):
        """Mọi view của wujia_portal_layout: không có route của module khác."""
        data = self.env['ir.model.data'].search([
            ('module', '=', 'wujia_portal_layout'), ('model', '=', 'ir.ui.view')])
        views = self.env['ir.ui.view'].browse(data.mapped('res_id')).exists()
        self.assertTrue(views, 'không tìm thấy view nào của khung — sai điều kiện lọc')
        bad = {}
        for view in views:
            foreign = self._foreign_routes(view.arch or '')
            if foreign:
                bad[view.key or view.name] = foreign
        self.assertFalse(bad, f'khung đang biết route Wujia: {bad}')

    def test_menu_shells_keep_only_frame_anchors(self):
        """3 khung menu chỉ còn neo + route của khung (không mục nghiệp vụ nào)."""
        for key in ('wujia_portal_layout.layout_sidenav',
                    'wujia_portal_layout.mobile_bottomnav',
                    'wujia_portal_layout.mobile_header'):
            view = self.env.ref(key)
            self.assertFalse(self._foreign_routes(view.arch or ''), key)

    def test_sidenav_shell_keeps_inheritance_anchors(self):
        """Neo cho module chèn mục: 3 tiêu đề nhóm (BA, E8b) + neo đáy phải có id ổn định."""
        arch = self.env.ref('wujia_portal_layout.layout_sidenav').arch
        for anchor in ('nav_header_main', 'nav_header_finance', 'nav_header_ops', 'nav_end',
                       'main-menu-navigation'):
            self.assertIn(f'id="{anchor}"', arch)
        # Nhóm "Tiện ích" + mục Tài khoản đã gỡ (Tài khoản ở avatar, E8c).
        for gone in ('nav_header_utils', 'nav_item_account', '/portal/profile'):
            self.assertNotIn(gone, arch)
