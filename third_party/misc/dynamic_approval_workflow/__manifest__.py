# Copyright 2026 Abdalrahman Shahrour
{
    "name": "Dynamic Approval Workflow",
    "version": "19.0.1.0.1",
    "summary": "Reusable multi-stage approval engine for any Odoo model",
    "description": """
        Provides a configurable, multi-stage approval engine that can be added
        to any Odoo model without modifying existing code.

        Key features:
        - ApprovalMixin AbstractModel for zero-touch integration
        - Domain-filtered workflow configurations per model
        - Per-stage approvers: specific user, group, or dynamic field
        - Full state machine: draft → pending → approved / rejected / returned
        - Chatter-based audit trail on every document
        - OWL dashboard: "My Pending Approvals" with live count badges
        - Cron-based escalation for overdue requests
        - Email notifications to approvers on each stage
        - Server action hook for Automated Actions integration
    """,
    "author": "Abdalrahman Shahrour",
    "website": "https://github.com/AbdelrahmanShahrour",
    "category": "Technical",
    "depends": ["base", "mail", "base_automation", "sale"],
    "data": [
        "security/security.xml",
        "security/ir.model.access.csv",
        "data/approval_sequence.xml",
        "data/approval_email_template.xml",
        "data/approval_workflow_data.xml",
        "data/approval_cron.xml",
        "data/approval_server_action.xml",
        "views/approval_workflow_config_views.xml",
        "views/approval_request_views.xml",
        "views/sale_order_views.xml",
        "wizard/approval_action_wizard_views.xml",
        "views/menus.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "dynamic_approval_workflow/static/src/js/my_approvals_dashboard.js",
            "dynamic_approval_workflow/static/src/xml/my_approvals_dashboard.xml",
            "dynamic_approval_workflow/static/src/scss/my_approvals_dashboard.scss",
        ],
    },
    "installable": True,
    "application": True,
    "auto_install": False,
    "license": "LGPL-3",
    "price": 00.0,
    "currency": "USD",
    "images": ["static/description/images/Screenshot8-dashboard-screen.png"],
}
