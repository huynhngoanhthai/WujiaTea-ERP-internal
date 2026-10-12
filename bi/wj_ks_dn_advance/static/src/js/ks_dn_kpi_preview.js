/** @odoo-module */

import { patch } from "@web/core/utils/patch";
import {KsKpiPreviewowl} from '@ks_dashboard_ninja/js/ks_dashboard_ninja_kpi_preview';
import field_utils from 'web.field_utils';
import { qweb } from 'web.core';
import utils from 'web.utils';
import session from 'web.session';
const { useEffect, useRef, xml, onWillUpdateProps,onWillStart} = owl;

patch(KsKpiPreviewowl.prototype,"ks_dn_advance",{

    ksNumFormatter(num, digits) {
         return this._super(...arguments);
        },
        ksNumIndianFormatter(num, digits) {
             return this._super(...arguments);
        },

        _get_rgba_format(val) {
             return this._super(...arguments);
        },
        _onKsGlobalFormatter(ks_record_count, ks_data_format, ks_precision_digits){
            return this._super(...arguments);
        },
        file_type_magic_word:{
            '/': 'jpg',
            'R': 'gif',
            'i': 'png',
            'P': 'svg+xml',
        },

        kpi_render(){
        $(this.input.el.parentElement).find('div').remove()
        $(this.input.el.parentElement).find('input').addClass('d-none')
        var rec = this.props.record.data;
            if (rec.ks_dashboard_item_type === 'ks_kpi') {
                if(rec.ks_data_calculation_type === "custom"){
                    this._super(...arguments);
                } else {
                if (rec.ks_kpi_data==""){
                var kpi_data=false
                }else
                { var kpi_data = JSON.parse(rec.ks_kpi_data)}
                 if (kpi_data){
                        this.KsRenderKpi();
                    }else{
                       $(this.input.el.parentElement).append($('<div>').text("Please run the appropriate Query"));
                    }
                }
            }
        },

        KsRenderKpi(){
            var self = this;
            var field = this.props.record.data;
            if (field.ks_kpi_data==""){
            var kpi_data=false
            }else{
            var kpi_data = JSON.parse(field.ks_kpi_data);
            }
            var count_1 = kpi_data[0].record_data ? kpi_data[0].record_data:0;
            var count_2 = kpi_data[1] ? kpi_data[1].record_data : undefined;
            var target_1 = kpi_data[0].target;
            var target_view = field.ks_target_view,
                pre_view = field.ks_prev_view;
            var ks_rgba_background_color = self._get_rgba_format(field.ks_background_color);
            var ks_rgba_font_color = self._get_rgba_format(field.ks_font_color);
            var ks_rgba_icon_color = self._get_rgba_format(field.ks_default_icon_color);
            var acheive = false;
            var pre_acheive = false;
            var pre_deviation = false;
            if(isNaN(kpi_data[0]['record_data'])){
                var count_value = kpi_data[0]['record_data']
            }else
            {
                var count_value = self._onKsGlobalFormatter(kpi_data[0]['record_data'], field.ks_data_format, field.ks_precision_digits);
            }
            var item_info = {
                count_1: count_value,
                count_1_tooltip: kpi_data[0]['record_data'],
                count_2: kpi_data[1] ? String(kpi_data[1]['record_data']) : false,
                name: field.name ? field.name : "Name",
                target_progress_deviation:false,
                icon_select: field.ks_icon_select,
                default_icon: field.ks_default_icon,
                icon_color: ks_rgba_icon_color,
                target_deviation: false,
                target_arrow: acheive ? 'up' : 'down',
                ks_enable_goal: field.ks_goal_enable,
                ks_previous_period: false,
                target: self.ksNumFormatter(target_1, 1),
                previous_period_data: false,
                pre_deviation: pre_deviation,
                pre_arrow: pre_acheive ? 'up' : 'down',
                target_view: field.ks_target_view,
            }

            if (field.ks_icon) {
                if (!utils.is_bin_size(field.ks_icon)) {
                    // Use magic-word technique for detecting image type
                    item_info['img_src'] = 'data:image/' + (self.file_type_magic_word[field.ks_icon[0]] || 'png') + ';base64,' + field.ks_icon;
                } else {
                    item_info['img_src'] = session.url('/web/image', {
                        model: self.env.model.root.resModel,
                        id: JSON.stringify(this.props.record.data.id),
                        field: "ks_icon",
                        // unique forces a reload of the image when the record has been updated
                        unique: String(this.props.record.data.__last_update.ts),
                    });
                }
            }

            var $kpi_preview;
            if (!kpi_data[1]) {
                if (target_view === "Number" || !field.ks_goal_enable) {
                    $kpi_preview = $(qweb.render("ks_kpi_preview_template", item_info));
                } else if (target_view === "Progress Bar" && field.ks_goal_enable) {
                    $kpi_preview = $(qweb.render("ks_kpi_preview_template_3", item_info));
                    $kpi_preview.find('#ks_progressbar').val(parseInt(item_info.target_progress_deviation));
                }


                if ($kpi_preview.find('.row').children().length !== 2) {
                    $kpi_preview.find('.row').children().addClass('text-center');
                }
            }
            $kpi_preview.css({
                "background-color": ks_rgba_background_color,
                "color": ks_rgba_font_color,
            });
             $(this.input.el.parentElement).append($kpi_preview);
        },

    });
