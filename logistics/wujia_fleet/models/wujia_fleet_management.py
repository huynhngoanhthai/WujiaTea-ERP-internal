import base64
import io
import logging

from odoo import _, api, fields, models

_logger = logging.getLogger(__name__)

try:
    import qrcode
except ImportError:
    qrcode = None
    _logger.info("qrcode python package not installed — wujia.fleet.management.qr_code will return False.")


VEHICLE_STATUS = [
    ('available', 'Available'),
    ('in_yard', 'At the yard'),
    ('assigned', 'Trip planned'),
    ('delivering', 'In transit'),
    ('maintenance', 'Under maintenance'),
    ('inactive', 'Retired'),
]


class WujiaFleetManagement(models.Model):
    _name = 'wujia.fleet.management'
    _description = 'Wujia Fleet Vehicle'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'provider_id, name'

    name = fields.Char(
        string='Vehicle name',
        required=True,
        tracking=True,
        help='Display name, e.g. "51C-12345 — 3.5T payload".',
    )
    code = fields.Char(string='Vehicle code', index=True)
    provider_id = fields.Many2one(
        'wujia.fleet.provider',
        string='Carrier',
        required=True,
        ondelete='restrict',
        tracking=True,
        index=True,
        domain=[('active', '=', True)],
    )
    fleet_type_id = fields.Many2one(
        'wujia.fleet.type',
        string='Vehicle type',
        required=True,
        ondelete='restrict',
        tracking=True,
        index=True,
    )
    vehicle_category = fields.Selection(
        related='fleet_type_id.vehicle_category',
        store=True,
        readonly=True,
    )
    payload_capacity_ton = fields.Float(
        related='fleet_type_id.payload_capacity_ton',
        store=True,
        readonly=True,
        digits=(10, 2),
    )
    max_payload_kg = fields.Float(
        related='fleet_type_id.max_payload_kg',
        store=True,
        readonly=True,
        digits='Stock Weight',
    )

    license_plate = fields.Char(string='License plate', tracking=True, index=True)
    driver_name = fields.Char(string='Driver')
    driver_phone = fields.Char(string='Driver phone')
    contact = fields.Char(
        string='Contact details',
        help='Quick contact details (vehicle number / driver).',
    )

    vehicle_status = fields.Selection(
        VEHICLE_STATUS,
        string='Vehicle status',
        required=True,
        default='available',
        tracking=True,
        index=True,
    )

    franchise_ids = fields.Many2many(
        'wujia.franchise.management',
        'wujia_fleet_franchise_rel',
        'fleet_id',
        'franchise_id',
        string='Frequently served stores',
        help='Stores usually served by this vehicle — used as a dispatch hint.',
    )

    qr_code = fields.Binary(
        string='QR Code',
        compute='_compute_qr_code',
        help='QR code carrying the vehicle code — used for check-in at the yard.',
    )

    description = fields.Text(string='Description')
    last_update_datetime = fields.Datetime(
        string='Last status update',
        readonly=True,
    )
    active = fields.Boolean(default=True)
    note = fields.Text(string='Internal note')

    _code_uniq = models.Constraint(
        'UNIQUE (code)',
        'Vehicle code must be unique.',
    )

    @api.depends('code')
    def _compute_qr_code(self):
        for rec in self:
            if not qrcode or not rec.code:
                rec.qr_code = False
                continue
            try:
                img = qrcode.make(rec.code)
                buf = io.BytesIO()
                img.save(buf, format='PNG')
                rec.qr_code = base64.b64encode(buf.getvalue())
            except Exception as exc:
                _logger.warning("QR code generation failed for vehicle %s: %s", rec.code, exc)
                rec.qr_code = False

    def write(self, vals):
        if 'vehicle_status' in vals:
            vals.setdefault('last_update_datetime', fields.Datetime.now())
        return super().write(vals)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            vals.setdefault('last_update_datetime', fields.Datetime.now())
        return super().create(vals_list)

