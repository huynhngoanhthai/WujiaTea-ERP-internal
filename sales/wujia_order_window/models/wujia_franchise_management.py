from odoo import fields, models


class WujiaFranchiseManagement(models.Model):
    _inherit = 'wujia.franchise.management'

    tz = fields.Selection(
        related='partner_id.tz',
        readonly=False,
        string='Timezone',
        help='IANA timezone of the store. Portal ordering windows are checked in this local time.',
    )
