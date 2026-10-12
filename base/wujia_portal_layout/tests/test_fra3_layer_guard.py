"""FR-A3 — khung kênh không được ngã khi nghiệp vụ tắt (ADR-027 R2).

`wujia_portal_layout` chỉ depend `base/web/auth_signup/http_routing`, nhưng ACL ảnh
đại diện gọi `res.users._get_accessible_franchise_ids()` — method của
`wujia_franchise`. Cài khung một mình rồi mở ảnh của người khác là `AttributeError`
→ 500. Guard phải cho ra 403 (đóng), không phải lỗi máy chủ.
"""

from unittest.mock import patch

from odoo.tests import tagged
from odoo.tests.common import HttpCase


class _Absent:
    """Method KHÔNG tồn tại: mọi truy cập đều trượt như module chưa cài."""

    def __get__(self, obj, owner=None):
        raise AttributeError('method của module nghiệp vụ chưa nạp')


@tagged('post_install', '-at_install', 'wujia_fra3')
class TestAvatarAclWithoutFranchise(HttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        portal = cls.env.ref('base.group_portal').id
        cls.me = cls.env['res.users'].create({
            'name': 'fra3_me', 'login': 'fra3_me', 'password': 'fra3_me',
            'group_ids': [(6, 0, [portal])]})
        cls.other = cls.env['res.users'].create({
            'name': 'fra3_other', 'login': 'fra3_other', 'password': 'fra3_other',
            'group_ids': [(6, 0, [portal])]})

    def test_avatar_of_other_user_is_forbidden_not_500(self):
        """Nghiệp vụ tắt ⇒ đóng (403), tuyệt đối không 500."""
        Users = type(self.env['res.users'])
        self.authenticate('fra3_me', 'fra3_me')
        with patch.object(Users, '_get_accessible_franchise_ids', _Absent(), create=True):
            res = self.url_open(f'/portal/profile/avatar/{self.other.id}', timeout=30)
        self.assertEqual(
            res.status_code, 403,
            'ACL ảnh phải đóng khi module nghiệp vụ tắt — xem guard getattr trong '
            'portal_profile_avatar')
