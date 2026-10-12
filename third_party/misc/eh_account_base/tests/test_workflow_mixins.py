# -*- encoding: utf-8 -*-
##############################################################################
# ERP Heritage - Copyright (C) 2026 (https://www.erpheritage.com.au/)
##############################################################################
"""Focused contracts for shared workflow and post-once mixins."""

import inspect

from odoo.tests import tagged

from odoo.addons.eh_account_base.models.workflow_mixins import (
    EhPostOnce,
    EhWorkflowGuard,
)

from .common import EhAccountUnitTestCase


@tagged('eh_account_base', 'unit')
class TestWorkflowMixinContracts(EhAccountUnitTestCase):

    def test_guard_uses_server_provenance_not_context_sentinel(self):
        source = '\n'.join((
            inspect.getsource(EhWorkflowGuard.create),
            inspect.getsource(EhWorkflowGuard.write),
        ))
        self.assertIn('env.su', source)
        self.assertNotIn('EH_WORKFLOW_ACTION', source)
        self.assertNotIn("context.get('eh_workflow_action')", source)

    def test_post_once_locks_are_sorted_stable_and_actor_independent(self):
        helper = self.env['eh.post.once']
        first = helper._eh_lock_post_once_sources('actual_ids', [9, 2, 9])
        second = helper._eh_lock_post_once_sources('actual_ids', [2, 9])

        self.assertEqual(first, second)
        self.assertEqual(first, (
            'eh.post.once:post-once:actual_ids:2',
            'eh.post.once:post-once:actual_ids:9',
        ))
        self.assertNotIn(str(self.env.uid), ':'.join(first))

    def test_post_once_duplicate_search_is_sudo_and_includes_archived(self):
        source = inspect.getsource(EhPostOnce._eh_assert_source_unposted)
        self.assertIn('self.sudo()', source)
        self.assertIn('active_test=False', source)
        self.assertIn('FOR UPDATE', source)
