from odoo import _, api, fields, models, tools
from odoo.exceptions import ValidationError

from ..tools.brand_palette import DEFAULT_PRIMARY, brand_palette, normalize_hex, palette_css

# Field mà portal/backend đọc qua _wj_brand_info() — đổi field nào trong đây thì xoá cache.
# Tên thương hiệu điền sẵn khi cài / nâng cấp lên 19.0.2.1.0 (công ty UAT tên "My Company").
DEFAULT_BRAND_NAME = 'Ngô Gia'

BRAND_FIELDS = {
    'name', 'logo', 'wj_brand_name', 'wj_primary_color',
    'wj_logo_mobile', 'wj_favicon', 'wj_login_background',
}


class ResCompany(models.Model):
    _inherit = 'res.company'

    # Logo PC = `logo` sẵn có của công ty, không tạo field trùng.
    wj_brand_name = fields.Char(
        string='Brand name',
        help='Shown in the browser tab, logo alt text and login page. Empty = company name.',
    )
    wj_primary_color = fields.Char(
        string='Primary color',
        default=DEFAULT_PRIMARY,
        help='Hex #RRGGBB. Darker/lighter shades and the button color are generated from it.',
    )
    wj_logo_mobile = fields.Image(
        string='Mobile logo', max_width=512, max_height=512,
        help='Logo for the mobile header. Empty = company logo.',
    )
    wj_favicon = fields.Image(
        string='Favicon', max_width=512, max_height=512,
        help='Square image, at least 180×180. Empty = company logo.',
    )
    wj_login_background = fields.Image(
        string='Login background', max_width=1920, max_height=1920,
        help='Background image of the portal login page. Empty = default image.',
    )

    @api.constrains('wj_primary_color')
    def _check_wj_primary_color(self):
        for company in self:
            if company.wj_primary_color and not normalize_hex(company.wj_primary_color):
                raise ValidationError(_('Primary color must be a hex code like #28A9DF.'))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('wj_primary_color'):
                vals['wj_primary_color'] = normalize_hex(vals['wj_primary_color']) or vals['wj_primary_color']
        return super().create(vals_list)

    def write(self, vals):
        if vals.get('wj_primary_color'):
            vals['wj_primary_color'] = normalize_hex(vals['wj_primary_color']) or vals['wj_primary_color']
        res = super().write(vals)
        if BRAND_FIELDS & set(vals):
            self.env.registry.clear_cache()
        return res

    @api.model
    def _wj_fill_default_brand_name(self):
        """Điền tên thương hiệu cho công ty còn trống — không ghi đè tên đã đặt."""
        self.sudo().search([('wj_brand_name', '=', False)]).write({'wj_brand_name': DEFAULT_BRAND_NAME})

    @tools.ormcache('self.id')
    def _wj_brand_info(self):
        """Mọi thứ trang cần để dựng brand, 1 lần/công ty (1500 user ⇒ không đọc lại mỗi request).

        Trả dict thuần (không recordset) vì nằm trong ormcache."""
        self.ensure_one()
        company = self.sudo()
        primary = normalize_hex(company.wj_primary_color) or DEFAULT_PRIMARY
        return {
            'name': company.wj_brand_name or company.name,
            'primary': primary,
            'palette': brand_palette(primary),
            'css': palette_css(primary),
            'has_logo': bool(company.logo),
            'has_logo_mobile': bool(company.wj_logo_mobile),
            'has_favicon': bool(company.wj_favicon),
            'has_login_background': bool(company.wj_login_background),
            # Bust cache trình duyệt cho ảnh: đổi bất kỳ field brand nào ⇒ write_date đổi.
            'version': int(company.write_date.timestamp()) if company.write_date else 0,
        }

    def _wj_brand_text(self, text):
        """Điền tên thương hiệu vào chỗ `{brand}` của câu hiển thị (giữ nguyên Markup)."""
        return text.replace('{brand}', self._wj_brand_info()['name']) if text else text

    def _wj_brand_url(self, kind, width=0):
        """URL ảnh brand có `?v=` ⇒ trình duyệt cache lâu, đổi ảnh là đổi URL."""
        self.ensure_one()
        url = '/wj/brand/%s/%s?v=%s' % (self.id, kind, self._wj_brand_info()['version'])
        return url + ('&width=%s' % width if width else '')
