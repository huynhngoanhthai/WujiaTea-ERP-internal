"""E6 — CMP-BTN-001 Button/IconButton: hợp đồng template `wj_button` + `wj_icon_button`.

Bám dòng 40 tab `UI Component` (BA Confirmed 26/08/2026): 6 variant, 3 bậc size,
PC 32/40/46 · mobile 36/44/48, chạm >=44, radius 8 (sm) / 12 (md-lg),
typo 13/18/600 · 14/20/700 · 15/22/700, loading giữ nguyên bề rộng.

Khung chỉ giữ hợp đồng template + CSS của chính nó (luật F5b); call site của từng
màn nằm ở test của module sở hữu màn (`wujia_portal_support/tests/test_button_e6a.py`…).
"""
import os
import re

from lxml import html

from odoo.tests import TransactionCase, tagged

BTN = 'wujia_portal_layout.wj_button'
ICON = 'wujia_portal_layout.wj_icon_button'
HERE = os.path.dirname(__file__)
CSS_DIR = os.path.join(HERE, '..', 'static', 'assets', 'css')


def _css(name):
    with open(os.path.join(CSS_DIR, name), encoding='utf-8') as fh:
        return re.sub(r'/\*.*?\*/', '', fh.read(), flags=re.S)


def _block(css, selector):
    """Gộp thân MỌI rule khai cho đúng selector này — kể cả khi nó nằm trong một
    DANH SÁCH selector (`.wj-btn, .wj-iconbtn { … }`) hay trong `@media`.

    `test_e5_list_card.py` tìm bằng `selector + "{"` vì ListCard viết mỗi rule một
    selector; atom Button thì dùng chung rule cho hai họ nên cách đó không thấy gì.
    So theo TOKEN đã tách dấu phẩy, không phải chuỗi con — `.wj-btn` không được
    khớp nhầm `.wj-btn--sm` hay `.wj-empty-state > .wj-btn`."""
    than = [body for sel, body in re.findall(r'([^{}]+)\{([^{}]*)\}', css)
            if selector in [p.strip() for p in sel.split(',')]]
    assert than, 'không thấy selector %r' % selector
    return '\n'.join(than)


def _mobile(css):
    """Khối token mobile ở CUỐI `_variables.css` — số của <=991.98px."""
    m = re.search(r'@media \(max-width: 991\.98px\)(.*)$', css, re.S)
    assert m, 'thiếu khối token mobile'
    return m.group(1)


@tagged('post_install', '-at_install', 'wujia_button_e6')
class TestButtonTemplate(TransactionCase):

    def _render(self, tmpl=BTN, **ctx):
        sets = ''.join('<t t-set="%s" t-value="%s"/>' % (k, v) for k, v in ctx.items())
        arch = ('<t t-name="wujia_portal_layout.wj_btn_probe"><div>'
                '<t t-call="%s">%s</t></div></t>') % (tmpl, sets)
        view = self.env['ir.ui.view'].create({
            'name': 'wj_btn_probe', 'type': 'qweb',
            'key': 'wujia_portal_layout.wj_btn_probe', 'arch_db': arch,
        })
        doc = html.fromstring(self.env['ir.qweb']._render(view.id, {}))
        return doc.xpath('.//a | .//button')[0]

    # -------------------------------------------------------------- template
    def test_variant_va_size_ra_dung_class(self):
        """BT-1/BT-2: variant + size là CLASS, không phải style rời."""
        el = self._render(btn_label="'Gửi'")
        self.assertEqual(el.get('class'), 'wj-btn wj-btn--primary', 'mặc định phải là primary/md')
        for size in ('sm', 'lg'):
            el = self._render(btn_label="'Gửi'", btn_size="'%s'" % size)
            self.assertIn('wj-btn--%s' % size, el.get('class'))
        for variant in ('secondary', 'outline', 'danger', 'ghost'):
            el = self._render(btn_label="'X'", btn_variant="'%s'" % variant)
            self.assertIn('wj-btn--%s' % variant, el.get('class'))

    def test_md_khong_de_class_thua(self):
        """Bậc mặc định không sinh `wj-btn--md` — size md là chính khối gốc."""
        self.assertNotIn('wj-btn--md', self._render(btn_label="'X'", btn_size="'md'").get('class'))

    def test_dieu_huong_la_link_hanh_dong_la_button(self):
        """BT-8: có `btn_href` ⇒ <a href> thật; không có ⇒ <button> submit."""
        link = self._render(btn_label="'Tạo'", btn_href="'/portal/return/new'")
        self.assertEqual(link.tag, 'a')
        self.assertEqual(link.get('href'), '/portal/return/new')
        btn = self._render(btn_label="'Gửi'")
        self.assertEqual(btn.tag, 'button')
        self.assertEqual(btn.get('type'), 'submit')
        self.assertEqual(self._render(btn_label="'Hủy'", btn_type="'button'").get('type'), 'button')

    def test_icon_button_bat_buoc_ten_doc_duoc(self):
        """BT-6: IconButton icon-only phải có accessible name — và đọc được bằng
        CẢ hai đường (screen reader `aria-label`, chuột `title`)."""
        el = self._render(tmpl=ICON, btn_icon="'fa fa-eye'", btn_aria_label="'Xem ticket'")
        self.assertEqual(el.get('aria-label'), 'Xem ticket')
        self.assertEqual(el.get('title'), 'Xem ticket')
        self.assertFalse((el.text or '').strip(), 'icon button không được có chữ')

    def test_icon_button_mac_dinh_secondary(self):
        """Nút phụ ở hàng danh sách là số đông ⇒ mặc định secondary, không primary."""
        el = self._render(tmpl=ICON, btn_icon="'fa fa-eye'", btn_aria_label="'Xem'")
        self.assertEqual(el.get('class'), 'wj-iconbtn wj-iconbtn--secondary')
        self.assertIn('wj-iconbtn--sm',
                      self._render(tmpl=ICON, btn_icon="'fa fa-eye'", btn_size="'sm'",
                                   btn_aria_label="'Xem'").get('class'))

    def test_class_call_site_khong_de_mat_class_atom(self):
        """`btn_class` chỉ ghép thêm (bố cục), không thay hợp đồng."""
        el = self._render(btn_label="'Gửi'", btn_class="'mt-3'", btn_block='True')
        cls = el.get('class').split()
        self.assertEqual(cls[:2], ['wj-btn', 'wj-btn--primary'])
        self.assertIn('wj-btn--block', cls)
        self.assertIn('mt-3', cls)

    def test_attrs_tho_di_qua_duoc(self):
        """Form Odoo cần `name`/`value`/`id` — atom không được nuốt mất."""
        el = self._render(btn_label="'Đọc hết'",
                          btn_attrs="{'id': 'wj-noti-bulk-read', 'name': 'act'}")
        self.assertEqual(el.get('id'), 'wj-noti-bulk-read')
        self.assertEqual(el.get('name'), 'act')

    # ------------------------------------------------------------------- CSS
    def test_sau_con_so_size_theo_ba(self):
        """BT-2: PC 32/40/46 · mobile 36/44/48, khai bằng token chứ không px cứng."""
        var = _css('_variables.css')
        root = var[:re.search(r'@media \(max-width: 991\.98px\)', var).start()]
        for tok, px in (('--wj-btn-h-sm', 32), ('--wj-btn-h-md', 40), ('--wj-btn-h-lg', 46),
                        ('--wj-btn-icon-sm', 32), ('--wj-btn-icon-md', 40)):
            self.assertRegex(root, re.escape(tok) + r':\s*%dpx' % px, 'PC %s' % tok)
        mob = _mobile(var)
        for tok, px in (('--wj-btn-h-sm', 36), ('--wj-btn-h-md', 44), ('--wj-btn-h-lg', 48),
                        ('--wj-btn-icon-sm', 36), ('--wj-btn-icon-md', 44)):
            self.assertRegex(mob, re.escape(tok) + r':\s*%dpx' % px, 'mobile %s' % tok)

        css = _css('_components.css')
        for sel, tok in (('.wj-btn', '--wj-btn-h-md'), ('.wj-btn--sm', '--wj-btn-h-sm'),
                         ('.wj-btn--lg', '--wj-btn-h-lg')):
            self.assertRegex(_block(css, sel), r'height:\s*var\(%s\)' % tok,
                             '%s phải lấy số từ token, không px cứng' % sel)

    def test_typo_ba_bac(self):
        """BT-2: 13/18/600 · 14/20/700 · 15/22/700."""
        css = _css('_components.css')
        for sel, (fs, lh) in (('.wj-btn', (14, 20)), ('.wj-btn--sm', (13, 18)),
                              ('.wj-btn--lg', (15, 22))):
            blk = _block(css, sel)
            self.assertRegex(blk, r'font-size:\s*%dpx' % fs)
            self.assertRegex(blk, r'line-height:\s*%dpx' % lh)
        self.assertRegex(_block(css, '.wj-btn'), r'font-weight:\s*700')
        self.assertRegex(_block(css, '.wj-btn--sm'), r'font-weight:\s*600')

    def test_radius_sm_8_md_lg_12(self):
        css = _css('_components.css')
        var = _css('_variables.css')
        self.assertRegex(var, r'--wj-btn-radius-sm:\s*8px')
        self.assertRegex(var, r'--wj-btn-radius:\s*12px')
        self.assertRegex(_block(css, '.wj-btn'), r'border-radius:\s*var\(--wj-btn-radius\)')
        self.assertRegex(_block(css, '.wj-btn--sm'), r'border-radius:\s*var\(--wj-btn-radius-sm\)')
        # lg dùng chung 12 của md ⇒ không được tự khai lại radius
        self.assertNotIn('border-radius', _block(css, '.wj-btn--lg'))

    def test_vung_cham_44_bang_pseudo_khong_phinh_visual(self):
        """BT-3: bậc sm trên mobile chỉ cao 36 ⇒ nới vùng chạm bằng pseudo."""
        css = _css('_components.css')
        blk = _block(css, '.wj-btn--sm::before')
        self.assertRegex(blk, r'position:\s*absolute')
        self.assertRegex(blk, r'min-width:\s*44px')
        self.assertRegex(blk, r'height:\s*44px')
        self.assertIn('.wj-iconbtn--sm::before', css, 'icon button sm cũng phải có vùng chạm')
        m = re.search(r'@media \(max-width: 991\.98px\) \{[^@]*?\.wj-btn--sm::before', css, re.S)
        self.assertTrue(m, 'vùng chạm phải nằm trong khối mobile — PC không cần phình')

    def test_loading_giu_nguyen_be_rong(self):
        """BT-10: loading không được co nút (nhãn tàng hình tại chỗ, spinner vẽ đè)."""
        css = _css('_components.css')
        blk = _block(css, '.wj-btn.is-loading')
        self.assertRegex(blk, r'color:\s*transparent', 'nhãn phải tàng hình, không bị gỡ')
        for cam in ('width', 'padding', 'font-size'):
            self.assertNotIn(cam, blk, 'loading đụng %s ⇒ nút đổi bề rộng' % cam)
        self.assertRegex(_block(css, '.wj-btn.is-loading::after'), r'position:\s*absolute')

    def test_disabled_khong_bam_duoc(self):
        blk = _block(_css('_components.css'), '.wj-btn:disabled')
        self.assertRegex(blk, r'pointer-events:\s*none')
        self.assertRegex(blk, r'opacity:\s*\.55')

    def test_khong_gianh_trang_thai_chung_cua_c6(self):
        """C6: hover/pressed của bề mặt trung tính do `_interaction.css` giữ —
        atom chỉ khai thêm cho variant NỀN ĐẬM, không viết lại lần hai."""
        inter = _css('_interaction.css')
        for v in ('secondary', 'outline'):
            self.assertIn('.wj-btn--%s' % v, inter, 'variant %s phải đi theo C6' % v)
        comp = _css('_components.css')
        hover = re.findall(r'\.wj-btn--(\w+)[^{]*:hover', comp)
        self.assertNotIn('secondary', hover, 'hover secondary khai hai nơi ⇒ file sau đè file trước')
        self.assertNotIn('outline', hover)

    def test_khong_dung_vao_ho_cu_cua_khao_sat(self):
        """LIMIT E6: `.wj-pc-btn` còn của nhóm Khảo sát (code anh Thái) — giữ nguyên."""
        # họ cũ sống ở `_pc_components.css` (PC-only), không phải `_components.css`
        self.assertIn('.wj-pc-btn', _css('_pc_components.css'),
                      'không được xoá họ cũ khi Khảo sát còn dùng')
        self.assertRegex(_css('_variables.css'), r'--wujia-btn-height:\s*42px')
