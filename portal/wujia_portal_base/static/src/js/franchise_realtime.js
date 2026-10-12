import { Interaction } from "@web/public/interaction";
import { registry } from "@web/core/registry";
import { rpc } from "@web/core/network/rpc";

// Màu badge theo vai trò; nhãn lấy `role_label` server đã dịch (ROLE_LABELS, J-V2).
const ROLE_BADGE_CLS = { owner: "primary", manager: "info", staff: "secondary" };

export class FranchiseMembersRealtime extends Interaction {
    static selector = "#o_wujia_franchise_members";

    setup() {
        this.franchiseId = parseInt(this.el.dataset.franchiseId, 10) || null;
        this.tbody = this.el.querySelector("tbody");
        this.indicator = document.getElementById("o_wujia_realtime_indicator");
    }

    async willStart() {
        if (!this.franchiseId) {
            return;
        }
        const bus = this.services.bus_service;
        bus.addChannel(`wujia.franchise_${this.franchiseId}`);
        bus.subscribe(
            "wujia_franchise_members_changed",
            this.onMembersChanged.bind(this),
        );
    }

    async onMembersChanged(payload) {
        if (!payload || payload.franchise_id !== this.franchiseId) {
            return;
        }
        const data = await rpc(`/my/franchises/${this.franchiseId}/members`);
        if (!data || data.error) {
            return;
        }
        this.renderMembers(data.members || []);
        this.flashIndicator();
    }

    renderMembers(members) {
        if (!this.tbody) {
            return;
        }
        this.tbody.innerHTML = members.map((m) => this.renderRow(m)).join("");
    }

    renderRow(m) {
        const badge = {
            cls: ROLE_BADGE_CLS[m.role] || "secondary",
            label: m.role_label || m.role || "",
        };
        const mainOwner = window.wjMsg ? window.wjMsg(this.el, "main-owner", "Main owner") : "Main owner";
        const primaryBadge = m.is_primary_owner
            ? `<span class="badge text-bg-warning ms-1">${escapeHtml(mainOwner)}</span>`
            : "";
        const dateRange = `${m.date_from || ""} — ${m.date_to || "—"}`;
        return `<tr>
            <td>${escapeHtml(m.user_name || "")} ${primaryBadge}</td>
            <td><span class="badge text-bg-${badge.cls}">${escapeHtml(badge.label)}</span></td>
            <td>${escapeHtml(dateRange)}</td>
        </tr>`;
    }

    flashIndicator() {
        if (!this.indicator) {
            return;
        }
        this.indicator.classList.remove("d-none");
        clearTimeout(this._indicatorTimer);
        this._indicatorTimer = setTimeout(() => {
            this.indicator.classList.add("d-none");
        }, 2500);
    }
}

function escapeHtml(s) {
    const div = document.createElement("div");
    div.textContent = String(s ?? "");
    return div.innerHTML;
}

registry
    .category("public.interactions")
    .add("wujia_portal_base.franchise_members_realtime", FranchiseMembersRealtime);
