"""Đổi trả chỉ theo MỘT cửa hàng đang chọn: list, form, chi tiết, tệp đính kèm, submit.

Chạy: `--test-tags wujia_scope_i4b`.
"""
import base64

from odoo.exceptions import ValidationError
from odoo.tests import tagged
from odoo.tests.common import HttpCase

from odoo.addons.wujia_portal_base.controllers.portal import ACTIVE_FRANCHISE_COOKIE
from odoo.addons.wujia_return.tests.common import ReturnFixture

PROMPT_NEED_PICK = 'data-store-scope="need_pick"'


@tagged('post_install', '-at_install', 'wujia_scope_i4b')
class TestReturnStoreScope(HttpCase, ReturnFixture):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._setup_return_data()
        user = cls.env['res.users'].create({
            'name': 'i4b_ret', 'login': 'i4b_ret', 'password': 'i4b_ret',
            'group_ids': [(6, 0, [cls.env.ref('base.group_portal').id])]})
        for store in (cls.franchise, cls.other):
            cls.env['wujia.franchise.member'].create({
                'user_id': user.id, 'franchise_id': store.id, 'role': 'owner'})
        cls.rr_a = cls._request(cls.franchise, cls.order_ok)
        cls.rr_b = cls._request(cls.other, cls.order_other)
        cls.att_a, cls.att_b = (cls.env['ir.attachment'].create({
            'name': 'i4b.jpg', 'res_model': rr._name, 'res_id': rr.id,
            'datas': base64.b64encode(b'x'), 'mimetype': 'image/jpeg'}) for rr in (cls.rr_a, cls.rr_b))
        cls.rr_a.image_attachment_ids = [(4, cls.att_a.id)]
        cls.rr_b.image_attachment_ids = [(4, cls.att_b.id)]

    def _open(self, url, store=None):
        self.authenticate('i4b_ret', 'i4b_ret')
        if store is not None:
            self.opener.cookies.set(ACTIVE_FRANCHISE_COOKIE, str(store.id))
        return self.url_open(url, timeout=30, allow_redirects=False)

    def _att_url(self, rr, att):
        return '/portal/return/%d/attachment/%d' % (rr.id, att.id)

    def _assert_redirect_list(self, res):
        self.assertEqual(res.status_code, 303)
        self.assertTrue(res.headers['Location'].endswith('/portal/return'), res.headers['Location'])

    def test_not_selected_prompt_no_data(self):
        res = self._open('/portal/return')
        self.assertEqual(res.status_code, 200)
        self.assertIn(PROMPT_NEED_PICK, res.text)
        self.assertNotIn(self.rr_a.name, res.text)
        self.assertNotIn(self.rr_b.name, res.text)

    def test_not_selected_detail_form_attachment_blocked(self):
        self._assert_redirect_list(self._open('/portal/return/%d' % self.rr_a.id))
        self._assert_redirect_list(self._open('/portal/return/new'))
        self.assertEqual(self._open(self._att_url(self.rr_a, self.att_a)).status_code, 403)

    def test_selected_a_only_a(self):
        html = self._open('/portal/return', self.franchise).text
        self.assertIn(self.rr_a.name, html)
        self.assertNotIn(self.rr_b.name, html)
        self.assertEqual(self._open('/portal/return/%d' % self.rr_a.id, self.franchise).status_code, 200)
        self.assertEqual(self._open(self._att_url(self.rr_a, self.att_a), self.franchise).status_code, 200)
        form = self._open('/portal/return/new', self.franchise).text
        self.assertIn(self.order_ok.name, form)
        self.assertNotIn(self.order_other.name, form)

    def test_switch_to_b_only_b(self):
        html = self._open('/portal/return', self.other).text
        self.assertIn(self.rr_b.name, html)
        self.assertNotIn(self.rr_a.name, html)

    def test_foreign_ids_blocked(self):
        res = self._open('/portal/return/%d' % self.rr_b.id, self.franchise)
        self.assertEqual(res.status_code, 303)
        self.assertIn('notice=not_found', res.headers['Location'])
        self.assertEqual(self._open(self._att_url(self.rr_b, self.att_b), self.franchise).status_code, 404)
        # Phiếu A nhưng tệp của B ⇒ không tải được.
        self.assertEqual(self._open(self._att_url(self.rr_a, self.att_b), self.franchise).status_code, 403)

    def test_submit_for_other_store_rejected(self):
        line = self.order_other.order_line[0]
        post = {'franchise_id': str(self.other.id), 'sale_order_id': str(self.order_other.id),
                'sale_order_line_id': str(line.id), 'issue_type_id': str(self.issue_type.id),
                'request_qty': '3', 'opening_datetime': '2026-09-01T08:00'}
        with self.assertRaises(ValidationError):
            self.env['wujia.return.request']._portal_prepare_vals(post, (self.franchise.id,))
