# -*- coding: utf-8 -*-
from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install', 'wujia_dynamic_tracking')
class TestDynamicTracking(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.TrackingConfig = cls.env['wujia.field.tracking.config']
        cls.IrModel = cls.env['ir.model']
        cls.Partner = cls.env['res.partner']

        # Find or ensure model res.partner is mail.thread
        cls.partner_model = cls.IrModel.search([('model', '=', 'res.partner')], limit=1)

    def test_01_is_mail_thread_computed(self):
        """Verify that is_mail_thread is True for res.partner and False for models without chatter."""
        self.assertTrue(self.partner_model.is_mail_thread, "res.partner must be recognized as having mail.thread")

        ir_model_model = self.IrModel.search([('model', '=', 'ir.model')], limit=1)
        self.assertFalse(ir_model_model.is_mail_thread, "ir.model must not have mail.thread")

    def test_02_fetch_model_fields(self):
        """Test fetching fields automatically into tracking configuration."""
        config = self.TrackingConfig.create({
            'model_id': self.partner_model.id,
        })
        self.assertEqual(len(config.line_ids), 0)

        config.action_fetch_model_fields()
        self.assertTrue(len(config.line_ids) > 0, "Lines must be populated with partner fields")

        # Verify specific partner field exists in line_ids
        website_line = config.line_ids.filtered(lambda l: l.field_name == 'website')
        self.assertTrue(website_line, "Field 'website' should be present in fetched lines")

    def test_03_dynamic_field_tracking_in_chatter(self):
        """Test enabling tracking dynamically for website field and verifying chatter message."""
        config = self.TrackingConfig.create({
            'model_id': self.partner_model.id,
        })
        config.action_fetch_model_fields()

        # Find field 'website' which is not tracked by default in res.partner
        website_line = config.line_ids.filtered(lambda l: l.field_name == 'website')
        self.assertTrue(website_line)

        # Enable dynamic tracking
        website_line.write({'is_tracked': True})

        # Verify that 'website' is now in _track_get_fields() (cache automatically cleared on write)
        tracked_fields = self.Partner._track_get_fields()
        self.assertIn('website', tracked_fields, "'website' must now be included in tracked fields")

        # Create a partner and update website
        partner = self.Partner.create({'name': 'Test Partner Dynamic Tracking'})
        self.env.flush_all()
        self.cr.precommit.run()
        msg_count_before = len(partner.message_ids)

        partner.write({'website': 'https://wujiatea.com'})
        self.env.flush_all()
        self.cr.precommit.run()

        # Verify a new tracking message was created in chatter
        msg_count_after = len(partner.message_ids)
        self.assertTrue(msg_count_after > msg_count_before, "A chatter message must be logged when tracked field changes")

        tracking_values = partner.message_ids.mapped('tracking_value_ids')
        tracked_field_names = tracking_values.mapped('field_id.name')
        self.assertIn('website', tracked_field_names, "Tracking value for 'website' must be recorded in chatter")

    def test_04_mail_tracking_value_fields(self):
        """Verify author_id, date, and record_name on mail.tracking.value."""
        config = self.TrackingConfig.create({
            'model_id': self.partner_model.id,
        })
        config.action_fetch_model_fields()
        website_line = config.line_ids.filtered(lambda l: l.field_name == 'website')
        website_line.write({'is_tracked': True})

        partner = self.Partner.create({'name': 'Partner Tracking Value Test'})
        self.env.flush_all()
        self.cr.precommit.run()

        partner.write({'website': 'https://test-tracking-author.com'})
        self.env.flush_all()
        self.cr.precommit.run()

        tracking_values = partner.message_ids.mapped('tracking_value_ids')
        website_tv = tracking_values.filtered(lambda tv: tv.field_id.name == 'website')
        self.assertTrue(website_tv, "Tracking value for website must exist")
        self.assertEqual(website_tv.author_id, self.env.user.partner_id, "author_id must match current user partner")
        self.assertTrue(website_tv.date, "date must be populated on tracking value")
        self.assertEqual(website_tv.record_name, partner.name, "record_name must match partner name")

    def test_05_binary_fields_excluded_from_fetch(self):
        """Verify binary and unsupported fields are excluded and purged from tracking lines."""
        config = self.TrackingConfig.create({
            'model_id': self.partner_model.id,
        })
        config.action_fetch_model_fields()

        # res.partner has image_1920 (binary), it should NOT be in line_ids
        binary_lines = config.line_ids.filtered(lambda l: l.ttype == 'binary')
        self.assertEqual(len(binary_lines), 0, "Binary fields like image_1920 must not be fetched into tracking lines")

    def test_06_binary_tracking_handled_gracefully(self):
        """Verify binary field tracking produces tracking values without raising NotImplementedError."""
        field_info = self.Partner.fields_get(['image_1920'])['image_1920']
        partner = self.Partner.create({'name': 'Binary Test Partner'})

        vals = self.env['mail.tracking.value']._create_tracking_values(
            False, b'fake_binary_data', 'image_1920', field_info, partner
        )
        self.assertEqual(vals.get('old_value_char'), 'Empty')
        self.assertEqual(vals.get('new_value_char'), 'Attached / Signed')
