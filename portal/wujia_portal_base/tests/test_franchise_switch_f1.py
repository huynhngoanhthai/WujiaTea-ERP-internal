"""F1 — đổi cửa hàng không được redirect ra ngoài site."""
from urllib.parse import urlsplit

from odoo import http
from odoo.tests import tagged
from odoo.tests.common import HttpCase


@tagged('post_install', '-at_install', 'wujia_f1')
class TestFranchiseSwitchF1(HttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        cls.franchise = env['wujia.franchise.management'].create({
            'code': 'F1SW', 'name': 'F1 switch store', 'franchise_end_date': '2030-01-01',
            'partner_id': env['res.partner'].create({'name': 'F1 sw partner'}).id})
        cls.user = env['res.users'].create({
            'name': 'f1 sw', 'login': 'f1.sw', 'password': 'f1.sw',
            'group_ids': [(6, 0, [env.ref('base.group_portal').id])]})
        env['wujia.franchise.member'].create({
            'user_id': cls.user.id, 'franchise_id': cls.franchise.id, 'role': 'owner'})

    def _switch(self, redirect):
        self.authenticate('f1.sw', 'f1.sw')
        res = self.url_open('/portal/franchise/switch', data={
            'franchise_id': self.franchise.id, 'redirect': redirect,
            'csrf_token': http.Request.csrf_token(self)}, allow_redirects=False)
        loc = urlsplit(res.headers['Location'])
        return loc

    def test_external_targets_fall_back_to_portal(self):
        for bad in ('//evil.com/x', '\\\\evil.com', '/\\evil.com', 'https://evil.com/portal',
                    'javascript:alert(1)'):
            loc = self._switch(bad)
            self.assertNotIn('evil', loc.netloc + loc.path, bad)
            self.assertEqual(loc.path, '/portal', bad)

    def test_internal_target_kept(self):
        loc = self._switch('/portal/order?x=1')
        self.assertEqual((loc.path, loc.query), ('/portal/order', 'x=1'))
