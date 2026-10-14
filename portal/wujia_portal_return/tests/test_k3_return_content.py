"""#175 — Đổi trả: Home, danh sách, chi tiết cùng một bộ nội dung theo cửa hàng đang chọn."""
import re
from datetime import timedelta

from odoo import fields
from odoo.tests import tagged
from odoo.tests.common import HttpCase

from odoo.addons.wujia_portal_base.controllers.portal import ACTIVE_FRANCHISE_COOKIE
from odoo.addons.wujia_return.tests.common import ReturnFixture

GROUPS = ['summary', 'request', 'product', 'issue', 'feedback']


@tagged('post_install', '-at_install', 'wujia_return_k3')
class TestReturnContentK3(HttpCase, ReturnFixture):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._setup_return_data()
        user = cls.env['res.users'].create({
            'name': 'k3_ret', 'login': 'k3_ret', 'password': 'k3_ret_pw', 'lang': 'en_US',
            'group_ids': [(6, 0, [cls.env.ref('base.group_portal').id])]})
        for store in (cls.franchise, cls.other):
            cls.env['wujia.franchise.member'].create({
                'user_id': user.id, 'franchise_id': store.id, 'role': 'owner'})
        now = fields.Datetime.now()
        cls.rr_draft = cls._request(state='draft', request_date=now)
        cls.rr_tie_lo = cls._request(request_date=now - timedelta(hours=1))
        cls.rr_tie_hi = cls._request(request_date=now - timedelta(hours=1))
        cls.rr_old = cls._request(request_date=now - timedelta(days=3), production_date=False, note=False)
        cls.rr_rejected = cls._request(state='rejected', request_date=now, reject_reason='K3 reject')
        cls.rr_other = cls._request(cls.other, cls.order_other, request_date=now)

    @staticmethod
    def _content(html):
        # Hộp chọn cửa hàng của layout nằm sau nội dung và luôn có tên cửa hàng.
        body = html[html.index('wj-ret-g--summary'):]
        return body[:body.index('wujia-store-intro')] if 'wujia-store-intro' in body else body

    def _get(self, url, store):
        self.authenticate('k3_ret', 'k3_ret_pw')
        self.opener.cookies.set(ACTIVE_FRANCHISE_COOKIE, str(store.id))
        res = self.url_open(url, timeout=30)
        self.assertEqual(res.status_code, 200, url)
        return res.text

    def test_home_recent_block(self):
        html = self._get('/portal', self.franchise)
        self.assertNotIn('Total: —', html)
        for rr in (self.rr_draft, self.rr_rejected, self.rr_old, self.rr_other):
            self.assertNotIn(rr.name, html)
        # Cùng ngày yêu cầu ⇒ ID lớn trước; PC và mobile cùng thứ tự.
        pos = [m.start() for m in re.finditer(re.escape(self.rr_tie_hi.name), html)]
        pos_lo = [m.start() for m in re.finditer(re.escape(self.rr_tie_lo.name), html)]
        self.assertTrue(pos and pos_lo)
        self.assertLess(pos[0], pos_lo[0])
        self.assertIn('CT3 tea · 12 kg', html)

    def test_list_current_store_only_without_store_column(self):
        html = self._get('/portal/return', self.franchise)
        for rr in (self.rr_draft, self.rr_tie_hi, self.rr_tie_lo, self.rr_old, self.rr_rejected):
            self.assertIn(rr.name, html)
        self.assertNotIn(self.rr_other.name, html)
        self.assertNotIn('<th scope="col">Store</th>', html)
        self.assertIn('12 kg', html)
        self.assertLess(html.index(self.rr_tie_hi.name), html.index(self.rr_tie_lo.name))
        html_b = self._get('/portal/return', self.other)
        self.assertIn(self.rr_other.name, html_b)
        self.assertNotIn(self.rr_tie_hi.name, html_b)

    def test_detail_same_groups_both_platforms(self):
        html = self._get('/portal/return/%d' % self.rr_old.id, self.franchise)
        groups = re.findall(r'wj-ret-g--(\w+)', html)
        self.assertEqual(groups, GROUPS + GROUPS)
        body = self._content(html)
        self.assertNotIn(self.franchise.name, body)
        self.assertNotIn('Order information', body)
        self.assertEqual(body.count('Request information'), 2)
        for label in ('Production date', 'Created by'):
            self.assertEqual(body.count('>%s<' % label), 2, label)
        self.assertEqual(body.count('Not recorded'), 2)
        self.assertEqual(body.count('The store left no note'), 2)
        self.assertNotIn('Notes &amp; feedback', body)

    def test_detail_rejected_feedback_separate_from_note(self):
        self.rr_rejected.note = 'K3 store note'
        html = self._get('/portal/return/%d' % self.rr_rejected.id, self.franchise)
        body = self._content(html)
        for _ in range(2):
            issue = body.index('wj-ret-g--issue')
            feedback = body.index('wj-ret-g--feedback')
            self.assertLess(issue, body.index('K3 store note', issue), 'note stays in issue group')
            self.assertLess(body.index('K3 store note', issue), feedback)
            self.assertLess(feedback, body.index('K3 reject', feedback))
            body = body[feedback + 1:]
