"""D5 — CMP-DL-001 DataList: hợp đồng render của `wj_data_list` + số BA của bảng.

Bám cột `Kết quả mong muốn` của issue UI-DATALIST-001 (STT 126) cho phần lượt D5b
phủ: cấu trúc DataViewport/DataItem/DataState/Pagination, `th[scope]` ở 3 call site
đầu, guard pager `page_count > 1`, và ba con số desktop 44 / 52 / `10px 16px`.

F5b: call site của 12 module nghiệp vụ đã dời sang
`wujia_portal_base/tests/test_scan_d5_data_list.py`, `wujia_portal_debt`,
`wujia_portal_exam`; helper đọc CSS module khác sang `portal_base/tests/css_probe.py`.
"""
import os
import re

from lxml import etree, html

from odoo.tests import TransactionCase, tagged

TMPL = 'wujia_portal_layout.wj_data_list'
HERE = os.path.dirname(__file__)
CSS_DIR = os.path.join(HERE, '..', 'static', 'assets', 'css')
CUSTOM = os.path.abspath(os.path.join(HERE, '..', '..'))


def _css(name):
    with open(os.path.join(CSS_DIR, name), encoding='utf-8') as fh:
        return fh.read()


def _mod_css(module, name):
    with open(os.path.join(CUSTOM, module, 'static', 'src', 'css', name), encoding='utf-8') as fh:
        return fh.read()


def _strip_comments(css):
    return re.sub(r'/\*.*?\*/', '', css, flags=re.S)


def _rule(css, selector):
    """Thân của rule ở TẦNG GỐC (ngoài mọi @media) — bẫy D4a: gộp @media vào là
    đọc ra số của bản mobile."""
    css = _strip_comments(css)
    depth, i, out = 0, 0, None
    while i < len(css):
        c = css[i]
        if c == '{':
            depth += 1
        elif c == '}':
            depth -= 1
        elif depth == 0 and css.startswith(selector, i):
            after = css[i + len(selector)]
            if after in ' ,{\n':
                j = css.index('{', i)
                if css[i:j].strip() == selector:
                    out = css[j + 1:css.index('}', j)]
                    break
        i += 1
    return out


def _rule_in_media(css, selector):
    """Thân của rule nằm TRONG @media. `_rule()` cố ý chỉ đọc tầng gốc (bẫy D4a)
    nên gọi thẳng cho mknow/mnoti trả None ⇒ guard chứng-minh-rỗng (D5e)."""
    css = _strip_comments(css)
    depth, i, out = 0, 0, None
    while i < len(css):
        c = css[i]
        if c == '{':
            depth += 1
        elif c == '}':
            depth -= 1
        elif depth == 1 and css.startswith(selector, i):
            after = css[i + len(selector)]
            if after in ' ,{\n':
                j = css.index('{', i)
                if css[i:j].strip() == selector:
                    out = css[j + 1:css.index('}', j)]
                    break
        i += 1
    return out


def _chu_the(selector_part):
    """Compound CUỐI của một selector — phần thực sự bị style. Bỏ pseudo-element
    (::before) vì đó là con sinh ra, không phải chính hàng."""
    if '::' in selector_part:
        return ''
    return re.split(r'[ >+~]+', selector_part.strip())[-1]


def _view(module, filename):
    """Đọc dạng BYTES: file view có khai báo encoding, lxml từ chối chuỗi unicode."""
    with open(os.path.join(CUSTOM, module, 'views', filename), 'rb') as fh:
        return etree.fromstring(fh.read())


@tagged('post_install', '-at_install', 'wujia_data_list_d5')
class TestDataListComponent(TransactionCase):

    def _render(self, values=None, slot=''):
        """Render QUA t-call như call site thật: Odoo 19 bỏ values['0'], slot chỉ
        tồn tại khi đi qua thân của t-call."""
        sets = ''.join(
            '<t t-set="%s" t-value="%r"/>' % (k, v) if not (isinstance(v, str) and v.startswith('<'))
            else '<t t-set="%s">%s</t>' % (k, v)
            for k, v in (values or {}).items())
        arch = ('<t t-name="wujia_portal_layout.wj_dl_probe">'
                '<t t-call="%s">%s%s</t></t>') % (TMPL, sets, slot)
        view = self.env['ir.ui.view'].create({
            'name': 'wj_dl_probe', 'type': 'qweb',
            'key': 'wujia_portal_layout.wj_dl_probe', 'arch_db': arch,
        })
        rendered = self.env['ir.qweb']._render(view.id)
        return html.fromstring(rendered)

    # ---------------------------------------------------------- cấu trúc
    def test_table_variant_dung_ba_tang(self):
        """DataList > DataViewport > table — thiếu tầng nào cũng đỏ."""
        root = self._render(slot='<thead><tr><th>A</th></tr></thead>')
        self.assertEqual(root.get('class').split()[0], 'wj-data-list')
        self.assertIn('wj-data-list--table', root.get('class'))
        viewports = root.xpath('./div[contains(@class, "wj-data-viewport")]')
        self.assertEqual(len(viewports), 1, 'phải có đúng một DataViewport')
        self.assertEqual([e.tag for e in viewports[0]], ['table'])
        self.assertIn('wj-data-table', viewports[0][0].get('class'))

    def test_lop_cu_cua_call_site_duoc_giu(self):
        """Lớp cũ đi qua dl_table_class/dl_class — CSS con và :is() hover không đứt."""
        root = self._render(
            {'dl_table_class': 'wujia-content-card-table', 'dl_class': 'legacy-wrapper'},
            slot='<tbody><tr><td>x</td></tr></tbody>')
        self.assertIn('legacy-wrapper', root.get('class'))
        table = root.xpath('.//table')[0]
        self.assertEqual(
            set(table.get('class').split()), {'wj-data-table', 'wujia-content-card-table'})

    def test_variant_khong_phai_bang_thi_khong_dung_table(self):
        for variant in ('compact-row', 'detail-card'):
            root = self._render({'dl_variant': variant}, slot='<a class="item">x</a>')
            self.assertIn('wj-data-list--%s' % variant, root.get('class'))
            self.assertFalse(root.xpath('.//table'), '%s không được bọc <table>' % variant)
            self.assertTrue(root.xpath('.//a[@class="item"]'))

    def test_variant_la_khong_biet_thi_ve_table(self):
        root = self._render({'dl_variant': 'bảng-lạ'}, slot='<tbody/>')
        self.assertIn('wj-data-list--table', root.get('class'))

    # ---------------------------------------------------------- DataState
    def test_datastate_thay_cho_viewport_khi_rong(self):
        root = self._render(
            {'dl_empty': True, 'dl_state': '<div class="wujia-empty-state">Chưa có dữ liệu</div>'},
            slot='<tbody><tr><td>không được render</td></tr></tbody>')
        self.assertFalse(root.xpath('.//table'), 'rỗng thì KHÔNG render viewport')
        self.assertEqual(len(root.xpath('.//div[@class="wujia-empty-state"]')), 1)

    def test_co_du_lieu_thi_khong_render_datastate(self):
        root = self._render(
            {'dl_empty': False, 'dl_state': '<div class="wujia-empty-state">x</div>'},
            slot='<tbody><tr><td>1</td></tr></tbody>')
        self.assertTrue(root.xpath('.//table'))
        self.assertFalse(root.xpath('.//div[@class="wujia-empty-state"]'))

    # ---------------------------------------------------------- Pagination
    def test_pager_nam_ngoai_viewport(self):
        root = self._render({'dl_pager': '<nav class="pager">1/2</nav>'},
                            slot='<tbody><tr><td>1</td></tr></tbody>')
        nav = root.xpath('.//nav[@class="pager"]')
        self.assertEqual(len(nav), 1)
        self.assertFalse(nav[0].xpath('ancestor::div[contains(@class,"wj-data-viewport")]'),
                         'Pagination phải NGOÀI DataViewport')

    def test_khong_truyen_pager_thi_khong_co_the_rong(self):
        root = self._render(slot='<tbody/>')
        self.assertFalse(root.xpath('.//nav'))

    # ---------------------------------------------------------- số BA
    def test_header_cao_44(self):
        body = _rule(_css('_components.css'), '.wj-data-table thead th')
        self.assertIsNotNone(body, 'không tìm thấy rule header ở tầng gốc')
        self.assertRegex(body, r'height:\s*44px')
        self.assertRegex(body, r'padding:\s*0 16px')

    def test_row_san_52(self):
        body = _rule(_css('_components.css'), '.wj-data-table tbody tr')
        self.assertIsNotNone(body)
        self.assertRegex(body, r'height:\s*52px')

    def test_cell_padding_10_16(self):
        body = _rule(_css('_components.css'), '.wj-data-table tbody td')
        self.assertIsNotNone(body)
        self.assertRegex(body, r'padding:\s*10px 16px')

    def test_mot_chu_so_huu_dang(self):
        """Bảng đã migrate KHÔNG được chạm rule cũ: mọi rule của lớp cũ phải mang
        `:not(.wj-data-table)`."""
        css = _strip_comments(_css('_components.css'))
        selectors = re.findall(r'([^{}]*\.wujia-content-card-table[^{}]*)\{', css)
        self.assertTrue(selectors)
        for sel in selectors:
            for part in sel.split(','):
                if '.wujia-content-card-table' in part:
                    self.assertIn(':not(.wj-data-table)', part,
                                  'rule cũ còn chạm bảng đã migrate: %s' % part.strip())
