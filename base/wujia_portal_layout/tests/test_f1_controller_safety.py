"""F1 — set_lang chỉ quay về trang nội bộ; lỗi hồ sơ trong query string được encode."""
from unittest.mock import patch
from urllib.parse import urlsplit

from odoo import http
from odoo.exceptions import ValidationError
from odoo.tests import tagged
from odoo.tests.common import HttpCase

from odoo.addons.wujia_portal_layout.controllers.utils import safe_local_path


@tagged('post_install', '-at_install', 'wujia_f1')
class TestLayoutSafetyF1(HttpCase):

    def test_safe_local_path(self):
        host = 'erp.local:8069'
        for bad in ('//evil.com', '\\\\evil.com', '/\\evil.com', 'https://evil.com/a',
                    'javascript:alert(1)', 'portal', '', None, '/a\nb'):
            self.assertEqual(safe_local_path(bad, host=host), '/portal', bad)
        self.assertEqual(safe_local_path('http://erp.local:8069//evil.com/a', host=host), '/portal')
        self.assertEqual(safe_local_path('/portal/order?x=1'), '/portal/order?x=1')
        self.assertEqual(safe_local_path('http://erp.local:8069/portal/debt?w=2', host=host),
                         '/portal/debt?w=2')

    def test_set_lang_ignores_foreign_referrer(self):
        res = self.url_open('/portal/set-lang/en_US', allow_redirects=False,
                            headers={'Referer': 'http://evil.com/portal/order'})
        self.assertEqual(urlsplit(res.headers['Location']).path, '/portal')

    def test_profile_error_is_url_encoded(self):
        user = self.env['res.users'].create({
            'name': 'f1 prof', 'login': 'f1.prof', 'password': 'f1.prof',
            'group_ids': [(6, 0, [self.env.ref('base.group_portal').id])]})
        Partner = type(self.env['res.partner'])
        original = Partner.write

        def write(recs, vals):
            if vals.get('street') == 'F1BOOM':
                raise ValidationError('a&b#c')
            return original(recs, vals)

        self.authenticate('f1.prof', 'f1.prof')
        with patch.object(Partner, 'write', write):
            res = self.url_open('/portal/profile/update', data={
                'name': user.name, 'street': 'F1BOOM',
                'csrf_token': http.Request.csrf_token(self)}, allow_redirects=False)
        self.assertIn('error=a%26b%23c', res.headers['Location'])
