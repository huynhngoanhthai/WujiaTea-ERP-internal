/** @odoo-module **/

import { Component } from "@odoo/owl";

export class WujiaMobileEmptyState extends Component {
    static template = "wujia_mobile_core.WujiaMobileEmptyState";
    static props = {
        icon: { type: String, optional: true },
        title: { type: String, optional: true },
        text: { type: String, optional: true },
    };
    static defaultProps = {
        icon: "fa-inbox",
        title: "No data available",
        text: "There are no records to display at this moment.",
    };
}
