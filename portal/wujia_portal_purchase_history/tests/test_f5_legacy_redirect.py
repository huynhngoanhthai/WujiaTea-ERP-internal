"""F5a — 301 từ slug v14 cũ, dời từ `wujia_portal_layout` về module sở hữu route đích.

Giữ nguyên mã 301 (vĩnh viễn) vì ~1500 người dùng còn bookmark/email HQ trỏ slug cũ.
"""
from urllib.parse import urlsplit

from odoo.tests import tagged
from odoo.tests.common import HttpCase


@tagged('post_install', '-at_install', 'wujia_f5')
class TestLegacyRedirectPurchaseHistory(HttpCase):

    def test_legacy_slug_redirects_permanently(self):
        res = self.url_open('/portal/purchase_history', allow_redirects=False)
        self.assertEqual(res.status_code, 301)
        self.assertEqual(urlsplit(res.headers['Location']).path, '/portal/purchase-history')
