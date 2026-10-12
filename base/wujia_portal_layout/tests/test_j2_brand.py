"""J-B2 — khung portal lấy brand từ `res.company` (wujia_core), không chép cứng.

Head (title/author/favicon), logo, CSS màu, câu "{brand}" đều theo Settings; logo là URL
`/wj/brand/…` (không nhúng base64 vào mỗi trang).
"""
import base64
import io

from PIL import Image

from odoo.tests import tagged
from odoo.tests.common import HttpCase

from .common import load_vi


def _png(color):
    buf = io.BytesIO()
    Image.new('RGB', (200, 60), color).save(buf, 'PNG')
    return base64.b64encode(buf.getvalue())


@tagged('post_install', '-at_install', 'wujia_j2_brand')
class TestPortalBrand(HttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = load_vi(cls.env)
        cls.company = cls.env.company
        cls.company.write({'wj_brand_name': 'Trà ABC', 'wj_primary_color': '#E4572E',
                           'logo': _png('red'), 'wj_favicon': False,
                           'wj_logo_mobile': False, 'wj_login_background': False})
        cls.user = cls.env['res.users'].create({
            'name': 'j2_me', 'login': 'j2_me', 'password': 'j2_me', 'lang': 'vi_VN',
            'group_ids': [(6, 0, [cls.env.ref('base.group_portal').id])]})

    def _get(self, url):
        res = self.url_open(url, timeout=30)
        self.assertEqual(res.status_code, 200, url)
        return res.text

    def _assert_brand_head(self, html):
        head = html[:html.index('</head>')]
        self.assertIn('<meta name="author" content="Trà ABC"', head)
        self.assertIn('Trà ABC</title>', head)
        self.assertIn('href="/wj/brand/%s/favicon?' % self.company.id, head)
        self.assertIn('id="wj-brand-css"', head)
        self.assertIn('--wujia-primary:#E4572E', head)
        # CSS brand phải đứng SAU file token để ghi đè được (cùng độ ưu tiên :root).
        self.assertGreater(head.index('id="wj-brand-css"'), head.index('_variables.css'))
        self.assertNotIn('Cloudmedia', head)

    def _assert_no_old_brand(self, html):
        self.assertNotIn('Ngô Gia', html)
        self.assertNotIn('data:image/png;base64', html)

    def test_login_page(self):
        html = self._get('/portal/login')
        self._assert_brand_head(html)
        self._assert_no_old_brand(html)
        self.assertIn('Sử dụng tài khoản Trà ABC đã cấp', html)
        self.assertIn('nhượng quyền Trà ABC trong cùng', html)
        self.assertIn('src="/wj/brand/%s/logo?' % self.company.id, html)
        self.assertIn('alt="Trà ABC"', html)
        # Không có nền đăng nhập ⇒ giữ nền màu chủ đạo, không trỏ ảnh 404.
        self.assertNotIn('/login_background', html)

    def test_login_background(self):
        self.company.wj_login_background = _png('blue')
        html = self._get('/portal/login')
        self.assertIn('/wj/brand/%s/login_background?' % self.company.id, html)

    def test_app_pages(self):
        self.authenticate('j2_me', 'j2_me')
        html = self._get('/portal/profile')
        self._assert_brand_head(html)
        self._assert_no_old_brand(html)
        self.assertIn('được quản lý bởi Trà ABC.', html)
        # Không logo mobile riêng ⇒ header mobile dùng route logo_mobile (route tự rơi về logo).
        self.assertIn('/wj/brand/%s/logo_mobile?' % self.company.id, html)
        html = self._get('/portal/change-password')
        self._assert_no_old_brand(html)

    def test_brand_name_is_escaped(self):
        self.company.wj_brand_name = 'A<b>B'
        html = self._get('/portal/login')
        self.assertNotIn('A<b>B', html)
        self.assertIn('A&lt;b&gt;B', html)

    def test_no_logo_no_broken_image(self):
        self.company.write({'logo': False, 'wj_logo_mobile': False, 'wj_favicon': False})
        self.authenticate('j2_me', 'j2_me')
        for url in ('/portal/profile', '/portal/change-password'):
            self.assertNotIn('/wj/brand/', self._get(url), url)
