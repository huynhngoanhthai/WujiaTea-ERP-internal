/** @odoo-module **/

/**
 * Onboarding tour for the ERP Heritage Approval Workflow.
 *
 * Reachable from a chat-bubble icon next to the user menu when the
 * user has not yet dismissed it. Walks a first-time admin through
 * the two concrete things they need to do before approvals will
 * actually gate posts:
 *
 *   1. Open the Approval menu (which lands on the kanban).
 *   2. Visit Approval Policies and create a per-document-type
 *      policy with at least one rule.
 *   3. Add an approver group + an SLA target on the rule.
 *
 * The tour deliberately does NOT cover the request-side flow
 * (creating + approving + rejecting) — that's pure click-through
 * for an end user, not a setup task an admin has to learn.
 *
 * The tour is auto-discovered by the tour service via the
 * registry.category("web_tour.tours") add call below; it ships
 * disabled-by-default and starts when the user clicks the floating
 * Tutorials button OR by URL ?tour=eh_approval_setup_tour.
 */

import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { markup } from "@odoo/owl";

registry.category("web_tour.tours").add("eh_approval_setup_tour", {
    url: "/odoo",
    steps: () => [
        {
            trigger: ".o_main_navbar",
            content: markup(_t(
                "Welcome to the <b>Approval Workflow</b>. " +
                "This walkthrough shows the two setup steps " +
                "you need to do before approvals start gating posts."
            )),
            run: () => {},
        },
        {
            trigger: 'a.o_menu_brand, button[data-menu-xmlid="account.menu_finance"]',
            content: markup(_t(
                "Open the <b>Accounting</b> menu first."
            )),
            run: "click",
        },
        {
            trigger: ".o_main_navbar",
            content: markup(_t(
                "Now find the <b>Approval Policies</b> entry under " +
                "Configuration. A policy maps a document type " +
                "(vendor bills, customer invoices, journal entries) " +
                "to a set of approver groups."
            )),
            run: () => {},
        },
        {
            trigger: ".breadcrumb",
            content: markup(_t(
                "On a policy, add at least one <b>rule</b> with an " +
                "amount band and an ordered list of approver groups. " +
                "The first rule whose band matches the move's amount " +
                "wins; the request walks the group list one signature " +
                "at a time."
            )),
            run: () => {},
        },
        {
            trigger: ".o_main_navbar",
            content: markup(_t(
                "Set <b>SLA hours</b>, <b>Reminder hours</b>, and an " +
                "<b>Escalation group</b> on the rule for the request " +
                "to track its deadline. The hourly cron sends " +
                "reminders inside the SLA window and forwards a " +
                "breached request to the escalation group once."
            )),
            run: () => {},
        },
        {
            trigger: ".o_main_navbar",
            content: markup(_t(
                "That's it. Once a policy + rule cover a document, " +
                "users see a <b>Request Approval</b> button on the " +
                "draft form, and posting is blocked until every group " +
                "in the rule has signed off. " +
                "<br/><br/>" +
                "The Approvals menu shows the live pipeline as a " +
                "kanban grouped by state."
            )),
            run: () => {},
        },
    ],
});
