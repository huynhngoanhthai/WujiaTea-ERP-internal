"""G3b — 7 block record của Home PC theo mockup V4 (issue 142 UI-PC-HOME-REDESIGN-001).

Chạy: `--test-tags wujia_home_pc_g3b`.

Thứ tự V4: Đơn hàng gần đây · Yêu cầu đổi trả gần đây · Giao hàng sắp tới · Thông báo nổi bật ·
Bài viết / Kiến thức mới · Hỗ trợ nhanh · Thông tin cửa hàng (rộng cả hàng). Dòng record chép
từ block mobile (cùng biến, chữ, badge, link) nên PC không có query riêng. Chủ dự án chốt 30/09:
Giao hàng có dòng phụ "N đơn chưa giao" + "Xem tất cả"; lưới 2 cột ≥992, 3 cột ≥1400; dòng Thông
báo dùng ô icon chuông như mobile. Phần đo pixel (0 cắt chữ, block cùng hàng cao bằng nhau, chuỗi
VI/EN/ZH dài, mobile Δ0) thuộc `scripts/qa/wj_home_g3.py`.
"""
import re

from lxml import etree, html

from odoo.tests import TransactionCase, tagged
from odoo.tests.common import HttpCase

from odoo.addons.wujia_portal_base.controllers.utils import portal_money
from odoo.addons.wujia_portal_base.tests.css_probe import _mod_css, _strip_comments
from odoo.addons.wujia_portal_base.tests.common import load_vi
from odoo.addons.wujia_portal_base.tests.test_g3a_home_pc import PC, _cls, _src, _text

BLOCKS = [
    # (modifier, tiêu đề, icon header, href "Xem tất cả" | None)
    ('orders', 'Đơn hàng gần đây', 'file-text', '/portal/purchase-history'),
    ('returns', 'Yêu cầu đổi trả gần đây', 'corner-up-left', '/portal/return'),
    ('delivery', 'Giao hàng sắp tới', 'truck', '/portal/delivery'),
    ('noti', 'Thông báo nổi bật', 'bell', '/portal/notification'),
    ('knowledge', 'Bài viết / Kiến thức mới', 'book', '/portal/knowledge'),
    ('support', 'Hỗ trợ nhanh', 'headphones', None),
    ('info', 'Thông tin cửa hàng', 'map-pin', None),
]
# Icon ô của dòng record — đúng loại record, trùng block mobile tương ứng.
ROW_ICON = {'orders': 'file-text', 'returns': 'corner-up-left', 'delivery': 'truck',
            'noti': 'bell', 'knowledge': 'file-text'}


def _tval(el, name):
    t = el.xpath(f".//t[@t-set='{name}']")
    return t[0].get('t-value') if t else None


@tagged('post_install', '-at_install', 'wujia_home_pc_g3b')
class TestHomePcBlocksArch(TransactionCase):
    """View GỐC của portal_base."""

    def setUp(self):
        super().setUp()
        # J-V2: arch đọc ở vi_VN (câu gốc đã là tiếng Anh, nhãn VN nằm ở .po).
        view = load_vi(self.env).ref('wujia_portal_base.portal_home_page')
        self.root = etree.fromstring(view.arch_db.encode())
        self.pc = self.root.xpath(PC)[0]
        grid = self.pc.xpath(f".//div[{_cls('wujia-home-blocks')}]")
        self.assertEqual(len(grid), 1)
        self.grid = grid[0]
        # Mỗi block = 1 lần gọi SurfaceCard con trực tiếp của lưới (CSS grid cần card là con).
        self.cards = self.grid.xpath("./t[@t-call='wujia_portal_layout.wj_surface_card']")

    def _mod(self, card):
        cls = _tval(card, 'sc_class').strip("'").split()
        self.assertIn('wujia-home-block', cls)
        return next(c for c in cls if c.startswith('wujia-home-block--')).split('--')[1]

    def test_seven_blocks_in_v4_order(self):
        self.assertEqual([self._mod(c) for c in self.cards], [b[0] for b in BLOCKS])
        titles = [_text(c.xpath(".//t[@t-set='ch_title']")[0]) for c in self.cards]
        self.assertEqual(titles, [b[1] for b in BLOCKS])

    def test_header_icon_and_view_all_link(self):
        for card, (mod, _title, icon, href) in zip(self.cards, BLOCKS):
            with self.subTest(block=mod):
                header = card.xpath(".//t[@t-call='wujia_portal_layout.wj_card_header']")[0]
                self.assertEqual(_tval(header, 'ch_icon'), repr(icon))
                self.assertEqual(_tval(header, 'ch_platform'), "'pc'")
                self.assertEqual(_tval(header, 'ch_action_url'), repr(href) if href else None)
                # Nhãn mặc định của CardHeader là "Xem tất cả"; cấm icon mũi tên kèm theo.
                self.assertIsNone(_tval(header, 'ch_action_label'))
                self.assertIsNone(_tval(header, 'ch_action_icon'))

    def test_delivery_header_has_undelivered_subtitle(self):
        header = self.cards[2].xpath(".//t[@t-call='wujia_portal_layout.wj_card_header']")[0]
        self.assertIn('m_undelivered_count', _tval(header, 'ch_subtitle'))
        # J-V2: câu nằm ở <t t-set> (dịch được), biểu thức chỉ ghép số vào.
        self.assertIn('_hm_t_undelivered', _tval(header, 'ch_subtitle'))
        self.assertEqual(header.xpath(".//t[@t-set='_hm_t_undelivered']")[0].text, '%s đơn chưa giao')

    def test_row_icons_match_record_type(self):
        for card in self.cards:
            mod = self._mod(card)
            if mod not in ROW_ICON:
                continue
            with self.subTest(block=mod):
                rows = card.xpath(f".//a[{_cls('wujia-mdash-row')}]")
                self.assertEqual(len(rows), 1, 'một dòng mẫu trong t-foreach')
                icon = rows[0].xpath(f".//span[{_cls('wujia-mdash-tile')}]/i")[0].get('class')
                self.assertEqual(icon, f'feather icon-{ROW_ICON[mod]}')

    def test_rows_reuse_mobile_sources(self):
        """Cùng biến/nguồn với block mobile — không nguồn riêng cho PC."""
        src = _src(self.grid)
        mobile = _src(self.root.xpath(f"//div[{_cls('wujia-mhome')}]")[0])
        for var in ('t-foreach="recent_orders"', 't-foreach="latest_returns"', 't-foreach="m_upcoming_batches"',
                    't-foreach="latest_notifications"', 't-foreach="articles"',
                    "money(o.amount_total, o.currency_id.symbol, o.currency_id.decimal_places)",
                    "money(it['total'], store_currency_symbol, store_currency_decimals)",
                    'wj_return_status(r)', 'wj_order_badge(o)', 'm_hotline',
                    'active_franchise.main_owner_member_id.user_id.name'):
            self.assertIn(var, src)
            self.assertIn(var, mobile)

    def test_notification_badge_map_single_source(self):
        maps = [t for t in self.root.iter('t') if t.get('t-set') == 'noti_badge_map']
        self.assertEqual(len(maps), 1)
        self.assertNotIn("'URG': 'wujia-badge-danger'", _src(self.pc))
        self.assertNotIn("'URG': 'wujia-badge-danger'", _src(self.root.xpath(f"//div[{_cls('wujia-mhome')}]")[0]))

    def test_old_list_blocks_and_arrows_gone(self):
        src = _src(self.pc)
        for gone in ('wujia-content-card', 'chevron-right', 'icon-arrow-right', 'Thông báo mới nhất'):
            self.assertNotIn(gone, src)

    def test_grid_is_css_not_bootstrap_cols(self):
        self.assertFalse(self.grid.xpath(".//div[contains(@class, 'col-')]"))


@tagged('post_install', '-at_install', 'wujia_home_pc_g3b')
class TestHomePcBlocksCss(TransactionCase):

    def setUp(self):
        super().setUp()
        self.css = _strip_comments(_mod_css('wujia_portal_base', 'portal_dashboard.css'))

    def _media(self, query):
        start = self.css.index(f'@media ({query})')
        body = self.css[self.css.index('{', start) + 1:]
        depth = 1
        for i, c in enumerate(body):
            depth += c == '{'
            depth -= c == '}'
            if not depth:
                return body[:i]
        raise AssertionError(query)

    def _rule(self, block, selector):
        m = re.search(re.escape(selector) + r'\s*(?:,[^{]*)?\{([^}]*)\}', block)
        self.assertTrue(m, selector)
        return m.group(1)

    def test_breakpoints_two_then_three_columns(self):
        pc = self._media('min-width: 992px')
        wide = self._media('min-width: 1400px')
        self.assertIn('repeat(2, minmax(0, 1fr))', self._rule(pc, '.wujia-home-pc .wujia-home-blocks'))
        self.assertIn('repeat(3, minmax(0, 1fr))', self._rule(wide, '.wujia-home-pc .wujia-home-blocks'))
        self.assertIn('grid-column: 1 / -1', self._rule(pc, '.wujia-home-pc .wujia-home-block--info'))

    def test_wide_media_scoped_to_pc(self):
        for sel in re.findall(r'([^{}]+)\{', self._media('min-width: 1400px')):
            for part in sel.split(','):
                self.assertTrue(part.strip().startswith('.wujia-home-pc '), part)

    def test_block_classes_only_inside_pc_media(self):
        outside = self.css.replace(self._media('min-width: 992px'), '').replace(self._media('min-width: 1400px'), '')
        for cls in ('.wujia-home-blocks', '.wujia-home-block', '.wujia-home-info', '.wujia-home-support'):
            self.assertNotIn(cls, outside)

    def test_row_text_wraps_not_ellipsis(self):
        rule = self._rule(self._media('min-width: 992px'), '.wujia-home-pc .wujia-mdash-row-title')
        self.assertIn('white-space: normal', rule)
        self.assertIn('text-overflow: clip', rule)
        self.assertIn('overflow-wrap: anywhere', rule)
        self.assertNotIn('ellipsis', rule)

    def test_view_all_stays_on_title_row(self):
        pc = self._media('min-width: 992px')
        self.assertIn('flex-wrap: nowrap', self._rule(pc, '.wujia-home-pc .wujia-home-block .wj-card-header'))
        self.assertIn('white-space: nowrap', self._rule(pc, '.wujia-home-pc .wujia-home-block .wj-card-header__action'))


@tagged('post_install', '-at_install', 'wujia_home_pc_g3b')
class TestHomePcBlocksRender(HttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        partner = env['res.partner'].create({'name': 'G3b partner'})
        cls.store = env['wujia.franchise.management'].create({
            'code': 'G3B1', 'name': 'G3b store', 'franchise_end_date': '2030-01-01',
            'partner_id': partner.id})
        user = env['res.users'].create({
            'name': 'g3b_mgr', 'login': 'g3b_mgr', 'password': 'g3b_mgr',
            'group_ids': [(6, 0, [env.ref('base.group_portal').id])]})
        env['wujia.franchise.member'].create({
            'user_id': user.id, 'franchise_id': cls.store.id, 'role': 'manager'})
        empty = env['wujia.franchise.management'].create({
            'code': 'G3B2', 'name': 'G3b empty', 'franchise_end_date': '2030-01-01',
            'partner_id': env['res.partner'].create({'name': 'G3b empty partner'}).id})
        user2 = env['res.users'].create({
            'name': 'g3b_new', 'login': 'g3b_new', 'password': 'g3b_new',
            'group_ids': [(6, 0, [env.ref('base.group_portal').id])]})
        env['wujia.franchise.member'].create({
            'user_id': user2.id, 'franchise_id': empty.id, 'role': 'owner'})
        cls.order = env['sale.order'].create({'partner_id': partner.id, 'franchise_id': cls.store.id})

    def _doc(self, login):
        self.authenticate(login, login)
        res = self.url_open('/portal', timeout=30)
        self.assertEqual(res.status_code, 200)
        return html.fromstring(res.text)

    def _block(self, doc, mod):
        return doc.xpath(f"{PC}//div[{_cls('wujia-home-block--' + mod)}]")[0]

    def test_order_row_money_same_as_mobile(self):
        doc = self._doc('g3b_mgr')
        row = self._block(doc, 'orders').xpath(f".//a[@href='/portal/purchase-history/{self.order.id}']")
        self.assertEqual(len(row), 1)
        cur = self.order.currency_id
        money = portal_money(self.order.amount_total, cur.symbol, cur.decimal_places)
        self.assertIn(money, _text(row[0]))
        m_row = doc.xpath(f"//div[{_cls('wujia-mhome')}]//a[@href='/portal/purchase-history/{self.order.id}']")[0]
        self.assertEqual(_text(row[0]), _text(m_row))

    def test_view_all_links_rendered_without_arrow(self):
        doc = self._doc('g3b_mgr')
        for mod, _title, _icon, href in BLOCKS:
            with self.subTest(block=mod):
                action = self._block(doc, mod).xpath(f".//a[{_cls('wj-card-header__action')}]")
                if href is None:
                    self.assertFalse(action)
                    continue
                self.assertEqual(action[0].get('href'), href)
                self.assertEqual(_text(action[0]), 'Xem tất cả')
                self.assertFalse(action[0].xpath('.//i'))

    def test_delivery_subtitle_and_empty_states(self):
        doc = self._doc('g3b_new')
        sub = self._block(doc, 'delivery').xpath(f".//p[{_cls('wj-card-header__subtitle')}]")
        self.assertRegex(_text(sub[0]), r'^\d+ đơn chưa giao$')
        for mod, title in (('orders', 'Chưa có đơn hàng'), ('returns', 'Chưa có yêu cầu đổi trả'),
                           ('delivery', 'Chưa có chuyến giao sắp tới')):
            with self.subTest(block=mod):
                self.assertIn(title, _text(self._block(doc, mod)))

    def test_store_info_row_falls_back_to_dash(self):
        info = self._block(self._doc('g3b_new'), 'info')
        cells = info.xpath(f".//div[{_cls('wujia-home-info-cell')}]")
        self.assertEqual([_text(c).split(' ')[0] for c in cells], ['Địa', 'Điện', 'Người'])
        # Cửa hàng mới chưa có địa chỉ/điện thoại ⇒ "—" như mobile (Người phụ trách = chủ tiệm).
        self.assertEqual([_text(c)[-1] for c in cells[:2]], ['—', '—'])
