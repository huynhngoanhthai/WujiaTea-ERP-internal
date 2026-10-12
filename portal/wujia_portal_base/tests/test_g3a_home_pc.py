"""G3a — khung Home PC theo mockup V4 (issue 142 UI-PC-HOME-REDESIGN-001).

Chạy: `--test-tags wujia_home_pc_g3a`.

Hàng đầu 50/50 Cửa hàng hiện tại | Khung giờ đặt hàng, 4 KPI Đơn hàng · Thông báo · Đổi trả ·
Công nợ với thuật ngữ + nguồn + link như Home mobile; không mũi tên phải, không "Đơn chờ xử lý",
không bảng top sản phẩm (chủ dự án chốt 30/09: bỏ theo đúng danh sách BA, bỏ luôn query).
Phần đo pixel (2 card cao bằng nhau, không tràn/cắt chữ ở 1440/1280/1024/992, mobile Δ0) thuộc
`scripts/qa/wj_home_g3.py`.
"""
import re
from types import SimpleNamespace
from unittest.mock import patch

from lxml import etree, html

from odoo.tests import TransactionCase, tagged
from odoo.tests.common import HttpCase

from odoo.addons.wujia_portal_base.controllers.portal import WujiaPortal
from odoo.addons.wujia_portal_base.tests.css_probe import _mod_css, _strip_comments
from odoo.addons.wujia_portal_base.tests.common import load_vi

PC = "//div[contains(concat(' ', @class, ' '), ' wujia-home-pc ')]"
KPI_ORDER = ['Đơn hàng', 'Thông báo', 'Đổi trả', 'Công nợ']
KPI_HREF = ['/portal/purchase-history', '/portal/notification', '/portal/return']


def _text(el):
    return re.sub(r'\s+', ' ', ''.join(el.itertext())).strip()


def _src(el):
    """Markup không kèm comment — comment được phép nhắc tên thứ đã bỏ."""
    el = etree.fromstring(etree.tostring(el))
    for c in el.xpath('//comment()'):
        c.getparent().remove(c)
    return etree.tostring(el, encoding='unicode')


def _cls(name):
    return f"contains(concat(' ', @class, ' '), ' {name} ')"


@tagged('post_install', '-at_install', 'wujia_home_pc_g3a')
class TestHomePcFrameArch(TransactionCase):
    """Cấu trúc view GỐC của portal_base (chưa ghép wujia_portal_debt)."""

    def setUp(self):
        super().setUp()
        # J-V2: arch đọc ở vi_VN (câu gốc đã là tiếng Anh, nhãn VN nằm ở .po).
        view = load_vi(self.env).ref('wujia_portal_base.portal_home_page')
        self.root = etree.fromstring(view.arch_db.encode())
        self.pc = self.root.xpath(PC)
        self.assertEqual(len(self.pc), 1, 'khối PC phải có đúng một vỏ .wujia-home-pc')
        self.pc = self.pc[0]
        self.assertIn('d-lg-block', self.pc.get('class'))

    def test_top_row_is_store_then_window_half_half(self):
        rows = self.pc.xpath(f".//div[{_cls('wujia-home-toprow')}]")
        self.assertEqual(len(rows), 1)
        cols = rows[0].xpath('./div')
        self.assertEqual([c.get('class') for c in cols], ['col-lg-6 col-12'] * 2)
        classes = [c.xpath(".//t[@t-set='sc_class']")[0].get('t-value') for c in cols]
        self.assertEqual(classes, ["'wujia-home-store'", "'wujia-home-window'"])

    def test_top_row_comes_before_kpis(self):
        order = [el.get('class') for el in self.pc.iter()
                 if el.get('class') in ('row wujia-home-toprow', 'wujia-home-kpis')]
        self.assertEqual(order, ['row wujia-home-toprow', 'wujia-home-kpis'])

    def test_four_kpis_in_mobile_order_with_mobile_links(self):
        sec = self.pc.xpath(f".//section[{_cls('wujia-home-kpis')}]")
        self.assertEqual(len(sec), 1)
        labels = [_text(p) for p in sec[0].xpath(f".//p[{_cls('wujia-kpi-label')}]")]
        self.assertEqual(labels, KPI_ORDER)
        hrefs = [t.get('t-value') for t in sec[0].xpath(".//t[@t-set='sc_href']")]
        self.assertEqual(hrefs[:3], [repr(h) for h in KPI_HREF])
        # Công nợ: link chỉ khi wujia_portal_debt đặt khe `home_debt_kpi`, không thì ô inert.
        self.assertEqual(hrefs[3], "home_debt_kpi and '/portal/debt'")

    def test_kpis_share_mobile_sources(self):
        """Cùng biến controller với 4 ô KPI mobile — không có con số riêng cho PC."""
        pc_vals = [v.get('t-out') for v in self.pc.xpath(f".//div[{_cls('wujia-kpi-value')}]")]
        m_vals = [v.get('t-out') for v in self.root.xpath(f"//span[{_cls('wujia-mhome-kpi-value')}]")]
        self.assertEqual(pc_vals[:3], m_vals[:3])

    def test_no_table_datalist_left_on_home(self):
        self.assertFalse(self.root.xpath('//t[@t-call="wujia_portal_layout.wj_data_list"][.//thead]'))

    def test_no_arrow_no_separator_no_dropped_blocks(self):
        src = _src(self.pc)
        for gone in ('wujia-kpi-arrow', 'wujia-kpi-separator', 'Đơn chờ xử lý',
                     'waiting_orders_count', 'Sản phẩm mua nhiều nhất', 'top_products'):
            self.assertNotIn(gone, src)
        kpis = self.pc.xpath(f".//section[{_cls('wujia-home-kpis')}]")[0]
        self.assertFalse(kpis.xpath(".//i[contains(@class, 'chevron')]"))

    def test_no_hero_and_no_quick_actions_on_pc(self):
        src = _src(self.pc)
        for mobile_only in ('wujia-mhome-hero', 'wujia-mhome-actions', 'Hành động nhanh', 'Thao tác nhanh'):
            self.assertNotIn(mobile_only, src)

    def test_role_pill_uses_status_badge_and_one_label_source(self):
        pill = self.pc.xpath(f".//span[{_cls('wujia-home-store-role')}]")
        self.assertEqual(len(pill), 1)
        self.assertIn('wj-status-badge', pill[0].get('class'))
        self.assertEqual(pill[0].get('t-out'), 'role_labels.get(active_role, active_role)')


@tagged('post_install', '-at_install', 'wujia_home_pc_g3a')
class TestHomePcController(TransactionCase):

    def test_dropped_keys_and_helper_are_gone(self):
        self.assertFalse(hasattr(WujiaPortal, '_top_products'))
        fake = SimpleNamespace(env=self.env)
        with patch('odoo.addons.wujia_portal_base.controllers.portal.request', new=fake):
            vals = WujiaPortal()._dashboard_values(())
        for key in ('waiting_orders_count', 'top_products', 'top_currency_symbol'):
            self.assertNotIn(key, vals)
        for key in ('recent_orders_count', 'unread_count', 'return_requests_count'):
            self.assertIn(key, vals)


@tagged('post_install', '-at_install', 'wujia_home_pc_g3a')
class TestHomePcCss(TransactionCase):
    """Mọi rule G3a nằm trong @media ≥992 và có tiền tố .wujia-home-pc ⇒ Home mobile không đổi."""

    def test_rules_are_scoped_to_pc(self):
        css = _strip_comments(_mod_css('wujia_portal_base', 'portal_dashboard.css'))
        start = css.index('@media (min-width: 992px)')
        body = css[css.index('{', start) + 1:]
        depth, end = 1, 0
        for i, c in enumerate(body):
            depth += c == '{'
            depth -= c == '}'
            if not depth:
                end = i
                break
        block = body[:end]
        selectors = [s.strip() for s in re.findall(r'([^{}]+)\{', block)]
        self.assertTrue(selectors)
        for sel in selectors:
            for part in sel.split(','):
                self.assertTrue(part.strip().startswith('.wujia-home-pc '), part)
        # Các lớp mới chỉ xuất hiện trong khối đó.
        outside = css[:start] + body[end:]
        for cls in ('.wujia-home-store', '.wujia-home-window', '.wujia-home-tile', '.wujia-home-toprow'):
            self.assertNotIn(cls, outside)

    def test_dead_kpi_classes_removed(self):
        css = _mod_css('wujia_portal_base', 'portal_dashboard.css')
        self.assertNotIn('.wujia-kpi-arrow', css)
        self.assertNotIn('.wujia-kpi-separator', css)

    def test_store_name_wraps_not_ellipsis(self):
        css = _strip_comments(_mod_css('wujia_portal_base', 'portal_dashboard.css'))
        rule = css[css.index('.wujia-home-pc .wujia-home-store-name'):]
        rule = rule[:rule.index('}')]
        self.assertIn('overflow-wrap: anywhere', rule)
        self.assertNotIn('ellipsis', rule)
        self.assertNotIn('nowrap', rule)


@tagged('post_install', '-at_install', 'wujia_home_pc_g3a')
class TestHomePcRender(HttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        cls.store = env['wujia.franchise.management'].create({
            'code': 'G3A1', 'name': 'G3a store', 'franchise_end_date': '2030-01-01',
            'partner_id': env['res.partner'].create({'name': 'G3a partner'}).id})
        user = env['res.users'].create({
            'name': 'g3a_mgr', 'login': 'g3a_mgr', 'password': 'g3a_mgr',
            'group_ids': [(6, 0, [env.ref('base.group_portal').id])]})
        env['wujia.franchise.member'].create({
            'user_id': user.id, 'franchise_id': cls.store.id, 'role': 'manager'})

    def _pc(self, window=None):
        self.authenticate('g3a_mgr', 'g3a_mgr')
        if window is None:
            res = self.url_open('/portal', timeout=30)
        else:
            with patch.object(WujiaPortal, '_order_window_view', lambda self, franchise=None: window):
                res = self.url_open('/portal', timeout=30)
        self.assertEqual(res.status_code, 200)
        doc = html.fromstring(res.text)
        pc = doc.xpath(PC)
        self.assertEqual(len(pc), 1)
        return pc[0]

    def test_store_card_prints_store_and_vietnamese_role(self):
        store = self._pc().xpath(f".//div[{_cls('wujia-home-store')}]")[0]
        text = _text(store)
        self.assertIn('Cửa hàng hiện tại', text)
        self.assertIn(self.store.display_name, text)
        self.assertEqual(_text(store.xpath(f".//span[{_cls('wujia-home-store-role')}]")[0]), 'Quản lý')

    def test_window_three_states(self):
        tz = 'Asia/Ho_Chi_Minh (UTC+07:00)'
        cases = [
            ({'state': 'open', 'remaining_hhmm': '02:15', 'progress_pct': 40, 'to_hhmm': '17:00', 'tz_label': tz},
             'is-open', ['Đang mở', '02:15', 'Có thể đặt hàng đến 17:00 hôm nay', tz], True),
            ({'state': 'closed', 'from_hhmm': '08:00', 'tz_label': tz}, 'is-closed',
             ['Đã đóng', 'Mở lại lúc 08:00', tz], False),
            ({'state': 'tz_missing'}, 'is-closed', ['chưa cấu hình múi giờ'], False),
            ({'state': 'always'}, 'is-always', ['Đặt hàng 24/7', 'Đặt hàng mọi lúc trong ngày'], False),
        ]
        for window, cls, texts, bar in cases:
            with self.subTest(state=window['state']):
                win = self._pc(window).xpath(f".//div[{_cls('wujia-home-window')}]")[0]
                self.assertTrue(win.xpath(f".//span[{_cls('wujia-mhome-window-status')} and {_cls(cls)}]"))
                for t in texts:
                    self.assertIn(t, _text(win))
                self.assertEqual(bool(win.xpath(f".//div[{_cls('wujia-mhome-window-progress')}]")), bar)

    def test_kpi_labels_and_links_rendered(self):
        kpis = self._pc().xpath(f".//section[{_cls('wujia-home-kpis')}]")[0]
        self.assertEqual([_text(p) for p in kpis.xpath(f".//p[{_cls('wujia-kpi-label')}]")], KPI_ORDER)
        links = [a.get('href') for a in kpis.xpath('.//a')]
        self.assertEqual(links[:3], KPI_HREF)
        self.assertNotIn('Sản phẩm mua nhiều nhất', _text(self._pc()))
