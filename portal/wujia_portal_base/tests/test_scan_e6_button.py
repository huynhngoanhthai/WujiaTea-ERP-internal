"""E6 (quét nhiều module) — call site Button CMP-BTN-001 (`UI-BUTTON-001`).

Khung `wujia_portal_layout` giữ hợp đồng atom (luật F5b); ở đây là sổ "màn nào đã
về atom" cộng bốn luật không màn nào được phá:

  · đủ số call site — đếm >= (bài học E5b2 #2: "có ít nhất một" xanh giả khi màn
    nhiều nút mà rơi mất lớp ở một chỗ);
  · họ class cũ của màn đã migrate biến mất khỏi CẢ view lẫn CSS module;
  · module không tự khai lại `.wj-btn*`/`.wj-iconbtn*` dáng — một implementation;
  · icon-only phải có tên đọc được ngay tại call site.

E6b/E6c thêm màn chỉ bằng cách thêm một dòng vào MIGRATED.
"""
import os
import re

from lxml import etree

from odoo.tests import TransactionCase, tagged

from odoo.addons.wujia_portal_base.tests.css_probe import (
    CUSTOM, _css, _mod_css, _strip_comments, _view,
)

# (module, file view, số call site .wj-btn, số .wj-iconbtn, họ cũ phải biến mất,
#  file CSS module)
MIGRATED = [
    ('wujia_portal_support', 'portal_support.xml', 7, 1,
     ('wj-pc-btn', 'wj-pc-btn--primary', 'wj-pc-btn--secondary', 'btn-primary',
      'btn-secondary', 'btn-sm', 'wj-empty-state-btn'), 'portal_support.css'),
    ('wujia_portal_return', 'portal_return_list.xml', 2, 1,
     ('btn-outline-primary', 'btn-sm', 'wj-empty-state-btn'), 'portal_return.css'),
    ('wujia_portal_return', 'portal_return_form.xml', 4, 0,
     ('wujia-mreturn-btn-cancel', 'wujia-mreturn-btn-submit', 'wj-pc-btn',
      'wj-pc-btn--primary', 'wj-pc-btn--secondary'), 'portal_return.css'),
    ('wujia_portal_notification', 'portal_notification.xml', 4, 0,
     ('wj-pc-btn', 'wj-pc-btn--primary', 'btn-primary', 'btn-sm',
      'wj-empty-state-btn'), 'portal_notification.css'),
    ('wujia_portal_notification', 'header_bell_inherit.xml', 1, 0,
     ('btn-primary', 'btn-sm'), 'portal_notification.css'),
    # --- E6b1 ---
    ('wujia_portal_delivery', 'portal_delivery.xml', 6, 0,
     ('wj-pc-btn', 'wj-pc-btn--primary', 'wj-pc-btn--secondary',
      'wj-pc-dlv-btn-xem', 'wj-empty-state-btn'), 'portal_delivery.css'),
    ('wujia_portal_knowledge', 'portal_knowledge.xml', 3, 0,
     ('btn-secondary', 'wj-empty-state-btn'), 'portal_knowledge.css'),
    ('wujia_portal_info_request', 'portal_info_request_form.xml', 3, 0,
     ('btn-primary', 'btn-secondary', 'btn-outline-primary'), None),
    ('wujia_portal_info_request', 'portal_info_request_list.xml', 0, 1,
     ('btn-sm', 'btn-outline-primary'), None),
    ('wujia_portal_info_request', 'portal_info_request_detail.xml', 1, 0,
     ('btn-outline-danger',), None),
    ('wujia_portal_purchase_history', 'portal_history.xml', 2, 0,
     ('wj-empty-state-btn',), 'portal_history.css'),
    ('wujia_portal_base', 'store_picker_modal.xml', 2, 1,
     ('btn-outline-secondary', 'wj-cta-btn'), 'store_picker.css'),
    ('wujia_portal_base', 'portal_franchises_in_layout.xml', 1, 0,
     ('btn-sm', 'wj-cta-btn'), 'portal_dashboard.css'),
    ('wujia_portal_base', 'portal_franchise_profile.xml', 1, 0,
     ('btn-outline-primary',), 'portal_dashboard.css'),
    # Công nợ: 10 call site về atom. `wj-pc-btn` KHÔNG nằm trong danh sách họ cũ —
    # 3 nút của thanh lọc còn giữ họ đó theo FB-08, và `wj-debt-cta`/`-copy`/
    # `-pc-copy`/`-pc-modal__close` ở lại làm hook bố cục (dáng đã gỡ khỏi CSS).
    ('wujia_portal_debt', 'portal_debt.xml', 5, 5,
     ('wj-debt-pc-pdf',), 'portal_debt.css'),
    # --- E6b2: Đặt hàng/giỏ. `wujia-mcart-del`/`-submit`/`-empty-cta`,
    # `wj-pc-cart-del`/`-submit` và `btn-add-cart-detail` Ở LẠI làm móc JS/bố cục
    # (dáng đã gỡ khỏi portal_order.css) nên không nằm trong danh sách họ cũ.
    ('wujia_portal_sale', 'portal_order_cart.xml', 2, 1,
     ('wj-empty-state-btn',), 'portal_order.css'),
    ('wujia_portal_sale', 'pc_cart_panel.xml', 2, 1,
     ('wj-pc-btn', 'wj-pc-btn--secondary'), 'portal_order.css'),
    ('wujia_portal_sale', 'portal_order_product_detail.xml', 2, 0,
     ('wj-cta-btn', 'btn-outline-secondary'), 'portal_order.css'),
    # --- E6b2: màn auth (CSS ở wujia_portal_layout/static/assets/css ⇒ None,
    # kiểm riêng bằng TestDangAuthVeAtom bên dưới).
    ('wujia_portal_layout', 'login_page.xml', 6, 0,
     ('btn-primary', 'btn-outline-primary', 'btn-block'), None),
    ('wujia_portal_layout', 'forgot_pass.xml', 2, 0,
     ('btn-primary', 'btn-outline-primary', 'btn-block'), None),
    ('wujia_portal_layout', 'change_password_page.xml', 3, 0,
     ('wj-pc-btn', 'wj-pc-btn--primary', 'wj-pc-btn--secondary',
      'wj-pc-btn--disabled', 'btn-primary'), None),
    # --- E6c: màn Thi. Ô ngày/khung giờ/FAB/nút lùi wizard là boundary đọc token
    # (test riêng ở wujia_portal_exam/tests/test_button_e6c.py).
    ('wujia_portal_exam', 'portal_exam.xml', 21, 7,
     ('wj-pc-btn', 'wj-pc-btn--primary', 'wj-pc-btn--secondary', 'wujia-mexam-btn',
      'wujia-mexam-btn-primary', 'wujia-mexam-btn-outline', 'wj-empty-state-btn',
      'wj-exam-pc-navbtn', 'wujia-mexam-cal-navbtn', 'wujia-mexam-person-del'),
     'portal_exam.css'),
]

VARIANT = ('primary', 'secondary', 'outline', 'danger', 'ghost')
SIZE = ('sm', 'lg', 'block')


def _atoms(root, base):
    """Phần tử mang ĐÚNG token lớp gốc — `contains()` sẽ khớp cả `wj-btn--primary`
    lẫn `wj-iconbtn` (bẫy tên con BEM đã dính ở D4e/D5c)."""
    out = []
    for el in root.iter():
        cls = ((el.get('class') or '') + ' ' + (el.get('t-attf-class') or '')).split()
        if base in cls:
            out.append((el, cls))
    return out


@tagged('post_install', '-at_install', 'wujia_button_e6')
class TestButtonCallSites(TransactionCase):

    def test_du_so_call_site(self):
        for module, filename, n_btn, n_icon, _cu, _css in MIGRATED:
            root = _view(module, filename)
            self.assertGreaterEqual(
                len(_atoms(root, 'wj-btn')), n_btn,
                '%s/%s: thiếu call site wj-btn' % (module, filename))
            self.assertGreaterEqual(
                len(_atoms(root, 'wj-iconbtn')), n_icon,
                '%s/%s: thiếu call site wj-iconbtn' % (module, filename))

    def test_moi_atom_mang_dung_mot_variant(self):
        """Không variant ⇒ nút trong suốt không viền; hai variant ⇒ cái sau đè."""
        for module, filename, _nb, _ni, _cu, _css in MIGRATED:
            root = _view(module, filename)
            for base in ('wj-btn', 'wj-iconbtn'):
                for _el, cls in _atoms(root, base):
                    co = [v for v in VARIANT if '%s--%s' % (base, v) in cls]
                    self.assertEqual(len(co), 1,
                                     '%s/%s: %s mang %d variant (%s)'
                                     % (module, filename, base, len(co), ' '.join(cls)))

    def test_icon_only_co_ten_doc_duoc(self):
        """BT-6: 40 link icon-only của PC trước E6 không có tên đọc được nào —
        migrate xong thì cấm tái phạm ngay tại call site."""
        for module, filename, _nb, _ni, _cu, _css in MIGRATED:
            for el, cls in _atoms(_view(module, filename), 'wj-iconbtn'):
                ten = (el.get('aria-label') or el.get('t-att-aria-label')
                       or el.get('t-attf-aria-label') or '')
                self.assertTrue(ten.strip(),
                                '%s/%s: icon button thiếu aria-label (%s)'
                                % (module, filename, ' '.join(cls)))

    def test_khong_con_ho_class_cu(self):
        """Hai bộ dáng cùng sống là nguồn hồi quy specificity đã trả giá ở D3/D4."""
        for module, filename, _nb, _ni, cu, css_file in MIGRATED:
            with open(os.path.join(CUSTOM, module, 'views', filename), encoding='utf-8') as fh:
                view = fh.read()
            css = _strip_comments(_mod_css(module, css_file)) if css_file else ''
            for ho in cu:
                self.assertNotRegex(view, r'%s(?![-\w])' % re.escape(ho),
                                    '%s/%s: họ cũ %s còn trong view' % (module, filename, ho))
                self.assertNotRegex(css, r'\.%s(?![-\w])' % re.escape(ho),
                                    '%s: họ cũ %s còn rule CSS' % (module, ho))

    def test_module_khong_khai_lai_dang_cua_atom(self):
        """BT-11 một implementation: module chỉ được khai BỐ CỤC (flex/margin/
        width trong ngữ cảnh của mình), cấm giành dáng (cao/bo/nền/viền/chữ)."""
        cam = ('height', 'border-radius', 'background', 'border', 'font-size',
               'font-weight', 'padding', 'color')
        thay = []
        for root, _dirs, files in os.walk(CUSTOM):
            if '/static/' not in root or not root.endswith('css'):
                continue
            if os.sep + 'wujia_portal_layout' + os.sep in root:
                continue
            for fn in files:
                if not fn.endswith('.css'):
                    continue
                css = _strip_comments(open(os.path.join(root, fn), encoding='utf-8').read())
                for sel, body in re.findall(r'([^{}]+)\{([^{}]*)\}', css):
                    if not re.search(r'\.wj-(icon)?btn(?![-\w])|\.wj-(icon)?btn--', sel):
                        continue
                    khai = {d.split(':')[0].strip() for d in body.split(';') if ':' in d}
                    xau = sorted(k for k in khai if any(k == c or k.startswith(c + '-')
                                                        for c in cam))
                    if xau:
                        thay.append('%s: %s { %s }' % (fn, sel.strip(), ', '.join(xau)))
        self.assertFalse(thay, 'module giành dáng của atom:\n' + '\n'.join(thay))

    def test_class_di_kem_atom_khong_gianh_dang(self):
        """E6c M8: class đứng CÙNG phần tử với atom (`wj-exam-pc-back`) cũng không được khai dáng."""
        atom = re.compile(r'^wj-(icon)?btn(--[\w-]+)?$')
        cam = ('height', 'border-radius', 'background', 'border', 'font-size',
               'font-weight', 'padding', 'color')
        kem = set()
        for root, _dirs, files in os.walk(CUSTOM):
            if not os.path.relpath(root, CUSTOM).startswith('wujia_portal'):
                continue
            for fn in files:
                path = os.path.join(root, fn)
                if fn.endswith('.xml') and os.sep + 'views' in root:
                    classes = [((el.get('class') or '') + ' ' + (el.get('t-attf-class') or '')).split()
                               for el in etree.parse(path).iter() if isinstance(el.tag, str)]
                elif fn.endswith('.js') and os.sep + 'static' + os.sep in path:
                    classes = [c.split() for c in re.findall(r'class="([^"]*wj-(?:icon)?btn[^"]*)"',
                                                             open(path, encoding='utf-8').read())]
                else:
                    continue
                for cls in classes:
                    if any(atom.match(c) for c in cls):
                        kem |= {c for c in cls if not atom.match(c) and re.match(r'^[a-z][\w-]*$', c)}
        thay = []
        for root, _dirs, files in os.walk(CUSTOM):
            if '/static/' not in root or os.sep + 'wujia_portal_layout' + os.sep in root:
                continue
            for fn in (f for f in files if f.endswith('.css')):
                css = _strip_comments(open(os.path.join(root, fn), encoding='utf-8').read())
                for sel, body in re.findall(r'([^{}@]+)\{([^{}]*)\}', css):
                    for s in sel.split(','):
                        cuoi = re.split(r'[\s>+~]+', s.strip())[-1]
                        if '.is-' in cuoi or not set(re.findall(r'\.([\w-]+)', cuoi)) & kem:
                            continue
                        khai = {d.split(':')[0].strip() for d in body.split(';') if ':' in d}
                        xau = sorted(k for k in khai if any(k == c or k.startswith(c + '-') for c in cam))
                        if xau:
                            thay.append('%s: %s { %s }' % (fn, s.strip(), ', '.join(xau)))
        self.assertTrue(kem, 'không gom được class đi kèm atom — test rỗng')
        self.assertFalse(thay, 'class đi kèm atom giành dáng:\n' + '\n'.join(thay))

    def test_ho_cu_cua_khao_sat_khong_bi_dung(self):
        """LIMIT E6: `wujia_portal_inspection` (code anh Thái) còn dùng `.wj-pc-btn`
        ở 3 template + 1 JS ⇒ E6 thu hẹp, KHÔNG xoá."""
        con = []
        for root, _dirs, files in os.walk(os.path.join(CUSTOM, 'wujia_portal_inspection')):
            for fn in files:
                if fn.endswith(('.xml', '.js')):
                    txt = open(os.path.join(root, fn), encoding='utf-8').read()
                    if re.search(r'wj-pc-btn(?![-\w])', txt):
                        con.append(fn)
        self.assertTrue(con, 'Khảo sát hết dùng .wj-pc-btn ⇒ gỡ LIMIT và xoá họ cũ')


# Thanh lọc mà E4 đã đo và ký duyệt (`docs/e4-filter-inventory.md`): nút bên trong
# giữ chiều cao của Filter (FB-08) chứ KHÔNG về bậc size của CMP-BTN-001. Ba màn
# đầu tự dựng thanh lọc, phần còn lại gọi component `wj_filter_bar`.
FILTER_FORMS = (
    ('wujia_portal_debt', 'portal_debt.xml', 'wj-debt-filter'),
    ('wujia_portal_debt', 'portal_debt.xml', 'wj-debt-pc-filter'),
    ('wujia_portal_sale', 'portal_order_catalog.xml', 'wujia-morder-search'),
)


@tagged('post_install', '-at_install', 'wujia_button_e6')
class TestRanhGioiThanhLoc(TransactionCase):
    """Cùng một tên class `wj-pc-btn--primary` trong `portal_debt.xml` vừa là nút
    *Tìm kiếm* của thanh lọc (giữ 42) vừa là nút *Thanh toán số còn lại* (về 40).
    Tên class không phân biệt được hai vai trò ⇒ luật phải đọc theo NGỮ CẢNH, và
    phải canh cả hai chiều để không lượt nào kéo nhầm nút của cụm kia."""

    def _trong_thanh_loc(self, module, filename, moc):
        root = _view(module, filename)
        for node in root.iter():
            cls = (node.get('class') or '').split()
            if moc in cls:
                yield node

    def test_nut_thanh_loc_khong_bi_keo_ve_atom(self):
        """Chiều A — E6 không được migrate nút nằm trong thanh lọc."""
        for module, filename, moc in FILTER_FORMS:
            for form in self._trong_thanh_loc(module, filename, moc):
                for el in form.iter():
                    cls = ((el.get('class') or '') + ' '
                           + (el.get('t-attf-class') or '')).split()
                    self.assertNotIn(
                        'wj-btn', cls,
                        '%s: nút trong thanh lọc %s đã bị kéo về atom, mất 42/38 của FB-08'
                        % (filename, moc))
                    self.assertNotIn('wj-iconbtn', cls, filename)

    def test_nut_thanh_loc_doc_token_dung_chung(self):
        """Chiều B — ba nút lọc tự dựng phải đọc token chiều cao của Filter, để
        đổi FB-08 một chỗ là cả 21 thanh lọc theo, không sót màn tự dựng.

        Kiểm TỪNG khối, không chỉ kiểm "file có nhắc token": một mũi mutation đổi
        riêng nút lọc PC của Công nợ về 40px vẫn lọt nếu chỉ tìm chuỗi cả file."""
        khoi = (('wujia_portal_debt', 'portal_debt.css', '.wj-debt-filter__go'),
                ('wujia_portal_debt', 'portal_debt.css', '.wj-debt-pc-filter .wj-pc-btn'),
                ('wujia_portal_sale', 'portal_order.css', '.wujia-morder-search-btn'))
        for module, css_file, selector in khoi:
            css = _strip_comments(_mod_css(module, css_file))
            self.assertIn(selector, css, '%s: mất khối %s' % (css_file, selector))
            body = css[css.index(selector):]
            body = body[body.index('{'):body.index('}')]
            self.assertIn('--wj-filter-btn-h-', body,
                          '%s %s: khai chiều cao bằng số cứng, đổi FB-08 sẽ sót màn này'
                          % (css_file, selector))
            self.assertNotRegex(body, r'(height|width):\s*\d+px',
                                '%s %s: vẫn còn số cứng cạnh token' % (css_file, selector))


@tagged('post_install', '-at_install', 'wujia_button_e6')
class TestNutNavbarLaBoundary(TransactionCase):
    """LIMIT E6b1 — nút chuông/giỏ trên navbar là nút ĐIỀU HƯỚNG của shell: tròn
    40 (bo 20), nền kính trên navbar màu (`_pc_account.css`, @≥1200). Kéo về atom
    thì hoặc mất dáng navbar, hoặc phải khai đè cao/bo/nền — tức giành dáng của
    atom. Cùng loại với BottomNavigation mà BA đã liệt là boundary."""

    def test_nut_navbar_khong_mang_atom(self):
        for module, filename in (('wujia_portal_notification', 'header_bell_inherit.xml'),
                                 ('wujia_portal_sale', 'header_cart_inherit.xml')):
            for el, cls in _atoms(_view(module, filename), 'wj-iconbtn'):
                self.assertNotIn('wujia-header-icon-btn', cls,
                                 '%s: nút navbar bị kéo về atom' % filename)

    def test_dang_cua_nut_navbar_van_o_mot_cho(self):
        """Nếu ngày nào navbar bỏ dáng riêng thì test đỏ để nhắc gỡ boundary."""
        css = _strip_comments(_css('_pc_account.css'))
        self.assertIn('wujia-header-icon-btn', css)


@tagged('post_install', '-at_install', 'wujia_button_e6')
class TestKhungPortalGocLaBoundary(TransactionCase):
    """LIMIT E6b1 — `/my/franchises` dựng bằng `portal.portal_layout` của Odoo.
    CSS design system nạp bằng `<link>` trong vỏ Wujia, khung gốc không có ⇒ atom
    ở đó ra nút trần (thước đo E6b1 bắt: bo 0, chữ 14/400). Màn Vuexy tương đương
    là `/portal/franchises` — nút ở đó mới phải là atom."""

    def test_man_khung_goc_khong_dung_atom(self):
        view = _view('wujia_portal_base', 'portal_templates.xml')
        self.assertFalse(_atoms(view, 'wj-btn') + _atoms(view, 'wj-iconbtn'),
                         'portal_templates.xml dùng khung Odoo gốc, atom sẽ không có dáng')

    def test_ban_vuexy_cua_cung_danh_sach_van_la_atom(self):
        """Chiều ngược: bỏ atom ở màn Vuexy thì test đỏ, tránh lấy LIMIT này làm cớ."""
        view = _view('wujia_portal_base', 'portal_franchises_in_layout.xml')
        self.assertTrue(_atoms(view, 'wj-btn'))



# E6b2 — màn Đặt hàng: bốn nhóm giữ boundary theo chốt chủ dự án 21/09. Ghim cả
# hai chiều: chúng không được mang atom, và atom không được mọc vào trong chúng.
BOUNDARY_ORDER = (
    ('wujia_portal_sale', 'portal_order_catalog.xml',
     ('wj-pc-order-add', 'wujia-morder-row-add', 'wujia-morder-mstep',
      'wujia-morder-search-btn', 'wujia-morder-floatbar-btn')),
    ('wujia_portal_sale', 'portal_order_cart.xml', ('wujia-mcart-step',)),
    ('wujia_portal_sale', 'pc_cart_panel.xml', ('wj-pc-cart-step',)),
)

# Lớp mà JS đang bắt. Chúng ở lại view SAU khi dáng đã về atom — đổi tên ở một
# phía là giỏ hàng chết lặng (không lỗi JS, chỉ là nút bấm không làm gì).
MOC_JS = (
    ('btn-add-cart-detail', 'portal_order_product_detail.xml', 'portal_order.js'),
    # G5 (WJ-ORD-028): nút gửi đơn PC + mobile chỉ mở hộp xác nhận, JS bắt qua data-attr
    # thay cho lớp `wujia-mcart-submit` (lớp đó còn ở view, chỉ là móc đo QA).
    ('data-wj-confirm-open', 'portal_order_cart.xml', 'portal_order.js'),
    ('data-wj-confirm-open', 'pc_cart_panel.xml', 'portal_order.js'),
    ('data-wj-confirm-form', 'portal_order_cart.xml', 'portal_order.js'),
    ('data-wj-confirm-form', 'pc_cart_panel.xml', 'portal_order.js'),
)


@tagged('post_install', '-at_install', 'wujia_button_e6')
class TestBoundaryManDatHang(TransactionCase):
    """Nút thêm-vào-giỏ theo hàng đổi dáng theo trạng thái giỏ bằng JS, cùng một
    thể với QuantityStepper mà BA đã liệt boundary; nút tìm thuộc FB-08; thanh
    nổi "Xem giỏ" cùng loại BottomNavigation."""

    def test_nhom_boundary_khong_mang_atom(self):
        for module, filename, nhom in BOUNDARY_ORDER:
            root = _view(module, filename)
            for el in root.iter():
                cls = ((el.get('class') or '') + ' '
                       + (el.get('t-attf-class') or '')).split()
                for moc in nhom:
                    if moc in cls:
                        self.assertNotIn(
                            'wj-btn', cls,
                            '%s: %s bị kéo về atom — mất dáng theo trạng thái giỏ'
                            % (filename, moc))
                        self.assertNotIn('wj-iconbtn', cls, '%s: %s' % (filename, moc))

    def test_nhom_boundary_van_giu_dang_rieng(self):
        """Chiều ngược: ngày nào các nhóm này hết dáng riêng thì test đỏ để nhắc
        gỡ boundary, đừng để LIMIT sống mãi bằng quán tính."""
        css = _strip_comments(_mod_css('wujia_portal_sale', 'portal_order.css'))
        for moc in ('wj-pc-order-add', 'wujia-morder-row-add', 'wujia-morder-mstep'):
            self.assertRegex(css, r'\.%s(?![-\w])' % moc,
                             '%s hết rule riêng ⇒ xem lại boundary' % moc)


@tagged('post_install', '-at_install', 'wujia_button_e6')
class TestMocJsGioHang(TransactionCase):
    """Dáng về atom nhưng móc JS phải còn ở CẢ hai phía."""

    def test_moc_con_du_hai_phia(self):
        for moc, view_file, js_file in MOC_JS:
            view = open(os.path.join(CUSTOM, 'wujia_portal_sale', 'views', view_file),
                        encoding='utf-8').read()
            js = open(os.path.join(CUSTOM, 'wujia_portal_sale', 'static', 'src', 'js',
                                   js_file), encoding='utf-8').read()
            self.assertRegex(view, r'%s(?![-\w])' % re.escape(moc),
                             '%s: mất móc %s, JS không còn bắt được nút' % (view_file, moc))
            self.assertIn(moc, js, '%s: JS không còn bắt %s' % (js_file, moc))

    def test_moc_js_chi_la_moc_khong_con_dang(self):
        """Móc mà vẫn khai dáng thì lại là hai bộ dáng cùng sống."""
        css = _strip_comments(_mod_css('wujia_portal_sale', 'portal_order.css'))
        cam = ('height', 'border-radius', 'background', 'font-size', 'font-weight')
        for sel, body in re.findall(r'([^{}]+)\{([^{}]*)\}', css):
            if not re.search(r'\.(wujia-mcart-(submit|del|empty-cta)|wj-pc-cart-(submit|del))'
                             r'(?![-\w])', sel):
                continue
            khai = {d.split(':')[0].strip() for d in body.split(';') if ':' in d}
            xau = sorted(k for k in khai if any(k == c or k.startswith(c + '-') for c in cam))
            self.assertFalse(xau, 'móc %s còn khai dáng: %s' % (sel.strip(), ', '.join(xau)))

    def test_ghost_tu_khai_trang_thai_nhan(self):
        """Nút xóa dòng giỏ bỏ marker `wj-state-surface` (F4) ⇒ atom phải tự có hover + nhấn."""
        css = _strip_comments(_css('_components.css'))
        for trang_thai in (':hover', ':active'):
            self.assertRegex(css, r'\.wj-iconbtn--ghost:not\(:disabled\)%s' % trang_thai,
                             'ghost mất trạng thái %s, nút xóa giỏ không còn phản hồi' % trang_thai)


# E6b2 — ba template auth KHÔNG controller nào render (`wujia_portal_layout/
# controllers/auth.py` chỉ render login · forgot_pass · reset_pass). Chúng vẫn
# được migrate cho đồng bộ, nhưng KHÔNG có bằng chứng đo bằng trình duyệt ⇒ ghim
# lại đúng sự thật đó: ngày nào có controller render, test đỏ để bắt đi đo thật.
AUTH_CHET = ('wujia_portal_layout.signup',
             'wujia_portal_layout.login_totp',
             'wujia_portal_layout.forgot_pass_back')


@tagged('post_install', '-at_install', 'wujia_button_e6')
class TestDangAuthVeAtom(TransactionCase):

    def test_khung_khong_con_khai_dang_nut_auth(self):
        """`_auth.css` nạp SAU `_components.css` nên mọi khai dáng còn sót ở đây
        đều THẮNG atom — đúng cơ chế đã làm nút auth cao 50 thay vì 46."""
        cam = ('height', 'border-radius', 'background', 'font-size', 'font-weight',
               'border', 'color')
        for ten, moc in (('_auth.css', 'wj-auth-submit'),
                         ('_components.css', 'wujia-maccount-submit'),
                         ('_pc_account.css', 'wj-pc-acct-pw-actions')):
            css = _strip_comments(_css(ten))
            for sel, body in re.findall(r'([^{}]+)\{([^{}]*)\}', css):
                if not re.search(r'\.%s(?![-\w])' % moc, sel):
                    continue
                khai = {d.split(':')[0].strip() for d in body.split(';') if ':' in d}
                xau = sorted(k for k in khai
                             if any(k == c or k.startswith(c + '-') for c in cam))
                self.assertFalse(xau, '%s: %s giành dáng của atom (%s)'
                                 % (ten, sel.strip(), ', '.join(xau)))

    def test_trang_thai_disabled_dung_cua_atom(self):
        self.assertNotRegex(_strip_comments(_css('_pc_account.css')),
                            r'\.wj-pc-btn--disabled(?![-\w])',
                            'họ disabled cũ còn sống song song .is-disabled của atom')

    def test_template_auth_chet_van_chua_ai_render(self):
        goi = []
        for root, _dirs, files in os.walk(CUSTOM):
            # Chỉ mã chạy thật mới tính; file test có nhắc tên template (kể cả
            # chính danh sách này) không phải là "đã nối controller".
            if os.sep + 'tests' in root:
                continue
            for fn in files:
                if not fn.endswith('.py'):
                    continue
                txt = open(os.path.join(root, fn), encoding='utf-8').read()
                for xmlid in AUTH_CHET:
                    if xmlid in txt:
                        goi.append('%s → %s' % (fn, xmlid))
        self.assertFalse(
            goi, 'template auth đã được nối controller: phải đo bằng trình duyệt '
                 'rồi bỏ khỏi AUTH_CHET — %s' % ', '.join(goi))
