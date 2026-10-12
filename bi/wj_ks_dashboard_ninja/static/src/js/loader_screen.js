/** @odoo-module **/

import { LoadingIndicator } from "@web/webclient/loading_indicator/loading_indicator";
import { patch } from "@web/core/utils/patch";
import { browser } from "@web/core/browser/browser";
import { useService } from "@web/core/utils/hooks";
import { BlockUI } from "@web/core/ui/block_ui";
import { useEffect, useRef, xml } from "@odoo/owl";


patch(LoadingIndicator.prototype, {
  setup() {
    super.setup();
    this.shouldBlock = false;
  },
      requestCall({ detail }) {
        if (detail.settings.silent) {
            return;
        }
        if (this.state.count === 0) {
            browser.clearTimeout(this.startShowTimer);
            this.startShowTimer = browser.setTimeout(() => {
                if (this.state.count) {
                    this.state.show = true;
                    let ks_active_el = this.env.services.ui.activeElement.querySelector('.chat-ai-box')?.length
                    if((!ks_active_el) &&( this.env.services.menu?.getCurrentApp()?.xmlid === "wj_ks_dashboard_ninja.board_menu_root" ||
                                            this.env.services.action.currentController?.action?.tag === 'wj_ks_dashboard_ninja' )){

                        this.blockUITimer = browser.setTimeout(() => {
                                this.env.services.ui.block();
                                this.shouldBlock = true;
                            }, 3000);
                        }
                }
            }, 250);
        }
        this.rpcIds.add(detail.data.id);
        this.state.count++;
    },

    responseCall({ detail }) {
        if(this.blockUITimer){
            clearTimeout(this.blockUITimer)
            if(this.shouldBlock){
                this.env.services.ui.unblock();
                this.shouldBlock = false;
            }
        }
        if (detail.settings.silent) {
            return;
        }
        this.rpcIds.delete(detail.data.id);
        this.state.count = this.rpcIds.size;
        if (this.state.count === 0) {
            browser.clearTimeout(this.startShowTimer);
            this.state.show = false;
        }
    }

});

patch(BlockUI.prototype, {
    setup(){
        super.setup();
        this.menuService = useService('menu');

        useEffect( () => {
            let spinnerImg = document.querySelector('.o_blockUI .o_spinner img');
            if(spinnerImg && spinnerImg.src){
                spinnerImg.src = "/web/static/img/spin.svg"
            }
            let currentApp = this.menuService?.getCurrentApp();
            if (currentApp && (currentApp.xmlid === "wj_ks_dashboard_ninja.board_menu_root" ||
                        this.env.services.action?.currentController?.action?.tag === 'wj_ks_dashboard_ninja')){
                if(spinnerImg && spinnerImg.src){
                    spinnerImg.src = "/wj_ks_dashboard_ninja/static/images/loader.gif"
                }
            }
        });
    }
});
