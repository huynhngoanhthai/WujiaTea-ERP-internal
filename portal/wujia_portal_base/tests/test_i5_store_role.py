"""Quyền theo role tại cửa hàng đang chọn: Chủ ở A không cấp quyền ở B.

Chạy: `--test-tags wujia_role_i5`.
"""
from odoo import http
from odoo.tests import tagged
from odoo.tests.common import HttpCase

from odoo.addons.wujia_portal_base.controllers.portal import ACTIVE_FRANCHISE_COOKIE

NO_PERMISSION = 'wj-no-permission'


class I5Common(HttpCase):
    """`i5.mix` = Chủ tại A, Nhân viên tại B · `i5.mgr` = Quản lý tại A · `i5.peer` = Nhân viên tại A và B."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        Partner, Franchise = env['res.partner'], env['wujia.franchise.management']
        cls.store_a, cls.store_b = (Franchise.create({
            'code': code, 'name': 'I5 store %s' % code, 'franchise_end_date': '2030-01-01',
            'status': 'active',
            'partner_id': Partner.create({'name': 'I5 partner %s' % code}).id,
        }) for code in ('I5A', 'I5B'))
        portal = env.ref('base.group_portal').id

        def user(login, roles):
            u = env['res.users'].create({
                'name': login, 'login': login, 'password': login,
                'group_ids': [(6, 0, [portal])]})
            for store, role in roles:
                env['wujia.franchise.member'].create({
                    'user_id': u.id, 'franchise_id': store.id, 'role': role})
            return u
        cls.mix = user('i5.mix', [(cls.store_a, 'owner'), (cls.store_b, 'staff')])
        cls.mgr = user('i5.mgr', [(cls.store_a, 'manager')])
        cls.peer = user('i5.peer', [(cls.store_a, 'staff'), (cls.store_b, 'staff')])

    def _open(self, url, store, login='i5.mix', **kw):
        self.authenticate(login, login)
        self.opener.cookies.set(ACTIVE_FRANCHISE_COOKIE, str(store.id))
        return self.url_open(url, timeout=30, **kw)

    def _post(self, url, store, data, login='i5.mix'):
        self.authenticate(login, login)
        self.opener.cookies.set(ACTIVE_FRANCHISE_COOKIE, str(store.id))
        data = dict(data, csrf_token=http.Request.csrf_token(self))
        return self.url_open(url, data=data, timeout=30)


@tagged('post_install', '-at_install', 'wujia_role_i5')
class TestStoreRoleBase(I5Common):

    def test_home_debt_kpi_only_for_admin(self):
        html_a = self._open('/portal', self.store_a).text
        self.assertIn('wujia-home-kpi-debt', html_a)
        self.assertEqual(html_a.count('wujia-mhome-kpi-label'), 4)
        html_b = self._open('/portal', self.store_b).text
        self.assertNotIn('wujia-home-kpi-debt', html_b)
        self.assertNotIn('/portal/debt', html_b)
        self.assertEqual(html_b.count('wujia-mhome-kpi-label'), 3)
        self.assertIn('col-lg-4 col-12', html_b)

    def test_store_profile_members_only_for_admin(self):
        for login in ('i5.mix', 'i5.mgr'):
            res = self._open('/portal/franchise-information', self.store_a, login)
            self.assertEqual(res.status_code, 200)
            self.assertIn('i5.peer', res.text, login)
        res = self._open('/portal/franchise-information', self.store_b)
        self.assertEqual(res.status_code, 200)
        self.assertNotIn('i5.peer', res.text)
        self.assertNotIn('wj-pc-acct-members', res.text)

    def test_legacy_member_routes(self):
        for url in ('/portal/franchises/%s', '/my/franchises/%s'):
            self.assertIn('i5.peer', self._open(url % self.store_a.id, self.store_a).text)
            html_b = self._open(url % self.store_b.id, self.store_a).text
            self.assertNotIn('i5.peer', html_b)
            self.assertNotIn('o_wujia_franchise_members', html_b)

    def test_members_json(self):
        self.authenticate('i5.mix', 'i5.mix')
        ok = self.make_jsonrpc_request('/my/franchises/%s/members' % self.store_a.id, {})
        self.assertIn('i5.peer', [m['user_name'] for m in ok['members']])
        denied = self.make_jsonrpc_request('/my/franchises/%s/members' % self.store_b.id, {})
        self.assertEqual(denied, {'error': 'forbidden'})
