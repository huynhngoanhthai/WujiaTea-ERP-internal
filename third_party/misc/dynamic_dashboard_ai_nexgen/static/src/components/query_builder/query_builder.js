/** Copyright (C) NexGen Solutions */
/** @odoo-module **/

import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { Component, useState, onWillStart } from "@odoo/owl";
import { standardFieldProps } from "@web/views/fields/standard_field_props";

/**
 * Counter to generate unique IDs for rows in every section.
 * This ensures OWL t-key uniqueness even when items are added/removed.
 */
let _uid = 0;
function nextUid() { return ++_uid; }

const NUMERIC_TTYPES = new Set([
    "integer", "float", "monetary",
]);
const DATE_TTYPES = new Set(["date", "datetime"]);
const NON_NUMERIC_FOR_AGG = new Set([
    "char", "text", "html", "boolean", "binary", "selection", "reference",
]);
const AGG_FUNCS = new Set([
    "SUM", "AVG", "MIN", "MAX", "COUNT", "COUNT_DISTINCT",
    "STRING_AGG", "ARRAY_AGG", "BOOL_OR", "BOOL_AND",
]);
const OPS_NO_VALUE = new Set(["IS NULL", "IS NOT NULL"]);

export class SqlQueryBuilderWidget extends Component {
    static template = "dynamic_dashboard_ai_nexgen.SqlQueryBuilderWidget";
    static props = {
        ...standardFieldProps,
    };

    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.state = useState({
            // Core query parts
            baseModel: "",
            fields: [],
            joins: [],
            wheres: [],
            groupBys: [],
            havings: [],
            orderBys: [],

            // Advanced options
            distinct: false,
            distinctOn: [],
            limit: "",
            offset: "",

            // Raw custom expressions (SELECT columns that are freeform SQL)
            customExpressions: [],

            // Window functions & CTEs
            windowFuncs: [],
            ctes: [],

            // UI state
            availableModels: [],
            modelFields: {},
            collapsedSections: {},
            sqlPreviewVisible: true,
            fieldSearch: "",
            testResult: null,
            testBusy: false,
        });

        onWillStart(async () => {
            if (this.props.record.data[this.props.name]) {
                try {
                    const data = JSON.parse(this.props.record.data[this.props.name]);
                    this.state.baseModel = data.baseModel || "";
                    this.state.fields = (data.fields || []).map(f => ({ ...f, _uid: nextUid() }));
                    this.state.joins = (data.joins || []).map(j => ({
                        ...j,
                        conditions: j.conditions || (j.leftField ? [{
                            leftModel: j.leftModel || this.state.baseModel,
                            leftField: j.leftField || "",
                            operator: j.operator || "=",
                            rightField: j.rightField || "",
                            _uid: nextUid(),
                        }] : []),
                        _uid: nextUid(),
                    }));
                    this.state.wheres = (data.wheres || []).map(w => ({
                        ...w,
                        connector: w.connector || "AND",
                        cast: w.cast || "",
                        valueType: w.valueType === "value" ? "literal" : (w.valueType || "literal"),
                        _uid: nextUid(),
                    }));
                    this.state.groupBys = (data.groupBys || []).map(g => ({
                        ...g,
                        func: g.func || "",
                        funcParam: g.funcParam || "",
                        _uid: nextUid(),
                    }));
                    this.state.havings = (data.havings || []).map(h => ({
                        ...h,
                        connector: h.connector || "AND",
                        _uid: nextUid(),
                    }));
                    this.state.orderBys = (data.orderBys || []).map(o => ({
                        ...o,
                        nulls: o.nulls || "",
                        _uid: nextUid(),
                    }));

                    this.state.distinct = data.distinct || false;
                    this.state.distinctOn = (data.distinctOn || []).map(d => ({ ...d, _uid: nextUid() }));
                    this.state.limit = data.limit || "";
                    this.state.offset = data.offset || "";
                    this.state.customExpressions = (data.customExpressions || []).map(e => ({
                        ...e, _uid: nextUid(),
                    }));
                    this.state.windowFuncs = (data.windowFuncs || []).map(w => ({
                        ...w, _uid: nextUid(),
                    }));
                    this.state.ctes = (data.ctes || []).map(c => ({
                        ...c, _uid: nextUid(),
                    }));
                } catch (e) { console.warn("VQB: Could not parse saved state", e); }
            }
            this.state.availableModels = await this.orm.call(
                "ir.model", "search_read", [[], ["model", "name"]], { limit: 1000 }
            );
            if (this.state.baseModel) {
                await this.loadFields(this.state.baseModel);
            }
            for (let join of this.state.joins) {
                if (join.model) await this.loadFields(join.model);
                for (let cond of (join.conditions || [])) {
                    if (cond.leftModel) await this.loadFields(cond.leftModel);
                }
            }
        });
    }

    // ═══════════════════════════════════════════════════════════════════
    //  UI Helpers
    // ═══════════════════════════════════════════════════════════════════

    toggleSection(section) {
        this.state.collapsedSections[section] = !this.state.collapsedSections[section];
    }

    expandSection(section) {
        this.state.collapsedSections[section] = false;
        // Ensure sections wrapper is visible
        if (!this.state.baseModel && section !== "source") {
            return;
        }
    }

    onIssueClick(issue) {
        if (issue && issue.section) {
            this.expandSection(issue.section);
        }
    }

    toggleSqlPreview() {
        this.state.sqlPreviewVisible = !this.state.sqlPreviewVisible;
    }

    get availableTableModels() {
        const models = [];
        if (this.state.baseModel) {
            models.push(this.state.baseModel);
        }
        for (const j of this.state.joins) {
            if (j.model && !models.includes(j.model)) {
                models.push(j.model);
            }
        }
        return models;
    }

    /**
     * Filter model fields by global fieldSearch (name / description).
     */
    filteredFields(modelName) {
        const fields = this.state.modelFields[modelName] || [];
        const q = (this.state.fieldSearch || "").trim().toLowerCase();
        if (!q) return fields;
        return fields.filter(f =>
            (f.name || "").toLowerCase().includes(q) ||
            (f.field_description || "").toLowerCase().includes(q)
        );
    }

    fieldMeta(modelName, fieldName) {
        if (!modelName || !fieldName) return null;
        const fields = this.state.modelFields[modelName];
        if (!fields) return null;
        return fields.find(f => f.name === fieldName) || null;
    }

    isFieldMissing(modelName, fieldName) {
        if (!fieldName || fieldName === "*") return false;
        if (!modelName) return true;
        const fields = this.state.modelFields[modelName];
        if (!fields || !fields.length) return false; // still loading
        return !fields.some(f => f.name === fieldName);
    }

    get suggestedJoins() {
        if (!this.state.baseModel) return [];
        const fields = this.state.modelFields[this.state.baseModel] || [];
        const existing = new Set(
            (this.state.joins || []).map(j => j.model).filter(Boolean)
        );
        return fields
            .filter(f => f.ttype === "many2one" && f.relation && !existing.has(f.relation))
            .slice(0, 12)
            .map(f => ({
                field: f.name,
                label: f.field_description || f.name,
                relation: f.relation,
            }));
    }

    get validationIssues() {
        const issues = [];
        const push = (level, code, title, message, fix, section) => {
            issues.push({ level, code, title, message, fix, section });
        };

        if (!this.state.baseModel) {
            push("error", "no_base", "No source table",
                "Pick a base model to build the query.",
                "Use the Source Table search box and select an Odoo model (e.g. sale.order).",
                "source");
            return issues;
        }

        if (!this.state.availableModels.some(m => m.model === this.state.baseModel)) {
            push("error", "bad_base", "Unknown source model",
                `"${this.state.baseModel}" is not in the available models list.`,
                "Re-select the model from the datalist, or check spelling (technical name).",
                "source");
        }

        // Field existence on SELECT
        for (const f of this.state.fields) {
            if (f.name && this.isFieldMissing(f.model || this.state.baseModel, f.name)) {
                push("error", "missing_select_field", "SELECT field not found",
                    `Field "${f.name}" was not found on ${(f.model || this.state.baseModel)}.`,
                    "Open the Field dropdown and pick a listed field, or change the Table.",
                    "select");
            }
        }

        // Aggregates without GROUP BY when non-agg columns exist
        const hasAgg = this.state.fields.some(f => f.agg && AGG_FUNCS.has(f.agg));
        const hasNonAggCol = this.state.fields.some(f => f.name && !f.agg);
        const hasGroup = this.state.groupBys.some(g => g.model && g.field);
        if (hasAgg && hasNonAggCol && !hasGroup) {
            push("error", "agg_no_group", "Aggregates need GROUP BY",
                "You selected aggregates (SUM/AVG/…) together with plain columns.",
                "Add every non-aggregated column to GROUP BY, or wrap those columns in aggregates too.",
                "group");
        }

        // HAVING without GROUP BY
        if (this.state.havings.some(h => h.model && h.field) && !hasGroup) {
            push("error", "having_no_group", "HAVING without GROUP BY",
                "HAVING filters aggregate results and requires GROUP BY.",
                "Add grouping columns in GROUP BY, then keep your HAVING conditions.",
                "group");
        }

        // JOINs
        for (const j of this.state.joins) {
            if (!j.model) {
                push("error", "join_no_model", "JOIN missing target table",
                    "A join row has no target model.",
                    "Type a model technical name in Target Table (e.g. res.partner).",
                    "join");
                continue;
            }
            if (j.type !== "CROSS JOIN") {
                const conds = (j.conditions || []).filter(c => c.leftField || c.rightField);
                const valid = (j.conditions || []).filter(c =>
                    c.leftModel && c.leftField && c.rightField
                );
                if (!valid.length) {
                    push("error", "join_no_on", "JOIN missing ON conditions",
                        `Join to ${j.model} has no complete ON condition.`,
                        "Set Left Field and Right Field (usually base.m2o_field = related.id), or use Suggested Joins.",
                        "join");
                }
                for (const c of (j.conditions || [])) {
                    if (c.leftField && this.isFieldMissing(c.leftModel, c.leftField)) {
                        push("error", "join_left_missing", "JOIN left field missing",
                            `"${c.leftField}" not found on ${c.leftModel}.`,
                            "Pick a valid left field from the dropdown.",
                            "join");
                    }
                    if (c.rightField && this.isFieldMissing(j.model, c.rightField)) {
                        push("error", "join_right_missing", "JOIN right field missing",
                            `"${c.rightField}" not found on ${j.model}.`,
                            "Pick a valid right field (often id).",
                            "join");
                    }
                    if ((c.leftField && !c.rightField) || (!c.leftField && c.rightField) || conds.length && !c.leftField) {
                        if (!c.leftField || !c.rightField) {
                            push("warning", "join_partial_on", "Incomplete JOIN ON",
                                "An ON condition is missing a field.",
                                "Fill both Left Field and Right Field, or remove the condition.",
                                "join");
                        }
                    }
                }
            }
        }

        // Function / type warnings on SELECT
        for (const f of this.state.fields) {
            if (!f.name) continue;
            const meta = this.fieldMeta(f.model || this.state.baseModel, f.name);
            if (!meta) continue;
            const tt = meta.ttype;
            if (["SUM", "AVG", "MIN", "MAX"].includes(f.agg) && NON_NUMERIC_FOR_AGG.has(tt)) {
                push("warning", "agg_non_numeric", `${f.agg} on non-numeric field`,
                    `${f.agg}(${f.name}) uses ttype "${tt}".`,
                    "Pick a numeric field (integer/float/monetary), or CAST the column to NUMERIC first.",
                    "select");
            }
            if (["DATE_TRUNC", "EXTRACT"].includes(f.func) && !DATE_TTYPES.has(tt) && tt !== "char") {
                push("warning", "date_func_type", `${f.func} on non-date field`,
                    `${f.func} applied to "${f.name}" (${tt}).`,
                    "Choose a date/datetime field, or CAST to TIMESTAMP before DATE_TRUNC/EXTRACT.",
                    "select");
            }
            if (["UPPER", "LOWER", "TRIM", "INITCAP"].includes(f.func) && NUMERIC_TTYPES.has(tt) && tt !== "many2one") {
                push("warning", "text_func_numeric", `${f.func} on numeric field`,
                    `${f.func} on "${f.name}" (${tt}) is unusual.`,
                    "Use a char/text field, or CAST to TEXT first.",
                    "select");
            }
        }

        // Duplicate aliases
        const aliases = [];
        for (const f of this.state.fields) {
            if (f.alias) aliases.push(f.alias);
        }
        for (const ce of this.state.customExpressions) {
            if (ce.alias) aliases.push(ce.alias);
        }
        for (const w of this.state.windowFuncs) {
            if (w.alias) aliases.push(w.alias);
        }
        const seen = new Set();
        for (const a of aliases) {
            const key = a.toLowerCase();
            if (seen.has(key)) {
                push("error", "dup_alias", "Duplicate alias",
                    `Alias "${a}" is used more than once.`,
                    "Give each SELECT / window / expression column a unique alias.",
                    "select");
            }
            seen.add(key);
        }

        // Empty custom expressions
        for (const ce of this.state.customExpressions) {
            if (!(ce.expression || "").trim()) {
                push("warning", "empty_expr", "Empty custom expression",
                    "A custom expression row has no SQL.",
                    "Enter an expression (e.g. CASE … END) or remove the row. Use “Insert CASE” for a starter.",
                    "select");
            }
        }

        // WHERE value checks
        for (const w of this.state.wheres) {
            if (!w.field) continue;
            if (this.isFieldMissing(w.model, w.field)) {
                push("error", "missing_where_field", "WHERE field not found",
                    `Field "${w.field}" not found on ${w.model}.`,
                    "Pick a listed field or change the table.",
                    "where");
            }
            if (!OPS_NO_VALUE.has(w.operator)) {
                const val = (w.value || "").trim();
                if (!val && w.valueType !== "field") {
                    push("error", "where_empty_value", "WHERE value required",
                        `${w.field} ${w.operator} needs a value.`,
                        "Enter a literal, pick a placeholder chip, switch Value type to field/expression, or use IS NULL.",
                        "where");
                }
                if ((w.operator === "BETWEEN" || w.operator === "NOT BETWEEN") && val && !/\band\b/i.test(val)) {
                    push("error", "between_format", "BETWEEN needs AND",
                        `BETWEEN value must look like: 1 AND 10 (got "${w.value}").`,
                        "Write low AND high, e.g. 0 AND 100 or '2024-01-01' AND '2024-12-31'.",
                        "where");
                }
            }
        }

        // DISTINCT ON requires DISTINCT semantics
        if (this.state.distinctOn.some(d => d.field) && !this.state.distinct) {
            push("warning", "distinct_on_flag", "DISTINCT ON without DISTINCT",
                "DISTINCT ON is set but DISTINCT is unchecked.",
                "Enable the DISTINCT checkbox (SQL will use DISTINCT ON).",
                "options");
        }

        // Window incomplete
        for (const w of this.state.windowFuncs) {
            if (!w.func) {
                push("warning", "window_no_func", "Window row incomplete",
                    "A window function row has no function.",
                    "Choose ROW_NUMBER, RANK, SUM, LAG, etc., and set PARTITION/ORDER as needed.",
                    "window");
            }
        }

        // CTE incomplete
        for (const c of this.state.ctes) {
            if ((c.name || "").trim() && !(c.body || "").trim()) {
                push("warning", "cte_empty_body", "CTE missing body",
                    `CTE "${c.name}" has no SQL body.`,
                    "Paste a SELECT inside the CTE body, or remove the CTE.",
                    "cte");
            }
            if (!(c.name || "").trim() && (c.body || "").trim()) {
                push("warning", "cte_no_name", "CTE missing name",
                    "A CTE has a body but no name.",
                    "Give it a valid identifier name (e.g. base_data).",
                    "cte");
            }
        }

        return issues;
    }

    get healthStatus() {
        const issues = this.validationIssues;
        const errors = issues.filter(i => i.level === "error");
        if (this.state.testResult && this.state.testResult.ok) {
            return { label: "Query OK", kind: "ok" };
        }
        if (errors.length) {
            return { label: `${errors.length} issue${errors.length > 1 ? "s" : ""}`, kind: "error" };
        }
        if (issues.length) {
            return { label: `${issues.length} warning${issues.length > 1 ? "s" : ""}`, kind: "warn" };
        }
        if (this.state.baseModel) {
            return { label: "Ready", kind: "ready" };
        }
        return { label: "Ready", kind: "ready" };
    }

    get connectionId() {
        const raw = this.props.record.data.external_connection_id;
        if (!raw) return false;
        if (Array.isArray(raw)) return raw[0] || false;
        if (typeof raw === "object" && raw.id) return raw.id;
        return raw || false;
    }

    // ═══════════════════════════════════════════════════════════════════
    //  Model / Field loading
    // ═══════════════════════════════════════════════════════════════════

    async onModelChange(ev) {
        try {
            const newModel = ev.target.value;
            if (!newModel) {
                this.state.baseModel = "";
                this.state.testResult = null;
                this.updateValue();
                return;
            }
            const success = await this.loadFields(newModel);
            if (!success) {
                ev.target.value = this.state.baseModel || "";
                return;
            }
            this.state.baseModel = newModel;
            this.state.testResult = null;
            this.updateValue();
        } catch (e) {
            console.error("Error changing base model:", e);
        }
    }

    async onJoinModelChange(join, ev) {
        try {
            const newModel = ev.target.value;
            if (!newModel) {
                join.model = "";
                this.updateValue();
                return;
            }
            const success = await this.loadFields(newModel);
            if (!success) {
                ev.target.value = join.model || "";
                return;
            }
            join.model = newModel;
            this.updateValue();
        } catch (e) {
            console.error("Error changing join model:", e);
        }
    }

    async loadFields(modelName) {
        if (!modelName) return false;
        if (this.state.modelFields[modelName]) return true;
        try {
            const fields = await this.orm.call("ir.model.fields", "search_read", [
                [["model", "=", modelName]],
                ["name", "field_description", "ttype", "relation"],
            ], { limit: 1000, order: "field_description asc" });

            if (fields.length === 0) {
                const isValid = this.state.availableModels.some(m => m.model === modelName);
                if (!isValid) {
                    this.notification.add(`Model "${modelName}" does not exist.`, { type: "danger" });
                    return false;
                }
            }
            this.state.modelFields[modelName] = fields;
            return true;
        } catch (e) {
            console.warn("Could not load fields for", modelName, e);
            this.notification.add(`Error loading fields for ${modelName}.`, { type: "danger" });
            return false;
        }
    }

    async onRowModelChange(row, ev) {
        const newModel = ev.target.value;
        const success = await this.loadFields(newModel);
        if (!success) {
            ev.target.value = row.model || "";
            return;
        }
        row.model = newModel;
        this.updateValue();
    }

    async onCondLeftModelChange(cond, ev) {
        const newModel = ev.target.value;
        const success = await this.loadFields(newModel);
        if (!success) {
            ev.target.value = cond.leftModel || "";
            return;
        }
        cond.leftModel = newModel;
        this.updateValue();
    }

    async applySuggestedJoin(sug) {
        if (!sug || !sug.relation) return;
        const ok = await this.loadFields(sug.relation);
        if (!ok) return;
        this.state.joins.push({
            type: "LEFT JOIN",
            model: sug.relation,
            alias: "",
            conditions: [{
                leftModel: this.state.baseModel,
                leftField: sug.field,
                operator: "=",
                rightField: "id",
                _uid: nextUid(),
            }],
            _uid: nextUid(),
        });
        this.expandSection("join");
        this.updateValue();
    }

    // ═══════════════════════════════════════════════════════════════════
    //  Templates / CASE / placeholders
    // ═══════════════════════════════════════════════════════════════════

    applyTemplate(ev) {
        const name = ev.target.value;
        ev.target.value = "";
        if (!name || !this.state.baseModel) return;
        const base = this.state.baseModel;
        const fields = this.state.modelFields[base] || [];
        const dateField = fields.find(f => DATE_TTYPES.has(f.ttype));
        const numField = fields.find(f => ["integer", "float", "monetary"].includes(f.ttype) && f.name !== "id");
        const charField = fields.find(f => f.ttype === "char" || f.ttype === "selection");
        const activeField = fields.find(f => f.name === "active");

        if (name === "count_by") {
            const dim = charField || fields.find(f => f.name !== "id") || { name: "id" };
            this.state.fields = [
                { model: base, name: dim.name, alias: "group_key", agg: "", func: "", funcParam: "", _uid: nextUid() },
                { model: base, name: "id", alias: "cnt", agg: "COUNT", func: "", funcParam: "", _uid: nextUid() },
            ];
            this.state.groupBys = [
                { model: base, field: dim.name, func: "", funcParam: "", _uid: nextUid() },
            ];
            this.state.orderBys = [
                { model: base, field: dim.name, direction: "ASC", nulls: "", _uid: nextUid() },
            ];
        } else if (name === "sum_by_month") {
            const d = dateField || { name: "create_date" };
            const m = numField || { name: "id" };
            this.state.fields = [
                { model: base, name: d.name, alias: "period", agg: "", func: "DATE_TRUNC", funcParam: "month", _uid: nextUid() },
                { model: base, name: m.name, alias: "total", agg: "SUM", func: "", funcParam: "", _uid: nextUid() },
            ];
            this.state.groupBys = [
                { model: base, field: d.name, func: "DATE_TRUNC", funcParam: "month", _uid: nextUid() },
            ];
            this.state.orderBys = [
                { model: base, field: d.name, direction: "ASC", nulls: "", _uid: nextUid() },
            ];
        } else if (name === "top_n") {
            const m = numField || { name: "id" };
            const dim = charField || { name: "id" };
            this.state.fields = [
                { model: base, name: dim.name, alias: "label", agg: "", func: "", funcParam: "", _uid: nextUid() },
                { model: base, name: m.name, alias: "measure", agg: "", func: "", funcParam: "", _uid: nextUid() },
            ];
            this.state.orderBys = [
                { model: base, field: m.name, direction: "DESC", nulls: "LAST", _uid: nextUid() },
            ];
            this.state.limit = "10";
        } else if (name === "active") {
            this.state.fields = [
                { model: base, name: "", alias: "", agg: "", func: "", funcParam: "", _uid: nextUid() },
            ];
            if (activeField) {
                this.state.wheres = [{
                    model: base, field: "active", operator: "=", value: "true",
                    valueType: "literal", connector: "", cast: "", _uid: nextUid(),
                }];
            } else {
                this.state.wheres = [{
                    model: base, field: "create_date", operator: ">=", value: "{start_date}",
                    valueType: "placeholder", connector: "", cast: "", _uid: nextUid(),
                }];
            }
        }
        this.state.testResult = null;
        this.updateValue();
        this.notification.add(`Applied template: ${name.replace(/_/g, " ")}`, { type: "info" });
    }

    insertCaseTemplate() {
        this.state.customExpressions.push({
            expression: "CASE WHEN 1=1 THEN 1 ELSE 0 END",
            alias: "case_flag",
            _uid: nextUid(),
        });
        this.expandSection("select");
        this.updateValue();
    }

    insertPlaceholder(w, token) {
        w.value = token;
        w.valueType = "placeholder";
        this.updateValue();
    }

    // ═══════════════════════════════════════════════════════════════════
    //  SELECT columns
    // ═══════════════════════════════════════════════════════════════════

    addField() {
        this.state.fields.push({
            model: this.state.baseModel,
            name: "",
            alias: "",
            agg: "",
            func: "",
            funcParam: "",
            _uid: nextUid(),
        });
        this.updateValue();
    }

    removeField(item) {
        const idx = this.state.fields.indexOf(item);
        if (idx > -1) this.state.fields.splice(idx, 1);
        this.updateValue();
    }

    needsFuncParam(func) {
        return [
            "DATE_TRUNC", "EXTRACT", "COALESCE", "ROUND", "CAST", "CONCAT",
            "NULLIF", "GREATEST", "LEAST", "SUBSTRING", "REPLACE",
            "TO_CHAR", "TO_NUMBER", "AGE", "STRING_AGG", "LEFT", "RIGHT", "SPLIT_PART",
        ].includes(func);
    }

    // ═══════════════════════════════════════════════════════════════════
    //  Custom Expressions
    // ═══════════════════════════════════════════════════════════════════

    addCustomExpression() {
        this.state.customExpressions.push({
            expression: "",
            alias: "",
            _uid: nextUid(),
        });
        this.updateValue();
    }

    removeCustomExpression(item) {
        const idx = this.state.customExpressions.indexOf(item);
        if (idx > -1) this.state.customExpressions.splice(idx, 1);
        this.updateValue();
    }

    // ═══════════════════════════════════════════════════════════════════
    //  JOIN
    // ═══════════════════════════════════════════════════════════════════

    addJoin() {
        this.state.joins.push({
            type: "LEFT JOIN",
            model: "",
            alias: "",
            conditions: [{
                leftModel: this.state.baseModel,
                leftField: "",
                operator: "=",
                rightField: "",
                _uid: nextUid(),
            }],
            _uid: nextUid(),
        });
        this.updateValue();
    }

    removeJoin(item) {
        const idx = this.state.joins.indexOf(item);
        if (idx > -1) this.state.joins.splice(idx, 1);
        this.updateValue();
    }

    addJoinCondition(join) {
        if (!join.conditions) join.conditions = [];
        join.conditions.push({
            leftModel: this.state.baseModel,
            leftField: "",
            operator: "=",
            rightField: "",
            connector: "AND",
            _uid: nextUid(),
        });
        this.updateValue();
    }

    removeJoinCondition(join, cond) {
        const idx = (join.conditions || []).indexOf(cond);
        if (idx > -1) join.conditions.splice(idx, 1);
        this.updateValue();
    }

    // ═══════════════════════════════════════════════════════════════════
    //  WHERE / GROUP / HAVING / ORDER
    // ═══════════════════════════════════════════════════════════════════

    addWhere() {
        this.state.wheres.push({
            model: this.state.baseModel,
            field: "",
            operator: "=",
            value: "",
            valueType: "literal",
            connector: this.state.wheres.length > 0 ? "AND" : "",
            cast: "",
            _uid: nextUid(),
        });
        this.updateValue();
    }

    removeWhere(item) {
        const idx = this.state.wheres.indexOf(item);
        if (idx > -1) this.state.wheres.splice(idx, 1);
        if (this.state.wheres.length > 0) {
            this.state.wheres[0].connector = "";
        }
        this.updateValue();
    }

    addGroupBy() {
        this.state.groupBys.push({
            model: this.state.baseModel,
            field: "",
            func: "",
            funcParam: "",
            _uid: nextUid(),
        });
        this.updateValue();
    }

    removeGroupBy(item) {
        const idx = this.state.groupBys.indexOf(item);
        if (idx > -1) this.state.groupBys.splice(idx, 1);
        this.updateValue();
    }

    addHaving() {
        this.state.havings.push({
            model: this.state.baseModel,
            field: "",
            agg: "SUM",
            operator: ">",
            value: "",
            connector: this.state.havings.length > 0 ? "AND" : "",
            _uid: nextUid(),
        });
        this.updateValue();
    }

    removeHaving(item) {
        const idx = this.state.havings.indexOf(item);
        if (idx > -1) this.state.havings.splice(idx, 1);
        if (this.state.havings.length > 0) {
            this.state.havings[0].connector = "";
        }
        this.updateValue();
    }

    addOrderBy() {
        this.state.orderBys.push({
            model: this.state.baseModel,
            field: "",
            direction: "ASC",
            nulls: "",
            _uid: nextUid(),
        });
        this.updateValue();
    }

    removeOrderBy(item) {
        const idx = this.state.orderBys.indexOf(item);
        if (idx > -1) this.state.orderBys.splice(idx, 1);
        this.updateValue();
    }

    // ═══════════════════════════════════════════════════════════════════
    //  DISTINCT ON / WINDOW / CTE
    // ═══════════════════════════════════════════════════════════════════

    addDistinctOn() {
        this.state.distinctOn.push({
            model: this.state.baseModel,
            field: "",
            _uid: nextUid(),
        });
        this.state.distinct = true;
        this.updateValue();
    }

    removeDistinctOn(item) {
        const idx = this.state.distinctOn.indexOf(item);
        if (idx > -1) this.state.distinctOn.splice(idx, 1);
        this.updateValue();
    }

    addWindowFunc() {
        this.state.windowFuncs.push({
            func: "ROW_NUMBER",
            model: this.state.baseModel,
            field: "",
            partitionModel: this.state.baseModel,
            partitionField: "",
            orderModel: this.state.baseModel,
            orderField: "",
            orderDir: "ASC",
            alias: "",
            _uid: nextUid(),
        });
        this.updateValue();
    }

    removeWindowFunc(item) {
        const idx = this.state.windowFuncs.indexOf(item);
        if (idx > -1) this.state.windowFuncs.splice(idx, 1);
        this.updateValue();
    }

    addCte() {
        this.state.ctes.push({
            name: "",
            body: "",
            _uid: nextUid(),
        });
        this.updateValue();
    }

    removeCte(item) {
        const idx = this.state.ctes.indexOf(item);
        if (idx > -1) this.state.ctes.splice(idx, 1);
        this.updateValue();
    }

    // ═══════════════════════════════════════════════════════════════════
    //  Test / Copy
    // ═══════════════════════════════════════════════════════════════════

    async copySql() {
        const sql = this.generateSql();
        if (!sql) {
            this.notification.add("Nothing to copy — select a source table first.", { type: "warning" });
            return;
        }
        try {
            await navigator.clipboard.writeText(sql);
            this.notification.add("SQL copied to clipboard.", { type: "success" });
        } catch (e) {
            this.notification.add("Could not copy SQL.", { type: "danger" });
        }
    }

    async testQuery() {
        const sql = this.generateSql();
        if (!sql) {
            this.notification.add("Build a query first (pick a source table).", { type: "warning" });
            return;
        }
        this.state.testBusy = true;
        this.state.testResult = null;
        try {
            const result = await this.orm.call(
                "dynamic.dashboard.item",
                "vqb_test_sql",
                [sql, this.connectionId || false]
            );
            this.state.testResult = result || { ok: false, message: "No response" };
            if (result && result.ok) {
                this.notification.add(result.message || "Query OK", { type: "success" });
            } else {
                this.notification.add(
                    (result && (result.message || result.error)) || "Query failed",
                    { type: "danger" }
                );
            }
        } catch (e) {
            const msg = e.message || String(e);
            this.state.testResult = { ok: false, message: msg, error: msg };
            this.notification.add(msg, { type: "danger" });
        } finally {
            this.state.testBusy = false;
        }
    }

    // ═══════════════════════════════════════════════════════════════════
    //  SQL Generation
    // ═══════════════════════════════════════════════════════════════════

    _tbl(model) {
        return model ? model.replace(/\./g, '_') : '';
    }

    _col(model, fieldName) {
        return `${this._tbl(model)}."${fieldName}"`;
    }

    _wrapFunc(func, funcParam, col) {
        if (!func) return col;
        switch (func) {
            case 'DATE_TRUNC':
                return `DATE_TRUNC('${funcParam || 'month'}', ${col})`;
            case 'EXTRACT':
                return `EXTRACT(${funcParam || 'year'} FROM ${col})`;
            case 'COALESCE':
                return `COALESCE(${col}, ${funcParam || '0'})`;
            case 'UPPER':
                return `UPPER(${col})`;
            case 'LOWER':
                return `LOWER(${col})`;
            case 'TRIM':
                return `TRIM(${col})`;
            case 'ABS':
                return `ABS(${col})`;
            case 'ROUND':
                return `ROUND(${col}${funcParam ? ', ' + funcParam : ''})`;
            case 'CAST':
                return `CAST(${col} AS ${funcParam || 'TEXT'})`;
            case 'LENGTH':
                return `LENGTH(${col})`;
            case 'COUNT_DISTINCT':
                return `COUNT(DISTINCT ${col})`;
            case 'DATE':
                return `${col}::DATE`;
            case 'CONCAT':
                return `CONCAT(${col}${funcParam ? ', ' + funcParam : ''})`;
            case 'NULLIF':
                return `NULLIF(${col}, ${funcParam || "''"})`;
            case 'GREATEST':
                return `GREATEST(${col}${funcParam ? ', ' + funcParam : ''})`;
            case 'LEAST':
                return `LEAST(${col}${funcParam ? ', ' + funcParam : ''})`;
            case 'SUBSTRING':
                return `SUBSTRING(${col} FROM ${funcParam || '1'})`;
            case 'REPLACE':
                return `REPLACE(${col}, ${funcParam || "'', ''"})`;
            case 'TO_CHAR':
                return `TO_CHAR(${col}, '${funcParam || 'YYYY-MM-DD'}')`;
            case 'TO_NUMBER':
                return `TO_NUMBER(${col}::text, '${funcParam || '999999D99'}')`;
            case 'AGE':
                return funcParam ? `AGE(${col}, ${funcParam})` : `AGE(${col})`;
            case 'NOW':
                return 'NOW()';
            case 'CURRENT_DATE':
                return 'CURRENT_DATE';
            case 'STRING_AGG':
                return `STRING_AGG(${col}::text, ${funcParam || "','"})`;
            case 'BOOL_OR':
                return `BOOL_OR(${col})`;
            case 'BOOL_AND':
                return `BOOL_AND(${col})`;
            case 'INITCAP':
                return `INITCAP(${col})`;
            case 'MD5':
                return `MD5(${col}::text)`;
            case 'LEFT':
                return `LEFT(${col}, ${funcParam || '1'})`;
            case 'RIGHT':
                return `RIGHT(${col}, ${funcParam || '1'})`;
            case 'SPLIT_PART':
                return `SPLIT_PART(${col}, ${funcParam || "'.', 1"})`;
            default:
                return `${func}(${col})`;
        }
    }

    _wrapAgg(agg, col, funcParam) {
        if (!agg) return col;
        switch (agg) {
            case 'COUNT_DISTINCT':
                return `COUNT(DISTINCT ${col})`;
            case 'STRING_AGG':
                return `STRING_AGG(${col}::text, ${funcParam || "','"})`;
            case 'ARRAY_AGG':
                return `ARRAY_AGG(${col})`;
            case 'BOOL_OR':
                return `BOOL_OR(${col})`;
            case 'BOOL_AND':
                return `BOOL_AND(${col})`;
            default:
                return `${agg}(${col})`;
        }
    }

    _windowExpr(w) {
        const ranking = new Set(["ROW_NUMBER", "RANK", "DENSE_RANK"]);
        let inner;
        if (ranking.has(w.func)) {
            inner = `${w.func}()`;
        } else if (["LAG", "LEAD", "FIRST_VALUE", "LAST_VALUE"].includes(w.func)) {
            const col = w.field
                ? this._col(w.model || this.state.baseModel, w.field)
                : "1";
            inner = `${w.func}(${col})`;
        } else {
            const col = w.field
                ? this._col(w.model || this.state.baseModel, w.field)
                : "*";
            inner = `${w.func || "ROW_NUMBER"}(${col === "*" && w.func === "COUNT" ? "*" : col})`;
            if (w.func === "COUNT" && !w.field) {
                inner = "COUNT(*)";
            }
        }
        const parts = [];
        if (w.partitionField) {
            parts.push(`PARTITION BY ${this._col(w.partitionModel || this.state.baseModel, w.partitionField)}`);
        }
        if (w.orderField) {
            parts.push(`ORDER BY ${this._col(w.orderModel || this.state.baseModel, w.orderField)} ${w.orderDir || "ASC"}`);
        }
        const over = parts.length ? parts.join(" ") : "";
        let expr = `${inner} OVER (${over})`;
        if (w.alias) expr += ` AS "${w.alias}"`;
        return expr;
    }

    generateSql() {
        try {
            if (!this.state.baseModel) return "";
            const baseTable = this._tbl(this.state.baseModel);

            let sql = "";

            // ── WITH / CTE ──
            const validCtes = this.state.ctes.filter(c => (c.name || "").trim() && (c.body || "").trim());
            if (validCtes.length) {
                sql += "WITH ";
                sql += validCtes.map(c =>
                    `${c.name.trim()} AS (\n${c.body.trim()}\n)`
                ).join(",\n");
                sql += "\n";
            }

            // ── SELECT ──
            sql += `SELECT`;
            const distinctOnCols = this.state.distinctOn
                .filter(d => d.field)
                .map(d => this._col(d.model || this.state.baseModel, d.field));
            if (distinctOnCols.length) {
                sql += ` DISTINCT ON (${distinctOnCols.join(", ")})`;
            } else if (this.state.distinct) {
                sql += ` DISTINCT`;
            }
            sql += `\n`;

            const selects = [];

            for (const f of this.state.fields) {
                let col;
                if (f.func === "NOW" || f.func === "CURRENT_DATE") {
                    col = this._wrapFunc(f.func, f.funcParam, "");
                } else {
                    col = f.name ? this._col(f.model || this.state.baseModel, f.name) : '*';
                    if (f.func) {
                        col = this._wrapFunc(f.func, f.funcParam, col);
                    }
                }
                if (f.agg && f.name) {
                    col = this._wrapAgg(f.agg, col, f.funcParam);
                } else if (f.agg && !f.name && f.agg === "COUNT") {
                    col = "COUNT(*)";
                }
                if (f.alias) col += ` AS "${f.alias}"`;
                selects.push(`    ${col}`);
            }

            for (const ce of this.state.customExpressions) {
                if (ce.expression) {
                    let expr = `    ${ce.expression}`;
                    if (ce.alias) expr += ` AS "${ce.alias}"`;
                    selects.push(expr);
                }
            }

            for (const w of this.state.windowFuncs) {
                if (w.func) {
                    selects.push(`    ${this._windowExpr(w)}`);
                }
            }

            sql += selects.length ? selects.join(",\n") : "    *";

            // ── FROM ──
            sql += `\nFROM ${baseTable} AS ${baseTable}`;

            // ── JOIN ──
            for (const j of this.state.joins) {
                if (j.model) {
                    const joinTable = this._tbl(j.model);
                    const joinAlias = j.alias ? j.alias : joinTable;
                    if (j.type === "CROSS JOIN") {
                        sql += `\nCROSS JOIN ${joinTable} AS ${joinAlias}`;
                        continue;
                    }
                    const conditions = (j.conditions || []).filter(c =>
                        c.leftModel && c.leftField && c.rightField
                    );
                    let onClause = "1=1";
                    if (conditions.length) {
                        onClause = conditions.map((c, i) => {
                            const leftTbl = this._tbl(c.leftModel);
                            const op = c.operator || '=';
                            const cond = `${leftTbl}."${c.leftField}" ${op} ${joinAlias}."${c.rightField}"`;
                            return i === 0 ? cond : `${c.connector || 'AND'} ${cond}`;
                        }).join("\n        ");
                    }
                    sql += `\n${j.type} ${joinTable} AS ${joinAlias} ON ${onClause}`;
                }
            }

            // ── WHERE ──
            const validWheres = this.state.wheres.filter(w =>
                w.model && w.field && (
                    OPS_NO_VALUE.has(w.operator) ||
                    (w.value !== "" && w.value != null) ||
                    w.valueType === "field"
                )
            );
            if (validWheres.length) {
                const whereParts = validWheres.map((w, i) => {
                    let col = this._col(w.model, w.field);
                    if (w.cast) col = `CAST(${col} AS ${w.cast})`;
                    let clause;
                    if (OPS_NO_VALUE.has(w.operator)) {
                        clause = `${col} ${w.operator}`;
                    } else if (w.operator === "BETWEEN" || w.operator === "NOT BETWEEN") {
                        clause = `${col} ${w.operator} ${w.value}`;
                    } else if (w.valueType === "field" || w.valueType === "expression" || w.valueType === "placeholder") {
                        clause = `${col} ${w.operator} ${w.value}`;
                    } else {
                        clause = `${col} ${w.operator} ${w.value}`;
                    }
                    const prefix = i === 0 ? "" : `${w.connector || 'AND'} `;
                    return `    ${prefix}${clause}`;
                });
                sql += `\nWHERE ${whereParts[0].trim()}`;
                for (let i = 1; i < whereParts.length; i++) {
                    sql += `\n${whereParts[i]}`;
                }
            }

            // ── GROUP BY ──
            const validGroupBys = this.state.groupBys.filter(g => g.model && g.field);
            if (validGroupBys.length) {
                const groupCols = validGroupBys.map(g => {
                    let col = this._col(g.model, g.field);
                    if (g.func) {
                        col = this._wrapFunc(g.func, g.funcParam, col);
                    }
                    return col;
                });
                sql += `\nGROUP BY ${groupCols.join(", ")}`;
            }

            // ── HAVING ──
            const validHavings = this.state.havings.filter(h =>
                h.model && h.field && h.value !== ""
            );
            if (validHavings.length) {
                const havingParts = validHavings.map((h, i) => {
                    const col = this._col(h.model, h.field);
                    const clause = `${this._wrapAgg(h.agg || "SUM", col)} ${h.operator} ${h.value}`;
                    const prefix = i === 0 ? "" : `${h.connector || 'AND'} `;
                    return `    ${prefix}${clause}`;
                });
                sql += `\nHAVING ${havingParts[0].trim()}`;
                for (let i = 1; i < havingParts.length; i++) {
                    sql += `\n${havingParts[i]}`;
                }
            }

            // ── ORDER BY ──
            const validOrderBys = this.state.orderBys.filter(o => o.model && o.field);
            if (validOrderBys.length) {
                const orderCols = validOrderBys.map(o => {
                    let part = `${this._col(o.model, o.field)} ${o.direction}`;
                    if (o.nulls) part += ` NULLS ${o.nulls}`;
                    return part;
                });
                sql += `\nORDER BY ${orderCols.join(", ")}`;
            }

            // ── LIMIT / OFFSET ──
            if (this.state.limit) {
                sql += `\nLIMIT ${this.state.limit}`;
            }
            if (this.state.offset) {
                sql += `\nOFFSET ${this.state.offset}`;
            }

            return sql;
        } catch (e) {
            console.error("Error generating SQL:", e);
            return "ERROR GENERATING SQL";
        }
    }

    // ═══════════════════════════════════════════════════════════════════
    //  Persist to Odoo field
    // ═══════════════════════════════════════════════════════════════════

    _stripUids(arr) {
        return arr.map(item => {
            const copy = { ...item };
            delete copy._uid;
            if (copy.conditions) {
                copy.conditions = copy.conditions.map(c => {
                    const cc = { ...c };
                    delete cc._uid;
                    return cc;
                });
            }
            return copy;
        });
    }

    async updateValue() {
        try {
            this.state.testResult = null;
            const jsonStr = JSON.stringify({
                baseModel: this.state.baseModel,
                fields: this._stripUids(this.state.fields),
                joins: this._stripUids(this.state.joins),
                wheres: this._stripUids(this.state.wheres),
                groupBys: this._stripUids(this.state.groupBys),
                havings: this._stripUids(this.state.havings),
                orderBys: this._stripUids(this.state.orderBys),
                distinct: this.state.distinct,
                distinctOn: this._stripUids(this.state.distinctOn),
                limit: this.state.limit,
                offset: this.state.offset,
                customExpressions: this._stripUids(this.state.customExpressions),
                windowFuncs: this._stripUids(this.state.windowFuncs),
                ctes: this._stripUids(this.state.ctes),
            });
            const generatedSql = this.generateSql();
            await this.props.record.update({
                [this.props.name]: jsonStr,
                query: generatedSql
            });
        } catch (e) {
            console.error("Error updating field value:", e);
        }
    }
}

export const sqlQueryBuilderField = {
    component: SqlQueryBuilderWidget,
    supportedTypes: ["text", "char"],
};

registry.category("fields").add("sql_query_builder", sqlQueryBuilderField);
