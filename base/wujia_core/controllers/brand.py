from odoo import http
from odoo.http import request

# kind → (field ưu tiên, field dự phòng). Field dự phòng None ⇒ trống thì 404.
BRAND_IMAGES = {
    'logo': ('logo', None),
    'logo_mobile': ('wj_logo_mobile', 'logo'),
    'favicon': ('wj_favicon', 'logo'),
    'login_background': ('wj_login_background', None),
}
# Chỉ cho vài cỡ cố định: resize theo tham số tự do = ai cũng bắt server xử lý ảnh.
ALLOWED_WIDTHS = {0, 32, 64, 180, 192, 512}


class WujiaBrand(http.Controller):

    @http.route('/wj/brand/<int:company_id>/<string:kind>', type='http', auth='public',
                sitemap=False, readonly=True)
    def brand_image(self, company_id, kind, width=0, v=None, **kw):
        if kind not in BRAND_IMAGES:
            raise request.not_found()
        try:
            width = int(width or 0)
        except ValueError:
            width = 0
        if width not in ALLOWED_WIDTHS:
            raise request.not_found()
        company = request.env['res.company'].sudo().browse(company_id).exists()
        if not company:
            raise request.not_found()
        field, fallback = BRAND_IMAGES[kind]
        if not company[field]:
            if not fallback or not company[fallback]:
                raise request.not_found()
            field = fallback
        stream = request.env['ir.binary']._get_image_stream_from(company, field, width=width)
        # Có ?v= (URL do _wj_brand_url dựng) ⇒ nội dung bất biến, cache 1 năm.
        return stream.get_response(immutable=bool(v))
