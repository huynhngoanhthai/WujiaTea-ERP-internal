from odoo import fields, models


class ResPartnerBank(models.Model):
    _inherit = 'res.partner.bank'

    portal_payment_enabled = fields.Boolean(
        string='Use for Portal Payment',
        default=False,
        help='Expose this receiving account (and its QR/transfer info) to the franchise '
             'portal. Only accounts of the current company are used; the one with the '
             'smallest sequence wins (BA Model/Field N).',
    )
