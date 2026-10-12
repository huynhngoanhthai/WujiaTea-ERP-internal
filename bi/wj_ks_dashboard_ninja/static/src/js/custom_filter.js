/** @odoo-module **/

import { Component, useState, onWillStart, useRef } from "@odoo/owl";
import { getDomainDisplayedOperators } from "@web/core/domain_selector/domain_selector_operator_editor";
import { Domain } from "@web/core/domain";
import { useService, useBus, useChildRef } from "@web/core/utils/hooks";
// Odoo 19: treeFromDomain/domainFromTree moved out of condition_tree
import { treeFromDomain } from "@web/core/tree_editor/tree_from_domain";
import { domainFromTree } from "@web/core/tree_editor/domain_from_tree";
import { Dropdown } from "@web/core/dropdown/dropdown";
import { DropdownItem } from "@web/core/dropdown/dropdown_item";
import { getOperatorLabel } from "@web/core/tree_editor/tree_editor_operator_editor";
import { getDefaultValue, getValueEditorInfo } from "@web/core/tree_editor/tree_editor_value_editors";
import { getExpressionDisplayedOperators } from "@web/core/expression_editor/expression_editor_operator_editor";
import { KsDropDown } from "@wj_ks_dashboard_ninja/js/ks_dropdown";
import { _t } from "@web/core/l10n/translation";
import { disambiguate } from "@web/core/tree_editor/utils";
import { condition, connector } from "@web/core/tree_editor/condition_tree";
import { rpc } from "@web/core/network/rpc";
import { user } from "@web/core/user";


export class CustomFilter extends Component{
    static props = {
        domain: { type: String, optional: true },
        update: { type: Function, optional: true },
        options: { type: Object, optional: true },
        filter_info: { type: Object, optional: true },
    };
    static defaultProps = {
        update: () => {},
        domain: `[]`,
        filter_info: {},
    };

    setup(){
        this.notification = useService("notification");
        // Odoo 19: useLoadFieldInfo/useGetTreeDescription hooks removed — use services
        this.fieldService = useService("field");
        this.treeProcessor = useService("tree_processor");
        this.loadFieldInfo = (resModel, path) => this.fieldService.loadFieldInfo(resModel, path);
        this.getDomainTreeDescription = (resModel, tree) =>
            this.treeProcessor.getDomainTreeDescription(resModel, tree);
        this.state = useState({
            filtersRowList: []
        });
        this.customDomainFacets = {}
        this.operatorRef = useRef("operatorRef");
        this.filterRef = useRef("filterRef");
        this.dn_operatorRef = useChildRef();

        this.domain = this.props.domain
//        this.tree = treeFromDomain(this.domain);
        this.filter_info = this.props.filter_info

        onWillStart(() => this.willStart());
        useBus(this.env.bus, "Clear:Custom-Filter", (ev) => this.clearRows(ev.detail));
        useBus(this.env.bus, "Clear:Custom-Filter-Facets", (ev) => this.clearFacets(ev.detail));
    }

    willStart(){
        const filters_list = Object.values(this.props.filter_info)
        this.loadFieldDefs_and_Labels(filters_list);
        const defaultOperator = getDomainDisplayedOperators(filters_list[0])[0]
        this.defaultFilterRowObject = {
            id: filters_list[0].id,
            operator: defaultOperator,
            value: getDefaultValue(filters_list[0], defaultOperator),
        }
        this.state.filtersRowList.push(this.defaultFilterRowObject);
    }

    rowFilter(filter_id){
        let filter = this.props.filter_info[filter_id]
        return filter.name + ' ( ' + filter.model_name + ' ) '
    }

    rowOperator(row_index){
        return getOperatorLabel(this.state.filtersRowList[row_index].operator)
    }

    // Remove Data from python , we load field defs here
     async loadFieldDefs_and_Labels(filters_list) {
        const promises = [];
        const filter_labels = [];
        const fieldDefs = {};
        for (const filter of filters_list) {
            filter_labels.push({ filter_name: filter.name + ' ( ' + filter.model_name + ' ) ', filter_id: filter.id})
            if (typeof filter.field_name === "string") {
                promises.push(
                    this.loadFieldInfo(filter.model, filter.field_name).then(({ fieldDef }) => {
                        fieldDefs[filter.id] = fieldDef;
                    })
                );
            }
        }
        await Promise.all(promises);
        this.fieldDefs = fieldDefs;
        this.filterLabels = filter_labels
    }

    getOperatorInfo(filter_id) {
        const fieldDef = this.fieldDefs[filter_id];
        const operators = getDomainDisplayedOperators(fieldDef);
        const operatorList = operators.map((operator) => ({
                                operator: operator,
                                label: getOperatorLabel(operator),
                            }));
        return operatorList;
    }

    getValueInfo(filter_row) {
        const fieldDef = this.fieldDefs?.[filter_row.id] || this.filter_info[filter_row.id];
        let valueInfo = getValueEditorInfo(fieldDef, filter_row.operator);
        if(valueInfo.component?.name === 'Select' || valueInfo.component?.name === 'List'){
            const options = fieldDef.selection || [];
            const getOption = (value) => options.find(([v]) => v === value) || null;
            const params = {}
            const KsSelectComponent = {
                component: KsDropDown,
                extractProps: ({ value, update }) => ({
                    value,
                    update,
                    options,
                    addBlankOption: params.addBlankOption,
                }),
                isSupported: (value) => Boolean(getOption(value)),
                defaultValue: () => options[0]?.[0] ?? false,
                stringify: (value, disambiguate) => {
                    const option = getOption(value);
                    return option ? option[1] : disambiguate ? formatValue(value) : String(value);
                },
                message: _t("Value not in selection"),
            };

            if(valueInfo.component?.name === 'List'){
                let editorInfo = getValueEditorInfo(fieldDef, "=", {
                    addBlankOption: true,
                    startEmpty: true,
                });
                if(editorInfo.component?.name === 'Select'){
                    editorInfo = KsSelectComponent
                    valueInfo.extractProps = ({ value, update }) => {
                        if (!disambiguate(value)) {
                            const { stringify } = editorInfo;
                            editorInfo.stringify = (val) => stringify(val, false);
                        }
                        return {
                            value,
                            update,
                            editorInfo,
                        };
                    }
                }
                return valueInfo;
            }
            return KsSelectComponent;
        }
        return valueInfo;
    }

    getDefaultOperator(fieldDef) {
        return getExpressionDisplayedOperators(fieldDef)[0];
    }

    async getDomainTreeDescriptionCallback(resModel, tree) {
        let description = await this.getDomainTreeDescription(resModel, tree);
        return description;
    }

    onUpdateFilter(filter_id, row_index){
        const fieldDef = this.fieldDefs[filter_id];
        const operator = this.getDefaultOperator(fieldDef)
        this.state.filtersRowList[row_index] = {
            id: filter_id,
            operator: operator,
            value: getDefaultValue(fieldDef, operator),
        }
    }

    onUpdateValue(row_index, updated_value){
        this.state.filtersRowList[row_index].value = updated_value;
    }

    onUpdateOperator(operator, row_index){
        const fieldDef = this.fieldDefs[this.state.filtersRowList[row_index].id];
        this.state.filtersRowList[row_index].operator = operator;
        this.state.filtersRowList[row_index].value = getDefaultValue(fieldDef, operator, this.state.filtersRowList[row_index].value);
    }


    clearRows(ev){
        const node = JSON.parse(JSON.stringify(this.defaultFilterRowObject));
        this.state.filtersRowList = [node];
    }

    clearFacets(ev){
        this.customDomainFacets = {}
    }

    async applyFilters(ev) {
        const filterRowList = this.state.filtersRowList;
        const models_domain = {};

        for (const filter_row of filterRowList) {
            const filter = this.filter_info[filter_row.id];
            const { model, field_name, model_name } = filter;
            const {operator, value} = filter_row

            if (!models_domain[model]) {
                models_domain[model] = {
                    domain: connector('|'),
                    label: 'Custom Filter',
                    model_name
                };
            }
            models_domain[model].domain.children.push(condition(field_name, operator, value));
        }

        await Promise.all(
            Object.entries(models_domain).map(async ([model, model_domain]) => {
                model_domain.label = await this.getDomainTreeDescription(model, model_domain.domain);
                model_domain.domain = new Domain(domainFromTree(model_domain.domain)).toList();
            })
        );

        for(const [model, model_domain] of Object.entries(models_domain)){
            this.customDomainFacets[model] = this.customDomainFacets[model] || {labels: [] , model_name: model_domain.model_name}
            this.customDomainFacets[model].labels.push(model_domain.label)
            let domain;
            let isValid;
            try {
                const evalContext = { ...user.context };
                domain = new Domain(model_domain.domain).toList(evalContext);
            } catch {
                isValid = false;
            }
            if (isValid === undefined) {
                isValid = await rpc("/web/domain/validate", {
                    model: model,
                    domain,
                });
            }
            if (!isValid) {
                this.notification.add(_t("Domain is invalid. Please correct it"), {
                    type: "danger",
                });
                return;
            }
        }

        this.clearRows();
        this.props.update(models_domain);
    }

    onRemoveFacet(ev){
        ev.stopPropagation;
        let modelFacetIndex = ev.currentTarget.dataset.facetIndex
        let search_section = ev.currentTarget.parentElement.parentElement;
        let model = search_section.getAttribute('ksmodel');
        let index = Array.from(search_section.parentElement.children);
        index = index.indexOf(search_section)
        let modelFacets = this.customDomainFacets[model];
        modelFacets?.labels.splice(index, 1);
        if(!modelFacets?.labels.length)  delete this.customDomainFacets[model];
        this.__owl__.parent.component?.ksOnRemoveFilterFromSearchPanel(ev);
    }


    addFilterRow(ev){
        const node = JSON.parse(JSON.stringify(this.defaultFilterRowObject));
        this.state.filtersRowList.push(node);
    }

    deleteRow(row_index){
        this.state.filtersRowList.splice(row_index, 1);
    }
}

CustomFilter.template = "wj_ks_dashboard_ninja.custom_filter"

CustomFilter.components = { Dropdown, DropdownItem }
