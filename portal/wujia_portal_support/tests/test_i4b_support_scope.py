"""Hỗ trợ: ticket của chính mình tại MỘT cửa hàng đang chọn — list, chi tiết, trả lời, tệp, submit.

Chạy: `--test-tags wujia_scope_i4b`.
"""
from odoo import http
from odoo.tests import tagged
from odoo.tests.common import HttpCase

from odoo.addons.wujia_portal_base.controllers.portal import ACTIVE_FRANCHISE_COOKIE
from odoo.addons.wujia_support.tests.test_support import SupportCommon

PROMPT_NEED_PICK = 'data-store-scope="need_pick"'


@tagged('post_install', '-at_install', 'wujia_scope_i4b')
class TestSupportStoreScope(SupportCommon, HttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._setup_support()
        cls.env['wujia.franchise.member'].create({
            'user_id': cls.owner.id, 'franchise_id': cls.other_franchise.id, 'role': 'owner'})
        cls.t_a = cls._ticket(title='I4B ticket A')
        cls.t_b = cls._ticket(title='I4B ticket B', franchise_id=cls.other_franchise.id)
        cls.f_a = cls._pdf('a.pdf', res_model=cls.t_a._name, res_id=cls.t_a.id)
        cls.f_b = cls._pdf('b.pdf', res_model=cls.t_b._name, res_id=cls.t_b.id)

    def _login(self, store=None):
        self.authenticate('f10.owner', 'f10.owner')
        if store is not None:
            self.opener.cookies.set(ACTIVE_FRANCHISE_COOKIE, str(store.id))

    def _open(self, url, store=None):
        self._login(store)
        return self.url_open(url, timeout=30, allow_redirects=False)

    def _post(self, url, store=None, **data):
        self._login(store)
        data['csrf_token'] = http.Request.csrf_token(self)
        return self.url_open(url, data=data, timeout=30, allow_redirects=False)

    def _assert_redirect_list(self, res):
        self.assertEqual(res.status_code, 303)
        self.assertTrue(res.headers['Location'].endswith('/portal/support'), res.headers['Location'])

    def test_not_selected_prompt_no_data(self):
        html = self._open('/portal/support').text
        self.assertIn(PROMPT_NEED_PICK, html)
        self.assertNotIn('I4B ticket', html)
        self._assert_redirect_list(self._open('/portal/support/%d' % self.t_a.id))
        self._assert_redirect_list(self._open('/portal/support/new'))
        self.assertEqual(self._open('/portal/support/%d/attachment/%d' % (self.t_a.id, self.f_a.id)).status_code, 404)

    def test_selected_a_only_a(self):
        html = self._open('/portal/support', self.franchise).text
        self.assertIn('I4B ticket A', html)
        self.assertNotIn('I4B ticket B', html)
        self.assertEqual(self._open('/portal/support/%d' % self.t_a.id, self.franchise).status_code, 200)
        self.assertEqual(self._open('/portal/support/%d/attachment/%d' % (self.t_a.id, self.f_a.id),
                                    self.franchise).status_code, 200)

    def test_switch_to_b_only_b(self):
        html = self._open('/portal/support', self.other_franchise).text
        self.assertIn('I4B ticket B', html)
        self.assertNotIn('I4B ticket A', html)

    def test_foreign_ids_blocked(self):
        self._assert_redirect_list(self._open('/portal/support/%d' % self.t_b.id, self.franchise))
        self._assert_redirect_list(self._post('/portal/support/%d/reply' % self.t_b.id, self.franchise,
                                              body='I4B chen ngang'))
        self.assertNotIn('I4B chen ngang', ''.join(self.t_b.message_ids.mapped('body')))
        self.assertEqual(self._open('/portal/support/%d/attachment/%d' % (self.t_b.id, self.f_b.id),
                                    self.franchise).status_code, 404)

    def test_submit_for_other_store_rejected(self):
        res = self._post('/portal/support/new', self.franchise, franchise_id=self.other_franchise.id,
                         category_id=self.cat.id, title='I4B gửi sang B', description='x')
        self.assertIn('error=invalid_franchise', res.headers['Location'])
        self.assertFalse(self.Ticket.search([('title', '=', 'I4B gửi sang B')]))
