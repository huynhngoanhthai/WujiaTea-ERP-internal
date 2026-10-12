"""E4c — Báo cáo đơn hàng: khoảng ngày ngược phải nói ra, không im lặng trả rỗng.

Chạy: `--test-tags wujia_filter_e4c`.
"""
import re

from odoo.tests import tagged
from odoo.tests.common import HttpCase

from odoo.addons.wujia_portal_base.controllers.utils import ERR_DATE_RANGE

REVERSED = '?date_from=2026-09-30&date_to=2026-09-01'


@tagged('post_install', '-at_install', 'wujia_filter_e4c')
class TestReportFilterDatesE4c(HttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        cls.franchise = env['wujia.franchise.management'].create({
            'code': 'E4CR', 'name': 'E4CR store',
            'franchise_end_date': '2030-01-01',
            'partner_id': env['res.partner'].create({'name': 'E4CR partner'}).id,
        })
        cls.user = env['res.users'].create({
            'name': 'e4c_rep', 'login': 'e4c_rep', 'password': 'e4c_rep',
            'group_ids': [(6, 0, [env.ref('base.group_portal').id])],
        })
        env['wujia.franchise.member'].create({
            'user_id': cls.user.id, 'franchise_id': cls.franchise.id,
            'role': 'owner',
        })

    @property
    def err_date_range(self):
        """J-V2: ERR_DATE_RANGE là `_lt` ⇒ so đúng câu user thấy theo ngôn ngữ của user."""
        return self.env(context=dict(self.env.context, lang=self.user.lang))._(ERR_DATE_RANGE)

    def _get(self, url):
        self.authenticate('e4c_rep', 'e4c_rep')
        res = self.url_open(url, timeout=30)
        self.assertEqual(res.status_code, 200)
        return res.text

    @staticmethod
    def _tag(html, eid):
        return re.search(r'<p id="%s"[^>]*>' % eid, html)

    def test_ngay_nguoc_bao_ngay_tai_thanh_loc(self):
        """Không chặn thì domain vô nghiệm ⇒ empty state, người dùng tưởng hết dữ liệu."""
        html = self._get('/portal/reports/orders' + REVERSED)
        self.assertIn(self.err_date_range, html)
        tag = self._tag(html, 'wj-rep-pcerr')
        self.assertTrue(tag, 'thiếu ô báo lỗi wj-rep-pcerr')
        self.assertNotIn('hidden', tag.group(0))

    def test_giu_nguyen_chu_da_go(self):
        html = self._get('/portal/reports/orders' + REVERSED)
        self.assertIn('value="2026-09-30"', html)
        self.assertIn('value="2026-09-01"', html)

    def test_khong_loi_thi_o_bao_van_ton_tai_nhung_an(self):
        """Mất phần tử là JS thay khối hụt id ⇒ cả màn rơi về tải lại trang."""
        html = self._get('/portal/reports/orders')
        self.assertNotIn(self.err_date_range, html)
        for eid in ('wj-rep-pcerr', 'wj-rep-merr'):
            tag = self._tag(html, eid)
            self.assertTrue(tag, 'thiếu ô báo lỗi %s' % eid)
            self.assertIn('hidden', tag.group(0))
