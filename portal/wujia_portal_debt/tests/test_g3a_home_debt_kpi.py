"""G3a (issue 142) — ô KPI Công nợ trên Home PC V4, cùng nguồn với ô mobile.

Chạy: `--test-tags wujia_home_debt_g3a`.

portal_base in ô PC inert "—" và đọc khe biến `home_debt_kpi`; module này đặt khe đó MỘT lần
cho cả hai ô (get_home_debt_kpi có 1 search_count — gọi hai lần là thêm query mỗi lượt vào Home).
"""
import re
from unittest.mock import patch

from lxml import html

from odoo.tests import tagged
from odoo.tests.common import HttpCase


def _text(el):
    return re.sub(r'\s+', ' ', ''.join(el.itertext())).strip()


@tagged('post_install', '-at_install', 'wujia_home_debt_g3a')
class TestHomeDebtKpiG3a(HttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        store = env['wujia.franchise.management'].create({
            'code': 'G3AD', 'name': 'G3a debt store', 'franchise_end_date': '2030-01-01',
            'partner_id': env['res.partner'].create({'name': 'G3a debt partner'}).id})
        user = env['res.users'].create({
            'name': 'g3a_debt', 'login': 'g3a_debt', 'password': 'g3a_debt',
            'group_ids': [(6, 0, [env.ref('base.group_portal').id])]})
        env['wujia.franchise.member'].create({
            'user_id': user.id, 'franchise_id': store.id, 'role': 'owner'})

    def _home(self):
        self.authenticate('g3a_debt', 'g3a_debt')
        res = self.url_open('/portal', timeout=30)
        self.assertEqual(res.status_code, 200)
        return html.fromstring(res.text)

    def test_pc_tile_links_to_debt_with_same_label_as_mobile(self):
        doc = self._home()
        pc = doc.xpath("//div[contains(concat(' ', @class, ' '), ' wujia-home-kpi-debt ')]")
        self.assertEqual(len(pc), 1)
        link = pc[0].getparent()
        self.assertEqual(link.tag, 'a')
        self.assertEqual(link.get('href'), '/portal/debt')
        pc_val = _text(pc[0].xpath(".//div[contains(@class, 'wujia-kpi-value')]")[0])
        mobile = doc.xpath("//a[@href='/portal/debt' and contains(@class, 'wujia-mhome-kpi')]")
        self.assertEqual(len(mobile), 1)
        m_val = _text(mobile[0].xpath(".//span[contains(@class, 'wujia-mhome-kpi-value')]")[0])
        # Cửa hàng mới chưa có chứng từ ⇒ "—", không phải 0đ (STT11 acceptance #5).
        self.assertEqual(pc_val, m_val)
        self.assertEqual(pc_val, '—')

    def test_debt_kpi_computed_once_per_home(self):
        Debt = type(self.env['wujia.portal.debt'])
        orig = Debt.get_home_debt_kpi
        calls = []

        def spy(rec):
            calls.append(1)
            return orig(rec)

        with patch.object(Debt, 'get_home_debt_kpi', spy):
            self._home()
        self.assertEqual(len(calls), 1)
