/** Copyright (C) NexGen Solutions */
/** @odoo-module **/

import { WebClient } from "@web/webclient/webclient";
import { patch } from "@web/core/utils/patch";
import { onMounted } from "@odoo/owl";

patch(WebClient.prototype, {
    setup() {
        super.setup(...arguments);
        onMounted(() => {
            // Check if we are inside the persistent iframe of the dynamic dashboard website
            try {
                if (window.frameElement && window.frameElement.id === 'dd_persistent_iframe') {
                    document.body.classList.add('dd_iframe_mode');
                }
            } catch (e) {
                // Ignore cross-origin errors if any
            }
            
            // Fallback: check hash for iframe_mode
            if (window.location.hash.includes('iframe_mode=1')) {
                document.body.classList.add('dd_iframe_mode');
            }
        });
    }
});
