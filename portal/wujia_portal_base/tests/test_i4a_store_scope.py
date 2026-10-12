"""Dữ liệu Home chỉ theo MỘT cửa hàng đang chọn.

Chạy: `--test-tags wujia_scope_i4a`.

Luật BA 01/10: chưa chọn cửa hàng ⇒ không hiện dữ liệu gộp A+B, yêu cầu chọn; chọn A ⇒ chỉ A;
đổi B ⇒ chỉ B; tài khoản một cửa hàng tự chọn; lựa chọn cũ không còn hợp lệ bị xoá.
Giao hàng / Báo cáo kiểm trong module của chúng (cùng tag).
"""
from odoo.tests import tagged
from odoo.tests.common import HttpCase

from odoo.addons.wujia_portal_base.controllers.portal import ACTIVE_FRANCHISE_COOKIE

PROMPT_NEED_PICK = 'data-store-scope="need_pick"'
PROMPT_NO_STORE = 'data-store-scope="no_store"'


@tagged('post_install', '-at_install', 'wujia_scope_i4a')
class TestHomeStoreScope(HttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        Partner, Franchise = env['res.partner'], env['wujia.franchise.management']
        cls.store_a, cls.store_b, cls.store_c = (Franchise.create({
            'code': code, 'name': 'I4a store %s' % code, 'franchise_end_date': '2030-01-01',
            'partner_id': Partner.create({'name': 'I4a partner %s' % code}).id,
        }) for code in ('I4A', 'I4B', 'I4C'))
        product = env['product.product'].create({
            'name': 'I4a product', 'type': 'consu', 'list_price': 10_000})

        def order(store):
            return env['sale.order'].create({
                'partner_id': store.partner_id.id, 'franchise_id': store.id,
                'order_line': [(0, 0, {'product_id': product.id, 'product_uom_qty': 1})]})
        cls.so_a, cls.so_b, cls.so_c = order(cls.store_a), order(cls.store_b), order(cls.store_c)

        portal = env.ref('base.group_portal').id

        def user(login, stores):
            u = env['res.users'].create({
                'name': login, 'login': login, 'password': login,
                'group_ids': [(6, 0, [portal])]})
            for s in stores:
                env['wujia.franchise.member'].create({
                    'user_id': u.id, 'franchise_id': s.id, 'role': 'owner'})
            return u
        user('i4a.ab', cls.store_a | cls.store_b)
        user('i4a.a', cls.store_a)
        user('i4a.none', env['wujia.franchise.management'])

    def _home(self, login, store=None):
        self.authenticate(login, login)
        if store is not None:
            self.opener.cookies.set(ACTIVE_FRANCHISE_COOKIE, str(store.id))
        res = self.url_open('/portal', timeout=30)
        self.assertEqual(res.status_code, 200)
        return res

    def test_multi_store_not_selected_shows_prompt_not_aggregate(self):
        html = self._home('i4a.ab').text
        self.assertIn(PROMPT_NEED_PICK, html)
        self.assertNotIn(self.so_a.name, html)
        self.assertNotIn(self.so_b.name, html)
        self.assertNotIn('wujia-home-kpis', html, 'chưa chọn ⇒ không hiện KPI (số 0 dễ đọc nhầm)')

    def test_selected_store_only(self):
        html = self._home('i4a.ab', self.store_a).text
        self.assertNotIn(PROMPT_NEED_PICK, html)
        self.assertIn(self.so_a.name, html)
        self.assertNotIn(self.so_b.name, html)

    def test_switch_to_other_store(self):
        html = self._home('i4a.ab', self.store_b).text
        self.assertIn(self.so_b.name, html)
        self.assertNotIn(self.so_a.name, html)

    def test_single_store_auto_picked(self):
        html = self._home('i4a.a').text
        self.assertNotIn(PROMPT_NEED_PICK, html)
        self.assertIn(self.so_a.name, html)

    def test_no_store_keeps_contact_admin(self):
        html = self._home('i4a.none').text
        self.assertIn(PROMPT_NO_STORE, html)
        self.assertNotIn(PROMPT_NEED_PICK, html)

    def test_stale_cookie_is_cleared_and_prompts(self):
        """Cookie trỏ cửa hàng không còn quyền (C) ⇒ xoá cookie + nhắc chọn, không lộ dữ liệu C."""
        res = self._home('i4a.ab', self.store_c)
        self.assertIn(PROMPT_NEED_PICK, res.text)
        self.assertNotIn(self.so_c.name, res.text)
        cleared = [h for h in res.raw.headers.getlist('Set-Cookie')
                   if h.startswith(ACTIVE_FRANCHISE_COOKIE + '=')]
        self.assertTrue(cleared, 'phải trả Set-Cookie xoá lựa chọn cũ')
        self.assertTrue(any('Max-Age=0' in h or 'expires=Thu, 01 Jan 1970' in h for h in cleared), cleared)

    def test_lost_membership_falls_back(self):
        """Membership A hết hiệu lực khi đang chọn A ⇒ không còn thấy A, cookie bị xoá."""
        member = self.env['wujia.franchise.member'].search([
            ('user_id.login', '=', 'i4a.ab'), ('franchise_id', '=', self.store_a.id)])
        member.unlink()
        res = self._home('i4a.ab', self.store_a)
        # Còn đúng một cửa hàng hợp lệ (B) ⇒ tự chọn B.
        self.assertNotIn(self.so_a.name, res.text)
        self.assertIn(self.so_b.name, res.text)
        self.assertTrue([h for h in res.raw.headers.getlist('Set-Cookie')
                         if h.startswith(ACTIVE_FRANCHISE_COOKIE + '=')])
