from odoo import _, api, fields, models
from odoo.exceptions import UserError


class StockPickingToBatch(models.TransientModel):
    _inherit = 'stock.picking.to.batch'

    batch_id = fields.Many2one(
        'stock.picking.batch',
        string='Batch Transfer',
        domain="[('is_wave', '=', False), ('state', 'in', ('draft', 'in_progress')), ('delivery_batch_status', 'in', ('draft', 'assigned', 'loading')), ('vehicle_id', '!=', False)]",
    )
    picking_ids = fields.Many2many(
        'stock.picking',
        string='Selected Transfers',
        help="Transfers selected for batch dispatch.",
    )
    vehicle_id = fields.Many2one(
        'wujia.fleet.management',
        string='Delivery Vehicle',
        domain=[('active', '=', True)],
        help="Vehicle assigned to carry this batch transfer.",
    )
    provider_id = fields.Many2one(
        'wujia.fleet.provider',
        string='Carrier',
        compute='_compute_vehicle_info',
        readonly=True,
    )
    vehicle_capacity_kg = fields.Float(
        string='Vehicle Capacity (kg)',
        compute='_compute_vehicle_info',
        readonly=True,
        digits='Stock Weight',
    )

    picking_count = fields.Integer(
        string='Selected Pickings',
        compute='_compute_stats',
        readonly=True,
    )
    store_count = fields.Integer(
        string='Unique Stores',
        compute='_compute_stats',
        readonly=True,
    )
    selected_weight = fields.Float(
        string='Selected Weight (kg)',
        compute='_compute_stats',
        readonly=True,
        digits='Stock Weight',
    )
    current_batch_weight = fields.Float(
        string='Current Batch Weight (kg)',
        compute='_compute_stats',
        readonly=True,
        digits='Stock Weight',
    )
    resulting_weight = fields.Float(
        string='Resulting Weight (kg)',
        compute='_compute_stats',
        readonly=True,
        digits='Stock Weight',
    )
    capacity_utilization_percent = fields.Float(
        string='Capacity Utilisation %',
        compute='_compute_stats',
        readonly=True,
        digits=(8, 1),
    )
    capacity_utilization_ratio = fields.Float(
        string='Capacity Utilisation',
        compute='_compute_stats',
        readonly=True,
    )
    has_missing_weight = fields.Boolean(
        string='Has Missing Weight',
        compute='_compute_stats',
        readonly=True,
    )
    is_over_capacity = fields.Boolean(
        string='Overloaded',
        compute='_compute_stats',
        readonly=True,
    )
    overload_weight = fields.Float(
        string='Overload Weight (kg)',
        compute='_compute_stats',
        readonly=True,
        digits='Stock Weight',
    )
    alert_level = fields.Selection(
        [
            ('danger', 'Overload'),
            ('warning', 'Missing Weight'),
            ('success', 'Valid'),
            ('info', 'No Vehicle'),
        ],
        string='Alert Level',
        compute='_compute_stats',
        readonly=True,
    )
    alert_message = fields.Char(
        string='Alert Message',
        compute='_compute_stats',
        readonly=True,
    )

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        active_ids = self.env.context.get('active_ids') or []
        if active_ids and self.env.context.get('active_model') == 'stock.picking':
            pickings = self.env['stock.picking'].browse(active_ids).exists()
            res['picking_ids'] = [(6, 0, pickings.ids)]
            self._check_homogeneity(pickings)
        return res

    def _check_homogeneity(self, pickings):
        """Validate that all selected pickings share company, picking type, and source location."""
        if not pickings:
            return
        if len(pickings.mapped('company_id')) > 1:
            raise UserError(_("All selected pickings must belong to the same company."))
        if len(pickings.mapped('picking_type_id')) > 1:
            raise UserError(_("All selected pickings must have the same operation type."))
        if len(pickings.mapped('location_id')) > 1:
            raise UserError(_("All selected pickings must have the same source location."))

    @api.depends('mode', 'vehicle_id', 'batch_id', 'batch_id.vehicle_id')
    def _compute_vehicle_info(self):
        for wiz in self:
            if wiz.mode == 'new':
                vehicle = wiz.vehicle_id
            else:
                vehicle = wiz.batch_id.vehicle_id
            wiz.provider_id = vehicle.provider_id
            wiz.vehicle_capacity_kg = vehicle.max_payload_kg or 0.0

    @api.depends(
        'picking_ids',
        'picking_ids.planned_weight',
        'picking_ids.franchise_id',
        'picking_ids.move_ids.product_id.weight',
        'mode',
        'vehicle_id',
        'vehicle_id.max_payload_kg',
        'batch_id',
        'batch_id.vehicle_id',
        'batch_id.vehicle_id.max_payload_kg',
        'batch_id.planned_weight',
    )
    def _compute_stats(self):
        for wiz in self:
            pickings = wiz.picking_ids
            wiz.picking_count = len(pickings)
            stores = pickings.mapped('franchise_id').filtered(lambda s: s)
            wiz.store_count = len(stores)

            sel_weight = sum(pickings.mapped('planned_weight'))
            wiz.selected_weight = sel_weight

            if wiz.mode == 'existing' and wiz.batch_id:
                cur_weight = wiz.batch_id.planned_weight or 0.0
                vehicle = wiz.batch_id.vehicle_id
            else:
                cur_weight = 0.0
                vehicle = wiz.vehicle_id

            wiz.current_batch_weight = cur_weight
            res_weight = cur_weight + sel_weight
            wiz.resulting_weight = res_weight

            max_cap = vehicle.max_payload_kg or 0.0

            # Check if any non-service product in moves has missing weight
            has_missing = any(
                (not m.product_id.weight or m.product_id.weight <= 0)
                for p in pickings
                for m in p.move_ids
                if m.product_id and m.product_id.type != 'service'
            )
            wiz.has_missing_weight = has_missing

            if max_cap > 0:
                ratio = res_weight / max_cap
                utilization = ratio * 100.0
                is_over = res_weight > max_cap
                over_weight = max(res_weight - max_cap, 0.0)
            else:
                ratio = 0.0
                utilization = 0.0
                is_over = False
                over_weight = 0.0

            wiz.capacity_utilization_ratio = ratio
            wiz.capacity_utilization_percent = utilization
            wiz.is_over_capacity = is_over
            wiz.overload_weight = over_weight

            if not vehicle:
                wiz.alert_level = 'info'
                wiz.alert_message = _("Please select a delivery vehicle to inspect load capacity.")
            elif is_over:
                wiz.alert_level = 'danger'
                wiz.alert_message = _(
                    "WARNING: VEHICLE OVERLOAD! Exceeds capacity by %.1f kg (Total: %.1f kg / Max: %.1f kg)."
                ) % (over_weight, res_weight, max_cap)
            elif has_missing:
                wiz.alert_level = 'warning'
                wiz.alert_message = _(
                    "WARNING: Some products have no weight specified; load capacity cannot be accurately verified (Recorded: %.1f kg / Max: %.1f kg)."
                ) % (res_weight, max_cap)
            else:
                wiz.alert_level = 'success'
                wiz.alert_message = _(
                    "VALID: Reached %.1f%% of vehicle capacity (%.1f kg / %.1f kg)."
                ) % (utilization, res_weight, max_cap)

    def attach_pickings(self):
        self.ensure_one()
        pickings = self.picking_ids
        if not pickings:
            active_ids = self.env.context.get('active_ids') or []
            pickings = self.env['stock.picking'].browse(active_ids).exists()

        if not pickings:
            raise UserError(_("No pickings selected for dispatch planning."))

        self._check_homogeneity(pickings)

        # Anti-concurrency check: re-read active records from database
        fresh_pickings = self.env['stock.picking'].browse(pickings.ids).exists()
        if len(fresh_pickings) != len(pickings):
            raise UserError(_("Some selected pickings no longer exist in the system."))

        conflicted = fresh_pickings.filtered(
            lambda p: p.batch_id and (self.mode == 'new' or p.batch_id != self.batch_id)
        )
        if conflicted:
            names = ", ".join(conflicted.mapped('name'))
            raise UserError(_(
                "The following picking(s) are already assigned to another batch transfer: %s. "
                "Please refresh the list and try again."
            ) % names)

        invalid_state = fresh_pickings.filtered(lambda p: p.state in ('done', 'cancel'))
        if invalid_state:
            names = ", ".join(invalid_state.mapped('name'))
            raise UserError(_(
                "The following picking(s) are already completed or cancelled: %s. "
                "Please refresh the list and try again."
            ) % names)

        if self.mode == 'new':
            if not self.vehicle_id:
                raise UserError(_("Please select a delivery vehicle for the new batch transfer."))
            company = fresh_pickings.company_id
            batch = self.env['stock.picking.batch'].create({
                'user_id': self.user_id.id or self.env.user.id,
                'company_id': company.id,
                'picking_type_id': fresh_pickings[0].picking_type_id.id,
                'description': self.description,
                'vehicle_id': self.vehicle_id.id,
                'delivery_batch_status': 'assigned',
            })
            notification_title = _("The following batch transfer has been created")
        else:
            if not self.batch_id:
                raise UserError(_("Please select an existing batch transfer."))
            if self.batch_id.delivery_batch_status not in ('draft', 'assigned', 'loading'):
                raise UserError(_("Cannot add pickings to a batch that has already departed, completed, or been cancelled."))
            if not self.batch_id.vehicle_id:
                raise UserError(_("The selected batch transfer must have an assigned vehicle."))
            if self.batch_id.company_id != fresh_pickings[0].company_id:
                raise UserError(_("The selected batch belongs to a different company."))
            if self.batch_id.picking_ids and any(p.location_id != fresh_pickings[0].location_id for p in self.batch_id.picking_ids):
                raise UserError(_("The selected batch has a different source location."))
            batch = self.batch_id
            notification_title = _("The following batch transfer has been updated")

        # Overload authorization check
        vehicle = batch.vehicle_id
        max_cap = vehicle.max_payload_kg or 0.0
        total_weight = (batch.planned_weight or 0.0) + sum(fresh_pickings.mapped('planned_weight'))
        if max_cap > 0 and total_weight > max_cap:
            if not (
                self.env.user.has_group('wujia_fleet.group_fleet_manager')
                or self.env.user.has_group('stock.group_stock_manager')
                or self.env.is_superuser()
            ):
                raise UserError(_(
                    "Vehicle overload detected (%.1f kg over capacity). "
                    "Only Fleet Managers or Inventory Managers can approve overloaded dispatch."
                ) % (total_weight - max_cap))

        fresh_pickings.write({'batch_id': batch.id})

        if self.mode == 'new' and not self.is_create_draft:
            batch.action_confirm()

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': notification_title,
                'message': '%s',
                'links': [{
                    'label': batch.name,
                    'url': f'/odoo/action-stock_picking_batch.stock_picking_batch_action/{batch.id}',
                }],
                'sticky': False,
                'next': {'type': 'ir.actions.act_window_close'},
            },
        }
