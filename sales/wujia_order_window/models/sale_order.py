from odoo import _, api, models
from odoo.exceptions import ValidationError


def _hhmm(value):
    """10.5 → '10:30' (giờ thập phân của khung giờ → giờ:phút)."""
    minutes = round(float(value or 0.0) * 60) % (24 * 60)
    return '%02d:%02d' % divmod(minutes, 60)


class OrderWindowClosed(ValidationError):
    """Đơn portal tạo ngoài khung giờ — nơi gọi bắt theo lớp, không dò câu chữ."""


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    @api.model_create_multi
    def create(self, vals_list):
        # Chặn cả khi controller bỏ sót; cùng luật với banner portal.
        Settings = self.env['res.config.settings'].sudo()
        Franchise = self.env['wujia.franchise.management'].sudo()
        for vals in vals_list:
            if not vals.get('is_portal_order'):
                continue
            franchise = Franchise.browse(vals.get('franchise_id') or [])
            allowed, window = Settings._is_within_order_window(franchise=franchise)
            if window.get('tz_missing'):
                raise OrderWindowClosed(_(
                    "The store's timezone is not configured, so ordering is unavailable. "
                    "Please contact the head office."
                ))
            if not allowed:
                raise OrderWindowClosed(_(
                    "Not within the ordering window right now. "
                    "Please order within %(f)s – %(t)s.",
                    f=_hhmm(window['from']), t=_hhmm(window['to']),
                ))
        return super().create(vals_list)
