# -*- coding: utf-8 -*-
"""F4 (quét nhiều module) — module không viết đè dáng component chung.

F5b dời khỏi `wujia_portal_layout`: khung không được biết màn nào. Phần chỉ đọc CSS
của khung vẫn ở lại layout (`test_f4_overrides.py`).
"""
import os
import re

from odoo.tests import TransactionCase, tagged

CUSTOM = os.path.normpath(os.path.join(os.path.dirname(__file__), '..', '..'))


def _read(*parts):
    with open(os.path.join(CUSTOM, *parts), encoding='utf-8') as fh:
        return fh.read()


def _nocomment(css):
    return re.sub(r'/\*.*?\*/', '', css, flags=re.S)


@tagged('post_install', '-at_install', 'wujia_f4')
class TestF4VariantsCallSites(TransactionCase):

    def test_badge_sm_variants_live_in_layout(self):
        comp = _nocomment(_read('wujia_portal_layout', 'static', 'assets', 'css', '_components.css'))
        self.assertRegex(comp, r'\.wujia-badge--sm\s*\{[^}]*font-size:\s*11px[^}]*padding:\s*3px 8px')
        pc = _nocomment(_read('wujia_portal_layout', 'static', 'assets', 'css', '_pc_components.css'))
        self.assertRegex(pc, r'\.wj-pc-badge--sm\s*\{[^}]*height:\s*auto[^}]*font-size:\s*11px')
        noti = _nocomment(_read('wujia_portal_notification', 'static', 'src', 'css', 'portal_notification.css'))
        self.assertNotRegex(noti, r'\.wujia-mnoti-row-tags \.wujia-badge\s*\{')
        self.assertNotRegex(noti, r'popup__item-tags \.wj-pc-badge\s*\{')
        xml = _read('wujia_portal_notification', 'views', 'portal_notification.xml')
        self.assertEqual(xml.count('wujia-badge wujia-badge--sm'), 2)
        js = _read('wujia_portal_notification', 'static', 'src', 'js', 'header_bell_badge.js')
        self.assertEqual(js.count('wj-pc-badge wj-pc-badge--sm'), 2)

    def test_pc_page_header_title_weight_beats_shell_h1(self):
        pc = _nocomment(_read('wujia_portal_layout', 'static', 'assets', 'css', '_pc_components.css'))
        self.assertRegex(pc, r'\.wj-pc-page-header \.wj-pc-page-header__title\s*\{[^}]*font-weight:\s*800\s*!important')
        exam = _nocomment(_read('wujia_portal_exam', 'static', 'src', 'css', 'portal_exam.css'))
        self.assertNotIn('.wj-exam-pc .wj-pc-page-header__title', exam)

    def test_no_legacy_shell_rules_left(self):
        files = (('wujia_portal_debt', 'portal_debt.css'), ('wujia_portal_delivery', 'portal_delivery.css'),
                 ('wujia_portal_exam', 'portal_exam.css'), ('wujia_portal_knowledge', 'portal_knowledge.css'),
                 ('wujia_portal_notification', 'portal_notification.css'),
                 ('wujia_portal_purchase_history', 'portal_history.css'), ('wujia_portal_return', 'portal_return.css'))
        for module, name in files:
            with self.subTest(file=name):
                css = _nocomment(_read(module, 'static', 'src', 'css', name))
                self.assertNotIn(':not(.wj-data-item)', css)


@tagged('post_install', '-at_install', 'wujia_f4')
class TestF4InteractionCallSites(TransactionCase):

    def test_screen_surfaces_carry_the_marker(self):
        sites = (
            # FR-B(b): 4 -> 3. Ô KPI thứ tư là <div> hiện '—' khi thiếu dữ liệu công nợ,
            # không bấm được ⇒ đã gỡ marker. Ba ô còn lại là <a>.
            (('wujia_portal_base', 'views', 'portal_home.xml'), 'wujia-mhome-kpi wj-state-surface', 3),
            (('wujia_portal_base', 'views', 'portal_home.xml'), 'wujia-mhome-action wj-state-surface', 6),
            (('wujia_portal_base', 'views', 'portal_home.xml'), 'wujia-kpi-card-link wj-state-surface', 4),
            (('wujia_portal_debt', 'views', 'portal_debt.xml'), 'wj-debt-pc-tab wj-state-surface', 2),
            (('wujia_portal_debt', 'views', 'portal_debt.xml'), 'wj-debt-actionrow wj-state-surface', 1),
            # E6b1: nút PDF công nợ đã về `.wj-btn--secondary` — variant nằm sẵn trong
            # danh sách bề mặt của _interaction.css nên không cần marker (tiền lệ E6a).
            (('wujia_portal_delivery', 'views', 'portal_delivery.xml'), 'wj-pc-dlv-chip wj-state-surface', 4),
            (('wujia_portal_knowledge', 'views', 'portal_knowledge.xml'), 'wujia-mknow-feat wj-state-surface', 1),
            # E6c: 2 nút đổi tháng màn Thi về `.wj-iconbtn--secondary` (có sẵn trong danh sách bề mặt).
            (('wujia_portal_exam', 'views', 'portal_exam.xml'), 'wj-state-surface', 0),
            # E6b2: 3 -> 2. Nút xóa dòng giỏ đã về `.wj-iconbtn--ghost`; atom tự khai
            # hover + nhấn (_components.css) nên không cần marker. Còn lại là nút bước.
            (('wujia_portal_sale', 'views', 'pc_cart_panel.xml'), 'wj-state-surface', 2),
            (('wujia_portal_sale', 'views', 'portal_order_cart.xml'), 'wj-state-surface', 2),
            (('wujia_portal_sale', 'views', 'portal_order_catalog.xml'), 'wj-state-surface', 4),
            # E6a: nút Hủy mobile của Đổi trả đã về `.wj-btn--secondary` — variant đó
            # nằm thẳng trong danh sách bề mặt của _interaction.css nên không cần marker.
            (('wujia_portal_base', 'views', 'store_picker_navbar.xml'), 'wujia-store-mobile-strip--clickable wj-state-surface', 1),
        )
        for parts, needle, n in sites:
            with self.subTest(file=parts[-1], needle=needle):
                self.assertEqual(_read(*parts).count(needle), n)

    def test_marker_never_on_a_plain_surface_card(self):
        """FR-B(b): template wj_surface_card bọc <a> khi có sc_href, còn lại là <div> thuần.
        Vậy marker phải đi với sc_link_class; đặt ở sc_class = hover trên chỗ bấm không ăn gì."""
        root = CUSTOM
        offenders = []
        for module in sorted(os.listdir(root)):
            if not module.startswith('wujia_portal_') or module == 'wujia_portal_inspection':
                continue
            views = os.path.join(root, module, 'views')
            if not os.path.isdir(views):
                continue
            for name in sorted(os.listdir(views)):
                if not name.endswith('.xml'):
                    continue
                for i, line in enumerate(_read(module, 'views', name).split('\n'), 1):
                    if 'sc_class' in line and 'wj-state-surface' in line:
                        offenders.append('%s/views/%s:%d' % (module, name, i))
        self.assertEqual(offenders, [], 'marker phải ở sc_link_class, không ở sc_class')

    def test_marker_only_on_clickable_tags(self):
        """FR-B(b): marker gắn thẳng trên thẻ thì thẻ đó phải là a/button/input/select."""
        root = CUSTOM
        offenders = []
        opening = re.compile(r'<([a-zA-Z]+)[\s>]')
        for module in sorted(os.listdir(root)):
            if not module.startswith('wujia_portal_') or module == 'wujia_portal_inspection':
                continue
            views = os.path.join(root, module, 'views')
            if not os.path.isdir(views):
                continue
            for name in sorted(os.listdir(views)):
                if not name.endswith('.xml'):
                    continue
                lines = _read(module, 'views', name).split('\n')
                for i, line in enumerate(lines):
                    if 'wj-state-surface' not in line or 'sc_class' in line or 'sc_link_class' in line:
                        continue
                    # Thẻ mở của phần tử = '<x' CUỐI CÙNG đứng TRƯỚC vị trí marker.
                    # (Quét cả dòng sẽ bắt nhầm thẻ con viết sau, vd `>Tất cả <t t-out=…/></a>`.)
                    head = '\n'.join(lines[max(0, i - 3):i])
                    head += '\n' + line[:line.index('wj-state-surface')]
                    tags = opening.findall(head)
                    tag = tags[-1] if tags else None
                    if tag not in ('a', 'button', 'input', 'select'):
                        offenders.append('%s/views/%s:%d <%s>' % (module, name, i + 1, tag))
        self.assertEqual(offenders, [], 'marker chỉ được nằm trên phần tử bấm được')
