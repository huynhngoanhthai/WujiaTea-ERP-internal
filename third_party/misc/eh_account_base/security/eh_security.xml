<?xml version="1.0" encoding="UTF-8" ?>
<odoo noupdate="0">
    <data>

        <!--
            Privilege groups for the ERP Heritage accounting suite.

            Why a dedicated privilege rather than reusing account.group_
            account_user / _manager directly: lets a deployment grant
            standard accounting access to one cohort and EH suite access
            to a different (overlapping) cohort. An accounting user who
            does not need the EH features simply does not get the
            eh_account_base.group_eh_user assignment, while still being
            able to perform every standard Odoo accounting task.

            Both new groups imply the corresponding upstream account.
            group_account_* group, so any user assigned an EH group can
            reach every base accounting feature too. The post-install
            migration script seeds the new groups by copying every
            existing account.group_account_user / _manager member into
            the corresponding eh group, so an upgrade from 19.0.1.0.0 to
            19.0.1.0.1 preserves all current EH-module access.
        -->

        <record id="privilege_eh_accounting" model="res.groups.privilege">
            <field name="name">ERP Heritage Accounting Suite</field>
            <field name="sequence">90</field>
        </record>

        <record id="group_eh_user" model="res.groups">
            <field name="name">EH Accounting User</field>
            <field name="privilege_id" ref="privilege_eh_accounting"/>
            <field name="implied_ids" eval="[(4, ref('account.group_account_user'))]"/>
            <field name="comment">Read and operational access to ERP Heritage accounting modules. Implies the standard Accounting User role.</field>
        </record>

        <record id="group_eh_manager" model="res.groups">
            <field name="name">EH Accounting Manager</field>
            <field name="privilege_id" ref="privilege_eh_accounting"/>
            <field name="implied_ids" eval="[(4, ref('eh_account_base.group_eh_user')), (4, ref('account.group_account_manager'))]"/>
            <field name="comment">Manager access to ERP Heritage accounting modules: posting, configuration, override actions. Implies the standard Accounting Manager role.</field>
        </record>

        <!--
            Read-only auditor role.

            Grants visibility on every audit-log table and the report
            execution log without granting write access to any operational
            object. An auditor can re-run reports, inspect override
            history, trace approval decisions, and read the cache audit
            entries; they cannot post journal entries, edit budgets,
            modify mandates, or touch configuration. The role is a
            standalone group; it deliberately does NOT imply group_eh_user
            so an auditor account stays read-only.

            Per-model read access is granted via dedicated rows in
            ir.model.access.csv with perm_write/create/unlink set to 0.
            Modules that own audit log tables add the auditor row
            themselves so the auditor's reach grows with the suite.
        -->
        <record id="group_eh_auditor" model="res.groups">
            <field name="name">EH Accounting Auditor (read-only)</field>
            <field name="privilege_id" ref="privilege_eh_accounting"/>
            <field name="implied_ids" eval="[(4, ref('account.group_account_readonly'))]"/>
            <field name="comment">Read-only auditor: visibility on every ERP Heritage audit log without write access. Cannot post, edit, or delete operational data.</field>
        </record>

    </data>
</odoo>
