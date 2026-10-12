/** @odoo-module **/

// ============================================================================
// ERP Heritage
// Copyright (C) 2026 (https://www.erpheritage.com.au/)
// ============================================================================

import { Component } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { standardFieldProps } from "@web/views/fields/standard_field_props";

const ICON_CLASS_RE = /^fa-[a-z0-9-]+$/;
const TAG_CLASS_RE = /^o_tag_color_(?:[0-9]|1[01])$/;
const ACTION_METHOD_RE = /^action_view_[a-z0-9_]+$/;
const DEFAULT_ICON_CLASS = "fa-circle";

function cleanClassToken(value, pattern) {
    if (typeof value !== "string") {
        return "";
    }
    const token = value.trim();
    return pattern.test(token) ? token : "";
}

/**
 * Convert one server statistic into safe, predictable template data.
 *
 * Invalid entries disappear instead of breaking whole list row. Zero remains
 * valid. Missing/invalid optional classes degrade to neutral Odoo badge.
 */
export function normalizeListStatistic(value) {
    if (!value || typeof value !== "object" || Array.isArray(value)) {
        return null;
    }

    const valueType = typeof value.value;
    const hasDisplayValue =
        (valueType === "number" && Number.isFinite(value.value)) ||
        (valueType === "string" && value.value.trim() !== "");
    const label = typeof value.label === "string" ? value.label.trim() : "";
    if (!hasDisplayValue || !label) {
        return null;
    }

    return {
        // This value originates in trusted, read-only Python hooks. Repeat
        // the server's view-only allowlist here so malformed legacy/cache
        // payloads can never turn a badge into an arbitrary model RPC.
        actionMethod:
            typeof value.actionMethod === "string" &&
            ACTION_METHOD_RE.test(value.actionMethod)
                ? value.actionMethod
                : "",
        iconClass:
            cleanClassToken(value.iconClass, ICON_CLASS_RE) ||
            DEFAULT_ICON_CLASS,
        label,
        tagClass: cleanClassToken(value.tagClass, TAG_CLASS_RE),
        value: value.value,
    };
}

export class EhListStatisticsField extends Component {
    static template = "eh_account_base.EhListStatisticsField";
    static props = {
        ...standardFieldProps,
    };

    setup() {
        this.orm = useService("orm");
        this.actionService = useService("action");
        this.openingAction = false;
    }

    get statistics() {
        const record = this.props.record;
        const rawValue = record && record.data
            ? record.data[this.props.name]
            : null;
        if (!Array.isArray(rawValue)) {
            return [];
        }
        return rawValue.map(normalizeListStatistic).filter(Boolean);
    }

    async openStatistic(statistic) {
        const record = this.props.record;
        const actionMethod = statistic && statistic.actionMethod;
        if (
            this.openingAction ||
            typeof actionMethod !== "string" ||
            !ACTION_METHOD_RE.test(actionMethod) ||
            !record ||
            typeof record.resModel !== "string" ||
            !record.resModel.trim() ||
            !Number.isInteger(record.resId) ||
            record.resId <= 0
        ) {
            return;
        }

        this.openingAction = true;
        try {
            const action = await this.orm.call(
                record.resModel,
                actionMethod,
                [[record.resId]],
            );
            if (action) {
                await this.actionService.doAction(action);
            }
        } finally {
            this.openingAction = false;
        }
    }
}

// EH_LIST_STATS_ODOO16_REGISTRATION_START
// Odoo 17-19 field registries consume descriptor objects. Backporter replaces
// only this marked block with Odoo 16 direct-component registrations.
export const ehListStatisticsField = {
    component: EhListStatisticsField,
    displayName: _t("List Statistics"),
    supportedTypes: ["json"],
};

registry.category("fields").add("eh_list_statistics", ehListStatisticsField);
// EH_LIST_STATS_ODOO16_REGISTRATION_END
