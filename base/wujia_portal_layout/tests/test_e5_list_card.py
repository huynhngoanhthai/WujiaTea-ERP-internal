"""E5 — CMP-LC-001 ListCard: hợp đồng template `wj_list_card` + `wj_list_card_row`.

Bám cột `Kết quả mong muốn` của `UI-LISTCARD-001` (STT 136): tên trái / state phải,
2–3 hàng phụ cột linh hoạt, token p12·r12·gap8 (header–body 8, gap hàng 6–8),
title 15–16/600, badge 12, metadata 13–14, không divider/shadow nội bộ.

Khung chỉ giữ hợp đồng template + CSS của chính nó (luật F5b); call site của từng
màn nằm ở `wujia_portal_base/tests/test_scan_e5_list_card.py`.
"""
import os
import re

from lxml import html

from odoo.tests import TransactionCase, tagged

TMPL = 'wujia_portal_layout.wj_list_card'
ROW = 'wujia_portal_layout.wj_list_card_row'
HERE = os.path.dirname(__file__)
CSS_DIR = os.path.join(HERE, '..', 'static', 'assets', 'css')


def _css(name):
    with open(os.path.join(CSS_DIR, name), encoding='utf-8') as fh:
        return re.sub(r'/\*.*?\*/', '', fh.read(), flags=re.S)


def _resolved(block):
    """Thay `var(--x)` bằng giá trị trong `_variables.css` (UI-LISTCARD-002 đưa số vào token)."""
    tokens = dict(re.findall(r'(--[\w-]+)\s*:\s*([^;]+);', _css('_variables.css')))
    return re.sub(r'var\((--[\w-]+)\)', lambda m: tokens.get(m.group(1), m.group(0)).strip(), block)


def _block(css, selector):
    """Khối rule theo selector đúng chữ. Phải nuốt khoảng trắng trước `{`: rule
    một dòng được canh cột nên `selector + " {"` không khớp (bẫy đã dính 1 lần)."""
    m = re.search(re.escape(selector) + r'\s*\{', css)
    assert m, 'không thấy selector %r' % selector
    return css[m.start():css.index('}', m.start()) + 1]


@tagged('post_install', '-at_install', 'wujia_list_card_e5')
class TestListCardTemplate(TransactionCase):

    def _render(self, tmpl=TMPL, slots=None, **ctx):
        sets = ''.join('<t t-set="%s" t-value="%s"/>' % (k, v) for k, v in ctx.items())
        sets += ''.join('<t t-set="%s">%s</t>' % (k, v) for k, v in (slots or {}).items())
        arch = ('<t t-name="wujia_portal_layout.wj_lc_probe"><div class="wj-data-item wj-lc">'
                '<t t-call="%s">%s</t></div></t>') % (tmpl, sets)
        view = self.env['ir.ui.view'].create({
            'name': 'wj_lc_probe', 'type': 'qweb',
            'key': 'wujia_portal_layout.wj_lc_probe', 'arch_db': arch,
        })
        return html.fromstring(self.env['ir.qweb']._render(view.id, {}))

    def _card(self, **extra):
        ctx = {'lc_name': "'S00653'"}
        slots = {'lc_state': '<span class="wj-status-badge wj-status-badge--compact">Chờ</span>'}
        slots.update(extra.pop('slots', {}))
        ctx.update(extra)
        return self._render(slots=slots, **ctx)

    # ---------------------------------------------------------------- anatomy
    def test_ten_trai_trang_thai_phai(self):
        """LC-03/LC-04: tên và badge cùng một hàng head, tên đứng TRƯỚC badge."""
        doc = self._card()
        head = doc.xpath('.//span[@class="wj-lc__head"]')
        self.assertEqual(len(head), 1, 'thiếu đúng một hàng head')
        order = [el.get('class') for el in head[0].iterchildren()]
        self.assertEqual(order, ['wj-lc__lead', 'wj-lc__state'],
                         'thứ tự phải là tên rồi mới tới trạng thái')
        self.assertEqual(doc.xpath('.//span[@class="wj-lc__name"]')[0].text, 'S00653')

    def test_khong_co_state_thi_khong_do_o_rong(self):
        """LC-04: "một trạng thái chính NẾU CÓ" — thiếu badge thì không đẻ ô rỗng."""
        doc = self._render(lc_name="'S1'")
        self.assertFalse(doc.xpath('.//span[@class="wj-lc__state"]'))

    def test_hang_phu_nhan_va_gia_tri(self):
        """LC-05/LC-06: mỗi hàng phụ = nhãn + giá trị; thiếu nhãn vẫn hợp lệ."""
        doc = self._render(
            tmpl=ROW, lcr_value="'17:59 · 19/09/2026'",
            slots={'lcr_label': 'Ngày đặt'})
        self.assertEqual(doc.xpath('.//span[@class="wj-lc__label"]')[0].text.strip(), 'Ngày đặt')
        self.assertEqual(doc.xpath('.//span[@class="wj-lc__value"]')[0].text, '17:59 · 19/09/2026')
        trong = self._render(tmpl=ROW, lcr_value="'—'")
        self.assertFalse(trong.xpath('.//span[@class="wj-lc__label"]'))

    def test_truong_dai_chiem_ca_hang(self):
        """LC-05: lcr_full ⇒ hàng riêng, nhãn nằm trên giá trị."""
        doc = self._render(tmpl=ROW, lcr_value="'Lý do rất dài'", lcr_full='True',
                           slots={'lcr_label': 'Lý do'})
        self.assertIn('wj-lc__row--full', doc.xpath('.//span[contains(@class, "wj-lc__row")]')[0].get('class'))

    def test_gia_tri_nhan_manh(self):
        """LC-06: "Tổng tiền có thể đậm hơn" — bằng modifier, không CSS theo route."""
        doc = self._render(tmpl=ROW, lcr_value="'73.600,00 $'", lcr_strong='True')
        self.assertIn('wj-lc__value--strong', doc.xpath('.//span[contains(@class,"wj-lc__value")]')[0].get('class'))

    def test_khong_boc_them_lop_vo(self):
        """LC-01: component là RUỘT — không được đẻ thêm khung bên trong card."""
        doc = self._card()
        # html.fromstring trả về CHÍNH thẻ bọc khi fragment có một gốc duy nhất.
        item = doc if 'wj-data-item' in (doc.get('class') or '') \
            else doc.xpath('.//div[contains(@class, "wj-data-item")]')[0]
        con = [el.get('class') for el in item.iterchildren()]
        self.assertEqual(con, ['wj-lc__head'], 'component tự bọc thêm lớp vỏ')

    def test_actions_la_slot_rieng(self):
        """LC-11: action có vùng riêng, không lồng vào hàng tên."""
        doc = self._card(slots={'lc_actions': '<button type="button">Chọn</button>'})
        act = doc.xpath('.//span[@class="wj-lc__actions"]')
        self.assertEqual(len(act), 1)
        self.assertFalse(doc.xpath('.//span[@class="wj-lc__head"]//button'))

    # ------------------------------------------------------------------- CSS
    def test_token_khung_theo_ba(self):
        """LC-07/LC-25: header–body 8 · gap hàng 6–8 · title 15–16/600 · meta 13–14."""
        css = _css('_components.css')
        card = _block(css, '.wj-data-item.wj-lc')
        self.assertRegex(card, r'flex-direction:\s*column')
        self.assertRegex(card, r'gap:\s*8px', 'header–body phải là 8')
        name = _resolved(_block(css, '.wj-lc__name'))
        self.assertRegex(name, r'font-size:\s*1[56]px')
        self.assertRegex(name, r'font-weight:\s*600')
        row = _resolved(_block(css, '.wj-lc__row'))
        self.assertRegex(row, r'font-size:\s*1[34]px')
        gap = re.search(r'gap:\s*\d+px\s+(\d+)px', row)
        self.assertTrue(gap and 6 <= int(gap.group(1)) <= 8, 'gap hàng phải 6–8')
        body = _block(css, '.wj-lc__body')
        self.assertRegex(body, r'gap:\s*[678]px')

    def test_khong_dang_rieng_trong_component(self):
        """LC-01: dáng ngoài (viền/bo/đệm) vẫn của .wj-data-item — ruột không giành."""
        css = _css('_components.css')
        card = _block(css, '.wj-data-item.wj-lc')
        for cam in ('border:', 'border-radius', 'padding:', 'box-shadow'):
            self.assertNotIn(cam, card, 'ruột ListCard giành dáng của CMP-DL-001: %s' % cam)

    def test_badge_compact_la_modifier_chung(self):
        """LC-04/LC-25: chữ 12 làm bằng modifier CHUNG của CMP-SB-001."""
        css = _css('_components.css')
        blk = _block(css, '.wj-status-badge--compact')
        self.assertRegex(blk, r'font-size:\s*12px')
        # chỉ đổi chữ (cỡ + line-height I10) — cao/bo/màu vẫn là chuẩn E2
        self.assertNotRegex(blk, r'(?<![\w-])height\s*:')
        self.assertNotIn('background', blk)

    def test_ten_va_gia_tri_khong_bi_cat(self):
        """LC-03/LC-10: cấm ellipsis mã và cấm tách số tiền."""
        css = _css('_components.css')
        for sel in ('.wj-lc__name', '.wj-lc__value'):
            blk = _block(css, sel)
            self.assertNotIn('text-overflow', blk)
            self.assertNotIn('white-space: nowrap', blk)
            self.assertIn('overflow-wrap: anywhere', blk)

    def test_badge_xuong_hang_can_phai(self):
        """LC-04: hẹp quá thì badge xuống hàng CĂN PHẢI, không chồng lên tên."""
        css = _css('_components.css')
        blk = _block(css, '.wj-lc__state')
        self.assertRegex(blk, r'margin-left:\s*auto')
        self.assertRegex(blk, r'text-align:\s*right')

    # ------------------------------------------------------------------
    # E5c — nhịp và bề ngang: số của TRANG, không phải của card (LC-07/LC-08)
    # ------------------------------------------------------------------
    def test_dem_item_la_12_deu_bon_phia(self):
        """LC-07: đệm 12. 14 ngang trước đây là để bù gutter 16 — gutter nay 12."""
        css = _css('_components.css')
        for variant in ('compact-row', 'detail-card'):
            blk = _block(css, '.wj-data-list--%s .wj-data-item' % variant)
            self.assertRegex(blk, r'padding:\s*12px;',
                             'variant %s phải đệm 12 đều bốn phía' % variant)

    def test_listcard_khong_tu_them_gutter(self):
        """LC-08: gutter là việc của TRANG. Component không được khai margin ngang."""
        css = _css('_components.css')
        for sel in ('.wj-data-item.wj-lc', '.wj-lc__head', '.wj-lc__body'):
            blk = _block(css, sel)
            self.assertNotRegex(blk, r'margin-(left|right|inline)',
                                '%s tự thêm lề ngang — gutter phải do trang cấp' % sel)

    def test_nhip_loc_bang_hai_nhip_trang(self):
        """G2: thanh lọc → nội dung kế = 16 = gap trang (8) + đúng một nhịp nữa.

        Khai bằng TOKEN chứ không phải 8px cứng: trang đổi nhịp thì thanh lọc đổi
        theo, khỏi phải nhớ hai con số ở hai nơi.
        """
        blk = _block(_css('_components.css'), '.wj-filter-card')
        self.assertRegex(blk, r'margin-bottom:\s*var\(--wujia-mshell-content-gap\)')

    def test_token_gutter_bang_12(self):
        """LC-08 (BA Q2): gutter danh sách mobile 12, khai ở khối mobile của token."""
        css = _css('_variables.css')
        m = re.search(r'@media \(max-width: 991\.98px\)(.*)$', css, re.S)
        self.assertTrue(m)
        self.assertRegex(css, r'--wujia-mshell-content-pad-x:\s*12px')

    def test_link_hanh_dong_du_vung_cham(self):
        """A11y ≥44: chữ "Chọn" chỉ cao 21 — nới bằng đệm, bù lề âm để card không cao thêm."""
        blk = _block(_css('_components.css'), '.wj-lc__link')
        self.assertRegex(blk, r'display:\s*inline-(block|flex)',
                         'inline thường không ăn đệm dọc nên vùng chạm không nới được')
        pad = re.search(r'padding:\s*(\d+)px\s+(\d+)px', blk)
        mar = re.search(r'margin:\s*-(\d+)px\s+-(\d+)px', blk)
        self.assertTrue(pad and mar, 'thiếu cặp đệm + lề âm cho vùng chạm')
        self.assertGreaterEqual(int(pad.group(1)) * 2 + 20, 44, 'vùng chạm dọc < 44')
        self.assertEqual(pad.groups(), mar.groups(), 'lề âm phải bù đúng đệm')
