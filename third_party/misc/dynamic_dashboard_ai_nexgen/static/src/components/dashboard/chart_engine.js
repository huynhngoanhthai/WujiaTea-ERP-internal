/** Copyright (C) NexGen Solutions */
/** @odoo-module **/

import { loadJS } from "@web/core/assets";
import { isDashboardPaintBurst } from "./render_scheduler";

/** All amCharts-rendered item types (excludes tile/kpi/list/map uses am5map). */
export const AM5_CHART_TYPES = [
    "bar", "barLine", "horizontalBar", "line", "area", "stepLine", "smoothedLine",
    "waterfall", "pie", "doughnut", "polarArea", "radar", "flower", "scatter",
    "radialBar", "gauge", "funnel", "pyramid", "pictorial", "bullet",
    "treemap", "sunburst", "forceDirected", "pack", "tree", "partition", "voronoiTreemap",
    "sankey", "chord", "chordDirected", "chordNonRibbon", "arcDiagram",
    "heatmap", "matrixHeatmap",
    "wordCloud", "venn", "candlestick", "ohlc", "timeline", "serpentine", "spiral",
];

export const AM5_MAP_TYPES = ["map", "mapPoints"];

export const XY_ZOOM_TYPES = [
    "bar", "barLine", "horizontalBar", "line", "area", "stepLine", "smoothedLine",
    "waterfall", "scatter", "bullet", "candlestick", "ohlc", "heatmap", "matrixHeatmap",
    "timeline", "serpentine", "spiral",
];

const LIB = "/dynamic_dashboard_ai_nexgen/static/lib/amcharts5";

/** Deduplicate concurrent script loads across many dashboard items. */
const _amLoadPromises = new Map();

function loadAmScriptOnce(key, src) {
    if (typeof window !== "undefined" && window[key]) {
        return Promise.resolve();
    }
    if (_amLoadPromises.has(key)) {
        return _amLoadPromises.get(key);
    }
    const p = loadJS(src).catch((err) => {
        _amLoadPromises.delete(key);
        throw err;
    });
    _amLoadPromises.set(key, p);
    return p;
}

export async function loadAmChartsLibs(itemType) {
    if (AM5_MAP_TYPES.includes(itemType) || AM5_CHART_TYPES.includes(itemType)) {
        await loadAmScriptOnce("am5", `${LIB}/index.js`);
        await loadAmScriptOnce("am5xy", `${LIB}/xy.js`);
        await loadAmScriptOnce("am5themes_Animated", `${LIB}/themes/Animated.js`);
        await loadAmScriptOnce("am5themes_Responsive", `${LIB}/themes/Responsive.js`);
    }
    if (["pie", "doughnut", "funnel", "pyramid", "pictorial", "polarArea"].includes(itemType)) {
        await loadAmScriptOnce("am5percent", `${LIB}/percent.js`);
    }
    if (["radar", "flower", "radialBar", "gauge", "polarArea"].includes(itemType)) {
        await loadAmScriptOnce("am5radar", `${LIB}/radar.js`);
    }
    if (AM5_MAP_TYPES.includes(itemType)) {
        await loadAmScriptOnce("am5map", `${LIB}/map.js`);
        await loadAmScriptOnce("am5geodata_worldLow", `${LIB}/geodata/worldLow.js`);
    }
    if (["treemap", "sunburst", "forceDirected", "pack", "tree", "partition", "voronoiTreemap"].includes(itemType)) {
        await loadAmScriptOnce("am5hierarchy", `${LIB}/hierarchy.js`);
    }
    if (["sankey", "chord", "chordDirected", "chordNonRibbon", "arcDiagram"].includes(itemType)) {
        await loadAmScriptOnce("am5flow", `${LIB}/flow.js`);
    }
    if (itemType === "wordCloud") {
        await loadAmScriptOnce("am5wc", `${LIB}/wc.js`);
    }
    if (itemType === "venn") {
        await loadAmScriptOnce("am5venn", `${LIB}/venn.js`);
    }
    if (["timeline", "serpentine", "spiral"].includes(itemType)) {
        await loadAmScriptOnce("am5timeline", `${LIB}/timeline.js`);
    }
}

/** Warm the shared AmCharts core once for the whole dashboard. */
export async function preloadAmChartsCore() {
    await loadAmChartsLibs("bar");
}

export function optEnabled(value) {
    return value === true || value === 1 || value === "true" || value === "True" || value === "1";
}

export function animationMs(data) {
    if (isDashboardPaintBurst()) {
        return 0;
    }
    if (!optEnabled(data.enable_animation !== undefined ? data.enable_animation : true)) {
        return 0;
    }
    const n = Number(data.chart_animation_duration);
    return Number.isFinite(n) && n >= 0 ? n : 800;
}

export function applyRootThemes(root, data) {
    const themes = [];
    const ui = data.amcharts_ui_theme || "animated";
    if (ui === "dark" && window.am5themes_Dark) {
        themes.push(am5themes_Dark.new(root));
    } else if (ui === "material" && window.am5themes_Material) {
        themes.push(am5themes_Material.new(root));
    }
    // Skip Animated theme during boot burst — it is a major main-thread cost
    if (ui !== "none"
        && !isDashboardPaintBurst()
        && optEnabled(data.enable_animation !== undefined ? data.enable_animation : true)
        && window.am5themes_Animated) {
        themes.push(am5themes_Animated.new(root));
    }
    if (window.am5themes_Responsive) {
        themes.push(am5themes_Responsive.new(root));
    }
    if (themes.length) {
        root.setThemes(themes);
    }
}

export function applySliceGrouper(series, root, data) {
    if (!optEnabled(data.enable_slice_grouper) || !window.am5plugins_sliceGrouper || !series) {
        return null;
    }
    try {
        const threshold = Number(data.slice_group_threshold);
        return am5plugins_sliceGrouper.SliceGrouper.new(root, {
            series,
            legend: undefined,
            threshold: Number.isFinite(threshold) ? threshold : 5,
            groupName: "Other",
            clickBehavior: "break",
        });
    } catch (e) {
        console.warn("sliceGrouper failed", e);
        return null;
    }
}

export function numOpt(data, key, fallback) {
    const n = Number(data?.[key]);
    return Number.isFinite(n) ? n : fallback;
}


export function strOpt(data, key, fallback) {
    const v = data?.[key];
    if (v === undefined || v === null || v === false || v === "") {
        return fallback;
    }
    return String(v);
}

export function colorOpt(data, key, fallbackHex) {
    const v = strOpt(data, key, fallbackHex);
    try {
        return am5.color(v);
    } catch (e) {
        return am5.color(fallbackHex);
    }
}

export function applyChartPadding(chart, data, defaults = {}) {
    if (!chart?.setAll) return;
    chart.setAll({
        paddingTop: numOpt(data, "chart_padding_top", defaults.top ?? 12),
        paddingRight: numOpt(data, "chart_padding_right", defaults.right ?? 16),
        paddingBottom: numOpt(data, "chart_padding_bottom", defaults.bottom ?? 8),
        paddingLeft: numOpt(data, "chart_padding_left", defaults.left ?? 8),
    });
}

export function am5NumberFormat(data) {
    const format = data?.data_format || "exact";
    if (format === "english") {
        return "#.#a";
    }
    if (format === "indian") {
        return "#,###.##";
    }
    return "#,###.#";
}

/** Build an amCharts tooltip label with compact/pretty number formatting. */
export function tipText(data, kind = "xy") {
    const fmt = am5NumberFormat(data);
    switch (kind) {
        case "h":
            return `[bold]{name}[/]\n{categoryY}: {valueX.formatNumber('${fmt}')}`;
        case "value":
            return `{category}: {value.formatNumber('${fmt}')}`;
        case "heat":
            return `{categoryX} / {categoryY}: {value.formatNumber('${fmt}')}`;
        case "ohlc":
            return `O:{openValueY.formatNumber('${fmt}')} H:{highValueY.formatNumber('${fmt}')}\nL:{lowValueY.formatNumber('${fmt}')} C:{valueY.formatNumber('${fmt}')}`;
        case "step":
            return `{categoryX}: {stepValue.formatNumber('${fmt}')}`;
        case "xy":
        default:
            return `[bold]{name}[/]\n{categoryX}: {valueY.formatNumber('${fmt}')}`;
    }
}

export function applyNumberFormat(root, data) {
    if (!root?.numberFormatter) return;
    const fmt = strOpt(data, "chart_number_format", am5NumberFormat(data));
    try {
        root.numberFormatter.setAll({
            numberFormat: fmt,
            smallNumberThreshold: 0.001,
        });
    } catch (e) {
        try {
            root.numberFormatter.set("numberFormat", fmt);
        } catch (e2) { /* ignore */ }
    }
}

export function makeTooltip(root, data, labelText) {
    if (!optEnabled(data.show_tooltip !== undefined ? data.show_tooltip : true)) {
        return undefined;
    }
    const tip = am5.Tooltip.new(root, {
        getFillFromSprite: true,
        autoTextColor: true,
        pointerOrientation: data.tooltip_pointer_orientation || "vertical",
        paddingTop: 9,
        paddingBottom: 9,
        paddingLeft: 12,
        paddingRight: 12,
        animationDuration: 150,
    });
    tip.label.setAll({
        text: labelText,
        fontSize: 12,
        fontWeight: "500",
        populateText: true,
        lineHeight: 1.35,
    });
    tip.get("background")?.setAll({
        fillOpacity: 0.96,
        strokeOpacity: 0.12,
        cornerRadius: 8,
        shadowColor: am5.color(0x0f172a),
        shadowBlur: 16,
        shadowOffsetY: 4,
        shadowOpacity: 0.18,
    });
    return tip;
}

/** True when chart tooltips should be shown (default on). */
export function tooltipsEnabled(data) {
    return optEnabled(data?.show_tooltip !== undefined ? data.show_tooltip : true);
}

/**
 * Clear tooltip objects / tooltipText on a series and its common templates.
 * Needed because some amCharts types keep a default tooltip even when series.tooltip is undefined.
 */
export function clearSeriesTooltips(series) {
    if (!series) {
        return;
    }
    const clearTemplate = (tpl) => {
        if (!tpl?.set) return;
        try { tpl.set("tooltipText", undefined); } catch (e) { /* */ }
        try { tpl.set("tooltipHTML", undefined); } catch (e) { /* */ }
        try { tpl.set("tooltip", undefined); } catch (e) { /* */ }
    };
    try { series.set("tooltip", undefined); } catch (e) { /* */ }
    try { series.set("tooltipText", undefined); } catch (e) { /* */ }
    clearTemplate(series.columns?.template);
    clearTemplate(series.slices?.template);
    clearTemplate(series.nodes?.template);
    clearTemplate(series.links?.template);
    clearTemplate(series.labels?.template);
    clearTemplate(series.mapPolygons?.template);
    clearTemplate(series.bullets?.template);
    try {
        const nodes = series.get?.("nodes");
        clearTemplate(nodes?.template);
    } catch (e) { /* */ }
}

/**
 * Attach a tooltip to a series (object tooltip and/or template tooltipText).
 * Respects data.show_tooltip — when off, all tooltips on the series are cleared.
 */
export function attachSeriesTooltip(series, root, data, labelText, opts = {}) {
    if (!series) {
        return false;
    }
    if (!tooltipsEnabled(data)) {
        clearSeriesTooltips(series);
        return false;
    }
    const text = labelText || opts.text;
    if (!text) {
        return true;
    }
    const mode = opts.mode || "auto"; // auto | object | text
    if (mode === "text" || (mode === "auto" && (series.slices || series.nodes || series.labels || series.mapPolygons))) {
        try {
            if (series.slices?.template) {
                series.slices.template.set("tooltipText", text);
            }
            if (series.nodes?.template) {
                series.nodes.template.set("tooltipText", text);
            }
            if (series.links?.template) {
                series.links.template.set("tooltipText", text);
            }
            if (series.labels?.template && opts.onLabels) {
                series.labels.template.set("tooltipText", text);
            }
            if (series.mapPolygons?.template) {
                series.mapPolygons.template.set("tooltipText", text);
            }
            if (series.columns?.template && opts.onColumns) {
                series.columns.template.set("tooltipText", text);
            }
        } catch (e) { /* */ }
    }
    if (mode === "object" || mode === "auto") {
        const tip = makeTooltip(root, data, text);
        if (tip) {
            try { series.set("tooltip", tip); } catch (e) { /* */ }
        }
    }
    return true;
}

export function applyValueAxisBounds(axis, data) {
    if (!axis) return;
    const minV = data.axis_min;
    const maxV = data.axis_max;
    if (minV !== null && minV !== undefined && minV !== false && minV !== "" && Number.isFinite(Number(minV))) {
        axis.set("min", Number(minV));
    }
    if (maxV !== null && maxV !== undefined && maxV !== false && maxV !== "" && Number.isFinite(Number(maxV))) {
        axis.set("max", Number(maxV));
    }
    if (optEnabled(data.logarithmic_scale)) {
        try { axis.set("logarithmic", true); } catch (e) { /* ignore */ }
    }
}

export function applyAxisLabelVisibility(axes, data) {
    const showLabels = optEnabled(data.show_axis_labels !== undefined ? data.show_axis_labels : true);
    const showCat = optEnabled(data.show_category_axis !== undefined ? data.show_category_axis : true);
    const showVal = optEnabled(data.show_value_axis !== undefined ? data.show_value_axis : true);
    (axes || []).forEach((axis) => {
        if (!axis) return;
        try {
            const renderer = axis.get("renderer");
            if (!renderer) return;
            const isCategory = !!axis.get("categoryField") || axis.className === "CategoryAxis";
            const axisVisible = isCategory ? showCat : showVal;
            if (!axisVisible) {
                renderer.labels.template.set("forceHidden", true);
                if (renderer.grid) renderer.grid.template.set("forceHidden", true);
                axis.set("visible", false);
                return;
            }
            if (!showLabels) {
                renderer.labels.template.set("forceHidden", true);
            }
        } catch (e) { /* ignore */ }
    });
}

export function applyCategoryLabelStyle(renderer, data, opts = {}) {
    if (!renderer?.labels) return;
    const maxW = numOpt(data, "category_label_max_width", opts.maxWidth || 110);
    const rotate = optEnabled(data.rotate_category_labels) || opts.forceRotate;
    const style = {
        maxWidth: maxW,
        oversizedBehavior: "truncate",
        ellipsis: "…",
        fontSize: opts.fontSize || 11,
    };
    if (rotate) {
        Object.assign(style, {
            rotation: -45,
            centerY: am5.p50,
            centerX: am5.p100,
            paddingRight: 15,
        });
    }
    renderer.labels.template.setAll(style);
}

export function applyCursorLines(cursor, data, defaults = {}) {
    if (!cursor) return;
    const showX = optEnabled(data.show_cursor_line_x !== undefined ? data.show_cursor_line_x : (defaults.x !== false));
    const showY = optEnabled(data.show_cursor_line_y !== undefined ? data.show_cursor_line_y : !!defaults.y);
    try {
        cursor.lineX?.set("visible", showX);
        cursor.lineY?.set("visible", showY);
        if (optEnabled(data.cursor_snap) && cursor.set) {
            // snap enabled when series set via set("snapToSeries", ...)
        }
    } catch (e) { /* ignore */ }
}

export function applyColumnAppearance(series, data, opts = {}) {
    if (!series?.columns) return;
    const cr = numOpt(data, "column_corner_radius", opts.corner ?? 6);
    const cw = numOpt(data, "column_width_percent", opts.widthPercent ?? 68);
    const strokeW = numOpt(data, "column_stroke_width", 0);
    const strokeOp = numOpt(data, "column_stroke_opacity", 0);
    const fillOp = numOpt(data, "series_fill_opacity", opts.fillOpacity ?? 1);
    const horizontal = !!opts.horizontal;
    const conf = {
        strokeOpacity: strokeOp,
        strokeWidth: strokeW,
        fillOpacity: fillOp,
    };
    if (horizontal) {
        Object.assign(conf, {
            cornerRadiusTR: cr,
            cornerRadiusBR: cr,
            height: am5.percent(cw),
        });
    } else {
        Object.assign(conf, {
            cornerRadiusTL: cr,
            cornerRadiusTR: cr,
            width: am5.percent(cw),
        });
    }
    series.columns.template.setAll(conf);
}

export function applyLineAppearance(series, root, data, opts = {}) {
    if (!series) return;
    if (series.strokes) {
        series.strokes.template.setAll({
            strokeWidth: numOpt(data, "line_stroke_width", opts.strokeWidth ?? 2.75),
        });
    }
    if (opts.fill && series.fills) {
        series.fills.template.setAll({
            visible: true,
            fillOpacity: numOpt(data, "area_fill_opacity", opts.fillOpacity ?? 0.22),
        });
    }
    if (data.connect_nulls !== undefined) {
        try { series.set("connect", optEnabled(data.connect_nulls)); } catch (e) { /* */ }
    }
    if (opts.tension != null || data.line_tension != null) {
        try { series.set("tension", numOpt(data, "line_tension", opts.tension ?? 0.5)); } catch (e) { /* */ }
    }
    if (opts.step && data.step_to) {
        const map = { left: 0, center: 0.5, right: 1 };
        try { series.set("stepTo", data.step_to); } catch (e) {
            try { series.set("locationX", map[data.step_to] ?? 0); } catch (e2) { /* */ }
        }
    }
    if (optEnabled(data.show_line_bullets !== undefined ? data.show_line_bullets : true) && opts.bullets !== false) {
        const br = numOpt(data, "bullet_radius", opts.bulletRadius ?? 4.5);
        series.bullets.push(() => am5.Bullet.new(root, {
            sprite: am5.Circle.new(root, {
                radius: br,
                fill: series.get("fill"),
                stroke: root.interfaceColors.get("background"),
                strokeWidth: 2,
            }),
        }));
    }
    if (data.mask_bullets !== undefined) {
        try { series.set("maskBullets", optEnabled(data.mask_bullets)); } catch (e) { /* */ }
    }
}

export function applyHeatRuleColors(series, data, target, valueField, minV, maxV, component = null) {
    if (!series || !optEnabled(data.enable_heat_rules !== undefined ? data.enable_heat_rules : true)) {
        return;
    }
    const themeKey = data.theme || data.chart_theme || 'default';
    const themeHeat = component?.getThemeHeatColors?.(themeKey) || { min: '#eff6ff', max: '#1d4ed8' };
    series.set("heatRules", [{
        target,
        dataField: valueField,
        min: colorOpt(data, "heat_min_color", themeHeat.min),
        max: colorOpt(data, "heat_max_color", themeHeat.max),
        key: "fill",
        minValue: minV,
        maxValue: maxV || 1,
    }]);
}





export function legendHidden(data) {
    return optEnabled(data.hide_legend) || data.legend_position === "none";
}

export function addLegend(chart, root, data, legendData) {
    if (legendHidden(data) || !legendData || !legendData.length) {
        return null;
    }
    const pos = data.legend_position || "bottom";
    const opts = {
        paddingTop: 8,
        paddingBottom: 2,
        layout: root.horizontalLayout,
        clickTarget: "itemContainer",
    };
    if (pos === "right") {
        Object.assign(opts, {
            centerY: am5.p50,
            y: am5.p50,
            layout: root.verticalLayout,
            width: am5.percent(28),
            height: am5.percent(100),
        });
    } else if (pos === "left") {
        Object.assign(opts, {
            centerY: am5.p50,
            y: am5.p50,
            layout: root.verticalLayout,
            width: am5.percent(28),
            height: am5.percent(100),
        });
        chart.children.moveValue(chart.children.push(am5.Legend.new(root, opts)), 0);
        const legend = chart.children.values[0];
        legend.data.setAll(legendData);
        return legend;
    } else if (pos === "top") {
        Object.assign(opts, {
            centerX: am5.p50,
            x: am5.p50,
            height: am5.percent(12),
        });
        const legend = chart.children.push(am5.Legend.new(root, opts));
        chart.children.moveValue(legend, 0);
        legend.data.setAll(legendData);
        return legend;
    } else {
        Object.assign(opts, {
            centerX: am5.p50,
            x: am5.p50,
            height: am5.percent(15),
        });
    }
    const legend = chart.children.push(am5.Legend.new(root, opts));
    if (legend.labels) {
        legend.labels.template.setAll({
            fontSize: 11,
            fontWeight: "500",
            fill: am5.color(0x64748b),
            oversizedBehavior: "truncate",
            maxWidth: 140,
        });
    }
    if (legend.valueLabels) {
        legend.valueLabels.template.setAll({
            fontSize: 11,
            fontWeight: "600",
            fill: am5.color(0x334155),
        });
    }
    const msize = numOpt(data, "legend_marker_size", 11);
    if (legend.markers) {
        legend.markers.template.setAll({ width: msize, height: msize });
    }
    if (!optEnabled(data.legend_clickable !== undefined ? data.legend_clickable : true)) {
        legend.set("clickTarget", "none");
    }
    if (optEnabled(data.legend_scrollable !== undefined ? data.legend_scrollable : true)) {
        try {
            legend.set("verticalScrollbar", am5.Scrollbar.new(root, { orientation: "vertical" }));
        } catch (e) { /* ignore */ }
    }
    legend.data.setAll(legendData);
    return legend;
}

export function applyGridVisibility(axes, data) {
    if (optEnabled(data.show_grid !== undefined ? data.show_grid : true)) {
        return;
    }
    (axes || []).forEach((axis) => {
        try {
            const renderer = axis.get("renderer");
            if (renderer?.grid) {
                renderer.grid.template.set("forceHidden", true);
            }
        } catch (e) { /* ignore */ }
    });
}

export function applyExportMenu(root, data) {
    if (!optEnabled(data.show_export_menu) || !window.am5plugins_exporting) {
        return null;
    }
    try {
        return am5plugins_exporting.Exporting.new(root, {
            menu: am5plugins_exporting.ExportingMenu.new(root, {}),
            pngOptions: { quality: 0.92 },
            jpgOptions: { quality: 0.92 },
        });
    } catch (e) {
        return null;
    }
}

export async function ensureExportingPlugin(data) {
    if (optEnabled(data.show_export_menu) && !window.am5plugins_exporting) {
        await loadJS(`${LIB}/plugins/exporting.js`);
    }
    if (optEnabled(data.enable_slice_grouper) && !window.am5plugins_sliceGrouper) {
        await loadJS(`${LIB}/plugins/sliceGrouper.js`);
    }
}

/**
 * Render extended chart types not handled by the legacy XY/pie path.
 * Returns true if handled.
 */
export function renderExtendedChart(ctx) {
    const { root, cType, data, am5data, component } = ctx;
    const dur = animationMs(data);

    if (["stepLine", "smoothedLine"].includes(cType)) {
        return renderStepOrSmoothed(ctx, dur);
    }
    if (cType === "waterfall") {
        return renderWaterfall(ctx, dur);
    }
    if (cType === "pyramid" || cType === "pictorial") {
        return renderPyramidPictorial(ctx, dur);
    }
    if (cType === "gauge") {
        return renderGauge(ctx, dur);
    }
    if (["treemap", "sunburst", "forceDirected", "pack", "tree", "partition", "voronoiTreemap"].includes(cType)) {
        return renderHierarchy(ctx, dur);
    }
    if (["sankey", "chord", "chordDirected", "chordNonRibbon", "arcDiagram"].includes(cType)) {
        return renderFlow(ctx, dur);
    }
    if (cType === "heatmap" || cType === "matrixHeatmap") {
        return renderMatrixHeatmap(ctx, dur);
    }
    if (cType === "wordCloud") {
        return renderWordCloud(ctx, dur);
    }
    if (cType === "venn") {
        return renderVenn(ctx, dur);
    }
    if (cType === "candlestick" || cType === "ohlc") {
        return renderCandlestick(ctx, dur);
    }
    if (cType === "timeline" || cType === "serpentine" || cType === "spiral") {
        return renderTimeline(ctx, dur);
    }
    return false;
}

function renderStepOrSmoothed(ctx, dur) {
    const { root, cType, data, am5data, component } = ctx;
    const pan = optEnabled(data.enable_pan !== undefined ? data.enable_pan : true);
    const zoom = optEnabled(data.enable_zoom !== undefined ? data.enable_zoom : true);
    applyNumberFormat(root, data);
    const chart = root.container.children.push(am5xy.XYChart.new(root, {
        width: am5.percent(100),
        height: am5.percent(100),
        panX: pan,
        panY: false,
        wheelX: "none",
        wheelY: "none",
        pinchZoomX: zoom,
    }));
    applyChartPadding(chart, data);
    component._amChart = chart;
    component.applyChartColors(chart, data, am5data, "category");
    if (optEnabled(data.show_scrollbar_x)) {
        chart.set("scrollbarX", am5.Scrollbar.new(root, { orientation: "horizontal" }));
    }
    if (optEnabled(data.show_cursor !== undefined ? data.show_cursor : true)) {
        const cursor = chart.set("cursor", am5xy.XYCursor.new(root, { behavior: zoom ? "zoomX" : "none" }));
        applyCursorLines(cursor, data, { x: true, y: false });
    }
    const xRenderer = am5xy.AxisRendererX.new(root, {
        minGridDistance: numOpt(data, "min_grid_distance", 30),
    });
    applyCategoryLabelStyle(xRenderer, data);
    const xAxis = chart.xAxes.push(am5xy.CategoryAxis.new(root, {
        categoryField: "category",
        renderer: xRenderer,
        tooltip: makeTooltip(root, data, "{category}"),
    }));
    xAxis.data.setAll(am5data);
    const yAxis = chart.yAxes.push(am5xy.ValueAxis.new(root, {
        renderer: am5xy.AxisRendererY.new(root, {}),
    }));
    applyValueAxisBounds(yAxis, data);
    applyGridVisibility([xAxis, yAxis], data);
    applyAxisLabelVisibility([xAxis, yAxis], data);
    const SeriesClass = cType === "smoothedLine"
        ? am5xy.SmoothedXLineSeries
        : am5xy.StepLineSeries;
    const series = chart.series.push(SeriesClass.new(root, {
        name: data.name,
        xAxis,
        yAxis,
        valueYField: "value",
        categoryXField: "category",
        tooltip: makeTooltip(root, data, `{categoryX}: {valueY.formatNumber('${am5NumberFormat(data)}')}`),
        sequencedInterpolation: true,
    }));
    applyLineAppearance(series, root, data, {
        fill: cType === "smoothedLine",
        fillOpacity: 0.15,
        step: cType === "stepLine",
        tension: cType === "smoothedLine" ? 0.5 : undefined,
    });
    component._applySeriesThemeColor(series, chart, 0);
    series.data.setAll(am5data);
    component._bindSeriesClick(series, cType);
    component._addDataValueBullets(series, root, cType, data, am5data.length);
    if (!tooltipsEnabled(data)) {
        clearSeriesTooltips(series);
    }
    addLegend(chart, root, data, chart.series.values);
    applyExportMenu(root, data);
    component._finalizeChartStyle(root, chart);
    if (dur) {
        chart.appear(dur, 80);
    }
    return true;
}

function renderWaterfall(ctx, dur) {
    const { root, data, am5data, component } = ctx;
    let points = data.waterfall_data || [];
    if (!points.length && am5data?.length) {
        // Fallback: build open/close steps from category series
        let running = 0;
        points = am5data.map((row) => {
            const step = Number(row.value) || 0;
            const openValue = running;
            running += step;
            return {
                category: row.category,
                value: running,
                openValue,
                stepValue: step,
            };
        });
    }
    if (!points.length) {
        return false;
    }
    const chart = root.container.children.push(am5xy.XYChart.new(root, {
        width: am5.percent(100),
        height: am5.percent(100),
        panX: optEnabled(data.enable_pan !== undefined ? data.enable_pan : true),
        wheelX: "none",
        wheelY: "none",
        paddingTop: 12,
        paddingRight: 16,
        paddingBottom: 8,
        paddingLeft: 8,
    }));
    component._amChart = chart;
    const themeKey = data.theme || data.chart_theme || 'default';
    const polarity = component.getThemePolarityColors?.(themeKey)
        || { positive: '#16A34A', negative: '#DC2626', total: '#2563EB' };
    // Seed ColorSet with polarity + palette so legend / exports stay themed
    component.applyChartColors(chart, data, [
        { category: 'positive' },
        { category: 'negative' },
        { category: 'total' },
        ...points,
    ], "category");
    try {
        chart.set("colors", am5.ColorSet.new(root, {
            colors: [
                am5.color(polarity.positive),
                am5.color(polarity.negative),
                am5.color(polarity.total),
                ...component.getThemeColors(themeKey, Math.max(points.length, 4)).map((c) => am5.color(c)),
            ],
            reuse: true,
            step: 1,
        }));
    } catch (e) { /* ignore */ }
    if (optEnabled(data.show_scrollbar_x)) {
        chart.set("scrollbarX", am5.Scrollbar.new(root, { orientation: "horizontal" }));
    }
    if (optEnabled(data.show_cursor !== undefined ? data.show_cursor : true)) {
        chart.set("cursor", am5xy.XYCursor.new(root, { behavior: "zoomX" }));
    }
    const xAxis = chart.xAxes.push(am5xy.CategoryAxis.new(root, {
        categoryField: "category",
        renderer: am5xy.AxisRendererX.new(root, { minGridDistance: 30 }),
    }));
    xAxis.data.setAll(points);
    const yAxis = chart.yAxes.push(am5xy.ValueAxis.new(root, {
        renderer: am5xy.AxisRendererY.new(root, {}),
    }));
    applyGridVisibility([xAxis, yAxis], data);
    const series = chart.series.push(am5xy.ColumnSeries.new(root, {
        name: data.name,
        xAxis,
        yAxis,
        valueYField: "value",
        openValueYField: "openValue",
        categoryXField: "category",
        tooltip: makeTooltip(root, data, tipText(data, "step")),
    }));
    series.columns.template.setAll({
        strokeOpacity: 0,
        cornerRadiusTL: 4,
        cornerRadiusTR: 4,
        width: am5.percent(60),
    });
    series.columns.template.adapters.add("fill", (fill, target) => {
        const ctxRow = target.dataItem?.dataContext || {};
        if (ctxRow.isTotal || ctxRow.is_total) {
            return am5.color(polarity.total);
        }
        const step = Number(ctxRow.stepValue) || 0;
        return am5.color(step >= 0 ? polarity.positive : polarity.negative);
    });
    series.columns.template.adapters.add("stroke", (stroke, target) => {
        const ctxRow = target.dataItem?.dataContext || {};
        if (ctxRow.isTotal || ctxRow.is_total) {
            return am5.color(polarity.total);
        }
        const step = Number(ctxRow.stepValue) || 0;
        return am5.color(step >= 0 ? polarity.positive : polarity.negative);
    });
    series.data.setAll(points);
    component._bindSeriesClick(series, "waterfall");
    component._addDataValueBullets(series, root, "waterfall", data, points.length);
    if (!tooltipsEnabled(data)) {
        clearSeriesTooltips(series);
    }
    addLegend(chart, root, data, chart.series.values);
    applyExportMenu(root, data);
    component._finalizeChartStyle(root, chart);
    if (dur) {
        chart.appear(dur, 80);
    }
    return true;
}

function renderPyramidPictorial(ctx, dur) {
    const { root, cType, data, am5data, component } = ctx;
    const chart = root.container.children.push(am5percent.SlicedChart.new(root, {
        width: am5.percent(100),
        height: am5.percent(100),
        layout: root.verticalLayout,
        paddingTop: 8,
        paddingBottom: 8,
    }));
    component._amChart = chart;
    component.applyChartColors(chart, data, am5data, "category");
    const SeriesClass = cType === "pictorial"
        ? am5percent.PictorialStackedSeries
        : am5percent.PyramidSeries;
    const seriesOpts = {
        valueField: "value",
        categoryField: "category",
        orientation: data.funnel_orientation || "vertical",
        alignLabels: true,
    };
    if (cType === "pictorial") {
        // Simple man silhouette path used by amCharts demos
        seriesOpts.svgPath = "M250 50c27.6 0 50 22.4 50 50s-22.4 50-50 50-50-22.4-50-50 22.4-50 50-50zm-75 130h150v220H175V180z";
    }
    const series = chart.series.push(SeriesClass.new(root, seriesOpts));
    series.slices.template.adapters.add("fill", (fill, target) =>
        chart.get("colors").getIndex(series.slices.indexOf(target))
    );
    series.slices.template.events.on("click", (ev) => {
        component.onChartClick(ev.target.dataItem.dataContext.category);
    });
    if (!optEnabled(data.show_data_value)) {
        series.labels.template.set("forceHidden", true);
    } else {
        const fmt = am5NumberFormat(data);
        series.labels.template.setAll({
            text: `{category}: {value.formatNumber('${fmt}')}`,
            populateText: true,
            fontSize: 11,
            fontWeight: "600",
        });
    }
    const fmtTip = am5NumberFormat(data);
    attachSeriesTooltip(series, root, data, `{category}: {value.formatNumber('${fmtTip}')}`, {
        mode: "text",
    });
    series.data.setAll(am5data);
    addLegend(chart, root, data, series.dataItems);
    applyExportMenu(root, data);
    component._finalizeChartStyle(root, chart);
    if (dur) {
        series.appear(dur, 80);
    }
    return true;
}

function renderGauge(ctx, dur) {
    const { root, data, am5data, component } = ctx;
    const value = am5data.reduce((s, r) => s + (Number(r.value) || 0), 0);
    const gMin = numOpt(data, "gauge_min", 0);
    const gMaxOpt = numOpt(data, "gauge_max", 0);
    const maxVal = gMaxOpt > 0
        ? gMaxOpt
        : Math.max(value * 1.25, Number(data.target_value) || value || 100, 1);
    applyNumberFormat(root, data);
    const chart = root.container.children.push(am5radar.RadarChart.new(root, {
        width: am5.percent(100),
        height: am5.percent(100),
        panX: false,
        panY: false,
        innerRadius: -20,
        startAngle: numOpt(data, "gauge_start_angle", -210),
        endAngle: numOpt(data, "gauge_end_angle", 30),
        radius: am5.percent(numOpt(data, "pie_radius", 85)),
    }));
    applyChartPadding(chart, data, { top: 8, right: 8, bottom: 8, left: 8 });
    component._amChart = chart;
    component.applyChartColors(chart, data, am5data, "category");
    const axisRenderer = am5radar.AxisRendererCircular.new(root, {
        strokeOpacity: 0.1,
        minGridDistance: numOpt(data, "min_grid_distance", 30),
    });
    axisRenderer.ticks.template.setAll({ visible: true, strokeOpacity: 0.3 });
    axisRenderer.grid.template.set("forceHidden", true);
    const axis = chart.xAxes.push(am5xy.ValueAxis.new(root, {
        maxDeviation: 0,
        min: gMin,
        max: maxVal,
        strictMinMax: true,
        renderer: axisRenderer,
    }));
    const clockHand = am5radar.ClockHand.new(root, {
        pinRadius: am5.percent(8),
        radius: am5.percent(90),
        bottomWidth: 12,
    });
    const handDataItem = axis.makeDataItem({ value });
    axis.createAxisRange(handDataItem);
    handDataItem.set("bullet", am5xy.AxisBullet.new(root, {
        sprite: clockHand,
    }));
    try {
        const themeColor = chart.get("colors")?.getIndex?.(0);
        if (themeColor) {
            clockHand.set("fill", themeColor);
            clockHand.set("stroke", themeColor);
        }
    } catch (e) { /* ignore */ }
    const label = chart.radarContainer.children.push(am5.Label.new(root, {
        centerX: am5.p50,
        centerY: am5.p50,
        text: root.numberFormatter.format(value, am5NumberFormat(data)),
        fontSize: 28,
        fontWeight: "700",
        fill: am5.color(0x111827),
        visible: optEnabled(data.show_data_value !== undefined ? data.show_data_value : true),
        background: am5.RoundedRectangle.new(root, {
            fill: am5.color(0xffffff),
            fillOpacity: 0.88,
            cornerRadiusTL: 10,
            cornerRadiusTR: 10,
            cornerRadiusBL: 10,
            cornerRadiusBR: 10,
        }),
        paddingTop: 6,
        paddingBottom: 6,
        paddingLeft: 12,
        paddingRight: 12,
    }));
    if (!optEnabled(data.show_data_value !== undefined ? data.show_data_value : true)) {
        label.set("forceHidden", true);
    }
    if (data.enable_target && data.target_value) {
        const range = axis.createAxisRange(axis.makeDataItem({
            value: data.target_value,
            endValue: maxVal,
        }));
        const accent = chart.get("colors")?.getIndex?.(1)
            || am5.color((component.getThemeColors?.(data.theme || data.chart_theme || 'default', 2) || ['#FBBF24'])[1] || '#FBBF24');
        range.get("axisFill")?.setAll({
            fill: accent,
            fillOpacity: 0.22,
            visible: true,
        });
    }
    applyExportMenu(root, data);
    component._finalizeChartStyle(root, chart);
    if (dur) {
        chart.appear(dur, 80);
        label.appear(dur);
    }
    return true;
}

function renderHierarchy(ctx, dur) {
    const { root, cType, data, component } = ctx;
    if (!window.am5hierarchy) {
        return false;
    }
    const tree = (data.hierarchy_data && data.hierarchy_data[0]) || {
        name: "Root",
        children: (data.labels || []).map((lab, i) => ({
            name: lab,
            value: (data.datasets?.[0]?.data?.[i]) || (data.data?.[i]) || 0,
        })),
    };
    const SeriesMap = {
        treemap: am5hierarchy.Treemap,
        sunburst: am5hierarchy.Sunburst,
        forceDirected: am5hierarchy.ForceDirected,
        pack: am5hierarchy.Pack,
        tree: am5hierarchy.Tree,
        partition: am5hierarchy.Partition,
        voronoiTreemap: am5hierarchy.VoronoiTreemap,
    };
    const SeriesClass = SeriesMap[cType];
    if (!SeriesClass) {
        return false;
    }
    applyNumberFormat(root, data);
    const initialDepth = Math.max(1, numOpt(data, "hierarchy_initial_depth", 2));
    const series = root.container.children.push(SeriesClass.new(root, {
        valueField: "value",
        categoryField: "name",
        childDataField: "children",
        topDepth: Math.max(0, numOpt(data, "hierarchy_top_depth", 1)),
        initialDepth,
        legendLabelText: "{category}",
        legendValueText: "{sum}",
        nodePadding: numOpt(data, "node_padding", 4),
    }));
    component._amChart = series;
    if (!optEnabled(data.show_node_labels !== undefined ? data.show_node_labels : true)
        || !optEnabled(data.show_data_value !== undefined ? data.show_data_value : true)) {
        try {
            series.labels.template.set("forceHidden", true);
        } catch (e) { /* ignore */ }
    }
    if (cType === "forceDirected") {
        series.set("manyBodyStrength", numOpt(data, "force_many_body_strength", -15));
        series.set("centerStrength", numOpt(data, "force_center_strength", 0.5));
        try { series.set("linkStrength", numOpt(data, "force_link_strength", 0.5)); } catch (e) { /* */ }
    }
    if (series.nodes) {
        series.nodes.template.setAll({ toggleKey: "none" });
        series.nodes.template.events.on("click", (ev) => {
            const name = ev.target.dataItem?.dataContext?.name;
            if (name && name !== "Root") {
                component.onChartClick(name);
            }
        });
        const fmt = am5NumberFormat(data);
        attachSeriesTooltip(series, root, data, `{category}: {sum.formatNumber('${fmt}')}`, {
            mode: "text",
        });
        if (!tooltipsEnabled(data)) {
            clearSeriesTooltips(series);
        }
    } else {
        attachSeriesTooltip(series, root, data, "{category}: {value}", { mode: "text" });
    }
    series.data.setAll([tree]);
    series.set("selectedDataItem", series.dataItems[0]);
    // Theme colors for hierarchy nodes (treemap / sunburst / pack / …)
    try {
        const leaves = [];
        const walk = (node) => {
            if (!node) return;
            if (node.children && node.children.length) {
                node.children.forEach(walk);
            } else {
                leaves.push({ category: node.name, name: node.name, value: node.value });
            }
        };
        walk(tree);
        component.applyChartColors(series, data, leaves.length ? leaves : (ctx.am5data || []), "category");
        if (series.nodes?.template) {
            series.nodes.template.adapters.add("fill", (fill, target) => {
                try {
                    const colors = series.get("colors");
                    const idx = series.nodes.indexOf(target);
                    return colors?.getIndex?.(Math.max(idx, 0)) || fill;
                } catch (e) {
                    return fill;
                }
            });
        }
    } catch (e) {
        console.warn("hierarchy theme colors failed", e);
    }
    if (!legendHidden(data) && series.dataItems[0]) {
        addLegend(root.container, root, data, series.dataItems[0].get("children") || []);
    }
    applyExportMenu(root, data);
    if (dur) {
        series.appear(dur, 80);
    }
    return true;
}

function renderFlow(ctx, dur) {
    const { root, cType, data, component } = ctx;
    if (!window.am5flow) {
        return false;
    }
    const links = data.flow_data || [];
    if (!links.length) {
        // Build from labels × datasets as source→series
        const labels = data.labels || [];
        const datasets = data.datasets || [];
        datasets.forEach((ds) => {
            (ds.data || []).forEach((v, i) => {
                if (v) {
                    links.push({
                        source: String(labels[i] || ""),
                        target: String(ds.label || ""),
                        value: Number(v) || 0,
                    });
                }
            });
        });
    }
    const SeriesMap = {
        sankey: am5flow.Sankey,
        chord: am5flow.Chord,
        chordDirected: am5flow.ChordDirected,
        chordNonRibbon: am5flow.ChordNonRibbon,
        arcDiagram: am5flow.ArcDiagram,
    };
    const FlowClass = SeriesMap[cType];
    if (!FlowClass) {
        return false;
    }
    applyNumberFormat(root, data);
    const flowOpts = {
        sourceIdField: "source",
        targetIdField: "target",
        valueField: "value",
        paddingTop: 10,
        paddingBottom: 10,
        paddingLeft: 10,
        paddingRight: 10,
    };
    if (cType === "sankey") {
        flowOpts.nodeAlign = data.sankey_node_align || "justify";
        flowOpts.nodeWidth = numOpt(data, "sankey_node_width", 10);
        flowOpts.nodePadding = numOpt(data, "sankey_node_padding", 8);
    }
    if (["chord", "chordDirected", "chordNonRibbon"].includes(cType)) {
        flowOpts.padAngle = numOpt(data, "chord_pad_angle", 0.02);
    }
    const series = root.container.children.push(FlowClass.new(root, flowOpts));
    if (!optEnabled(data.show_flow_labels !== undefined ? data.show_flow_labels : true)
        || !optEnabled(data.show_data_value !== undefined ? data.show_data_value : true)) {
        try { series.nodes.labels.template.set("forceHidden", true); } catch (e) { /* */ }
    }
    if (!optEnabled(data.show_tooltip !== undefined ? data.show_tooltip : true)) {
        clearSeriesTooltips(series);
    } else {
        const fmt = am5NumberFormat(data);
        attachSeriesTooltip(series, root, data, `{source} → {target}: {value.formatNumber('${fmt}')}`, {
            mode: "text",
        });
        try {
            series.nodes?.template?.set("tooltipText", `{name}: {sum.formatNumber('${fmt}')}`);
        } catch (e) { /* */ }
    }
    component._amChart = series;
    component.applyChartColors(series, data, links.map((l, i) => ({
        category: l.source || l.target || String(i),
        value: l.value,
    })), "category");
    if (cType === "sankey") {
        try { series.nodes.get("colors").set("step", 1); } catch (e) { /* */ }
    }
    series.data.setAll(links);
    applyExportMenu(root, data);
    if (dur) {
        series.appear(dur, 80);
    }
    return true;
}

function renderMatrixHeatmap(ctx, dur) {
    const { root, data, component } = ctx;
    const cells = data.matrix_data || [];
    const xCats = [...new Set(cells.map((c) => c.x))];
    const yCats = [...new Set(cells.map((c) => c.y))];
    const chart = root.container.children.push(am5xy.XYChart.new(root, {
        width: am5.percent(100),
        height: am5.percent(100),
        panX: false,
        panY: false,
        wheelX: "none",
        wheelY: "none",
        layout: root.verticalLayout,
        paddingTop: 8,
        paddingRight: 12,
        paddingBottom: 8,
        paddingLeft: 8,
    }));
    component._amChart = chart;
    const xRenderer = am5xy.AxisRendererX.new(root, {
        minGridDistance: 30,
        opposite: true,
    });
    xRenderer.grid.template.set("forceHidden", true);
    const xAxis = chart.xAxes.push(am5xy.CategoryAxis.new(root, {
        categoryField: "x",
        renderer: xRenderer,
        tooltip: makeTooltip(root, data, "{category}"),
    }));
    xAxis.data.setAll(xCats.map((x) => ({ x })));
    const yRenderer = am5xy.AxisRendererY.new(root, { minGridDistance: 20, inversed: true });
    yRenderer.grid.template.set("forceHidden", true);
    const yAxis = chart.yAxes.push(am5xy.CategoryAxis.new(root, {
        categoryField: "y",
        renderer: yRenderer,
    }));
    yAxis.data.setAll(yCats.map((y) => ({ y })));
    const series = chart.series.push(am5xy.ColumnSeries.new(root, {
        xAxis,
        yAxis,
        categoryXField: "x",
        categoryYField: "y",
        valueField: "value",
        calculateAggregates: true,
        tooltip: makeTooltip(root, data, tipText(data, "heat")),
    }));
    series.columns.template.setAll({
        strokeOpacity: 0,
        strokeWidth: 1,
        width: am5.percent(98),
        height: am5.percent(98),
        templateField: "columnSettings",
    });
    const values = cells.map((c) => c.value);
    const minV = Math.min(...values, 0);
    const maxV = Math.max(...values, 1);
    applyHeatRuleColors(series, data, series.columns.template, "value", minV, maxV, component);
    if (optEnabled(data.show_data_value)) {
        const heatFmt = am5NumberFormat(data);
        series.bullets.push(() => am5.Bullet.new(root, {
            sprite: am5.Label.new(root, {
                text: `{value.formatNumber('${heatFmt}')}`,
                populateText: true,
                centerX: am5.p50,
                centerY: am5.p50,
                fontSize: 10,
                fontWeight: "600",
                fill: am5.color(0x0f172a),
                oversizedBehavior: "hide",
                background: am5.RoundedRectangle.new(root, {
                    fill: am5.color(0xffffff),
                    fillOpacity: 0.72,
                    cornerRadiusTL: 3,
                    cornerRadiusTR: 3,
                    cornerRadiusBL: 3,
                    cornerRadiusBR: 3,
                }),
                paddingTop: 1,
                paddingBottom: 1,
                paddingLeft: 3,
                paddingRight: 3,
            }),
        }));
    }
    series.data.setAll(cells);
    if (optEnabled(data.enable_heat_rules !== undefined ? data.enable_heat_rules : true)
        && optEnabled(data.show_heat_legend !== undefined ? data.show_heat_legend : true)) {
        const themeHeat = component.getThemeHeatColors?.(data.theme || data.chart_theme || 'default')
            || { min: '#eff6ff', max: '#1d4ed8' };
        const heatLegend = chart.children.push(am5.HeatLegend.new(root, {
            orientation: "horizontal",
            startColor: colorOpt(data, "heat_min_color", themeHeat.min),
            endColor: colorOpt(data, "heat_max_color", themeHeat.max),
            startText: String(Math.round(minV)),
            endText: String(Math.round(maxV)),
            height: 12,
            marginTop: 8,
        }));
        heatLegend.startLabel.setAll({ fontSize: 10 });
        heatLegend.endLabel.setAll({ fontSize: 10 });
    }
    applyExportMenu(root, data);
    component._finalizeChartStyle(root, chart);
    if (dur) {
        chart.appear(dur, 80);
    }
    return true;
}

function renderWordCloud(ctx, dur) {
    const { root, data, component } = ctx;
    if (!window.am5wc) {
        return false;
    }
    let words = data.word_cloud_data || [];
    if (!words.length && data.labels) {
        const vals = data.datasets?.[0]?.data || data.data || [];
        words = data.labels.map((lab, i) => ({
            category: lab,
            value: Number(vals[i]) || 1,
        }));
    }
    applyNumberFormat(root, data);
    const anglesMode = data.word_angles_mode || "mixed";
    const angles = anglesMode === "horizontal" ? [0]
        : (anglesMode === "vertical" ? [-90] : [0, -90]);
    const series = root.container.children.push(am5wc.WordCloud.new(root, {
        categoryField: "category",
        valueField: "value",
        calculateAggregates: true,
        randomness: numOpt(data, "word_cloud_randomness", 0.1),
        minFontSize: numOpt(data, "word_min_font_size", 8),
        maxFontSize: numOpt(data, "word_max_font_size", 48),
        minWordLength: numOpt(data, "word_min_length", 2),
        angles,
    }));
    component._amChart = series;
    component.applyChartColors(series, data, words, "category");
    series.labels.template.setAll({
        paddingTop: 4,
        paddingBottom: 4,
        paddingLeft: 4,
        paddingRight: 4,
        fontFamily: "Inter, system-ui, sans-serif",
    });
    series.labels.template.adapters.add("fill", (fill, target) => {
        try {
            const colors = series.get("colors");
            const idx = series.labels.indexOf(target);
            return colors?.getIndex?.(Math.max(idx, 0)) || fill;
        } catch (e) {
            return fill;
        }
    });
    series.labels.template.events.on("click", (ev) => {
        const cat = ev.target.dataItem?.dataContext?.category;
        if (cat) {
            component.onChartClick(cat);
        }
    });
    const fmtWc = am5NumberFormat(data);
    if (tooltipsEnabled(data)) {
        series.labels.template.set("tooltipText", `{category}: {value.formatNumber('${fmtWc}')}`);
    } else {
        clearSeriesTooltips(series);
        try { series.labels.template.set("tooltipText", undefined); } catch (e) { /* */ }
    }
    series.data.setAll(words);
    applyExportMenu(root, data);
    if (dur) {
        series.appear(dur, 80);
    }
    return true;
}

function renderVenn(ctx, dur) {
    const { root, data, am5data, component } = ctx;
    if (!window.am5venn) {
        return false;
    }
    // Build simple overlapping sets from first 2–3 categories
    const slices = (am5data || []).slice(0, 3).map((r) => ({
        name: r.category,
        value: Number(r.value) || 0,
    }));
    const sets = slices.map((s) => ({ name: s.name, value: s.value }));
    if (slices.length >= 2) {
        sets.push({
            name: `${slices[0].name} ∩ ${slices[1].name}`,
            value: Math.min(slices[0].value, slices[1].value) * 0.35,
            sets: [slices[0].name, slices[1].name],
        });
    }
    if (slices.length >= 3) {
        sets.push({
            name: `${slices[1].name} ∩ ${slices[2].name}`,
            value: Math.min(slices[1].value, slices[2].value) * 0.3,
            sets: [slices[1].name, slices[2].name],
        });
        sets.push({
            name: "All",
            value: Math.min(slices[0].value, slices[1].value, slices[2].value) * 0.15,
            sets: slices.map((s) => s.name),
        });
    }
    const series = root.container.children.push(am5venn.Venn.new(root, {
        categoryField: "name",
        valueField: "value",
        intersectionsField: "sets",
        paddingTop: 10,
        paddingBottom: 10,
    }));
    component._amChart = series;
    component.applyChartColors(series, data, sets.map((s) => ({ category: s.name, value: s.value })), "category");
    try {
        series.slices.template.adapters.add("fill", (fill, target) => {
            const colors = series.get("colors");
            const idx = series.slices.indexOf(target);
            return colors?.getIndex?.(Math.max(idx, 0)) || fill;
        });
    } catch (e) { /* ignore */ }
    if (optEnabled(data.show_data_value !== undefined ? data.show_data_value : true)) {
        const fmt = am5NumberFormat(data);
        try {
            series.labels.template.setAll({
                text: `{value.formatNumber('${fmt}')}`,
                populateText: true,
                fontSize: 11,
                fontWeight: "600",
                fill: am5.color(0x0f172a),
            });
        } catch (e) { /* ignore */ }
    } else {
        try { series.labels.template.set("forceHidden", true); } catch (e) { /* ignore */ }
    }
    const fmtVenn = am5NumberFormat(data);
    attachSeriesTooltip(series, root, data, `{category}: {value.formatNumber('${fmtVenn}')}`, {
        mode: "text",
    });
    series.data.setAll(sets);
    applyExportMenu(root, data);
    if (dur) {
        series.appear(dur, 80);
    }
    return true;
}

function synthesizeOhlcFromSeries(data, am5data) {
    const labels = data.labels || (am5data || []).map((r) => r.category);
    const values = data.datasets?.[0]?.data
        || data.data
        || (am5data || []).map((r) => r.value);
    const points = [];
    let prevClose = null;
    labels.forEach((lab, i) => {
        const close = Number(values[i]) || 0;
        const open = prevClose != null ? prevClose : close;
        let high = Math.max(open, close);
        let low = Math.min(open, close);
        let span = Math.abs(close - open);
        if (span <= 0) {
            span = Math.abs(close) * 0.05 || 1;
        }
        high += span * 0.25;
        low -= span * 0.25;
        points.push({
            category: String(lab ?? ""),
            open,
            high,
            low,
            close,
        });
        prevClose = close;
    });
    return points;
}

function renderCandlestick(ctx, dur) {
    const { root, data, am5data, component } = ctx;
    let points = data.ohlc_data || [];
    if (!points.length) {
        points = synthesizeOhlcFromSeries(data, am5data);
    }
    if (!points.length) {
        return false;
    }
    const chart = root.container.children.push(am5xy.XYChart.new(root, {
        width: am5.percent(100),
        height: am5.percent(100),
        panX: optEnabled(data.enable_pan !== undefined ? data.enable_pan : true),
        wheelX: "none",
        wheelY: "none",
        paddingTop: 12,
        paddingRight: 16,
        paddingBottom: 8,
        paddingLeft: 8,
    }));
    component._amChart = chart;
    const themeKey = data.theme || data.chart_theme || 'default';
    const polarity = component.getThemePolarityColors?.(themeKey)
        || { positive: '#16A34A', negative: '#DC2626', total: '#2563EB' };
    component.applyChartColors(chart, data, points, "series");
    try {
        chart.set("colors", am5.ColorSet.new(root, {
            colors: [
                am5.color(polarity.positive),
                am5.color(polarity.negative),
                am5.color(polarity.total),
            ],
            reuse: true,
            step: 1,
        }));
    } catch (e) { /* ignore */ }
    if (optEnabled(data.show_scrollbar_x)) {
        chart.set("scrollbarX", am5.Scrollbar.new(root, { orientation: "horizontal" }));
    }
    if (optEnabled(data.show_cursor !== undefined ? data.show_cursor : true)) {
        chart.set("cursor", am5xy.XYCursor.new(root, { behavior: "zoomX" }));
    }
    const xRenderer = am5xy.AxisRendererX.new(root, { minGridDistance: 40 });
    if (points.length > 6) {
        xRenderer.labels.template.setAll({
            rotation: -45,
            centerY: am5.p50,
            centerX: am5.p100,
            paddingRight: 8,
            fontSize: 10,
        });
    }
    const xAxis = chart.xAxes.push(am5xy.CategoryAxis.new(root, {
        categoryField: "category",
        renderer: xRenderer,
        tooltip: makeTooltip(root, data, "{category}"),
    }));
    xAxis.data.setAll(points);
    const yAxis = chart.yAxes.push(am5xy.ValueAxis.new(root, {
        renderer: am5xy.AxisRendererY.new(root, {}),
        extraMax: 0.05,
        extraMin: 0.05,
    }));
    applyGridVisibility([xAxis, yAxis], data);
    const SeriesClass = (ctx.cType === "ohlc" && am5xy.OHLCSeries)
        ? am5xy.OHLCSeries
        : am5xy.CandlestickSeries;
    const series = chart.series.push(SeriesClass.new(root, {
        name: data.name || "OHLC",
        xAxis,
        yAxis,
        categoryXField: "category",
        openValueYField: "open",
        highValueYField: "high",
        lowValueYField: "low",
        valueYField: "close",
        tooltip: makeTooltip(root, data, tipText(data, "ohlc")),
    }));
    // Theme-aware up/down colors
    series.columns.template.states.create("riseFromOpen", {
        fill: am5.color(polarity.positive),
        stroke: am5.color(polarity.positive),
    });
    series.columns.template.states.create("dropFromOpen", {
        fill: am5.color(polarity.negative),
        stroke: am5.color(polarity.negative),
    });
    series.data.setAll(points);
    component._addDataValueBullets(series, root, ctx.cType || "candlestick", data, points.length);
    if (!tooltipsEnabled(data)) {
        clearSeriesTooltips(series);
    }
    addLegend(chart, root, data, chart.series.values);
    applyExportMenu(root, data);
    component._finalizeChartStyle(root, chart);
    if (dur) {
        chart.appear(dur, 80);
        series.appear(dur);
    }
    return true;
}

function renderTimeline(ctx, dur) {
    const { root, cType, data, am5data, component } = ctx;
    if (!window.am5timeline) {
        return false;
    }
    const isSerpentine = cType === "serpentine";
    const isSpiral = cType === "spiral";
    const ChartClass = isSpiral
        ? am5timeline.SpiralChart
        : (isSerpentine ? am5timeline.SerpentineChart : am5timeline.CurveChart);

    applyNumberFormat(root, data);
    const chartOpts = {
        width: am5.percent(100),
        height: am5.percent(100),
        panX: false,
        panY: false,
        wheelX: "none",
        wheelY: "none",
        orientation: data.timeline_orientation || "horizontal",
    };
    if (isSerpentine || isSpiral) {
        chartOpts.levelCount = Math.max(1, numOpt(data, "serpentine_level_count", 3));
        chartOpts.curveDistance = numOpt(data, "curve_distance", 40);
        chartOpts.yAxisRadius = am5.percent(20);
    }
    const chart = root.container.children.push(ChartClass.new(root, chartOpts));
    component._amChart = chart;
    component.applyChartColors(chart, data, am5data, "category");

    // Y renderer MUST be created first and passed into AxisRendererCurveX
    // (timeline updateLabel reads xRenderer.yRenderer.axis).
    const yRenderer = am5timeline.AxisRendererCurveY.new(root, {
        minGridDistance: 20,
    });
    yRenderer.grid.template.setAll({
        strokeOpacity: 0.08,
    });
    const yAxis = chart.yAxes.push(am5xy.ValueAxis.new(root, {
        renderer: yRenderer,
        min: 0,
        extraMax: 0.1,
    }));

    const xRendererOpts = {
        minGridDistance: 40,
        yRenderer,
    };
    // Plain CurveChart needs explicit control points; Serpentine generates its own path.
    if (!isSerpentine) {
        xRendererOpts.points = [
            { x: -400, y: 0 },
            { x: -200, y: -40 },
            { x: 0, y: 40 },
            { x: 200, y: -40 },
            { x: 400, y: 0 },
        ];
    }
    const xRenderer = am5timeline.AxisRendererCurveX.new(root, xRendererOpts);
    xRenderer.grid.template.setAll({
        strokeOpacity: 0.08,
    });
    const xAxis = chart.xAxes.push(am5xy.CategoryAxis.new(root, {
        categoryField: "category",
        renderer: xRenderer,
        tooltip: makeTooltip(root, data, "{category}"),
    }));
    xAxis.data.setAll(am5data);

    const series = chart.series.push(am5timeline.CurveColumnSeries.new(root, {
        name: data.name || "Value",
        xAxis,
        yAxis,
        valueYField: "value",
        categoryXField: "category",
        tooltip: makeTooltip(root, data, `{categoryX}: {valueY.formatNumber('${am5NumberFormat(data)}')}`),
    }));
    series.columns.template.setAll({
        strokeOpacity: 0,
        width: am5.percent(55),
        fillOpacity: 0.9,
    });
    series.columns.template.adapters.add("fill", (fill, target) => {
        try {
            return chart.get("colors").getIndex(series.columns.indexOf(target));
        } catch (e) {
            return fill;
        }
    });
    series.data.setAll(am5data);
    component._addDataValueBullets(series, root, cType, data, am5data.length);
    if (!tooltipsEnabled(data)) {
        clearSeriesTooltips(series);
    }
    applyExportMenu(root, data);
    if (dur) {
        chart.appear(dur, 80);
        series.appear(dur);
    }
    return true;
}

/**
 * Render amCharts MapChart (replaces jVectorMap).
 */
export function renderAmChartsMap(component, data) {
    const el = component.mapRef?.el;
    if (!el || !window.am5 || !window.am5map || !window.am5geodata_worldLow) {
        return false;
    }
    if (component.root) {
        try { component.root.dispose(); } catch (e) { /* */ }
        component.root = null;
    }
    const root = am5.Root.new(el);
    component.root = root;
    root.autoResize = true;
    applyRootThemes(root, data);
    const projectionName = data.map_projection || "mercator";
    const ProjectionClass = {
        mercator: am5map.geoMercator,
        orthographic: am5map.geoOrthographic,
        equirectangular: am5map.geoEquirectangular,
        naturalEarth1: am5map.geoNaturalEarth1,
    }[projectionName] || am5map.geoMercator;

    applyNumberFormat(root, data);
    const allowZoom = optEnabled(data.enable_zoom !== undefined ? data.enable_zoom : true);
    const chart = root.container.children.push(am5map.MapChart.new(root, {
        panX: data.map_pan_x_mode || "rotateX",
        panY: optEnabled(data.enable_pan !== undefined ? data.enable_pan : true) ? "translateY" : "none",
        projection: ProjectionClass(),
        homeGeoPoint: { longitude: 10, latitude: 20 },
        homeZoomLevel: numOpt(data, "map_home_zoom_level", 1),
        wheelY: allowZoom ? "zoom" : "none",
        pinchZoom: allowZoom,
    }));
    component._amChart = chart;
    component._visualZoomScale = 1;
    const exclude = optEnabled(data.map_exclude_antarctica !== undefined ? data.map_exclude_antarctica : true)
        ? ["AQ"] : [];
    const polygonSeries = chart.series.push(am5map.MapPolygonSeries.new(root, {
        geoJSON: window.am5geodata_worldLow,
        exclude,
        valueField: "value",
        calculateAggregates: true,
    }));
    const mapValues = data.datasets?.[0]?.data || data.data || [];
    const labels = data.labels || [];
    const polyData = [];
    let minV = Infinity;
    let maxV = -Infinity;
    labels.forEach((lab, i) => {
        const id = String(lab || "").trim().toUpperCase();
        if (!id) return;
        const value = Number(mapValues[i]) || 0;
        polyData.push({ id, value });
        minV = Math.min(minV, value);
        maxV = Math.max(maxV, value);
    });
    if (!Number.isFinite(minV)) {
        minV = 0;
        maxV = 1;
    }
    applyHeatRuleColors(
        polygonSeries, data, polygonSeries.mapPolygons.template, "value", minV, maxV || 1, component
    );
    polygonSeries.mapPolygons.template.setAll({
        tooltipText: "{name}: {value}",
        interactive: true,
        strokeWidth: 0.5,
        stroke: am5.color(0xffffff),
        fillOpacity: numOpt(data, "map_fill_opacity", 1),
    });
    if (!optEnabled(data.show_tooltip !== undefined ? data.show_tooltip : true)) {
        polygonSeries.mapPolygons.template.set("tooltipText", undefined);
    }
    polygonSeries.mapPolygons.template.events.on("click", (ev) => {
        const id = ev.target.dataItem?.get("id") || ev.target.dataItem?.dataContext?.id;
        if (id) {
            component.onChartClick(id);
        }
    });
    polygonSeries.data.setAll(polyData);
    if (optEnabled(data.show_map_labels) || optEnabled(data.show_data_value)) {
        polygonSeries.mapPolygons.template.set("templateField", "polygonSettings");
        const fmt = am5NumberFormat(data);
        polygonSeries.bullets.push(() => am5.Bullet.new(root, {
            sprite: am5.Label.new(root, {
                text: optEnabled(data.show_data_value)
                    ? `{value.formatNumber('${fmt}')}`
                    : "{id}",
                populateText: true,
                fontSize: 9,
                fontWeight: optEnabled(data.show_data_value) ? "600" : "400",
                fill: am5.color(0x111827),
                centerX: am5.p50,
                centerY: am5.p50,
                background: optEnabled(data.show_data_value) ? am5.RoundedRectangle.new(root, {
                    fill: am5.color(0xffffff),
                    fillOpacity: 0.75,
                    cornerRadiusTL: 3,
                    cornerRadiusTR: 3,
                    cornerRadiusBL: 3,
                    cornerRadiusBR: 3,
                }) : undefined,
                paddingTop: 1,
                paddingBottom: 1,
                paddingLeft: 3,
                paddingRight: 3,
            }),
        }));
    }
    if (optEnabled(data.show_map_zoom_control !== undefined ? data.show_map_zoom_control : true)) {
        chart.set("zoomControl", am5map.ZoomControl.new(root, {}));
    }
    if (optEnabled(data.enable_heat_rules !== undefined ? data.enable_heat_rules : true)
        && optEnabled(data.show_heat_legend !== undefined ? data.show_heat_legend : true)) {
        const themeHeat = component.getThemeHeatColors?.(data.theme || data.chart_theme || 'default')
            || { min: '#dbeafe', max: '#1e40af' };
        const heatLegend = chart.children.push(am5.HeatLegend.new(root, {
            orientation: "horizontal",
            startColor: colorOpt(data, "heat_min_color", themeHeat.min),
            endColor: colorOpt(data, "heat_max_color", themeHeat.max),
            startText: String(Math.round(minV)),
            endText: String(Math.round(maxV)),
            x: am5.p50,
            centerX: am5.p50,
            paddingBottom: 8,
            height: 12,
        }));
        heatLegend.startLabel.setAll({ fontSize: 10 });
        heatLegend.endLabel.setAll({ fontSize: 10 });
    }
    // Optional bubble/point overlay for mapPoints (centroids of valued regions)
    if (component.activeItemType === "mapPoints" && am5map.MapPointSeries) {
        const pointSeries = chart.series.push(am5map.MapPointSeries.new(root, {
            valueField: "value",
            calculateAggregates: true,
            latitudeField: "latitude",
            longitudeField: "longitude",
        }));
        const pointData = [];
        const collect = () => {
            pointData.length = 0;
            polygonSeries.mapPolygons.each((poly) => {
                const di = poly.dataItem;
                if (!di) return;
                const ctx = di.dataContext || {};
                if (ctx.value === undefined || ctx.value === null) return;
                try {
                    const center = typeof poly.geoCentroid === "function"
                        ? poly.geoCentroid()
                        : (di.get("geoCentroid") || null);
                    if (!center) return;
                    const lat = center.latitude ?? center[1];
                    const lon = center.longitude ?? center[0];
                    if (lat == null || lon == null) return;
                    pointData.push({
                        latitude: lat,
                        longitude: lon,
                        value: Number(ctx.value) || 0,
                        id: ctx.id,
                    });
                } catch (e) { /* ignore */ }
            });
            if (!pointData.length) return;
            pointSeries.data.setAll(pointData);
        };
        pointSeries.bullets.push(() => {
            const themeColor = (component.getThemeColors?.(data.theme || data.chart_theme || 'default', 1) || ['#F59E0B'])[0];
            const circle = am5.Circle.new(root, {
                radius: 5,
                fill: am5.color(themeColor),
                stroke: am5.color(0xffffff),
                strokeWidth: 1,
                tooltipText: optEnabled(data.show_tooltip !== undefined ? data.show_tooltip : true)
                    ? "{id}: {value}" : undefined,
            });
            circle.adapters.add("radius", (r, target) => {
                const di = target.dataItem;
                if (!di) return r;
                const v = Number(di.get("value") || di.dataContext?.value || 0);
                const span = (maxV - minV) || 1;
                const tNorm = Math.max(0, Math.min(1, (v - minV) / span));
                return 3 + tNorm * 14;
            });
            return am5.Bullet.new(root, { sprite: circle });
        });
        // Centroids available after polygon series validates geometry
        polygonSeries.events.on("datavalidated", collect);
        collect();
    }
    applyExportMenu(root, data);
    const dur = animationMs(data);
    if (dur) {
        chart.appear(dur, 80);
    }
    return true;
}
