    /** @odoo-module */

import { patch } from "@web/core/utils/patch";
import { Dialog } from "@web/core/dialog/dialog";
import {KsDashboardNinja} from "@wj_ks_dashboard_ninja/js/wj_ks_dashboard_ninja_new";
import { _t } from "@web/core/l10n/translation";
import { renderToElement,renderToString,renderToFragment } from "@web/core/utils/render";
import { isBrowserChrome, isMobileOS } from "@web/core/browser/feature_detection";
import { Ksdashboardtile } from '@wj_ks_dashboard_ninja/components/ks_dashboard_tile_view/ks_dashboard_tile';
import { getDomainDisplayedOperators } from "@web/core/domain_selector/domain_selector_operator_editor";
import { getOperatorLabel } from "@web/core/tree_editor/tree_editor_operator_editor";
import { DateTimeInput } from "@web/core/datetime/datetime_input";
const { DateTime } = luxon;
import { user } from "@web/core/user";
import {formatDate,formatDateTime} from "@web/core/l10n/dates";
import {parseDateTime,parseDate,} from "@web/core/l10n/dates";
import { serializeDateTime, serializeDate } from "@web/core/l10n/dates";
import { ConfirmationDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { Component } from "@odoo/owl";
import { rpc } from "@web/core/network/rpc";
import { cloneTree } from "@web/core/tree_editor/condition_tree";
import { domainFromTree } from "@web/core/tree_editor/condition_tree";
import { Domain } from "@web/core/domain";



const ks_field_type = {
    binary: "binary",
    boolean: "boolean",
    char: "char",
    date: "date",
    datetime: "datetime",
    float: "number",
    html: "char",
    id: "id",
    integer: "number",
    many2many: "char",
    many2one:"char",
    monetary: "number",
    one2many: "char",
    selection: "selection",
    text: "char"
}


export class FavFilterWizard extends Component{

    setup(){
        super.setup();
    }

}

FavFilterWizard.template = "wj_ks_dashboard_ninja.FavFilterWizard"

FavFilterWizard.components = { Dialog }


patch(KsDashboardNinja.prototype,{
    ks_fetch_items_data(){
        var self = this;
        return super.ks_fetch_items_data().then(function(){
            if (self.ks_dashboard_data.ks_dashboard_domain_data) self.ks_init_domain_data_index();
        });
    },

    ks_init_domain_data_index(){
        var self = this;
        // TODO: Make domain data index from backend : loop wasted
        var temp_data = {};
        var to_insert = Object.values(this.ks_dashboard_data.ks_dashboard_pre_domain_filter).filter((x)=>{
            return x.type==='filter' && x.active && self.ks_dashboard_data.ks_dashboard_domain_data[x.model].ks_domain_index_data.length === 0
        });
        (to_insert).forEach((x)=>{
            this.isPredefined = true
            if(x['categ'] in temp_data) {
               temp_data[x['categ']]['domain']= temp_data[x['categ']]['domain'].concat(x['domain']);
               temp_data[x['categ']]['label']= temp_data[x['categ']]['label'].concat(x['name']);
            } else {
                temp_data[x['categ']] = {'domain': x['domain'], 'label': [x['name']], 'categ': x['categ'], 'model': x['model']};
            }
        })
        Object.values(temp_data).forEach((x)=>{
            this.isModelVisePredefined[x.model] = true;
            self.ks_dashboard_data.ks_dashboard_domain_data[x.model].ks_domain_index_data.push(x);
        })
    },
    onKsDnDynamicFilterSelect(ev){
        var self = this;
        if(this.isFavFilter){
            self.ks_dashboard_data.ks_dashboard_domain_data = {}
            self.header.el?.querySelector('.ks_fav_filters_checked')?.classList.remove('ks_fav_filters_checked', 'global-active')
        }
        this.isFavFilter = false;
        if (ev.currentTarget.classList.contains('dn_dynamic_filter_selected')) {
            self._ksRemoveDynamicFilter(ev.currentTarget.dataset['filterId']);
            ev.currentTarget.classList.remove('dn_dynamic_filter_selected');
        } else {
            self._ksAppendDynamicFilter(ev.currentTarget.dataset['filterId']);
            ev.currentTarget.classList.add('dn_dynamic_filter_selected');
        }
        var storedData = this.getObjectFromCookie('FilterOrderData' + self.ks_dashboard_id);
        if(storedData !== null ){
            this.eraseCookie('FilterOrderData' + self.ks_dashboard_id);
        }
        if(Object.keys(self.ks_dashboard_data.ks_dashboard_domain_data).length !==0){
            this.setObjectInCookie('FilterOrderData' + self.ks_dashboard_id, self.ks_dashboard_data.ks_dashboard_domain_data, 1);
        }else{
            this.setObjectInCookie('FilterOrderData' + self.ks_dashboard_id, {}, 1);
        }
    },

    _ksAppendDynamicFilter(filterId){
        // Update predomain data -> Add into Domain Index -> Add or remove class
        this.ks_dashboard_data.ks_dashboard_pre_domain_filter[filterId].active = true;

        var action = 'add_dynamic_filter';

        var categ = this.ks_dashboard_data.ks_dashboard_pre_domain_filter[filterId].categ;
        var params = {
            'model': this.ks_dashboard_data.ks_dashboard_pre_domain_filter[filterId].model,
            'model_name': this.ks_dashboard_data.ks_dashboard_pre_domain_filter[filterId].model_name,
        }
        this._ksUpdateAddDomainIndexData(action, categ, params);
    },

    _ksRemoveDynamicFilter(filterId){
         // Update predomain data -> Remove from Domain Index -> Add or remove class
        this.ks_dashboard_data.ks_dashboard_pre_domain_filter[filterId].active = false;

        var action = 'remove_dynamic_filter';
        var categ = this.ks_dashboard_data.ks_dashboard_pre_domain_filter[filterId].categ;
        var params = {
            'model': this.ks_dashboard_data.ks_dashboard_pre_domain_filter[filterId].model,
            'model_name': this.ks_dashboard_data.ks_dashboard_pre_domain_filter[filterId].model_name,
        }
        this._ksUpdateRemoveDomainIndexData(action, categ, params);
    },

    _ksUpdateAddDomainIndexData(action, categ, params){
        // Update Domain Index: Add or Remove model related data, Update its domain, item ids
        // Fetch records for the effected items
        // Re-render Search box of this name if the value is add
        var self = this;
        self.header.el?.querySelector('.custom-filter-tab')?.classList.remove('disabled-div');
        this.isPredefined = true
        var model = params['model'] || false;
        this.isModelVisePredefined[model] = true;
        var model_name = params['model_name'] || '';
        const filterAppliedContainer = document.querySelector('.ks_dn_filter_applied_container');
        if (filterAppliedContainer) {
            filterAppliedContainer.classList.remove('ks_hide');
        }

        var filters_to_update = Object.values(this.ks_dashboard_data.ks_dashboard_pre_domain_filter).filter((x)=>{return x.active === true && x.categ === categ});
        var domain_data = self.ks_dashboard_data.ks_dashboard_domain_data[model];
        if (domain_data) {
            var domain_index = (domain_data?.ks_domain_index_data)?.find((x)=>{return x.categ === categ});
            if (domain_index) {
                domain_index['domain'] = [];
                domain_index['label'] = [];
                (filters_to_update).forEach((x)=>{
                    if (domain_index['domain'].length>0) domain_index['domain'].unshift('|');
                    domain_index['domain'] = domain_index['domain'].concat(x['domain']);
                    domain_index['label'] = domain_index['label'].concat(x['name']);
                })
            } else {
                domain_index = {
                    categ: categ,
                    domain: [],
                    label: [],
                    model: model,
                };
                filters_to_update.forEach((x)=>{
                    if (domain_index['domain'].length>0) domain_index['domain'].unshift('|');
                    domain_index['domain'] = domain_index['domain'].concat(x['domain']);
                    domain_index['label'] = domain_index['label'].concat(x['name']);
                });
                domain_data.ks_domain_index_data.push(domain_index);
            }

        } else {
            var domain_index = {
                    categ: categ,
                    domain: [],
                    label: [],
                    model: model,
            };
            filters_to_update.forEach((x)=>{
                if (domain_index['domain'].length>0) domain_index['domain'].unshift('|');
                domain_index['domain'] = domain_index['domain'].concat(x['domain']);
                domain_index['label'] = domain_index['label'].concat(x['name']);
            });
            domain_data = {
                'domain': [],
                'model_name': model_name,
                'item_ids': self.ks_dashboard_data.ks_model_item_relation[model],
                'ks_domain_index_data': [domain_index],
            };
            self.ks_dashboard_data.ks_dashboard_domain_data[model] = domain_data;
        }

        domain_data['domain'] = self._ksMakeDomainFromDomainIndex(domain_data.ks_domain_index_data);
        self.state.pre_defined_filter = {...domain_data}
        self.state.ksDateFilterSelection = 'none'
        self.state.custom_filter = {}
    },

    _ksUpdateRemoveDomainIndexData(action, categ, params){
        var self = this;
        var model = params['model'] || false;
        var model_name = params['model_name'] || '';
        var filters_to_update = Object.values(this.ks_dashboard_data.ks_dashboard_pre_domain_filter).filter((x)=>{return x.active === true && x.categ === categ});
        var domain_data = self.ks_dashboard_data.ks_dashboard_domain_data[model];
        var domain_index = (domain_data.ks_domain_index_data).find((x)=>{return x.categ === categ});


        if (filters_to_update.length<1) {
            if (domain_data.ks_domain_index_data.length>1){
                domain_data.ks_domain_index_data.splice(domain_data.ks_domain_index_data.indexOf(domain_index),1);
//                $('.o_searchview_facet[data-ks-categ="'+ categ + '"]').remove();
            }else {
//                $('.ks_dn_filter_section_container[data-ks-model-selector="'+ model + '"]').remove();
                delete self.ks_dashboard_data.ks_dashboard_domain_data[model];
                if(!Object.keys(self.ks_dashboard_data.ks_dashboard_domain_data).length){
                   const filterAppliedContainer = document.querySelector('.ks_dn_filter_applied_container');
                    if (filterAppliedContainer) {
                        filterAppliedContainer.classList.add('ks_hide');
                    }
                }
            }
        } else{
            domain_index['domain'] = [];
            domain_index['label'] = [];
            (filters_to_update).forEach((x)=>{
                if (domain_index['domain'].length>0) domain_index['domain'].unshift('|');
                domain_index['domain'] = domain_index['domain'].concat(x['domain']);
                domain_index['label'] = domain_index['label'].concat(x['name']);
            })
        }
        if(!domain_index) return;

        if(!Object.values(this.ks_dashboard_data.ks_dashboard_pre_domain_filter).filter((x)=>{return x.active === true}).length){
            this.isPredefined = false
        }
        if(!Object.values(this.ks_dashboard_data.ks_dashboard_pre_domain_filter).filter((x)=>{return x.active === true && x.model === model}).length)
                this.isModelVisePredefined[model] = false;

        domain_data['domain'] = self._ksMakeDomainFromDomainIndex(domain_data.ks_domain_index_data);
        domain_data['ks_remove'] = true
         self.state.pre_defined_filter = {...domain_data}
         if(domain_data['domain'].length != 0){
                var storedData = this.getObjectFromCookie('FilterOrderData' + self.ks_dashboard_id);
                var storedPredefinedData = this.getObjectFromCookie('PredefinedData' + self.ks_dashboard_id);
                if(storedData !== null || storedPredefinedData !== null){
                    this.eraseCookie('FilterOrderData' + self.ks_dashboard_id);
                    this.eraseCookie('PredefinedData' + self.ks_dashboard_id);
                }
                if(Object.keys(self.ks_dashboard_data.ks_dashboard_domain_data).length !==0){
                    this.setObjectInCookie('FilterOrderData' + self.ks_dashboard_id, self.ks_dashboard_data.ks_dashboard_domain_data, 1);
                    this.setObjectInCookie('PredefinedData' + self.ks_dashboard_id, this.ks_dashboard_data.ks_dashboard_pre_domain_filter, 1);
                }else{
                    this.setObjectInCookie('FilterOrderData' + self.ks_dashboard_id, {}, 1);
                    this.setObjectInCookie('PredefinedData' + self.ks_dashboard_id, {}, 1);
                }
         }else{
                var storedData = this.getObjectFromCookie('FilterOrderData' + self.ks_dashboard_id);
                if(storedData){
                   this.eraseCookie('FilterOrderData' + self.ks_dashboard_id);
                   var storedPredefinedData = this.getObjectFromCookie('PredefinedData' + self.ks_dashboard_id);
                   if (storedPredefinedData) this.eraseCookie('PredefinedData' + self.ks_dashboard_id);
                }
                this.setObjectInCookie('FilterOrderData' + self.ks_dashboard_id, {}, 1);
                 this.setObjectInCookie('PredefinedData' + self.ks_dashboard_id, {}, 1);
         }
         self.state.ksDateFilterSelection = 'none'
         self.state.custom_filter = {}
    },

    _ksMakeDomainFromDomainIndex(ks_domain_index_data){
        var domain = [];
        (ks_domain_index_data).forEach((x)=>{
            if (domain.length>0) domain.unshift('&');
            domain = domain.concat((x['domain']));
        })
        return domain;
    },
    ksOnRemoveFilterFromSearchPanel(ev){
        var self = this;
        ev.stopPropagation();
//        ev.preventDefault();
        var search_section = ev.currentTarget.parentElement.parentElement;
        var model = search_section.getAttribute('ksmodel');
        if (search_section.getAttribute('kscateg') != '0'){
            var categ = search_section.getAttribute('kscateg');
            var action = 'remove_dynamic_filter';
            var selected_pre_define_filter = document.querySelectorAll(".dn_dynamic_filter_selected.dn_filter_click_event_selector[data-ks-categ='" + categ + "']");
            selected_pre_define_filter.forEach(function(element) {
                element.classList.remove("dn_dynamic_filter_selected");
                var filterId = element.getAttribute('data-filter-id');
                self.ks_dashboard_data.ks_dashboard_pre_domain_filter[filterId].active = false;
            });

            var params = {
                'model': model,
                'model_name': search_section.getAttribute('modelName'),
            }
            this._ksUpdateRemoveDomainIndexData(action, categ, params);
        } else {
            var domain_data_index = Array.from(search_section.parentElement.children);
            domain_data_index = domain_data_index.indexOf(search_section)
            var domain_data = self.ks_dashboard_data.ks_dashboard_domain_data[model];
            domain_data.ks_domain_index_data.forEach((ks_domain_index_data, index)=>{
                if(ks_domain_index_data.isCustomFilter && domain_data_index >= 0){
                    if(domain_data_index === 0){
                        domain_data.ks_domain_index_data.splice(index, 1);
                    }
                    domain_data_index -= 1
                }

            })

            if (domain_data.ks_domain_index_data.length === 0) {
//                document.querySelector('.ks_dn_filter_section_container[data-ks-model-selector="'+ model + '"]').classList.remove();
//                document.querySelectorAll('.ks_dn_filter_section_container[data-ks-model-selector="' + model + '"]').forEach(function(element) {
//                    element.remove();
//                });
                delete self.ks_dashboard_data.ks_dashboard_domain_data[model];
                if(!Object.keys(self.ks_dashboard_data.ks_dashboard_domain_data).length){
                    const filterAppliedContainers = document.querySelectorAll('.ks_dn_filter_applied_container');
                    filterAppliedContainers.forEach(container => {
                        container.classList.add('ks_hide');
                    });
                }
            }
            if(!Object.values(this.ks_dashboard_data.ks_dashboard_pre_domain_filter).filter((x)=>{return x.active === true}).length)
                this.isPredefined = false

            domain_data['domain'] = self._ksMakeDomainFromDomainIndex(domain_data.ks_domain_index_data);
            domain_data['ks_remove'] = true
            self.state.pre_defined_filter = {}
            self.state.ksDateFilterSelection = 'none'
            self.state.custom_filter = {...domain_data}
            if(domain_data['domain'].length != 0){
                var storedData = this.getObjectFromCookie('FilterOrderData' + self.ks_dashboard_id);
                if(storedData !== null ){
                    this.eraseCookie('FilterOrderData' + self.ks_dashboard_id);
                }
                this.setObjectInCookie('FilterOrderData' + self.ks_dashboard_id, self.ks_dashboard_data.ks_dashboard_domain_data, 1);
            }else{
                var storedData = this.getObjectFromCookie('FilterOrderData' + self.ks_dashboard_id);
                if(storedData){
                   this.eraseCookie('FilterOrderData' + self.ks_dashboard_id);
                }
            }

        }
    },

     ksGetParamsForItemFetch(item_id) {
        var self = this;
        let isCarouselParentClass = false;
        if(item_id.isCarouselParentClass){
            isCarouselParentClass = item_id.isCarouselParentClass
            item_id = item_id.item_id
        }
        var model1 = self.ks_dashboard_data.ks_item_model_relation[item_id][0];
        var model2 = self.ks_dashboard_data.ks_item_model_relation[item_id][1];

        if(model1 in self.ks_dashboard_data.ks_model_item_relation) {
            if (self.ks_dashboard_data.ks_model_item_relation[model1].indexOf(item_id)<0)
                self.ks_dashboard_data.ks_model_item_relation[model1].push(item_id);
        }else {
            self.ks_dashboard_data.ks_model_item_relation[model1] = [item_id];
        }

        if(model2 in self.ks_dashboard_data.ks_model_item_relation) {
            if (self.ks_dashboard_data.ks_model_item_relation[model2].indexOf(item_id)<0)
                self.ks_dashboard_data.ks_model_item_relation[model2].push(item_id);
        }else {
            self.ks_dashboard_data.ks_model_item_relation[model2] = [item_id];
        }

        var ks_domain_1 = self.ks_dashboard_data.ks_dashboard_domain_data[model1] && self.ks_dashboard_data.ks_dashboard_domain_data[model1]['domain'] || [];
        var ks_domain_2 = self.ks_dashboard_data.ks_dashboard_domain_data[model2] && self.ks_dashboard_data.ks_dashboard_domain_data[model2]['domain'] || [];

        if(isCarouselParentClass){
            return this.env.bus.trigger(`TV:List_Load_More_${item_id}`, {
                ks_domain_1: ks_domain_1,
                ks_domain_2: ks_domain_2,
            });
        }
        else{
            return {
                ks_domain_1: ks_domain_1,
                ks_domain_2: ks_domain_2,
            }
        }
    },

    ksRenderDashboard(){
        var self = this;
//        const script = document.createElement('script');
//        script.type = 'text/javascript';
//        script.src = 'https://code.jquery.com/ui/1.13.2/jquery-ui.min.js';
//        document.head.appendChild(script);
//
//        const link = document.createElement('link');
//        link.rel = 'stylesheet';
//        link.href = 'https://code.jquery.com/ui/1.13.2/themes/base/jquery-ui.css';
//        document.head.appendChild(link);
        super.ksRenderDashboard();
        var show_remove_option = false;
         this.ks_custom_filter_option = {};
//        if (Object.values(self.ks_dashboard_data.ks_dashboard_custom_domain_filter).length>0) self.ks_render_custom_filter(show_remove_option);
    },

    ks_render_custom_filter(show_remove_option){
        let table_row_id = document.querySelectorAll('#ks_dn_custom_filters_container .ks_dn_custom_filter_input_container_section').length + 1;
        var newRow = document.createElement('div');
        newRow.id = 'div-' + table_row_id;
        newRow.className = 'ks_dn_custom_filter_input_container_section table-row';
        var self = this;
        var container = renderToFragment('ks_dn_custom_filter_input_container', {
                            ks_dashboard_custom_domain_filter: Object.values(this.ks_dashboard_data.ks_dashboard_custom_domain_filter),
                            show_remove_option: show_remove_option,
                            self: self,
                            this: this,
                            ksOnCustomFilterFieldSelect: self.ksOnCustomFilterFieldSelect.bind(this),
                            trId: "div-" + table_row_id
                        });
//        const tempContainer = document.createElement('div');
//        tempContainer.innerHTML = container;
        if (container)
            Object.values(container.children).forEach( (childContainer) => newRow.append(childContainer));

//        newRow.innerHTML += container

        var first_field_select = Object.values(this.ks_dashboard_data.ks_dashboard_custom_domain_filter)[0]
        var relation = first_field_select.relation
        var field_type = first_field_select.type;
        var ks_operators = getDomainDisplayedOperators(first_field_select);
        var operatorsinfo = ks_operators.map((x)=> getOperatorLabel(x));
        this.operators = ks_operators.map((val,index)=>{
            return{
                'symbol': val,
                'description': operatorsinfo[index]
            }
        })

        var operator_type = this.operators[0];
        var operator_input = renderToElement('ks_dn_custom_domain_input_operator', {
            operators: this.operators,
            self: self,
            this: this,
            trId: "div-" + table_row_id,
            ksOnCustomFilterOperatorSelect: this.ksOnCustomFilterOperatorSelect.bind(this)
        });

        if (operator_input) {
            newRow.append(operator_input);
        }

        const value_input = this._ksRenderCustomFilterInputSection(
            relation,
            operator_type?.symbol,
            ks_field_type[field_type],
            first_field_select.special_data,
            show_remove_option,
            "div-" + table_row_id
        );
        if (value_input) {
            newRow.append(value_input);
        }
        const filtersContainer = document.getElementById("ks_dn_custom_filters_container");
        filtersContainer?.append(newRow);
    },

    async ks_render_filter_options(ev){
        var self = this;
        ev.stopPropagation();
        ev.preventDefault();
        var relation = ev.currentTarget.dataset.relation
        let domain = this.state.domain
        var filter_id = ev.currentTarget.closest('.o_generator_menu_value_td').parentElement.querySelector('.custom_filter_current_value_section').getAttribute('data-index')
        var ks_current_operator_value = ev.currentTarget.closest('.o_generator_menu_value_td').parentElement.querySelector('.operator_current_value_section').getAttribute('data-value')
        var ks_path = "/web/dataset/call_kw/"+relation+"/name_search"
        if (!ev.target.parentElement.classList.contains("awesomplete")){
            var result = await rpc(ks_path,{
                    model: relation,
                    method: "name_search",
                    args: [],
                    kwargs: {
                        name: '',
                        args: domain,
                        operator: "ilike",
                        limit: 10
                    }
                });
            self.ks_custom_filter_option[filter_id] = result
            self.ks_autocomplete_data_result = result.map((item)=> item[1]);
        }


        if (!ev.target.parentElement.classList.contains("awesomplete") && ks_current_operator_value != 'in'){
            this.awesomplete = new Awesomplete(ev.target,{
                minChars: 0,
                autoFirst: true,
            });
        }
        if (!ev.target.parentElement.classList.contains("awesomplete") && ks_current_operator_value === 'in'){
            this.awesomplete = new Awesomplete(ev.target,{
                minChars: 0,
                autoFirst: true,
                filter: function(text, input) {
		            return Awesomplete.FILTER_CONTAINS(text, input.match(/[^,]*$/)[0]);
	            },

                item: function(text, input) {
                    return Awesomplete.ITEM(text, input.match(/[^,]*$/)[0]);
                },

                replace: function(text) {
                    var before = this.input.value.match(/^.+,\s*|/)[0];
                    this.input.value = before + text + ", ";
                }
            });
        }
        this.awesomplete.list = self.ks_autocomplete_data_result
        this.awesomplete?.evaluate();
        ev.target.focus();
        this.filterTableDropdownShow(ev)

    },


    _ksRenderCustomFilterInputSection(relation, operator_type, field_type, special_data, show_remove_option,trId){
        let self = this;
        var value_input;
        switch (field_type) {
            case 'boolean':
                return false;
                break;
            case 'selection':
                if (!operator_type) return false;
                else {
                    value_input = renderToFragment('ks_dn_custom_domain_input_selection', {
                        selection_input: special_data['select_options'] || [],
                        show_remove_option: show_remove_option,
                        ksOnCustomFilterConditionRemove: this.ksOnCustomFilterConditionRemove.bind(this),
                        onCustomFilterSelectionFieldSelect: this.onCustomFilterSelectionFieldSelect.bind(this),
                        self: self,
                        this: this,
                        relation: relation,
                        operator: operator_type,
                        trId
                    });
                }
            break;
            case 'date':
            case 'datetime':
                if (!operator_type) return false;
                value_input = this._ksRenderDateTimeFilterInput(operator_type, field_type, show_remove_option);
                break;
            case 'char':
            case 'id':
            case 'number' :
                if (!operator_type) return false;
                else {
                    value_input = renderToFragment('ks_dn_custom_domain_input_text', {
                        show_remove_option: show_remove_option,
                        self: self,
                        this: this,
                        ksOnCustomFilterConditionRemove: this.ksOnCustomFilterConditionRemove.bind(this),
                        relation: relation,
                        operator: operator_type,
                        autoCompleteFocusOut: this.autoCompleteFocusOut.bind(this),
                        trId
                    });
                }
                break;
            default:
                return;
        }
        return value_input;
    },

    onCustomFilterSelectionFieldSelect(ev){
        let targetRowId = '#' + ev.target.dataset?.trId;
        let changedValue = ev.currentTarget.textContent;
        let valueAttribute = ev.currentTarget.getAttribute('value');
        document.querySelector('#ks_dn_custom_filters_container ' + targetRowId + ' .o_generator_menu_value_td .o_generator_menu_value').textContent = changedValue;
        document.querySelector('#ks_dn_custom_filters_container ' + targetRowId + ' .o_generator_menu_value_td .o_generator_menu_value').dataset.value = valueAttribute;
    },

    _ksRenderDateTimeFilterInput(operator, field_type, show_remove_option){
        var self = this;
        var value_container = renderToFragment('ks_dn_custom_domain_input_date', {
            operator: operator,
            field_type: field_type,
            show_remove_option: show_remove_option,
            ksOnCustomFilterConditionRemove: this.ksOnCustomFilterConditionRemove.bind(this)
        });

        var datetimePicker = value_container.querySelector("#datetimepicker1");

        if (field_type == 'date'){
            if (datetimePicker) {
                datetimePicker.value = formatDate(DateTime.now(), { format: "yyyy-MM-dd" });
            }

        }else{
            if (datetimePicker) {
                datetimePicker.value = new Date(DateTime.now() + new Date().getTimezoneOffset() * -60 * 1000).toISOString().slice(0, 19);
            }
        }
        return value_container;
    },

    ksOnCustomFilterApply(ev){
        var self = this;
        var model_domain = {};
        if(this.isFavFilter){
            self.ks_dashboard_data.ks_dashboard_domain_data = {}
        }
        this.isFavFilter = false;
        document.querySelectorAll('.ks_dn_custom_filter_input_container_section').forEach((filter_container) => {
            var field_id = filter_container.querySelector('.custom_filter_current_value_section').getAttribute('data-index');
            var field_select = this.ks_dashboard_data.ks_dashboard_custom_domain_filter[field_id];
            var field_type = field_select.type;
            var domainValue = [];
            var domainArray = [];
            var operatorIndex = filter_container.querySelector('.operator_current_value_section').getAttribute('data-index');
            var operator = getDomainDisplayedOperators(field_select)[operatorIndex];
            var ks_label = this.operators.filter((x) => x.symbol === operator)

            var label = field_select.name + ' ' + ks_label[0].description;
            if (['date', 'datetime'].includes(field_type)) {
                var dateValue = [];
                filter_container.querySelectorAll(".o_generator_menu_value_td .o_datepicker").forEach((input_val) => {
                    var a = input_val.value;
                    if (field_type === 'datetime'){
                        var b = formatDateTime(DateTime.fromISO(a),{ format: "yyyy-MM-dd HH:mm:ss" });
                        var c = formatDateTime(DateTime.fromISO(a),{ format: "dd/MM/yyyy HH:mm:ss" })  ;
                    }else{
                        var b = formatDate(DateTime.fromFormat(a,'yyyy-MM-dd'),{ format: "yyyy-MM-dd" });
                        var c = formatDate(DateTime.fromFormat(a,'yyyy-MM-dd'),{ format: "dd/MM/yyyy" });
                    }

                    domainValue.push(b);
                    dateValue.push(c);
                });
                label = label +' ' + dateValue.join(" and " );
            } else if (field_type === 'selection') {
                let domainValueText = filter_container.querySelectorA(".o_generator_menu_value_td .o_generator_menu_value").textContent
                domainValue = [domainValueText];
                label = label + ' ' + domainValueText;
            }
            else if (field_type === 'boolean') {
                let domainValueBool = filter_container.querySelector(".ks_operator_option_selector_td .operator_current_value_section").textContent
                domainValueBool = domainValueBool === 'is not' ? false : true
                operator = domainValueBool === 'is not' ? '!=' : '='
                domainValue = [domainValueBool];
//                label = label + ' ' + domainValueText;
            }
            else {
                if (operator === 'in'){
                    var ks_input_value = filter_container.querySelector(".o_generator_menu_value_td textarea").value.split(',');
                    ks_input_value.pop();
                    ks_input_value = ks_input_value.map((x)=> x.trim());
                    var ks_filter_options = this.ks_custom_filter_option[field_id]
                    const ks_domain_array = (ks_filter_options)?.filter((item)=> ks_input_value.includes(item[1])).map((value)=>value[0])
                    if(ks_domain_array) domainValue = [...ks_domain_array]
                    else domainValue = []
                     label = label + ' ' + filter_container.querySelector(".o_generator_menu_value_td textarea").value;
                }
                else{
                    let inputvalues;
                    if (operator === 'between') {
                        inputvalues = filter_container.querySelectorAll(".o_generator_menu_value_td input")
                        inputvalues = Array.from(inputvalues).map(input => input.value)
                    }
                    let defaultCondition = {
                        negate: false,
                        operator: "=",
                        path: "id",
                        type: "condition",
                        value: 1
                    }
                    let node = cloneTree(defaultCondition);
                    node.path = field_select.field_name
                    node.operator = operator
                    node.value = inputvalues ? inputvalues : filter_container.querySelector(".o_generator_menu_value_td input").value
                    let domain = Domain.and([domainFromTree(node)])

                    if(operator === 'between'){
                        domainValue = [domain.ast?.value[1]?.value[2]?.value, domain.ast?.value[2]?.value[2]?.value];
                        label = label + ' ' + domainValue[0] + " & " + domainValue[1];
                    }
                    else{
                        domainValue = [domain.ast?.value[0]?.value[2]?.value];
                        label = label + ' ' + filter_container.querySelector(".o_generator_menu_value_td input").value;
                        operator = domain?.ast?.value[0]?.value[1]?.value
                    }

                }
            }

            if (operator === 'between') {
                domainArray.push(
                    [field_select.field_name, '>=', domainValue[0]],
                    [field_select.field_name, '<=', domainValue[1]]
                );
                domainArray.unshift('&');
            } else {
                if(operator === 'in'){
                    domainArray.push([field_select.field_name, operator, domainValue]);

                }else{
                    domainArray.push([field_select.field_name, operator, domainValue[0]]);
                }
            }

            if(field_select.model in model_domain){
                model_domain[field_select.model]['domain'] = model_domain[field_select.model]['domain'].concat(domainArray);
                model_domain[field_select.model]['domain'].unshift('|');
                model_domain[field_select.model]['label'] = model_domain[field_select.model]['label'] + ' or ' +  label;
            } else {
                model_domain[field_select.model] = {
                    'domain': domainArray,
                    'label': label,
                    'model_name': field_select.model_name,
                }
            }
        });
        this.ksAddCustomDomain(model_domain);
    },

    eraseCookie(name) {
        document.cookie = name + '=; Max-Age=-99999999; path=/';
    },

    setCookie(name, value, days) {
        var expires = "";
        if (days) {
            var date = new Date();
            date.setTime(date.getTime() + (days*24*60*60*1000));
            expires = "; expires=" + date.toUTCString();
        }
        document.cookie = name + "=" + (value || "") + expires + "; path=/";
    },

     setObjectInCookie(name, object, days) {
        var jsonString = JSON.stringify(object);
        this.setCookie(name, jsonString, days);
    },

    getCookie(name) {
        var nameEQ = name + "=";
        var ca = document.cookie.split(';');
        for (var i = 0; i < ca.length; i++) {
            var c = ca[i];
            while (c.charAt(0) == ' ') c = c.substring(1, c.length);
            if (c.indexOf(nameEQ) == 0) return c.substring(nameEQ.length, c.length);
        }
        return null;
    },

    getObjectFromCookie(name) {
        var jsonString = this.getCookie(name);
        return jsonString ? JSON.parse(jsonString) : null;
    },

    ksAddCustomDomain(model_domain){
        var self = this;
        const container = document.querySelector('.ks_dn_filter_applied_container');
        if (container) {
            container.classList.remove('ks_hide');
        }
        Object.entries(model_domain).map(([model,val])=>{
            var domain_data = self.ks_dashboard_data.ks_dashboard_domain_data[model];
            var domain_index = {
                categ: false,
                domain: val['domain'],
                label: [val['label']],
                model: model,
                isCustomFilter: true,
            }

            if (domain_data) {
                domain_data.ks_domain_index_data.push(domain_index);
            } else {
                domain_data = {
                    'domain': [],
                    'model_name': val.model_name,
                    'item_ids': self.ks_dashboard_data.ks_model_item_relation[model],
                    'ks_domain_index_data': [domain_index],
                }
                self.ks_dashboard_data.ks_dashboard_domain_data[model] = domain_data;
            }

//            document.getElementById('ks_dn_custom_filters_container').innerHTML = '';
//            var show_remove_option = false;
//            self.ks_render_custom_filter(show_remove_option);

            domain_data['domain'] = self._ksMakeDomainFromDomainIndex(domain_data.ks_domain_index_data);
            self.state.custom_filter = {...domain_data}

            if(domain_data['domain'][0] !== undefined && domain_data['domain'].length != 0){
                var storedData = this.getObjectFromCookie('FilterOrderData' + self.ks_dashboard_id);
                if(storedData !== null ){
                    this.eraseCookie('FilterOrderData' + self.ks_dashboard_id);
                }
                this.setObjectInCookie('FilterOrderData' + self.ks_dashboard_id, self.ks_dashboard_data.ks_dashboard_domain_data, 1);
            }

            self.state.pre_defined_filter = {}
            self.state.ksDateFilterSelection = 'none'
        })
    },

    ksOnCustomFilterFieldSelect(ev){
        var self =this;
        let targetRowId = '#' + ev.target.dataset?.trId
        let displayed_filter_container = document.querySelector(targetRowId + ' .custom_filter_current_value_section');
        if(displayed_filter_container)  {
            displayed_filter_container.textContent = ev.currentTarget.text;
            displayed_filter_container.setAttribute('data-index', ev.currentTarget.dataset?.value);
        }
        var parent_container = document.getElementById('ks_custom_filter_table');
        var operatorOptionSelector = parent_container.querySelector(targetRowId + ' .ks_operator_option_selector_td');
        if (operatorOptionSelector) {
            operatorOptionSelector.remove();
        }
        var generatorMenuValue = parent_container.querySelector(targetRowId + ' .o_generator_menu_value_td');
        if (generatorMenuValue) {
            generatorMenuValue.remove();
        }
        var customFilterDeleteBtn = parent_container.querySelector(targetRowId + ' .customFilterDeleteBtn');
        if (customFilterDeleteBtn) {
            customFilterDeleteBtn.remove();
        }
        var field_id = ev.currentTarget.dataset.value;
        var field_select = self.ks_dashboard_data.ks_dashboard_custom_domain_filter[field_id];
        var relation = field_select.relation
        var field_type = field_select.type;
        var ks_operators = getDomainDisplayedOperators(field_select);
        var operatorsinfo = ks_operators.map((x)=> getOperatorLabel(x));
        this.operators = ks_operators.map((val,index)=>{
            return{
                'symbol': val,
                'description': operatorsinfo[index]
            }

         })
        var operator_type = self.operators[0];
        const operator_td = renderToElement('ks_dn_custom_domain_input_operator', {
            operators: self.operators,
            self: self,
            this: this,
            trId: ev.target.dataset?.trId,
            ksOnCustomFilterOperatorSelect: this.ksOnCustomFilterOperatorSelect.bind(this)
        });

        document.querySelector(targetRowId).appendChild(operator_td);
        let isShowDeleteBtn = document.getElementById('ks_dn_custom_filters_container').children.length <= 1 || ev.target.dataset?.trId === 'div-1' ? false : true;
        var value_input = self._ksRenderCustomFilterInputSection(relation, operator_type?.symbol, ks_field_type[field_type], field_select.special_data, isShowDeleteBtn, ev.target.dataset?.trId);
        if (value_input) {
            let targetRow = document.querySelector(targetRowId)
            Object.values(value_input.children).forEach( (value) => targetRow.appendChild(value));
        }
    },

    ksOnCustomFilterOperatorSelect(ev){
        var parent_container = document.getElementById('ks_custom_filter_table');
        let targetRowId = '#' + ev.target.dataset?.trId
        let displayed_operator_container = document.querySelector(targetRowId + ' .operator_current_value_section');
        if(displayed_operator_container){
            displayed_operator_container.textContent = ev.currentTarget.text;
            displayed_operator_container.setAttribute('data-index', ev.currentTarget.dataset?.index);
            displayed_operator_container.setAttribute('data-value', ev.currentTarget.dataset?.value);
        }
        var operator_symbol = ev.currentTarget.dataset?.value;
        var customFilterSection = parent_container.querySelector(targetRowId + ' .custom_filter_current_value_section');
        var field_id = customFilterSection ? customFilterSection.getAttribute('data-index') : null;
        var field_select = this.ks_dashboard_data.ks_dashboard_custom_domain_filter[field_id];
        var relation = field_select?.relation
        var field_type = field_select?.type;
        var ks_operators = getDomainDisplayedOperators(field_select);
        var operator_type = ks_operators[ev.currentTarget.dataset?.index];

//        parent_container.querySelector(targetRowId + ' .o_generator_menu_value_td')?.classList.remove();
        const elementToRemove = parent_container.querySelector(targetRowId + ' .o_generator_menu_value_td');
        if (elementToRemove) {
            elementToRemove.remove();
        }
        const removeDelete = parent_container.querySelector(targetRowId + ' .customFilterDeleteBtn');
        if (removeDelete) {
            removeDelete.remove();
        }
//        parent_container.querySelector(targetRowId + ' .customFilterDeleteBtn')?.classList.remove();
        let isShowDeleteBtn = (document.getElementById('ks_dn_custom_filters_container')?.children?.length <= 1 || ev.target.dataset?.trId === 'div-1') ? false : true;
        var value_td = this._ksRenderCustomFilterInputSection(relation, operator_type, ks_field_type[field_type], field_select?.special_data, isShowDeleteBtn, ev.target.dataset?.trId)
//        if (value_td) {
//            document.querySelector(targetRowId)?.appendChild(value_td);
//        }
        if (value_td) {
            let targetRow = document.querySelector(targetRowId)
            Object.values(value_td.children).forEach( (value) => targetRow.appendChild(value));
        }
    },

    ksOnCustomFilterConditionAdd(){
        var show_remove_option = true;
        this.ks_render_custom_filter(show_remove_option);
    },
    ksOnCustomFilterConditionRemove(ev){
        ev.stopPropagation();
        ev.currentTarget.parentElement.remove();
    },

    searchPredefinedFilter(ev){
        let searchName = ev.currentTarget.value;
        let searchedPredefinedFilters;
        if(ev.currentTarget.value !== ''){
            searchedPredefinedFilters = Object.values(this.state.ks_dn_pre_defined_filters).filter(
                (filter) => filter.name.toLowerCase().includes(searchName.toLowerCase()) || filter.type === 'separator'
            );
            while(searchedPredefinedFilters.length && searchedPredefinedFilters[searchedPredefinedFilters.length - 1].type === 'separator')
                searchedPredefinedFilters.pop();
            while(searchedPredefinedFilters.length && searchedPredefinedFilters[0].type === 'separator')   searchedPredefinedFilters.shift();
        }
        else{
            searchedPredefinedFilters = this.state.ks_dn_pre_defined_filters ;
        }

        let filterSection = ev.currentTarget.closest('.ks_dn_pre_filter_menu').querySelector('.predefined_filters_section');
        this.attachSearchFilter(filterSection, searchedPredefinedFilters);
    },

    predefinedSearchFocusout(ev){
        let input = ev.currentTarget.querySelector('.dropdown-menu.show .predefinedFilterSearchInput');
        if (input) input.value = '';
        let filterSection = ev.currentTarget.querySelector('.dropdown-menu.show .predefined_filters_section');
        this.attachSearchFilter(filterSection, Object.values(this.state.ks_dn_pre_defined_filters));
    },

    attachSearchFilter(filterSection, searchedPredefinedFilters){
        if (filterSection) {
            let searchedFilters = renderToElement("search_filter_dropdown", {
                searchedPredefinedFilters: searchedPredefinedFilters,
                onKsDnDynamicFilterSelect: this.onKsDnDynamicFilterSelect.bind(this)
            });
            filterSection.parentNode.replaceChild(searchedFilters, filterSection);
        }
    },

    favFilterLayoutToggle(ev){
        this.env.services.dialog.add(FavFilterWizard,{
            ks_save_favourite: this.ks_save_favourite.bind(this)
        });
    },

    ks_save_favourite(ev, dialogCloseCallback){
        ev.preventDefault();
        ev.stopPropagation();
        var self = this;
        var ks_filter_name = document.getElementById('favourite_filter_name').value;
        var ks_is_fav_filter_shared = document.getElementById('favFilterShareBool').checked;
        if (!ks_filter_name.length){
            this.notification.add(_t("A name for your favorite filter is required."), {
                    type: "warning",
                });

        }else{
            var ks_saved_fav_filters = Object.keys(self.ks_dashboard_data.ks_dashboard_favourite_filter)
            const favourite = ks_saved_fav_filters.find(item => item == ks_filter_name)
            if (favourite?.length){
                this.notification.add(_t("A filter with same name already exists."), {
                    type: "warning",
                });
            }
            else{
                var ks_filter_to_save = JSON.stringify(self.ks_dashboard_data.ks_dashboard_domain_data)
                rpc("/web/dataset/call_kw/ks_dashboard_ninja.favourite_filters/create", {
                    model: 'ks_dashboard_ninja.favourite_filters',
                    method: 'create',
                    args: [{
                        name:ks_filter_name,
                        ks_dashboard_board_id: self.ks_dashboard_id,
                        ks_filter: ks_filter_to_save,
                        ks_access_id: ks_is_fav_filter_shared ? false : user.context.uid
                    }],
                    kwargs: {}
                }).then(function(result){

                    var ks_filter_obj = {
                                id:result,
                                filter: JSON.parse(JSON.stringify(self.ks_dashboard_data.ks_dashboard_domain_data)),
                                name:ks_filter_name,
                                ks_access_id: ks_is_fav_filter_shared ? false : user.context.uid
                    };
                    self.ks_dashboard_data.ks_dashboard_favourite_filter[ks_filter_name] = ks_filter_obj
//                    self.state.stateToggle = !self.state.stateToggle
                    var filterContainer = renderToElement('dn_favourite_filter_dropdown', {
                        ks_favourite_filters: self.ks_dashboard_data.ks_dashboard_favourite_filter,
                        onksfavfilterselected: self.onksfavfilterselected.bind(self),
                        ks_delete_favourite_filter: self.ks_delete_favourite_filter.bind(self),
                        self: self,
                        ks_dashboard_data: self.ks_dashboard_data
                    });
                    var favFilterDropdowns = document.querySelectorAll('#favFilterMain .favFilterDropdown');
                    favFilterDropdowns.forEach(function(dropdown) {
                        dropdown.remove();
                    });
                    document.getElementById('favFilterMain')?.replaceWith(filterContainer);
                    document.getElementById('favFilterMain')?.classList.remove('ks_hide');
                    dialogCloseCallback();
                });
            }
        }
    },



    ks_delete_favourite_filter(ev){
        ev.stopPropagation();
        ev.preventDefault();
        var self = this;
        var ks_filter_id_to_del = ev.currentTarget.getAttribute('fav-id');
        var ks_filter_name_to_del = ev.currentTarget.getAttribute('fav-name');
        var ks_filter_domain = self.ks_dashboard_data.ks_dashboard_favourite_filter[ks_filter_name_to_del].filter;
        var ks_access_id = self.ks_dashboard_data.ks_dashboard_favourite_filter[ks_filter_name_to_del].ks_access_id;
        var ks_remove_filter_models = Object.keys(ks_filter_domain)
        const ks_items_to_update_remove = self.ks_dashboard_data.ks_dashboard_items_ids.filter((item) =>
               ks_remove_filter_models.includes(self.ks_dashboard_data.ks_item_model_relation[item][0])|| ks_remove_filter_models.includes(self.ks_dashboard_data.ks_item_model_relation[item][1])
        );
        if (ks_access_id){
            self.dialogService.add(ConfirmationDialog, {
            body: _t("Are you sure you want to remove this filter?"),
            confirm: () => {
                self.ks_delete_fav_filter(ks_filter_name_to_del,ks_filter_id_to_del,ks_items_to_update_remove)
            }
            })
        }else{
            self.dialogService.add(ConfirmationDialog, {
            body: _t("This filter is global and will be removed for everybody if you continue."),
            confirm: () => {
                    self.ks_delete_fav_filter(ks_filter_name_to_del,ks_filter_id_to_del,ks_items_to_update_remove)
                }
            })
        }
    },



    ks_delete_fav_filter(ks_filter_name_to_del,ks_filter_id_to_del,ks_items_to_update_remove){
         var self = this;
         this.isFavFilter = false;
         rpc("/web/dataset/call_kw/ks_dashboard_ninja.favourite_filters/unlink", {
            model: 'ks_dashboard_ninja.favourite_filters',
            method: 'unlink',
            args: [Number(ks_filter_id_to_del)],
            kwargs: {}
        }).then(function(result) {
            delete self.ks_dashboard_data.ks_dashboard_favourite_filter[ks_filter_name_to_del]
            var filterContainer = renderToElement('dn_favourite_filter_dropdown', {
                ks_favourite_filters: self.ks_dashboard_data.ks_dashboard_favourite_filter,
                onksfavfilterselected: self.onksfavfilterselected.bind(self),
                ks_delete_favourite_filter: self.ks_delete_favourite_filter.bind(self),
                self: self,
                ks_dashboard_data: self.ks_dashboard_data
            });
             var favFilterDropdowns = document.querySelectorAll('#favFilterMain .favFilterDropdown');
            favFilterDropdowns.forEach(function(dropdown) {
                dropdown.remove();
            });
            if(document.getElementById('favFilterMain')) {
                document.getElementById('favFilterMain').appendChild(filterContainer);
            }
            document.querySelector('#favFilterMain').classList.remove('ks_hide');
            if (!document.querySelector('.favFilterListItems')) {
                document.getElementById('favFilterMain').classList.add('ks_hide');
            }

            Object.keys(self.ks_dashboard_data.ks_dashboard_domain_data).forEach((model) => {
                self.state.pre_defined_filter = self.ks_dashboard_data.ks_dashboard_domain_data[model];
            })

            self.state['domain_data']=self.ks_dashboard_data.ks_dashboard_domain_data;
        });
    },

    ksFavFilterFacetRemove(ev){
        ev.preventDefault();
        ev.stopPropagation();
        this.isFavFilter = false;
        this.header.el?.querySelector('.custom-filter-tab')?.classList.remove('disabled-div')
        let FilterModels = Object.keys(this.ks_dashboard_data.ks_dashboard_domain_data);
        if (FilterModels.length){
                let domain_data = {
                    item_ids: [],
                };
                FilterModels.forEach((model)=>{
                    let item_ids = this.ks_dashboard_data.ks_dashboard_favourite_filter[this.activeFavFilterName].filter[model]?.item_ids
                    if(item_ids)
                        domain_data.item_ids = [ ...domain_data['item_ids'],...item_ids];
                })
                this.state.pre_defined_filter = {...domain_data};
            }
        this.state.stateToggle = !this.state.stateToggle
        ev.currentTarget.parentElement.parentElement?.remove();
        this.ks_dashboard_data.ks_dashboard_domain_data = {}
        var elements = this.header.el?.querySelectorAll('.ks_fav_filters_checked');
        elements.forEach((element) => {
            element.classList.remove('ks_fav_filters_checked', 'global-active');
        });
    },

    onksfavfilterselected(ev){
        var self = this;
        ev.stopPropagation();
        ev.preventDefault();
        this.env.bus.trigger("Clear:Custom-Filter-Facets",{})
        this.env.bus.trigger("Clear:Custom-Filter",{})
        // remove pre define filters first
       var ks_filters_to_remove = document.querySelectorAll('.ks_dn_filter_applied_container .ks_dn_filter_section_container .o_searchview_facet');
        this.ks_pre_define_filters_model = [];
        ks_filters_to_remove.forEach(function(filter,item){
           var ks_filter_model = filter.getAttribute('ksmodel');
           var categ = filter.getAttribute('kscateg');
           // to update the domain only once for the item having both custom and pre-define filters.
           if (!self.ks_pre_define_filters_model.includes(ks_filter_model)){
               var filters = JSON.parse(JSON.stringify(self.ks_dashboard_data.ks_dashboard_favourite_filter))
               self.ks_dashboard_data.ks_dashboard_domain_data[ks_filter_model].domain = [];
               self.ks_dashboard_data.ks_dashboard_favourite_filter = filters
               // to restrict one fetch update for the item with same model in pre-define and fav filters when more than one filters are selected in pre-define
              var favName = ev.currentTarget.getAttribute('fav-name');
              var ks_filters = Object.keys(self.ks_dashboard_data.ks_dashboard_favourite_filter[favName].filter);
               self.ks_pre_define_filters_model.push(ks_filter_model);
               if (!ks_filters.includes(ks_filter_model)){
                    self._ksUpdateRemoveDomain(self.ks_dashboard_data.ks_dashboard_domain_data[ks_filter_model]);
               }
           }
        });
//       var facetsToRemove = document.querySelectorAll('.o_searchview_facet');
//        facetsToRemove.forEach(function(facet) {
//            facet.remove();
//        });
        var dynamicFilters = document.querySelectorAll('.dn_dynamic_filter_selected');
        dynamicFilters.forEach(function(filter) {
            var filterId = filter.getAttribute('data-filter-id');
            self.ks_dashboard_data.ks_dashboard_pre_domain_filter[filterId].active = false;
            filter.classList.remove('dn_dynamic_filter_selected', 'global-active');
        });
        var elementsToRemove = document.querySelectorAll('.ks_dn_filter_applied_container .ks_dn_filter_section_container');
        elementsToRemove.forEach(function(element) {
            element.remove();
        });
//        $(".ks_dn_filter_applied_container").addClass('ks_hide');

        // unchecked the checked filters first
        var currentTarget = ev.currentTarget.parentElement.parentElement;
        var ks_filter_to_uncheck = currentTarget?.querySelector('.ks_fav_filters_checked');
        let item_for_update = [];
        if (ks_filter_to_uncheck){
            self.isFavFilter = false;
            self.header.el?.querySelector('.custom-filter-tab')?.classList.remove('disabled-div')
            var ks_remove_filter_name = ks_filter_to_uncheck.getAttribute('fav-name');
            var ks_remove_filter_domain = self.ks_dashboard_data.ks_dashboard_favourite_filter[ks_remove_filter_name].filter;
            var ks_remove_filter_models = Object.keys(ks_remove_filter_domain)
            const ks_items_to_update_remove = self.ks_dashboard_data.ks_dashboard_items_ids.filter((item) =>
               ks_remove_filter_models.includes(self.ks_dashboard_data.ks_item_model_relation[item][0])|| ks_remove_filter_models.includes(self.ks_dashboard_data.ks_item_model_relation[item][1])
            );
            item_for_update = ks_items_to_update_remove;
             if (ks_items_to_update_remove.length && ks_filter_to_uncheck.getAttribute('fav-name') === ev.currentTarget?.getAttribute('fav-name')){
                let domain_data = {
                    item_ids: [],
                };
                self.ks_dashboard_data.ks_dashboard_domain_data = {}
                ks_remove_filter_models.forEach((model)=>{
                    let item_ids = self.ks_dashboard_data.ks_dashboard_favourite_filter[ks_remove_filter_name].filter[model].item_ids
                    if(item_ids)
                        domain_data.item_ids = [ ...domain_data['item_ids'],...item_ids];
                })
                self.state.pre_defined_filter = {...domain_data};
            }
            this.state.stateToggle = !this.state.stateToggle
            var currentTarget = ev.currentTarget;
            var parentElement = currentTarget.parentElement.parentElement;
            var checkedElements = parentElement.querySelectorAll('.ks_fav_filters_checked');
            checkedElements.forEach(function(element) {
                element?.classList.remove('ks_fav_filters_checked', 'global-active');
            });

        }
        // Apply the fav filter
        if (ks_filter_to_uncheck?.getAttribute('fav-name') != ev.currentTarget?.getAttribute('fav-name')){
            self.isFavFilter = true;
            self.header.el?.querySelector('.custom-filter-tab')?.classList.add('disabled-div')
            var ks_applied_filter_name = ev.currentTarget.getAttribute('fav-name');
            self.activeFavFilterName = ks_applied_filter_name;
            ev.currentTarget.classList.add('ks_fav_filters_checked');
            var ks_applied_filter_domain = self.ks_dashboard_data.ks_dashboard_favourite_filter[ks_applied_filter_name].filter;
            var ks_applied_filter_models = Object.keys(ks_applied_filter_domain)
            let ks_items_to_update = self.ks_dashboard_data.ks_dashboard_items_ids.filter((item) =>
               ks_applied_filter_models.includes(self.ks_dashboard_data.ks_item_model_relation[item][0])|| ks_applied_filter_models.includes(self.ks_dashboard_data.ks_item_model_relation[item][1])
            );
            if(item_for_update.length !== 0){
                ks_items_to_update = [...new Set([...ks_items_to_update, ...item_for_update])]
            }
            ev.currentTarget.classList.add('ks_fav_filters_checked', 'global-active');
            if (ks_items_to_update.length){
                let domain_data = {
                    item_ids: [],
                };
                self.ks_dashboard_data.ks_dashboard_domain_data = {...ks_applied_filter_domain}
                self.state['domain_data'] = self.ks_dashboard_data.ks_dashboard_domain_data;
                ks_applied_filter_models.forEach((model)=>{
                    let item_ids = self.ks_dashboard_data.ks_dashboard_favourite_filter[ks_applied_filter_name].filter[model].item_ids
                    if(item_ids)
                        domain_data.item_ids = [ ...domain_data['item_ids'],...item_ids];
                })
                if(item_for_update.length !== 0){
                    domain_data.item_ids = [...new Set([...domain_data['item_ids'], ...item_for_update])]
                }
                self.state.pre_defined_filter = {...domain_data};

            }
            this.state.stateToggle = !this.state.stateToggle
        }
    },

    ks_remove_favourite_filter(filter){
        var self = this;
        var ks_remove_filter_name = filter;
        var ks_remove_filter_domain = self.ks_dashboard_data.ks_dashboard_favourite_filter[ks_remove_filter_name].filter;
        var ks_remove_filter_models = Object.keys(ks_remove_filter_domain)
        const ks_items_to_update_remove = self.ks_dashboard_data.ks_dashboard_items_ids.filter((item) =>
           ks_remove_filter_models.includes(self.ks_dashboard_data.ks_item_model_relation[item][0])|| ks_remove_filter_models.includes(self.ks_dashboard_data.ks_item_model_relation[item][1])
        );
         if (ks_items_to_update_remove.length){
            let domain_data = {
                    item_ids: [],
                };
            self.ks_dashboard_data.ks_dashboard_domain_data = {}
            ks_remove_filter_models.forEach((model)=>{
                let item_ids = self.ks_dashboard_data.ks_dashboard_favourite_filter[ks_remove_filter_name].filter[model].item_ids;
                if(item_ids)
                    domain_data.item_ids = [ ...domain_data['item_ids'],...item_ids];
            })
            self.state.pre_defined_filter = {...domain_data}
        }
    },

    _ksUpdateRemoveDomain(domain_data){
        var self =this;
        self.state.pre_defined_filter = {...domain_data}
    },

    clear_filters(ev){
        document.getElementById('ks_dn_custom_filters_container').innerHTML = '';
        this.ks_render_custom_filter(false);
    },



    filterTableDropdownShow(e) {
        let targetElement = e.target.closest('.filter_dropdown');

        if (targetElement) {
            let dropdownMenu = targetElement.querySelector('.dropdown-menu') || targetElement.querySelector('ul');
            var dropdownToggle = targetElement.querySelector('.dropdown-toggle') || targetElement.querySelector('.ks_input_filter_options');

            if (dropdownMenu && dropdownToggle) {
                if(dropdownMenu.id?.includes("awesomplete_list"))   dropdownMenu.classList.add('awesomplete_list_ul');
                document.body.appendChild(dropdownMenu);
                var targetRect = targetElement.getBoundingClientRect();

                dropdownMenu.style.display = 'block';
                dropdownMenu.style.position = 'absolute';
                dropdownMenu.style.top = (targetRect.top + window.scrollY + targetElement.offsetHeight) + 'px';
                dropdownMenu.style.left = (targetRect.left + window.scrollX) + 'px';

                dropdownMenu.style.width = dropdownToggle.offsetWidth + 'px';
            }
        }
    },

    filterTableDropdownHide(e) {
        var targetElement = e.target.closest('.filter_dropdown');
        let dropdownMenu = document.querySelector('.customFilterDropdown.show');

        if (targetElement && dropdownMenu) {
            targetElement.appendChild(dropdownMenu);
            dropdownMenu.style.display = 'none';
        }
    },

    autoCompleteFocusOut(e) {
        var targetElement = e.target.closest('.filter_dropdown');
        targetElement = targetElement.querySelector('.ks_input_filter_options');
        let ariaControls = targetElement.getAttribute('aria-controls');
        let dropdownMenu = document.getElementById(ariaControls);

        if (targetElement && dropdownMenu) {
            targetElement.parentElement.appendChild(dropdownMenu);
            dropdownMenu.style.display = 'none';
        }
    },

});