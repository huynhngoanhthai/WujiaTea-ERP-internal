import { DropdownItem } from "@web/core/dropdown/dropdown_item";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { Component } from "@odoo/owl";

const cogMenuRegistry = registry.category("cogMenu");

export class ViewFieldsValueCogMenu extends Component {
    static template = "wujia_fields_value.ViewFieldsValueCogMenu";
    static components = { DropdownItem };

    setup() {
        this.actionService = useService("action");
    }

    async onSelected() {
        const root = this.env?.model?.root;
        const resId = root?.resId || this.env?.config?.resId;
        const resModel = root?.resModel || this.env?.config?.resModel;

        if (!resId || !resModel) {
            return;
        }

        // Open in-memory transient wizard without saving anything to DB
        await this.actionService.doAction({
            type: "ir.actions.act_window",
            name: "View Fields Value",
            res_model: "wujia.fields.value",
            views: [[false, "form"]],
            target: "new",
            context: {
                default_res_id: resId,
                default_model: resModel,
                from_fields_value: true,
            },
        });
    }
}

export const viewFieldsValueItem = {
    Component: ViewFieldsValueCogMenu,
    groupNumber: 20,
    isDisplayed: (env) => {
        return env?.config?.viewType === "form" && Boolean(env?.model?.root?.resId || env?.config?.resId);
    },
};

cogMenuRegistry.add("wujia-fields-value-menu", viewFieldsValueItem, { sequence: 50 });

// Pure JS Widget for line actions (Zero DB saves, 100% in-memory)
export class WujiaFieldsValueActionsWidget extends Component {
    static template = "wujia_fields_value.ActionsWidget";

    setup() {
        this.actionService = useService("action");
    }

    get record() {
        return this.props.record;
    }

    get hasRelation() {
        return Boolean(this.record.data.has_relation);
    }

    async onViewDetail(ev) {
        ev.stopPropagation();
        ev.preventDefault();

        const data = this.record.data;
        const relModel = data.relation_model;
        let targetResId = data.relation_res_id;

        if (!targetResId && data.relation_res_ids) {
            try {
                const ids = JSON.parse(data.relation_res_ids);
                if (ids && ids.length) {
                    targetResId = ids[0];
                }
            } catch (e) {}
        }

        if (relModel && targetResId) {
            await this.actionService.doAction({
                type: "ir.actions.act_window",
                name: "View Fields Value",
                res_model: "wujia.fields.value",
                views: [[false, "form"]],
                target: "new",
                context: {
                    default_model: relModel,
                    default_res_id: targetResId,
                },
            });
        }
    }

    async onOpenTarget(ev) {
        ev.stopPropagation();
        ev.preventDefault();

        const data = this.record.data;
        const relModel = data.relation_model;
        const relResId = data.relation_res_id;
        const relResIdsStr = data.relation_res_ids;
        const label = data.field_label || data.field_name || relModel;

        if (!relModel) return;

        if (relResId) {
            await this.actionService.doAction({
                type: "ir.actions.act_window",
                name: `${label} (${relModel})`,
                res_model: relModel,
                res_id: relResId,
                views: [[false, "form"]],
                target: "current",
            });
        } else if (relResIdsStr) {
            let resIds = [];
            try {
                resIds = JSON.parse(relResIdsStr);
            } catch (e) {}
            if (resIds && resIds.length) {
                await this.actionService.doAction({
                    type: "ir.actions.act_window",
                    name: `${label} (${relModel})`,
                    res_model: relModel,
                    domain: [["id", "in", resIds]],
                    views: [[false, "list"], [false, "form"]],
                    target: "current",
                });
            }
        }
    }
}

export const wujiaFieldsValueActionsWidget = {
    component: WujiaFieldsValueActionsWidget,
    fieldDependencies: [
        { name: "has_relation", type: "boolean" },
        { name: "relation_model", type: "char" },
        { name: "relation_res_id", type: "integer" },
        { name: "relation_res_ids", type: "char" },
        { name: "field_label", type: "char" },
        { name: "field_name", type: "char" },
    ],
};

registry.category("fields").add("wujia_fields_value_actions", wujiaFieldsValueActionsWidget);
