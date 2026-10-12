/** @odoo-module */

import { registry } from "@web/core/registry";
import { qweb } from 'web.core';
import core from 'web.core';
import field_utils from 'web.field_utils';
import session from 'web.session';
import utils from 'web.utils';
import { CharField } from "@web/views/fields/char/char_field";
const { useEffect, useRef,onWillUpdateProps} = owl;

class KsYLabels extends CharField{

//        events: _.extend({}, AbstractField.prototype.events, {
//            'change select': 'ks_toggle_icon_input_click',
//            'blur .ks_stack_group': 'ks_group_input_click',
//        }),
       setup() {
        super.setup();
        const self = this;
        this.ks_columns = {};


        const inputRef = useRef("input");
        useEffect(
            (input) => {
                if (input) {
                self.ks_y_render();
            }
            },
            () => [inputRef.el]

        );
        document.body.addEventListener('change', function(evt) {
        if ($(evt.target).hasClass("ks_label_select'")) {
        self.ks_toggle_icon_input_click(evt);
    }
}, false);
        document.body.addEventListener('focusout', function(evt) {
        if ($(evt.target).hasClass("ks_stack_group")) {
        self.ks_group_input_click(evt);
    }
}, false);



        onWillUpdateProps(this.onWillUpdateProps);
//        onWillStart(this.onWillStart);

}
    onWillUpdateProps(){
    this.ks_y_render()

}

        ks_y_render(){
        var self = this;
        self.ks_rows_chart_type = {};
        $(this.input.el.parentElement).find('div').remove()
        $(this.input.el.parentElement).find('input').addClass('d-none')
         $(this.input.el.parentElement).find("table").remove()
        var field = this.props.record.data;
            if(field.ks_query_result && field.ks_dashboard_item_type !== 'ks_kpi'){
                var ks_query_result = JSON.parse(field.ks_query_result);
                if (field.ks_dashboard_item_type !== 'ks_kpi' && ks_query_result.header.length){
                    if (field.ks_dashboard_item_type !== 'ks_list_view' && field.ks_dashboard_item_type !=='ks_kpi' && field.ks_dashboard_item_type !== 'ks_tile'){
                        self.ks_check_for_labels();
                        var $view = $(qweb.render('ks_y_label_table',{
                            label_rows: self.ks_columns,
                            chart_type: self.ks_rows_chart_type,
                            mode: self.props.record.mode,
                            ks_is_group_column: ks_query_result.ks_is_group_column
                        }));
                        if (Object.keys(self.ks_rows_chart_type).length==0){

                        this.props.update(JSON.stringify(self.ks_value))
                        }

                        self.ks_rows_keys.forEach(function(key){
                            $view.find('#' + key).val(self.ks_rows_chart_type[key]);
                        })
                        if(document.querySelector(".table")==null){
                        $(this.input.el.parentElement).append($view)
                        }else{
                        document.querySelector(".table").remove()
                        $(this.input.el.parentElement).append($view)
                        }
//                        if (this.props.record.mode == 'edit') self.ks_toggle_icon_input_click();
                    }
                } else {
                     $(self.input.el.parentElement).append($('<div>').text("No Data Available"));
                }
            } else {
                 $(self.input.el.parentElement).append($('<div>').text("Please Enter the Appropriate Query for this"));
            }
            if (this.props.record.mode === 'readonly') {
                $(self.input.el.parentElement).find('select').addClass('ks_not_click');
                $(self.input.el.parentElement).find('td.ks_stack_group').addClass('ks_not_click');
            }
        }
        ks_check_for_labels(){
            var self = this;
            self.ks_columns = {};
            self.ks_rows_keys = [];
            self.ks_rows_chart_type = {};
            self.ks_value={};
            if(self.props.record.data.ks_ylabels !=""){
                var ks_columns = JSON.parse(self.props.record.data.ks_ylabels);
                Object.keys(ks_columns).forEach(function(key){
                    var chart_type = ks_columns[key]['chart_type'];
                    self.ks_rows_chart_type[key] = chart_type;
                    ks_columns[key]['chart_type'] = {}
                    if(self.props.record.data.ks_dashboard_item_type === 'ks_bar_chart'){
                        var chart_type_temp = self.props.record.data.ks_dashboard_item_type.split("_")[1];
                        if (chart_type_temp !== chart_type) {
                            chart_type = chart_type_temp;
                        }
                        ks_columns[key]['chart_type'][chart_type] = self.ks_title(chart_type);
                        if (chart_type === "bar"){
                            ks_columns[key]['chart_type']["line"] = "Line";
                        } else {
                            ks_columns[key]['chart_type']["bar"] = "Bar"
                        }
                    } else {
                        var chart_type = self.props.record.data.ks_dashboard_item_type.split("_")[1];
                        ks_columns[key]['chart_type'][chart_type] = self.ks_title(chart_type);
                        if (chart_type === "bar") ks_columns[key]['chart_type']["line"] = "Line";
                    }
                    self.ks_rows_keys.push(key);
                });
                self.ks_columns = ks_columns;
            } else {
                var query_result = JSON.parse(self.props.record.data.ks_query_result);

                query_result.header.forEach(function(key){
                    for(var i =0;i< query_result.header.length; i++){
                        if(query_result.type_code[query_result.header.indexOf(key)] !== 'numeric'){
                            continue;
                        }
                        if(query_result.type_code[query_result.header.indexOf(key)] == 'numeric') {
                            var ks_row = {}
                            ks_row['measure'] = self.ks_title(key.replace("_", " "));
                            ks_row['chart_type'] = {}
                            var chart_type = self.props.record.data.ks_dashboard_item_type.split("_")[1];
                            ks_row['chart_type'][chart_type] = self.ks_title(chart_type);
                            if (chart_type === "bar") ks_row['chart_type']["line"] = "Line";
                            ks_row['group'] = " ";
                            self.ks_columns[key] = JSON.parse(JSON.stringify(ks_row));
                            if (chart_type === "bar"){
                            delete(ks_row['chart_type']['line'])
                            ks_row['chart_type']='bar'
                            self.ks_value[key]=ks_row
                            }else{
                            ks_row['chart_type']=self.props.record.data.ks_dashboard_item_type.split("_")[1]
                            self.ks_value[key]=ks_row
                            }
                        }
                        break;
                    }
                });
            }
        }

        ks_toggle_icon_input_click(e){
            var self = this;
//            this.props.update(self.props.value);
            if (e.target.id != ""){
            var ks_tbody =  $(this.input.el.parentElement).find('tbody.ks_y_axis');
            ks_tbody.find('select').each(function(){
                self.ks_columns[this.id]['chart_type'] = this.value;
            });
            var value = JSON.stringify(self.ks_columns);
            this.props.update(value)
            }
        }

        ks_title(str) {
            var split_str = str.toLowerCase().split(' ');
            for (var i = 0; i < split_str.length; i++) {
                split_str[i] = split_str[i].charAt(0).toUpperCase() + split_str[i].substring(1);
                str = split_str.join(' ');
            }
            return str;
        }

        ks_group_input_click(e){
            var self = this;
            if (this.input.el === null){
                  var ks_tbody =  $('.ks_y_axis');
            }else {
                var ks_tbody =  $(this.input.el.parentElement).find('tbody.ks_y_axis');
            }

            ks_tbody.find('select').each(function(){
                self.ks_columns[this.id]['chart_type'] = this.value;
            });
            self.ks_columns[e.target.id]['group'] = e.target.textContent.trim();
            var value = JSON.stringify(self.ks_columns);
            this.props.update(value)
        }
    }

    registry.category("fields").add('ks_y_labels', KsYLabels);
