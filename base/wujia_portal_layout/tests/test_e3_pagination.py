"""E3a — CMP-PGNT-001 Pagination: hợp đồng render của `wj_pagination` + token dáng.

Bám cột `Kết quả mong muốn` của `UI-PAGINATION-001` (STT 130): ẩn khi `totalPages <= 1`,
a11y `nav[aria-label]` + `aria-current` + tên cho nút icon, không `href="#"`,
token 36/10/8 + chạm 44.

F5b: khung không được đọc của module nghiệp vụ nữa. Dữ liệu vào template nay là
FIXTURE viết tại chỗ (dict đúng hợp đồng) thay vì gọi `build_pager` của
`wujia_portal_base`; phép toán pager + call site đã sang
`wujia_portal_base/tests/test_scan_e3_pagination.py`.
"""
import os
import re

from lxml import html

from odoo.tests import TransactionCase, tagged

from .common import load_vi

TMPL = 'wujia_portal_layout.wj_pagination'
CSS_DIR = os.path.join(os.path.dirname(__file__), '..', 'static', 'assets', 'css')
ELLIPSIS = '…'


def _css(name):
    with open(os.path.join(CSS_DIR, name), encoding='utf-8') as fh:
        return re.sub(r'/\*.*?\*/', '', fh.read(), flags=re.S)


def _pgn(total, page, page_size, *, item_label='bản ghi', page_size_options=(),
         size_param='page_size', path='/x'):
    """Fixture: dict đúng hợp đồng mà mọi controller truyền vào component."""
    total_pages = max(1, -(-total // page_size))
    page = min(max(1, page), total_pages)
    offset = (page - 1) * page_size
    numbers = list(range(1, total_pages + 1))

    def url(num):
        return '%s?page=%d' % (path, num)

    return {
        'page': page,
        'total_pages': total_pages,
        'total_items': total,
        'page_size': page_size,
        'page_size_options': list(page_size_options),
        'size_param': size_param,
        'offset': offset,
        'from_': offset + 1 if total else 0,
        'to': min(offset + page_size, total),
        'numbers': numbers,
        'item_label': item_label,
        'urls': {n: url(n) for n in numbers if n != ELLIPSIS},
        'prev_url': url(max(1, page - 1)),
        'next_url': url(min(total_pages, page + 1)),
        'base_url': path,
        'hidden': [],
    }


@tagged('post_install', '-at_install', 'wujia_pagination_e3')
class TestPaginationTemplate(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = load_vi(cls.env)

    def _render(self, pgn):
        arch = ('<t t-name="wujia_portal_layout.wj_pgn_probe">'
                '<div><t t-call="%s"/></div></t>') % TMPL
        view = self.env['ir.ui.view'].create({
            'name': 'wj_pgn_probe', 'type': 'qweb',
            'key': 'wujia_portal_layout.wj_pgn_probe', 'arch_db': arch,
        })
        rendered = self.env['ir.qweb']._render(view.id, {'pgn': pgn})
        return html.fromstring(rendered)

    def test_mot_trang_thi_khong_render_gi(self):
        root = self._render(_pgn(5, 1, 10, path='/x'))
        self.assertEqual(root.xpath('.//nav'), [])

    def test_khong_co_pgn_thi_khong_no(self):
        self.assertEqual(self._render(None).xpath('.//nav'), [])

    def test_nav_co_nhan_va_trang_hien_tai_co_aria_current(self):
        root = self._render(_pgn(30, 2, 10, path='/x'))
        nav = root.xpath('.//nav[@class="wj-pagination"]')
        self.assertEqual(len(nav), 1)
        self.assertEqual(nav[0].get('aria-label'), 'Phân trang')
        cur = root.xpath('.//*[@aria-current="page"]')
        self.assertEqual([e.text.strip() for e in cur], ['2'])

    def test_nut_truoc_sau_co_ten_doc_duoc(self):
        root = self._render(_pgn(30, 2, 10, path='/x'))
        labels = [e.text.strip()
                  for e in root.xpath('.//span[@class="wj-pagination__label"]')]
        self.assertEqual(labels, ['Trang trước', 'Trang sau'])

    def test_trang_dau_thi_nut_truoc_khong_phai_link(self):
        root = self._render(_pgn(30, 1, 10, path='/x'))
        disabled = root.xpath('.//*[@aria-disabled="true"]')
        self.assertEqual(len(disabled), 1)
        self.assertEqual(disabled[0].tag, 'span')
        self.assertIn('is-disabled', disabled[0].get('class'))

    def test_trang_cuoi_thi_nut_sau_khong_phai_link(self):
        root = self._render(_pgn(30, 3, 10, path='/x'))
        disabled = root.xpath('.//*[@aria-disabled="true"]')
        self.assertEqual(len(disabled), 1)
        self.assertEqual(
            disabled[0].xpath('.//span[@class="wj-pagination__label"]')[0].text.strip(),
            'Trang sau')

    def test_khong_bao_gio_dung_href_thang(self):
        root = self._render(_pgn(30, 2, 10, path='/x'))
        hrefs = root.xpath('.//a/@href')
        self.assertTrue(hrefs)
        self.assertNotIn('#', ''.join(hrefs))

    def test_nhan_trang_x_tren_y_cho_mobile(self):
        root = self._render(_pgn(30, 2, 10, path='/x'))
        status = root.xpath('.//span[@class="wj-pagination__status"]')
        self.assertEqual(len(status), 1)
        self.assertEqual(' '.join(status[0].text_content().split()), 'Trang 2 / 3')

    def test_count_dung_don_vi_cua_man_hinh(self):
        root = self._render(_pgn(30, 1, 10, path='/x', item_label='yêu cầu'))
        count = root.xpath('.//span[@class="wj-pagination__count"]')[0]
        self.assertEqual(' '.join(count.text_content().split()),
                         'Hiển thị 1–10 / 30 yêu cầu')

    def test_o_page_size_chi_hien_khi_vuot_option_nho_nhat(self):
        it = dict(path='/x', page_size_options=(10, 20, 50))
        # Biên 10 là chỗ phân biệt "> min" với ">= min" — bỏ biên là assert rỗng.
        for total in (9, 10):
            self.assertEqual(self._render(_pgn(total, 1, 10, **it)).xpath('.//select'),
                             [], 'total=%d không được hiện ô page-size' % total)
        self.assertEqual(
            len(self._render(_pgn(11, 1, 10, **it)).xpath('.//select')), 1)

    def test_mot_trang_ma_con_o_page_size_thi_an_o_mobile(self):
        """Chọn 50 còn 20 bản ghi: PC vẫn bấm về 10 được, mobile không để ô trống."""
        root = self._render(_pgn(20, 1, 50, path='/x',
                                        page_size_options=(10, 20, 50)))
        nav = root.xpath('.//nav')[0]
        self.assertIn('is-navless', nav.get('class'))
        self.assertEqual(nav.xpath('.//div[@class="wj-pagination__nav"]'), [])

    def test_o_page_size_mang_ten_param_cua_route(self):
        root = self._render(_pgn(30, 1, 10, path='/x', size_param='limit',
                                        page_size_options=(10, 20)))
        self.assertEqual(root.xpath('.//select')[0].get('name'), 'limit')


@tagged('post_install', '-at_install', 'wujia_pagination_e3')
class TestPaginationTokens(TransactionCase):
    """Số BA đo được: 36 / radius 10 / gap 8 / chạm 44."""

    def test_token_dung_so_ba(self):
        css = _css('_variables.css')
        for token, value in (('--wj-pgn-size', '36px'), ('--wj-pgn-radius', '10px'),
                             ('--wj-pgn-gap', '8px'), ('--wj-pgn-touch', '44px'),
                             # WJ-PORTAL-UI-006: #9CA3AF chỉ 2.54 — chữ vô hiệu theo token chung ≥4.5
                             ('--wj-pgn-disabled-fg', 'var(--wj-disabled-fg)')):
            self.assertRegex(css, re.escape(token) + r':\s*' + re.escape(value) + r';')

    def test_nut_dung_token_khong_go_so_cung(self):
        body = _css('_components.css').split('.wj-pagination__btn {')[1].split('}')[0]
        self.assertIn('height: var(--wj-pgn-size);', body)
        self.assertIn('min-width: var(--wj-pgn-size);', body)
        self.assertIn('border-radius: var(--wj-pgn-radius);', body)

    def test_vung_cham_44_khong_no_visual(self):
        """BA: chạm >=44 nhưng KHÔNG được tăng chiều cao danh sách."""
        css = _css('_components.css')
        before = css.split('.wj-pagination__btn::before {')[1].split('}')[0]
        self.assertIn('var(--wj-pgn-touch)', before)
        self.assertIn('position: absolute;', before)

    def test_content_card_khong_khoa_chieu_cao(self):
        """height:100% khoá card ⇒ bảng dài tràn ra đè lên pager (bắt được ở E3a)."""
        body = _css('_components.css').split('.wujia-content-card {')[1].split('}')[0]
        self.assertIn('min-height: 100%;', body)
        self.assertNotRegex(body, r'(?<!min-)height:\s*100%')
