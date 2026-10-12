"""D5 (quét nhiều module) — call site DataList CMP-DL-001.

F5b dời khỏi `wujia_portal_layout`: khung không được biết màn nào. Hợp đồng render
của component + số BA của bảng vẫn ở layout.
"""
import os
import re

from lxml import html

from odoo.tests import TransactionCase, tagged

from odoo.addons.wujia_portal_base.tests.css_probe import (
    CSS_DIR, CUSTOM, _chu_the, _css, _mod_css, _rule, _rule_in_media, _strip_comments,
    _view,
)

TMPL = 'wujia_portal_layout.wj_data_list'


@tagged('post_install', '-at_install', 'wujia_data_list_d5')
class TestDataListCallSites(TransactionCase):
    """3 call site của lượt D5b — semantic + guard pager, đọc thẳng file view."""

    # G3a (142): Home PC bỏ bảng top sản phẩm (mockup V4) ⇒ Home hết DataList dạng bảng;
    # guard "Home không có bảng" nằm ở test_g3a_home_pc.
    CALL_SITES = [
        ('wujia_portal_return', 'portal_return_list.xml', 7),
        ('wujia_portal_support', 'portal_support.xml', 8),
        # D5c — họ wj-pc-table
        ('wujia_portal_purchase_history', 'portal_history.xml', 7),
        ('wujia_portal_delivery', 'portal_delivery.xml', 8),
        ('wujia_portal_notification', 'portal_notification.xml', 5),
    ]

    def test_moi_th_deu_co_scope(self):
        for module, filename, n_cols in self.CALL_SITES:
            root = _view(module, filename)
            # Chọn theo cấu trúc (DataList có <thead>) chứ không theo số lượng call.
            calls = root.xpath('//t[@t-call="wujia_portal_layout.wj_data_list"][.//thead]')
            self.assertEqual(len(calls), 1, '%s: phải có đúng 1 DataList dạng bảng' % module)
            ths = calls[0].xpath('.//thead//th')
            self.assertEqual(len(ths), n_cols, '%s: số cột đổi' % module)
            khong_scope = [html.tostring(t, encoding='unicode')[:60]
                           for t in ths if t.get('scope') != 'col']
            self.assertEqual(khong_scope, [], '%s: th thiếu scope' % module)

    def test_pager_chi_hien_khi_nhieu_hon_mot_trang(self):
        # E3b: mọi call site đã về `wj_pagination`; guard ">1 trang" nay nằm trong
        # component (test_e3_pagination), nên ở đây ghim "không ai tự dựng lại pager".
        for module, filename, _n in self.CALL_SITES:
            root = _view(module, filename)
            self.assertFalse(
                root.xpath('//nav[.//ul[contains(@class, "wujia-pagination")]]'),
                '%s: pager cũ quay lại' % module)
            for el in root.iter():
                cls = el.get('class') or el.get('t-attf-class') or ''
                self.assertNotIn('wj-pc-page-btn', cls.split(),
                                 '%s: nút trang cũ quay lại' % module)

    def test_home_preview_khong_gan_pagination(self):
        """BA: preview dashboard dùng "Xem tất cả" ở CardHeader, KHÔNG pager.
        G3b/142: 3 block list cũ (ul.wujia-content-card-body) thay bằng 5 block record V4
        có danh sách (Hỗ trợ nhanh / Thông tin cửa hàng không phải danh sách)."""
        root = _view('wujia_portal_base', 'portal_home.xml')
        previews = root.xpath(
            '//div[contains(concat(" ", @class, " "), " wujia-home-blocks ")]'
            '//t[@t-call="wujia_portal_layout.wj_data_list"]')
        self.assertEqual(len(previews), 5, 'phải đủ 5 khối preview record Home PC')
        for call in previews:
            self.assertFalse(call.xpath('.//t[@t-set="dl_pager"]'))
            self.assertFalse(call.xpath('.//nav'))


@tagged('post_install', '-at_install', 'wujia_data_list_d5')
class TestDataListPcTable(TransactionCase):
    """D5c — họ bảng PC `wj-pc-table`: một chủ sở hữu dáng, guard pager, dáng mượn."""

    # Biến thể Ô, không phải hình học danh sách ⇒ cố ý vẫn chạm bảng đã migrate.
    ALLOWLIST = ('.wj-pc-td--code', '.wj-pc-td--muted', '.wj-pc-td--amount')

    def test_pc_mot_chu_so_huu_dang(self):
        css = _strip_comments(_css('_pc_components.css'))
        selectors = re.findall(r'([^{}]*\.wj-pc-table[^{}]*)\{', css)
        self.assertTrue(selectors)
        kiem = 0
        for sel in selectors:
            for part in sel.split(','):
                if '.wj-pc-table' not in part:
                    continue
                if any(x in part for x in self.ALLOWLIST):
                    continue
                kiem += 1
                self.assertIn(':not(.wj-data-table)', part,
                              'rule cũ còn chạm bảng đã migrate: %s' % part.strip())
        self.assertGreaterEqual(kiem, 9, 'quét hụt rule .wj-pc-table')

    def test_bang_khong_migrate_giu_nguyen_50_58(self):
        """Khoá sai tay là 12 bảng khác (exam/debt/inspection/báo cáo…) đổi dáng theo."""
        css = _css('_pc_components.css')
        self.assertRegex(_rule(css, '.wj-pc-table:not(.wj-data-table) thead th'),
                         r'height:\s*var\(--wj-pc-table-header-h\)')
        self.assertRegex(_rule(css, '.wj-pc-table:not(.wj-data-table) tbody td'),
                         r'height:\s*var\(--wj-pc-table-row-h\)')
        var = _rule(_css('_variables.css'), ':root')
        self.assertRegex(var, r'--wj-pc-table-header-h:\s*50px')
        self.assertRegex(var, r'--wj-pc-table-row-h:\s*58px')

    def test_pager_bang_pc_di_qua_component(self):
        """E3b: bảng PC của thông báo và giao hàng phân trang bằng `wj_pagination`
        (guard ">1 trang" ở trong component), không còn khối `wj-pc-pagination`."""
        for module, filename in [
                ('wujia_portal_notification', 'portal_notification.xml'),
                ('wujia_portal_delivery', 'portal_delivery.xml')]:
            root = _view(module, filename)
            self.assertFalse(root.xpath('//div[@class="wj-pc-pagination"]'),
                             '%s: khối pager cũ quay lại' % module)
            self.assertTrue(
                root.xpath('//t[@t-call="wujia_portal_layout.wj_pagination"]'),
                '%s: mất pager PC' % module)

    def test_noti_giu_lop_va_id_cu(self):
        """`wj-pc-noti-row` KHÔNG có rule CSS nào — dáng đến hoàn toàn từ wj-pc-table,
        nên mất lớp hay mất id là mất dáng/điểm bám mà không test nào khác bắt được."""
        root = _view('wujia_portal_notification', 'portal_notification.xml')
        call = root.xpath('//t[@t-call="wujia_portal_layout.wj_data_list"]')[0]
        self.assertEqual(call.xpath('.//t[@t-set="dl_table_id"]')[0].get('t-value'),
                         "'wj-noti-table'")
        self.assertIn('wj-pc-noti-table',
                      call.xpath('.//t[@t-set="dl_table_class"]')[0].get('t-value'))
        # `contains()` là guard RỖNG ở đây: chuỗi con "wj-pc-noti-row" vẫn khớp qua
        # nhánh "wj-pc-noti-row--unread" bên trong #{...}. Phải neo vào token đứng đầu.
        rows = call.xpath('.//tbody//tr[@t-attf-class]')
        self.assertEqual(len(rows), 1)
        self.assertRegex(rows[0].get('t-attf-class'), r'^wj-pc-noti-row(\s|$)')

    def test_component_chuyen_duoc_id_bang(self):
        arch = ('<t t-name="wujia_portal_layout.wj_dl_id_probe">'
                '<t t-call="%s"><t t-set="dl_table_id" t-value="\'x-tbl\'"/>'
                '<tbody><tr><td>1</td></tr></tbody></t></t>') % TMPL
        view = self.env['ir.ui.view'].create({
            'name': 'wj_dl_id_probe', 'type': 'qweb',
            'key': 'wujia_portal_layout.wj_dl_id_probe', 'arch_db': arch,
        })
        root = html.fromstring(self.env['ir.qweb']._render(view.id))
        self.assertEqual(root.xpath('.//table')[0].get('id'), 'x-tbl')

    def test_hover_noti_khong_bi_zebra_nuot(self):
        """Zebra và hover cùng độ đặc hiệu (0,2,2) ⇒ row chẵn mất hover nếu không nâng."""
        path = os.path.join(CUSTOM, 'wujia_portal_notification', 'static', 'src', 'css',
                            'portal_notification.css')
        with open(path, encoding='utf-8') as fh:
            css = fh.read()
        body = _rule(css, '.wj-data-table.wj-pc-noti-table tbody tr:hover')
        self.assertIsNotNone(body, 'thiếu rule hover nâng độ đặc hiệu cho bảng noti')
        # Nền hover = màu chủ đạo 4% — qua token brand (J-B2), không hex cứng.
        self.assertIn('rgb(var(--wujia-primary-rgb) / 0.04)', body)

    def test_skeleton_delivery_khop_row_that(self):
        """Skeleton giả hàng bảng — lệch số là loading nhảy hình khi đổ dữ liệu."""
        path = os.path.join(CUSTOM, 'wujia_portal_delivery', 'static', 'src', 'css',
                            'portal_delivery.css')
        with open(path, encoding='utf-8') as fh:
            body = _rule(fh.read(), '.wj-pc-dlv-skel-row')
        self.assertIsNotNone(body)
        self.assertRegex(body, r'height:\s*52px')
        self.assertRegex(body, r'padding:\s*10px 16px')


@tagged('post_install', '-at_install', 'wujia_data_list_d5')
class TestDataListCompactRow(TransactionCase):
    """D5d — danh sách PC không phải bảng (`li.wujia-content-card-row`): variant
    compact-row, một chủ sở hữu dáng, và call site đầu tiên dùng `dl_pager`."""

    # (module, file, số call site, họ cũ item còn phải mang — None = đã sang CMP-LC-001)
    # E5b1: danh sách PC Kiến thức đã về ListCard ⇒ item bỏ họ `wujia-content-card-row`,
    # CSS con (bullet/date) chuyển sang lớp riêng; hợp đồng ruột ở test_scan_e5_list_card.
    # G3b/142: Home PC bỏ họ `wujia-content-card-row` (3 block list cũ) — 7 block V4 dùng
    # dòng `wujia-mdash-row` như mobile, hợp đồng ở test_g3b_home_pc.py.
    COMPACT_SITES = [
        ('wujia_portal_knowledge', 'portal_knowledge.xml', 1, None),
    ]

    def _compact_calls(self, module, filename):
        root = _view(module, filename)
        # D5e: mobile cũng dùng compact-row ⇒ neo vào container PC thật, không
        # chỉ vào variant (nếu không phép chọn vớ luôn 6 call site mobile).
        return root.xpath(
            '//t[@t-call="wujia_portal_layout.wj_data_list"]'
            '[t[@t-set="dl_variant"][@t-value="\'compact-row\'"]]'
            '[.//ul[@class="wujia-content-card-body"]]')

    def test_bon_call_site_dung_variant_compact_row(self):
        for module, filename, n, _ho in self.COMPACT_SITES:
            calls = self._compact_calls(module, filename)
            self.assertEqual(len(calls), n, '%s: số call site compact-row đổi' % module)
            for call in calls:
                self.assertTrue(call.xpath('.//ul[@class="wujia-content-card-body"]'),
                                '%s: mất container danh sách' % module)

    def test_item_mang_ca_hai_lop(self):
        """Neo vào TOKEN, không `contains()` — bẫy D5c #3 (tên lớp có biến thể BEM)."""
        for module, filename, n, ho in self.COMPACT_SITES:
            for call in self._compact_calls(module, filename):
                ul = './/ul[@class="wujia-content-card-body"]'
                lis = call.xpath(ul + '/li') + call.xpath(ul + '/t/li')
                self.assertEqual(len(lis), 1, '%s: mỗi danh sách đúng 1 item mẫu' % module)
                tokens = (lis[0].get('class') or '').split()
                self.assertIn('wj-data-item', tokens, '%s: item thiếu wj-data-item' % module)
                if ho:
                    self.assertIn(ho, tokens,
                                  '%s: item mất lớp cũ (CSS con bullet/content/date đứt)' % module)
                else:
                    self.assertIn('wj-lc', tokens,
                                  '%s: item đã migrate phải mang ruột ListCard' % module)

    def test_mot_chu_so_huu_dang_compact_row(self):
        """Mọi rule chạm CHÍNH lớp `.wujia-content-card-row` — kể cả trong @media —
        phải mang `:not(.wj-data-item)`. Regex loại tên con BEM bằng ranh giới ký tự."""
        css = _strip_comments(_css('_components.css'))
        selectors = re.findall(r'([^{}]*\.wujia-content-card-row(?![-\w])[^{}]*)\{', css)
        self.assertTrue(selectors, 'không còn rule nào của lớp cũ — sai phép đo')
        for sel in selectors:
            for part in sel.split(','):
                # D5e: rule layout MỚI của chính item đã migrate mang `.wj-data-item`
                # ngoài `:not()` — đó không phải rule cũ.
                if '.wj-data-item' in re.sub(r':not\([^)]*\)', '', part):
                    continue
                if re.search(r'\.wujia-content-card-row(?![-\w])', part):
                    self.assertIn(':not(.wj-data-item)', part,
                                  'rule cũ còn chạm item đã migrate: %s' % part.strip())

    def test_so_ba_cua_compact_row(self):
        body = _rule(_css('_components.css'), '.wj-data-list--compact-row .wj-data-item')
        self.assertIsNotNone(body, 'không tìm thấy rule item ở tầng gốc')
        self.assertRegex(body, r'min-height:\s*64px')       # BA 64–76
        self.assertRegex(body, r'padding:\s*12px;')         # LC-07 (E5c: bỏ 14 ngang)
        self.assertRegex(body, r'border-radius:\s*12px')    # BA 12
        gap = _rule(_css('_components.css'),
                    '.wj-data-list--compact-row .wj-data-item + .wj-data-item')
        self.assertIsNotNone(gap, 'thiếu rule gap giữa hai item')
        self.assertRegex(gap, r'margin-top:\s*8px')         # BA gap 8

    def test_knowledge_pager_di_qua_dl_pager(self):
        """Pager vào TRONG DataList (sơ đồ BA), guard `page_count > 1` giữ nguyên,
        và khối PC không còn nav nào nằm ngoài."""
        root = _view('wujia_portal_knowledge', 'portal_knowledge.xml')
        call = self._compact_calls('wujia_portal_knowledge', 'portal_knowledge.xml')[0]
        calls = call.xpath(
            './t[@t-set="dl_pager"]//t[@t-call="wujia_portal_layout.wj_pagination"]')
        self.assertEqual(len(calls), 1, 'pager phải nằm trong dl_pager')
        pc = root.xpath('//div[@id="wj-know-pc-body"]')[0]
        ngoai = [n for n in pc.xpath('.//nav')
                 if not n.xpath('ancestor::t[@t-set="dl_pager"]')]
        self.assertEqual(ngoai, [], 'còn pager cũ nằm ngoài DataList')

    def test_dl_pager_render_duoc_khoi_co_t_foreach(self):
        """Call site đầu tiên dùng dl_pager: chứng minh markup có `t-foreach` đi qua
        `t-set` ra đủ nút, không rơi vào họ bẫy D5b #1 (Odoo 19 bỏ values['0'])."""
        arch = ('<t t-name="wujia_portal_layout.wj_dl_pager_probe">'
                '<t t-call="wujia_portal_layout.wj_data_list">'
                '<t t-set="dl_variant" t-value="\'compact-row\'"/>'
                '<t t-set="dl_pager">'
                '<nav class="pager"><t t-foreach="range(1, 4)" t-as="pn">'
                '<a class="page-link" t-out="pn"/></t></nav>'
                '</t>'
                '<ul><li class="wj-data-item">x</li></ul>'
                '</t></t>')
        view = self.env['ir.ui.view'].create({
            'name': 'wj_dl_pager_probe', 'type': 'qweb',
            'key': 'wujia_portal_layout.wj_dl_pager_probe', 'arch_db': arch,
        })
        root = html.fromstring(self.env['ir.qweb']._render(view.id))
        links = root.xpath('.//nav[@class="pager"]/a')
        self.assertEqual([a.text for a in links], ['1', '2', '3'])
        self.assertFalse(root.xpath('.//nav[@class="pager"]'
                                    '/ancestor::div[contains(@class,"wj-data-viewport")]'),
                         'Pagination phải NGOÀI DataViewport')


@tagged('post_install', '-at_install', 'wujia_data_list_d5')
class TestDataListCompactRowMobile(TransactionCase):
    """D5e — 9 call site mobile (mdash ×6 · mhist · mnoti · mknow): một chủ sở hữu
    dáng cho CẢ BỐN họ, layout riêng từng họ, và bộ số BA của compact-row."""

    # E5: Lịch sử đặt hàng (E5a) rồi Hỗ trợ · Thông báo · Kiến thức (E5b1) đã rời họ
    # riêng sang CMP-LC-001 ⇒ ra khỏi bảng này; hợp đồng của chúng nằm ở
    # test_scan_e5_list_card.py. Còn lại đúng khối Home giữ grouped rows (LC-23).
    MOBILE_SITES = [
        ('wujia_portal_base', 'portal_home.xml', 5),
    ]
    HO = ('wujia-mdash-row',)

    def _mobile_calls(self, module, filename):
        """Call site compact-row KHÔNG phải của D5d (D5d dùng ul.wujia-content-card-body).
        G3b: bỏ khối Home PC (`.wujia-home-pc`) — cùng họ mdash nhưng hợp đồng ở test_g3b."""
        root = _view(module, filename)
        return root.xpath(
            '//t[@t-call="wujia_portal_layout.wj_data_list"]'
            '[t[@t-set="dl_variant"][@t-value="\'compact-row\'"]]'
            '[not(.//ul[@class="wujia-content-card-body"])]'
            '[not(ancestor::div[contains(concat(" ", @class, " "), " wujia-home-pc ")])]')

    def _items(self, call):
        out = []
        for el in call.iter():
            cls = el.get('class') or el.get('t-attf-class') or ''
            if any(re.match(r'%s(\s|$)' % h, cls) for h in self.HO):
                out.append((el, cls))
        return out

    def test_chin_call_site_mobile(self):
        tong = 0
        for module, filename, n in self.MOBILE_SITES:
            calls = self._mobile_calls(module, filename)
            self.assertEqual(len(calls), n, '%s: số call site mobile đổi' % module)
            tong += len(calls)
        self.assertEqual(tong, 5, 'D5e còn 5 call site Home (3 màn kia sang E5)')

    def test_item_mang_ca_hai_lop(self):
        """Neo TOKEN ĐỨNG ĐẦU — `contains()` khớp cả tên con BEM (bẫy D5c #3)."""
        for module, filename, _n in self.MOBILE_SITES:
            for call in self._mobile_calls(module, filename):
                items = self._items(call)
                self.assertEqual(len(items), 1,
                                 '%s: mỗi danh sách đúng 1 item mẫu' % module)
                self.assertIn('wj-data-item', items[0][1].split(),
                              '%s: item thiếu wj-data-item' % module)

    def test_is_stacked_con_du_ba_cho(self):
        """3/6 khối mdash là biến thể nhiều dòng phụ — mất modifier là icon/badge
        tụt về giữa khối mà không số đo nào đỏ."""
        stacked = [cls for call in self._mobile_calls('wujia_portal_base', 'portal_home.xml')
                   for _el, cls in self._items(call) if 'is-stacked' in cls.split()]
        self.assertEqual(len(stacked), 3, 'số khối is-stacked đổi')

    def test_muoi_hang_mdash_khong_phai_danh_sach_giu_nguyen(self):
        """`wujia-mdash-row` còn 13 chỗ KHÔNG phải danh sách record (lối tắt Home,
        hàng thông tin tĩnh Home/support; G3b +3 lối tắt Hỗ trợ nhanh của Home PC) — đụng
        vào là đổi dáng 13 chỗ ngoài phạm vi."""
        con_lai = 0
        for module, filename in (('wujia_portal_base', 'portal_home.xml'),
                                 ('wujia_portal_support', 'portal_support.xml')):
            root = _view(module, filename)
            for el in root.iter():
                cls = el.get('class') or el.get('t-attf-class') or ''
                if re.match(r'wujia-mdash-row(\s|$)', cls) and 'wj-data-item' not in cls.split():
                    con_lai += 1
        self.assertEqual(con_lai, 13, 'số hàng mdash ngoài phạm vi đổi')

    def test_mot_chu_so_huu_dang_bon_ho(self):
        """Rule cũ chỉ được chạm hàng CHƯA migrate. Xét compound CUỐI của mỗi
        selector (rule của lớp con và ::before là biến thể ô, cố ý giữ)."""
        for filename, ho in ((os.path.join(CSS_DIR, '_components.css'), ('wujia-mdash-row',)),):
            with open(filename, encoding='utf-8') as fh:
                css = _strip_comments(fh.read())
            for lop in ho:
                pat = re.compile(r'\.%s(?![-\w])' % lop)
                selectors = re.findall(r'([^{}]*\.%s(?![-\w])[^{}]*)\{' % lop, css)
                self.assertTrue(selectors, 'không còn rule nào của %s — sai phép đo' % lop)
                kiem = 0
                for sel in selectors:
                    for part in sel.split(','):
                        if not pat.search(_chu_the(part)):
                            continue
                        # `:not(.wj-data-item)` cũng chứa chuỗi `.wj-data-item` ⇒ phải
                        # bóc `:not()` trước, nếu không guard tự chứng minh rỗng.
                        if '.wj-data-item' in re.sub(r':not\([^)]*\)', '', part):
                            continue
                        kiem += 1
                        self.assertIn(':not(.wj-data-item)', part,
                                      'rule cũ còn chạm item đã migrate: %s' % part.strip())
                # F4 xoá hẳn rule vỏ `:not(.wj-data-item)` (0 phần tử khớp) ⇒ kiem có thể 0;
                # phép quét vẫn được giữ đúng bằng assertTrue(selectors) ở trên.

    def test_layout_tung_ho_tach_khoi_dang(self):
        """Dáng dùng chung ở .wj-data-item; layout (flex/grid) ở từng họ — gộp lại
        là ép lưới 4 cột của PC lên hàng mobile, vỡ cả 9 chỗ."""
        css = _css('_components.css')
        dang = _rule(css, '.wj-data-list--compact-row .wj-data-item')
        self.assertIsNotNone(dang)
        self.assertNotIn('display: grid', dang, 'dáng chung không được mang layout')
        self.assertNotIn('grid-template-columns', dang)
        for src, sel in ((css, '.wj-data-list--compact-row .wujia-mdash-row.wj-data-item'),):
            body = _rule(src, sel)
            self.assertIsNotNone(body, 'thiếu rule layout: %s' % sel)
            self.assertRegex(body, r'display:\s*flex')
        pc = _rule(css, '.wj-data-list--compact-row .wujia-content-card-row.wj-data-item')
        self.assertIsNotNone(pc, 'D5d mất rule layout lưới 4 cột')
        self.assertRegex(pc, r'grid-template-columns:\s*auto 1fr auto auto')

    def test_layout_ho_mdash_nam_o_tang_goc(self):
        """E5b1: hai họ khai trong @media (mknow, mnoti) đã sang CMP-LC-001 ⇒ ở D5e
        chỉ còn họ mdash của Home. Giữ phép đo để đừng ai gộp layout vào dáng."""
        css = _css('_components.css')
        body = _rule(css, '.wj-data-list--compact-row .wujia-mdash-row.wj-data-item')
        self.assertIsNotNone(body, 'thiếu rule layout mdash')
        self.assertRegex(body, r'display:\s*flex')
        for cam in ('padding', 'border-radius', 'background'):
            self.assertNotRegex(body, r'\b%s\s*:' % cam,
                                'layout giành lại dáng (%s)' % cam)


@tagged('post_install', '-at_install', 'wujia_data_list_d5')
class TestDataListDetailCard(TransactionCase):
    """D5f — variant `detail-card`: call site record còn lại của D5 (`mreturn`).
    Skeleton của Giao hàng đã sang `.wj-lc` cùng lượt E5."""

    # E5: Giao hàng (E5a) rồi Bù hàng (E5b1) đã sang CMP-LC-001 ⇒ ở đây chỉ còn bộ số
    # BA của variant, khối skeleton và pager; ruột item do test_scan_e5_list_card giữ.
    SITES = [
        ('wujia_portal_return', 'portal_return_list.xml'),
    ]

    def _calls(self, module, filename):
        root = _view(module, filename)
        return root.xpath(
            '//t[@t-call="wujia_portal_layout.wj_data_list"]'
            '[t[@t-set="dl_variant"][@t-value="\'detail-card\'"]]')

    def _la_skeleton(self, call):
        return bool(call.xpath('.//*[contains(@class, "wujia-mdelivery-skel")]'))

    def test_hai_call_site_record(self):
        """2 call site RECORD. Khối skeleton cũng đi qua component nhưng không
        phải record ⇒ đếm phải loại nó ra, nếu không inventory sai."""
        record = 0
        for module, filename in self.SITES:
            calls = self._calls(module, filename)
            self.assertTrue(calls, '%s: mất call site detail-card' % module)
            record += len([c for c in calls if not self._la_skeleton(c)])
        self.assertEqual(record, 1, 'D5f còn 1 call site record (Giao hàng sang E5)')

    def test_so_ba_cua_detail_card(self):
        body = _rule(_css('_components.css'), '.wj-data-list--detail-card .wj-data-item')
        self.assertIsNotNone(body, 'không tìm thấy rule dáng detail-card ở tầng gốc')
        self.assertRegex(body, r'min-height:\s*96px')       # BA 96–120
        self.assertRegex(body, r'padding:\s*12px;')         # LC-07 (E5c: bỏ 14 ngang)
        self.assertRegex(body, r'border-radius:\s*12px')    # BA 12
        gap = _rule(_css('_components.css'),
                    '.wj-data-list--detail-card .wj-data-item + .wj-data-item')
        self.assertIsNotNone(gap, 'thiếu rule gap giữa hai item')
        self.assertRegex(gap, r'margin-top:\s*8px')         # BA gap 8

    def test_skeleton_cung_dang_nhung_khong_phai_record(self):
        """Skeleton là placeholder của CHÍNH hàng đó ⇒ phải mang `wj-data-item` để
        không lệch dáng lúc đang tải; nhưng nó không phải bản ghi."""
        calls = self._calls('wujia_portal_delivery', 'portal_delivery.xml')
        skel = [c for c in calls if self._la_skeleton(c)]
        self.assertEqual(len(skel), 1, 'khối skeleton phải đi qua DataList')
        self.assertTrue(skel[0].xpath('.//t[@t-foreach="[1, 2, 3]"]'),
                        'skeleton không còn là 3 hàng giả')
        cls = skel[0].xpath('.//div[contains(@class, "wujia-mdelivery-skel")]')[0].get('class')
        self.assertIn('wj-data-item', cls.split(), 'skeleton lệch dáng với hàng thật')

    def test_pager_hai_cho_di_qua_component(self):
        """E3b: hai pager mobile này về `wj_pagination`; họ `wujia-mhist-pager` đi hẳn."""
        for module, filename in self.SITES:
            root = _view(module, filename)
            self.assertFalse(root.xpath('//nav[@class="wujia-mhist-pager"]'),
                             '%s: pager mobile cũ quay lại' % module)
            self.assertTrue(
                root.xpath('//t[@t-call="wujia_portal_layout.wj_pagination"]'),
                '%s: mất pager mobile' % module)

    def test_radius_khong_dung_token_chung(self):
        """`--wujia-morder-radius` còn dùng ở 3 chỗ khác; đè radius tại rule
        detail-card, KHÔNG sửa token."""
        token = _rule(_css('_variables.css'), ':root')
        self.assertRegex(token, r'--wujia-morder-radius:\s*14px')
        body = _rule(_css('_components.css'), '.wj-data-list--detail-card .wj-data-item')
        self.assertNotIn('--wujia-morder-radius', body)


@tagged('post_install', '-at_install', 'wujia_data_list_d5')
class TestDataListAdjacent(TransactionCase):
    """D5h — 3 call site KỀ CẬN ngoài 10 route BA: bảng PC /portal/info-request và
    /portal/franchise-information (bảng PC thành viên + danh sách mobile)."""

    def _calls(self, module, filename, variant=None):
        out = []
        for call in _view(module, filename).xpath(
                '//t[@t-call="wujia_portal_layout.wj_data_list"]'):
            got = call.xpath('./t[@t-set="dl_variant"]/@t-value')
            got = got[0].strip("'") if got else None
            if got == variant:
                out.append(call)
        return out

    def test_ba_call_site(self):
        self.assertEqual(
            len(self._calls('wujia_portal_info_request', 'portal_info_request_list.xml')),
            1, 'bảng PC yêu cầu cập nhật thông tin')
        self.assertEqual(
            len(self._calls('wujia_portal_base', 'portal_franchise_information.xml')),
            1, 'bảng PC thành viên cửa hàng')
        self.assertEqual(
            len(self._calls('wujia_portal_base', 'portal_franchise_information.xml',
                            'compact-row')),
            1, 'danh sách thành viên mobile')

    def test_th_scope_du_muoi_hai_cot(self):
        tong = 0
        for module, filename in (('wujia_portal_info_request', 'portal_info_request_list.xml'),
                                 ('wujia_portal_base', 'portal_franchise_information.xml')):
            for call in self._calls(module, filename):
                ths = call.xpath('.//thead//th')
                self.assertTrue(ths, '%s: bảng mất thead' % module)
                for th in ths:
                    self.assertEqual(th.get('scope'), 'col',
                                     '%s: th thiếu scope="col"' % module)
                tong += len(ths)
        self.assertEqual(tong, 12, 'số cột 2 bảng kề cận đổi (8 + 4)')

    def test_item_mobile_mang_ca_hai_lop(self):
        # Chọn theo CẤU TRÚC (có lớp item), không theo dl_variant — đổi variant là
        # phép của test_ba_call_site, không được kéo test này đỏ theo (bài học D5g #3).
        # E5b1: hàng thành viên rời họ `wujia-mdash-row` sang ruột ListCard, dáng
        # ngoài vẫn là việc của D5 ⇒ neo vào `wj-data-item` chứ không vào họ cũ.
        thay = 0
        for el in _view('wujia_portal_base', 'portal_franchise_information.xml').iter():
            cls = el.get('class') or el.get('t-attf-class') or ''
            if 'wj-data-item' in cls.split():
                self.assertIn('wj-lc', cls.split(),
                              'hàng thành viên mobile thiếu ruột ListCard')
                thay += 1
        self.assertEqual(thay, 1, 'phải đúng 1 item mẫu')

    def test_pager_thanh_vien_la_component_that(self):
        """Pager cũ ở đây là ô `10 / trang` trơ với 0 nút trang, luôn hiện dù chỉ 1
        trang. E3b: phân trang THẬT phía server, dựng bằng component."""
        root = _view('wujia_portal_base', 'portal_franchise_information.xml')
        for el in root.iter():
            cls = el.get('class') or el.get('t-attf-class') or ''
            self.assertNotIn('wj-pc-page-btn', cls.split(),
                             'nút trang cứng đã quay lại màn thông tin cửa hàng')
            self.assertNotIn('wj-pc-pagination', cls.split(),
                             'khối pager giả đã quay lại màn thông tin cửa hàng')
        self.assertEqual(
            len(root.xpath('//t[@t-call="wujia_portal_layout.wj_pagination"]')), 2,
            'phân trang thành viên phải có ở cả bảng PC lẫn danh sách mobile')

    def test_pager_info_request_di_qua_component(self):
        """E3b: pager về `wj_pagination` và vẫn cố ý nằm NGOÀI DataList (tiền lệ D5b
        của cùng họ `wujia-content-card-table`)."""
        root = _view('wujia_portal_info_request', 'portal_info_request_list.xml')
        calls = root.xpath('//t[@t-call="wujia_portal_layout.wj_pagination"]')
        self.assertEqual(len(calls), 1, 'mất pager của info-request')
        for call in self._calls('wujia_portal_info_request', 'portal_info_request_list.xml'):
            self.assertFalse(
                call.xpath('.//t[@t-call="wujia_portal_layout.wj_pagination"]'),
                'pager đã bị kéo vào DataList — đổi bố cục, ngoài phạm vi lượt')
