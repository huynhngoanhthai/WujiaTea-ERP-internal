"""Yêu cầu cập nhật chỉ theo MỘT cửa hàng đang chọn: list, chi tiết, huỷ, AJAX giá trị, tệp, submit.

Chạy: `--test-tags wujia_scope_i4b`.
"""
import base64
import json
import re

from odoo import http
from odoo.tests import tagged
from odoo.tests.common import HttpCase

from odoo.addons.wujia_portal_base.controllers.portal import ACTIVE_FRANCHISE_COOKIE

PROMPT_NEED_PICK = 'data-store-scope="need_pick"'


@tagged('post_install', '-at_install', 'wujia_scope_i4b')
class TestInfoRequestStoreScope(HttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        Franchise, Partner = env['wujia.franchise.management'], env['res.partner']
        cls.store_a, cls.store_b = (Franchise.create({
            'code': code, 'name': 'I4b info %s' % code, 'franchise_end_date': '2030-01-01', 'phone': '0281',
            'partner_id': Partner.create({'name': 'I4b info partner %s' % code}).id}) for code in ('I4IA', 'I4IB'))
        cls.user = env['res.users'].create({
            'name': 'i4b_inf', 'login': 'i4b_inf', 'password': 'i4b_inf',
            'group_ids': [(6, 0, [env.ref('base.group_portal').id])]})
        for store in (cls.store_a, cls.store_b):
            env['wujia.franchise.member'].create({
                'user_id': cls.user.id, 'franchise_id': store.id, 'role': 'owner'})
        cls.Model = env['wujia.info.update.request']
        cls.rec_a, cls.rec_b = (cls.Model.create({
            'franchise_id': store.id, 'request_type': 'phone', 'new_value': '0909',
            'created_by_user_id': cls.user.id, 'state': 'submitted'}) for store in (cls.store_a, cls.store_b))
        cls.att_a, cls.att_b = (env['ir.attachment'].create({
            'name': 'i4b.pdf', 'res_model': rec._name, 'res_id': rec.id,
            'datas': base64.b64encode(b'%PDF i4b'), 'mimetype': 'application/pdf'}) for rec in (cls.rec_a, cls.rec_b))
        cls.rec_a.attachment_ids = [(4, cls.att_a.id)]
        cls.rec_b.attachment_ids = [(4, cls.att_b.id)]

    def _login(self, store=None):
        self.authenticate('i4b_inf', 'i4b_inf')
        if store is not None:
            self.opener.cookies.set(ACTIVE_FRANCHISE_COOKIE, str(store.id))

    def _open(self, url, store=None):
        self._login(store)
        return self.url_open(url, timeout=30, allow_redirects=False)

    def _post(self, url, store=None, **data):
        self._login(store)
        data['csrf_token'] = http.Request.csrf_token(self)
        return self.url_open(url, data=data, timeout=30, allow_redirects=False)

    def _values(self, fid, store=None):
        self._login(store)
        res = self.url_open('/portal/info-request/franchise/%d/values' % fid, timeout=30,
                            data=json.dumps({'jsonrpc': '2.0', 'method': 'call',
                                             'params': {'request_type': 'phone'}}),
                            headers={'Content-Type': 'application/json'})
        return res.json()['result']

    def _att_url(self, rec, att):
        return '/portal/info-request/%d/attachment/%d' % (rec.id, att.id)

    def _assert_redirect_list(self, res):
        self.assertEqual(res.status_code, 303)
        self.assertTrue(res.headers['Location'].endswith('/portal/info-request'), res.headers['Location'])

    def test_not_selected_prompt_no_data(self):
        html = self._open('/portal/info-request').text
        self.assertIn(PROMPT_NEED_PICK, html)
        self.assertNotIn(self.rec_a.name, html)
        self.assertNotIn(self.rec_b.name, html)

    def test_not_selected_everything_else_blocked(self):
        self._assert_redirect_list(self._open('/portal/info-request/%d' % self.rec_a.id))
        self._assert_redirect_list(self._open('/portal/info-request/new'))
        self._assert_redirect_list(self._post('/portal/info-request/%d/cancel' % self.rec_a.id))
        self.assertEqual(self.rec_a.state, 'submitted')
        self.assertEqual(self._values(self.store_a.id), {'error': 'forbidden'})
        self.assertEqual(self._open(self._att_url(self.rec_a, self.att_a)).status_code, 404)

    def test_selected_a_only_a(self):
        html = self._open('/portal/info-request', self.store_a).text
        self.assertIn(self.rec_a.name, html)
        self.assertNotIn(self.rec_b.name, html)
        detail = self._open('/portal/info-request/%d' % self.rec_a.id, self.store_a)
        self.assertEqual(detail.status_code, 200)
        self.assertIn(self._att_url(self.rec_a, self.att_a), detail.text)
        self.assertNotIn('/web/content/%d' % self.att_a.id, detail.text)
        self.assertEqual(self._open(self._att_url(self.rec_a, self.att_a), self.store_a).status_code, 200)
        self.assertEqual(self._values(self.store_a.id, self.store_a), {'old_value': '0281'})
        form = self._open('/portal/info-request/new', self.store_a).text
        select = re.search(r'<select name="franchise_id".*?</select>', form, re.S).group(0)
        self.assertIn('value="%d"' % self.store_a.id, select)
        self.assertNotIn('value="%d"' % self.store_b.id, select)

    def test_switch_to_b_only_b(self):
        html = self._open('/portal/info-request', self.store_b).text
        self.assertIn(self.rec_b.name, html)
        self.assertNotIn(self.rec_a.name, html)

    def test_foreign_ids_blocked(self):
        self._assert_redirect_list(self._open('/portal/info-request/%d' % self.rec_b.id, self.store_a))
        self._assert_redirect_list(self._post('/portal/info-request/%d/cancel' % self.rec_b.id, self.store_a))
        self.assertEqual(self.rec_b.state, 'submitted')
        self.assertEqual(self._values(self.store_b.id, self.store_a), {'error': 'forbidden'})
        self.assertEqual(self._open(self._att_url(self.rec_b, self.att_b), self.store_a).status_code, 404)
        self.assertEqual(self._open(self._att_url(self.rec_a, self.att_b), self.store_a).status_code, 404)

    def test_submit_for_other_store_rejected(self):
        res = self._post('/portal/info-request/new', self.store_a, franchise_id=self.store_b.id,
                         request_type='phone', new_value='0912', action='submit')
        self.assertEqual(res.status_code, 200)
        self.assertFalse(self.Model.search([('franchise_id', '=', self.store_b.id), ('new_value', '=', '0912')]))
