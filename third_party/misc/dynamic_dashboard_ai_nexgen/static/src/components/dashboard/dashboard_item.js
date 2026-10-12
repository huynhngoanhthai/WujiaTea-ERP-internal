/** Copyright (C) NexGen Solutions */
/** @odoo-module **/

import { useService } from "@web/core/utils/hooks";
import { Component, onWillStart, onMounted, onWillUnmount, onWillUpdateProps, useRef, useState, useEffect } from "@odoo/owl";
import { loadJS, loadCSS } from "@web/core/assets";
import { user } from "@web/core/user";
import { _t } from "@web/core/l10n/translation";
import { formatDashboardNumber, getUserLocale } from "@dynamic_dashboard_ai_nexgen/utils/l10n";
import { captureElementToCanvas } from "@dynamic_dashboard_ai_nexgen/utils/html2canvas_capture";
import {
    AM5_CHART_TYPES,
    AM5_MAP_TYPES,
    XY_ZOOM_TYPES,
    loadAmChartsLibs,
    ensureExportingPlugin,
    applyRootThemes,
    animationMs,
    optEnabled,
    makeTooltip,
    clearSeriesTooltips,
    tooltipsEnabled,
    attachSeriesTooltip,
    addLegend,
    legendHidden,
    applyGridVisibility,
    applyExportMenu,
    applySliceGrouper,
    numOpt,
    applyChartPadding,
    applyNumberFormat,
    applyValueAxisBounds,
    applyAxisLabelVisibility,
    applyCategoryLabelStyle,
    applyCursorLines,
    applyColumnAppearance,
    applyLineAppearance,
    applyHeatRuleColors,
    colorOpt,
    am5NumberFormat,
    renderExtendedChart,
    renderAmChartsMap,
} from "./chart_engine";
import { scheduleChartRender } from "./render_scheduler";

export class DynamicDashboardItem extends Component {
    async _ensureLibs() {
        const type = this.activeItemType || this.props.itemType;
        if (AM5_CHART_TYPES.includes(type) || AM5_MAP_TYPES.includes(type)) {
            await loadAmChartsLibs(type);
            // Export plugins are optional — do not block first paint
            ensureExportingPlugin(this.state?.data || this.props || {}).catch(() => {});
        }
    }

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notification = useService("notification");
        this.chartRef = useRef("chartContainer");
        this.mapRef = useRef("mapContainer");
        this.itemCardRef = useRef("itemCard");
        this.newTodoInput = useRef("newTodoInput");
        this.chartInstance = null;
        
        this.state = useState({
            data: {},
            loading: true,
            error: null,
            drillStack: [],
            drillDateType: null,
            quickEditOpen: false,
            quickEdit: { name: '', chart_theme: 'default', item_type: '' },
            canEdit: false,
            listOffset: 0,
            listSearch: '',
            listSortCol: null,
            listSortAsc: true,
            // Local layout override after Switch Layout (avoids full page reload)
            overrideItemType: null,
            inView: false,
        });

        onWillStart(async () => {
            if (this.props.canEdit !== undefined) {
                this.state.canEdit = !!this.props.canEdit;
            } else {
                this.state.canEdit = await user.hasGroup("dynamic_dashboard_ai_nexgen.group_dashboard_manager");
            }
            // Prefer batched parent payload — avoids one RPC per card on first paint
            if (this.props.prefetchedData && typeof this.props.prefetchedData === 'object') {
                this._applyPayload(this.props.prefetchedData);
            } else if (this.props.awaitingBatch) {
                // Parent is batch-loading; keep skeleton until prefetchedData arrives
                this.state.loading = true;
            } else {
                await this._ensureLibs();
                await this.loadItemData();
            }
        });

        onWillUpdateProps(async (nextProps) => {
            if (nextProps.canEdit !== undefined && nextProps.canEdit !== this.props.canEdit) {
                this.state.canEdit = !!nextProps.canEdit;
            }
            if (nextProps.previewData && nextProps.previewData !== this.props.previewData) {
                try {
                    this.state.data = JSON.parse(nextProps.previewData);
                    if (this.state.data.error) this.state.error = this.state.data.error;
                    else this.state.error = null;
                } catch (e) {
                    this.state.error = _t("Invalid preview data.");
                }
                return;
            }
            // Batched parent refresh — apply payload without another round-trip
            if (nextProps.prefetchedData
                && nextProps.prefetchedData !== this.props.prefetchedData
                && typeof nextProps.prefetchedData === 'object') {
                if (nextProps.itemType !== this.props.itemType) {
                    this.state.overrideItemType = null;
                }
                this._applyPayload(nextProps.prefetchedData);
                return;
            }
            if (nextProps.awaitingBatch && !nextProps.prefetchedData) {
                this.state.loading = true;
                return;
            }
            if (nextProps.itemType !== this.props.itemType ||
                nextProps.globalDateFilter !== this.props.globalDateFilter ||
                nextProps.globalCompare !== this.props.globalCompare ||
                nextProps.refreshKey !== this.props.refreshKey ||
                JSON.stringify(nextProps.customFilterDomains) !== JSON.stringify(this.props.customFilterDomains)) {
                // Parent caught up with a layout change — drop local override
                if (nextProps.itemType !== this.props.itemType) {
                    this.state.overrideItemType = null;
                }
                // If parent already supplied a fresh payload for this refresh, skip RPC
                if (nextProps.prefetchedData && typeof nextProps.prefetchedData === 'object'
                    && nextProps.refreshKey !== this.props.refreshKey) {
                    this._applyPayload(nextProps.prefetchedData);
                    return;
                }
                if (nextProps.awaitingBatch) {
                    this.state.loading = true;
                    return;
                }
                this.state.drillStack = [];
                this.state.drillDateType = null;
                this.state.listOffset = 0;
                this.state.listSearch = '';
                this.state.listSortCol = null;
                await this.loadItemData({
                    globalDateFilter: nextProps.globalDateFilter,
                    globalCompare: nextProps.globalCompare,
                    customFilterDomains: nextProps.customFilterDomains,
                });
            }
        });


        onMounted(() => {
            this._onDdChartResize = () => this.resizeChart();
            this.itemCardRef.el?.addEventListener("dd-chart-resize", this._onDdChartResize);
            this._setupVisibilityObserver();
        });
        
        onWillUnmount(() => {
            this._teardownVisibilityObserver();
            this._teardownChartZoomWheel();
            this._teardownChartResizeObserver();
            if (this.mapResizeObserver) {
                this.mapResizeObserver.disconnect();
                this.mapResizeObserver = null;
            }
            if (this.root) {
                try { this.root.dispose(); } catch (e) {}
                this.root = null;
                this._amChart = null;
                this._amLegend = null;
                this._amPieSeries = null;
            }
            try {
                this.itemCardRef.el?.removeEventListener("dd-chart-resize", this._onDdChartResize);
            } catch (e) {}
        });
        
        useEffect(() => {
            if (!this.state.inView || this.state.loading) return;
            let cancelled = false;
            const cancel = scheduleChartRender(async () => {
                if (cancelled || this.__owl__.status === 5) return;
                await this._ensureLibs();
                if (cancelled || this.__owl__.status === 5) return;
                this.renderChart();
                this.renderMap();
            });
            return () => {
                cancelled = true;
                cancel();
            };
        }, () => [this.state.data, this.props.itemType, this.state.overrideItemType, this.state.inView]);
        
        useEffect(() => {
            let intervalId = null;
            let ms = 0;
            const autoUpdate = this.props.item?.auto_update_type;
            switch(autoUpdate) {
                case 'realtime': ms = 5000; break;
                case '15s': ms = 15000; break;
                case '30s': ms = 30000; break;
                case '1m': ms = 60000; break;
                case '5m': ms = 300000; break;
            }
            if (ms > 0) {
                intervalId = setInterval(() => {
                    this.loadItemData();
                }, ms);
            }
            return () => {
                if (intervalId) clearInterval(intervalId);
            };
        }, () => [this.props.item?.auto_update_type]);
    }

    _applyPayload(payload) {
        if (!payload || typeof payload !== 'object') return;
        this.state.data = payload;
        this.state.error = payload.error || null;
        this.state.loading = false;
    }

    _setupVisibilityObserver() {
        const el = this.itemCardRef?.el;
        if (!el || typeof IntersectionObserver === 'undefined') {
            this.state.inView = true;
            return;
        }
        // Only queue chart work when the card is near/in the viewport.
        // Do NOT eagerly mark every above-the-fold card — that freezes scroll.
        this._visibilityObserver = new IntersectionObserver((entries) => {
            for (const entry of entries) {
                if (entry.isIntersecting) {
                    this.state.inView = true;
                } else if (this.root || this._amChart) {
                    // Keep charts that already built; no need to flip inView off
                }
            }
        }, { root: null, rootMargin: '80px 0px', threshold: 0.01 });
        this._visibilityObserver.observe(el);
    }

    _teardownVisibilityObserver() {
        if (this._visibilityObserver) {
            try { this._visibilityObserver.disconnect(); } catch (e) {}
            this._visibilityObserver = null;
        }
    }

    async loadItemData(override = null) {
        this.state.loading = true;
        this.state.error = false;
        
        if (this.props.previewData) {
            try {
                this.state.data = JSON.parse(this.props.previewData);
                if (this.state.data.error) {
                    this.state.error = this.state.data.error;
                }
            } catch (e) {
                this.state.error = _t("Invalid preview data.");
            }
            this.state.loading = false;
            return;
        }

        // override may be a date-filter string (legacy) or an options object
        let filter = this.props.globalDateFilter;
        let compare = this.props.globalCompare || false;
        let customDomains = this.props.customFilterDomains || [];
        if (override !== null && override !== undefined) {
            if (typeof override === 'object' && !Array.isArray(override)) {
                if (override.globalDateFilter !== undefined) filter = override.globalDateFilter;
                if (override.globalCompare !== undefined) compare = override.globalCompare;
                if (override.customFilterDomains !== undefined) customDomains = override.customFilterDomains;
            } else {
                filter = override;
            }
        }

        const drillDomain = this.state.drillStack.map((step) => step.leaf);
        try {
            const data = await this.orm.call(
                'dynamic.dashboard.item',
                'fetch_item_data',
                [this.props.itemId],
                { 
                    global_date_filter: filter,
                    global_compare: compare || false,
                    custom_filter_domains: customDomains,
                    share_token: this.props.shareToken || false,
                    drill_domain: drillDomain,
                    drill_date_type: this.state.drillDateType || false,
                    list_offset: this.state.listOffset || 0,
                }
            );
            if (data.error) {
                this.state.error = data.error;
            } else {
                this.state.data = data;
            }
        } catch (e) {
            this.state.error = 'Failed to load item data.';
        } finally {
            this.state.loading = false;
        }
    }

    getThemeColors(theme, count) {
        // Distinct primary hues so theme switches are obvious even on single-series charts
        const palettes = {
            default: ['#2563EB', '#F04343', '#16A34A', '#EAB308', '#06B6D4', '#7C3AED', '#DB2777', '#475569', '#F97316', '#0D9488'],
            cool: ['#0EA5E9', '#22D3EE', '#2DD4BF', '#38BDF8', '#6366F1', '#818CF8', '#67E8F9', '#5EEAD4'],
            warm: ['#EA580C', '#F59E0B', '#EF4444', '#F97316', '#E11D48', '#FB7185', '#FBBF24', '#DC2626'],
            neon: ['#00F0FF', '#FF2BD6', '#B8FF00', '#FFE600', '#FF5A00', '#A855F7', '#00FFC2', '#FF3B5C'],
            pastel: ['#93C5FD', '#F9A8D4', '#86EFAC', '#FDE68A', '#C4B5FD', '#FDBA74', '#99F6E4', '#FDA4AF'],
            corporate: ['#1E3A5F', '#3B82F6', '#0F766E', '#B45309', '#64748B', '#1D4ED8', '#334155', '#0369A1'],
            vibrant: ['#EC4899', '#8B5CF6', '#14B8A6', '#F59E0B', '#EF4444', '#3B82F6', '#84CC16', '#F43F5E'],
            ocean: ['#0369A1', '#0284C7', '#0EA5E9', '#38BDF8', '#7DD3FC', '#155E75', '#0891B2', '#22D3EE'],
            sunset: ['#F97316', '#FB923C', '#F43F5E', '#E11D48', '#FBBF24', '#EA580C', '#FB7185', '#F59E0B'],
        };
        const key = (theme || 'default').toString().toLowerCase();
        const colors = palettes[key] || palettes.default;
        const n = Math.max(Number(count) || 1, 1);
        const finalColors = [];
        for (let i = 0; i < n; i++) {
            finalColors.push(colors[i % colors.length]);
        }
        return finalColors;
    }

    /** Heat legend / map gradient endpoints derived from the active chart theme. */
    getThemeHeatColors(theme) {
        const ranges = {
            default: { min: '#DBEAFE', max: '#1D4ED8' },
            cool: { min: '#CFFAFE', max: '#0E7490' },
            warm: { min: '#FFEDD5', max: '#C2410C' },
            neon: { min: '#F5D0FE', max: '#A21CAF' },
            pastel: { min: '#FCE7F3', max: '#DB2777' },
            corporate: { min: '#E2E8F0', max: '#1E3A5F' },
            vibrant: { min: '#FCE7F3', max: '#BE185D' },
            ocean: { min: '#E0F2FE', max: '#075985' },
            sunset: { min: '#FFEDD5', max: '#9A3412' },
        };
        const key = (theme || 'default').toString().toLowerCase();
        return ranges[key] || ranges.default;
    }

    /**
     * Up/down (or gain/loss) colors that still change with each chart theme.
     * Used by waterfall and candlestick/OHLC.
     */
    getThemePolarityColors(theme) {
        const ranges = {
            default: { positive: '#16A34A', negative: '#DC2626', total: '#2563EB' },
            cool: { positive: '#06B6D4', negative: '#6366F1', total: '#0EA5E9' },
            warm: { positive: '#F59E0B', negative: '#EF4444', total: '#EA580C' },
            neon: { positive: '#B8FF00', negative: '#FF2BD6', total: '#00F0FF' },
            pastel: { positive: '#86EFAC', negative: '#FDA4AF', total: '#93C5FD' },
            corporate: { positive: '#0F766E', negative: '#B45309', total: '#1E3A5F' },
            vibrant: { positive: '#14B8A6', negative: '#F43F5E', total: '#8B5CF6' },
            ocean: { positive: '#22D3EE', negative: '#0369A1', total: '#0284C7' },
            sunset: { positive: '#FBBF24', negative: '#E11D48', total: '#F97316' },
        };
        const key = (theme || 'default').toString().toLowerCase();
        return ranges[key] || ranges.default;
    }

    /** Soft grid, label, and chrome colors for all AmCharts roots. */
    _polishRoot(root) {
        if (!root || !window.am5) {
            return;
        }
        try {
            root.interfaceColors.setAll({
                text: am5.color(0x374151),
                secondaryButton: am5.color(0x2B9EFF),
                secondaryButtonHover: am5.color(0x1A8AE6),
                secondaryButtonDown: am5.color(0x1570BA),
                secondaryButtonActive: am5.color(0x2B9EFF),
                secondaryButtonText: am5.color(0xffffff),
                secondaryButtonStroke: am5.color(0x2B9EFF),
                grid: am5.color(0xE5E7EB),
                alternativeBackground: am5.color(0xF8F9FA),
            });
        } catch (e) {
            /* ignore older amCharts builds */
        }
    }

    _styleAxisRenderer(renderer) {
        if (!renderer || !window.am5) {
            return;
        }
        try {
            if (renderer.grid) {
                renderer.grid.template.setAll({
                    stroke: am5.color(0xE5E7EB),
                    strokeOpacity: 1,
                    strokeDasharray: [4, 4],
                });
            }
            if (renderer.labels) {
                renderer.labels.template.setAll({
                    fill: am5.color(0x6B7280),
                    fontSize: 11,
                    fontWeight: "500",
                });
            }
        } catch (e) {
            /* ignore */
        }
    }

    /** Soften axes/grids after chart axes are created. */
    _finalizeChartStyle(root, chart) {
        this._polishRoot(root);
        if (!chart) {
            return;
        }
        // Global Tooltip toggle: strip leftover default tooltips on all series
        if (!tooltipsEnabled(this.state.data || {})) {
            try {
                const seriesList = chart.series?.values || [];
                seriesList.forEach((s) => clearSeriesTooltips(s));
            } catch (e) { /* ignore */ }
            clearSeriesTooltips(chart);
        }
        try {
            const axes = []
                .concat(chart.xAxes?.values || [])
                .concat(chart.yAxes?.values || []);
            axes.forEach((axis) => {
                this._styleAxisRenderer(axis.get("renderer"));
                if (!tooltipsEnabled(this.state.data || {})) {
                    try { axis.set("tooltip", undefined); } catch (e2) { /* */ }
                }
            });
        } catch (e) {
            /* ignore */
        }
        try {
            // Light scrollbars for a cleaner analytics shell
            const sx = chart.get("scrollbarX");
            const sy = chart.get("scrollbarY");
            if (sx) {
                sx.setAll({ height: 5, marginTop: 4, opacity: 0.55 });
            }
            if (sy) {
                sy.setAll({ width: 5, marginRight: 2, opacity: 0.55 });
            }
        } catch (e) {
            /* ignore */
        }
    }

    _makeSeriesTooltip(root, labelText) {
        return makeTooltip(root, this.state.data || {}, labelText);
    }

    /** Ensure Tooltip toggle is respected on a just-created series. */
    _syncSeriesTooltip(series, labelText) {
        if (!series) return;
        const data = this.state.data || {};
        if (!tooltipsEnabled(data)) {
            clearSeriesTooltips(series);
            return;
        }
        if (labelText) {
            attachSeriesTooltip(series, this.root, data, labelText, { mode: "auto" });
        }
    }

    /**
     * Apply theme palette and optional per-segment custom colors to an amCharts chart.
     * @param {Object} chart - amCharts chart instance
     * @param {Object} data - item payload from backend
     * @param {Array} am5data - prepared chart data rows
     * @param {String} mode - 'category' (color by label) or 'series' (color by dataset index)
     */
    applyChartColors(chart, data, am5data, mode = 'category') {
        if (!chart || !window.am5) {
            return [];
        }
        const custom = data.custom_segment_colors || {};
        const theme = data.theme || data.chart_theme || 'default';
        const seriesCount = (data.datasets && data.datasets.length) || 1;
        const rows = Array.isArray(am5data) ? am5data : [];
        const count = mode === 'series'
            ? Math.max(seriesCount, 1)
            : Math.max(rows.length, seriesCount, 1);
        const baseColors = this.getThemeColors(theme, Math.max(count, 12));
        let finalColors;
        if (mode === 'category' && rows.length) {
            finalColors = rows.map((row, i) => {
                const key = (row && (row.category || row.name || row.id)) || null;
                return (key && custom[key]) || baseColors[i % baseColors.length];
            });
        } else if (mode === 'series') {
            finalColors = (data.datasets || [{ label: data.name }]).map((ds, i) =>
                custom[ds.label] || baseColors[i % baseColors.length]
            );
        } else {
            finalColors = baseColors.slice(0, Math.max(count, 1));
        }
        if (!finalColors.length) {
            finalColors = [baseColors[0]];
        }
        try {
            const root = chart.root || this.root;
            if (!root) {
                return finalColors;
            }
            const amColors = finalColors.map((c) => am5.color(c));
            const colorSet = am5.ColorSet.new(root, {
                colors: amColors,
                reuse: true,
                step: 1,
            });
            if (typeof chart.set === 'function') {
                chart.set("colors", colorSet);
            }
            // Flow / hierarchy keep a nested nodes ColorSet
            try {
                const nodes = chart.nodes || (typeof chart.get === 'function' ? chart.get("nodes") : null);
                if (nodes && typeof nodes.set === 'function') {
                    nodes.set("colors", am5.ColorSet.new(root, {
                        colors: amColors,
                        reuse: true,
                        step: 1,
                    }));
                }
            } catch (e) { /* ignore */ }
        } catch (e) {
            console.warn("applyChartColors failed", e);
        }
        return finalColors;
    }

    /** Paint a series fill/stroke from the chart ColorSet (needed for single-series lines). */
    _applySeriesThemeColor(series, chart, index = 0) {
        if (!series || !chart || !window.am5) {
            return;
        }
        try {
            const colorSet = chart.get?.("colors");
            const fallback = this.getThemeColors(
                this.state.data?.theme || this.state.data?.chart_theme || 'default', 1
            )[0];
            const color = colorSet?.getIndex?.(index) || am5.color(fallback);
            series.set("fill", color);
            series.set("stroke", color);
        } catch (e) { /* ignore */ }
    }

    /** Coerce RPC/JSON flags so Chart Options toggles always take effect. */
    _optEnabled(value) {
        return optEnabled(value);
    }

    _addChartLegend(chart, root, data, legendData) {
        return addLegend(chart, root, data, legendData);
    }

    _addDataValueBullets(series, root, cType, data, categoryCount = 0) {
        if (!this._optEnabled(data.show_data_value) || !series) {
            return;
        }
        // Skip labels on previous-period / comparison series — they cause double overlaps
        if (series.get("name") && /previous|prior|last period/i.test(String(series.get("name")))) {
            return;
        }
        const isH = cType === "horizontalBar" || cType === "bullet" || cType === "radialBar";
        const isLine = ["line", "area", "stepLine", "smoothedLine", "radar"].includes(cType);
        const isScatter = cType === "scatter";
        const isWaterfall = cType === "waterfall";
        const isOhlc = cType === "candlestick" || cType === "ohlc";
        const count = categoryCount
            || (Array.isArray(data?.labels) ? data.labels.length : 0)
            || (Array.isArray(data?.data) ? data.data.length : 0);
        const dense = count > 10;
        const fmt = am5NumberFormat(data || {});
        const valueField = isH ? "valueX" : "valueY";
        const textTpl = `{${valueField}.formatNumber('${fmt}')}`;

        // amcharts-style: hide overlapping value labels on dense series
        if (dense) {
            try {
                series.set("minBulletDistance", isLine || isScatter ? 36 : 26);
            } catch (e) { /* ignore */ }
        }

        series.bullets.push(() => {
            const seriesFill = series.get("fill") || am5.color(0x2563eb);
            const label = am5.Label.new(root, {
                text: textTpl,
                populateText: true,
                fontSize: dense ? 9 : 10,
                fontWeight: "600",
                fill: isH ? am5.color(0xffffff) : am5.color(0x0f172a),
                centerX: isH ? am5.p100 : am5.p50,
                centerY: isH ? am5.p50 : am5.p100,
                dy: isH ? 0 : (isLine || isScatter || isOhlc ? -10 : -2),
                dx: isH ? -4 : 0,
                paddingTop: 2,
                paddingBottom: 2,
                paddingLeft: 5,
                paddingRight: 5,
                oversizedBehavior: "hide",
            });
            if (isWaterfall) {
                label.adapters.add("text", (_text, target) => {
                    try {
                        const step = target.dataItem?.dataContext?.stepValue;
                        if (step !== undefined && step !== null) {
                            return root.numberFormatter.format(Number(step) || 0, fmt);
                        }
                    } catch (e) { /* ignore */ }
                    return _text;
                });
            }
            // Pill chip behind values
            if (!isH) {
                label.set("background", am5.RoundedRectangle.new(root, {
                    fill: am5.color(0xffffff),
                    fillOpacity: 0.92,
                    stroke: seriesFill,
                    strokeWidth: 1,
                    strokeOpacity: 0.55,
                    cornerRadiusTL: 4,
                    cornerRadiusTR: 4,
                    cornerRadiusBL: 4,
                    cornerRadiusBR: 4,
                }));
            } else {
                label.set("background", am5.RoundedRectangle.new(root, {
                    fill: am5.color(0x0f172a),
                    fillOpacity: 0.35,
                    cornerRadiusTL: 3,
                    cornerRadiusTR: 3,
                    cornerRadiusBL: 3,
                    cornerRadiusBR: 3,
                }));
            }
            return am5.Bullet.new(root, {
                locationY: isH ? 0.5 : 1,
                locationX: isH ? 0.98 : 0.5,
                sprite: label,
            });
        });
    }

    _valueTooltipText(isHorizontal = false) {
        const fmt = am5NumberFormat(this.state.data || {});
        if (isHorizontal) {
            return `[bold]{name}[/]\n{categoryY}: {valueX.formatNumber('${fmt}')}`;
        }
        return `[bold]{name}[/]\n{categoryX}: {valueY.formatNumber('${fmt}')}`;
    }

    _bindSeriesClick(series, cType) {
        if (!series) return;
        const onClick = (ev) => {
            const ctx = ev.target?.dataItem?.dataContext;
            const label = ctx?.category || ctx?.categoryX || ctx?.categoryY;
            if (label != null) {
                this.onChartClick(label);
            }
        };
        if (series.columns) {
            series.columns.template.events.on("click", onClick);
        }
        if (series.slices) {
            series.slices.template.events.on("click", onClick);
        }
        // Line / area / scatter points
        series.events.on("click", (ev) => {
            const di = ev.target?.dataItem || ev.dataItem;
            const ctx = di?.dataContext;
            const label = ctx?.category || ctx?.categoryX || ctx?.categoryY;
            if (label != null) {
                this.onChartClick(label);
            }
        });
    }

    renderChart() {
        try {
            this._renderChartInner();
        } catch (e) {
            // Keep item usable (e.g. Switch Layout / refresh) — do not latch into state.error
            console.error("DynamicDashboardItem.renderChart failed", e);
        }
    }

    _renderChartInner() {
        const chartTypes = AM5_CHART_TYPES;
        if (this.state.loading || this.state.error || !chartTypes.includes(this.activeItemType)) {
            return;
        }
        
        if (!this.chartRef.el || !window.am5) {
            return;
        }

        const data = this.state.data;
        if (!data || (!data.data && !data.datasets && !data.hierarchy_data
            && !data.flow_data && !data.word_cloud_data && !data.ohlc_data
            && !data.matrix_data && !data.waterfall_data && !data.scatter_xy)) {
            // Still allow empty labels for extended charts that build from labels
            if (!data?.labels && !data?.scatter_points) {
                return;
            }
        }

        if (this.root) {
            this._teardownChartZoomWheel();
            this._teardownChartResizeObserver();
            this._clearHostZoomTransform();
            try { this.root.dispose(); } catch (e) {}
            this.root = null;
            this._amChart = null;
            this._amLegend = null;
            this._amPieSeries = null;
            this._visualZoomScale = 1;
        }

        // Size host to the grid cell BEFORE AmCharts reads dimensions
        this._syncChartHostSize();

        const root = am5.Root.new(this.chartRef.el);
        this.root = root;
        // Auto-fit to container (GridStack resize / edit layout)
        root.autoResize = true;
        root.utc = false;

        const locale = (this.state.data && this.state.data.locale) || getUserLocale();
        try {
            root.numberFormatter.setAll({
                numberFormat: "#,###.##",
                intlLocales: locale,
            });
        } catch (e) {
            root.numberFormatter.set("numberFormat", "#.#a");
        }

        applyRootThemes(root, data);
        applyNumberFormat(root, data);
        this._polishRoot(root);
        ensureExportingPlugin(data).catch(() => {});

        let cType = this.activeItemType;
        let am5data = [];
        
        if (data.labels && data.data) {
             data.labels.forEach((lbl, i) => {
                 am5data.push({ category: lbl, value: data.data[i] });
             });
        } else if (data.labels && data.datasets) {
             data.labels.forEach((lbl, i) => {
                 // Always expose `value` from the first dataset so single-series
                 // charts (pie, radar, funnel, etc.) can bind to valueField.
                 let obj = { category: lbl, value: data.datasets[0]?.data[i] ?? 0 };
                 data.datasets.forEach((ds, idx) => {
                     obj['value' + idx] = ds.data[i];
                 });
                 am5data.push(obj);
             });
        }

        const multiSeries = data.datasets && data.datasets.length > 1;
        const colorMode = multiSeries ? 'series' : 'category';
        const animDur = animationMs(data);

        // Extended chart types (Phase 2–5)
        if (renderExtendedChart({ root, cType, data, am5data, component: this })) {
            this._setupChartResizeObserver();
            this._setupChartZoomWheel();
            requestAnimationFrame(() => {
                this.resizeChart();
                requestAnimationFrame(() => {
                    this.resizeChart();
                    this._fitChartToData();
                });
            });
            return;
        }

        if (['bar', 'barLine', 'horizontalBar', 'line', 'area'].includes(cType) || (cType === 'scatter' && !data.scatter_xy)) {
            let chart = root.container.children.push(am5xy.XYChart.new(root, {
                width: am5.percent(100),
                height: am5.percent(100),
                panX: cType !== 'horizontalBar',
                panY: cType === 'horizontalBar',
                // Wheel zoom handled by `_setupChartZoomWheel` (more reliable in GridStack)
                wheelX: "none",
                wheelY: "none",
                pinchZoomX: cType !== 'horizontalBar',
                pinchZoomY: cType === 'horizontalBar',
            }));
            applyChartPadding(chart, data);
            this._amChart = chart;
            this.applyChartColors(chart, data, am5data, colorMode);
            const vc = data.visual_config || {};
            const allowPan = this._optEnabled(data.enable_pan !== undefined ? data.enable_pan : true);
            const allowZoom = this._optEnabled(data.enable_zoom !== undefined ? data.enable_zoom : true);
            const showCursor = this._optEnabled(data.show_cursor !== undefined ? data.show_cursor : true);
            // Scrollbars respect toggles (horizontal zoom bar off by default)
            if (cType === 'horizontalBar') {
                if (this._optEnabled(data.show_scrollbar_y) || this._optEnabled(data.show_scrollbar_x)) {
                    chart.set("scrollbarY", am5.Scrollbar.new(root, { orientation: "vertical" }));
                    chart.get("scrollbarY").set("width", 6);
                }
            } else if (this._optEnabled(data.show_scrollbar_x)) {
                chart.set("scrollbarX", am5.Scrollbar.new(root, { orientation: "horizontal" }));
                if (!vc.scrollbar) {
                    chart.get("scrollbarX").set("height", 6);
                }
            }
            if (this._optEnabled(data.show_scrollbar_y) && cType !== 'horizontalBar') {
                chart.set("scrollbarY", am5.Scrollbar.new(root, { orientation: "vertical" }));
            }
            
            // Drag on plot area to zoom; Reset button zooms out
            if (showCursor) {
                const cursorBehavior = !allowZoom ? "none"
                    : (cType === 'horizontalBar' ? "zoomY" : "zoomX");
                let cursor = chart.set("cursor", am5xy.XYCursor.new(root, {
                    behavior: cursorBehavior,
                }));
                applyCursorLines(cursor, data, {
                    x: cType !== 'horizontalBar',
                    y: cType === 'horizontalBar',
                });
                if (this._optEnabled(data.cursor_snap) && chart.series) {
                    try { cursor.set("snapToSeries", chart.series.values); } catch (e) { /* */ }
                }
            }
            chart.set("panX", allowPan && cType !== 'horizontalBar');
            chart.set("panY", allowPan && cType === 'horizontalBar');
            chart.set("pinchZoomX", allowZoom && cType !== 'horizontalBar');
            chart.set("pinchZoomY", allowZoom && cType === 'horizontalBar');
            
            const gridDist = numOpt(data, "min_grid_distance", am5data.length > 12 ? 40 : 30);
            let xRenderer = am5xy.AxisRendererX.new(root, {
                minGridDistance: gridDist,
                cellStartLocation: 0.1,
                cellEndLocation: 0.9,
            });
            // For horizontal bars: space categories enough that names/values don't collide;
            // AmCharts will zoom + scrollbarY handles overflow.
            const hostH = Math.max(this.chartRef.el?.clientHeight || 200, 120);
            const hBarMinDist = cType === 'horizontalBar'
                ? Math.max(22, Math.min(42, Math.floor(hostH / Math.max(am5data.length, 1))))
                : 28;
            let yRenderer = am5xy.AxisRendererY.new(root, {
                minGridDistance: hBarMinDist,
                inversed: cType === 'horizontalBar',
            });

            let xAxis, yAxis;
            
            // Dynamic check for label rotation (only when needed)
            let rotateXLabels = false;
            if (cType !== 'horizontalBar' && am5data.length > 0) {
                let maxLabelLen = Math.max(...am5data.map(d => String(d.category || '').length));
                if (am5data.length > 5 || maxLabelLen > 10) {
                    rotateXLabels = true;
                }
            }
            
            if (cType === 'horizontalBar') {
                yRenderer.labels.template.setAll({
                    maxWidth: 110,
                    oversizedBehavior: "truncate",
                    ellipsis: "…",
                    fontSize: am5data.length > 10 ? 10 : 11,
                    textAlign: "right",
                    paddingRight: 8,
                });
                // Room on the right for value labels; more left room for user names
                chart.setAll({
                    paddingLeft: 8,
                    paddingRight: 18,
                });
                yAxis = chart.yAxes.push(am5xy.CategoryAxis.new(root, {
                    categoryField: "category",
                    renderer: yRenderer,
                    tooltip: makeTooltip(root, data, "{category}"),
                }));
                yAxis.data.setAll(am5data);
                xAxis = chart.xAxes.push(am5xy.ValueAxis.new(root, {
                    renderer: xRenderer,
                    // Extra headroom so labels inside bar tips don't clip at the plot edge
                    extraMax: 0.08,
                }));
            } else {
                xAxis = chart.xAxes.push(am5xy.CategoryAxis.new(root, {
                    categoryField: "category",
                    renderer: xRenderer,
                    tooltip: makeTooltip(root, data, "{category}"),
                }));
                xAxis.data.setAll(am5data);
                const yAxisOpts = { renderer: yRenderer };
                if (vc.axis_max) yAxisOpts.max = Number(vc.axis_max);
                yAxis = chart.yAxes.push(am5xy.ValueAxis.new(root, yAxisOpts));
                
                if (rotateXLabels) {
                    xRenderer.labels.template.setAll({
                        rotation: -45,
                        centerY: am5.p50,
                        centerX: am5.p100,
                        paddingRight: 15
                    });
                }
            }
            if (cType === 'horizontalBar') {
                applyCategoryLabelStyle(yRenderer, data, { maxWidth: 110 });
            } else {
                applyCategoryLabelStyle(xRenderer, data, { forceRotate: rotateXLabels });
            }
            applyValueAxisBounds(cType === 'horizontalBar' ? xAxis : yAxis, data);
            applyGridVisibility([xAxis, yAxis], data);
            applyAxisLabelVisibility([xAxis, yAxis], data);
            
            let yAxisRight = null;
            if (cType === 'barLine') {
                yAxisRight = chart.yAxes.push(am5xy.ValueAxis.new(root, {
                    renderer: am5xy.AxisRendererY.new(root, { opposite: true }),
                }));
            }
            if (data.datasets) {
                const doStack = this._optEnabled(data.is_stacked)
                    && ['bar', 'barLine', 'horizontalBar', 'area'].includes(cType);
                const doStack100 = doStack && this._optEnabled(data.is_stacked_100);
                data.datasets.forEach((ds, idx) => {
                    const seriesStyle = ds.series_chart_type
                        || (ds.yAxisID === 'y1' ? 'line' : null)
                        || (cType === 'barLine' ? (idx === 0 ? 'column' : 'line') : null)
                        || (cType === 'line' || cType === 'area' ? 'line' : 'column');
                    const useLine = seriesStyle === 'line' || cType === 'line' || cType === 'area';
                    // Stack columns always; stack filled area series when stacked is on
                    const stackThis = doStack && (!useLine || cType === 'area');
                    const seriesYAxis = (cType === 'barLine' && useLine && yAxisRight) ? yAxisRight : yAxis;
                    let series = chart.series.push(
                        useLine ? am5xy.LineSeries.new(root, {
                            name: ds.label, xAxis: xAxis, yAxis: seriesYAxis,
                            valueYField: cType === 'horizontalBar' ? undefined : 'value' + idx,
                            categoryXField: cType === 'horizontalBar' ? undefined : "category",
                            valueXField: cType === 'horizontalBar' ? 'value' + idx : undefined,
                            categoryYField: cType === 'horizontalBar' ? "category" : undefined,
                            stacked: stackThis,
                            tooltip: this._makeSeriesTooltip(root, this._valueTooltipText(cType === 'horizontalBar'))
                        }) : am5xy.ColumnSeries.new(root, {
                            name: ds.label, xAxis: xAxis, yAxis: seriesYAxis,
                            valueYField: cType === 'horizontalBar' ? undefined : 'value' + idx,
                            categoryXField: cType === 'horizontalBar' ? undefined : "category",
                            valueXField: cType === 'horizontalBar' ? 'value' + idx : undefined,
                            categoryYField: cType === 'horizontalBar' ? "category" : undefined,
                            tooltip: this._makeSeriesTooltip(root, this._valueTooltipText(cType === 'horizontalBar')),
                            stacked: stackThis,
                        })
                    );
                    if (stackThis) {
                        series.set("stacked", true);
                        if (doStack100) {
                            const showKey = cType === 'horizontalBar' ? "valueXShow" : "valueYShow";
                            const pctKey = cType === 'horizontalBar' ? "valueXTotalPercent" : "valueYTotalPercent";
                            series.set(showKey, pctKey);
                        }
                    }
                    if (!useLine && series.columns) {
                        applyColumnAppearance(series, data, { horizontal: cType === 'horizontalBar' });
                    }
                    if (useLine) {
                        applyLineAppearance(series, root, data, {
                            fill: cType === 'area',
                            fillOpacity: 0.22,
                            bullets: false, // added below for previous-period awareness
                        });
                        // Always bind series color from theme ColorSet (single + multi)
                        this._applySeriesThemeColor(series, chart, idx);
                    }

                    // Previous-period series: dashed / lighter so it reads as comparison
                    if (ds.is_previous_period) {
                        if (series.strokes) {
                            series.strokes.template.setAll({
                                strokeWidth: 2,
                                strokeDasharray: [6, 4],
                                opacity: 0.85,
                            });
                        }
                        if (series.columns) {
                            series.columns.template.setAll({
                                opacity: 0.45,
                                strokeOpacity: 0.6,
                            });
                        }
                        if (series.fills) {
                            series.fills.template.setAll({
                                opacity: 0.25,
                            });
                        }
                    }

                    // Multi-series: color whole series from theme; single-series bars: color by category
                    if (!useLine && (multiSeries || (cType === 'barLine' && data.datasets.length === 1))) {
                        this._applySeriesThemeColor(series, chart, idx);
                    } else if (!useLine && series.columns) {
                        series.columns.template.adapters.add("fill", (fill, target) => {
                            return chart.get("colors").getIndex(series.columns.indexOf(target));
                        });
                        series.columns.template.adapters.add("stroke", (stroke, target) => {
                            return chart.get("colors").getIndex(series.columns.indexOf(target));
                        });
                    }
                    
                    if (!ds.is_previous_period) {
                        this._addDataValueBullets(series, root, cType, data, am5data.length);
                    }

                    if (useLine) {
                        // Bullets (applyLineAppearance skipped bullets above)
                        if (this._optEnabled(data.show_line_bullets !== undefined ? data.show_line_bullets : true)
                            && !ds.is_previous_period) {
                            const br = numOpt(data, "bullet_radius", 4.5);
                            series.bullets.push(function () {
                                return am5.Bullet.new(root, {
                                    sprite: am5.Circle.new(root, {
                                        radius: br,
                                        fill: series.get("fill"),
                                        stroke: root.interfaceColors.get("background"),
                                        strokeWidth: 2,
                                    })
                                });
                            });
                        }
                    }
                    if (!useLine && series.columns
                        && this._optEnabled(data.enable_heat_rules)
                        && ['bar', 'horizontalBar'].includes(cType)) {
                        const vals = am5data.map((d) => Number(d["value" + idx] ?? d.value) || 0);
                        const minH = Math.min(...vals, 0);
                        const maxH = Math.max(...vals, 1);
                        applyHeatRuleColors(
                            series, data, series.columns.template,
                            cType === "horizontalBar" ? "valueX" : "valueY",
                            minH, maxH, this
                        );
                    }

                    series.data.setAll(am5data);
                    this._bindSeriesClick(series, cType);
                });

                if (cType === 'barLine' && data.datasets.length === 1) {
                    const ds = data.datasets[0];
                    const trendColor = chart.get("colors").getIndex(1);
                    const trend = chart.series.push(am5xy.LineSeries.new(root, {
                        name: `${ds.label || data.name || 'Trend'} (line)`,
                        xAxis: xAxis,
                        yAxis: yAxisRight || yAxis,
                        valueYField: 'value0',
                        categoryXField: 'category',
                        tooltip: this._makeSeriesTooltip(root, this._valueTooltipText(false)),
                    }));
                    trend.set("fill", trendColor);
                    trend.set("stroke", trendColor);
                    trend.strokes.template.setAll({ strokeWidth: 2.75 });
                    trend.bullets.push(function () {
                        return am5.Bullet.new(root, {
                            sprite: am5.Circle.new(root, {
                                radius: 4.5,
                                fill: trend.get("fill"),
                                stroke: root.interfaceColors.get("background"),
                                strokeWidth: 2,
                            }),
                        });
                    });
                    trend.data.setAll(am5data);
                    this._bindSeriesClick(trend, cType);
                }
            } else {
                const useLine = cType === 'line' || cType === 'area';
                let series = chart.series.push(
                    useLine ? am5xy.LineSeries.new(root, {
                        name: data.name, xAxis: xAxis, yAxis: yAxis,
                        valueYField: cType === 'horizontalBar' ? undefined : 'value',
                        categoryXField: cType === 'horizontalBar' ? undefined : "category",
                        valueXField: cType === 'horizontalBar' ? 'value' : undefined,
                        categoryYField: cType === 'horizontalBar' ? "category" : undefined,
                        tooltip: this._makeSeriesTooltip(root, this._valueTooltipText(cType === 'horizontalBar'))
                    }) : am5xy.ColumnSeries.new(root, {
                        name: data.name, xAxis: xAxis, yAxis: yAxis,
                        valueYField: cType === 'horizontalBar' ? undefined : 'value',
                        categoryXField: cType === 'horizontalBar' ? undefined : "category",
                        valueXField: cType === 'horizontalBar' ? 'value' : undefined,
                        categoryYField: cType === 'horizontalBar' ? "category" : undefined,
                        tooltip: this._makeSeriesTooltip(root, this._valueTooltipText(cType === 'horizontalBar')),
                        stacked: this._optEnabled(data.is_stacked),
                    })
                );

                if ((cType === 'bar' || cType === 'horizontalBar') && series.columns) {
                    applyColumnAppearance(series, data, { horizontal: cType === 'horizontalBar' });
                    series.columns.template.adapters.add("fill", function(fill, target) {
                        return chart.get("colors").getIndex(series.columns.indexOf(target));
                    });
                    series.columns.template.adapters.add("stroke", function(stroke, target) {
                        return chart.get("colors").getIndex(series.columns.indexOf(target));
                    });
                }
                if (useLine) {
                    applyLineAppearance(series, root, data, { fill: cType === 'area', fillOpacity: 0.22 });
                    this._applySeriesThemeColor(series, chart, 0);
                }
                this._addDataValueBullets(series, root, cType, data, am5data.length);
                if (!useLine && series.columns
                    && this._optEnabled(data.enable_heat_rules)
                    && ['bar', 'horizontalBar'].includes(cType)) {
                    const vals = am5data.map((d) => Number(d.value) || 0);
                    const minH = Math.min(...vals, 0);
                    const maxH = Math.max(...vals, 1);
                    applyHeatRuleColors(
                        series, data, series.columns.template,
                        cType === "horizontalBar" ? "valueX" : "valueY",
                        minH, maxH, this
                    );
                }
                series.data.setAll(am5data);
                this._bindSeriesClick(series, cType);
            }

            this._addChartLegend(chart, root, data, chart.series.values);
            applyExportMenu(root, data);
            this._finalizeChartStyle(root, chart);
            if (animDur) { chart.appear(animDur, 80); }
            
        } else if (cType === 'scatter' && data.scatter_xy) {
            const points = data.scatter_points || [];
            let chart = root.container.children.push(am5xy.XYChart.new(root, {
                width: am5.percent(100),
                height: am5.percent(100),
                panX: this._optEnabled(data.enable_pan !== undefined ? data.enable_pan : true),
                panY: this._optEnabled(data.enable_pan !== undefined ? data.enable_pan : true),
                wheelX: "none",
                wheelY: "none",
                pinchZoomX: this._optEnabled(data.enable_zoom !== undefined ? data.enable_zoom : true),
                pinchZoomY: this._optEnabled(data.enable_zoom !== undefined ? data.enable_zoom : true),
            }));
            applyChartPadding(chart, data, { top: 8, right: 12, bottom: 4, left: 4 });
            this._amChart = chart;
            this.applyChartColors(chart, data, points, 'series');
            if (this._optEnabled(data.show_scrollbar_x)) {
                chart.set("scrollbarX", am5.Scrollbar.new(root, { orientation: "horizontal" }));
            }
            if (this._optEnabled(data.show_scrollbar_y)) {
                chart.set("scrollbarY", am5.Scrollbar.new(root, { orientation: "vertical" }));
            }
            if (this._optEnabled(data.show_cursor !== undefined ? data.show_cursor : true)) {
                const cursor = chart.set("cursor", am5xy.XYCursor.new(root, { behavior: "zoomXY" }));
                applyCursorLines(cursor, data, { x: true, y: true });
            }
            let xAxis = chart.xAxes.push(am5xy.ValueAxis.new(root, {
                renderer: am5xy.AxisRendererX.new(root, {
                    minGridDistance: numOpt(data, "min_grid_distance", 40),
                }),
                tooltip: makeTooltip(root, data, `{valueX.formatNumber('${am5NumberFormat(data)}')}`),
            }));
            let yAxis = chart.yAxes.push(am5xy.ValueAxis.new(root, {
                renderer: am5xy.AxisRendererY.new(root, {}),
                tooltip: makeTooltip(root, data, `{valueY.formatNumber('${am5NumberFormat(data)}')}`),
            }));
            applyValueAxisBounds(xAxis, data);
            applyValueAxisBounds(yAxis, data);
            applyGridVisibility([xAxis, yAxis], data);
            applyAxisLabelVisibility([xAxis, yAxis], data);
            let series = chart.series.push(am5xy.LineSeries.new(root, {
                name: (data.datasets && data.datasets[0] && data.datasets[0].label) || data.name,
                xAxis, yAxis,
                valueXField: "x",
                valueYField: "y",
                tooltip: makeTooltip(root, data, `{category}\nX: {valueX.formatNumber('${am5NumberFormat(data)}')} Y: {valueY.formatNumber('${am5NumberFormat(data)}')}`),
            }));
            series.strokes.template.set("visible", false);
            series.bullets.push(function () {
                return am5.Bullet.new(root, {
                    sprite: am5.Circle.new(root, {
                        radius: numOpt(data, "bullet_radius", 6),
                        fill: series.get("fill"),
                        fillOpacity: numOpt(data, "scatter_fill_opacity", 0.85),
                        stroke: root.interfaceColors.get("background"),
                        strokeWidth: 1,
                    }),
                });
            });
            series.data.setAll(points);
            this._addDataValueBullets(series, root, 'scatter', data, points.length);
            this._addChartLegend(chart, root, data, chart.series.values);
            applyExportMenu(root, data);
            this._finalizeChartStyle(root, chart);
            if (animDur) { chart.appear(animDur, 80); }

        } else if (cType === 'pie' || cType === 'doughnut') {
            const hostEl = this.chartRef.el;
            const hostW = hostEl?.clientWidth || 300;
            const hostH = hostEl?.clientHeight || 240;
            const sliceCount = am5data.length;
            // Prefer legend + inside % labels so all values stay visible without clipping
            const useOutsideLabels = sliceCount <= 5 && Math.min(hostW, hostH) >= 280;
            const legendHidden = this._optEnabled(data.hide_legend) || data.legend_position === 'none';
            const legendPos = legendHidden
                ? 'none'
                : (data.legend_position || (hostW > hostH * 1.15 && hostW > 360 ? 'right' : 'bottom'));
            const useSideLegend = legendPos === 'left' || legendPos === 'right';

            const defaultRadius = useSideLegend ? 78 : (useOutsideLabels ? 62 : 70);
            const pieConfig = {
                width: am5.percent(100),
                height: am5.percent(100),
                layout: useSideLegend ? root.horizontalLayout : root.verticalLayout,
                innerRadius: cType === 'doughnut'
                    ? am5.percent(numOpt(data, "pie_inner_radius", 50))
                    : 0,
                // Keep pie inside the cell — high radius looks "zoomed" in small widgets
                radius: am5.percent(numOpt(data, "pie_radius", defaultRadius)),
                paddingTop: 4,
                paddingBottom: 4,
                paddingLeft: 4,
                paddingRight: 4,
            };
            if (this._optEnabled(data.is_semi_circle)) {
                pieConfig.startAngle = 180;
                pieConfig.endAngle = 360;
            } else {
                pieConfig.startAngle = numOpt(data, "pie_start_angle", -90);
                pieConfig.endAngle = numOpt(data, "pie_end_angle", 270);
            }
            let chart = root.container.children.push(am5percent.PieChart.new(root, pieConfig));
            applyChartPadding(chart, data, { top: 4, right: 4, bottom: 4, left: 4 });
            this._amChart = chart;
            this.applyChartColors(chart, data, am5data, 'category');
            let series = chart.series.push(am5percent.PieSeries.new(root, {
                valueField: "value",
                categoryField: "category",
                alignLabels: useOutsideLabels,
                ...(this._optEnabled(data.is_semi_circle) ? { startAngle: 180, endAngle: 360 } : {}),
            }));
            this._amPieSeries = series;
            series.slices.template.adapters.add("fill", (fill, target) => {
                return chart.get("colors").getIndex(series.slices.indexOf(target));
            });
            const pieFmt = am5NumberFormat(data);
            series.slices.template.setAll({
                tooltipText: this._optEnabled(data.show_tooltip !== undefined ? data.show_tooltip : true)
                    ? `{category}: {value.formatNumber('${pieFmt}')} ({valuePercentTotal.formatNumber('#.0')}%)`
                    : undefined,
                stroke: am5.color(0xffffff),
                strokeWidth: numOpt(data, "slice_stroke_width", 2),
                strokeOpacity: 1,
                cornerRadius: numOpt(data, "column_corner_radius", 4),
            });
            if (!tooltipsEnabled(data)) {
                clearSeriesTooltips(series);
            }
            series.slices.template.states.create("hover", {
                scale: numOpt(data, "slice_hover_scale", 1.04),
                shiftRadius: 4,
            });

            const labelPos = data.label_position || "auto";
            if (!this._optEnabled(data.show_data_value) || labelPos === "none") {
                series.labels.template.set("forceHidden", true);
                series.ticks.template.set("forceHidden", true);
            } else if (labelPos === "outside" || (labelPos === "auto" && useOutsideLabels)) {
                series.labels.template.setAll({
                    text: `{category}: {value.formatNumber('${pieFmt}')}`,
                    textType: "circular",
                    oversizedBehavior: "truncate",
                    maxWidth: 110,
                    fontSize: 11,
                    fontWeight: "500",
                });
                series.ticks.template.setAll({
                    visible: this._optEnabled(data.show_slice_ticks !== undefined ? data.show_slice_ticks : true),
                });
            } else if (labelPos === "inside" || labelPos === "auto") {
                series.labels.template.setAll({
                    text: `{value.formatNumber('${pieFmt}')}`,
                    textType: "radial",
                    centerX: am5.percent(100),
                    populateText: true,
                    fontSize: 11,
                    fontWeight: "600",
                    fill: am5.color(0xffffff),
                });
                series.ticks.template.setAll({ forceHidden: true });
                series.labels.template.adapters.add("forceHidden", (_hidden, target) => {
                    const di = target.dataItem;
                    if (!di) return true;
                    return (di.get("valuePercentTotal") || 0) < 3;
                });
            } else {
                series.labels.template.set("forceHidden", true);
                series.ticks.template.set("forceHidden", true);
            }

            series.data.setAll(am5data);
            applySliceGrouper(series, root, data);
            series.slices.template.events.on("click", (ev) => {
                this.onChartClick(ev.target.dataItem.dataContext.category);
            });
            if (!legendHidden) {
                // Honor explicit legend_position; fall back to auto side/bottom layout
                const pieLegendData = Object.assign({}, data, { legend_position: legendPos });
                const legend = this._addChartLegend(chart, root, pieLegendData, series.dataItems);
                this._amLegend = legend;
                if (legend) {
                    legend.labels.template.setAll({
                        fontSize: 11,
                        fontWeight: "500",
                        fill: am5.color(0x6B7280),
                        oversizedBehavior: "truncate",
                        maxWidth: useSideLegend ? 160 : 150,
                    });
                    legend.valueLabels.template.setAll({
                        fontSize: 11,
                        fontWeight: "600",
                        fill: am5.color(0x374151),
                        text: `{value.formatNumber('${pieFmt}')} ({valuePercentTotal.formatNumber('#.0')}%)`,
                        oversizedBehavior: "truncate",
                        maxWidth: useSideLegend ? 120 : 130,
                    });
                    legend.markers.template.setAll({ width: 11, height: 11 });
                    try {
                        legend.set("verticalScrollbar", am5.Scrollbar.new(root, {
                            orientation: "vertical",
                        }));
                    } catch (e) { /* ignore */ }
                }
            }
            applyExportMenu(root, data);
            this._finalizeChartStyle(root, chart);
            if (animDur) { series.appear(animDur, 80); }
            if (animDur) { chart.appear(animDur, 80); }
            
        } else if (cType === 'polarArea' || cType === 'radar' || cType === 'flower') {
            let chart = root.container.children.push(am5radar.RadarChart.new(root, {
                width: am5.percent(100),
                height: am5.percent(100),
                panX: false,
                panY: false,
                wheelX: "none",
                wheelY: "none",
                innerRadius: cType === 'flower'
                    ? am5.percent(numOpt(data, "pie_inner_radius", 20))
                    : 0,
                radius: am5.percent(numOpt(data, "pie_radius", 72)),
                paddingTop: 8,
                paddingBottom: 8,
                paddingLeft: 8,
                paddingRight: 8,
            }));
            this._amChart = chart;
            this.applyChartColors(chart, data, am5data, 'category');
            let xRenderer = am5radar.AxisRendererCircular.new(root, {});
            xRenderer.labels.template.setAll({ radius: 10 });
            let xAxis = chart.xAxes.push(am5xy.CategoryAxis.new(root, { categoryField: "category", renderer: xRenderer }));
            xAxis.data.setAll(am5data);
            let yRenderer = am5radar.AxisRendererRadial.new(root, {});
            let yAxis = chart.yAxes.push(am5xy.ValueAxis.new(root, { renderer: yRenderer }));
            applyGridVisibility([xAxis, yAxis], data);
            if (this._optEnabled(data.show_cursor !== undefined ? data.show_cursor : true)) {
                const cursor = chart.set("cursor", am5radar.RadarCursor.new(root, { behavior: "none" }));
                try { cursor.lineY.set("visible", false); } catch (e) { /* ignore */ }
            }

            let series;
            if (cType === 'radar') {
                // Classic radar: line + filled area
                series = chart.series.push(am5radar.RadarLineSeries.new(root, {
                    name: data.name, xAxis, yAxis,
                    valueYField: "value", categoryXField: "category",
                    tooltip: this._makeSeriesTooltip(root, this._valueTooltipText(false)),
                }));
                this._applySeriesThemeColor(series, chart, 0);
                if (series.strokes) {
                    series.strokes.template.setAll({
                        strokeWidth: numOpt(data, "line_stroke_width", 2.5),
                    });
                }
                if (series.fills) {
                    series.fills.template.setAll({
                        visible: true,
                        fillOpacity: numOpt(data, "area_fill_opacity", 0.25),
                    });
                }
                if (this._optEnabled(data.show_line_bullets !== undefined ? data.show_line_bullets : true)) {
                    const br = numOpt(data, "bullet_radius", 4);
                    series.bullets.push(() => am5.Bullet.new(root, {
                        sprite: am5.Circle.new(root, {
                            radius: br,
                            fill: series.get("fill"),
                        }),
                    }));
                }
            } else {
                series = chart.series.push(am5radar.RadarColumnSeries.new(root, {
                    name: data.name, xAxis, yAxis,
                    valueYField: "value", categoryXField: "category",
                    tooltip: this._makeSeriesTooltip(root, this._valueTooltipText(false)),
                }));
                if (cType === 'flower' && series.columns) {
                    series.columns.template.setAll({
                        cornerRadius: 15,
                        cornerRadiusTL: 15, cornerRadiusTR: 15, cornerRadiusBL: 15, cornerRadiusBR: 15,
                        fillOpacity: 0.85, strokeOpacity: 0, width: am5.percent(95),
                    });
                } else if (series.columns) {
                    // polarArea
                    series.columns.template.setAll({
                        strokeOpacity: 0,
                        fillOpacity: 0.9,
                        width: am5.percent(100),
                    });
                }
                if (series.columns) {
                    series.columns.template.adapters.add("fill", (fill, target) =>
                        chart.get("colors").getIndex(series.columns.indexOf(target)));
                    series.columns.template.adapters.add("stroke", (stroke, target) =>
                        chart.get("colors").getIndex(series.columns.indexOf(target)));
                    series.columns.template.events.on("click", (ev) => {
                        this.onChartClick(ev.target.dataItem.dataContext.category);
                    });
                }
            }
            this._addDataValueBullets(series, root, cType, data, am5data.length);
            series.data.setAll(am5data);
            this._bindSeriesClick(series, cType);
            if (animDur) { series.appear(animDur); }
            this._addChartLegend(chart, root, data, chart.series.values);
            applyExportMenu(root, data);
            this._finalizeChartStyle(root, chart);
            if (animDur) { chart.appear(animDur, 80); }
        } else if (cType === 'radialBar') {
            let chart = root.container.children.push(am5radar.RadarChart.new(root, {
                width: am5.percent(100),
                height: am5.percent(100),
                panX: false, panY: false, wheelX: "none", wheelY: "none",
                innerRadius: am5.percent(numOpt(data, "pie_inner_radius", 30)),
                startAngle: -90, endAngle: 270,
                radius: am5.percent(numOpt(data, "pie_radius", 72)),
                paddingTop: 8,
                paddingBottom: 8,
                paddingLeft: 8,
                paddingRight: 8,
            }));
            this._amChart = chart;
            this.applyChartColors(chart, data, am5data, 'category');
            if (this._optEnabled(data.show_cursor !== undefined ? data.show_cursor : true)) {
                let cursor = chart.set("cursor", am5radar.RadarCursor.new(root, { behavior: "none" }));
                cursor.lineY.set("visible", false);
            }

            let xRenderer = am5radar.AxisRendererCircular.new(root, {});
            xRenderer.labels.template.setAll({ forceHidden: true });
            xRenderer.grid.template.setAll({ forceHidden: true });
            let xAxis = chart.xAxes.push(am5xy.ValueAxis.new(root, {
                renderer: xRenderer, min: 0,
                extraMax: 0.1
            }));

            let yRenderer = am5radar.AxisRendererRadial.new(root, { minGridDistance: 20 });
            yRenderer.labels.template.setAll({ centerX: am5.p100, fontSize: "0.8em" });
            if (!this._optEnabled(data.show_grid !== undefined ? data.show_grid : true)) {
                yRenderer.grid.template.setAll({ forceHidden: true });
            }
            let yAxis = chart.yAxes.push(am5xy.CategoryAxis.new(root, {
                categoryField: "category", renderer: yRenderer
            }));
            yAxis.data.setAll(am5data);

            let series = chart.series.push(am5radar.RadarColumnSeries.new(root, {
                name: data.name, xAxis: xAxis, yAxis: yAxis,
                valueXField: "value", categoryYField: "category",
                tooltip: this._makeSeriesTooltip(root, this._valueTooltipText(true)),
            }));
            series.columns.template.setAll({
                cornerRadius: 20, cornerRadiusTL: 20, cornerRadiusTR: 20,
                cornerRadiusBL: 20, cornerRadiusBR: 20,
                width: am5.percent(80), strokeOpacity: 0
            });
            series.columns.template.adapters.add("fill", function(fill, target) { return chart.get("colors").getIndex(series.columns.indexOf(target)); });
            series.columns.template.events.on("click", (ev) => {
                this.onChartClick(ev.target.dataItem.dataContext.category);
            });
            this._addDataValueBullets(series, root, "horizontalBar", data, am5data.length);
            series.data.setAll(am5data);
            if (animDur) { series.appear(animDur); }
            this._addChartLegend(chart, root, data, chart.series.values);
            applyExportMenu(root, data);
            this._finalizeChartStyle(root, chart);
            if (animDur) { chart.appear(animDur, 80); }
        } else if (cType === 'funnel') {
            let chart = root.container.children.push(am5percent.SlicedChart.new(root, {
                width: am5.percent(100),
                height: am5.percent(100),
                layout: root.verticalLayout,
            }));
            applyChartPadding(chart, data, { top: 8, right: 8, bottom: 8, left: 8 });
            this._amChart = chart;
            this.applyChartColors(chart, data, am5data, 'category');
            let series = chart.series.push(am5percent.FunnelSeries.new(root, {
                alignLabels: true,
                orientation: data.funnel_orientation || "vertical",
                valueField: "value",
                categoryField: "category",
                bottomRatio: numOpt(data, "funnel_bottom_ratio", 0.1),
            }));
            series.slices.template.adapters.add("fill", (fill, target) => {
                return chart.get("colors").getIndex(series.slices.indexOf(target));
            });
            series.slices.template.setAll({
                stroke: am5.color(0xffffff),
                strokeWidth: 1.5,
                strokeOpacity: 1,
            });
            series.data.setAll(am5data);
            
            if (this._optEnabled(data.show_data_value)) {
                const funnelFmt = am5NumberFormat(data);
                series.labels.template.setAll({
                    text: `{category}: {value.formatNumber('${funnelFmt}')}`,
                    populateText: true,
                    fill: am5.color(0x374151),
                    fontSize: 11,
                    fontWeight: "600",
                });
            } else {
                series.labels.template.set("forceHidden", true);
            }
            if (this._optEnabled(data.show_tooltip !== undefined ? data.show_tooltip : true)) {
                const funnelFmt = am5NumberFormat(data);
                series.slices.template.set("tooltipText",
                    `{category}: {value.formatNumber('${funnelFmt}')}`);
            } else {
                clearSeriesTooltips(series);
                series.slices.template.set("tooltipText", undefined);
            }

            series.slices.template.events.on("click", (ev) => {
                this.onChartClick(ev.target.dataItem.dataContext.category);
            });
            this._addChartLegend(chart, root, data, series.dataItems);
            applyExportMenu(root, data);
            this._finalizeChartStyle(root, chart);
            if (animDur) { series.appear(animDur, 80); }
        } else if (cType === 'bullet') {
            const allowZoom = this._optEnabled(data.enable_zoom !== undefined ? data.enable_zoom : true);
            const showCursor = this._optEnabled(data.show_cursor !== undefined ? data.show_cursor : true);
            let chart = root.container.children.push(am5xy.XYChart.new(root, {
                width: am5.percent(100),
                height: am5.percent(100),
                panX: this._optEnabled(data.enable_pan !== undefined ? data.enable_pan : true),
                panY: false,
                wheelX: "none",
                wheelY: "none",
                pinchZoomX: allowZoom,
                paddingTop: 8,
                paddingRight: 12,
                paddingBottom: 4,
                paddingLeft: 4,
            }));
            this._amChart = chart;
            this.applyChartColors(chart, data, am5data, 'category');
            if (this._optEnabled(data.show_scrollbar_x)) {
                chart.set("scrollbarX", am5.Scrollbar.new(root, { orientation: "horizontal" }));
                chart.get("scrollbarX").set("height", 6);
            }
            if (showCursor) {
                chart.set("cursor", am5xy.XYCursor.new(root, { behavior: allowZoom ? "zoomX" : "none" }));
            }
            let yRenderer = am5xy.AxisRendererY.new(root, { minGridDistance: 30 });
            let yAxis = chart.yAxes.push(am5xy.CategoryAxis.new(root, { categoryField: "category", renderer: yRenderer }));
            yAxis.data.setAll(am5data);
            let xRenderer = am5xy.AxisRendererX.new(root, { minGridDistance: 30 });
            let xAxis = chart.xAxes.push(am5xy.ValueAxis.new(root, { renderer: xRenderer }));
            applyGridVisibility([xAxis, yAxis], data);

            let series = chart.series.push(am5xy.ColumnSeries.new(root, {
                name: data.name, xAxis: xAxis, yAxis: yAxis,
                valueXField: "value", categoryYField: "category",
                tooltip: this._makeSeriesTooltip(root, this._valueTooltipText(true)),
            }));
            series.columns.template.setAll({
                height: am5.percent(68),
                cornerRadiusBR: 6,
                cornerRadiusTR: 6,
                strokeOpacity: 0,
            });
            series.columns.template.adapters.add("fill", function(fill, target) { return chart.get("colors").getIndex(series.columns.indexOf(target)); });
            
            series.columns.template.events.on("click", (ev) => {
                this.onChartClick(ev.target.dataItem.dataContext.category);
            });
            this._addDataValueBullets(series, root, "bullet", data, am5data.length);
            series.data.setAll(am5data);

            if (data.enable_target && data.target_value) {
                let rangeDataItem = xAxis.makeDataItem({
                    value: data.target_value
                });
                let range = xAxis.createAxisRange(rangeDataItem);
                range.get("grid").setAll({
                    strokeOpacity: 1,
                    stroke: am5.color(0xdc3545),
                    strokeWidth: 3
                });
                range.get("label").setAll({
                    text: "Target (" + data.target_value + ")",
                    fill: am5.color(0xdc3545),
                    inside: true,
                    centerY: am5.p100
                });
            }

            
            applyExportMenu(root, data);
            this._finalizeChartStyle(root, chart);
            if (animDur) { chart.appear(animDur, 80); }
        }

        this._setupChartResizeObserver();
        this._setupChartZoomWheel();
        // Defer so GridStack / flex layout has final dimensions, then fit view
        requestAnimationFrame(() => {
            this.resizeChart();
            requestAnimationFrame(() => {
                this.resizeChart();
                this._fitChartToData();
            });
        });
    }

    /**
     * Reset zoom to the layout-fitted normal view (Reset Zoom button / initial load).
     * Do NOT call from resize — that cancels intentional axis zoom.
     */
    _fitChartToData() {
        this._visualZoomScale = 1;
        this._clearHostZoomTransform();
        try {
            const chart = this._amChart;
            if (!chart || !window.am5) {
                this._refitChartToLayout();
                return;
            }
            if (AM5_MAP_TYPES.includes(this.activeItemType)) {
                if (typeof chart.goHome === "function") {
                    chart.goHome(0);
                } else if (typeof chart.zoomOut === "function") {
                    chart.zoomOut();
                }
                this._refitChartToLayout();
                return;
            }
            // Clear any leftover amCharts scale positioning from older zoom logic
            try {
                chart.setAll({
                    scale: 1,
                    x: undefined,
                    y: undefined,
                    centerX: undefined,
                    centerY: undefined,
                });
            } catch (e) {
                try { chart.set("scale", 1); } catch (e2) { /* */ }
            }
            if (typeof chart.zoomOut === "function" && !this._chartHasAxes(chart)) {
                try { chart.zoomOut(); } catch (e) { /* */ }
            }
            const resetAxis = (axis) => {
                if (!axis) return;
                try {
                    if (typeof axis.zoom === "function") {
                        axis.zoom(0, 1);
                    }
                    if (typeof axis.zoomToIndexes === "function" && axis.dataItems?.length) {
                        axis.zoomToIndexes(0, axis.dataItems.length);
                    }
                } catch (e) {}
            };
            if (chart.xAxes?.each) chart.xAxes.each(resetAxis);
            else (chart.xAxes?.values || []).forEach(resetAxis);
            if (chart.yAxes?.each) chart.yAxes.each(resetAxis);
            else (chart.yAxes?.values || []).forEach(resetAxis);
            this._refitChartToLayout();
        } catch (e) {
            this._refitChartToLayout();
        }
    }

    /** Re-measure host and restore chart to the current grid cell size. */
    _refitChartToLayout() {
        try {
            this._syncChartHostSize();
            this._adaptCircularChartToHost();
            if (this.root && typeof this.root.resize === "function") {
                this.root.resize();
            }
        } catch (e) { /* */ }
    }

    get supportsChartZoom() {
        const data = this.state.data || {};
        if (!this._optEnabled(data.enable_zoom !== undefined ? data.enable_zoom : true)) {
            return false;
        }
        return this.isAmChartsVisual;
    }

    get activeItemType() {
        let t = this.state.overrideItemType || this.props.itemType;
        if (Array.isArray(t)) return t[0];
        return t;
    }

    get isAmChartsVisual() {
        const t = this.activeItemType;
        return AM5_CHART_TYPES.includes(t) || AM5_MAP_TYPES.includes(t);
    }

    _chartHasAxes(chart = this._amChart) {
        if (!chart) return false;
        const xLen = chart.xAxes?.length ?? chart.xAxes?.values?.length ?? 0;
        const yLen = chart.yAxes?.length ?? chart.yAxes?.values?.length ?? 0;
        return xLen > 0 || yLen > 0;
    }

    _isCircularZoomType(type = this.activeItemType) {
        return [
            'pie', 'doughnut', 'polarArea', 'radar', 'flower', 'radialBar', 'gauge',
        ].includes(type);
    }

    _getZoomHostEl() {
        return this.chartRef?.el || this.mapRef?.el || null;
    }

    _getZoomTransformEl() {
        const host = this._getZoomHostEl();
        if (!host) return null;
        // AmCharts root wrapper fills the host; scale that inside overflow:hidden
        return host.querySelector(":scope > div") || host.firstElementChild || host;
    }

    _clearHostZoomTransform() {
        const host = this._getZoomHostEl();
        const el = this._getZoomTransformEl();
        [host, el].filter(Boolean).forEach((node) => {
            try {
                node.style.removeProperty("transform");
                node.style.removeProperty("transform-origin");
            } catch (e) { /* */ }
        });
    }

    /**
     * Layout-bounded zoom: magnify content inside the chart cell (clipped).
     * Scale 1 = normal fit to layout. Never changes amCharts chart size props.
     */
    _zoomHostInLayout(multiplier) {
        const current = this._visualZoomScale || 1;
        // Keep zoom within layout: not smaller than fitted, not extreme
        const next = Math.min(1.75, Math.max(1, +(current * multiplier).toFixed(3)));
        if (Math.abs(next - current) < 0.001) {
            if (next <= 1) {
                this._visualZoomScale = 1;
                this._clearHostZoomTransform();
            }
            return false;
        }
        this._visualZoomScale = next;
        const el = this._getZoomTransformEl();
        if (!el) return false;
        if (next <= 1) {
            this._visualZoomScale = 1;
            this._clearHostZoomTransform();
            this._refitChartToLayout();
            return true;
        }
        el.style.transformOrigin = "center center";
        el.style.transform = `scale(${next})`;
        return true;
    }

    _eachZoomAxis(callback) {
        const chart = this._amChart;
        if (!chart || !callback || !this._chartHasAxes(chart)) return;
        const itemType = this.activeItemType;
        const visit = (axis) => {
            if (axis) callback(axis);
        };

        if (itemType === 'horizontalBar') {
            // Categories are on Y for horizontal bars
            if (chart.yAxes?.each) chart.yAxes.each(visit);
            else (chart.yAxes?.values || []).forEach(visit);
            return;
        }

        if (chart.xAxes?.each) chart.xAxes.each(visit);
        else (chart.xAxes?.values || []).forEach(visit);

        // Dual-axis zoom for scatter / heat / OHLC charts
        if (['scatter', 'heatmap', 'matrixHeatmap', 'candlestick', 'ohlc'].includes(itemType)) {
            if (chart.yAxes?.each) chart.yAxes.each(visit);
            else (chart.yAxes?.values || []).forEach(visit);
        }
    }

    _zoomSingleAxis(axis, factor) {
        if (!axis || typeof axis.zoom !== "function") return false;
        try {
            axis.set("zoomable", true);
            // Prefer index zoom for category axes (visible even with few categories)
            const dataItems = axis.dataItems;
            if (dataItems && dataItems.length > 1 && typeof axis.zoomToIndexes === "function") {
                let startIndex = axis.getPrivate?.("startIndex");
                let endIndex = axis.getPrivate?.("endIndex");
                if (startIndex == null) startIndex = 0;
                if (endIndex == null) endIndex = dataItems.length;
                const count = Math.max(1, endIndex - startIndex);
                const mid = startIndex + count / 2;
                // Keep enough categories visible so the chart does not look empty/weird
                const minCount = Math.max(2, Math.ceil(dataItems.length * 0.2));
                let newCount = Math.max(1, Math.round(count * factor));
                if (factor < 1 && newCount >= count) {
                    newCount = Math.max(1, count - 1);
                }
                if (factor > 1 && newCount <= count) {
                    newCount = Math.min(dataItems.length, count + 1);
                }
                newCount = Math.min(dataItems.length, Math.max(minCount, newCount));
                if (factor < 1 && newCount >= count) {
                    return false; // already at max useful zoom-in
                }
                let newStart = Math.round(mid - newCount / 2);
                let newEnd = newStart + newCount;
                if (newStart < 0) {
                    newEnd -= newStart;
                    newStart = 0;
                }
                if (newEnd > dataItems.length) {
                    newStart = Math.max(0, newStart - (newEnd - dataItems.length));
                    newEnd = dataItems.length;
                }
                if (newStart === startIndex && newEnd === endIndex) {
                    return false;
                }
                axis.zoomToIndexes(newStart, newEnd);
                return true;
            }

            const start = axis.get("start", 0) ?? 0;
            const end = axis.get("end", 1) ?? 1;
            const mid = (start + end) / 2;
            // Cap zoom-in so value axes never collapse to a hairline view
            const minHalf = 0.08;
            let half = ((end - start) / 2) * factor;
            half = Math.max(minHalf, Math.min(0.5, half));
            if (factor < 1 && (end - start) <= minHalf * 2 + 0.001) {
                return false;
            }
            let nextStart = mid - half;
            let nextEnd = mid + half;
            if (nextStart < 0) {
                nextEnd = Math.min(1, nextEnd - nextStart);
                nextStart = 0;
            }
            if (nextEnd > 1) {
                nextStart = Math.max(0, nextStart - (nextEnd - 1));
                nextEnd = 1;
            }
            if (Math.abs(nextStart - start) < 1e-6 && Math.abs(nextEnd - end) < 1e-6) {
                return false;
            }
            axis.zoom(nextStart, nextEnd, 200);
            return true;
        } catch (e) {
            console.warn("chart axis zoom failed", e);
            return false;
        }
    }

    _zoomAxes(factor) {
        const chart = this._amChart;
        if (!chart || !this.supportsChartZoom || !this._chartHasAxes(chart)) return false;
        let any = false;
        this._eachZoomAxis((axis) => {
            if (this._zoomSingleAxis(axis, factor)) {
                any = true;
            }
        });
        return any;
    }

    _zoomMap(direction) {
        const chart = this._amChart;
        if (!chart || !AM5_MAP_TYPES.includes(this.activeItemType)) {
            return false;
        }
        try {
            if (direction > 0 && typeof chart.zoomIn === "function") {
                chart.zoomIn();
                return true;
            }
            if (direction < 0 && typeof chart.zoomOut === "function") {
                chart.zoomOut();
                return true;
            }
        } catch (e) {
            console.warn("map zoom failed", e);
        }
        return false;
    }

    zoomChartIn() {
        if (!this.supportsChartZoom) return;
        if (this._zoomMap(1)) return;
        // XY charts: zoom data range inside the same layout size
        if (this._chartHasAxes()) {
            this._zoomAxes(0.7);
            return;
        }
        // Pie / hierarchy / etc.: magnify inside the cell (layout-clipped)
        this._zoomHostInLayout(1.12);
    }

    zoomChartOut() {
        if (!this.supportsChartZoom) return;
        if (this._zoomMap(-1)) return;

        if (this._chartHasAxes()) {
            let nearFull = true;
            this._eachZoomAxis((axis) => {
                const start = axis.get("start", 0) ?? 0;
                const end = axis.get("end", 1) ?? 1;
                if (end - start < 0.92) {
                    nearFull = false;
                }
                const dataItems = axis.dataItems;
                if (dataItems && dataItems.length > 1) {
                    const startIndex = axis.getPrivate?.("startIndex") ?? 0;
                    const endIndex = axis.getPrivate?.("endIndex") ?? dataItems.length;
                    if (endIndex - startIndex < dataItems.length) {
                        nearFull = false;
                    }
                }
            });
            if (nearFull) {
                this.resetChartZoom();
                return;
            }
            this._zoomAxes(1.35);
            return;
        }

        const scale = this._visualZoomScale || 1;
        if (scale <= 1.02) {
            this.resetChartZoom();
            return;
        }
        this._zoomHostInLayout(1 / 1.12);
    }

    resetChartZoom() {
        this._fitChartToData();
    }

    _teardownChartZoomWheel() {
        const hosts = [this.chartRef?.el, this.mapRef?.el].filter(Boolean);
        if (this._onChartWheel) {
            hosts.forEach((host) => {
                try { host.removeEventListener("wheel", this._onChartWheel); } catch (e) {}
            });
        }
        this._onChartWheel = null;
        this._zoomWheelHost = null;
    }

    _setupChartZoomWheel() {
        this._teardownChartZoomWheel();
        if (!this.supportsChartZoom) return;
        // MapChart already handles wheel zoom natively when enable_zoom is on
        if (AM5_MAP_TYPES.includes(this.activeItemType)) return;
        const host = this.chartRef?.el || this.mapRef?.el;
        if (!host) return;
        this._zoomWheelHost = host;
        this._onChartWheel = (ev) => {
            if (!this._amChart || !this.supportsChartZoom) return;
            // Zoom with wheel over the chart (prevents page scroll while hovering)
            ev.preventDefault();
            ev.stopPropagation();
            if (ev.deltaY < 0) {
                this.zoomChartIn();
            } else if (ev.deltaY > 0) {
                this.zoomChartOut();
            }
        };
        host.addEventListener("wheel", this._onChartWheel, { passive: false });
    }

    _teardownChartResizeObserver() {
        if (this._chartResizeObserver) {
            try { this._chartResizeObserver.disconnect(); } catch (e) {}
            this._chartResizeObserver = null;
        }
        if (this._chartResizeRaf) {
            cancelAnimationFrame(this._chartResizeRaf);
            this._chartResizeRaf = null;
        }
    }

    _syncChartHostSize() {
        const host = this.chartRef?.el || this.mapRef?.el;
        const card = this.itemCardRef?.el;
        if (!host) return { w: 0, h: 0 };

        const gridItem = card?.closest?.(".grid-stack-item") || host.closest?.(".grid-stack-item");
        const itemContent = gridItem?.querySelector?.(".grid-stack-item-content") || gridItem;
        const container = host.parentElement; // .chart-container
        const cardBody = card?.querySelector?.(".dd-chart-card-body") || card?.querySelector?.(".card-body");
        const dragHandle = itemContent?.querySelector?.(".dd-drag-handle");

        let w = 0;
        let h = 0;

        if (gridItem && gridItem.clientWidth > 20 && gridItem.clientHeight > 20) {
            const header = cardBody?.querySelector?.(".border-bottom");
            const drillBtn = cardBody?.querySelector?.(".fa-level-up");
            const drill = drillBtn?.closest?.(".d-flex");
            const insight = cardBody?.querySelector?.(".alert");
            const bodyStyle = cardBody ? getComputedStyle(cardBody) : null;
            const padY = bodyStyle
                ? (parseFloat(bodyStyle.paddingTop) || 0) + (parseFloat(bodyStyle.paddingBottom) || 0)
                : 16;
            const padX = bodyStyle
                ? (parseFloat(bodyStyle.paddingLeft) || 0) + (parseFloat(bodyStyle.paddingRight) || 0)
                : 16;
            const chrome =
                (dragHandle?.offsetHeight || 0) +
                (header?.offsetHeight || 0) +
                (drill?.offsetHeight || 0) +
                (insight?.offsetHeight || 0) +
                padY +
                8;
            // Use content box width (inside card padding)
            w = Math.max(80, (itemContent?.clientWidth || gridItem.clientWidth) - padX);
            h = Math.max(100, gridItem.clientHeight - chrome);
        } else if (container && container.clientWidth > 20 && container.clientHeight > 20) {
            w = container.clientWidth;
            h = Math.max(100, container.clientHeight);
        }

        if (container && w > 0 && h > 0) {
            container.style.setProperty("height", `${h}px`, "important");
            container.style.setProperty("min-height", `${Math.min(h, 120)}px`, "important");
            container.style.setProperty("max-height", `${h}px`, "important");
            container.style.width = "100%";
        }
        if (w > 0 && h > 0) {
            // Fill the chart-container — avoid oversized absolute widths
            host.style.setProperty("position", "absolute", "important");
            host.style.setProperty("inset", "0", "important");
            host.style.setProperty("width", "100%", "important");
            host.style.setProperty("height", "100%", "important");
            host.style.setProperty("max-width", "100%", "important");
            host.style.setProperty("max-height", "100%", "important");
        }
        return { w, h };
    }

    _adaptCircularChartToHost() {
        if (!this.root || !this._amChart || !window.am5) return;
        const host = this.chartRef?.el;
        if (!host) return;
        const w = host.clientWidth || 0;
        const h = host.clientHeight || 0;
        if (w < 40 || h < 40) return;

        const cType = this.activeItemType;
        if (!['pie', 'doughnut', 'polarArea', 'radar', 'flower', 'radialBar'].includes(cType)) {
            return;
        }

        // Scale radius with the smaller side so the pie fits the layout cell
        const minSide = Math.min(w, h);
        let radiusPct = 70;
        if (minSide < 180) radiusPct = 58;
        else if (minSide < 260) radiusPct = 65;
        else if (minSide > 420) radiusPct = 74;

        try {
            if (['pie', 'doughnut'].includes(cType)) {
                const sliceCount = (this.state.data?.labels || []).length;
                const useOutsideLabels = sliceCount <= 5 && minSide >= 280;
                const useSideLegend = !this._optEnabled(this.state.data?.hide_legend) && w > h * 1.15 && w > 360;
                if (useSideLegend) radiusPct = Math.min(radiusPct + 6, 78);
                if (useOutsideLabels) radiusPct = Math.min(radiusPct, 62);

                this._amChart.setAll({
                    layout: useSideLegend ? this.root.horizontalLayout : this.root.verticalLayout,
                    radius: am5.percent(radiusPct),
                    width: am5.percent(100),
                    height: am5.percent(100),
                    scale: 1,
                });
                if (this._amPieSeries) {
                    if (useOutsideLabels) {
                        this._amPieSeries.set("alignLabels", true);
                        this._amPieSeries.labels.template.setAll({
                            forceHidden: false,
                            text: "{category}: {valuePercentTotal.formatNumber('#.0')}%",
                            textType: "circular",
                            fill: this.root.interfaceColors.get("text"),
                        });
                        this._amPieSeries.ticks.template.setAll({ forceHidden: false, visible: true });
                        this._amPieSeries.labels.template.adapters.remove("forceHidden");
                    } else {
                        this._amPieSeries.set("alignLabels", false);
                        this._amPieSeries.labels.template.setAll({
                            text: "{valuePercentTotal.formatNumber('#.#')}%",
                            textType: "radial",
                            centerX: am5.percent(100),
                            fontSize: minSide < 200 ? 9 : 11,
                            fill: am5.color(0xffffff),
                        });
                        this._amPieSeries.ticks.template.setAll({ forceHidden: true });
                        this._amPieSeries.labels.template.adapters.remove("forceHidden");
                        this._amPieSeries.labels.template.adapters.add("forceHidden", (_hidden, target) => {
                            const di = target.dataItem;
                            if (!di) return true;
                            return (di.get("valuePercentTotal") || 0) < 4;
                        });
                    }
                }
                if (this._amLegend) {
                    if (useSideLegend) {
                        this._amLegend.setAll({
                            width: am5.percent(38),
                            height: am5.percent(100),
                            layout: this.root.verticalLayout,
                            centerX: undefined,
                            x: undefined,
                            centerY: am5.p50,
                            y: am5.p50,
                        });
                    } else {
                        this._amLegend.setAll({
                            width: am5.percent(100),
                            height: am5.percent(Math.min(36, 12 + sliceCount * 2)),
                            layout: this.root.verticalLayout,
                            centerX: am5.percent(50),
                            x: am5.percent(50),
                            centerY: undefined,
                            y: undefined,
                        });
                    }
                    this._amLegend.valueLabels.template.setAll({
                        forceHidden: false,
                        text: `{value.formatNumber('${am5NumberFormat(this.state.data || {})}')} ({valuePercentTotal.formatNumber('#.0')}%)`,
                    });
                }
            } else {
                this._amChart.setAll({
                    width: am5.percent(100),
                    height: am5.percent(100),
                    radius: am5.percent(radiusPct),
                    scale: 1,
                });
            }
        } catch (e) {
            console.warn("circular chart adapt failed", e);
        }
    }

    resizeChart() {
        this._syncChartHostSize();
        this._adaptCircularChartToHost();

        if (this.root) {
            try {
                if (typeof this.root.resize === "function") {
                    this.root.resize();
                }
            } catch (e) {
                console.warn("chart resize failed", e);
            }
        }
        // Re-apply layout-clipped CSS zoom after resize (does not change chart size)
        const scale = this._visualZoomScale || 1;
        if (scale > 1.01 && !this._chartHasAxes() && !AM5_MAP_TYPES.includes(this.activeItemType)) {
            const el = this._getZoomTransformEl();
            if (el) {
                el.style.transformOrigin = "center center";
                el.style.transform = `scale(${scale})`;
            }
        } else if (scale <= 1.01) {
            this._clearHostZoomTransform();
        }
        // Maps
        try {
            if (this.mapRef?.el && window.jQuery) {
                const $el = $(this.mapRef.el);
                if ($el.children(".jvectormap-container").length) {
                    const mapObject = $el.vectorMap("get", "mapObject");
                    if (mapObject) mapObject.updateSize();
                }
            }
        } catch (e) {}
    }

    _setupChartResizeObserver() {
        this._teardownChartResizeObserver();
        if (typeof ResizeObserver === "undefined") return;

        const observeTargets = [
            this.itemCardRef?.el,
            this.itemCardRef?.el?.closest?.(".grid-stack-item"),
            this.itemCardRef?.el?.closest?.(".grid-stack-item-content"),
            this.chartRef?.el?.parentElement,
            this.mapRef?.el?.parentElement,
        ].filter(Boolean);

        if (!observeTargets.length) return;

        this._chartResizeObserver = new ResizeObserver(() => {
            if (this._chartResizeRaf) cancelAnimationFrame(this._chartResizeRaf);
            this._chartResizeRaf = requestAnimationFrame(() => {
                this._chartResizeRaf = null;
                this.resizeChart();
            });
        });
        // Unique elements only
        [...new Set(observeTargets)].forEach((el) => this._chartResizeObserver.observe(el));
    }

    renderMap() {
        try {
            this._renderMapInner();
        } catch (e) {
            console.error("DynamicDashboardItem.renderMap failed", e);
        }
    }

    _renderMapInner() {
        if (!AM5_MAP_TYPES.includes(this.activeItemType) || !this.mapRef.el) {
            return;
        }
        const data = this.state.data || {};
        if (this.state.loading || this.state.error) {
            return;
        }
        const mapValues = data.datasets && data.datasets.length > 0
            ? data.datasets[0].data
            : data.data;
        if (!data.labels || !mapValues) {
            return;
        }
        const host = this.mapRef.el;
        const w = host.clientWidth || host.offsetWidth || 0;
        const h = host.clientHeight || host.offsetHeight || 0;
        if (w < 40 || h < 40) {
            if (this._mapInitAttempts == null) {
                this._mapInitAttempts = 0;
            }
            if (this._mapInitAttempts < 20) {
                this._mapInitAttempts += 1;
                requestAnimationFrame(() => this.renderMap());
            }
            return;
        }
        this._mapInitAttempts = 0;
        ensureExportingPlugin(data).then(() => {
            renderAmChartsMap(this, data);
            this._setupChartResizeObserver();
            this._setupChartZoomWheel();
        }).catch(() => {
            renderAmChartsMap(this, data);
            this._setupChartResizeObserver();
            this._setupChartZoomWheel();
        });
    }

    get percentage() {
        if (!this.state.data || !this.state.data.previous_value) return 0;
        const current = this.state.data.value;
        const prev = this.state.data.previous_value;
        if (prev === 0) return current > 0 ? 100 : 0;
        return Math.round(((current - prev) / prev) * 100);
    }

    getItemShellStyle() {
        const data = this.state.data || {};
        const t = this.activeItemType;
        if (['tile', 'kpi', 'scorecard'].includes(t)) {
            return 'background:transparent;border:none;box-shadow:none;';
        }
        const bg = data.background_color || '#ffffff';
        const fg = data.font_color || '#212529';
        return `background-color:${bg};color:${fg};`;
    }

    getItemShellClass() {
        const t = this.activeItemType;
        if (['tile', 'kpi', 'scorecard'].includes(t)) {
            return 'dd-shell-flush';
        }
        return '';
    }

    getKpiAccent() {
        const data = this.state.data || {};
        const theme = data.tile_theme || 'ocean';
        const themes = {
            ocean: '#0284c7',
            sky: '#0ea5e9',
            indigo: '#4f46e5',
            violet: '#7c3aed',
            plum: '#a855f7',
            berry: '#e11d48',
            rose: '#e11d48',
            coral: '#ea580c',
            tangerine: '#f97316',
            amber: '#d97706',
            sunflower: '#ca8a04',
            forest: '#059669',
            emerald: '#10b981',
            mint: '#0d9488',
            teal: '#0f766e',
            slate: '#475569',
            graphite: '#334155',
            navy: '#1e3a8a',
            midnight: '#38bdf8',
            custom: data.tile_color || data.color || '#0284c7',
        };
        if (theme === 'custom') {
            return data.tile_color || data.color || '#0284c7';
        }
        return themes[theme] || themes.ocean;
    }

    getTileThemePalette() {
        const data = this.state.data || {};
        const theme = data.tile_theme || 'ocean';
        const accent = this.getKpiAccent();
        const palettes = {
            ocean: { accent, bg: '#f0f9ff', fg: '#0c4a6e', muted: '#0369a1', soft: '#e0f2fe', grad: 'linear-gradient(135deg, #0ea5e9 0%, #0369a1 100%)', dark: false },
            sky: { accent, bg: '#f0f9ff', fg: '#075985', muted: '#0284c7', soft: '#e0f2fe', grad: 'linear-gradient(135deg, #38bdf8 0%, #0284c7 100%)', dark: false },
            indigo: { accent, bg: '#eef2ff', fg: '#312e81', muted: '#4338ca', soft: '#e0e7ff', grad: 'linear-gradient(135deg, #818cf8 0%, #4338ca 100%)', dark: false },
            violet: { accent, bg: '#f5f3ff', fg: '#4c1d95', muted: '#6d28d9', soft: '#ede9fe', grad: 'linear-gradient(135deg, #a78bfa 0%, #6d28d9 100%)', dark: false },
            plum: { accent, bg: '#faf5ff', fg: '#581c87', muted: '#7e22ce', soft: '#f3e8ff', grad: 'linear-gradient(135deg, #c084fc 0%, #7e22ce 100%)', dark: false },
            berry: { accent, bg: '#fff1f2', fg: '#881337', muted: '#be123c', soft: '#ffe4e6', grad: 'linear-gradient(135deg, #fb7185 0%, #9f1239 100%)', dark: false },
            rose: { accent, bg: '#fff1f2', fg: '#9f1239', muted: '#e11d48', soft: '#ffe4e6', grad: 'linear-gradient(135deg, #fb7185 0%, #be123c 100%)', dark: false },
            coral: { accent, bg: '#fff7ed', fg: '#7c2d12', muted: '#c2410c', soft: '#ffedd5', grad: 'linear-gradient(135deg, #fb923c 0%, #c2410c 100%)', dark: false },
            tangerine: { accent, bg: '#fff7ed', fg: '#9a3412', muted: '#ea580c', soft: '#ffedd5', grad: 'linear-gradient(135deg, #fdba74 0%, #ea580c 100%)', dark: false },
            amber: { accent, bg: '#fffbeb', fg: '#78350f', muted: '#b45309', soft: '#fef3c7', grad: 'linear-gradient(135deg, #fbbf24 0%, #b45309 100%)', dark: false },
            sunflower: { accent, bg: '#fefce8', fg: '#713f12', muted: '#a16207', soft: '#fef9c3', grad: 'linear-gradient(135deg, #facc15 0%, #a16207 100%)', dark: false },
            forest: { accent, bg: '#ecfdf5', fg: '#064e3b', muted: '#047857', soft: '#d1fae5', grad: 'linear-gradient(135deg, #34d399 0%, #047857 100%)', dark: false },
            emerald: { accent, bg: '#ecfdf5', fg: '#065f46', muted: '#059669', soft: '#d1fae5', grad: 'linear-gradient(135deg, #34d399 0%, #059669 100%)', dark: false },
            mint: { accent, bg: '#f0fdfa', fg: '#134e4a', muted: '#0f766e', soft: '#ccfbf1', grad: 'linear-gradient(135deg, #2dd4bf 0%, #0f766e 100%)', dark: false },
            teal: { accent, bg: '#f0fdfa', fg: '#115e59', muted: '#0f766e', soft: '#ccfbf1', grad: 'linear-gradient(135deg, #14b8a6 0%, #0f766e 100%)', dark: false },
            slate: { accent, bg: '#f8fafc', fg: '#0f172a', muted: '#475569', soft: '#e2e8f0', grad: 'linear-gradient(135deg, #94a3b8 0%, #334155 100%)', dark: false },
            graphite: { accent, bg: '#1e293b', fg: '#f8fafc', muted: '#94a3b8', soft: '#334155', grad: 'linear-gradient(135deg, #475569 0%, #0f172a 100%)', dark: true },
            navy: { accent, bg: '#0b1f4a', fg: '#eef2ff', muted: '#93c5fd', soft: '#1e3a8a', grad: 'linear-gradient(135deg, #1d4ed8 0%, #0b1f4a 100%)', dark: true },
            midnight: { accent, bg: '#0f172a', fg: '#f8fafc', muted: '#94a3b8', soft: '#1e293b', grad: 'linear-gradient(135deg, #1e293b 0%, #0f172a 55%, #0369a1 160%)', dark: true },
            custom: {
                accent,
                bg: data.background_color || '#ffffff',
                fg: data.font_color || '#1f2937',
                muted: '#6b7280',
                soft: typeof accent === 'string' && accent.startsWith('#') ? `${accent}18` : 'rgba(2,132,199,0.1)',
                grad: `linear-gradient(135deg, ${accent} 0%, ${accent}cc 100%)`,
                dark: false,
            },
        };
        return palettes[theme] || palettes.ocean;
    }

    getTileIconBg() {
        return this.getTileThemePalette().soft;
    }

    getKpiCardStyle() {
        const data = this.state.data || {};
        const p = this.getTileThemePalette();
        const layout = data.tile_layout || 'layout1';
        const vars = [
            `--dd-kpi-accent:${p.accent}`,
            `--dd-kpi-bg:${p.bg}`,
            `--dd-kpi-fg:${p.fg}`,
            `--dd-kpi-muted:${p.muted}`,
            `--dd-kpi-soft:${p.soft}`,
            `--dd-kpi-grad:${p.grad}`,
            `--dd-tile-icon-bg:${p.soft}`,
            `color:${p.fg}`,
            'cursor:pointer',
        ];
        // Hero / dark themes paint their own background via CSS; still set vars
        const darkThemes = ['midnight', 'graphite', 'navy'];
        const isDark = darkThemes.includes(data.tile_theme);
        if (layout === 'layout4' || (isDark && layout !== 'layout1')) {
            vars.push(`background:${p.grad}`);
            if (layout === 'layout4' || isDark) {
                vars.push('color:#f8fafc');
            }
        } else {
            vars.push(`background-color:${p.bg}`);
        }
        return vars.join(';');
    }

    getScorecardWrapStyle() {
        const p = this.getTileThemePalette();
        return `--dd-kpi-accent:${p.accent};--dd-kpi-bg:${p.bg};--dd-kpi-fg:${p.fg};--dd-kpi-muted:${p.muted};--dd-kpi-soft:${p.soft};background:${p.bg};color:${p.fg};`;
    }

    getKpiGrowth() {
        if (!this.state.data || !this.state.data.compare_previous_period) {
            return 0;
        }
        return this.percentage;
    }

    getKpiAchievement() {
        const data = this.state.data || {};
        if (data.achievement !== undefined && data.achievement !== null && data.achievement !== false) {
            return Math.round(Number(data.achievement) || 0);
        }
        const target = Number(data.target_value);
        if (!target) {
            return null;
        }
        return Math.round((Number(data.value) || 0) / target * 100);
    }

    getKpiRingDash() {
        const pct = Math.min(Math.max(this.getKpiAchievement() || 0, 0), 100);
        return `${pct}, 100`;
    }
    
    formatNumber(value) {
        const data = this.state.data || {};
        const locale = data.locale || getUserLocale();
        return formatDashboardNumber(value, data, locale);
    }

    onChartClick(clickedLabel = null) {
        if (!this.state.data) return;
        const data = this.state.data;

        // Drill-down on segment click when enabled and further drill is possible
        if (clickedLabel && this._optEnabled(data.enable_drill_down) && data.group_by_field) {
            const canDateDrill = !!data.next_drill_date_type;
            const canSubDrill = !!data.has_sub_group;
            const alreadyDrilled = this.state.drillStack.length > 0;
            // Always allow first click filter; allow further when date/sub drill remains
            if (!alreadyDrilled || canDateDrill || canSubDrill) {
                const map = data.label_domain_map || {};
                const domainVal = Object.prototype.hasOwnProperty.call(map, clickedLabel)
                    ? map[clickedLabel]
                    : (clickedLabel === 'Undefined' ? false : clickedLabel);
                const leaf = [data.group_by_field, '=', domainVal];
                this.state.drillStack.push({ label: clickedLabel, leaf });
                if (data.next_drill_date_type) {
                    this.state.drillDateType = data.next_drill_date_type;
                }
                this.loadItemData();
                return;
            }
        }
        
        if (data.action_type === 'window' && data.action_id) {
            this.action.doAction(data.action_id);
        } else if (data.action_type === 'client' && data.client_action_tag) {
            this.action.doAction(data.client_action_tag);
        } else if (data.action_type === 'url' && data.action_url) {
            window.open(data.action_url, '_blank');
        } else {
            if (!data.model || !this._optEnabled(data.show_records)) return;
            
            let finalDomain = data.domain ? JSON.parse(JSON.stringify(data.domain)) : [];
            if (clickedLabel && data.group_by_field) {
                const map = data.label_domain_map || {};
                const domainVal = Object.prototype.hasOwnProperty.call(map, clickedLabel)
                    ? map[clickedLabel]
                    : (clickedLabel === 'Undefined' ? false : clickedLabel);
                finalDomain.push([data.group_by_field, '=', domainVal]);
            }
            
            this.action.doAction({
                name: data.name,
                type: 'ir.actions.act_window',
                res_model: data.model,
                view_mode: 'list,form',
                domain: finalDomain,
                views: [[false, 'list'], [false, 'form']],
                target: 'current',
                dashboard_item_id: this.props.itemId,
                share_token: this.props.shareToken || false,
            });
        }
    }

    drillUp(index = null) {
        if (!this.state.drillStack.length) return;
        if (index === null) {
            this.state.drillStack.pop();
        } else {
            this.state.drillStack.splice(index + 1);
        }
        if (!this.state.drillStack.length) {
            this.state.drillDateType = null;
        }
        this.loadItemData();
    }

    openRecordsFromDrill() {
        const data = this.state.data;
        if (!data?.model) return;
        let finalDomain = data.domain ? JSON.parse(JSON.stringify(data.domain)) : [];
        this.action.doAction({
            name: data.name,
            type: 'ir.actions.act_window',
            res_model: data.model,
            view_mode: 'list,form',
            domain: finalDomain,
            views: [[false, 'list'], [false, 'form']],
            target: 'current',
        });
    }

    openEmbeddedAction() {
        const actionId = this.state.data?.odoo_action_id;
        if (actionId) {
            this.action.doAction(actionId);
        }
    }

    openQuickEdit() {
        if (!this.state.canEdit) return;
        this.state.quickEdit = {
            name: this.state.data.name || '',
            chart_theme: this.state.data.theme || 'default',
            item_type: this.props.itemType,
        };
        this.state.quickEditOpen = true;
    }

    closeQuickEdit() {
        this.state.quickEditOpen = false;
    }

    async saveQuickEdit() {
        const vals = {
            name: this.state.quickEdit.name,
            chart_theme: this.state.quickEdit.chart_theme,
        };
        if (this.state.quickEdit.item_type && this.state.quickEdit.item_type !== this.props.itemType) {
            vals.item_type = this.state.quickEdit.item_type;
        }
        await this.orm.call('dynamic.dashboard.item', 'update_user_preference', [this.props.itemId, vals]);
        this.state.quickEditOpen = false;
        if (vals.item_type) {
            this.action.doAction({ type: 'ir.actions.client', tag: 'reload' });
        } else {
            await this.loadItemData();
            this.notification.add(_t("Item updated."), { type: 'success' });
        }
    }

    editItem() {
        this.action.doAction({
            type: 'ir.actions.act_window',
            res_model: 'dynamic.dashboard.item',
            res_id: this.props.itemId,
            views: [[false, 'form']],
            target: 'current',
        });
    }

    async openInternalChat() {
        try {
            const action = await this.orm.call('dynamic.dashboard.item', 'action_internal_chat', [[this.props.itemId]]);
            if (action) {
                this.action.doAction(action);
            }
        } catch (error) {
            console.error("Failed to open internal chat", error);
            this.env.services.notification.add(
                _t("Could not open internal chat."),
                { type: "danger" }
            );
        }
    }

    async toggleTodo(todoId, ev) {
        const isDone = ev.target.checked;
        await this.orm.write('dynamic.dashboard.todo', [todoId], { is_done: isDone });
        const todo = this.state.data.todos.find(t => t.id === todoId);
        if (todo) todo.is_done = isDone;
    }

    async addTodo() {
        if (!this.newTodoInput.el) return;
        const name = this.newTodoInput.el.value;
        if (!name || !name.trim()) return;
        
        const todoId = await this.orm.create('dynamic.dashboard.todo', [{
            name: name,
            dashboard_item_id: this.props.itemId
        }]);
        
        this.state.data.todos.push({
            id: todoId[0],
            name: name,
            is_done: false
        });
        this.newTodoInput.el.value = '';
    }

    onNewTodoKeyup(ev) {
        if (ev.key === 'Enter') {
            this.addTodo();
        }
    }

    async changeItemType(newType) {
        if (!newType || newType === this.activeItemType) {
            return;
        }
        try {
            this._visualZoomScale = 1;
            this._clearHostZoomTransform();
            await this.orm.call('dynamic.dashboard.item', 'update_user_preference', [this.props.itemId, { item_type: newType }]);
            // Keep parent item list in sync when the same object is shared
            if (this.props.item) {
                this.props.item.item_type = newType;
            }
            this.state.overrideItemType = newType;
            this.state.quickEdit.item_type = newType;
            await loadAmChartsLibs(newType);
            await ensureExportingPlugin(this.state.data || {});
            await this.loadItemData();
            this.notification.add(_t("Layout updated"), { type: "success" });
        } catch (e) {
            console.error(e);
            this.notification.add(_t("Could not switch layout"), { type: "danger" });
        }
    }

    get supportsStackedOption() {
        return ['bar', 'barLine', 'horizontalBar', 'area'].includes(this.activeItemType);
    }

    get supportsSemiCircleOption() {
        return ['pie', 'doughnut'].includes(this.activeItemType);
    }

    get supportsGridOption() {
        return [
            'bar', 'barLine', 'horizontalBar', 'line', 'area', 'stepLine', 'smoothedLine',
            'waterfall', 'scatter', 'radar', 'polarArea', 'flower', 'radialBar',
            'bullet', 'candlestick', 'ohlc', 'heatmap', 'matrixHeatmap',
            'timeline', 'serpentine', 'spiral',
        ].includes(this.activeItemType);
    }

    get supportsCursorOption() {
        return this.supportsGridOption || ['map', 'mapPoints'].includes(this.activeItemType);
    }

    get supportsZoomOption() {
        return this.isAmChartsVisual;
    }

    get supportsScrollbarOption() {
        return XY_ZOOM_TYPES.includes(this.activeItemType);
    }

    get chartThemeOptions() {
        return [
            { value: 'default', label: 'Default', swatch: '#2563EB' },
            { value: 'cool', label: 'Cool', swatch: '#0EA5E9' },
            { value: 'warm', label: 'Warm', swatch: '#EA580C' },
            { value: 'neon', label: 'Neon', swatch: '#FF2BD6' },
            { value: 'pastel', label: 'Pastel', swatch: '#F9A8D4' },
            { value: 'corporate', label: 'Corporate', swatch: '#1E3A5F' },
            { value: 'vibrant', label: 'Vibrant', swatch: '#EC4899' },
            { value: 'ocean', label: 'Ocean', swatch: '#0369A1' },
            { value: 'sunset', label: 'Sunset', swatch: '#F97316' },
        ];
    }

    get chartLayoutOptions() {
        return [
            { value: 'bar', label: 'Bar', icon: 'fa-bar-chart' },
            { value: 'barLine', label: 'Bar + Line', icon: 'fa-line-chart' },
            { value: 'horizontalBar', label: 'Horizontal Bar', icon: 'fa-align-left' },
            { value: 'line', label: 'Line', icon: 'fa-line-chart' },
            { value: 'area', label: 'Area', icon: 'fa-area-chart' },
            { value: 'stepLine', label: 'Step Line', icon: 'fa-area-chart' },
            { value: 'smoothedLine', label: 'Smoothed', icon: 'fa-line-chart' },
            { value: 'waterfall', label: 'Waterfall', icon: 'fa-sort-amount-asc' },
            { value: 'pie', label: 'Pie', icon: 'fa-pie-chart' },
            { value: 'doughnut', label: 'Doughnut', icon: 'fa-circle-o' },
            { value: 'polarArea', label: 'Polar Area', icon: 'fa-life-ring' },
            { value: 'radar', label: 'Radar', icon: 'fa-bullseye' },
            { value: 'flower', label: 'Flower', icon: 'fa-pagelines' },
            { value: 'scatter', label: 'Scatter', icon: 'fa-dot-circle-o' },
            { value: 'radialBar', label: 'Radial Bar', icon: 'fa-spinner' },
            { value: 'gauge', label: 'Gauge', icon: 'fa-dashboard' },
            { value: 'funnel', label: 'Funnel', icon: 'fa-filter' },
            { value: 'pyramid', label: 'Pyramid', icon: 'fa-sort-amount-desc' },
            { value: 'treemap', label: 'Treemap', icon: 'fa-th-large' },
            { value: 'sunburst', label: 'Sunburst', icon: 'fa-sun-o' },
            { value: 'forceDirected', label: 'Force', icon: 'fa-share-alt' },
            { value: 'pack', label: 'Pack', icon: 'fa-circle' },
            { value: 'tree', label: 'Tree', icon: 'fa-sitemap' },
            { value: 'partition', label: 'Partition', icon: 'fa-columns' },
            { value: 'voronoiTreemap', label: 'Voronoi', icon: 'fa-delicious' },
            { value: 'sankey', label: 'Sankey', icon: 'fa-share-alt' },
            { value: 'chord', label: 'Chord', icon: 'fa-refresh' },
            { value: 'chordDirected', label: 'Directed Chord', icon: 'fa-mail-forward' },
            { value: 'arcDiagram', label: 'Arc', icon: 'fa-exchange' },
            { value: 'heatmap', label: 'Heatmap', icon: 'fa-th' },
            { value: 'map', label: 'Map', icon: 'fa-globe' },
            { value: 'mapPoints', label: 'Map Points', icon: 'fa-map-marker' },
            { value: 'wordCloud', label: 'Word Cloud', icon: 'fa-cloud' },
            { value: 'candlestick', label: 'Candlestick', icon: 'fa-btc' },
            { value: 'ohlc', label: 'OHLC', icon: 'fa-bar-chart' },
            { value: 'timeline', label: 'Timeline', icon: 'fa-clock-o' },
            { value: 'serpentine', label: 'Serpentine', icon: 'fa-long-arrow-right' },
            { value: 'spiral', label: 'Spiral', icon: 'fa-refresh' },
            { value: 'bullet', label: 'Bullet', icon: 'fa-tasks' },
        ];
    }

    get currentChartTheme() {
        return this.state.data?.theme || this.state.data?.chart_theme || 'default';
    }

    isChartLayout(type) {
        return this.activeItemType === type;
    }

    /** Defaults must match model / chart_engine so toggles reflect real chart state. */
    _displayOptionDefaults() {
        return {
            hide_legend: false,
            show_data_value: true,
            show_tooltip: true,
            enable_animation: true,
            show_grid: true,
            show_cursor: true,
            enable_zoom: true,
            show_scrollbar_x: false,
            is_stacked: false,
            is_stacked_100: false,
            is_semi_circle: false,
        };
    }

    _displayOptionValue(field) {
        const data = this.state.data || {};
        if (field === 'hide_legend') {
            return !!(data.hide_legend || data.legend_position === 'none');
        }
        const defaults = this._displayOptionDefaults();
        if (data[field] === undefined || data[field] === null) {
            return !!defaults[field];
        }
        return this._optEnabled(data[field]);
    }

    isChartTheme(theme) {
        return this.currentChartTheme === theme;
    }

    isLegendPosition(position) {
        const data = this.state.data || {};
        if (this._displayOptionValue('hide_legend') || data.legend_position === 'none') {
            return false;
        }
        return (data.legend_position || 'bottom') === position;
    }

    async _persistDisplayOptions(vals) {
        if (!this.props.itemId || !vals || !Object.keys(vals).length) {
            return;
        }
        try {
            if (this.state.canEdit) {
                await this.orm.write('dynamic.dashboard.item', [this.props.itemId], vals);
            } else {
                await this.orm.call(
                    'dynamic.dashboard.item',
                    'update_user_preference',
                    [this.props.itemId, vals],
                );
            }
            // Optimistic local update so toggles feel instant
            Object.assign(this.state.data, vals);
            if ('chart_theme' in vals) {
                this.state.data.theme = vals.chart_theme;
                this.state.data.chart_theme = vals.chart_theme;
            }
            if ('hide_legend' in vals && vals.hide_legend) {
                this.state.data.legend_position = 'none';
            }
            await this.loadItemData();
            // Keep explicit theme after reload and force a redraw (mutation alone
            // does not always re-trigger the chart useEffect).
            if ('chart_theme' in vals) {
                this.state.data = {
                    ...this.state.data,
                    theme: vals.chart_theme,
                    chart_theme: vals.chart_theme,
                };
                this.renderChart();
                this.renderMap();
            }
        } catch (e) {
            console.error(e);
            this.notification.add(_t("Could not update chart options"), { type: "danger" });
        }
    }

    async toggleDisplayOption(field) {
        if (!field) return;
        const next = !this._displayOptionValue(field);
        const vals = { [field]: next };
        if (field === 'hide_legend') {
            vals.legend_position = next ? 'none' : 'bottom';
        }
        if (field === 'is_stacked' && !next) {
            vals.is_stacked_100 = false;
        }
        await this._persistDisplayOptions(vals);
    }

    async setDisplayOption(field, value) {
        await this._persistDisplayOptions({ [field]: value });
    }

    async setLegendPosition(position) {
        const vals = {
            legend_position: position,
            hide_legend: position === 'none',
        };
        await this._persistDisplayOptions(vals);
    }

    async setChartTheme(theme) {
        if (!theme) return;
        await this._persistDisplayOptions({ chart_theme: theme });
        this.state.data.theme = theme;
        this.state.data.chart_theme = theme;
        this.notification.add(_t("Chart theme updated"), { type: "info" });
    }

    get tileLayoutOptions() {
        return [
            { value: 'layout1', label: 'Accent Left' },
            { value: 'layout2', label: 'Icon Left' },
            { value: 'layout3', label: 'Centered' },
            { value: 'layout4', label: 'Gradient Hero' },
            { value: 'layout5', label: 'Split Band' },
            { value: 'layout6', label: 'Soft Float' },
            { value: 'layout7', label: 'Value First' },
            { value: 'layout8', label: 'Pill Header' },
        ];
    }

    get tileThemeOptions() {
        return [
            { value: 'ocean', label: 'Ocean', swatch: '#0284c7' },
            { value: 'sky', label: 'Sky', swatch: '#0ea5e9' },
            { value: 'indigo', label: 'Indigo', swatch: '#4f46e5' },
            { value: 'violet', label: 'Violet', swatch: '#7c3aed' },
            { value: 'plum', label: 'Plum', swatch: '#a855f7' },
            { value: 'berry', label: 'Berry', swatch: '#e11d48' },
            { value: 'rose', label: 'Rose', swatch: '#f43f5e' },
            { value: 'coral', label: 'Coral', swatch: '#ea580c' },
            { value: 'tangerine', label: 'Tangerine', swatch: '#f97316' },
            { value: 'amber', label: 'Amber', swatch: '#d97706' },
            { value: 'sunflower', label: 'Sunflower', swatch: '#ca8a04' },
            { value: 'forest', label: 'Forest', swatch: '#059669' },
            { value: 'emerald', label: 'Emerald', swatch: '#10b981' },
            { value: 'mint', label: 'Mint', swatch: '#0d9488' },
            { value: 'teal', label: 'Teal', swatch: '#0f766e' },
            { value: 'slate', label: 'Slate', swatch: '#475569' },
            { value: 'graphite', label: 'Graphite', swatch: '#334155' },
            { value: 'navy', label: 'Navy', swatch: '#1e3a8a' },
            { value: 'midnight', label: 'Midnight', swatch: '#0f172a' },
        ];
    }

    get tileColorPresets() {
        return [
            '#2563EB', '#0EA5E9', '#06B6D4', '#14B8A6', '#10B981', '#22C55E',
            '#84CC16', '#EAB308', '#F59E0B', '#F97316', '#EF4444', '#F43F5E',
            '#EC4899', '#D946EF', '#A855F7', '#8B5CF6', '#6366F1', '#3B82F6',
            '#64748B', '#334155', '#0F172A', '#1E3A8A',
        ];
    }

    isTileLayout(layout) {
        return (this.state.data?.tile_layout || 'layout1') === layout;
    }

    isTileTheme(theme) {
        return (this.state.data?.tile_theme || 'ocean') === theme;
    }

    isTileColor(color) {
        if ((this.state.data?.tile_theme || 'ocean') !== 'custom') return false;
        return String(this.state.data?.tile_color || '').toLowerCase() === String(color || '').toLowerCase();
    }

    async cycleTileLayout() {
        const layouts = this.tileLayoutOptions.map((l) => l.value);
        const current = this.state.data?.tile_layout || 'layout1';
        let idx = layouts.indexOf(current) + 1;
        if (idx < 0 || idx >= layouts.length) idx = 0;
        await this._persistDisplayOptions({ tile_layout: layouts[idx] });
        this.notification.add(_t("Card layout updated"), { type: "info" });
    }

    async setTileLayout(layout) {
        if (!layout || layout === (this.state.data?.tile_layout || 'layout1')) return;
        await this._persistDisplayOptions({ tile_layout: layout });
    }

    async cycleTileTheme() {
        const themes = this.tileThemeOptions.map((t) => t.value);
        const current = this.state.data?.tile_theme || 'ocean';
        let idx = themes.indexOf(current) + 1;
        if (idx < 0 || idx >= themes.length) idx = 0;
        await this._persistDisplayOptions({ tile_theme: themes[idx] });
    }

    async setTileTheme(theme) {
        if (!theme) return;
        await this._persistDisplayOptions({ tile_theme: theme });
    }

    async setTileColor(color) {
        if (!color) return;
        await this._persistDisplayOptions({
            tile_theme: 'custom',
            tile_color: color,
        });
    }

    async setListLayout(layout) {
        if (!layout || layout === (this.state.data?.list_view_layout || 'layout1')) return;
        await this._persistDisplayOptions({ list_view_layout: layout });
    }

    async setScorecardColumns(cols) {
        if (!cols || cols === (this.state.data?.scorecard_columns || 'auto')) return;
        await this._persistDisplayOptions({ scorecard_columns: cols });
    }

    isScorecardColumns(cols) {
        return (this.state.data?.scorecard_columns || 'auto') === cols;
    }

    get scorecardColumnOptions() {
        return [
            { value: 'auto', label: 'Auto' },
            { value: '2', label: '2 Columns' },
            { value: '3', label: '3 Columns' },
            { value: '4', label: '4 Columns' },
        ];
    }

    async quickRefreshItem() {
        await this.loadItemData();
        this.notification.add(_t("Item refreshed"), { type: "success" });
    }
    
    async changeColorTheme() {
        const themes = this.chartThemeOptions.map((t) => t.value);
        const currentTheme = this.currentChartTheme;
        let nextIdx = themes.indexOf(currentTheme) + 1;
        if (nextIdx >= themes.length || nextIdx < 0) nextIdx = 0;
        await this.setChartTheme(themes[nextIdx]);
    }    
    async generateAIInsight() {
        this.state.insightLoading = true;
        this.state.insight = null;
        try {
            const chartData = {
                name: this.state.data.name,
                labels: this.state.data.labels,
                datasets: this.state.data.datasets || [{label: this.state.data.name, data: this.state.data.data}]
            };
            const insightText = await this.orm.call('dynamic.dashboard.item', 'generate_ai_insight', [this.props.itemId, chartData]);
            this.state.insight = insightText;
        } catch (e) {
            console.error(e);
            this.state.insight = _t("Unable to generate AI insight. Ensure your API key is valid.");
        } finally {
            this.state.insightLoading = false;
        }
    }

    async listPrevPage() {
        const limit = this.state.data?.pagination_limit || 0;
        if (!limit) return;
        this.state.listOffset = Math.max(0, (this.state.listOffset || 0) - limit);
        await this.loadItemData();
    }

    async listNextPage() {
        const limit = this.state.data?.pagination_limit || 0;
        const total = this.state.data?.list_total || 0;
        if (!limit) return;
        const next = (this.state.listOffset || 0) + limit;
        if (next >= total) return;
        this.state.listOffset = next;
        await this.loadItemData();
    }

    get listPageInfo() {
        const data = this.state.data || {};
        const limit = data.pagination_limit || 0;
        const total = data.list_total || 0;
        if (!limit || !total) return null;
        const offset = data.list_offset || 0;
        const from = total ? offset + 1 : 0;
        const to = Math.min(offset + limit, total);
        return { from, to, total, canPrev: offset > 0, canNext: to < total };
    }

    onListSearchInput(ev) {
        this.state.listSearch = ev.target.value || '';
    }

    toggleListSort(col) {
        if (this.state.listSortCol === col) {
            this.state.listSortAsc = !this.state.listSortAsc;
        } else {
            this.state.listSortCol = col;
            this.state.listSortAsc = true;
        }
    }

    _cellDisplayValue(val) {
        if (Array.isArray(val)) return val[1] != null ? String(val[1]) : '';
        if (val == null) return '';
        return String(val);
    }

    get displayedListRecords() {
        const data = this.state.data || {};
        let records = [...(data.records || [])];
        const columns = data.column_keys || data.columns || [];
        const search = (this.state.listSearch || '').trim().toLowerCase();
        if (search) {
            records = records.filter((rec) => {
                return columns.some((col) => {
                    const key = col;
                    return this._cellDisplayValue(rec[key]).toLowerCase().includes(search);
                }) || Object.keys(rec).some((k) =>
                    this._cellDisplayValue(rec[k]).toLowerCase().includes(search)
                );
            });
        }
        const sortCol = this.state.listSortCol;
        if (sortCol) {
            const asc = this.state.listSortAsc;
            records.sort((a, b) => {
                const av = this._cellDisplayValue(a[sortCol]);
                const bv = this._cellDisplayValue(b[sortCol]);
                const an = parseFloat(av);
                const bn = parseFloat(bv);
                let cmp;
                if (!isNaN(an) && !isNaN(bn) && av.trim() !== '' && bv.trim() !== '') {
                    cmp = an - bn;
                } else {
                    cmp = av.localeCompare(bv, undefined, { sensitivity: 'base', numeric: true });
                }
                return asc ? cmp : -cmp;
            });
        }
        return records;
    }

    async exportToCSV() {
        if (!this.state.data) return;
        let csvContent = "data:text/csv;charset=utf-8,";
        let data = this.state.data;

        if (this.props.itemType === 'list' && data.export_all_records) {
            try {
                data = await this.orm.call(
                    'dynamic.dashboard.item',
                    'fetch_item_data',
                    [this.props.itemId],
                    {
                        global_date_filter: this.props.globalDateFilter,
                        global_compare: this.props.globalCompare || false,
                        custom_filter_domains: this.props.customFilterDomains || [],
                        export_all: true,
                    }
                );
            } catch (e) {
                data = this.state.data;
            }
        }

        if (this.props.itemType === 'list') {
            const columns = data.columns || [];
            const keys = data.column_keys || columns;
            csvContent += columns.join(",") + "\r\n";
            (data.records || []).forEach(row => {
                let r = keys.map(k => {
                    const v = row[k];
                    return Array.isArray(v) ? v[1] : (v ?? '');
                });
                csvContent += r.join(",") + "\r\n";
            });
        } else if (data.labels) {
            csvContent += "Label";
            if (data.datasets) {
                data.datasets.forEach(ds => { csvContent += "," + ds.label; });
                csvContent += "\r\n";
                data.labels.forEach((label, idx) => {
                    let row = `"${label}"`;
                    data.datasets.forEach(ds => { row += "," + ds.data[idx]; });
                    csvContent += row + "\r\n";
                });
            } else if (data.data) {
                csvContent += ",Value\r\n";
                data.labels.forEach((label, idx) => {
                    csvContent += `"${label}",` + data.data[idx] + "\r\n";
                });
            }
        } else {
            return;
        }

        const encodedUri = encodeURI(csvContent);
        const link = document.createElement("a");
        link.setAttribute("href", encodedUri);
        link.setAttribute("download", (data.name || "export") + ".csv");
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
    }

    _loadScript(src) {
        return new Promise((resolve, reject) => {
            if (document.querySelector(`script[src="${src}"]`)) {
                resolve();
                return;
            }
            const script = document.createElement('script');
            script.src = src;
            script.onload = resolve;
            script.onerror = reject;
            document.head.appendChild(script);
        });
    }

    async _captureItemImage() {
        const el = this.itemCardRef.el;
        if (!el) {
            throw new Error("Item card not found");
        }
        return captureElementToCanvas(el);
    }

    async exportToPNG() {
        try {
            this.notification.add(_t("Generating PNG..."), { type: 'info' });
            const canvas = await this._captureItemImage();
            const link = document.createElement("a");
            link.download = `${(this.state.data.name || "item").replace(/\s+/g, '_')}.png`;
            link.href = canvas.toDataURL('image/png');
            link.click();
            this.notification.add(_t("PNG exported."), { type: 'success' });
        } catch (e) {
            console.error(e);
            this.notification.add(_t("Failed to export PNG."), { type: 'danger' });
        }
    }

    async exportToPDF() {
        try {
            this.notification.add(_t("Generating PDF..."), { type: 'info' });
            if (!window.jspdf) {
                await this._loadScript('https://cdnjs.cloudflare.com/ajax/libs/jspdf/2.5.1/jspdf.umd.min.js');
            }
            const canvas = await this._captureItemImage();
            const imgData = canvas.toDataURL('image/jpeg', 0.95);
            const pdf = new window.jspdf.jsPDF({
                orientation: canvas.width > canvas.height ? 'l' : 'p',
                unit: 'pt',
                format: 'a4',
            });
            const pageW = pdf.internal.pageSize.getWidth();
            const pageH = pdf.internal.pageSize.getHeight();
            const ratio = Math.min(pageW / canvas.width, pageH / canvas.height);
            const w = canvas.width * ratio;
            const h = canvas.height * ratio;
            pdf.addImage(imgData, 'JPEG', (pageW - w) / 2, 20, w, h);
            pdf.save(`${(this.state.data.name || "item").replace(/\s+/g, '_')}.pdf`);
            this.notification.add(_t("PDF exported."), { type: 'success' });
        } catch (e) {
            console.error(e);
            this.notification.add(_t("Failed to export PDF."), { type: 'danger' });
        }
    }

    exportToExcel() {
        const data = this.state.data;
        if (!data) return;

        let headers = [];
        let rows = [];

        if (this.props.itemType === 'list') {
            headers = data.columns || [];
            const keys = data.column_keys || headers;
            rows = (data.records || []).map(row =>
                keys.map(k => {
                    const v = row[k];
                    return Array.isArray(v) ? v[1] : (v ?? '');
                })
            );
        } else if (data.labels && data.datasets) {
            headers = ['Label', ...data.datasets.map(ds => ds.label)];
            rows = data.labels.map((label, idx) =>
                [label, ...data.datasets.map(ds => ds.data[idx])]
            );
        } else if (data.labels && data.data) {
            headers = ['Label', 'Value'];
            rows = data.labels.map((label, idx) => [label, data.data[idx]]);
        } else {
            this.notification.add(_t("No tabular data to export."), { type: 'warning' });
            return;
        }

        const escapeXml = (v) => String(v ?? '')
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;');

        let sheet = `<?xml version="1.0"?>
<?mso-application progid="Excel.Sheet"?>
<Workbook xmlns="urn:schemas-microsoft-com:office:spreadsheet"
 xmlns:ss="urn:schemas-microsoft-com:office:spreadsheet">
 <Worksheet ss:Name="Sheet1">
  <Table>
   <Row>${headers.map(h => `<Cell><Data ss:Type="String">${escapeXml(h)}</Data></Cell>`).join('')}</Row>
`;
        rows.forEach(row => {
            sheet += '   <Row>' + row.map(cell => {
                const isNum = typeof cell === 'number' || (cell !== '' && !isNaN(cell) && cell !== null);
                const type = isNum ? 'Number' : 'String';
                return `<Cell><Data ss:Type="${type}">${escapeXml(cell)}</Data></Cell>`;
            }).join('') + '</Row>\n';
        });
        sheet += `  </Table>
 </Worksheet>
</Workbook>`;

        const blob = new Blob([sheet], { type: 'application/vnd.ms-excel' });
        const link = document.createElement('a');
        link.href = URL.createObjectURL(blob);
        link.download = `${(data.name || 'export').replace(/\s+/g, '_')}.xls`;
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        URL.revokeObjectURL(link.href);
    }
}

DynamicDashboardItem.template = "dynamic_dashboard_ai_nexgen.DashboardItem";
DynamicDashboardItem.props = {
    item: { type: Object, optional: true },
    itemId: Number,
    itemType: String,
    globalDateFilter: String,
    globalCompare: { type: Boolean, optional: true },
    customFilterDomains: { type: Array, optional: true },
    shareToken: { type: String, optional: true },
    prefetchedData: { type: Object, optional: true },
    awaitingBatch: { type: Boolean, optional: true },
    canEdit: { type: Boolean, optional: true },
    previewData: { type: String, optional: true },
    refreshKey: { type: Number, optional: true },
};
