/** @odoo-module **/

import { Component, onWillStart, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";

export class MetabaseDashboardClientAction extends Component {
    static template = "wujia_metabase_connector.MetabaseDashboardClientActionTemplate";

    setup() {
        this.state = useState({
            embedUrl: null,
            errorTitle: null,
            errorMessage: null,
            loading: true,
        });

        onWillStart(async () => {
            const dashboardId = this.props.action?.params?.dashboard_id || this.props.action?.context?.active_id;
            if (!dashboardId) {
                this.state.errorTitle = "Configuration Error";
                this.state.errorMessage = "No Metabase Dashboard ID was specified for this action.";
                this.state.loading = false;
                return;
            }

            try {
                const res = await fetch(`/metabase/embed_url/${dashboardId}`);
                const data = await res.json();
                if (data.status === "success") {
                    this.state.embedUrl = data.embed_url;
                } else {
                    this.state.errorTitle = data.error_title || "Error";
                    this.state.errorMessage = data.error_message || "Failed to load Metabase dashboard.";
                }
            } catch (err) {
                this.state.errorTitle = "Network Error";
                this.state.errorMessage = err.message || "Could not connect to server.";
            } finally {
                this.state.loading = false;
            }
        });
    }
}

registry.category("actions").add("wujia_metabase_dashboard_client_action", MetabaseDashboardClientAction);
