/** @odoo-module **/

import { _t } from "@web/core/l10n/translation";
import { Component,onRendered,  onWillStart, useState, onPatched     ,onMounted, onWillRender, useRef, useEffect,onWillUnmount  } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService, useBus } from "@web/core/utils/hooks";
import { loadJS,loadCSS } from "@web/core/assets";
import { localization } from "@web/core/l10n/localization";
import { user } from "@web/core/user";
import { download } from "@web/core/network/download";
import { WebClient } from "@web/webclient/webclient";
import { ConfirmationDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { patch } from "@web/core/utils/patch";
import { isBrowserChrome, isMobileOS } from "@web/core/browser/feature_detection";
import { FormViewDialog} from '@web/views/view_dialogs/form_view_dialog';
import { renderToElement } from "@web/core/utils/render";
import { globalfunction } from '@wj_ks_dashboard_ninja/js/ks_global_functions'
import { Ksdashboardtile } from '@wj_ks_dashboard_ninja/components/ks_dashboard_tile_view/ks_dashboard_tile';
import { Ksdashboardlistview } from '@wj_ks_dashboard_ninja/components/ks_dashboard_list_view/ks_dashboard_list';
import { Ksdashboardtodo } from '@wj_ks_dashboard_ninja/components/ks_dashboard_to_do_item/ks_dashboard_to_do';
import { Ksdashboardkpiview } from '@wj_ks_dashboard_ninja/components/ks_dashboard_kpi_view/ks_dashboard_kpi';
import { Ksdashboardgraph } from '@wj_ks_dashboard_ninja/components/ks_dashboard_graphs/ks_dashboard_graphs';
import { CustomFilter } from '@wj_ks_dashboard_ninja/js/custom_filter';
import { DateTimePicker } from "@web/core/datetime/datetime_picker";
import { DateTimeInput } from "@web/core/datetime/datetime_input";
const { DateTime } = luxon;
import {formatDate,formatDateTime} from "@web/core/l10n/dates";
import {parseDateTime,parseDate,} from "@web/core/l10n/dates";
import { dnNavBarAddClasses } from "@wj_ks_dashboard_ninja/js/dnNavBarExtend";
import { rpc } from "@web/core/network/rpc";



export class KsDashboardNinja extends Component {

    setup() {
        this.actionService = useService("action");
        this.uiService = useService("ui");
        this.dialogService = useService("dialog");
        this.notification = useService("notification");
        this.dialogService = useService("dialog");
        this.header =  useRef("ks_dashboard_header");
        this.footer =  useRef("ks_dashboard_footer");
        this.main_body = useRef("ks_main_body");
        this.reload_menu_option = {
            reload:this.props.action.context.ks_reload_menu,
            menu_id: this.props.action.context.ks_menu_id
        };
        this.ks_mode = 'active';
        this.action_manager = parent;
//      this.controllerID = params.controllerID;
        this.name = "ks_dashboard";
        this.ksIsDashboardManager = false;
        this.ksDashboardEditMode = false;
        this.ksNewDashboardName = false;
        this.recent_searches = useState({ value : []})
        this.file_type_magic_word = {
            '/': 'jpg',
            'R': 'gif',
            'i': 'png',
            'P': 'svg+xml',
        };
        this.ksAllowItemClick = true;

        //Dn Filters Iitialization

        this.date_format = localization.dateFormat
        //        this.date_format = this.date_format.replace(/\bYY\b/g, "YYYY");
        this.datetime_format = localization.dateTimeFormat
        //            this.is_dateFilter_rendered = false;
        this.ks_date_filter_data;

        // Adding date filter selection options in dictionary format : {'id':{'days':1,'text':"Text to show"}}
        this.ks_date_filter_selections = {
            'l_none': _t('Date Filter'),
            'l_day': _t('Today'),
            't_week': _t('This Week'),
            'td_week': _t('Week To Date'),
            't_month': _t('This Month'),
            'td_month': _t('Month to Date'),
            't_quarter': _t('This Quarter'),
            'td_quarter': _t('Quarter to Date'),
            't_year': _t('This Year'),
            'td_year': _t('Year to Date'),
            'n_day': _t('Next Day'),
            'n_week': _t('Next Week'),
            'n_month': _t('Next Month'),
            'n_quarter': _t('Next Quarter'),
            'n_year': _t('Next Year'),
            'ls_day': _t('Last Day'),
            'ls_week': _t('Last Week'),
            'ls_month': _t('Last Month'),
            'ls_quarter': _t('Last Quarter'),
            'ls_year': _t('Last Year'),
            'l_week': _t('Last 7 days'),
            'l_month': _t('Last 30 days'),
            'l_quarter': _t('Last 90 days'),
            'l_year': _t('Last 365 days'),
            'ls_past_until_now': _t('Past Till Now'),
            'ls_pastwithout_now': _t('Past Excluding Today'),
            'n_future_starting_now': _t('Future Starting Now'),
            'n_futurestarting_tomorrow': _t('Future Starting Tomorrow'),
            'l_custom': _t('Custom Filter'),
        };
        // To make sure date filter show date in specific order.
        this.ks_date_filter_selection_order = ['l_day', 't_week', 't_month', 't_quarter','t_year',
            'td_week','td_month','td_quarter', 'td_year','n_day','n_week', 'n_month', 'n_quarter', 'n_year',
            'ls_day','ls_week', 'ls_month', 'ls_quarter', 'ls_year', 'l_week', 'l_month', 'l_quarter', 'l_year',
            'ls_past_until_now', 'ls_pastwithout_now','n_future_starting_now', 'n_futurestarting_tomorrow',
            'l_custom'
        ];

        this.ks_dashboard_id = this.props.action.params.ks_dashboard_id;
        this.isReloadOnFirstCreate = this.props.action?.params?.isReloadOnFirstCreate ? true : false
        this.on_dialog = false;
        this.on_dialog = this.props.action.params.on_dialog ? true : false;
        this.explain_ai_whole = true;
//        this.explain_ai_whole = this.props.action.params.explain_ai_whole ? true : false;
        this.explain_ai_whole = this.props.action.params.explain_ai_whole === undefined ? true : false;



        this.gridstack_options = {
            staticGrid:true,
            float: false,
            cellHeight: 68,
            styleInHead : true,
//          disableOneColumnMode: true,
        };
        if (isMobileOS()) {
            this.gridstack_options.disableOneColumnMode = false
        }
        this.gridstackConfig = {};
        this.grid = true;
        this.chartMeasure = {};
        this.chart_container = {};
        this.list_container = {};
        this.state = useState({
            ks_dashboard_name: '',
            ks_multi_layout: false,
            ks_dash_name: '',
            ks_dashboard_manager :false,
            date_selection_data: {},
            date_selection_order :[],
            ks_show_create_layout_option : true,
            ks_show_layout :false,
            ks_selected_board_id:false,
            ks_child_boards:false,
            ks_dashboard_data:{},
            ks_dn_pre_defined_filters:[],
            ks_dashboard_item_length:0,
            ks_dashboard_items:[],
            update:false,
            ksDateFilterSelection :false,
            pre_defined_filter :{},
            ksDateFilterStartDate: DateTime.now(),
            ksDateFilterEndDate:DateTime.now(),
            stateToggle: false,
            dialog_header: true

        })
        this.ksChartColorOptions = ['default', 'cool', 'warm', 'neon'];
        this.ksDateFilterSelection = false;
        this.ksDateFilterStartDate = false;
        this.ksDateFilterEndDate = false;
        this.ksUpdateDashboard = {};
        document.innerHTML+= '<meta name="viewport" content="width=device-width, initial-scale=1, user-scalable=no">'
        if(this.props.action.context.ks_reload_menu){
            this.trigger_up('reload_menu_data', { keep_open: true, scroll_to_bottom: true});
        }
        var context = {
            ksDateFilterSelection: this.ksDateFilterSelection,
            ksDateFilterStartDate: self.ksDateFilterStartDate,
            ksDateFilterEndDate: self.ksDateFilterEndDate,
        }
        this.dn_state = {}
        this.dn_state['user_context']=context
        this.isFavFilter = false;
        this.activeFavFilterName = "FavouriteFilter"
        this.isPredefined = false;
        this.isModelVisePredefined = {};
        onWillStart(this.willStart);
        onWillRender(this.dashboard_mount);
        this.filter_facets_count = 0
        onMounted(() => {
            if (!this.ks_dashboard_data.ks_ai_explain_dash){
                this.grid_initiate();
            }
//            var filter_date_data = null
            var filter_date_data = this.getObjectFromCookie('FilterDateData' + this.ks_dashboard_id);

            if (filter_date_data != null){
                this.header.el.querySelector('.ks_date_filter_selected')?.classList.remove('ks_date_filter_selected');
                document.getElementById('ks_date_filter_selection').textContent = this.ks_date_filter_selections[filter_date_data];


                var element_selected = document.getElementById(filter_date_data);
                if(element_selected){
                    element_selected.classList.add('ks_date_filter_selected')
                }
                this.state.ksDateFilterSelection = filter_date_data;
                if(filter_date_data==='l_custom'){
                    var custom_range = this.getObjectFromCookie('custom_range' + this.ks_dashboard_id);
                    if(custom_range){
                        try {
                            this.state.ksDateFilterStartDate = parseDateTime(custom_range['start_date'], self.datetime_format)
                            this.state.ksDateFilterEndDate = parseDateTime(custom_range['end_date'], self.datetime_format)
                        } catch (error) {
                            this.eraseCookie('custom_range' + this.ks_dashboard_id);
                        }
                    }
                    this.header.el?.querySelector('.ks_date_input_fields')?.classList.remove("ks_hide")
                    document.querySelector('.ks_date_filter_dropdown')?.classList.add("ks_btn_first_child_radius");
                }

            }

            if (this.getObjectFromCookie('FilterDateData' + this.ks_dashboard_id) || this.getObjectFromCookie('FilterOrderData' + this.ks_dashboard_id)){
                var pre_defined_filters = document.querySelectorAll('.dn_filter_click_event_selector');
                var filters_applied = this.ks_dashboard_data.ks_dashboard_domain_data;
                var pre_defined_filters_data = this.ks_dashboard_data.ks_dashboard_pre_domain_filter;
                const elementsArray = document.querySelectorAll('.dn_filter_click_event_selector');
                if(Object.keys(filters_applied).length > 0){
                    elementsArray.forEach(element  => {
                  for (const key in pre_defined_filters_data) {
                    if(key === element.dataset.filterId){
                        for(const key1 in filters_applied){
                            for(const domain_index in filters_applied[key1].ks_domain_index_data){
                                if(filters_applied[key1].ks_domain_index_data[domain_index].categ){
                                    if(filters_applied[key1].ks_domain_index_data[domain_index].categ === pre_defined_filters_data[key].categ){
                                        if (filters_applied[key1].ks_domain_index_data[domain_index].label.includes(pre_defined_filters_data[key].name)) {
                                          if(!element.classList.contains('dn_dynamic_filter_selected')){
                                            element.classList.add('dn_dynamic_filter_selected')
                                          }
                                        } else {
                                           if(element.classList.contains('dn_dynamic_filter_selected')){
                                             element.classList.remove('dn_dynamic_filter_selected')
                                             element.classList.remove('global-active')
                                           }
                                        }
                                    }
                                }
                            }
                        }
                    }
                    }
                });
                }
                else{
                    elementsArray.forEach(element  => {
                      if(element.classList.contains('dn_dynamic_filter_selected')){
                        element.classList.remove('dn_dynamic_filter_selected')
                        element.classList.remove('global-active')
                      }

                    });
                }

                this._onKsApplyDateFilter();
            }
            document.querySelector('.table-custom')?.addEventListener('show.bs.dropdown', this.filterTableDropdownShow);
            document.querySelector('.table-custom')?.addEventListener('hide.bs.dropdown', this.filterTableDropdownHide);
            document.querySelector('.modal-footer button')?.classList.add("d-none")
            let filterFacetCountTag = this.header.el?.querySelector('.filters-amount')
            if(filterFacetCountTag)
                filterFacetCountTag.textContent = this.header.el?.querySelectorAll('.selcted-opt').length
        });

        onRendered(()=>{

            if(!document.body.classList.contains('ks_body_class'))
                    dnNavBarAddClasses();

            if(this.env.services.menu.getCurrentApp()?.xmlid !== "wj_ks_dashboard_ninja.board_menu_root")
                this.env.services.menu.reload()


            if(this.isReloadOnFirstCreate){
                this.isReloadOnFirstCreate = false;
                if(this.props.action.params && this.props.action.params.isReloadOnFirstCreate)
                    this.props.action.params.isReloadOnFirstCreate = false
                this.env.services.menu.reload();
                this.notification.add(_t('Your Personal Dashboard has been successfully created'),{
//                    title:_t("New Dashboard"),
                    type: 'success'
                });
            }
        })
        onPatched(() => {
            let filterFacetCountTag = this.header.el.querySelector('.filters-amount')
            if(filterFacetCountTag)
                filterFacetCountTag.textContent = this.header.el?.querySelectorAll('.selcted-opt').length
        })

        useBus(this.env.bus, "GET:ParamsForItemFetch", (ev) => this.ksGetParamsForItemFetch(ev.detail));
    }

    willStart(){
        var self = this;
        var def;
        var storedData = this.getObjectFromCookie('FilterOrderData' + self.ks_dashboard_id);
        var storedPredefinedData = this.getObjectFromCookie('PredefinedData' + self.ks_dashboard_id);
        if (this.reload_menu_option.reload && this.reload_menu_option.menu_id) {
            def = this.getParent().actionService.ksDnReloadMenu(this.reload_menu_option.menu_id);
        }
        // amCharts libs are loaded eagerly in web.assets_backend (form-preview widgets need am5 too)
        return Promise.all([def]).then(function() {
            return self.ks_fetch_data().then(function(){
                return self.ks_fetch_items_data().then(function(){
                    if(storedData != null ){
                           self.ks_dashboard_data.ks_dashboard_domain_data = storedData;
                            Object.keys(self.ks_dashboard_data.ks_dashboard_domain_data).forEach?.((model) => {
                                if(self.ks_dashboard_data.ks_dashboard_domain_data[model].ks_domain_index_data.length != (self.ks_dashboard_data.ks_dashboard_domain_data[model].ks_domain_index_data?.filter?.((x)=>{return x.isCustomFilter}).length)){
                                    self.isModelVisePredefined[model] = true;
                                }
                            })
                            self.isPredefined = true;


                            //  FIXME: It can be optimised , no need to be store predefined data in cookies , it must be resolved during making of compnenets for filters

                            if(storedPredefinedData){
                                var filters_to_update = Object.values(storedPredefinedData).filter((x)=>{return x.active === true});
                                filters_to_update.forEach?.( (pre_defined_filter) => {
                                    self.ks_dashboard_data.ks_dashboard_pre_domain_filter[pre_defined_filter.id].active = true;
                                })
                            }
                        }
                    });
            });
        });
    }

    dashboardImageUpdate(){
        let image_element = document.querySelector('.ks_dashboard_main_content');
        if(!document.querySelector('.ks_dashboard_main_content')?.childNodes.length){
            image_element = document.querySelector('.o_view_nocontent');
        }
        let self = this;
        this.env.services.ui.block();
//        this.uiService.block();
        let canvas = html2canvas(image_element,  {
                          height: image_element.clientHeight + 186,
                          width: image_element.clientWidth,
                          windowWidth: image_element.scrollWidth,
                          windowHeight: image_element.scrollHeight,
                          scrollY: 0,
                          scrollX: 0,
                          x: image_element.scrollLeft,
                          y: image_element.scrollTop,
                        }).then((canvas) => {
                                    let image = canvas.toDataURL("image/png");
                                    rpc("/web/dataset/call_kw/ks_dashboard_ninja.board/saveImage",{
                                                        model: 'ks_dashboard_ninja.board',
                                                        method: 'save_dashboard_image',
                                                        args: [[self.ks_dashboard_id]],
                                                        kwargs:{image: image},
                                                    }).then((result) => {
                                                            this.uiService.unblock();
                                                    });
        });
        this.notification.add(_t('Dashboard image updated successfully!'),{
                            title:_t("Dashboard Image Refreshed"),
                            type: 'success',
                        });
    }

    grid_initiate(){
        var self=this;
        const ks_element = this.main_body.el;
        var gridstackContainer = document.querySelector(".grid-stack");
        if(gridstackContainer){
            this.grid = GridStack.init(this.gridstack_options,gridstackContainer);
            var item = self.ksSortItems(self.ks_dashboard_data.ks_item_data)
            if(this.ks_dashboard_data.ks_gridstack_config){
                this.gridstackConfig = JSON.parse(this.ks_dashboard_data.ks_gridstack_config);
            }
            for (var i = 0; i < item.length; i++) {
                var graphs = ['ks_scatter_chart','ks_bar_chart', 'ks_horizontalBar_chart', 'ks_line_chart', 'ks_area_chart', 'ks_doughnut_chart','ks_polarArea_chart','ks_pie_chart','ks_flower_view', 'ks_radar_view','ks_radialBar_chart','ks_map_view','ks_funnel_chart','ks_bullet_chart', 'ks_to_do', 'ks_list_view']
                var ks_preview = document.getElementById(item[i].id)
                if (ks_preview && !this.ks_dashboard_data.ks_ai_explain_dash) {
                    if (item[i].id in self.gridstackConfig) {
                        var min_width = graphs.includes(item[i].ks_dashboard_item_type)? 3:2
                         self.grid.addWidget(ks_preview, {x:self.gridstackConfig[item[i].id].x, y:self.gridstackConfig[item[i].id].y, w:self.gridstackConfig[item[i].id].w, h: self.gridstackConfig[item[i].id].h, autoPosition:false, minW:min_width, maxW:null, minH:3, maxH:null, id:item[i].id});
                    } else if ( graphs.includes(item[i].ks_dashboard_item_type)) {
                         self.grid.addWidget(ks_preview, {x:0, y:0, w:5, h:6,autoPosition:true,minW:4,maxW:null,minH:3,maxH:null, id :item[i].id});
                    }else{
                        self.grid.addWidget(ks_preview, {x:0, y:0, w:2, h:2,autoPosition:true,minW:2,maxW:null,minH:3,maxH:2,id:item[i].id});
                    }
                }else{
                if (item[i].id in self.gridstackConfig) {
                        var min_width = graphs.includes(item[i].ks_dashboard_item_type)? 3:2
                         self.grid.addWidget(ks_preview, {x:self.gridstackConfig[item[i].id].x, y:self.gridstackConfig[item[i].id].y, w:12, h: 6, autoPosition:false, minW:min_width, maxW:null, minH:2, maxH:null, id:item[i].id});
                    } else  {
                         self.grid.addWidget(ks_preview, {x:0, y:0, w:12, h:6,autoPosition:true,minW:4,maxW:null,minH:3,maxH:null, id :item[i].id});
                    }
                   Object.values(ks_element.querySelectorAll(".ks_dashboard_item_button_container")).map((item) => {
                        item?.classList.add('d-none')
                        item?.classList.remove('d-md-flex')
                   })
                   Object.values(ks_element.querySelectorAll(".ks_pager_name")).map((item) => {
                        item?.classList.add('d-none')
                   })


                }
            }
            this.grid.setStatic(true);
        }
        this.ksRenderDashboard();
        // Events //

        Object.values(ks_element.querySelectorAll(".ks_duplicate_item")).map((item) => { item.addEventListener('click', this.onKsDuplicateItemClick.bind(this))})
        Object.values(ks_element.querySelectorAll(".ks_move_item")).map((item) => { item.addEventListener('click', this.onKsMoveItemClick.bind(this))})
        Object.values(ks_element.querySelectorAll(".ks_dashboard_item_delete")).map((item) => { item.addEventListener('click', this._onKsDeleteItemClick.bind(this))})
        Object.values(ks_element.querySelectorAll(".ks_chart_xls_csv_export")).map((item) => { item.addEventListener('click', this.ksChartExportXlsCsv.bind(this))})
        Object.values(ks_element.querySelectorAll(".ks_chart_pdf_export")).map((item) => { item.addEventListener('click', this.ksChartExportPdf.bind(this))})
        Object.values(ks_element.querySelectorAll(".ks_chart_image_export")).map((item) => { item.addEventListener('click', this.ksChartExportimage.bind(this))})
        Object.values(ks_element.querySelectorAll(".ks_chart_json_export")).map((item) => { item.addEventListener('click', this.ksItemExportJson.bind(this))})
        Object.values(ks_element.querySelectorAll(".ks_dashboard_quick_edit_action_popup")).map((item) => { item.addEventListener('click', this.onEditItemTypeClick.bind(this))})
        Object.values(ks_element.querySelectorAll(".ks_dashboard_item_customize")).map((item) => { item.addEventListener('click', this.onEditItemTypeClick.bind(this))})
        Object.values(ks_element.querySelectorAll(".ks_dashboard_menu_container")).map((item) => { item.addEventListener('click', this.stoppropagation.bind(this))})
        Object.values(ks_element.querySelectorAll(".ks_item_description")).map((item) => { item.addEventListener('click', this.stoppropagation.bind(this))})
        Object.values(ks_element.querySelectorAll(".ks_item_click")).map((item) => { item.addEventListener('click', this._onKsItemClick.bind(this))})
        Object.values(ks_element.querySelectorAll(".ks_dashboard_item_action")).map((item) => { item.addEventListener('click', this.ks_dashboard_item_action.bind(this))})
        Object.values(ks_element.querySelectorAll(".ks_dashboard_item_chart_info")).map((item) => { item.addEventListener('click', this.onChartMoreInfoClick.bind(this))})
//        document.querySelector('.table-custom')?.addEventListener('show.bs.dropdown', this.filterTableDropdownShow);
//        document.querySelector('.table-custom')?.addEventListener('hide.bs.dropdown', this.filterTableDropdownHide);
        document.querySelector('.predefined-filters')?.addEventListener('hide.bs.dropdown', this.predefinedSearchFocusout.bind(this));

//        Object.values((self.header.el).querySelectorAll(".ks_custom_filter_field_selector")).map((item) => { item.addEventListener('change', this.ksOnCustomFilterFieldSelect.bind(this))})


    }

    getContext() {
        var self = this;
        var context = {
            ksDateFilterSelection: self.ksDateFilterSelection,
            ksDateFilterStartDate: self.ksDateFilterStartDate,
            ksDateFilterEndDate: self.ksDateFilterEndDate,
        }
        if(self.dn_state['user_context']['ksDateFilterSelection'] !== undefined && self.ksDateFilterSelection !== 'l_none'){
            context = self.dn_state['user_context']
        }
        // Odoo 19: company service removed — user.context already carries allowed_company_ids
        var ks_new_obj = {...user.context}
        return Object.assign(context, ks_new_obj);
    }

    renderListViewData(item) {
        var list_view_data = JSON.parse(item.ks_list_view_data);
        if (item.ks_list_view_type === "ungrouped" && list_view_data) {
            if (list_view_data.date_index) {
                var index_data = list_view_data.date_index;
                for (var i = 0; i < index_data.length; i++) {
                    for (var j = 0; j < list_view_data.data_rows.length; j++) {
                        var index = index_data[i]
                        var date = list_view_data.data_rows[j]["data"][index]
                        if (date) {
                            if (list_view_data.fields_type[index] === 'date'){
                                list_view_data.data_rows[j]["data"][index] = luxon.DateTime.fromJSDate(new Date(date + " UTC")).toFormat?.(this.date_format);
                            }else{
                                list_view_data.data_rows[j]["data"][index] = luxon.DateTime.fromJSDate(new Date(date + " UTC")).toFormat?.(this.datetime_format);
                            }
                        }else{
//                            list_view_data.data_rows[j]["data"][index] = "";
                        }
                    }
                }
            }
        }
        return JSON.stringify(list_view_data);
    }

    ks_fetch_data(){
        var self = this;
        return rpc("/web/dataset/call_kw/ks_dashboard_ninja.board/ks_fetch_dashboard_data",{
            model: 'ks_dashboard_ninja.board',
            method: 'ks_fetch_dashboard_data',
            args: [self.ks_dashboard_id],
            kwargs : {context:self.getContext()},
//            context: self.getContext()
        }).then(function(result) {
        //                result = self.normalize_dn_data(result);
            self.ks_dashboard_data = result;
            self.ks_dashboard_data.ks_ai_explain_dash = self.props.action.params.explainWithAi ? true : false
            self.ks_dashboard_data['ks_dashboard_id'] = self.props.action.params.ks_dashboard_id
            self.ks_dashboard_data['context'] = self.getContext()
            self.ks_dashboard_data['ks_ai_dashboard'] = false
            self.ks_favourite_filters = JSON.parse(JSON.stringify(self.ks_dashboard_data.ks_dashboard_favourite_filter))
            if(self.dn_state['domain_data'] != undefined){
                Object.values(self.ks_dashboard_data.ks_dashboard_pre_domain_filter).map((x)=>{
                    if(self.dn_state['domain_data'][x['model']] != undefined){
                        if(self.dn_state['domain_data'][x['model']]['ks_domain_index_data'][0]['label'].indexOf(x['name']) ==-1){
                            self.ks_dashboard_data.ks_dashboard_pre_domain_filter[x['id']].active = false;
                        }
                    }
                    else{
                        self.ks_dashboard_data.ks_dashboard_pre_domain_filter[x['id']].active = false;
                    }
                })
            }
        });
    }

    dashboard_mount(){
        var self = this;
//        var items = self.ksSortItems(self.ks_dashboard_data.ks_item_data)
        var items = Object.values(self.ks_dashboard_data.ks_item_data)
        self.state.ks_dashboard_items = items
        self.ks_dashboard_data['context'] = self.getContext();
//        dnNavBarAddClasses();
    }

    ks_fetch_items_data(){
        var self = this;
        var items_promises = []

        self.ks_dashboard_data.ks_dashboard_items_ids.forEach(function(item_id){
            items_promises.push(rpc("/web/dataset/call_kw/ks_dashboard_ninja.board/ks_fetch_item",{
                model: "ks_dashboard_ninja.board",
                method: "ks_fetch_item",
                args : [[item_id], self.ks_dashboard_id, self.ksGetParamsForItemFetch(item_id)],
                kwargs:{context:self.getContext()}
            }).then(function(result){
                if(result[item_id].ks_list_view_data){
                    result[item_id].ks_list_view_data = self.renderListViewData(result[item_id])
                }
                self.ks_dashboard_data.ks_item_data[item_id] = result[item_id];
                const ks_default_end_time = result[item_id].ks_default_end_time;
                if (ks_default_end_time) {
                    self.state.ksDateFilterEndDate = DateTime.now().endOf('day');
                } else {
                    self.state.ksDateFilterEndDate = DateTime.now();
                 }
                self.state.ks_show_create_layout_option = (Object.keys(self.ks_dashboard_data.ks_item_data).length > 0) && self.ks_dashboard_data.ks_dashboard_manager
            }));
        });
        self.state.ks_dashboard_name = self.ks_dashboard_data.name,
        self.state.ks_multi_layout = self.ks_dashboard_data.multi_layouts,
        self.state.ks_dash_name = self.ks_dashboard_data.name,
        self.state.ks_dashboard_manager = self.ks_dashboard_data.ks_dashboard_manager,
        self.state.date_selection_data = self.ks_date_filter_selections,
        self.state.date_selection_order = self.ks_date_filter_selection_order,
        self.state.ks_show_layout = self.ks_dashboard_data.ks_dashboard_manager && self.ks_dashboard_data.ks_child_boards && true,
        self.state.ks_selected_board_id = self.ks_dashboard_data.ks_selected_board_id,
        self.state.ks_child_boards = self.ks_dashboard_data.ks_child_boards,
        self.state.ks_dashboard_data = self.ks_dashboard_data,
        self.state.ks_dn_pre_defined_filters = Object.values(self.ks_dashboard_data.ks_dashboard_pre_domain_filter).sort(function(a, b){return a.sequence - b.sequence}),
        self.state.ks_dashboard_item_length = self.ks_dashboard_data.ks_dashboard_items_ids.length
        self.state.update = false
        self.state.ksDateFilterSelection = self.state.ksDateFilterSelection == false ? 'none' : self.state.ksDateFilterSelection,
        self.state.pre_defined_filter = {}
        self.state.custom_filter = {}
        var custom_range = this.getObjectFromCookie('custom_range' + this.ks_dashboard_id);
        if(custom_range){
            try {
                this.state.ksDateFilterStartDate = parseDateTime(custom_range['start_date'], self.datetime_format)
                this.state.ksDateFilterEndDate = parseDateTime(custom_range['end_date'], self.datetime_format)
            } catch (error) {
                this.eraseCookie('custom_range' + this.ks_dashboard_id);
                self.state.ksDateFilterStartDate = DateTime.now()
                self.state.ksDateFilterEndDate = DateTime.now()
            }
        }else{
            self.state.ksDateFilterStartDate = DateTime.now()
            self.state.ksDateFilterEndDate = DateTime.now()
        }
        self.state.ks_user_name = user.name
        return Promise.all(items_promises)

    }


    ksGetParamsForItemFetch(){
        return {};
    }

    ksRenderDashboard(){
        var self = this;
        if (self.ks_dashboard_data.ks_child_boards) self.ks_dashboard_data.name = this.ks_dashboard_data.ks_child_boards[self.ks_dashboard_data.ks_selected_board_id][0];
        if (!isMobileOS()) {
            self.header.el.classList.add("ks_dashboard_header_sticky")
        }
        if (Object.keys(self.ks_dashboard_data.ks_item_data).length===0){
            self.header.el.querySelector('.ks_dashboard_link')?.classList.add("d-none");
            self.header.el.querySelector('.ks_dashboard_edit_layout')?.classList.add("ks_hide");
        }
        if(!self.state.ks_dashboard_manager){
            self.header.el.querySelector('#ks_dashboard_title')?.classList.add("ks_user")
        }
      self.ksRenderDashboardMainContent();
    }

    ksRenderDashboardMainContent(){
        var self = this;
        if (isMobileOS() && document.querySelector('#ks_dn_layout_button')?.firstElementChild) {
            document.querySelector('.ks_am_element')?.append(document.querySelector('#ks_dn_layout_button')?.firstElementChild.innerText)
            self.header.el.querySelector("#ks_dn_layout_button")?.classList.add("ks_hide");
        }
        if (Object.keys(self.ks_dashboard_data.ks_item_data)?.length){
        // todo  implement below mentioned function
            self._renderDateFilterDatePicker();
            self.header.el.querySelector('.ks_dashboard_link')?.classList.remove("ks_hide");
        } else if (!Object.keys(self.ks_dashboard_data.ks_item_data)?.length) {
            self.header.el.querySelector('.ks_dashboard_link')?.classList.add("ks_hide");
        }
    }

    _renderDateFilterDatePicker() {
        var self = this;
        self.header.el.querySelector(".ks_dashboard_link").classList.remove("ks_hide");
        self._KsGetDateValues();
    }

    loadDashboardData(date = false){
        var self = this;
        self.header.el.querySelector(".apply-dashboard-date-filter")?.classList.remove("ks_hide");
        self.header.el.querySelector(".clear-dashboard-date-filter")?.classList.remove("ks_hide");
        self.header.el.querySelector(".ks_dashboard_top_settings")?.classList.add("d-none");
        self.header.el.querySelector("#favFilterMain")?.classList.add("ks_hide");
        self.header.el.querySelector(".filters_section")?.classList.add("ks_hide");
    }

    _KsGetDateValues() {
            var self = this;
            //Setting Date Filter Selected Option in Date Filter DropDown Menu
            var date_filter_selected = self.ks_dashboard_data.ks_date_filter_selection;
            if (self.ksDateFilterSelection == 'l_none'){
                    var date_filter_selected = self.ksDateFilterSelection;
            }
            self.header.el.querySelector('#' + date_filter_selected)?.classList.add("ks_date_filter_selected","global-filter");
            self.header.el.querySelector('#ks_date_filter_selection').textContent = (self.ks_date_filter_selections[date_filter_selected]);

            if (self.ks_dashboard_data.ks_date_filter_selection === 'l_custom') {
                var ks_end_date = self.ks_dashboard_data.ks_dashboard_end_date;
                var ks_start_date = self.ks_dashboard_data.ks_dashboard_start_date;
                 var start_date = parseDateTime(ks_start_date, self.datetime_format)
                  var end_date = parseDateTime(ks_end_date, self.datetime_format)
                self.state.ksDateFilterStartDate = start_date
                self.state.ksDateFilterEndDate = end_date

                self.header.el.querySelector('.ks_date_input_fields')?.classList.remove("ks_hide");
                self.header.el.querySelector('.ks_date_filter_dropdown')?.classList.add("ks_btn_first_child_radius");
            } else if (self.ks_dashboard_data.ks_date_filter_selection !== 'l_custom') {
                self.header.el.querySelector('.ks_date_input_fields')?.classList.add("ks_hide");
            }
        }

    _ksOnDateFilterMenuSelect(e) {
        if (e.target.id !== 'ks_date_selector_container') {
            var self = this;
            document.querySelectorAll('.ks_date_filter_selected')?.forEach((itm) => {
                itm?.classList.remove("ks_date_filter_selected", "global-active");
            });

            e.target?.parentElement?.classList.add("ks_date_filter_selected", "global-active");

            document.getElementById('ks_date_filter_selection').textContent = self.ks_date_filter_selections[e.target.parentElement.id];

            self.header.el.querySelector('.custom-date-range-selector')?.classList.add("dn_hide");

            if (e.target.parentElement.id !== "l_custom") {
                self.header.el.querySelector(".ks_dashboard_top_settings")?.classList.remove("d-none");
                self.header.el.querySelector("#favFilterMain")?.classList.remove("ks_hide");
                self.header.el.querySelector(".filters_section")?.classList.remove("ks_hide");

                if (e.target?.parentElement.id === "l_none") {
                    self._onKsClearDateValues(true);
                } else {
                    self._onKsApplyDateFilter();
                }

                document.querySelectorAll('.ks_date_input_fields')?.forEach((field) => {
                    field?.classList.add("ks_hide");
                });
                document.querySelector('.ks_date_filter_dropdown')?.classList.remove("ks_btn_first_child_radius");

            } else if (e.target.parentElement.id === "l_custom") {
                self.header.el.querySelector(".ks_dashboard_top_settings")?.classList.add("d-none");
                self.header.el.querySelector("#favFilterMain")?.classList.add("ks_hide");
                self.header.el.querySelector(".filters_section")?.classList.add("ks_hide");

                self.header.el.querySelector('.custom_date_filter_section')?.classList.remove("ks_hide");
                var startDatePicker = document.getElementById("ks_start_date_picker");
                var endDatePicker = document.getElementById("ks_end_date_picker");
                if(startDatePicker) {
                    startDatePicker.value = null;
                    startDatePicker.classList.remove("ks_hide");
                }

                if(endDatePicker){
                    endDatePicker.value = null;
                    endDatePicker.classList.remove("ks_hide");
                }


                document.querySelectorAll('.ks_date_input_fields')?.forEach((field) => {
                    field.classList.remove("ks_hide");
                });
                document.querySelector('.ks_date_filter_dropdown')?.classList.add("ks_btn_first_child_radius");
            }

           if(self.state.ksDateFilterSelection === 'l_none'){
                this.eraseCookie('FilterDateData' + self.ks_dashboard_id);
           }else if(self.state.ksDateFilterSelection != 'none'){
                this.setObjectInCookie('FilterDateData' + self.ks_dashboard_id, self.state.ksDateFilterSelection, 1);
           }
        }
    }

    _onKsApplyDateFilter(e) {
        var self = this;
        var start_date = self.header.el.querySelector('#ks_btn_middle_child').value;
        var end_date = self.header.el.querySelector('#ks_btn_last_child').value;
        self.header.el.querySelector('.ks_dashboard_item_drill_up')?.classList.add("d-none")
        this.header.el.querySelectorAll('.custom-date-range-selector').forEach(function(element) {
            element.classList.remove('dn_hide');
        });

        if (start_date === "Invalid date") {
            this.notification.add(_t("Invalid Date is given in Start Date."), {
                type: "warning",
            });
        } else if (end_date === "Invalid date") {
            this.notification.add(_t("Invalid Date is given in End Date."), {
                type: "warning",
            });
        } else if (self.header.el.querySelector('.ks_date_filter_selected')?.getAttribute('id') !== "l_custom") {
            self.ksDateFilterSelection = self.header.el?.querySelector('.ks_date_filter_selected')?.getAttribute('id');
            var res = {};
            for (const [key, value] of Object.entries(self.ks_dashboard_data.ks_item_data)) {
                if (value.ks_dashboard_item_type != "ks_to_do") {
                    res[key] = value;
                }
            }
            var context = {
                ksDateFilterSelection: self.ksDateFilterSelection,
                ksDateFilterStartDate: self.ksDateFilterStartDate,
                ksDateFilterEndDate: self.ksDateFilterEndDate,
            }
            self.dn_state['user_context']=context
                self.header.el.querySelector("#favFilterMain")?.classList.remove("ks_hide");
                self.header.el.querySelector(".filters_section")?.classList.remove("ks_hide");
                self.header.el.querySelector(".ks_dashboard_top_settings")?.classList.remove("d-none");
                self.header.el.querySelectorAll('.custom_date_filter_section').forEach(function(element) {
                    element.classList.add('ks_hide');
                });

                self.header.el.querySelectorAll('.ks_date_input_fields').forEach(function(element) {
                    element.classList.add('ks_hide');
                });

                self.header.el.querySelectorAll('.custom-date-range-selector').forEach(function(element) {
                    element.classList.add('dn_hide');
                });


                self.state.ksDateFilterSelection = self.header.el?.querySelector('.ks_date_filter_selected')?.getAttribute('id') || "none";
                self.state.pre_defined_filter = {}
                self.state.custom_filter = {}
        } else {
            if (start_date && end_date) {
                if (parseDateTime(start_date,self.datetime_format) <= parseDateTime(end_date, self.datetime_format)) {
                    this.setObjectInCookie('custom_range' + self.ks_dashboard_id, {'start_date': start_date, 'end_date':end_date}, 1);
                    self.state.ksDateFilterStartDate = parseDateTime(start_date,self.datetime_format);
                    self.state.ksDateFilterEndDate = parseDateTime(end_date,self.datetime_format);
                    var start_date = formatDateTime(parseDateTime(start_date, self.datetime_format), { format: "yyyy-MM-dd HH:mm:ss"})
                    var end_date = formatDateTime(parseDateTime(end_date, self.datetime_format), { format: "yyyy-MM-dd HH:mm:ss" })
                    if (start_date === "Invalid date" || end_date === "Invalid date"){
                        this.notification.add(_t("Invalid Date"), {
                            type: "warning",
                        });
                    }else{
                        self.ksDateFilterSelection = self.header.el.querySelector('.ks_date_filter_selected')?.getAttribute('id');
                        self.ksDateFilterStartDate = start_date;
                        self.ksDateFilterEndDate = end_date;
                        var res = {};
                        for (const [key, value] of Object.entries(self.ks_dashboard_data.ks_item_data)) {
                            if (value.ks_dashboard_item_type != "ks_to_do") {
                                res[key] = value;
                            }
                        }
                        var context = {
                            ksDateFilterSelection: self.ksDateFilterSelection,
                            ksDateFilterStartDate: self.ksDateFilterStartDate,
                            ksDateFilterEndDate: self.ksDateFilterEndDate,
                        }
                        self.dn_state['user_context']=context
                            self.header.el.querySelector(".apply-dashboard-date-filter")?.classList.remove("ks_hide");
                            self.header.el.querySelector("#favFilterMain")?.classList.remove("ks_hide");
                            self.header.el.querySelector(".filters_section")?.classList.remove("ks_hide");
                            self.header.el.querySelector(".ks_dashboard_top_settings")?.classList.remove("d-none");
                            self.header.el.querySelectorAll('.custom_date_filter_section').forEach(function(element) {
                                element.classList.add('ks_hide');
                            });
                            self.header.el.querySelectorAll('.ks_date_input_fields').forEach(function(element) {
                                element.classList.add('ks_hide');
                            });

                            self.state.ksDateFilterSelection = self.header.el?.querySelector('.ks_date_filter_selected')?.getAttribute('id');
                            if(self.state.ksDateFilterSelection != 'none'){
                                this.setObjectInCookie('FilterDateData' + self.ks_dashboard_id, self.state.ksDateFilterSelection, 1);
                            }
                            self.state.pre_defined_filter = {}
                            self.state.custom_filter = {}
                   }
                } else {
                    this.notification.add(_t("Start date should be less than end date."), {
                        type: "warning",
                    });
                }
            } else {
                this.notification.add(_t("Please enter start date and end date."), {
                    type: "warning",
                });
            }
        }
    }

    setCookie(name, value, days) {
        var expires = "";
        if (days) {
            var date = new Date();
            date.setTime(date.getTime() + (days*24*60*60*1000));
            expires = "; expires=" + date.toUTCString();
        }
        document.cookie = name + "=" + (value || "") + expires + "; path=/";
    }

     setObjectInCookie(name, object, days) {
        var jsonString = JSON.stringify(object);
        this.setCookie(name, jsonString, days);
    }


    getCookie(name) {
        var nameEQ = name + "=";
        var ca = document.cookie.split(';');
        for (var i = 0; i < ca.length; i++) {
            var c = ca[i];
            while (c.charAt(0) == ' ') c = c.substring(1, c.length);
            if (c.indexOf(nameEQ) == 0) return c.substring(nameEQ.length, c.length);
        }
        return null;
    }

    getObjectFromCookie(name) {
        var jsonString = this.getCookie(name);
        return jsonString ? JSON.parse(jsonString) : null;
    }

    _onKsClearDateValues(ks_l_none=false) {
        var self = this;
        self.ksDateFilterSelection = 'l_none';
        self.ksDateFilterStartDate = false;
        self.ksDateFilterEndDate = false;
        var res = {};
        for (const [key, value] of Object.entries(self.ks_dashboard_data.ks_item_data)) {
            if (value.ks_dashboard_item_type != "ks_to_do") {
                res[key] = value;
            }
        }
        var context = {
            ksDateFilterSelection: self.ksDateFilterSelection,
            ksDateFilterStartDate: self.ksDateFilterStartDate,
            ksDateFilterEndDate: self.ksDateFilterEndDate,
        }
        self.dn_state['user_context']=context
        self.header.el.querySelector('.ks_date_input_fields')?.classList.add("ks_hide");
        self.header.el.querySelector('.ks_date_filter_dropdown')?.classList.remove("ks_btn_first_child_radius");
        self.state.ksDateFilterSelection = 'l_none';
        self.state.pre_defined_filter = {};
        self.state.custom_filter = {}
        self.header.el.querySelector(".ks_dashboard_top_settings.new-features")?.classList.remove("d-none");
        self.header.el.querySelector("#favFilterMain")?.classList.remove("ks_hide");
        self.header.el.querySelector(".filters_section")?.classList.remove("ks_hide");
        self.header.el.querySelectorAll('.custom_date_filter_section').forEach(function(element) {
            element.classList.add('ks_hide');
        });

    }

    ksSortItems(ks_item_data) {
        var items = []
        var self = this;
        var item_data = Object.assign({}, ks_item_data);
        if (self.ks_dashboard_data.ks_gridstack_config) {
            self.gridstackConfig = JSON.parse(self.ks_dashboard_data.ks_gridstack_config);
            var a = Object.values(self.gridstackConfig);
            var b = Object.keys(self.gridstackConfig);
            for (var i = 0; i < a.length; i++) {
                a[i]['id'] = b[i];
            }
            a.sort(function(a, b) {
                return (35 * a.y + a.x) - (35 * b.y + b.x);
            });
            for (var i = 0; i < a.length; i++) {
                if (item_data[a[i]['id']]) {
                    items.push(item_data[a[i]['id']]);
                    delete item_data[a[i]['id']];
                }
            }
        }

        return items.concat(Object.values(item_data));
    }

    onChartMoreInfoClick(e) {
            var self = this;
            var item_id = e.currentTarget.dataset.itemId;
            var item_data = self.ks_dashboard_data.ks_item_data[item_id];
            var groupBy = item_data.ks_chart_groupby_type === 'date_type' ? item_data.ks_chart_relation_groupby_name + ':' + item_data.ks_chart_date_groupby : item_data.ks_chart_relation_groupby_name;
            var domain = JSON.parse(item_data.ks_chart_data).previous_domain

            if (item_data.ks_show_records) {
                if (item_data.action) {

                    if (!item_data.ks_is_client_action){
                        var action = Object.assign({}, item_data.action);
                        if (action.view_mode.includes('tree')) action.view_mode = action.view_mode.replace('tree', 'list');
                            for (var i = 0; i < action.views.length; i++) action.views[i][1].includes('tree') ? action.views[i][1] = action.views[i][1].replace('tree', 'list') : action.views[i][1];
                                action['domain'] = item_data.ks_domain || [];
                                action['search_view_id'] = [action.search_view_id, 'search']
                        }else{
                            var action = Object.assign({}, item_data.action[0]);
                            if (action.params){
                                action.params.default_active_id || 'mailbox_inbox';
                                }else{
                                    action.params = {
                                    'default_active_id': 'mailbox_inbox'
                                    }
                                    action.context = {}
                                    action.context.params = {
                                    'active_model': false
                                    };
                                }
                            }
                } else {
                    var action = {
                        name: _t(item_data.name),
                        type: 'ir.actions.act_window',
                        res_model: item_data.ks_model_name,
                        domain: domain || [],
                        context: {
                            'group_by': groupBy ? groupBy:false ,
                        },
                        views: [
                            [false, 'list'],
                            [false, 'form']
                        ],
                        view_mode: 'list',
                        target: 'current',
                    }
                }
                self.actionService.doAction(action, {
                    on_reverse_breadcrumb: self.on_reverse_breadcrumb,
                });
            }
        }


    onKsDuplicateItemClick(e) {
        var self = this;
        var ks_item_id = e.target.closest('.ks_dashboarditem_id').getAttribute('id');
        var ks_selected  = e.target.closest('.ks_dashboarditem_id').querySelector('.ks_dashboard_select')
        var dashboard_id = ks_selected.value;
        var selected_index = ks_selected.selectedIndex;
        var dashboard_name = ks_selected.options[selected_index].innerText
        rpc("/web/dataset/call_kw/ks_dashboard_ninja.item/copy",{
            model: 'ks_dashboard_ninja.item',
            method: 'copy',
            args: [parseInt(ks_item_id), {
                'ks_dashboard_ninja_board_id': parseInt(dashboard_id)
            }],
            kwargs:{},
        }).then(function(result) {
            self.notification.add(_t('Selected item is duplicated to ' + dashboard_name + ' .'),{
                title:_t("Item Duplicated"),
                type: 'success',
            });
                            var js_id = self.actionService.currentController.jsId
                            self.actionService.restore(js_id)

            })
            e.stopPropagation()

    }

    onKsMoveItemClick(e) {
        var self = this;
        var ks_item_id = e.target.closest('.ks_dashboarditem_id').getAttribute('id');
        var ks_selected  = e.target.closest('.ks_dashboarditem_id').querySelector('.ks_dashboard_select')
        var dashboard_id = ks_selected.value;
        var selected_index = ks_selected.selectedIndex;
        var dashboard_name = ks_selected.options[selected_index].innerText;
        rpc("/web/dataset/call_kw/ks_dashboard_ninja.item/write",{
            model: 'ks_dashboard_ninja.item',
            method: 'write',
            args: [parseInt(ks_item_id), {
                'ks_dashboard_ninja_board_id': parseInt(dashboard_id)
            }],
            kwargs:{}
        }).then(function(result) {
            self.notification.add(_t('Selected item is moved to ' + dashboard_name + ' .'),{
                title:_t("Item Moved"),
                type: 'success',
            });

                    var js_id = self.actionService.currentController.jsId
                    self.actionService.restore(js_id)

        });
        e.stopPropagation()
    }

     _onKsItemClick(e){
        var self = this;
        //  To Handle only allow item to open when not clicking on item
        if (self.ksAllowItemClick) {
            e.preventDefault();
            if(self.ks_mode === 'edit')   return;
            if (e.target.title != "Customize Item") {
                var item_id = parseInt(e.currentTarget.firstElementChild.id);
                var item_data = self.ks_dashboard_data.ks_item_data[item_id];
                if(["excel", "csv"].includes(item_data.item_data_source)) return;
                if (item_data && item_data.ks_show_records && item_data.ks_data_calculation_type != 'query') {

                    if (item_data.action) {
                        if (!item_data.ks_is_client_action){
                            var action = Object.assign({}, item_data.action);
                            if (action.view_mode.includes('tree')) action.view_mode = action.view_mode.replace('tree', 'list');
                            for (var i = 0; i < action.views.length; i++) action.views[i][1].includes('tree') ? action.views[i][1] = action.views[i][1].replace('tree', 'list') : action.views[i][1];
                            action['domain'] = item_data.ks_domain || [];
                            action['search_view_id'] = [action.search_view_id, 'search']
                        }else{
                            var action = Object.assign({}, item_data.action[0]);
                            if (action.params){
                                action.params.default_active_id || 'mailbox_inbox';
                                }else{
                                    action.params = {
                                    'default_active_id': 'mailbox_inbox'
                                    }
                                    action.context = {}
                                    action.context.params = {
                                    'active_model': false
                                    };
                                }
                        }

                    } else {
                        var action = {
                            name: _t(item_data.name),
                            type: 'ir.actions.act_window',
                            res_model: item_data.ks_model_name,
                            domain: item_data.ks_domain || "[]",
                            views: [
                                [false, 'list'],
                                [false, 'form']
                            ],
                            view_mode: 'list',
                            target: 'current',
                        }
                    }

                    if (item_data.ks_is_client_action){
                        self.actionService.doAction(action,{})
                    }else{
                        self.actionService.doAction(action, {
                            on_reverse_breadcrumb: self.on_reverse_breadcrumb,
                        });
                    }
                }
            }
        } else {
            self.ksAllowItemClick = true;
        }
    }
    ks_dashboard_item_action(e){
        this.ksAllowItemClick = false;
    }

    _onKsDeleteItemClick(e) {
        var self = this;
        var item = e.target.closest(".grid-stack-item")
        var id = parseInt(e.target.closest(".grid-stack-item").getAttribute("id"));
        self.ks_delete_item(id, item);
        e.stopPropagation();
    }

    ks_delete_item(id, item) {
        var self = this;
        this.dialogService.add(ConfirmationDialog, {
        body: _t("Are you sure that you want to remove this item?"),
        confirmLabel: _t("Delete Item"),
        title: _t("Delete Dashboard Item"),
        confirm: () => {
            rpc("/web/dataset/call_kw/ks_dashboard_ninja.item/unlink",{
                model: 'ks_dashboard_ninja.item',
                method: 'unlink',
                args: [id],
                kwargs:{}
            }).then(function(result) {
                        // Clean Item Remove Process.
                delete self.ks_dashboard_data.ks_item_data[id];
                self.grid.removeWidget(item);

                if (Object.keys(self.ks_dashboard_data.ks_item_data).length > 0) {
                    self._ksSaveCurrentLayout();
                }

                var js_id = self.actionService.currentController.jsId
                self.actionService.restore(js_id)

                });

            },
            cancel: () => {},
            });
        }
        removeitems(){
            var self = this;
            var ks_items  = Object.values((self.main_body.el).querySelectorAll(".grid-stack-item"));
            ks_items.forEach((item) =>{
             self.grid.removeWidget(item);
             })
            }

    _ksSetCurrentLayoutClick(){
        var self = this;
        this.ks_dashboard_data.ks_selected_board_id = self.header.el.querySelector("#ks_dashboard_layout_dropdown_container").querySelector(".ks_layout_selected").dataset.ks_layout_id
        self.header.el.querySelector(".ks_dashboard_top_menu-new .ks_dashboard_top_settings.new-features")?.classList.remove("ks_hide")
        self.header.el.querySelector(".ks_dashboard_top_menu-new .ks_am_content_element")?.classList.remove("ks_hide")
        this.header.el.querySelectorAll('.ks_dashboard_top_settings.new-features').forEach(function(element) {
            element.classList.remove('dn_hide');
        });
        self.header.el.querySelector(".ks_dashboard_layout_edit_mode_settings")?.classList.add("ks_hide")
//            $('#ks_dashboard_title_input').val(this.ks_dashboard_data.ks_child_boards[this.ks_dashboard_data.ks_selected_board_id][0]);
        this.ks_dashboard_data.name = this.ks_dashboard_data.ks_child_boards[this.ks_dashboard_data.ks_selected_board_id][0];

        rpc("/web/dataset/call_kw/ks_dashboard_ninja.board/update_child_board",{
            model: 'ks_dashboard_ninja.board',
            method: 'update_child_board',
            args: ['update', self.ks_dashboard_id, {
                "ks_selected_board_id": this.ks_dashboard_data.ks_selected_board_id,
            }],
            kwargs:{},
        }).then(function(result){
            window.location.reload();
        });
    }

    _ksSetDiscardCurrentLayoutClick(){
        this.ksOnLayoutSelection(this.ks_dashboard_data.ks_selected_board_id);
        this.header.el.querySelector(".ks_dashboard_top_menu-new .ks_dashboard_top_settings.new-features")?.classList.remove("ks_hide");
        this.header.el.querySelector(".ks_dashboard_top_menu-new .ks_am_content_element")?.classList.remove("ks_hide");
        this.header.el.querySelector(".ks_dashboard_layout_edit_mode_settings")?.classList.add("ks_hide");
        this.header.el.querySelector(".ks_dashboard_top_menu-new .ks_dashboard_edit_layout")?.classList.remove("ks_hide");
        this.header.el.querySelectorAll('.ks_dashboard_top_settings.new-features').forEach(function(element) {
            element.classList.remove('dn_hide');
        });

    }

    _ksSaveCurrentLayout() {
        var self = this;
        var grid_config = self.ks_get_current_gridstack_config();
        var model = 'ks_dashboard_ninja.child_board';
        var rec_id = self.ks_dashboard_data.ks_gridstack_config_id;
        self.ks_dashboard_data.ks_gridstack_config = JSON.stringify(grid_config);
        if(this.ks_dashboard_data.ks_selected_board_id && this.ks_dashboard_data.ks_child_boards){
            this.ks_dashboard_data.ks_child_boards[this.ks_dashboard_data.ks_selected_board_id][1] = JSON.stringify(grid_config);
            if (this.ks_dashboard_data.ks_selected_board_id !== 'ks_default'){
                rec_id = parseInt(this.ks_dashboard_data.ks_selected_board_id)
            }
        }
        if (!isMobileOS()) {
            rpc("/web/dataset/call_kw/ks_dashboard_ninja.child_board/write",{
                model: model,
                method: 'write',
                args: [rec_id, {
                    "ks_gridstack_config": JSON.stringify(grid_config)
                }],
                kwargs:{},
            })
        }
    }

    ks_get_current_gridstack_config(){
        var self = this;
        if (document.querySelector('.grid-stack') && document.querySelector('.grid-stack').gridstack){
            var items = document.querySelector('.grid-stack').gridstack.el.gridstack.engine.nodes;
        }
        var grid_config = {}

        if (items){
            for (var i = 0; i < items.length; i++) {
                grid_config[items[i].id] = {
                    'x': items[i].x,
                    'y': items[i].y,
                    'w': items[i].w,
                    'h': items[i].h,
                }
            }
        }
        return grid_config;
    }

        ////////////////////////////// Export functions ////////////////////////////////////////////
    async ksChartExportXlsCsv(e) {
        var chart_id = e.currentTarget.dataset.chartId;
        var name = this.ks_dashboard_data.ks_item_data[chart_id].name;
        var context = this.getContext();
        if (this.ks_dashboard_data.ks_item_data[chart_id].ks_dashboard_item_type === 'ks_list_view'){
        var params = this.ksGetParamsForItemFetch(parseInt(chart_id));
        var data = {
            "header": name,
            "chart_data": typeof this.ks_dashboard_data.ks_item_data[chart_id].ks_list_view_data === 'string' ? this.ks_dashboard_data.ks_item_data[chart_id].ks_list_view_data : JSON.stringify(this.ks_dashboard_data.ks_item_data[chart_id].ks_list_view_data),
            "ks_item_id": chart_id,
            "ks_export_boolean": true,
            "context": context,
            'params':params,
        }
        }else{
            var data = {
                "header": name,
                "chart_data": this.ks_dashboard_data.ks_item_data[chart_id].ks_chart_data,

            }
        }
        this.uiService.block();
        try {
            await download({
                url: '/wj_ks_dashboard_ninja/export/' + e.currentTarget.dataset.format,
                data: {
                    data: JSON.stringify(data)
                },
            });
        } catch (error) {
            this.notification.add(_t('Export failed'), { type: 'danger' });
            throw error;
        } finally {
            this.uiService.unblock();
        }
    }

    ksChartExportPdf (e){
        var self = this;
        var chart_id = e.currentTarget.dataset.chartId;
        var name = this.ks_dashboard_data.ks_item_data[chart_id].name;
        var base64_image
        base64_image = e.target.closest(".grid-stack-item").querySelector(".ks_chart_card_body")
        var ks_height = base64_image.offsetHeight
        html2canvas(base64_image, {useCORS: true, allowTaint: false}).then(function(canvas){
            var ks_image = canvas.toDataURL("image/png");
            var ks_image_def = {
            content: [{
                    image: ks_image,
                    width: 500,
                    height: ks_height > 750 ? 750 : ks_height,
                    }],
            images: {
                bee: ks_image
            }
        };
        pdfMake.createPdf(ks_image_def).download(name + '.pdf');
        })

    }
    async updateBookmark(ev){
        ev.currentTarget.classList.toggle('active');
        let updatedBookmarks = await rpc("/web/dataset/call_kw/ks_dashboard_ninja.board/update_bookmarks",{
                                model: 'ks_dashboard_ninja.board',
                                method: 'update_bookmarks',
                                args: [[this.ks_dashboard_id]],
                                kwargs:{},
                            });
        updatedBookmarks = updatedBookmarks[1]
        if(updatedBookmarks)
            this.notification.add(_t('Dashboard added to your bookmarks'),{
                            title:_t("Bookmark Added"),
                            type: 'success',
                        });
        else
            this.notification.add(_t('Dashboard removed from your bookmarks'),{
                            title:_t("Bookmark Removed"),
                            type: 'success',
                        });
    }
    ksChartExportimage(e){
        var self = this;
        var chart_id = e.currentTarget.dataset.chartId;
        var name = this.ks_dashboard_data.ks_item_data[chart_id].name;
        var base64_image
        base64_image = e.target.closest(".grid-stack-item").querySelector(".ks_chart_card_body")
        html2canvas(base64_image,{useCORS: true, allowTaint: false}).then(function(canvas){
            var ks_image = canvas.toDataURL("image/png");
            const link = document.createElement('a');
            link.href =  ks_image;
            link.download = name + 'png'
            document.body.appendChild(link);
            link.click()
            document.body.removeChild(link);
        })

    }
    async ksItemExportJson(e) {
        e.stopPropagation();
        var itemId = e.target.closest('.grid-stack-item').getAttribute("id");
        var name = this.ks_dashboard_data.ks_item_data[itemId].name;
        var data = {
            'header': name,
            item_id: itemId,
        }
        this.uiService.block();
        try {
            await download({
                url: '/wj_ks_dashboard_ninja/export/item_json',
                data: {
                    data: JSON.stringify(data)
                },
            });
        } catch (error) {
            this.notification.add(_t('Export failed'), { type: 'danger' });
            throw error;
        } finally {
            this.uiService.unblock();
        }
    }

    ksOnDashboardExportClick(ev){
        ev.preventDefault();
        var self= this;
        var dashboard_id = JSON.stringify(this.ks_dashboard_id);
            rpc("/web/dataset/call_kw/ks_dashboard_ninja.board/ks_dashboard_export", {
            model: 'ks_dashboard_ninja.board',
            method: "ks_dashboard_export",
            args: [dashboard_id],
            kwargs: {dashboard_id: dashboard_id}
        }).then(function(result) {
            var name = "dashboard_ninja";
            var data = {
                "header": name,
                "dashboard_data":
                result,
            }
            download({
            data: {
                data:JSON.stringify(data)
            },
                url: '/wj_ks_dashboard_ninja/export/dashboard_json',
            });
        });
    }

    stoppropagation(ev){
        ev.stopPropagation();
        this.ksAllowItemClick = false;
    }

    ksOnDashboardImportClick(ev){
        ev.preventDefault();
        var self = this;
        var dashboard_id = this.ks_dashboard_id;
        rpc("/web/dataset/call_kw/ks_dashboard_ninja.board/ks_open_import", {
            model: 'ks_dashboard_ninja.board',
            method: 'ks_open_import',
            args: [dashboard_id],
            kwargs: {
                dashboard_id: dashboard_id
            }
        }).then((result)=>{
             self.actionService.doAction(result)
        });
    }

    _ksOnDnLayoutMenuSelect(ev){
        var selected_layout_id = ev.currentTarget.dataset.ks_layout_id;
        this.ksOnLayoutSelection(selected_layout_id);
    }

    ksOnLayoutSelection(layout_id){
        var self = this;
        var selected_layout_name = this.ks_dashboard_data.ks_child_boards[layout_id][0];
        var selected_layout_grid_config = this.ks_dashboard_data.ks_child_boards[layout_id][1];
        this.gridstackConfig = JSON.parse(selected_layout_grid_config);
        Object.entries(this.gridstackConfig).forEach((x,y)=>{
            self.grid.update(document.getElementById(x[0]),{ x:x[1]['x'], y:x[1]['y'], w:x[1]['w'], h:x[1]['h'],autoPosition:false});
        });


//            this.ks_dashboard_data.ks_selected_board_id = layout_id;
        self.header.el.querySelector("#ks_dashboard_layout_dropdown_container .ks_layout_selected")?.classList.remove("ks_layout_selected");
        self.header.el.querySelector("li.ks_dashboard_layout_event[data-ks_layout_id='"+ layout_id + "']")?.classList.add('ks_layout_selected');
        self.header.el.querySelector("#ks_dn_layout_button span:first-child").textContent = selected_layout_name;
        self.header.el.querySelector(".ks_dashboard_top_menu-new .ks_dashboard_edit_layout")?.classList.add("ks_hide");
        self.header.el.querySelector(".ks_dashboard_top_menu-new .ks_am_content_element")?.classList.add("ks_hide");
        this.header.el.querySelectorAll('.ks_dashboard_top_settings.new-features').forEach(function(element) {
            element.classList.add('dn_hide');
        });

        self.header.el.querySelector(".ks_dashboard_layout_edit_mode_settings")?.classList.remove("ks_hide");
    }

    _onKsSaveLayoutClick(){
        this.grid.setStatic(true)
        var self = this;
        //        Have  to save dashboard here
        self.header.el.querySelector(".ks_dashboard_top_settings.new-features")?.classList.remove("d-none");
        self.header.el.querySelector("#favFilterMain")?.classList.remove("ks_hide");
        self.header.el.querySelector(".filters_section")?.classList.remove("ks_hide");
        var dashboard_title = self.header.el.querySelector('#ks_dashboard_title_input').value;
        self.header.el.querySelectorAll('.hide-in-edit').forEach(function(element) {
            element.classList.remove('dn_hide');
        });

        self.header.el.querySelectorAll('.hide-in-edit.custom-date-range-selector').forEach(function(element) {
            element.classList.add('dn_hide');
        });

        if (dashboard_title != false && dashboard_title != 0 && dashboard_title !== self.ks_dashboard_data.name) {
            self.ks_dashboard_data.name = dashboard_title;
            var model = 'ks_dashboard_ninja.board';
            var rec_id = self.ks_dashboard_id;

            if(this.ks_dashboard_data.ks_selected_board_id && this.ks_dashboard_data.ks_child_boards){
                this.ks_dashboard_data.ks_child_boards[this.ks_dashboard_data.ks_selected_board_id][0] = dashboard_title;
                if (this.ks_dashboard_data.ks_selected_board_id !== 'ks_default'){
                    model = 'ks_dashboard_ninja.child_board';
                    rec_id = this.ks_dashboard_data.ks_selected_board_id;
                }
            }
            var new_model = `web/dataset/call_kw/${model}/write`
            rpc(new_model,{
                model: model,
                method: 'write',
                args: [rec_id, {
                    'name': dashboard_title
                }],
                kwargs : {},
            })
        }
        if (this.ks_dashboard_data.ks_item_data) self._ksSaveCurrentLayout();
        self._ksRenderActiveMode();
    }

    _onKsCancelLayoutClick(){
        var self = this;
        //        render page again

        var js_id = self.actionService.currentController.jsId
        self.actionService.restore(js_id)

    }

    _onKsCreateLayoutClick() {
        var self = this;
        self.grid.setStatic(true)
        self.header.el.querySelectorAll('.hide-in-edit').forEach(function(element) {
            element.classList.remove('dn_hide');
        });

        var dashboard_title = self.header.el.querySelector('#ks_dashboard_title_input').value;
        if (dashboard_title ==="") {
            self.call('notification', 'notify', {
                message: "Dashboard Name is required to save as New Layout.",
                type: 'warning',
            });
        } else{
            if (!self.ks_dashboard_data.ks_child_boards){
                self.ks_dashboard_data.ks_child_boards = {
                    'ks_default': [this.ks_dashboard_data.name, self.ks_dashboard_data.ks_gridstack_config]
                }
            }
            this.ks_dashboard_data.name = dashboard_title;

            var grid_config = self.ks_get_current_gridstack_config();
            rpc("/web/dataset/call_kw/ks_dashboard_ninja.board/update_child_board",{
                model: 'ks_dashboard_ninja.board',
                method: 'update_child_board',
                args: ['create', self.ks_dashboard_id, {
                    "ks_gridstack_config": JSON.stringify(grid_config),
                    "ks_dashboard_ninja_id": self.ks_dashboard_id,
                    "name": dashboard_title,
                    "ks_active": true,
                    "company_id": self.ks_dashboard_data.ks_company_id,
                }],
                kwargs : {},
            }).then(function(res_id){
                self.ks_update_child_board_value(dashboard_title, res_id, grid_config),
                self._ksRenderActiveMode();
                window.location.reload();
            });
        }
    }
    ks_update_child_board_value(dashboard_title, res_id, grid_config){
        var self = this;
        var child_board_id = res_id.toString();
        self.ks_dashboard_data.ks_selected_board_id = child_board_id;
        var update_data = {};
        update_data[child_board_id] = [dashboard_title, JSON.stringify(grid_config)];
        self.ks_dashboard_data.ks_child_boards = Object.assign(update_data,self.ks_dashboard_data.ks_child_boards);
    }

    _ksRenderActiveMode(){
        var self = this
        self.ks_mode = 'active';

       if (self.grid && document.querySelector('.grid-stack').gridstack) {
            document.querySelector('.grid-stack').gridstack.disable();
       }

        if (self.ks_dashboard_data.ks_child_boards) {
            var layout_container = renderToElement('ks_dn_layout_container_new', {
                ks_selected_board_id: self.ks_dashboard_data.ks_selected_board_id,
                ks_child_boards: self.ks_dashboard_data.ks_child_boards,
                ks_multi_layout: self.ks_dashboard_data.multi_layouts,
                ks_dash_name: self.ks_dashboard_data.name,
                self:self,
            });
            self.header.el.querySelector('#ks_dashboard_title .ks_am_element')?.replaceWith(layout_container)
            self.header.el.querySelector('#ks_dashboard_title_label')?.replaceWith(layout_container)
        }
        if (self.header.el.querySelector('#ks_dashboard_title_label')){
            self.header.el.querySelector('#ks_dashboard_title_label').textContent = self.ks_dashboard_data.name
        }

        self.header.el.querySelector('.ks_am_element')?.classList.remove("ks_hide");
        self.header.el.querySelector('.ks_em_element')?.classList.add("ks_hide");
        self.header.el.querySelector('.ks_dashboard_print_pdf')?.classList.remove("ks_hide");
        if (self.ks_dashboard_data.ks_item_data) self.header.el.querySelector('.ks_am_content_element')?.classList.remove("ks_hide");

        self.header.el.querySelector('.ks_item_not_click')?.classList.add('ks_item_click')
        self.header.el.querySelector('.ks_item_not_click')?.classList.remove('ks_item_not_click');
        self.header.el.querySelector('.ks_dashboard_item')?.classList.add('ks_dashboard_item_header_hover')
        self.header.el.querySelector('.ks_dashboard_item_header')?.classList.add('ks_dashboard_item_header_hover')

        self.header.el.querySelector('.ks_dashboard_item_l2')?.classList.add('ks_dashboard_item_header_hover')
        self.header.el.querySelector('.ks_dashboard_item_header_l2')?.classList.add('ks_dashboard_item_header_hover')

        //      For layout 5
        self.header.el.querySelector('.ks_dashboard_item_l5')?.classList.add('ks_dashboard_item_header_hover')


        self.header.el.querySelector('.ks_dashboard_item_button_container')?.classList.add('ks_dashboard_item_header_hover');

        self.header.el.querySelector('.ks_dashboard_top_settings.new-features')?.classList.remove("ks_hide")
        self.header.el.querySelector('.ks_dashboard_edit_mode_settings')?.classList.add("ks_hide")
        self.header.el.querySelector("#ks_dashboard_layout_edit")?.classList.remove("ks_hide")
        self.header.el.querySelector("#ks_import_item")?.classList.remove("ks_hide")

        self.header.el.querySelector('.ks_start_tv_dashboard')?.classList.remove('ks_hide');
        self.header.el.querySelector('.ks_chart_container')?.classList.remove('ks_item_not_click', 'ks_item_click');
        self.header.el.querySelector('.ks_list_view_container')?.classList.remove('ks_item_click');


        self.grid.commit();
    }


    onKsEditLayoutClick(e) {
        var self = this;
//        self.header.el.querySelector(".custom_date_filter_section")?.classList.add("d-none");
        self.grid.setStatic(false);
        self.ksAllowItemClick = false;
        self._ksRenderEditMode();
        self.header.el?.querySelectorAll('.hide-in-edit').forEach( (element) => {
            element.classList.add('dn_hide');
        })
    }

    _ksRenderEditMode(){
        var self = this;
        self.ks_mode = 'edit';

        // Update the value of an input element with the ID 'ks_dashboard_title_input'
        // using the current dashboard name
        self.header.el.querySelector('#ks_dashboard_title_input').value = self.ks_dashboard_data.name;

        // Hide and show certain elements based on the edit mode
        self.header.el.querySelector('.ks_am_element')?.classList.add("ks_hide");
        self.header.el.querySelector('.ks_em_element')?.classList.remove("ks_hide");
        self.header.el.querySelector('.ks_dashboard_print_pdf')?.classList.add("ks_hide");

        // Update classes for various dashboard elements to control their styling
        self.header.el.querySelector('.ks_item_click')?.classList.add('ks_item_not_click');
        self.header.el.querySelector('.ks_item_click')?.classList.remove('ks_item_click');
        self.header.el.querySelector('.ks_dashboard_item')?.classList.remove('ks_dashboard_item_header_hover');
        self.header.el.querySelector('.ks_dashboard_item_header')?.classList.remove('ks_dashboard_item_header_hover');
        self.header.el.querySelector('.ks_dashboard_item_l2')?.classList.remove('ks_dashboard_item_header_hover');
        self.header.el.querySelector('.ks_dashboard_item_header_l2')?.classList.remove('ks_dashboard_item_header_hover');
        self.header.el.querySelector('.ks_dashboard_item_l5')?.classList.remove('ks_dashboard_item_header_hover');
        self.header.el.querySelector('.ks_dashboard_item_button_container')?.classList.remove('ks_dashboard_item_header_hover');

//        self.header.el.querySelector('.ks_dashboard_link').addClass("ks_hide")
        self.header.el.querySelector('.ks_dashboard_top_settings.new-features')?.classList.add("ks_hide")
        self.header.el.querySelector('.ks_dashboard_edit_mode_settings')?.classList.remove("ks_hide")

        // Hide elements related to TV dashboard and make certain elements not clickable
        self.header.el.querySelector('.ks_start_tv_dashboard')?.classList.add('ks_hide');
        self.header.el.querySelector('.ks_chart_container')?.classList.add('ks_item_not_click');
        self.header.el.querySelector('.ks_list_view_container')?.classList.add('ks_item_not_click');

        if (self.grid) {
            self.grid.enable();
        }
    }


    onAddItemTypeClick(e) {
//        let self = this;
//        let action = {
//            name: _t('Create New Chart'),
//            type: 'ir.actions.act_window',
//            res_model: 'ks_dashboard_ninja.item',
//            context: {
//                'ks_dashboard_id': self.ks_dashboard_id,
//                'ks_dashboard_item_type': 'ks_tile',
//                'form_view_ref': 'wj_ks_dashboard_ninja.item_form_view',
//                'form_view_initial_mode': 'edit',
//                'ks_set_interval': self.ks_dashboard_data.ks_set_interval,
//                'ks_data_formatting':self.ks_dashboard_data.ks_data_formatting,
//                'ks_form_view' : true
//            },
//            views: [
//                [false, 'form']
//            ],
//            view_mode: 'form',
//            target: 'current',
//        }
//        self.actionService.doAction(action)

        var self = this;
        self.dialogService.add(FormViewDialog,{
            resModel: 'ks_dashboard_ninja.item',
            context: {
                'ks_dashboard_id': self.ks_dashboard_id,
                'ks_dashboard_item_type': 'ks_tile',
                'form_view_ref': 'wj_ks_dashboard_ninja.item_form_view',
                'form_view_initial_mode': 'edit',
                'ks_set_interval': self.ks_dashboard_data.ks_set_interval,
                'ks_data_formatting':self.ks_dashboard_data.ks_data_formatting,
                'ks_form_view' : true
            },
            onRecordSaved:()=>{
                var js_id = self.actionService.currentController.jsId
                self.actionService.restore(js_id)
                this.notification.add(_t("Your chart has been successfully created."), {
                    type: "success"
                });
            },
            size: "fs",
            title: "Create New Chart"
        });
    }

    ksImportItemJson(e) {
        var self = this;
        self.header.el.querySelector('.ks_input_import_item_button').click();
    }

     ksImportItem(e) {
        var self = this;
        var fileReader = new FileReader();
        fileReader.onload = function() {
            self.header.el.querySelector('.ks_input_import_item_button').value = '';
            rpc("/web/dataset/call_kw/ks_dashboard_ninja.board/ks_import_item", {
            model: 'ks_dashboard_ninja.board',
            method: 'ks_import_item',
            args: [self.ks_dashboard_id],
            kwargs: {
                file: fileReader.result,
                dashboard_id: self.ks_dashboard_id
            }
            }).then(function(result) {
                if (result === "Success") {

                var js_id = self.actionService.currentController.jsId
                self.actionService.restore(js_id)
                }
            });
        };
        fileReader.readAsText(self.header.el.querySelector('.ks_input_import_item_button').files[0]);
    }


    ksOnDashboardSettingClick(ev){
        var self= this;
        var dashboard_id = this.ks_dashboard_id;
        var action = {
            name: _t('Dashboard Settings'),
            type: 'ir.actions.act_window',
            res_model: 'ks_dashboard_ninja.board',
            res_id: dashboard_id,
            domain: [],
            context: {'create':false},
            views: [
                [false, 'form']
            ],
            view_mode: 'form',
            target: 'new',
        }
        self.actionService.doAction(action).then(function(result){
            self.eraseCookie('FilterOrderData' + self.ks_dashboard_id);
        });
    }

    ksOnDashboardDeleteClick(ev){
        ev.preventDefault();
        var dashboard_id = this.ks_dashboard_id;
        var self= this;
        self.dialogService.add(ConfirmationDialog, {
            body: _t("Are you sure you want to delete this dashboard ?"),
            confirmLabel: _t("Delete Dashboard"),
            title: _t("Delete Dashboard"),
            confirm: () => {
                rpc("/web/dataset/call_kw/ks.dashboard.delete.wizard/ks_delete_record", {
                    model: 'ks.dashboard.delete.wizard',
                    method: "ks_delete_record",
                    args: [self.ks_dashboard_id],
                    kwargs: {dashboard_id: dashboard_id}
                }).then((result)=>{
                    self.env.services.menu.reload();
                    let currentAppId = self.env.services.menu?.getCurrentApp()?.id;
                    self.env.services.menu.selectMenu(currentAppId).then(()=>{
                        self.notification.add(_t('Dashboard Deleted Successfully'),{
                            title:_t("Deleted"),
                            type: 'success',
                        });
                    });
                });
            },
            cancel: () => {

}
        });
    }

    ksOnDashboardCreateClick(ev){
        var self= this;
        var action = {
            name: _t('Add New Dashboard'),
            type: 'ir.actions.act_window',
            res_model: 'ks.dashboard.wizard',
            domain: [],
            context: {
            },
            views: [
                [false, 'form']
            ],
            view_mode: 'form',
            target: 'new',
        }
        self.actionService.doAction(action)
    }

    ksOnDashboardDuplicateClick(ev){
        ev.preventDefault();
        var self= this;
        var dashboard_id = this.ks_dashboard_id;
        rpc('/web/dataset/call_kw/ks.dashboard.duplicate.wizard/DuplicateDashBoard', {
            model: 'ks.dashboard.duplicate.wizard',
            method: "DuplicateDashBoard",
            args: [self.ks_dashboard_id],
            kwargs: {}
        }).then((result)=>{
            self.actionService.doAction(result)
        });
   }

    onEditItemTypeClick(ev) {
        this.ksAllowItemClick = false;
        var self =this
        if(ev.currentTarget.dataset.itemId){
            self.dialogService.add(FormViewDialog,{
                resModel: 'ks_dashboard_ninja.item',
                title: 'Edit Chart',
                resId : parseInt(ev.currentTarget.dataset.itemId),
                context: {
                    'form_view_ref': 'wj_ks_dashboard_ninja.item_form_view',
                    'form_view_initial_mode': 'edit',
                    'ks_form_view' :true
                },
                onRecordSaved:()=>{
                    var js_id = self.actionService.currentController.jsId
                    self.actionService.restore(js_id)
                },
                size: 'fs'
            });
        }

    }




    ks_switch_default_dashboard(){
        var self = this;
        if (!document.querySelectorAll('.modal-body .main-box').length) {
//            dnNavBarRemoveClasses();
        }

    }


    hideFilterTab() {
        Collapse.getInstance('#collapseExample').hide()
    }




    showDateFilterRange(ev){
        var favFilterMain = this.header.el.querySelector('#favFilterMain');
        if (favFilterMain) {
            favFilterMain.classList.add('ks_hide');
        }

        this.header.el.querySelectorAll('.filters_section').forEach(function(element) {
            element.classList.add('ks_hide');
        });

        this.header.el.querySelectorAll('.custom_date_filter_section').forEach(function(element) {
            element.classList.remove('ks_hide');
        });

        this.header.el.querySelectorAll('.ks_date_input_fields').forEach(function(element) {
            element.classList.remove('ks_hide');
        });

        this.header.el.querySelectorAll('.custom-date-range-selector').forEach(function(element) {
            element.classList.add('dn_hide');
        });

        this.header.el.querySelectorAll('.ks_dashboard_top_settings.new-features').forEach(function(element) {
            element.classList.add('d-none');
        });


    }

}

KsDashboardNinja.components = { Ksdashboardtile, Ksdashboardlistview, Ksdashboardgraph, Ksdashboardkpiview, Ksdashboardtodo, DateTimePicker, DateTimeInput, CustomFilter};
KsDashboardNinja.template = "wj_ks_dashboard_ninja.KsDashboardNinjaHeader"
registry.category("actions").add("wj_ks_dashboard_ninja", KsDashboardNinja);

const ks_dn_webclient ={
    async loadRouterState(...args) {
        var self = this;
//      const sup = await this.super(...args);
        const sup = await super.loadRouterState(...args);
        const ks_reload_menu = async (id) =>  {
            this.menuService.reload().then(() => {
                self.menuService.selectMenu(id);
            });
        }
        this.actionService.ksDnReloadMenu = ks_reload_menu;
        return sup;
    },
};
patch(WebClient.prototype, ks_dn_webclient)