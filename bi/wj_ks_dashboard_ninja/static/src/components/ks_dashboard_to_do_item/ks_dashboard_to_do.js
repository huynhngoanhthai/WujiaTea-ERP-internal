/** @odoo-module **/
import { Component, onWillStart, useState ,onMounted, onWillRender,useRef,onWillPatch, onRendered } from "@odoo/owl";
import {globalfunction } from '@wj_ks_dashboard_ninja/js/ks_global_functions';
import { isMobileOS } from "@web/core/browser/feature_detection";
import { useService } from "@web/core/utils/hooks";
import {Todoeditdialog,addtododialog} from "@wj_ks_dashboard_ninja/components/ks_dashboard_to_do_item/editdialog";
import { ConfirmationDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { _t } from "@web/core/l10n/translation";
import { rpc } from "@web/core/network/rpc";

export class Ksdashboardtodo extends Component{
    setup(){
        super.setup();
        this.dialogService = useService("dialog");
        this.state = useState({to_do_view_data : ""})
        this.storeService = useService("mail.store");
        this.item = this.props.item
        this.ks_dashboard_data = this.props.dashboard_data
        this.prepare_item();
    }


    ksFetchUpdateItem(item_id) {
        var self = this;
        return rpc("/web/dataset/call_kw/ks_dashboard_ninja.board/ks_fetch_item",{
            model: 'ks_dashboard_ninja.board',
            method: 'ks_fetch_item',
            args: [
                [parseInt(item_id)], self.ks_dashboard_data.ks_dashboard_id,{}
            ],
            kwargs:{context:this.props.dashboard_data.context},
        }).then(function(new_item_data) {
            this.ks_dashboard_data.ks_item_data[item_id] = new_item_data[item_id];
            this.item = this.ks_dashboard_data.ks_item_data[item_id] ;
            this.prepare_item()
        }.bind(this));
    }

    get ksIsDashboardManager(){
        return this.ks_dashboard_data.ks_dashboard_manager;
    }

    get ksIsUser(){
        return true;
    }

    get ks_dashboard_list(){
        return this.ks_dashboard_data.ks_dashboard_list;
    }

    prepare_item() {
        var self = this;
        var item = self.item
        self.ks_to_do_view_name = 'Test';
        self.item_id = item.id;
        self.list_to_do_data = JSON.parse(item.ks_to_do_data);
        self.state.to_do_view_data = JSON.parse(item.ks_to_do_data);

        self.ks_chart_title = item.name;

        if (item.ks_info){
            var ks_description = item.ks_info.split('\n');
            var ks_description = ks_description.filter(element => element !== '')
        }else {
            var ks_description = false;
        }
        self.ks_header_color = self._ks_get_rgba_format(item.ks_header_bg_color);
        self.ks_font_color = self._ks_get_rgba_format(item.ks_font_color);
        var ks_rgba_button_color = self._ks_get_rgba_format(item.ks_button_color);
        self.ks_rgba_button_color = ks_rgba_button_color
        self.ks_info = ks_description
        self.ks_company = item.ks_company
    }

    _ks_get_rgba_format(val){
        var rgba = val.split(',')[0].match(/[A-Za-z0-9]{2}/g);
        rgba = rgba.map(function(v) {
            return parseInt(v, 16)
        }).join(",");
        return "rgba(" + rgba + "," + val.split(',')[1] + ")";
    }
    _onKsEditTask(e){
        var self = this;
        var ks_description_id = e.currentTarget.dataset.contentId;
        var ks_item_id = e.currentTarget.dataset.itemId;
        var ks_section_id = e.currentTarget.dataset.sectionId;
        var ks_description = e.currentTarget.parentElement.parentElement.querySelector('.ks_description').value;
        var ks_result = this.dialogService.add(Todoeditdialog,{
             ks_description :ks_description,
             confirm: (event) => {
                    var content = event.currentTarget.parentElement.parentElement.querySelector('.ks_description').value;
                    if (content.length === 0){
                        content = ks_description;
                    }
                    self.onSaveTask(content, parseInt(ks_description_id), parseInt(ks_item_id), parseInt(ks_section_id));
             },
        });

    }
    onSaveTask(content, ks_description_id, ks_item_id, ks_section_id){
        var self = this;
        rpc("/web/dataset/call_kw/ks_to.do.description/write",{
            model: 'ks_to.do.description',
            method: 'write',
            args: [ks_description_id, {
                "ks_description": content
            }],
            kwargs:{},
            }).then(function() {
            self.ksFetchUpdateItem(ks_item_id).then(function(){
                const tabs = document.querySelectorAll(`.ks_li_tab[data-item-id="${ks_item_id}"]`);
                if(tabs) {
                    tabs.forEach(tab => tab.classList.remove('active'));
                }

                const newActiveTab = document.querySelector(`.ks_li_tab[data-section-id="${ks_section_id}"]`);
                if (newActiveTab) newActiveTab.classList.add('active');

                const sections = document.querySelectorAll(`.ks_tab_section[data-item-id="${ks_item_id}"]`);
                if(sections) {
                     sections.forEach(section => {
                        section.classList.remove('active');
                        section.classList.remove('show');
                    });
                }

                const newActiveSection = document.querySelector(`.ks_tab_section[data-section-id="${ks_section_id}"]`);
                if (newActiveSection) {
                    newActiveSection.classList.add('active');
                    newActiveSection.classList.add('show');
                }

                const addButton = document.querySelector(`.header_add_btn[data-item-id="${ks_item_id}"]`);
                if (addButton) {
                    addButton.setAttribute('data-section-id', ks_section_id);
                }
                });
           });
    }

    _onKsDeleteContent(e){
            var self = this;
            var ks_description_id = e.currentTarget.dataset.contentId;
            var ks_item_id = e.currentTarget.dataset.itemId;
            var ks_section_id = e.currentTarget.dataset.sectionId;
            this.dialogService.add(ConfirmationDialog, {
                body: _t("Are you sure you want to remove this task?"),
                confirm: () => {
                    rpc("/web/dataset/call_kw/ks_to.do.description/unlink",{
                    model: 'ks_to.do.description',
                    method: 'unlink',
                    args: [parseInt(ks_description_id)],
                    kwargs:{}
                }).then(function(result) {
                self.ksFetchUpdateItem(ks_item_id).then(function(){
                    const tabsToDeactivate = document.querySelectorAll(`.ks_li_tab[data-item-id="${ks_item_id}"]`);
                    if(tabsToDeactivate) {
                        tabsToDeactivate.forEach(tab => tab.classList.remove('active'));
                    }

                    const activeTab = document.querySelector(`.ks_li_tab[data-section-id="${ks_section_id}"]`);
                    if (activeTab) activeTab.classList.add('active');

                    const sectionsToDeactivate = document.querySelectorAll(`.ks_tab_section[data-item-id="${ks_item_id}"]`);
                    sectionsToDeactivate.forEach(section => {
                        section.classList.remove('active');
                        section.classList.remove('show');
                    });

                    const activeSection = document.querySelector(`.ks_tab_section[data-section-id="${ks_section_id}"]`);
                    if (activeSection) {
                        activeSection.classList.add('active');
                        activeSection.classList.add('show');
                    }

                    const addButton = document.querySelector(`.header_add_btn[data-item-id="${ks_item_id}"]`);
                    if (addButton) {
                        addButton.setAttribute('data-section-id', ks_section_id);
                    }
                });
            });

            },
            cancel: () => {},
            });
        }

    _onKsAddTask(e){
            var self = this;
            var ks_section_id = e.currentTarget.dataset.sectionId;
            var ks_item_id = e.currentTarget.dataset.itemId;
            var ks_result = this.dialogService.add(addtododialog,{
                confirm: (event) => {
                var content = event.currentTarget.parentElement.parentElement.querySelector('.ks_section').value;
                    if (content.length === 0){
                        console.log("")
                    }

                    self._onCreateTask(content, parseInt(ks_section_id), parseInt(ks_item_id));
                },
            });
    }
     _onCreateTask(content, ks_section_id, ks_item_id){
            var self = this;
            rpc("/web/dataset/call_kw/ks_to.do.description/create",{
                    model: 'ks_to.do.description',
                    method: 'create',
                    args: [{
                        ks_to_do_header_id: ks_section_id,
                        ks_description: content,
                    }],
                    kwargs:{}
                }).then(function() {
                    self.ksFetchUpdateItem(ks_item_id).then(function(){
                        document.querySelectorAll(`.ks_li_tab[data-item-id="${ks_item_id}"]`).forEach(tab => {
                            tab.classList.remove('active');
                        });

                        const activeTab = document.querySelector(`.ks_li_tab[data-section-id="${ks_section_id}"]`);
                        if (activeTab) {
                            activeTab.classList.add('active');
                        }

                        document.querySelectorAll(`.ks_tab_section[data-item-id="${ks_item_id}"]`).forEach(section => {
                            section.classList.remove('active');
                            section.classList.remove('show');
                        });

                        const activeSection = document.querySelector(`.ks_tab_section[data-section-id="${ks_section_id}"]`);
                        if (activeSection) {
                            activeSection.classList.add('active');
                            activeSection.classList.add('show');
                        }

                        const addButton = document.querySelector(`.header_add_btn[data-item-id="${ks_item_id}"]`);
                        if (addButton) {
                            addButton.setAttribute('data-section-id', ks_section_id);
                        }
                    });

                });
        }

        ksOnToDoClick(ev) {
            ev.preventDefault();
            const self = this;
            const tabId = ev.currentTarget?.getAttribute('href')?.substring(1);
            const tabSection = document.getElementById(tabId);

            ev.currentTarget?.classList.add("active");

            const siblings = ev.currentTarget?.parentNode?.parentNode?.children;
            Array.from(siblings)?.forEach(sibling => {
                if (sibling !== ev.currentTarget?.parentNode) {
                    sibling.querySelector('.active')?.classList.remove("active");
                }
            });

            const siblingSections = tabSection?.parentNode?.children;
            Array.from(siblingSections)?.forEach(section => {
                if (section !== tabSection) {
                    section.classList.remove("active");
                    section.classList.add("fade");
                }
            });

            tabSection.classList.remove("fade");
            tabSection.classList.add("active");

            const sectionId = ev.currentTarget?.dataset.sectionId;
            const parentSiblings = ev.currentTarget?.parentNode?.parentNode?.parentNode?.children;
            Array.from(parentSiblings)?.forEach(sibling => {
                if (sibling !== ev.currentTarget?.parentNode?.parentNode) {
                    sibling.setAttribute('data-section-id', sectionId);
                }
            });
        }


        _onKsActiveHandler(e){
            var self = this;
            var ks_item_id = e.currentTarget.dataset.itemId;
            var content_id = e.currentTarget.dataset.contentId;
            var ks_task_id = e.currentTarget.dataset.contentId;
            var ks_section_id = e.currentTarget.dataset.sectionId;
            var ks_value = e.currentTarget.dataset.valueId;
            if (ks_value== 'True'){
                ks_value = false
            }else{
                ks_value = true
            }
            self.content_id = parseInt(content_id);
            rpc("/web/dataset/call_kw/ks_to.do.description/write",{
                    model: 'ks_to.do.description',
                    method: 'write',
                    args: [parseInt(content_id), {
                        "ks_active": ks_value
                    }],
                    kwargs:{}
                }).then(function() {
                    self.ksFetchUpdateItem(ks_item_id).then(function(){
                        document.querySelectorAll(`.ks_li_tab[data-item-id="${ks_item_id}"]`).forEach(tab => {
                            tab.classList.remove('active');
                        });

                        const activeTab = document.querySelector(`.ks_li_tab[data-section-id="${ks_section_id}"]`);
                        if (activeTab) {
                            activeTab.classList.add('active');
                        }

                        document.querySelectorAll(`.ks_tab_section[data-item-id="${ks_item_id}"]`).forEach(section => {
                            section.classList.remove('active');
                            section.classList.remove('show');
                        });

                        const activeSection = document.querySelector(`.ks_tab_section[data-section-id="${ks_section_id}"]`);
                        if (activeSection) {
                            activeSection.classList.add('active');
                            activeSection.classList.add('show');
                        }

                        const addButton = document.querySelector(`.header_add_btn[data-item-id="${ks_item_id}"]`);
                        if (addButton) {
                            addButton.setAttribute('data-section-id', ks_section_id);
                        }
                    });
                });
        }

};

Ksdashboardtodo.props = {
    item: { type: Object, Optional:true},
    dashboard_data: { type: Object, Optional:true},
    hideButtons: { type: Number, optional: true },
    on_dialog: { type: Boolean, optional: true },
    explain_ai_whole: { type: Boolean, optional: true }
};
Ksdashboardtodo.components = {Todoeditdialog, addtododialog}

Ksdashboardtodo.template = "Ksdashboardtodo";
