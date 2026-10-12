/** Copyright (C) NexGen Solutions */
/** @odoo-module **/

import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { Component, onWillStart, onMounted, onWillUnmount, useState, useRef, useEffect } from "@odoo/owl";
import { loadJS, loadCSS } from "@web/core/assets";
import { DynamicDashboardItem } from "./dashboard_item";
import { session } from "@web/session";
import { user } from "@web/core/user";
import { _t } from "@web/core/l10n/translation";
import {
    getDateFilterOptions,
    resolveDashboardRtl,
} from "@dynamic_dashboard_ai_nexgen/utils/l10n";
import { preloadAmChartsCore } from "./chart_engine";
import { markDashboardPaintBurst, yieldToBrowser } from "./render_scheduler";
import { captureElementToCanvas } from "@dynamic_dashboard_ai_nexgen/utils/html2canvas_capture";

export class DynamicDashboard extends Component {
    setup() {
        this.session = session;
        this.orm = useService("orm");
        this.action = useService("action");
        this.busService = useService("bus_service");
        this.gridRef = useRef("grid");
        this.grid = null;
        this.state = useState({
            dashboards: [],
            selectedDashboard: null,
            globalDateFilter: 'none',
            globalCompare: false,
            activeCustomFilters: [],
            customFilters: [],
            customDateFilters: [],
            items: [],
            itemPayloads: {},
            awaitingPayloads: false,
            editMode: false,
            canEdit: false,
            isRtl: false,
            isMobile: false,
            backgroundColor: '#E9ECEF',
            stickyNavbar: true,
            categoryFilter: null,
            refreshKey: 0,
            refreshing: false,
            lastRefreshed: '',
            // TV Mode
            tvActive: false,
            tvPaused: false,
            tvIntervalSec: 15,
            tvModeType: 'dashboard',
            tvHideChrome: true,
            tvFocusItemId: null,
            presentMode: false,
            presentNotes: '',
            focusItemId: null,
            aiKeyword: '',
            aiMenuOpen: false,
            dateFilterOptions: getDateFilterOptions(),
        });
        this.tvInterval = null;
        this._onFullscreenChange = null;
        this._t = _t;

        onWillStart(async () => {
            this.state.canEdit = await user.hasGroup("dynamic_dashboard_ai_nexgen.group_dashboard_manager");
            this.state.isMobile = typeof window !== 'undefined' && window.innerWidth < 768;
            await Promise.all([
                loadCSS('/dynamic_dashboard_ai_nexgen/static/lib/gridstack/grid-stack.min.css'),
                loadJS('/dynamic_dashboard_ai_nexgen/static/lib/gridstack/gridstack-all.js'),
                preloadAmChartsCore().catch(() => {}),
            ]);
            await this.loadDashboards();
            this.state.customDateFilters = await this.orm.call(
                'dynamic.dashboard.date.filter',
                'get_filter_options',
                []
            );
            if (this.props.action?.context?.present_mode) {
                this._pendingPresentMode = true;
            }
        });
        
        onMounted(() => {
            this.initGridStack();
            this._onResize = () => {
                const mobile = window.innerWidth < 768;
                if (mobile !== this.state.isMobile) {
                    this.state.isMobile = mobile;
                    this.initGridStack();
                }
            };
            window.addEventListener('resize', this._onResize);
            this._onFullscreenChange = () => {
                if (!document.fullscreenElement && this.state.tvActive) {
                    this.stopTvMode();
                }
            };
            document.addEventListener('fullscreenchange', this._onFullscreenChange);
            this._onDocumentClick = (ev) => {
                if (!this.state.aiMenuOpen) {
                    return;
                }
                if (ev.target?.closest?.('.dd-ai-box')) {
                    return;
                }
                this.state.aiMenuOpen = false;
            };
            document.addEventListener('click', this._onDocumentClick);
            this.busService.addChannel("dynamic_dashboard_ai_nexgen");
            this.busService.subscribe("dynamic_dashboard_ai_nexgen_refresh", this._onBusRefresh);
            if (this._pendingPresentMode) {
                this._pendingPresentMode = false;
                // Start after grid/items exist
                setTimeout(() => this.startPresentMode(), 200);
            }
        });

        onWillUnmount(() => {
            if (this._onResize) {
                window.removeEventListener('resize', this._onResize);
            }
            if (this._onFullscreenChange) {
                document.removeEventListener('fullscreenchange', this._onFullscreenChange);
            }
            if (this._onDocumentClick) {
                document.removeEventListener('click', this._onDocumentClick);
            }
            try {
                this.busService.unsubscribe("dynamic_dashboard_ai_nexgen_refresh", this._onBusRefresh);
            } catch (e) {}
            if (this._busRefreshTimer) {
                clearTimeout(this._busRefreshTimer);
                this._busRefreshTimer = null;
            }
            if (this.tvInterval) {
                clearInterval(this.tvInterval);
                this.tvInterval = null;
            }
        });
        
        useEffect(() => {
            if (!this.state.items?.length) {
                return;
            }
            // While payloads are still streaming in, avoid destroy/recreate thrash
            if (this.state.awaitingPayloads && this.grid) {
                return;
            }
            const t = setTimeout(
                () => this.initGridStack({ light: !this.state.editMode }),
                this.state.awaitingPayloads ? 80 : 40,
            );
            return () => clearTimeout(t);
            // Do NOT depend on refreshKey — remounting GridStack on every refresh is costly
        }, () => [
            this.state.selectedDashboard?.id,
            this.state.items.length,
            this.state.isMobile,
            this.state.editMode,
            this.state.awaitingPayloads,
        ]);
    }

    async loadDashboards() {
        const dashboards = await this.orm.searchRead(
            'dynamic.dashboard',
            [],
            [
                'id', 'name', 'bookmarked_user_ids', 'is_rtl', 'layout_direction', 'background_color',
                'default_date_filter', 'tv_interval', 'tv_mode_type', 'tv_hide_chrome',
                'category_id', 'category', 'sticky_navbar', 'chart_theme', 'present_notes',
            ]
        );
        this.state.dashboards = dashboards;
        if (dashboards.length > 0) {
            let targetId = dashboards[0].id;
            const ctxId = this.props.action?.context?.default_dashboard_id;
            const urlId = this._getDashboardIdFromUrl();
            const rememberedId = this._getRememberedDashboardId();
            if (ctxId && dashboards.some((d) => d.id === ctxId)) {
                targetId = ctxId;
            } else if (urlId && dashboards.some((d) => d.id === urlId)) {
                targetId = urlId;
            } else if (rememberedId && dashboards.some((d) => d.id === rememberedId)) {
                targetId = rememberedId;
            }
            await this.selectDashboard(targetId);
        }
    }

    _getDashboardIdFromUrl() {
        try {
            const params = new URLSearchParams(window.location.search || '');
            const fromQuery = parseInt(params.get('dashboard_id'), 10);
            if (Number.isFinite(fromQuery)) {
                return fromQuery;
            }
            const hash = window.location.hash || '';
            const hashMatch = hash.match(/[?&]dashboard_id=(\d+)/);
            if (hashMatch) {
                return parseInt(hashMatch[1], 10);
            }
        } catch (e) { /* */ }
        return null;
    }

    _dashboardStorageKey() {
        const uid = user.userId || this.session?.uid || 'anon';
        return `dynamic_dashboard_ai_nexgen.last_dashboard_id.${uid}`;
    }

    _getRememberedDashboardId() {
        try {
            const raw = window.localStorage.getItem(this._dashboardStorageKey());
            const id = raw ? parseInt(raw, 10) : NaN;
            return Number.isFinite(id) ? id : null;
        } catch (e) {
            return null;
        }
    }

    _rememberDashboardId(dashboardId) {
        try {
            if (dashboardId) {
                window.localStorage.setItem(this._dashboardStorageKey(), String(dashboardId));
            }
        } catch (e) {
            // ignore quota / private mode
        }
    }

    async selectDashboard(dashboardId) {
        const dashboard = this.state.dashboards.find(d => d.id === dashboardId);
        if (dashboard) {
            this.state.selectedDashboard = dashboard;
            this._rememberDashboardId(dashboard.id);
            this.state.isRtl = resolveDashboardRtl(dashboard);
            this.state.backgroundColor = dashboard.background_color || '#E9ECEF';
            this.state.stickyNavbar = dashboard.sticky_navbar !== false;
            this.state.tvIntervalSec = dashboard.tv_interval || 15;
            this.state.tvModeType = dashboard.tv_mode_type || 'dashboard';
            this.state.tvHideChrome = dashboard.tv_hide_chrome !== false;
            this.state.tvFocusItemId = null;
            this.state.presentNotes = dashboard.present_notes || '';
            this.state.globalDateFilter = dashboard.default_date_filter || 'none';
            this.state.activeCustomFilters = [];
            this.state.itemPayloads = {};
            this.state.items = [];
            this.state.awaitingPayloads = false;
            this._stampRefresh();

            const [filters, items] = await Promise.all([
                this.orm.searchRead(
                    'dynamic.dashboard.filter',
                    [['dashboard_id', '=', dashboardId], ['is_active', '=', true]],
                    [
                        'id', 'name', 'domain', 'sequence', 'is_linked', 'widget_type',
                        'item_ids', 'analysis_ids', 'model_name', 'filter_field_id',
                    ]
                ),
                this.orm.searchRead(
                    'dynamic.dashboard.item',
                    [['dashboard_id', '=', dashboardId]],
                    [
                        'id', 'name', 'item_type', 'grid_x', 'grid_y', 'grid_w', 'grid_h',
                        'auto_update_type', 'dashboard_id', 'model_name',
                    ]
                ),
            ]);
            filters.sort((a, b) => (a.sequence || 0) - (b.sequence || 0));
            this.state.customFilters = filters;

            // Paint layout immediately; fill card data via one batched RPC
            this.state.awaitingPayloads = true;
            markDashboardPaintBurst(8000);
            this.state.items = items;
            await this._prefetchItemPayloads(items);
            this.state.awaitingPayloads = false;
            this.state.refreshKey += 1;
        }
    }

    async _prefetchItemPayloads(items = null) {
        const list = items || this.state.items || [];
        const ids = list.map((i) => i.id).filter(Boolean);
        if (!ids.length) {
            this.state.itemPayloads = {};
            return {};
        }
        const perItem = {};
        for (const item of list) {
            perItem[item.id] = {
                custom_filter_domains: this.getCustomFilterDomains(item.id),
            };
        }
        try {
            const payloads = await this.orm.call(
                'dynamic.dashboard.item',
                'fetch_items_data',
                [ids],
                {
                    shared_kwargs: {
                        global_date_filter: this.state.globalDateFilter,
                        global_compare: !!this.state.globalCompare,
                    },
                    per_item_kwargs: perItem,
                },
            );
            // Normalize keys to numbers for reliable lookup
            const normalized = {};
            for (const [k, v] of Object.entries(payloads || {})) {
                normalized[Number(k)] = v;
            }
            // Publish in small chunks so OWL + AmCharts do not freeze the tab
            await this._publishPayloadsProgressive(normalized);
            return normalized;
        } catch (e) {
            console.warn('Batch item prefetch failed; items will load individually', e);
            this.state.itemPayloads = {};
            return {};
        }
    }

    async _publishPayloadsProgressive(normalized) {
        markDashboardPaintBurst(6000);
        const byId = normalized || {};
        const ids = Object.keys(byId).map(Number).filter((n) => Number.isFinite(n));
        if (!ids.length) {
            this.state.itemPayloads = {};
            return;
        }
        // Prefer top-of-board cards first so the visible viewport fills sooner
        const layoutOrder = [...(this.state.items || [])].sort((a, b) => {
            const dy = (a.grid_y || 0) - (b.grid_y || 0);
            return dy !== 0 ? dy : (a.grid_x || 0) - (b.grid_x || 0);
        });
        const orderedIds = [];
        const seen = new Set();
        for (const item of layoutOrder) {
            if (byId[item.id] !== undefined && !seen.has(item.id)) {
                orderedIds.push(item.id);
                seen.add(item.id);
            }
        }
        for (const id of ids) {
            if (!seen.has(id)) {
                orderedIds.push(id);
            }
        }
        if (orderedIds.length <= 2) {
            this.state.itemPayloads = byId;
            return;
        }
        const chunkSize = orderedIds.length > 10 ? 1 : 2;
        const acc = {};
        for (let i = 0; i < orderedIds.length; i += chunkSize) {
            for (const id of orderedIds.slice(i, i + chunkSize)) {
                acc[id] = byId[id];
            }
            this.state.itemPayloads = { ...acc };
            await yieldToBrowser();
        }
    }

    getItemPayload(itemId) {
        return this.state.itemPayloads?.[itemId];
    }

    _onBusRefresh = (payload) => {
        if (!payload || !this.state.selectedDashboard) {
            return;
        }
        const dashId = this.state.selectedDashboard.id;
        const onBoard = payload.dashboard_id === dashId
            || (payload.item_id && (this.state.items || []).some((i) => i.id === payload.item_id));
        if (!onBoard) {
            return;
        }
        // Coalesce bursty writes into one batch reload
        if (this._busRefreshTimer) {
            clearTimeout(this._busRefreshTimer);
        }
        this._busRefreshTimer = setTimeout(() => {
            this._busRefreshTimer = null;
            this._reloadItemPayloads();
        }, 250);
    }

    onDashboardChange(ev) {
        const dashboardId = parseInt(ev.target.value);
        this.selectDashboard(dashboardId);
    }
    
    async onDashboardThemeChange(ev) {
        if (!this.state.selectedDashboard) return;
        const newTheme = ev.target.value || false;
        this.state.selectedDashboard.chart_theme = newTheme;
        await this.orm.call('dynamic.dashboard', 'update_user_preference', [this.state.selectedDashboard.id, {
            chart_theme: newTheme
        }]);
        // Push theme onto items so per-card theme resolution (item first) still updates the board
        const itemIds = (this.state.items || []).map((i) => i.id).filter(Boolean);
        if (itemIds.length && newTheme) {
            try {
                if (this.state.canEdit) {
                    await this.orm.write('dynamic.dashboard.item', itemIds, { chart_theme: newTheme });
                } else {
                    await Promise.all(itemIds.map((id) => this.orm.call(
                        'dynamic.dashboard.item',
                        'update_user_preference',
                        [id, { chart_theme: newTheme }],
                    )));
                }
            } catch (e) {
                console.warn("Could not apply dashboard theme to items", e);
            }
        }
        this.refreshAll();
    }
    
    onDateFilterChange(ev) {
        this.state.globalDateFilter = ev.target.value;
        this._reloadItemPayloads();
    }
    
    onCompareChange(ev) {
        this.state.globalCompare = ev.target.checked;
        this._reloadItemPayloads();
    }
    
    toggleCustomFilter(filterId) {
        const idx = this.state.activeCustomFilters.indexOf(filterId);
        if (idx > -1) {
            this.state.activeCustomFilters.splice(idx, 1);
        } else {
            this.state.activeCustomFilters.push(filterId);
        }
        this._reloadItemPayloads();
    }

    clearCustomFilters() {
        this.state.activeCustomFilters = [];
        this._reloadItemPayloads();
    }

    async _reloadItemPayloads() {
        if (!this.state.items?.length) return;
        this.state.refreshing = true;
        this.state.awaitingPayloads = true;
        try {
            await this._prefetchItemPayloads();
            this.state.refreshKey += 1;
            this._stampRefresh();
        } finally {
            this.state.awaitingPayloads = false;
            this.state.refreshing = false;
        }
    }

    getCategories() {
        const cats = new Set();
        for (const d of this.state.dashboards) {
            if (d.category) cats.add(d.category);
        }
        return [...cats].sort((a, b) => a.localeCompare(b));
    }

    setCategoryFilter(cat) {
        this.state.categoryFilter = cat;
        const visible = this.getVisibleDashboards();
        if (visible.length && (!this.state.selectedDashboard || !visible.find((d) => d.id === this.state.selectedDashboard.id))) {
            this.selectDashboard(visible[0].id);
        }
    }

    getVisibleDashboards() {
        if (!this.state.categoryFilter) return this.state.dashboards;
        return this.state.dashboards.filter((d) => d.category === this.state.categoryFilter);
    }

    getDashboardGroups() {
        const visible = this.getVisibleDashboards();
        const byCat = new Map();
        for (const d of visible) {
            const key = d.category || '';
            if (!byCat.has(key)) byCat.set(key, []);
            byCat.get(key).push(d);
        }
        const groups = [];
        const keys = [...byCat.keys()].sort((a, b) => {
            if (!a) return 1;
            if (!b) return -1;
            return a.localeCompare(b);
        });
        for (const key of keys) {
            groups.push({
                key: key || '_all',
                label: key || false,
                dashboards: byCat.get(key),
            });
        }
        return groups;
    }

    _stampRefresh() {
        const now = new Date();
        this.state.lastRefreshed = now.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    }

    async refreshAll() {
        this.state.refreshing = true;
        this.state.awaitingPayloads = true;
        try {
            await this._prefetchItemPayloads();
            this.state.refreshKey += 1;
            this._stampRefresh();
            this.env.services.notification.add(_t("Dashboard refreshed"), { type: 'success' });
        } finally {
            this.state.awaitingPayloads = false;
            this.state.refreshing = false;
        }
    }

    async shareFromViewer() {
        if (!this.state.selectedDashboard) return;
        try {
            const action = await this.orm.call(
                'dynamic.dashboard',
                'action_create_share_link',
                [[this.state.selectedDashboard.id]]
            );
            if (action) {
                await this.env.services.action.doAction(action);
            }
        } catch (e) {
            this.env.services.notification.add(e.message || String(e), { type: 'danger' });
        }
    }

    async openDashboardConfig() {
        if (!this.state.selectedDashboard) return;
        await this.env.services.action.doAction({
            type: 'ir.actions.act_window',
            res_model: 'dynamic.dashboard',
            res_id: this.state.selectedDashboard.id,
            views: [[false, 'form']],
            target: 'current',
        });
    }

    async duplicateDashboard() {
        if (!this.state.selectedDashboard) return;
        try {
            await this.orm.call(
                'dynamic.dashboard',
                'action_duplicate_dashboard',
                [[this.state.selectedDashboard.id]]
            );
            await this.loadDashboards();
            this.env.services.notification.add(_t("Dashboard duplicated"), { type: 'success' });
        } catch (e) {
            this.env.services.notification.add(e.message || String(e), { type: 'danger' });
        }
    }

    async createNewDashboard() {
        await this.env.services.action.doAction({
            type: 'ir.actions.act_window',
            res_model: 'dynamic.dashboard',
            views: [[false, 'form']],
            target: 'current',
        });
    }

    async openAiWizard(mode = 'create_dashboard') {
        this.state.aiMenuOpen = false;
        const actionService = this.action || this.env.services.action;
        await actionService.doAction({
            type: 'ir.actions.act_window',
            res_model: 'dynamic.dashboard.ai.wizard',
            views: [[false, 'form']],
            target: 'new',
            context: {
                default_dashboard_id: this.state.selectedDashboard?.id || false,
                default_generation_mode: mode,
                default_ai_keyword: (this.state.aiKeyword || '').trim() || false,
            },
        });
    }

    openAiCreateDashboard(ev) {
        ev?.preventDefault?.();
        ev?.stopPropagation?.();
        return this.openAiWizard('create_dashboard');
    }

    openAiGenerateItems(ev) {
        ev?.preventDefault?.();
        ev?.stopPropagation?.();
        if (!this.state.selectedDashboard) {
            this.env.services.notification.add(_t("Select a dashboard first"), { type: 'warning' });
            this.state.aiMenuOpen = false;
            return;
        }
        return this.openAiWizard('add_items');
    }

    onAiButtonClick(ev) {
        // Primary click on the magic button: open Owl menu (Bootstrap dropdown is unreliable here)
        ev?.preventDefault?.();
        ev?.stopPropagation?.();
        this.state.aiMenuOpen = !this.state.aiMenuOpen;
    }

    closeAiMenu() {
        this.state.aiMenuOpen = false;
    }

    onAiKeydown(ev) {
        if (ev.key === 'Enter') {
            ev.preventDefault();
            this.openAiGenerateItems(ev);
        } else if (ev.key === 'Escape') {
            this.closeAiMenu();
        }
    }

    async askAiKeyword(ev) {
        return this.openAiGenerateItems(ev);
    }
    
    getCustomFilterDomains(itemId = null) {
        const domains = [];
        const item = itemId
            ? (this.state.items || []).find((i) => i.id === itemId)
            : null;
        for (const fid of this.state.activeCustomFilters) {
            const f = this.state.customFilters.find((x) => x.id === fid);
            if (!f || !f.domain) {
                continue;
            }
            // Linked filters only apply to their target items (when set)
            if (f.is_linked) {
                const targetIds = (f.item_ids || []).map((x) => (Array.isArray(x) ? x[0] : x));
                if (targetIds.length) {
                    if (!itemId || !targetIds.includes(itemId)) {
                        continue;
                    }
                }
            }
            // Skip domains for a different model (avoids breaking unrelated charts)
            if (item?.model_name && f.model_name && item.model_name !== f.model_name) {
                continue;
            }
            domains.push(f.domain);
        }
        return domains;
    }
    
    async createNewItem() {
        if (!this.state.selectedDashboard) return;
        
        await this.env.services.action.doAction({
            type: 'ir.actions.act_window',
            res_model: 'dynamic.dashboard.item',
            views: [[false, 'form']],
            target: 'current',
            context: {
                default_dashboard_id: this.state.selectedDashboard.id,
            }
        });
    }
    
    toggleEditMode() {
        const entering = !this.state.editMode;
        this.state.editMode = entering;

        if (!entering && this.state.selectedDashboard) {
            // Save after useEffect re-inits grid as static — defer slightly
            setTimeout(() => {
                this._saveCurrentLayout();
                this.env.services.notification.add(_t("Layout saved"), { type: "success" });
            }, 50);
        } else if (entering) {
            this.env.services.notification.add(
                _t("Edit layout: drag the purple bar and resize from the edges"),
                { type: "info" }
            );
        }
    }

    _gridSizeForType(itemType) {
        const sizes = {
            tile: [3, 2], kpi: [3, 2], scorecard: [6, 3],
            gauge: [3, 3], radialBar: [3, 3], bullet: [6, 3],
            pie: [4, 4], doughnut: [4, 4], polarArea: [4, 4], radar: [4, 4],
            flower: [4, 4], venn: [4, 4], pictorial: [4, 4], spiral: [4, 4],
            bar: [6, 4], barLine: [6, 4], horizontalBar: [6, 4],
            line: [6, 4], area: [6, 4], stepLine: [6, 4], smoothedLine: [6, 4],
            waterfall: [6, 4], scatter: [6, 4], candlestick: [6, 4], ohlc: [6, 4],
            wordCloud: [6, 4], funnel: [4, 5], pyramid: [4, 5],
            treemap: [6, 5], sunburst: [6, 5], forceDirected: [6, 5], pack: [6, 5],
            tree: [6, 5], partition: [6, 5], voronoiTreemap: [6, 5],
            sankey: [12, 5], chord: [6, 5], chordDirected: [6, 5], chordNonRibbon: [6, 5],
            arcDiagram: [12, 4], map: [6, 5], mapPoints: [6, 5],
            heatmap: [6, 5], matrixHeatmap: [6, 5],
            timeline: [12, 4], serpentine: [12, 4],
            list: [6, 5], todo: [6, 4], iframe: [6, 5], odoo_view: [12, 6],
        };
        return sizes[itemType] || [6, 4];
    }

    _layoutPriority(itemType) {
        const order = {
            tile: 10, kpi: 20, scorecard: 30,
            bar: 100, barLine: 110, horizontalBar: 120,
            line: 130, area: 140, stepLine: 150, smoothedLine: 160,
            waterfall: 170, pie: 180, doughnut: 190,
            list: 800, todo: 900, iframe: 910, odoo_view: 920,
        };
        return order[itemType] ?? 550;
    }

    async autoArrangeLayout() {
        if (!this.state.selectedDashboard || !this.state.canEdit) return;

        try {
            await this.orm.call(
                "dynamic.dashboard",
                "action_repack_layout",
                [[this.state.selectedDashboard.id]],
            );
            this.env.services.notification.add(
                _t("Layout auto-sized and packed to remove blank space."),
                { type: "success" },
            );
            await this.selectDashboard(this.state.selectedDashboard.id);
        } catch (e) {
            console.error(e);
            this.env.services.notification.add(
                e.message || _t("Could not auto-arrange layout"),
                { type: "danger" },
            );
        }
    }

    async _saveCurrentLayout() {
        if (!this.grid || !this.state.selectedDashboard) return;
        const nodes = this.grid.engine?.nodes || [];
        for (const node of nodes) {
            const itemId = parseInt(node.el?.getAttribute("data-item-id"), 10);
            if (Number.isNaN(itemId)) continue;
            await this.orm.call("dynamic.dashboard.item", "update_user_preference", [itemId, {
                grid_x: node.x,
                grid_y: node.y,
                grid_w: node.w,
                grid_h: node.h,
            }]);
            const local = this.state.items.find((i) => i.id === itemId);
            if (local) {
                local.grid_x = node.x;
                local.grid_y = node.y;
                local.grid_w = node.w;
                local.grid_h = node.h;
            }
        }
        try {
            const layout = this.grid.save(false);
            await this.orm.call("dynamic.dashboard", "update_user_preference", [this.state.selectedDashboard.id, {
                gridstack_config: JSON.stringify(layout),
            }]);
        } catch (e) {
            // save() shape varies by GridStack version — item writes above are enough
            console.warn("gridstack_config save skipped", e);
        }
    }

    toggleTvMode() {
        if (this.state.tvActive) {
            this.stopTvMode();
            if (document.fullscreenElement) {
                document.exitFullscreen();
            }
            return;
        }
        const elem = document.querySelector('.dynamic-dashboard-container');
        if (!elem) return;
        elem.requestFullscreen().catch((err) => {
            this.env.services.notification.add(
                `Error attempting to enable fullscreen mode: ${err.message}`,
                { type: 'danger' }
            );
        });
        this.state.tvActive = true;
        this.state.tvPaused = false;
        this.startTvTicker();
    }

    stopTvMode() {
        this.state.tvActive = false;
        this.state.tvPaused = false;
        this.state.tvFocusItemId = null;
        this.state.presentMode = false;
        this.clearTvTicker();
    }

    clearTvTicker() {
        if (this.tvInterval) {
            clearInterval(this.tvInterval);
            this.tvInterval = null;
        }
    }

    startTvTicker() {
        this.clearTvTicker();
        const ms = Math.max(3, this.state.tvIntervalSec || 15) * 1000;
        this.tvInterval = setInterval(() => {
            if (this.state.tvPaused || !this.state.tvActive) return;
            this.advanceTvSlide();
        }, ms);
    }

    advanceTvSlide() {
        if (this.state.tvModeType === 'item') {
            const items = this.state.items || [];
            if (!items.length) return;
            const idx = items.findIndex((i) => i.id === this.state.tvFocusItemId);
            const next = items[(idx + 1) % items.length];
            this.state.tvFocusItemId = next.id;
            return;
        }
        if (this.state.dashboards.length > 1) {
            let idx = this.state.dashboards.findIndex((d) => d.id === this.state.selectedDashboard.id);
            idx = (idx + 1) % this.state.dashboards.length;
            this.selectDashboard(this.state.dashboards[idx].id);
        }
    }

    toggleTvPause() {
        this.state.tvPaused = !this.state.tvPaused;
    }

    onTvIntervalChange(ev) {
        const val = parseInt(ev.target.value, 10) || 15;
        this.state.tvIntervalSec = val;
        if (this.state.tvActive && !this.state.tvPaused) {
            this.startTvTicker();
        }
    }

    onTvModeTypeChange(ev) {
        this.state.tvModeType = ev.target.value;
        this.state.tvFocusItemId = null;
        if (this.state.tvModeType === 'item' && this.state.items.length) {
            this.state.tvFocusItemId = this.state.items[0].id;
        }
    }

    isTvFocused(itemId) {
        if (this.state.focusItemId) {
            return this.state.focusItemId === itemId;
        }
        if (!this.state.tvActive || this.state.tvModeType !== 'item') return true;
        if (!this.state.tvFocusItemId) return true;
        return this.state.tvFocusItemId === itemId;
    }

    toggleFocusItem(itemId) {
        this.state.focusItemId = this.state.focusItemId === itemId ? null : itemId;
    }

    startPresentMode() {
        this.state.presentMode = true;
        this.state.tvModeType = 'item';
        this.state.tvActive = true;
        this.state.tvPaused = false;
        this.state.tvHideChrome = true;
        this.state.presentNotes = this.state.selectedDashboard?.present_notes || this.state.presentNotes || '';
        if (this.state.items.length) {
            this.state.tvFocusItemId = this.state.items[0].id;
        }
        const elem = document.querySelector('.dynamic-dashboard-container');
        if (elem && !document.fullscreenElement) {
            elem.requestFullscreen?.().catch(() => {});
        }
        this.startTvTicker();
    }

    async exportPNG() {
        try {
            const canvas = await this._getDashboardCanvas();
            const img = canvas.toDataURL('image/png', 1.0);
            const a = document.createElement('a');
            a.href = img;
            a.download = `${this.state.selectedDashboard?.name || 'dashboard'}.png`;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            this.env.services.notification.add(_t("PNG exported"), { type: 'success' });
        } catch (e) {
            this.env.services.notification.add(_t("PNG export failed: " + (e.message || e)), { type: 'danger' });
            console.error(e);
        }
    }

    async exportPDF() {
        this.env.services.notification.add(_t("Generating PDF..."), { type: 'info' });
        try {
            if (!window.jspdf) {
                await this.loadScript('https://cdnjs.cloudflare.com/ajax/libs/jspdf/2.5.1/jspdf.umd.min.js');
            }
            const canvas = await this._getDashboardCanvas();
            const imgData = canvas.toDataURL('image/jpeg', 0.92);
            const pdf = new window.jspdf.jsPDF({
                orientation: canvas.width > canvas.height ? 'l' : 'p',
                unit: 'mm',
                format: 'a4',
            });
            const pageWidth = pdf.internal.pageSize.getWidth();
            const pageHeight = pdf.internal.pageSize.getHeight();
            const margin = 8;
            const headerH = 10;
            const usableWidth = pageWidth - margin * 2;
            const usableHeight = pageHeight - margin * 2 - headerH;
            const imgWidth = usableWidth;
            const imgHeight = (canvas.height * imgWidth) / canvas.width;

            const title = this.state.selectedDashboard?.name || 'Dashboard';
            let heightLeft = imgHeight;
            let position = margin + headerH;
            let page = 1;

            const drawHeader = () => {
                pdf.setFontSize(11);
                pdf.setTextColor(40);
                pdf.text(title, margin, margin + 5);
                pdf.setFontSize(8);
                pdf.setTextColor(120);
                pdf.text(`Page ${page}`, pageWidth - margin, margin + 5, { align: 'right' });
            };

            drawHeader();
            pdf.addImage(imgData, 'JPEG', margin, position, imgWidth, imgHeight);
            heightLeft -= usableHeight;

            while (heightLeft > 0) {
                page += 1;
                position = margin + headerH - (imgHeight - heightLeft);
                pdf.addPage();
                drawHeader();
                pdf.addImage(imgData, 'JPEG', margin, position, imgWidth, imgHeight);
                heightLeft -= usableHeight;
            }

            pdf.save(`${title}_Dashboard.pdf`);
            this.env.services.notification.add(_t("PDF Exported successfully!"), { type: 'success' });
        } catch (e) {
            this.env.services.notification.add(_t("Failed to generate PDF"), { type: 'danger' });
            console.error(e);
        }
    }

    get isBookmarked() {
        if (!this.state.selectedDashboard || !this.state.selectedDashboard.bookmarked_user_ids) return false;
        return this.state.selectedDashboard.bookmarked_user_ids.includes(user.userId);
    }

    async toggleBookmark() {
        if (!this.state.selectedDashboard) return;
        const isNowBookmarked = await this.orm.call('dynamic.dashboard', 'toggle_bookmark', [[this.state.selectedDashboard.id]]);
        if (isNowBookmarked) {
            this.state.selectedDashboard.bookmarked_user_ids = [...this.state.selectedDashboard.bookmarked_user_ids, user.userId];
        } else {
            this.state.selectedDashboard.bookmarked_user_ids = this.state.selectedDashboard.bookmarked_user_ids.filter(id => id !== user.userId);
        }
        this.env.services.notification.add(
            isNowBookmarked ? _t("Dashboard bookmarked!") : _t("Dashboard removed from bookmarks."),
            { type: "success" }
        );
    }

    async loadScript(src) {
        return new Promise((resolve, reject) => {
            const script = document.createElement('script');
            script.src = src;
            script.onload = resolve;
            script.onerror = reject;
            document.head.appendChild(script);
        });
    }

    async _getDashboardCanvas() {
        const container = document.querySelector('.dashboard-items-container');
        return captureElementToCanvas(container);
    }

    async _getDashboardImage() {
        const canvas = await this._getDashboardCanvas();
        return canvas.toDataURL('image/jpeg', 0.92);
    }

    async sendEmail() {
        this.env.services.notification.add(_t("Preparing Dashboard snapshot..."), { type: 'info' });
        try {
            const imgData = await this._getDashboardImage();
            const base64Data = imgData.split(',')[1];
            
            const action = await this.orm.call(
                'dynamic.dashboard',
                'action_send_dashboard_email',
                [this.state.selectedDashboard.id, base64Data]
            );
            await this.env.services.action.doAction(action);
            if (action?.tag !== 'display_notification') {
                this.env.services.notification.add(_t("Email composer opened with snapshot attached."), { type: 'success' });
            }
        } catch (e) {
            this.env.services.notification.add(e.message || _t("Failed to prepare email"), { type: 'danger' });
            console.error(e);
        }
    }

    initGridStack(options = {}) {
        if (!this.gridRef.el) return;
        const light = !!options.light;

        if (this.grid) {
            this.grid.destroy(false);
            this.grid = null;
        }

        const editing = this.state.editMode && !this.state.isMobile;

        this.grid = window.GridStack.init({
            column: this.state.isMobile ? 1 : 12,
            cellHeight: this.state.isMobile ? 120 : 110,
            staticGrid: !editing,
            margin: this.state.isMobile ? 6 : 8,
            // Only float while actively editing — otherwise GridStack leaves blank holes
            float: editing,
            disableOneColumnMode: !this.state.isMobile,
            oneColumnSize: 768,
            // Charts steal pointer events — only the handle starts a drag
            handle: editing ? ".dd-drag-handle" : undefined,
            draggable: editing
                ? { handle: ".dd-drag-handle", appendTo: "body", scroll: true }
                : undefined,
            resizable: editing
                ? { handles: "e, se, s, sw, w" }
                : undefined,
            // Avoid expensive animate/layout passes while browsing
            animate: editing,
        }, this.gridRef.el);

        if (editing && this.grid) {
            this.grid.setStatic(false);
            if (typeof this.grid.enableMove === "function") {
                this.grid.enableMove(true);
            }
            if (typeof this.grid.enableResize === "function") {
                this.grid.enableResize(true);
            }
        } else if (!light && this.grid && typeof this.grid.compact === "function") {
            // Compact only when explicitly requested (edit/layout repair) — not on every view load
            try {
                this.grid.compact("list");
            } catch (_e) {
                try { this.grid.compact(); } catch (__e) { /* older GridStack */ }
            }
        }

        // Ensure container height matches all rows after OWL paints items
        requestAnimationFrame(() => {
            if (!this.grid) return;
            if (typeof this.grid.onParentResize === "function") {
                this.grid.onParentResize();
            }
            // During light boot, skip broadcasting resize to every chart (causes jank)
            if (!light) {
                this._notifyChartsResize();
            }
        });

        this.grid.on("change", async (event, items) => {
            if (this.state.isMobile || !this.state.editMode) return;
            if (items && items.length > 0) {
                for (let item of items) {
                    const itemId = parseInt(item.el.getAttribute("data-item-id"), 10);
                    if (Number.isNaN(itemId)) continue;
                    await this.orm.call("dynamic.dashboard.item", "update_user_preference", [itemId, {
                        grid_x: item.x,
                        grid_y: item.y,
                        grid_w: item.w,
                        grid_h: item.h,
                    }]);
                    const local = this.state.items.find((i) => i.id === itemId);
                    if (local) {
                        local.grid_x = item.x;
                        local.grid_y = item.y;
                        local.grid_w = item.w;
                        local.grid_h = item.h;
                    }
                }
            }
            this._notifyChartsResize();
        });

        // Live resize while dragging handles in edit mode
        this.grid.on("resizestop", () => this._notifyChartsResize());
        this.grid.on("resize", () => this._notifyChartsResize(true));
        this.grid.on("dragstop", () => this._notifyChartsResize());
    }

    _notifyChartsResize(live = false) {
        // During live drag, throttle; on stop, do a settle pass
        if (live) {
            if (this._chartResizeNotifyRaf) return;
            this._chartResizeNotifyRaf = requestAnimationFrame(() => {
                this._chartResizeNotifyRaf = null;
                const cards = this.gridRef.el?.querySelectorAll(".dynamic-dashboard-item") || [];
                cards.forEach((el) => {
                    el.dispatchEvent(new CustomEvent("dd-chart-resize", { bubbles: true }));
                });
            });
            return;
        }
        const run = () => {
            const cards = this.gridRef.el?.querySelectorAll(".dynamic-dashboard-item") || [];
            cards.forEach((el) => {
                el.dispatchEvent(new CustomEvent("dd-chart-resize", { bubbles: true }));
            });
        };
        requestAnimationFrame(() => {
            run();
            setTimeout(run, 80);
        });
    }
}

DynamicDashboard.template = "dynamic_dashboard_ai_nexgen.Dashboard";
DynamicDashboard.components = { DynamicDashboardItem };
DynamicDashboard.props = ["*"];

registry.category("actions").add("dynamic_dashboard_ai_nexgen.dashboard_view", DynamicDashboard);
