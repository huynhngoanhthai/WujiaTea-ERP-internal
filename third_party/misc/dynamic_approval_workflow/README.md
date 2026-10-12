# Dynamic Approval Workflow

**Version:** 19.0.1.0.0 | **License:** LGPL-3 | **Author:** ashahrour

A fully configurable, multi-stage approval engine that can be plugged into
**any Odoo model** without touching existing code.  Configure workflows
through the UI, define as many sequential stages as you need, and let the
engine handle routing, notifications, and audit trails automatically.

---

## Features

| Feature | Description |
|---|---|
| **ApprovalMixin** | One-line integration into any Odoo model |
| **Domain-filtered configs** | Different workflows for the same model (e.g. PO < $1k vs ≥ $1k) |
| **Three approver types** | Fixed user · security group · dynamic field on the document |
| **Full state machine** | Draft → Pending → Approved / Rejected / Returned |
| **Chatter audit trail** | Every action logged on the source document and the request |
| **Reason wizard** | Mandatory reason capture when rejecting or returning |
| **Email notifications** | Automatic email to approver(s) on each stage transition |
| **Escalation cron** | Nightly job flags overdue requests and pings the escalation user |
| **My Approvals Dashboard** | OWL client action with live count badges and a pending-items table |
| **Automated Action hook** | Template server action for no-code automation integration |

---

## Installation

1. Copy the `dynamic_approval_workflow` folder into your Odoo add-ons path.
2. Restart the Odoo service.
3. Go to **Settings → Activate developer mode** (recommended for setup).
4. Go to **Apps**, click **Update Apps List**, search for
   *Dynamic Approval Workflow*, and click **Install**.

---

## User Roles

Two security groups are created:

| Group | Description |
|---|---|
| **Approval User** (default for all internal users) | Submit documents, view own requests, act as approver |
| **Approval Manager** | Full access: manage configs, view all requests, act on any request |

Assign users to **Approval Manager** via
**Settings → Users → user record → tab "Approvals"**.

---

## Configuration: Create an Approval Workflow

> **Who:** Approval Manager

1. Open the **Approvals** app from the main menu.
2. Go to **Configuration → Approval Workflows**.
3. Click **Create**.
4. Fill in the form:

   | Field | Guidance |
   |---|---|
   | **Name** | A descriptive label, e.g. *Purchase Order — High Value* |
   | **Model** | The Odoo model this workflow targets, e.g. `purchase.order` |
   | **Filter Domain** | *(Optional)* Odoo domain expression.  Only documents matching this domain will use the workflow.  Leave as `[]` to match all. Example: `[('amount_total', '>=', 5000)]` |
   | **Sequence** | Lower values are evaluated first when multiple workflows target the same model |
   | **Escalation After (Days)** | Calendar days before an overdue request is escalated |

5. In the **Approval Stages** tab, click **Add a line** to define each stage:

   | Field | Guidance |
   |---|---|
   | **Sequence** | Drag the handle to reorder |
   | **Stage Name** | e.g. *Line Manager*, *Finance Director* |
   | **Approver Type** | See table below |
   | **Approver / Group / Field** | Populated depending on Approver Type |
   | **Escalation User** | Who is notified when this stage is overdue |

   **Approver Type options:**

   | Type | When to use |
   |---|---|
   | **Specific User** | Always the same person |
   | **User Group** | Any member of a security group can approve |
   | **Dynamic Field** | The approver is taken from a Many2one(res.users) field on the document (e.g. `user_id`) |

6. Click **Save**.

---

## How to Plug the Mixin into a Custom Model

> **Who:** Odoo Developer

Add the mixin to any model in a **separate custom module** (do not edit core
modules):

```python
# my_module/models/my_model.py
class MyModel(models.Model):
    _name = 'my.model'
    _inherit = ['my.model', 'approval.mixin', 'mail.thread', 'mail.activity.mixin']
```

Then add smart-button and submit button to the form view:

```xml
<!-- my_module/views/my_model_views.xml -->
<record id="view_my_model_form_approval" model="ir.ui.view">
    <field name="name">my.model.form.approval</field>
    <field name="model">my.model</field>
    <field name="inherit_id" ref="my_module.view_my_model_form"/>
    <field name="arch" type="xml">
        <!-- Smart button (show request count) -->
        <div name="button_box" position="inside">
            <button name="action_view_approval_requests"
                    type="object"
                    class="oe_stat_button"
                    icon="fa-check-square-o"
                    invisible="approval_request_count == 0">
                <field name="approval_request_count"
                       string="Approvals"
                       widget="statinfo"/>
            </button>
        </div>
        <!-- Approval status bar -->
        <header position="inside">
            <button name="action_submit_for_approval"
                    string="Submit for Approval"
                    type="object"
                    class="btn-primary"
                    invisible="approval_state not in ('draft', 'returned')"/>
            <field name="approval_state"
                   widget="statusbar"
                   statusbar_visible="draft,pending_approval,approved"/>
        </header>
    </field>
</record>
```

---

## Using the Approval Workflow (End Users)

### Submitting a Document

1. Open the document (e.g. a purchase order).
2. Click **Submit for Approval** in the header.
3. The document's status changes to **Pending Approval**.
4. The first-stage approver receives an email notification.

### Approving a Request (as an Approver)

1. Open the **Approvals** app → **Pending My Action**, or click the email link.
2. Open the approval request.
3. Review the document by clicking **Open Document**.
4. Click **Approve**.  If more stages exist, the next approver is notified
   automatically.  When the final stage is approved, the document's status
   becomes **Approved**.

### Rejecting a Request

1. Open the approval request.
2. Click **Reject**.
3. Enter a mandatory reason in the dialog and click **Confirm**.
4. The document's status becomes **Rejected** and the requester sees the
   reason in the chatter.

### Returning a Request

1. Open the approval request.
2. Click **Return to Requester**.
3. Enter a reason and click **Confirm**.
4. The document's status becomes **Returned**.  The requester can edit the
   document and re-submit.

### Re-submitting after Return

1. Open the source document (e.g. the purchase order).
2. Make the required changes.
3. Click **Submit for Approval** again — a new request is created from the
   beginning of the workflow.

---

## My Approvals Dashboard

Go to **Approvals → My Approvals** for an at-a-glance view:

- **Count badges** — click any badge to open a filtered list of your
  submitted requests for that state.
- **Pending My Approval table** — lists every request currently awaiting
  your action, colour-coded by deadline.  Click **Review** to open the
  request directly.

The dashboard refreshes automatically every 60 seconds.

---

## Escalation

The nightly **Approval: Escalate Overdue Requests** cron job runs daily at
06:00.  For every pending request whose deadline has passed, it:

1. Posts a warning note on the request's chatter.
2. If the current stage has an **Escalation User** set, sends a chatter
   message that pings that user by email.

You can adjust the escalation period per workflow via the
**Escalation After (Days)** field on the workflow configuration.

---

## Automated Action Integration

An admin can trigger approval submission automatically on any Odoo event
(e.g. "when a Sale Order is confirmed"):

1. Go to **Settings → Technical → Actions → Automated Actions**.
2. Click **Create**.
3. Set **Model** to your target model (e.g. `sale.order`).
4. Set the **Trigger** (e.g. *When a record is updated*, field `state`).
5. Under **Action To Do**, choose **Execute server code** and enter:

   ```python
   records.action_submit_for_approval()
   ```

   Or set **Action** to *Execute a server action* and select
   **Approval: Submit for Approval (template)** from the list (requires
   the source model to already inherit `approval.mixin`).

---

## Technical Notes

### Module Dependencies
- `base` — core Odoo
- `mail` — chatter, mail.thread, email templates
- `base_automation` — automated action server action template

### Models Added

| Model | Description |
|---|---|
| `approval.mixin` | AbstractModel — inherited by target models |
| `approval.workflow.config` | Workflow configuration per model |
| `approval.workflow.stage` | One stage within a workflow |
| `approval.request` | One approval request per document submission |
| `approval.request.line` | Immutable audit trail (one row per action) |
| `approval.action.wizard` | TransientModel — reject/return reason dialog |

### State Field Summary

`approval_state` on the **source document** (via mixin):
`draft` → `pending_approval` → `approved` / `rejected` / `returned`

`state` on **approval.request** mirrors the above (minus `draft`).

### Sequence
Requests are numbered `APR/YYYY/NNNNN` (resets each year).

---

## Changelog

| Version | Date       | Description |
|---|------------|---|
| 19.0.1.0.0 | 2026-01-01 | Initial release |

---

## Support

send an email to <a.k.shahrour@gmail.com> with any questions or issues.