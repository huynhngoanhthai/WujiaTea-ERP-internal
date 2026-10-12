/** @odoo-module **/

import { Component } from "@odoo/owl";

export class WujiaMobileSkeleton extends Component {
    static template = "wujia_mobile_core.WujiaMobileSkeleton";
    static props = {
        count: { type: Number, optional: true },
    };
    static defaultProps = {
        count: 3,
    };

    get items() {
        return Array.from({ length: this.props.count }, (_, i) => i);
    }
}
