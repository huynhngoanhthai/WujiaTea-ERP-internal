from odoo.exceptions import AccessError, UserError
from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install', 'wujia_delivery')
class TestTransportPlanningWizard(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company

        # Location setup
        cls.customer_loc = cls.env.ref('stock.stock_location_customers')
        cls.stock_loc = cls.env.ref('stock.stock_location_stock')

        # Operation type with transport planning enabled
        cls.picking_type_dispatch = cls.env['stock.picking.type'].create({
            'name': 'Delivery to Stores',
            'code': 'outgoing',
            'sequence_code': 'OUT-DISPATCH',
            'default_location_src_id': cls.stock_loc.id,
            'default_location_dest_id': cls.customer_loc.id,
            'requires_transport_planning': True,
            'company_id': cls.company.id,
        })

        # Operation type without transport planning
        cls.picking_type_normal = cls.env['stock.picking.type'].create({
            'name': 'Normal Outgoing',
            'code': 'outgoing',
            'sequence_code': 'OUT-NORM',
            'default_location_src_id': cls.stock_loc.id,
            'default_location_dest_id': cls.customer_loc.id,
            'requires_transport_planning': False,
            'company_id': cls.company.id,
        })

        # Products
        cls.product_heavy = cls.env['product.product'].create({
            'name': 'Heavy Tea Bags',
            'type': 'consu',
            'weight': 100.0,  # 100 kg each
        })
        cls.product_light = cls.env['product.product'].create({
            'name': 'Straws Pack',
            'type': 'consu',
            'weight': 5.0,  # 5 kg each
        })
        cls.product_no_weight = cls.env['product.product'].create({
            'name': 'Marketing Flyer',
            'type': 'consu',
            'weight': 0.0,
        })

        # Partners
        cls.partner_a = cls.env['res.partner'].create({'name': 'Store Franchise A'})
        cls.partner_b = cls.env['res.partner'].create({'name': 'Store Franchise B'})

        # Fleet provider and vehicle
        cls.provider = cls.env['wujia.fleet.provider'].create({
            'name': 'Fast Transport Co',
            'code': 'P-TEST-01',
        })
        cls.fleet_type = cls.env['wujia.fleet.type'].create({
            'name': '1.5 Ton Truck',
            'code': 'T-1.5T',
            'payload_capacity_ton': 1.5,
        })
        cls.vehicle = cls.env['wujia.fleet.management'].create({
            'name': 'Truck 50H-190.78',
            'code': 'V-TEST-01',
            'provider_id': cls.provider.id,
            'fleet_type_id': cls.fleet_type.id,
            'license_plate': '50H-190.78',
            'payload_capacity_ton': 1.5,
        })

        # Users for permission checks
        cls.fleet_user = cls.env['res.users'].create({
            'name': 'Fleet Dispatcher User',
            'login': 'fleet_dispatcher_test',
            'email': 'dispatcher@test.com',
            'group_ids': [(6, 0, [
                cls.env.ref('base.group_user').id,
                cls.env.ref('stock.group_stock_user').id,
                cls.env.ref('wujia_fleet.group_fleet_user').id,
            ])],
        })
        cls.fleet_manager = cls.env['res.users'].create({
            'name': 'Fleet Manager User',
            'login': 'fleet_manager_test',
            'email': 'manager@test.com',
            'group_ids': [(6, 0, [
                cls.env.ref('base.group_user').id,
                cls.env.ref('stock.group_stock_user').id,
                cls.env.ref('wujia_fleet.group_fleet_user').id,
                cls.env.ref('wujia_fleet.group_fleet_manager').id,
            ])],
        })

    def _create_picking(self, picking_type, partner, product, qty, scheduled_date=False):
        picking = self.env['stock.picking'].create({
            'picking_type_id': picking_type.id,
            'partner_id': partner.id,
            'location_id': picking_type.default_location_src_id.id,
            'location_dest_id': picking_type.default_location_dest_id.id,
            'scheduled_date': scheduled_date,
        })
        move = self.env['stock.move'].create({
            'product_id': product.id,
            'product_uom_qty': qty,
            'product_uom': product.uom_id.id,
            'location_id': picking.location_id.id,
            'location_dest_id': picking.location_dest_id.id,
            'picking_id': picking.id,
        })
        picking.action_confirm()
        return picking

    def test_01_pending_dispatch_filter(self):
        """Test that only pickings with requires_transport_planning=True, batch_id=False,
        and state in ('waiting', 'confirmed', 'assigned') match the pending dispatch domain."""
        pick1 = self._create_picking(self.picking_type_dispatch, self.partner_a, self.product_light, 10)
        pick2 = self._create_picking(self.picking_type_normal, self.partner_a, self.product_light, 10)

        domain = [
            ('batch_id', '=', False),
            ('state', 'in', ('waiting', 'confirmed', 'assigned')),
            ('picking_type_id.requires_transport_planning', '=', True),
        ]
        pending_picks = self.env['stock.picking'].search(domain)
        self.assertIn(pick1, pending_picks, "Picking with requires_transport_planning must appear in pending dispatch.")
        self.assertNotIn(pick2, pending_picks, "Picking without requires_transport_planning must not appear.")

    def test_02_wizard_homogeneity_validation(self):
        """Homogeneity validation: raises UserError if pickings have different picking types or locations."""
        pick1 = self._create_picking(self.picking_type_dispatch, self.partner_a, self.product_light, 5)
        pick2 = self._create_picking(self.picking_type_normal, self.partner_b, self.product_light, 5)

        Wizard = self.env['stock.picking.to.batch']
        with self.assertRaises(UserError) as cm:
            Wizard.with_context(active_ids=[pick1.id, pick2.id], active_model='stock.picking').create({
                'mode': 'new',
                'vehicle_id': self.vehicle.id,
            })
        self.assertIn("same operation type", str(cm.exception))

    def test_03_wizard_successful_dispatch_new_batch(self):
        """Dispatch pickings to a new batch with vehicle: batch is created with assigned status and pickings bound."""
        pick1 = self._create_picking(self.picking_type_dispatch, self.partner_a, self.product_light, 10)  # 50 kg
        pick2 = self._create_picking(self.picking_type_dispatch, self.partner_b, self.product_light, 20)  # 100 kg

        wiz = self.env['stock.picking.to.batch'].with_context(
            active_ids=[pick1.id, pick2.id],
            active_model='stock.picking',
        ).create({
            'mode': 'new',
            'vehicle_id': self.vehicle.id,
        })

        self.assertEqual(wiz.picking_count, 2)
        self.assertEqual(wiz.selected_weight, 150.0)
        self.assertEqual(wiz.vehicle_capacity_kg, 1500.0)
        self.assertFalse(wiz.is_over_capacity)
        self.assertEqual(wiz.alert_level, 'success')

        res = wiz.attach_pickings()
        self.assertTrue(res.get('params', {}).get('links'))

        batch = pick1.batch_id
        self.assertTrue(batch, "Pickings must be linked to newly created batch.")
        self.assertEqual(pick2.batch_id, batch)
        self.assertEqual(batch.vehicle_id, self.vehicle)
        self.assertEqual(batch.delivery_batch_status, 'assigned')
        self.assertEqual(pick1.delivery_status, 'assigned')
        self.assertEqual(pick2.delivery_status, 'assigned')

    def test_04_wizard_overload_permission(self):
        """Overload detection: raises UserError for normal dispatcher, allowed for Fleet Manager."""
        # Vehicle max capacity = 1500 kg. We create picking with 2000 kg (20 * 100 kg).
        pick = self._create_picking(self.picking_type_dispatch, self.partner_a, self.product_heavy, 20)

        # 1. Normal dispatcher user tries to confirm overloaded dispatch -> BLOCKED
        wiz_user = self.env['stock.picking.to.batch'].with_user(self.fleet_user).with_context(
            active_ids=[pick.id],
            active_model='stock.picking',
        ).create({
            'mode': 'new',
            'vehicle_id': self.vehicle.id,
        })
        self.assertTrue(wiz_user.is_over_capacity)
        self.assertEqual(wiz_user.alert_level, 'danger')
        self.assertEqual(wiz_user.overload_weight, 500.0)

        with self.assertRaises(UserError) as cm:
            wiz_user.attach_pickings()
        self.assertIn("Vehicle overload detected", str(cm.exception))

        # 2. Manager user confirms overloaded dispatch -> ALLOWED
        wiz_mgr = self.env['stock.picking.to.batch'].with_user(self.fleet_manager).with_context(
            active_ids=[pick.id],
            active_model='stock.picking',
        ).create({
            'mode': 'new',
            'vehicle_id': self.vehicle.id,
        })
        wiz_mgr.attach_pickings()
        self.assertTrue(pick.batch_id, "Manager must be able to approve overloaded dispatch.")

    def test_05_anti_concurrency_conflict_rollback(self):
        """Concurrency protection: if a picking is already assigned to a batch, wizard aborts."""
        pick1 = self._create_picking(self.picking_type_dispatch, self.partner_a, self.product_light, 10)
        pick2 = self._create_picking(self.picking_type_dispatch, self.partner_b, self.product_light, 10)

        # Another user already assigned pick1 to another batch
        existing_batch = self.env['stock.picking.batch'].create({
            'company_id': self.company.id,
            'picking_type_id': self.picking_type_dispatch.id,
            'vehicle_id': self.vehicle.id,
        })
        pick1.write({'batch_id': existing_batch.id})

        wiz = self.env['stock.picking.to.batch'].create({
            'mode': 'new',
            'vehicle_id': self.vehicle.id,
            'picking_ids': [(6, 0, [pick1.id, pick2.id])],
        })

        with self.assertRaises(UserError) as cm:
            wiz.attach_pickings()
        self.assertIn("already assigned to another batch transfer", str(cm.exception))
        self.assertFalse(pick2.batch_id, "Transaction must rollback, leaving pick2 unassigned.")

    def test_06_reversibility_when_unlinked_from_batch(self):
        """Reversibility: removing picking from batch reverts delivery_status to pending."""
        pick = self._create_picking(self.picking_type_dispatch, self.partner_a, self.product_light, 10)
        wiz = self.env['stock.picking.to.batch'].with_context(
            active_ids=[pick.id],
            active_model='stock.picking',
        ).create({
            'mode': 'new',
            'vehicle_id': self.vehicle.id,
        })
        wiz.attach_pickings()
        self.assertEqual(pick.delivery_status, 'assigned')

        # Remove from batch
        pick.write({'batch_id': False})
        self.assertEqual(pick.delivery_status, 'pending')

        # Check it is in pending dispatch domain
        pending_picks = self.env['stock.picking'].search([
            ('batch_id', '=', False),
            ('state', 'in', ('waiting', 'confirmed', 'assigned')),
            ('picking_type_id.requires_transport_planning', '=', True),
        ])
        self.assertIn(pick, pending_picks, "Unlinked picking must return to pending dispatch queue.")
