/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { FormController } from "@web/views/form/form_controller";
import { onMounted, onRendered, useRef } from "@odoo/owl";
import { Notification } from "@web/core/notifications/notification";
import { renderToElement } from "@web/core/utils/render";
import { FormLabel } from "@web/views/form/form_label";

patch(FormController.prototype,{
    setup(){
        super.setup();
        onMounted(()=>{
            let cpSaveButton = this.rootRef.el?.querySelector('.o_form_button_save')
            let cpDiscardButton = this.rootRef.el?.querySelector('.o_form_button_cancel')

            if(this.rootRef.el && this.props.resModel?.startsWith('wj_ks_dashboard_ninja.')){
                if(cpSaveButton)    cpSaveButton.innerHTML = "Save"
                if(cpDiscardButton) cpDiscardButton.innerHTML = "Discard"

                let cpCogMenu = this.rootRef.el?.querySelector('.o_cp_action_menus')
                if(this.props.resModel === 'ks_dashboard_ninja.item' && cpCogMenu)  cpCogMenu.remove()
            }
        });

        onRendered(() => {
            if(this.props.resModel === 'ks_dashboard_ninja.item'){
                this.env.config.setDisplayName(this.displayName() === 'New' ? 'Create New Chart' : this.displayName());
            }
        });
    }
});


patch(FormLabel.prototype,{
    setup(){
        this.ksRootRef = useRef("ksRootRef");
        onMounted(()=>{
            let tooltip = this.ksRootRef.el?.querySelector('.text-info')
            if(tooltip && (this.env.model?.config?.resModel?.startsWith('wj_ks_dashboard_ninja.') ||
                                    this.env.services.action?.currentController?.action?.tag === 'wj_ks_dashboard_ninja'))
                    tooltip.innerHTML = '<i class="fa fa-exclamation-circle" aria-hidden="true"></i>'
        });
    }

});

patch(Notification.prototype,{
    setup(){
        super.setup();
        this.notificationRef = useRef('notificationRef');
        onMounted( () => {
            let notificationContainer = [this.notificationRef.el] || document.querySelectorAll('.o-main-components-container .o_notification');
            if(notificationContainer && (this.env.services.menu?.getCurrentApp()?.xmlid === "wj_ks_dashboard_ninja.board_menu_root" ||
                                                    this.env.services.action?.currentController?.action?.tag === 'wj_ks_dashboard_ninja')){
                let image = renderToElement('wj_ks_dashboard_ninja.ksNotificationImage', {
                                                type: this.props.type ,
                                            });
                notificationContainer.forEach((notification)=>{
                    notification.prepend(image);
                })
            }
        })
    }

});


