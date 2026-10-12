/** @odoo-module **/

import { registry } from "@web/core/registry";
import { Component, onWillStart, useState, onMounted, useEffect,useRef } from "@odoo/owl";
import { dnNavBarAddClasses } from "@wj_ks_dashboard_ninja/js/dnNavBarExtend";
import { ConfirmationDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { useService } from "@web/core/utils/hooks";
import { debounce } from "@web/core/utils/timing";
import { _t } from "@web/core/l10n/translation";
import { WarningDialog } from "@web/core/errors/error_dialogs";
import { rpc } from "@web/core/network/rpc";


export class KSDashboardNinjaOverview extends Component{
    setup(){
        this.orm = useService("orm");
        this.ks_overview = useRef("ks_overview_page")
        this.actionService = useService("action");
        this.notification = useService("notification");
        this.dialogService = useService("dialog");
        this.overviewTilesNames = [['All Dashboards', 'one'], ['All Charts', 'two'], ['Total Maps', 'three'],
                                    ['Bookmarked Dashboards', 'four'], ['All Lists', 'five']]
        this.state = useState({
            bookmarkedDashboards: false,
            filter: localStorage.getItem('dashboardFilter') || "All Dashboards",
        })

        onWillStart(async () => {
            await rpc("/web/dataset/call_kw/ks_dashboard_ninja.board/ks_update_menu_id",{
                                model: 'ks_dashboard_ninja.board',
                                method: 'ks_update_menu_id_old_db',
                                args: [[]],
                                kwargs:{},
                            });
            await this.env.services.menu.reload()
            this.data = await rpc("/web/dataset/call_kw/ks_dashboard_ninja.board/fetch_dashboard_overview",{
                                model: 'ks_dashboard_ninja.board',
                                method: 'fetch_dashboard_overview',
                                args: [[]],
                                kwargs:{},
                            });
        });

        onMounted(()=>{
            if(!document.body.classList.contains('ks_body_class'))
                    dnNavBarAddClasses();
        });

    }

    get filteredDashboards(){
        if (this.state.filter === 'Bookmarked'){
            let filteredData = Object.entries(this.data.dashboardsInfo).filter( (dashboard)=> dashboard[1].is_bookmarked);
            return filteredData.length ? Object.fromEntries(filteredData) : false;
        }
        return this.data.overviewInfo[0] ? this.data.dashboardsInfo : false;
    }

    async viewDashboard(ev){
        ev.preventDefault();
        const dashboardId = parseInt(ev.currentTarget.dataset.dashboardId)
        let clientActionId = await this.orm.silent.read(
            'ks_dashboard_ninja.board',
            [dashboardId],
            ['ks_dashboard_client_action_id']
        );
        clientActionId = clientActionId[0]?.ks_dashboard_client_action_id[0]

        this.actionService.doAction({
            type: "ir.actions.client",
            tag: "wj_ks_dashboard_ninja",
            params:{
                ks_dashboard_id: dashboardId
            },
            id: clientActionId
        });
//        if(menuId && this.env.services.menu.getMenu(menuId)){
//            let response = await this.env.services.menu.selectMenu(menuId);
//            }
//        else{
//            this.env.services.dialog.add(WarningDialog, {
//                    title: _t("Menu Access Error"),
//                    message: _t("Menu not accessible: Either you do not have permission, or the menu is inactive. Please change the dashboard menu"),
//                });
//        }

    }

    onFilterChange(ev){
        this.state.filter = ev.target.text;
        this.state.bookmarkedDashboards = !this.state.bookmarkedDashboards;
        localStorage.setItem("dashboardFilter", this.state.filter);
    }

    async updateBookmark(ev){
        let dashboardId = parseInt(ev.currentTarget.dataset.dashboardId);
        let unBookmarkSvg = this.ks_overview.el.querySelector(`#unBookmark${dashboardId}`);
        let bookmarkSvg = this.ks_overview.el.querySelector(`#bookmark${dashboardId}`);
        let bookmarkCountTag = document.getElementById('Bookmarked Dashboards');
        if (unBookmarkSvg && bookmarkSvg){
            unBookmarkSvg.classList.toggle('d-none');
            bookmarkSvg.classList.toggle('d-none');
        }
        this.data.dashboardsInfo[dashboardId].is_bookmarked = !this.data.dashboardsInfo[dashboardId].is_bookmarked;
        let updatedBookmarks = await rpc("/web/dataset/call_kw/ks_dashboard_ninja.board/update_bookmarks",{
                                model: 'ks_dashboard_ninja.board',
                                method: 'update_bookmarks',
                                args: [[dashboardId]],
                                kwargs:{},
                            });
        bookmarkCountTag.innerText = updatedBookmarks[0];
    }

    createDashboard(ev){
        let action = {
            name: _t('Create Dashboard'),
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
        this.actionService.doAction(action);
    }

    ksOnDashboardDeleteClick(ev){
        ev.preventDefault();
        var dashboard_id = parseInt(ev.currentTarget.dataset.dashboardId)
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
}

KSDashboardNinjaOverview.template = "wj_ks_dashboard_ninja.dashboardNinjaOverView";

registry.category("actions").add("dashboard_ninja", KSDashboardNinjaOverview);