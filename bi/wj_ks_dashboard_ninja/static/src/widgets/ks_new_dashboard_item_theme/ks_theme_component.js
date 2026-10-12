/** @odoo-module **/
import { registry } from "@web/core/registry";
const { Component} = owl;

export class KsDashboardTheme extends Component {
    setup(){
        var self = this.props;
        this.props.colors = ['white','blue','red','yellow','green']
        this.props.hexCode = {
                                white: '#DAEAF6',
                                blue: '#FFF4DE',
                                red: '#DCFCE7',
                                yellow: '#F3E8FF',
                                green: '#FFE2E5',
                                }
    }
    get value(){
        return this.props.record.data[this.props.name]
    }

    ks_dashboard_theme_input_container_click(ev) {
        var self = this.props;
        var box = ev.currentTarget.querySelector('input');
        if (box) {
            if (box.checked) {
                document.querySelectorAll('.ks_dashboard_theme_input').forEach(function(input) {
                    input.checked = false;
                });
                box.checked = true;
            } else {
                box.checked = false;
            }
            this.props.record.update({ [this.props.name]: box.value });
        }
    }
}
KsDashboardTheme.template="Ks_theme";
export const KsDashboardThemeField = {
    component:  KsDashboardTheme,
    supportedTypes: ["char"],
};

registry.category("fields").add('ks_dashboard_item_theme', KsDashboardThemeField);

