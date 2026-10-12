# -*- coding: utf-8 -*-
from odoo.tests.common import TransactionCase


class TestWujiaMobileCore(TransactionCase):
    """Automated unit tests for wujia_mobile_core module architecture,
    Odoo 19 security groups, and wujia.mobile.mixin helper methods.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))
        cls.mixin_model = cls.env['wujia.mobile.mixin']

    def test_01_security_group_exists(self):
        """Verify that Odoo 19 res.groups.privilege and user group exist."""
        privilege = self.env.ref('wujia_mobile_core.res_groups_privilege_wujia_mobile', raise_if_not_found=False)
        self.assertTrue(privilege, "Privilege res_groups_privilege_wujia_mobile must exist.")

        group = self.env.ref('wujia_mobile_core.group_wujia_mobile_user', raise_if_not_found=False)
        self.assertTrue(group, "Security group group_wujia_mobile_user must exist.")
        self.assertEqual(group.name, "User", "Group name must be set to 'User' per Rule 12.")

    def test_02_badge_class_mapping(self):
        """Verify state badge class mapping in wujia.mobile.mixin."""
        # BEM style (default)
        self.assertEqual(self.mixin_model.get_mobile_badge_class('sale'), 'wj_mobile_badge--success')
        self.assertEqual(self.mixin_model.get_mobile_badge_class('done'), 'wj_mobile_badge--success')
        self.assertEqual(self.mixin_model.get_mobile_badge_class('draft'), 'wj_mobile_badge--warning')
        self.assertEqual(self.mixin_model.get_mobile_badge_class('cancel'), 'wj_mobile_badge--danger')
        self.assertEqual(self.mixin_model.get_mobile_badge_class('assigned'), 'wj_mobile_badge--info')
        self.assertEqual(self.mixin_model.get_mobile_badge_class(False), 'wj_mobile_badge--neutral')

        # Legacy style
        self.assertEqual(self.mixin_model.get_mobile_badge_class('sale', style='legacy'), 'bg-wujia-success')
        self.assertEqual(self.mixin_model.get_mobile_badge_class('draft', style='legacy'), 'bg-wujia-warning')
