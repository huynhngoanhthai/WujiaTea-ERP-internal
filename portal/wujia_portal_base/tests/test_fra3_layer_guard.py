"""FR-A3 — L3a không được ngã khi module L3b tắt (ADR-027 R5).

`wujia_portal_base` gọi `_is_within_order_window` của `wujia_order_window`
mà KHÔNG (và không được) depend nó. Phép đo "cài `portal_base` một mình" của FR-A3
cho 5 lần `500 != 200` ở Home đúng vì chỗ này — `check_layers` chỉ đọc manifest nên
không thấy call chéo tầng lúc chạy.

Giả lập module tắt bằng descriptor ném `AttributeError`: `hasattr` trượt y như khi
method chưa từng được nạp vào registry.
"""

from unittest.mock import patch

from odoo.tests import tagged
from odoo.tests.common import HttpCase


class _Absent:
    """Method KHÔNG tồn tại: mọi truy cập đều trượt như module chưa cài."""

    def __get__(self, obj, owner=None):
        raise AttributeError('method của module khung giờ chưa nạp')


@tagged('post_install', '-at_install', 'wujia_fra3')
class TestHomeWithoutOrderWindow(HttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        cls.franchise = env['wujia.franchise.management'].create({
            'code': 'A3OW', 'name': 'FRA3 store', 'franchise_end_date': '2030-01-01',
            'partner_id': env['res.partner'].create({'name': 'FRA3 partner'}).id})
        cls.user = env['res.users'].create({
            'name': 'fra3_ow', 'login': 'fra3_ow', 'password': 'fra3_ow',
            'group_ids': [(6, 0, [env.ref('base.group_portal').id])]})
        env['wujia.franchise.member'].create({
            'user_id': cls.user.id, 'franchise_id': cls.franchise.id, 'role': 'owner'})

    def test_home_renders_when_order_window_module_absent(self):
        """Home vẫn 200 (khung giờ coi như tắt), không 500."""
        Settings = type(self.env['res.config.settings'])
        self.authenticate('fra3_ow', 'fra3_ow')
        with patch.object(Settings, '_is_within_order_window', _Absent(), create=True):
            res = self.url_open('/portal', timeout=30)
        self.assertEqual(
            res.status_code, 200,
            'Home phải sống khi wujia_order_window tắt — xem guard hasattr '
            'trong _order_window_view')
