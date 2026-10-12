/** @odoo-module */

import { registry } from "@web/core/registry";
import { qweb } from 'web.core';
import core from 'web.core';
import field_utils from 'web.field_utils';
import session from 'web.session';
import utils from 'web.utils';
import { CharField } from "@web/views/fields/char/char_field";
const { useEffect, useRef,onWillUpdateProps} = owl;


class KsXLabels extends CharField{

//        events: _.extend({}, AbstractField.prototype.events, {
//            'change select': 'ks_toggle_icon_input_click',
//        }),
        setup() {
        super.setup();
        const self = this;
        const inputRef = useRef("input");
        useEffect(
            (input) => {
                if (input) {
                if(this.props.readonly==true){
                self._ks_render_readonly()
                }else{
                self._Ks_render_edit()
                }
                }
            },
            () => [inputRef.el]

        );
        document.body.addEventListener('change', function(evt) {
        if ($(evt.target).hasClass("ks_label_select'")) {
       self.ks_toggle_icon_input_click(evt);
    }
}, false);



        onWillUpdateProps(this.onWillUpdateProps);
//        onWillStart(this.onWillStart);

}
    onWillUpdateProps(){
    this._Ks_render_edit()


}

        _Ks_render_edit(){
        var self = this;
        $(this.input.el.parentElement).find('div').remove()
        $(this.input.el.parentElement).find('input').addClass('d-none')
        $(this.input.el.parentElement).find("select").remove()
        var field = this.props.record.data;
            if(field.ks_query_result && field.ks_dashboard_item_type !== 'ks_kpi'){
                var ks_query_result = JSON.parse(field.ks_query_result);
                if (ks_query_result.header.length){
                    self.ks_check_for_labels();
                    var $view = $(qweb.render('ks_select_labels',{
                        ks_columns_list: self.ks_columns,
                        mode: self.props.record.mode,
                    }));

                    if (this.props.record.data.ks_xlabels=="") {
                        $view.val(false)
                    }else{
                    $view.val(this.props.record.data.ks_xlabels)
                    }
                    if(document.querySelector(".o_group_selector")==null){
                    $(this.input.el.parentElement).append($view)
                    }else{
//                    document.querySelector(".o_group_selector").remove()
                    $(this.input.el.parentElement).append($view)
                     }

                    if (this.props.record.mode === 'readonly') {
                        $(self.input.el.parentElement).find('.ks_label_select').addClass('ks_not_click');
                    }
                } else {
                    $(self.input.el.parentElement).append($('<div>').text("No Data Available"));
                }
            } else {
               $(self.input.el.parentElement).append($('<div>').text("Please Enter the Appropriate Query for this"));
            }

        }
        _ks_render_readonly(){
            var self = this;
        $(this.input.el.parentElement).find('div').remove()
        $(this.input.el.parentElement).find('input').addClass('d-none')
            var field = self.props.record.data;

            if(field.ks_query_result){
                var ks_query_result = JSON.parse(field.ks_query_result);
                if (field.ks_dashboard_item_type !== 'ks_kpi' && ks_query_result.records.length){
                    self.ks_check_for_labels();
                    var $view = $(qweb.render('ks_select_labels',{
                        ks_columns_list: self.ks_columns,
                        value: self.ks_columns[self.value],
                        mode: self.props.record.mode,
                    }));
                    if(document.querySelector(".o_group_selector")==null){
                    $(this.input.el.parentElement).append($view)
                    }else{
                    document.querySelector(".o_group_selector").remove()
                    $(this.input.el.parentElement).append($view)
                     }
                } else {
                   $(self.input.el.parentElement).append($('<div>').text("No Data Available"));
                }
            } else {
               $(self.input.el.parentElement).append($('<div>').text("Please Enter the Appropriate Query for this"))
            }
        }
        ks_toggle_icon_input_click(e){
            var self = this;
            if (e.target.id==""){
            this.props.update(e.target.value);
            }
            }

        ks_check_for_labels(){
            var self = this;
            self.ks_columns = {false:false};
            var query_result = JSON.parse(self.props.record.data.ks_query_result);
            if (self.props.name === "ks_ylabels"){
                query_result.header.forEach(function(key){
                    if(typeof(query_result[0][key]) === "number") {
                        self.ks_columns[key] = self.ks_title(key.replace("_", " "));
                    }
                });
            } else {
                query_result.header.forEach(function(key){
                    self.ks_columns[key] = self.ks_title(key.replace("_", " "));
                });
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
    }

registry.category("fields").add('ks_x_labels', KsXLabels);