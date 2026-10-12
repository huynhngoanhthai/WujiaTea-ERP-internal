from odoo import _, api, fields, models


DELIVERY_BATCH_STATUS = [
    ('draft', 'Draft'),
    ('assigned', 'Vehicle assigned'),
    ('loading', 'Loading'),
    ('delivering', 'In transit'),
    ('done', 'Delivery completed'),
    ('cancelled', 'Trip cancelled'),
]


class StockPickingBatch(models.Model):
    _inherit = 'stock.picking.batch'

    vehicle_id = fields.Many2one(
        'wujia.fleet.management',
        string='Vehicle',
        domain=[('active', '=', True)],
        tracking=True,
        index=True,
        help='Vehicle assigned to this trip.',
    )
    provider_id = fields.Many2one(
        'wujia.fleet.provider',
        string='Carrier',
        related='vehicle_id.provider_id',
        store=True,
        readonly=True,
        index=True,
    )
    fleet_type_id = fields.Many2one(
        'wujia.fleet.type',
        string='Vehicle type',
        related='vehicle_id.fleet_type_id',
        store=True,
        readonly=True,
        index=True,
    )
    vehicle_capacity_ton = fields.Float(
        string='Payload (tons)',
        related='vehicle_id.payload_capacity_ton',
        store=True,
        readonly=True,
        digits=(10, 2),
    )
    vehicle_capacity_kg = fields.Float(
        string='Payload (kg)',
        related='vehicle_id.max_payload_kg',
        store=True,
        readonly=True,
        digits='Stock Weight',
    )

    capacity_usage_percent = fields.Float(
        string='Payload utilisation %',
        compute='_compute_capacity_usage',
        store=True,
        digits=(8, 2),
    )
    is_over_capacity = fields.Boolean(
        string='Overloaded',
        compute='_compute_capacity_usage',
        store=True,
    )
    over_capacity_weight = fields.Float(
        string='Overload weight (kg)',
        compute='_compute_capacity_usage',
        store=True,
        digits='Stock Weight',
    )

    franchise_count = fields.Integer(
        string='Store count',
        compute='_compute_franchise_area',
        store=True,
    )
    area_ids = fields.Many2many(
        'res.area',
        'wujia_batch_area_rel',
        'batch_id',
        'area_id',
        string='Area',
        compute='_compute_franchise_area',
        store=True,
    )

    pricelist_id = fields.Many2one(
        'wujia.fleet.pricelist',
        string='Pricelist',
        compute='_compute_pricelist_id',
        store=True,
        readonly=False,
        tracking=True,
        index=True,
        help="Shipping pricelist. Auto-suggested from vehicle type + carrier + date; can be overridden manually.",
    )

    currency_id = fields.Many2one(
        'res.currency',
        string='Currency',
        related='company_id.currency_id',
        store=True,
        readonly=True,
    )
    shipping_cost = fields.Monetary(
        string='Shipping cost',
        currency_field='currency_id',
        compute='_compute_shipping_cost',
        store=True,
        readonly=False,
        help='Auto-computed from the pricelist once vehicle + area are known; can be overridden.',
    )
    drop_fee_total = fields.Monetary(
        string='Total drop fee',
        currency_field='currency_id',
        compute='_compute_shipping_cost',
        store=True,
        readonly=False,
    )
    total_shipping_cost = fields.Monetary(
        string='Total delivery cost',
        currency_field='currency_id',
        compute='_compute_total_shipping_cost',
        store=True,
    )

    planned_departure = fields.Datetime(string='Planned departure')
    actual_departure = fields.Datetime(string='Actual departure')

    delivery_batch_status = fields.Selection(
        DELIVERY_BATCH_STATUS,
        string='Dispatch status',
        default='draft',
        index=True,
        tracking=True,
        help='Runs alongside the standard state — it does not replace the Odoo state.',
    )
    delivery_note = fields.Text(string='Dispatch note')

    # ===========================================================
    # Compute
    # ===========================================================
    @api.depends('planned_weight', 'vehicle_capacity_kg')
    def _compute_capacity_usage(self):
        for batch in self:
            cap = batch.vehicle_capacity_kg or 0.0
            planned = batch.planned_weight or 0.0
            if cap <= 0:
                batch.capacity_usage_percent = 0.0
                batch.is_over_capacity = False
                batch.over_capacity_weight = 0.0
            else:
                batch.capacity_usage_percent = (planned / cap) * 100.0
                batch.is_over_capacity = planned > cap
                batch.over_capacity_weight = max(planned - cap, 0.0)

    @api.depends('picking_ids.franchise_id', 'picking_ids.area_id')
    def _compute_franchise_area(self):
        for batch in self:
            franchises = batch.picking_ids.mapped('franchise_id')
            areas = batch.picking_ids.mapped('area_id')
            batch.franchise_count = len(franchises)
            batch.area_ids = [(6, 0, areas.ids)]

    @api.depends('vehicle_id', 'fleet_type_id', 'provider_id', 'scheduled_date', 'area_ids')
    def _compute_pricelist_id(self):
        # Prefetch tất cả pricelist active 1 lần thay vì search per batch
        # → tránh O(n) query khi compute trên list nhiều batch.
        batches_need_compute = self.filtered(lambda b: not b.pricelist_id and b.fleet_type_id)
        for b in self - batches_need_compute:
            if not b.fleet_type_id:
                b.pricelist_id = False
        if not batches_need_compute:
            return

        type_ids = batches_need_compute.fleet_type_id.ids
        Pricelist = self.env['wujia.fleet.pricelist']
        all_pricelists = Pricelist.search([
            ('state', '=', 'active'),
            ('fleet_type_id', 'in', type_ids),
        ], order='sequence, id')

        for batch in batches_need_compute:
            ref_date = (batch.scheduled_date and batch.scheduled_date.date()) or fields.Date.context_today(batch)
            candidates = all_pricelists.filtered(lambda p: (
                p.fleet_type_id == batch.fleet_type_id
                and p.date_from <= ref_date
                and (not p.date_to or p.date_to >= ref_date)
                and (not batch.provider_id or not p.provider_id or p.provider_id == batch.provider_id)
            ))
            batch.pricelist_id = candidates[:1]

    @api.depends(
        'pricelist_id',
        'pricelist_id.line_ids',
        'pricelist_id.default_drop_fee',
        'area_ids',
        'picking_ids.area_id',
    )
    def _compute_shipping_cost(self):
        for batch in self:
            pl = batch.pricelist_id
            if not pl or not batch.area_ids:
                batch.shipping_cost = 0.0
                batch.drop_fee_total = 0.0
                continue
            batch_area_ids = set(batch.area_ids.ids)
            matched_lines = pl.line_ids.filtered(
                lambda l: l.active and (set(l.area_ids.ids) & batch_area_ids)
            )
            # Cước cơ bản: lấy giá cao nhất trong các line match.
            batch.shipping_cost = max(matched_lines.mapped('price'), default=0.0)
            # Drop fee: với mỗi picking, cộng line.drop_fee match (nếu không có dùng default).
            drop_total = 0.0
            for pick in batch.picking_ids:
                if not pick.area_id:
                    continue
                pick_lines = matched_lines.filtered(lambda l: pick.area_id.id in l.area_ids.ids)
                if pick_lines:
                    drop_total += sum(pick_lines.mapped('drop_fee'))
                else:
                    drop_total += pl.default_drop_fee
            batch.drop_fee_total = drop_total

    @api.depends('shipping_cost', 'drop_fee_total')
    def _compute_total_shipping_cost(self):
        for batch in self:
            batch.total_shipping_cost = (batch.shipping_cost or 0.0) + (batch.drop_fee_total or 0.0)

    # ===========================================================
    # Actions trạng thái điều phối
    # ===========================================================
    def action_delivery_assign(self):
        for batch in self:
            batch.delivery_batch_status = 'assigned'

    def action_delivery_loading(self):
        for batch in self:
            batch.delivery_batch_status = 'loading'

    def action_delivery_start(self):
        for batch in self:
            batch.delivery_batch_status = 'delivering'
            batch.actual_departure = fields.Datetime.now()
            # Đẩy delivery_status của các picking → delivering.
            batch.picking_ids.filtered(
                lambda p: p.delivery_status not in ('done', 'cancelled')
            ).write({'delivery_status': 'delivering'})

    def action_delivery_done(self):
        for batch in self:
            batch.delivery_batch_status = 'done'

    def action_delivery_cancel(self):
        for batch in self:
            batch.delivery_batch_status = 'cancelled'
