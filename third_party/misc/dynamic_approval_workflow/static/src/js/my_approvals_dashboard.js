/** @odoo-module **/

import { Component, onMounted, onWillUnmount, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { user } from "@web/core/user";

/**
 * OWL client action: "My Approvals Dashboard"
 *
 * Displays:
 * - Count badges by state (pending / approved / rejected / returned)
 *   for requests submitted by the current user.
 * - A live table of requests currently awaiting the current user's approval,
 *   with one-click navigation to the approval form or the source document.
 *
 * Registered as client action tag:
 *   ``dynamic_approval_workflow.my_approvals_dashboard``
 */
export class MyApprovalsDashboard extends Component {
    static template = "dynamic_approval_workflow.MyApprovalsDashboard";
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notification = useService("notification");
        this.userId = user.userId;

        this.state = useState({
            isLoading: true,
            pendingRequests: [],
            searchQuery: "",
            groupBy: "none",
            countByState: {
                pending_approval: 0,
                approved: 0,
                rejected: 0,
                returned: 0,
            },
        });

        // Auto-refresh every 60 seconds
        this._refreshInterval = null;

        onMounted(async () => {
            await this._loadData();
            this._refreshInterval = setInterval(() => this._loadData(), 60_000);
        });

        onWillUnmount(() => {
            if (this._refreshInterval) {
                clearInterval(this._refreshInterval);
            }
        });
    }

    // ------------------------------------------------------------------
    // Data loading
    // ------------------------------------------------------------------

    async _loadData() {
        this.state.isLoading = true;
        try {
            const userId = this.userId;
            const [pendingRequests, pendingCount, approvedCount, rejectedCount, returnedCount] =
                await Promise.all([
                // Requests waiting for THIS user to act
                this.orm.searchRead(
                    "approval.request",
                    [
                        ["current_approver_ids", "in", [userId]],
                        ["state", "=", "pending_approval"],
                    ],
                    [
                        "name",
                        "res_name",
                        "res_model",
                        "res_id",
                        "config_id",
                        "current_stage_id",
                        "requester_id",
                        "deadline",
                    ],
                    { limit: 80, order: "deadline asc, create_date asc" }
                ),
                // Counts of requests SUBMITTED by this user
                this.orm.searchCount(
                    "approval.request",
                    [["requester_id", "=", userId], ["state", "=", "pending_approval"]]
                ),
                this.orm.searchCount(
                    "approval.request",
                    [["requester_id", "=", userId], ["state", "=", "approved"]]
                ),
                this.orm.searchCount(
                    "approval.request",
                    [["requester_id", "=", userId], ["state", "=", "rejected"]]
                ),
                this.orm.searchCount(
                    "approval.request",
                    [["requester_id", "=", userId], ["state", "=", "returned"]]
                ),
            ]);

            this.state.pendingRequests = pendingRequests;
            this.state.countByState = {
                pending_approval: pendingCount || 0,
                approved: approvedCount || 0,
                rejected: rejectedCount || 0,
                returned: returnedCount || 0,
            };
        } catch (error) {
            this.notification.add(
                _t("Could not load approval data. Please refresh the page."),
                { type: "warning" }
            );
            console.error("MyApprovalsDashboard: _loadData error", error);
        } finally {
            this.state.isLoading = false;
        }
    }

    // ------------------------------------------------------------------
    // Navigation helpers
    // ------------------------------------------------------------------

    async openRequest(requestId) {
        await this.action.doAction({
            type: "ir.actions.act_window",
            res_model: "approval.request",
            res_id: requestId,
            views: [[false, "form"]],
            target: "current",
        });
    }

    async openDocument(resModel, resId) {
        if (!resModel || !resId) return;
        await this.action.doAction({
            type: "ir.actions.act_window",
            res_model: resModel,
            res_id: resId,
            views: [[false, "form"]],
            target: "current",
        });
    }

    async openAllPending() {
        await this.action.doAction(
            "dynamic_approval_workflow.action_my_pending_approvals"
        );
    }

    async openByState(state) {
        await this.action.doAction({
            type: "ir.actions.act_window",
            name: _t("My Submitted Requests — %(state)s", { state }),
            res_model: "approval.request",
            view_mode: "list,form",
            views: [[false, "list"], [false, "form"]],
            domain: [
                ["requester_id", "=", this.userId],
                ["state", "=", state],
            ],
        });
    }

    async refreshData() {
        await this._loadData();
    }

    onSearchInput(ev) {
        this.state.searchQuery = ev.target.value || "";
    }

    onGroupByChange(ev) {
        this.state.groupBy = ev.target.value || "none";
    }

    clearFilters() {
        this.state.searchQuery = "";
        this.state.groupBy = "none";
    }

    get hasActiveFilters() {
        return (
            Boolean((this.state.searchQuery || "").trim()) ||
            this.state.groupBy !== "none"
        );
    }

    _matchesSearch(req, query) {
        if (!query) return true;
        const haystack = [
            req.name,
            req.res_name,
            req.res_model,
            req.deadline,
            req.config_id && req.config_id[1],
            req.current_stage_id && req.current_stage_id[1],
            req.requester_id && req.requester_id[1],
        ]
            .filter(Boolean)
            .join(" ")
            .toLowerCase();
        return haystack.includes(query);
    }

    _deadlineGroupInfo(req) {
        if (!req.deadline) {
            return { key: "no_deadline", label: _t("No Deadline"), order: 50 };
        }

        const today = new Date();
        today.setHours(0, 0, 0, 0);
        const dl = new Date(req.deadline);
        dl.setHours(0, 0, 0, 0);
        const diffDays = Math.ceil((dl - today) / 86_400_000);

        if (diffDays < 0) {
            return { key: "overdue", label: _t("Overdue"), order: 10 };
        }
        if (diffDays === 0) {
            return { key: "today", label: _t("Due Today"), order: 20 };
        }
        if (diffDays === 1) {
            return { key: "tomorrow", label: _t("Due Tomorrow"), order: 30 };
        }
        return { key: "upcoming", label: _t("Upcoming"), order: 40 };
    }

    _groupInfo(req) {
        if (this.state.groupBy === "workflow") {
            return req.config_id
                ? {
                      key: `workflow_${req.config_id[0]}`,
                      label: req.config_id[1],
                      order: 100,
                  }
                : { key: "workflow_none", label: _t("No Workflow"), order: 900 };
        }
        if (this.state.groupBy === "stage") {
            return req.current_stage_id
                ? {
                      key: `stage_${req.current_stage_id[0]}`,
                      label: req.current_stage_id[1],
                      order: 100,
                  }
                : { key: "stage_none", label: _t("No Stage"), order: 900 };
        }
        if (this.state.groupBy === "requester") {
            return req.requester_id
                ? {
                      key: `requester_${req.requester_id[0]}`,
                      label: req.requester_id[1],
                      order: 100,
                  }
                : { key: "requester_none", label: _t("No Requester"), order: 900 };
        }
        if (this.state.groupBy === "deadline") {
            return this._deadlineGroupInfo(req);
        }
        return { key: "all", label: _t("All Requests"), order: 0 };
    }

    get groupedPendingRequests() {
        const query = (this.state.searchQuery || "").trim().toLowerCase();
        const filtered = this.state.pendingRequests.filter((req) =>
            this._matchesSearch(req, query)
        );
        const groups = new Map();

        for (const req of filtered) {
            const info = this._groupInfo(req);
            if (!groups.has(info.key)) {
                groups.set(info.key, {
                    key: info.key,
                    label: info.label,
                    order: info.order,
                    requests: [],
                });
            }
            groups.get(info.key).requests.push(req);
        }

        const result = [...groups.values()];
        result.sort((a, b) => {
            if (a.order !== b.order) {
                return a.order - b.order;
            }
            return a.label.localeCompare(b.label);
        });
        return result;
    }

    get filteredPendingCount() {
        return this.groupedPendingRequests.reduce(
            (total, group) => total + group.requests.length,
            0
        );
    }

    // ------------------------------------------------------------------
    // Utility
    // ------------------------------------------------------------------

    /**
     * Return a CSS class string for deadline date cells.
     * @param {string|false} deadline  ISO date string or false
     */
    getDeadlineClass(deadline) {
        if (!deadline) return "";
        const today = new Date();
        today.setHours(0, 0, 0, 0);
        const dl = new Date(deadline);
        const diffMs = dl - today;
        const diffDays = Math.ceil(diffMs / 86_400_000);
        if (diffDays < 0) return "o_approval_overdue";
        if (diffDays <= 2) return "o_approval_due_soon";
        return "";
    }

    /**
     * Human-friendly label for a deadline date.
     * @param {string|false} deadline
     */
    formatDeadline(deadline) {
        if (!deadline) return "—";
        const today = new Date();
        today.setHours(0, 0, 0, 0);
        const dl = new Date(deadline);
        const diffDays = Math.ceil((dl - today) / 86_400_000);
        if (diffDays < 0)
            return _t("%(d)s (%(n)s day(s) overdue)", {
                d: deadline,
                n: Math.abs(diffDays),
            });
        if (diffDays === 0) return _t("%(d)s (today)", { d: deadline });
        if (diffDays === 1) return _t("%(d)s (tomorrow)", { d: deadline });
        return deadline;
    }
}

registry
    .category("actions")
    .add(
        "dynamic_approval_workflow.my_approvals_dashboard",
        MyApprovalsDashboard
    );
