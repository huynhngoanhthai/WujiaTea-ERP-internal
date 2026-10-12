import base64
import io

from markupsafe import Markup
from PIL import Image

from odoo.exceptions import ValidationError
from odoo.tests import HttpCase, TransactionCase, tagged

from ..models.res_company import DEFAULT_BRAND_NAME
from ..tools.brand_palette import (
    DEFAULT_PALETTE, DEFAULT_PRIMARY, TINT_TOKENS, brand_palette, contrast_with_white, derive_palette,
    palette_css, retint,
)


def _png(color, size=(200, 200)):
    buf = io.BytesIO()
    Image.new('RGB', size, color).save(buf, 'PNG')
    return base64.b64encode(buf.getvalue())


@tagged('post_install', '-at_install', 'wujia_brand')
class TestBrandPalette(TransactionCase):

    def test_default_color_keeps_ba_tokens(self):
        # Màu mặc định ⇒ đúng bộ token đã chốt + không sinh CSS ghi đè (0 pixel đổi).
        self.assertEqual(brand_palette('#28a9df'), DEFAULT_PALETTE)
        self.assertEqual(palette_css('#28A9DF'), '')
        self.assertEqual(palette_css(None), '')

    def test_derivation_calibrated_on_default(self):
        derived = derive_palette('#28A9DF')
        for key, expected in DEFAULT_PALETTE.items():
            if key == 'primary-rgb':
                continue
            for a, b in zip(bytes.fromhex(expected[1:]), bytes.fromhex(derived[key][1:])):
                self.assertLessEqual(abs(a - b), 8, key)

    def test_cta_always_passes_aa(self):
        for color in ('#E4572E', '#2E7D32', '#FFD400', '#00E5FF', '#FFFFFF', '#9C27B0'):
            self.assertGreaterEqual(contrast_with_white(brand_palette(color)['cta']), 4.5, color)

    def test_custom_color_css(self):
        css = palette_css('#e4572e')
        self.assertTrue(css.startswith(':root{--wujia-primary:#E4572E;'))
        self.assertIn('--wujia-primary-rgb:228 87 46', css)

    def test_tint_tokens_follow_brand(self):
        # Màu mặc định: xoay sắc 0 ⇒ trả đúng hex cũ (CSS module giữ nguyên, 0 pixel đổi).
        for value in TINT_TOKENS.values():
            self.assertEqual(retint(value, DEFAULT_PRIMARY), value)
        css = palette_css('#E4572E')
        for name in TINT_TOKENS:
            self.assertIn('--%s:' % name, css)
        # Nền ô hành động nhanh: vẫn rất nhạt nhưng sang sắc cam (đỏ > xanh dương).
        r, g, b = bytes.fromhex(retint('#E9F7FC', '#E4572E')[1:])
        self.assertGreater(r, b)
        self.assertGreater(min(r, g, b), 225)
        # Gradient giữ cú pháp, chỉ đổi mã màu.
        grad = retint(TINT_TOKENS['wujia-mhome-hero-grad'], '#E4572E')
        self.assertTrue(grad.startswith('linear-gradient(135deg, #'))
        self.assertNotIn('#0B2430', grad)


@tagged('post_install', '-at_install', 'wujia_brand')
class TestBrandCompany(TransactionCase):

    def setUp(self):
        super().setUp()
        self.company = self.env.company

    def test_invalid_hex_rejected(self):
        with self.assertRaises(ValidationError):
            self.company.wj_primary_color = 'blue'

    def test_hex_normalized_and_cache_cleared(self):
        info = self.company._wj_brand_info()
        self.assertEqual(info['css'], '' if info['primary'] == '#28A9DF' else info['css'])
        self.company.write({'wj_primary_color': '#e4572e', 'wj_brand_name': 'Acme Tea'})
        self.assertEqual(self.company.wj_primary_color, '#E4572E')
        info = self.company._wj_brand_info()
        self.assertEqual(info['name'], 'Acme Tea')
        self.assertEqual(info['primary'], '#E4572E')
        self.assertIn('--wujia-primary:#E4572E', info['css'])

    def test_brand_name_falls_back_to_company(self):
        self.company.wj_brand_name = False
        self.assertEqual(self.company._wj_brand_info()['name'], self.company.name)

    def test_has_logo_follows_company_logo(self):
        self.company.logo = _png('red')
        self.assertTrue(self.company._wj_brand_info()['has_logo'])
        self.company.logo = False
        self.assertFalse(self.company._wj_brand_info()['has_logo'])

    def test_fill_default_name_keeps_existing(self):
        other = self.env['res.company'].create({'name': 'B2 Other'})
        self.company.wj_brand_name = 'Acme Tea'
        other.wj_brand_name = False
        self.env['res.company']._wj_fill_default_brand_name()
        self.assertEqual(self.company.wj_brand_name, 'Acme Tea')
        self.assertEqual(other.wj_brand_name, DEFAULT_BRAND_NAME)
        # Cache đã xoá khi ghi ⇒ trang thấy tên mới ngay.
        self.assertEqual(other._wj_brand_info()['name'], DEFAULT_BRAND_NAME)

    def test_brand_text_fills_placeholder(self):
        self.company.wj_brand_name = 'Acme <Tea>'
        self.assertEqual(self.company._wj_brand_text('Liên hệ {brand}.'), 'Liên hệ Acme <Tea>.')
        # Markup giữ an toàn: tên được escape khi chèn vào câu Markup.
        out = self.company._wj_brand_text(Markup('<b>{brand}</b>'))
        self.assertEqual(str(out), '<b>Acme &lt;Tea&gt;</b>')
        self.assertFalse(self.company._wj_brand_text(False))

    def test_settings_write_company(self):
        settings = self.env['res.config.settings'].create({
            'wj_brand_name': 'Acme Tea', 'wj_primary_color': '#2E7D32',
        })
        settings.execute()
        self.assertEqual(self.company.wj_brand_name, 'Acme Tea')
        self.assertEqual(self.company.wj_primary_color, '#2E7D32')


@tagged('post_install', '-at_install', 'wujia_brand')
class TestBrandRoute(HttpCase):

    def setUp(self):
        super().setUp()
        self.company = self.env.company
        self.company.write({'logo': _png('red'), 'wj_logo_mobile': False, 'wj_favicon': _png('blue')})

    def test_public_images(self):
        cid = self.company.id
        self.assertEqual(self.url_open('/wj/brand/%s/logo' % cid).status_code, 200)
        # Không có logo mobile ⇒ dùng logo công ty.
        self.assertEqual(self.url_open('/wj/brand/%s/logo_mobile' % cid).status_code, 200)
        res = self.url_open('/wj/brand/%s/favicon?width=32&v=1' % cid)
        self.assertEqual(res.status_code, 200)
        self.assertIn('immutable', res.headers.get('Cache-Control', ''))
        self.assertEqual(Image.open(io.BytesIO(res.content)).size[0], 32)

    def test_rejects_unknown_kind_width_and_empty(self):
        cid = self.company.id
        self.assertEqual(self.url_open('/wj/brand/%s/secret' % cid).status_code, 404)
        self.assertEqual(self.url_open('/wj/brand/%s/logo?width=777' % cid).status_code, 404)
        # Nền đăng nhập không có dự phòng ⇒ trống là 404 (trang tự dùng ảnh mặc định).
        self.assertEqual(self.url_open('/wj/brand/%s/login_background' % cid).status_code, 404)
        self.assertEqual(self.url_open('/wj/brand/999999/logo').status_code, 404)


@tagged('post_install', '-at_install', 'wujia_brand')
class TestBrandBackendLayout(HttpCase):
    """`web.layout` (backend + /web/login): favicon + title fallback theo brand."""

    def setUp(self):
        super().setUp()
        self.company = self.env.company
        self.company.write({'wj_brand_name': 'Acme Tea', 'logo': _png('red'), 'wj_favicon': False})

    def _head(self):
        html = self.url_open('/web/login').text
        return html[:html.index('</head>')]

    def test_login_tab_uses_brand(self):
        head = self._head()
        self.assertIn('<title>Acme Tea</title>', head)
        self.assertIn('href="/wj/brand/%s/favicon?' % self.company.id, head)
        self.assertNotIn('<title>Odoo</title>', head)

    def test_no_logo_no_brand_icon(self):
        # Công ty không logo, không favicon ⇒ không in link brand (tránh 404), giữ icon mặc định.
        self.company.write({'logo': False, 'wj_favicon': False})
        head = self._head()
        self.assertNotIn('/wj/brand/', head)
        self.assertIn('rel="shortcut icon"', head)
