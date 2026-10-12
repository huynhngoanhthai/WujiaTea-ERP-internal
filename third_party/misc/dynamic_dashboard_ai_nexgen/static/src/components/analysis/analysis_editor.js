/** Copyright (C) NexGen Solutions */
/** @odoo-module **/

import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { Component, onWillStart, useState } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";

export class AnalysisEditor extends Component {
    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.state = useState({
            analysisId: false,
            analysis: {},
            catalog: [],
            metrics: [],
            dimensions: [],
            preview: null,
            loading: true,
            aiPrompt: "",
            aiBusy: false,
        });
        onWillStart(async () => {
            const ctx = this.props.action?.context || {};
            this.state.analysisId = ctx.default_analysis_id || ctx.active_id;
            if (!this.state.analysisId) {
                this.state.loading = false;
                return;
            }
            await this.reload();
        });
    }

    async reload() {
        this.state.loading = true;
        const [analysis] = await this.orm.read("dynamic.dashboard.analysis", [this.state.analysisId], [
            "name", "visual_type", "source_type", "model_id", "domain", "visual_config",
        ]);
        this.state.analysis = analysis || {};
        this.state.catalog = await this.orm.call("dynamic.dashboard.analysis", "get_field_catalog", [this.state.analysisId]);
        this.state.metrics = await this.orm.searchRead(
            "dynamic.dashboard.analysis.metric",
            [["analysis_id", "=", this.state.analysisId]],
            ["id", "name", "field_id", "aggregation", "sequence"],
            { order: "sequence" }
        );
        this.state.dimensions = await this.orm.searchRead(
            "dynamic.dashboard.analysis.dimension",
            [["analysis_id", "=", this.state.analysisId]],
            ["id", "name", "field_id", "date_grain", "sequence"],
            { order: "sequence" }
        );
        this.state.preview = await this.orm.call(
            "dynamic.dashboard.analysis",
            "fetch_analysis_data",
            [this.state.analysisId],
            {}
        );
        this.state.loading = false;
    }

    async addMetric(field) {
        await this.orm.create("dynamic.dashboard.analysis.metric", [{
            analysis_id: this.state.analysisId,
            name: field.label,
            field_id: field.is_metric ? field.id : false,
            aggregation: field.is_metric ? "sum" : "count",
        }]);
        await this.reload();
    }

    async addDimension(field) {
        await this.orm.create("dynamic.dashboard.analysis.dimension", [{
            analysis_id: this.state.analysisId,
            name: field.label,
            field_id: field.id,
            date_grain: field.ttype === "date" || field.ttype === "datetime" ? "month" : false,
        }]);
        await this.reload();
    }

    async removeMetric(id) {
        await this.orm.unlink("dynamic.dashboard.analysis.metric", [id]);
        await this.reload();
    }

    async removeDimension(id) {
        await this.orm.unlink("dynamic.dashboard.analysis.dimension", [id]);
        await this.reload();
    }

    async onVisualChange(ev) {
        await this.orm.write("dynamic.dashboard.analysis", [this.state.analysisId], {
            visual_type: ev.target.value,
        });
        await this.reload();
    }

    async generateFromKeyword() {
        if (!this.state.aiPrompt.trim()) return;
        this.state.aiBusy = true;
        try {
            const modelName = this.state.analysis.model_id ? this.state.analysis.model_id[1] : "res.partner";
            // model_id read returns [id, name] display - need technical name
            let technical = "res.partner";
            if (this.state.analysis.model_id) {
                const [m] = await this.orm.read("ir.model", [this.state.analysis.model_id[0]], ["model"]);
                technical = m.model;
            }
            const res = await this.orm.call(
                "dynamic.dashboard.analysis",
                "generate_from_keyword",
                [this.state.aiPrompt, technical, false]
            );
            this.state.analysisId = res.analysis_id;
            this.notification.add(_t("Analysis generated from keyword"), { type: "success" });
            await this.reload();
        } catch (e) {
            this.notification.add(e.message || String(e), { type: "danger" });
        } finally {
            this.state.aiBusy = false;
        }
    }

    async explain() {
        try {
            const text = await this.orm.call("dynamic.dashboard.analysis", "explain_with_ai", [[this.state.analysisId]]);
            this.notification.add(text, { type: "info", sticky: true });
        } catch (e) {
            this.notification.add(e.message || String(e), { type: "danger" });
        }
    }
}

AnalysisEditor.template = "dynamic_dashboard_ai_nexgen.AnalysisEditor";
AnalysisEditor.props = ["*"];
registry.category("actions").add("dynamic_dashboard_ai_nexgen.analysis_editor", AnalysisEditor);
