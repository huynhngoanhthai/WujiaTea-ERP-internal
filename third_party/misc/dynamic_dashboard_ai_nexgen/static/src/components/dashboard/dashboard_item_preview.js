/** Copyright (C) NexGen Solutions */
/** @odoo-module **/

import { Component, xml } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { standardFieldProps } from "@web/views/fields/standard_field_props";
import { DynamicDashboardItem } from "./dashboard_item";

export class DynamicDashboardItemPreview extends Component {
    static template = xml`
        <div class="dynamic-dashboard-item-preview w-100 h-100 position-relative d-flex flex-column">
            <DynamicDashboardItem
                itemType="props.record.data.item_type"
                itemId="props.record.resId || 0"
                globalDateFilter="'none'"
                previewData="props.record.data.item_preview"
            />
        </div>
    `;
    static components = { DynamicDashboardItem };
    static props = {
        ...standardFieldProps,
    };
}

registry.category("fields").add("dynamic_dashboard_ai_nexgen_item_preview", {
    component: DynamicDashboardItemPreview,
});
