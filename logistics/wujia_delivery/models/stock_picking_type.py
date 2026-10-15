from odoo import _, fields, models
from odoo.exceptions import AccessError


class StockPickingType(models.Model):
    _inherit = 'stock.picking.type'

    requires_transport_planning = fields.Boolean(
        string='Requires Transport Planning',
        default=False,
        help="If checked, transfer orders of this operation type require vehicle and dispatch planning.",
    )

    def write(self, vals):
        if 'requires_transport_planning' in vals:
            if not (
                self.env.user.has_group('wujia_fleet.group_fleet_manager')
                or self.env.user.has_group('stock.group_stock_manager')
                or self.env.is_superuser()
            ):
                raise AccessError(_("Only Fleet Managers or Inventory Managers can modify the transport planning setting."))
        return super().write(vals)
