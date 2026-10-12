"""Hộp chọn cửa hàng là dialog modal (WJ-PORTAL-UI-005) + khối đầu Home PC (WJ-HOME-001 08/10).

Chạy: `--test-tags wujia_i12`. Hành vi bàn phím (focus/Tab/Esc/inert) đo bằng Playwright; ở đây giữ
markup + luật JS/CSS để không trôi ngược.
"""
import re

from lxml import html as lhtml

from odoo.tests import tagged
from odoo.tests.common import HttpCase
from odoo.tools.misc import file_path

from odoo.addons.wujia_portal_base.controllers.portal import ACTIVE_FRANCHISE_COOKIE

HEADINGS = './/*[self::h1 or self::h2 or self::h3 or self::h4]'


def _read(path):
    with open(file_path(path)) as f:
        return f.read()


@tagged('post_install', '-at_install', 'wujia_i12')
class TestDialogHomeRender(HttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        mk = lambda code: env['wujia.franchise.management'].create({  # noqa: E731
            'code': code, 'name': 'I12 store %s' % code, 'status': 'active',
            'partner_id': env['res.partner'].create({'name': 'I12 partner %s' % code}).id})
        cls.store_a, cls.store_b = mk('I12A'), mk('I12B')
        portal = env.ref('base.group_portal').id
        cls.user = env['res.users'].create({
            'name': 'I12 Multi', 'login': 'i12.multi', 'password': 'i12.multi', 'lang': 'en_US',
            'group_ids': [(6, 0, [portal])]})
        for store in (cls.store_a, cls.store_b):
            env['wujia.franchise.member'].create({'user_id': cls.user.id, 'franchise_id': store.id, 'role': 'owner'})

    def _tree(self, store=True):
        self.authenticate('i12.multi', 'i12.multi')
        if store:
            self.opener.cookies.set(ACTIVE_FRANCHISE_COOKIE, str(self.store_a.id))
        res = self.url_open('/portal', timeout=30)
        self.assertEqual(res.status_code, 200)
        return lhtml.fromstring(res.text)

    # ---------- #169 store switcher dialog ----------

    def _dialog(self, tree):
        dialogs = tree.xpath('//*[@id="wujiaStoreOverlay"]//*[@role="dialog"]')
        self.assertEqual(len(dialogs), 1)
        dlg = dialogs[0]
        self.assertEqual(dlg.get('aria-modal'), 'true')
        title = tree.get_element_by_id(dlg.get('aria-labelledby'))
        self.assertTrue(dlg.xpath('.//*[@id=$i]', i=title.get('id')), 'tên dialog nằm trong hộp')
        self.assertTrue(title.text_content().strip())
        self.assertTrue(tree.get_element_by_id(dlg.get('aria-describedby')).text_content().strip())
        return dlg, title

    def test_dialog_has_role_modal_and_name(self):
        tree = self._tree()
        dlg, title = self._dialog(tree)
        self.assertEqual(re.sub(r'\s+', ' ', title.text_content()).strip(), 'Switch the store you work on')
        self.assertTrue(dlg.find_class('wujia-store-close'), 'có nút Đóng để nhận focus khi mở')

    def test_must_pick_dialog_same_semantics(self):
        tree = self._tree(store=False)
        overlay = tree.get_element_by_id('wujiaStoreOverlay')
        self.assertIn('wujia-store-overlay--show', overlay.get('class'))
        dlg, title = self._dialog(tree)
        self.assertEqual(re.sub(r'\s+', ' ', title.text_content()).strip(), 'Select the store to work on')
        self.assertFalse(dlg.find_class('wujia-store-close'), 'bắt buộc chọn ⇒ không có đường thoát')

    def test_current_store_triggers_announce_dialog(self):
        tree = self._tree()
        for cls in ('wujia-active-store-badge', 'wujia-store-mobile-strip--clickable'):
            nodes = tree.find_class(cls)
            self.assertEqual(len(nodes), 1, cls)
            self.assertEqual(nodes[0].get('aria-haspopup'), 'dialog', cls)
            self.assertEqual(nodes[0].get('aria-controls'), 'wujiaStoreOverlay', cls)
        for trig in tree.xpath('//*[@data-action="open-store-picker"]'):
            self.assertEqual(trig.get('aria-haspopup'), 'dialog')

    def test_js_manages_focus(self):
        js = _read('wujia_portal_base/static/src/js/store_picker.js')
        show = re.search(r'function show\(trigger\) \{(.*?)\n        \}', js, re.S).group(1)
        hide = re.search(r'function hide\(\) \{(.*?)\n        \}', js, re.S).group(1)
        self.assertIn('setInert(true)', show)
        self.assertIn('focusInitial()', show)
        self.assertIn('setInert(false)', hide)
        self.assertIn('back.focus()', hide)
        self.assertIn('el.inert = true', js)
        self.assertIn('ev.key === "Escape"', js)
        self.assertIn('ev.key !== "Tab"', js)
        self.assertIn('.wujia-active-store-badge, .wujia-store-mobile-strip--clickable', js)
        # must_pick: hộp mở sẵn từ server cũng phải inert nền + kéo focus vào
        self.assertRegex(js, r'if \(isOpen\(\)\) \{\s*setInert\(true\);\s*focusInitial\(\);')

    # ---------- #171 khối đầu Home ----------

    def test_home_single_visually_hidden_h1(self):
        tree = self._tree()
        wrapper = tree.find_class('wujia-home-wrapper')[0]
        h1s = wrapper.xpath('.//h1')
        self.assertEqual(len(h1s), 1)
        h1 = h1s[0]
        self.assertEqual(h1.text_content().strip(), 'Store overview')
        self.assertIn('visually-hidden', h1.get('class').split())
        self.assertIs(h1.getparent(), wrapper, 'H1 ngoài khối kênh (d-none ⇒ mất khỏi cây truy cập)')

    def test_home_pc_no_visible_title_or_greeting(self):
        tree = self._tree()
        pc = tree.find_class('wujia-home-pc')[0]
        self.assertFalse(pc.find_class('wj-page-header'))
        self.assertFalse(pc.find_class('content-header'))
        self.assertNotIn('Welcome', pc.text_content())
        self.assertNotIn('Here is the activity summary', tree.text_content())

    def test_home_heading_levels(self):
        tree = self._tree()
        for cls in ('wujia-home-pc', 'wujia-mhome'):
            block = tree.find_class(cls)[0]
            levels = [int(h.tag[1]) for h in block.xpath(HEADINGS)]
            self.assertTrue(levels, cls)
            self.assertEqual(levels[0], 2, '%s: heading đầu là h2 ngay dưới H1' % cls)
            for prev, cur in zip(levels, levels[1:]):
                self.assertLessEqual(cur - prev, 1, '%s: nhảy cấp heading %s' % (cls, levels))

    def test_visually_hidden_css(self):
        css = _read('wujia_portal_layout/static/assets/css/_components.css')
        rule = re.search(r'\n\.visually-hidden\s*\{([^}]*)\}', css)
        self.assertTrue(rule)
        body = rule.group(1)
        for decl in ('position: absolute', 'width: 1px', 'height: 1px', 'overflow: hidden', 'clip: rect(0, 0, 0, 0)'):
            self.assertIn(decl, body)
        self.assertNotIn('visibility', body)
        self.assertNotIn('display', body)
