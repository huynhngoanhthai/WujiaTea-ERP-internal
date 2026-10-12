/** @odoo-module **/
import { registry } from "@web/core/registry";
import { standardFieldProps } from "@web/views/fields/standard_field_props";
const { Component,useState,onWillUpdateProps} = owl;

export class KsColorPicker extends Component{
        setup(){
            var self=this.props;
        }
        get value(){
            return{
                'ks_color':this.props.record.data[this.props.name].split(",")[0] || "#376CAE",
                'ks_opacity':this.props.record.data[this.props.name].split(",")[1] ||'0.99'
            }
        }

        _ksOnColorChange(ev) {
            var new_value=(ev.currentTarget.value.concat("," + this.props.record.data[this.props.name].split(',')[1]));
            this.props.record.update({ [this.props.name]: new_value });

        }

        _ksOnOpacityChange(ev) {
            var new_value=(this.props.record.data[this.props.name].split(',')[0].concat("," + event.currentTarget.value));
            this.props.record.update({ [this.props.name]: new_value });
        }

        _ksOnOpacityInputNew(ev){
            const newOpacity = ev.currentTarget.value;
            const percentage = (newOpacity - ev.currentTarget.min) / (ev.currentTarget.max - ev.currentTarget.min) * 100;

            ev.currentTarget.style.background = `linear-gradient(to right, rgba(231, 198, 201, 1) ${percentage}%, #d3d3d3 ${percentage}%)`;
        }

        _ksOnOpacityInput(ev) {
            var self = this;
            var color;
            var value = ev.currentTarget.value;

            if (this.props.name === "ks_background_color") {
                var ksDbItemPreviewColorPicker = document.querySelector('.ks_db_item_preview_color_picker');
                color = window.getComputedStyle(ksDbItemPreviewColorPicker).backgroundColor;
                ksDbItemPreviewColorPicker.style.backgroundColor = self.get_color_opacity_value(color, value);

                var ksDbItemPreviewL2 = document.querySelector('.ks_db_item_preview_l2');
                color = window.getComputedStyle(ksDbItemPreviewL2).backgroundColor;
                ksDbItemPreviewL2.style.backgroundColor = self.get_color_opacity_value(color, value);

            } else if (this.props.name === "ks_default_icon_color") {
                var ksDashboardIconColorPickerSpan = document.querySelector('.ks_dashboard_icon_color_picker > span');
                color = window.getComputedStyle(ksDashboardIconColorPickerSpan).color;
                ksDashboardIconColorPickerSpan.style.color = self.get_color_opacity_value(color, value);

            } else if (this.props.name === "ks_font_color") {
                var ksDbItemPreview = document.querySelector('.ks_db_item_preview');
                color = window.getComputedStyle(ksDbItemPreview).color;
                ksDbItemPreview.style.color = self.get_color_opacity_value(color, value);
            }
        }


        get_color_opacity_value(color, val) {
            if (color) {
                return color.replace(color.split(',')[3], val + ")");
            } else {
                return false;
            }
        }


 }
 KsColorPicker.template="Ks_color_picker_opacity_view";
 KsColorPicker.props = {
    ...standardFieldProps,
};
export const ksColorPickerField = {
    component:  KsColorPicker,
    supportedTypes: ["char"],
};
 registry.category("fields").add('Ks_dashboard_color_picker_owl', ksColorPickerField);
