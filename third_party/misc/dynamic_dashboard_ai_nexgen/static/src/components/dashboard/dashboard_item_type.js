/** Copyright (C) NexGen Solutions */
/** @odoo-module **/

import { Component, useState, xml } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { standardFieldProps } from "@web/views/fields/standard_field_props";

const TYPE_META = {
    tile: { label: "Tile", icon: "fa-th-large", category: "cards", hint: "Single metric card" },
    kpi: { label: "KPI", icon: "fa-tachometer", category: "cards", hint: "Compare & track KPIs" },
    scorecard: { label: "Scorecard", icon: "fa-id-card-o", category: "cards", hint: "Multi-cell metrics" },
    bar: { label: "Bar", icon: "fa-bar-chart", category: "bars", hint: "Compare categories" },
    barLine: { label: "Bar + Line", icon: "fa-signal", category: "bars", hint: "Dual series chart" },
    horizontalBar: { label: "H-Bar", icon: "fa-align-left", category: "bars", hint: "Horizontal bars" },
    waterfall: { label: "Waterfall", icon: "fa-sort-amount-asc", category: "bars", hint: "Cumulative change" },
    bullet: { label: "Bullet", icon: "fa-tasks", category: "bars", hint: "Target vs actual" },
    heatmap: { label: "Heatmap", icon: "fa-th", category: "bars", hint: "Intensity matrix" },
    matrixHeatmap: { label: "Matrix", icon: "fa-table", category: "bars", hint: "2D heat matrix" },
    candlestick: { label: "Candle", icon: "fa-btc", category: "bars", hint: "OHLC candles" },
    ohlc: { label: "OHLC", icon: "fa-sliders", category: "bars", hint: "Open-high-low-close" },
    line: { label: "Line", icon: "fa-line-chart", category: "lines", hint: "Trends over time" },
    area: { label: "Area", icon: "fa-area-chart", category: "lines", hint: "Filled trend" },
    stepLine: { label: "Step", icon: "fa-area-chart", category: "lines", hint: "Step changes" },
    smoothedLine: { label: "Smoothed", icon: "fa-magic", category: "lines", hint: "Curved trend" },
    scatter: { label: "Scatter", icon: "fa-dot-circle-o", category: "lines", hint: "X / Y points" },
    timeline: { label: "Timeline", icon: "fa-clock-o", category: "lines", hint: "Events in time" },
    serpentine: { label: "Serpentine", icon: "fa-long-arrow-right", category: "lines", hint: "Winding timeline" },
    spiral: { label: "Spiral", icon: "fa-refresh", category: "lines", hint: "Spiral timeline" },
    pie: { label: "Pie", icon: "fa-pie-chart", category: "circular", hint: "Part-to-whole" },
    doughnut: { label: "Doughnut", icon: "fa-circle-o-notch", category: "circular", hint: "Ring breakdown" },
    polarArea: { label: "Polar", icon: "fa-life-ring", category: "circular", hint: "Polar sectors" },
    radar: { label: "Radar", icon: "fa-bullseye", category: "circular", hint: "Multi-axis spider" },
    flower: { label: "Flower", icon: "fa-pagelines", category: "circular", hint: "Petal chart" },
    radialBar: { label: "Radial", icon: "fa-spinner", category: "circular", hint: "Circular bars" },
    gauge: { label: "Gauge", icon: "fa-dashboard", category: "circular", hint: "Speedometer" },
    funnel: { label: "Funnel", icon: "fa-filter", category: "circular", hint: "Conversion stages" },
    pyramid: { label: "Pyramid", icon: "fa-sort-amount-desc", category: "circular", hint: "Hierarchy levels" },
    pictorial: { label: "Pictorial", icon: "fa-picture-o", category: "circular", hint: "Icon-based chart" },
    venn: { label: "Venn", icon: "fa-circle-o", category: "circular", hint: "Overlapping sets" },
    treemap: { label: "Treemap", icon: "fa-th-large", category: "hierarchy", hint: "Nested rectangles" },
    sunburst: { label: "Sunburst", icon: "fa-sun-o", category: "hierarchy", hint: "Radial hierarchy" },
    forceDirected: { label: "Force", icon: "fa-share-alt", category: "hierarchy", hint: "Network graph" },
    pack: { label: "Pack", icon: "fa-circle", category: "hierarchy", hint: "Circle packing" },
    tree: { label: "Tree", icon: "fa-sitemap", category: "hierarchy", hint: "Tree layout" },
    partition: { label: "Partition", icon: "fa-columns", category: "hierarchy", hint: "Icicle / partition" },
    voronoiTreemap: { label: "Voronoi", icon: "fa-delicious", category: "hierarchy", hint: "Organic cells" },
    sankey: { label: "Sankey", icon: "fa-random", category: "flow", hint: "Flow volumes" },
    chord: { label: "Chord", icon: "fa-refresh", category: "flow", hint: "Relationship arcs" },
    chordDirected: { label: "Dir. Chord", icon: "fa-mail-forward", category: "flow", hint: "Directed links" },
    chordNonRibbon: { label: "Chord NR", icon: "fa-circle-o-notch", category: "flow", hint: "Non-ribbon chord" },
    arcDiagram: { label: "Arc", icon: "fa-exchange", category: "flow", hint: "Arc connections" },
    map: { label: "Map", icon: "fa-globe", category: "map", hint: "Geographic regions" },
    mapPoints: { label: "Map Points", icon: "fa-map-marker", category: "map", hint: "Pinned locations" },
    wordCloud: { label: "Words", icon: "fa-cloud", category: "content", hint: "Word frequency" },
    list: { label: "List", icon: "fa-list-ul", category: "content", hint: "Tabular records" },
    todo: { label: "To-Do", icon: "fa-check-square-o", category: "content", hint: "Checklist tasks" },
    iframe: { label: "Iframe", icon: "fa-window-maximize", category: "content", hint: "Embed a URL" },
    odoo_view: { label: "Odoo View", icon: "fa-external-link", category: "content", hint: "Embed an action" },
};

const CATEGORIES = [
    { id: "all", label: "All", icon: "fa-th" },
    { id: "cards", label: "Cards", icon: "fa-id-badge" },
    { id: "bars", label: "Bars", icon: "fa-bar-chart" },
    { id: "lines", label: "Lines", icon: "fa-line-chart" },
    { id: "circular", label: "Circular", icon: "fa-pie-chart" },
    { id: "hierarchy", label: "Hierarchy", icon: "fa-sitemap" },
    { id: "flow", label: "Flow", icon: "fa-random" },
    { id: "map", label: "Map", icon: "fa-globe" },
    { id: "content", label: "Content", icon: "fa-files-o" },
];

const FALLBACK_ICON = "fa-cube";

export class DynamicDashboardItemType extends Component {
    static template = xml`
        <div class="dd-type-picker" t-att-class="{'dd-type-picker--readonly': props.readonly}">
            <div class="dd-type-picker__selected" t-if="selectedType">
                <div class="dd-type-picker__selected-icon" t-att-data-cat="selectedType.category">
                    <i t-attf-class="fa {{ selectedType.icon }}"/>
                </div>
                <div class="dd-type-picker__selected-meta">
                    <span class="dd-type-picker__selected-label"><t t-esc="selectedType.label"/></span>
                    <span class="dd-type-picker__selected-hint"><t t-esc="selectedType.hint"/></span>
                </div>
                <span class="dd-type-picker__selected-badge">Selected</span>
            </div>

            <div class="dd-type-picker__toolbar">
                <div class="dd-type-picker__search">
                    <i class="fa fa-search"/>
                    <input type="text"
                           class="dd-type-picker__search-input"
                           placeholder="Search visual types…"
                           t-att-value="state.query"
                           t-on-input="onSearchInput"
                           t-att-disabled="props.readonly"/>
                    <button type="button"
                            class="dd-type-picker__search-clear"
                            t-if="state.query"
                            t-on-click="clearSearch"
                            title="Clear search">
                        <i class="fa fa-times"/>
                    </button>
                </div>
            </div>

            <div class="dd-type-picker__cats" role="tablist">
                <t t-foreach="categories" t-as="cat" t-key="cat.id">
                    <button type="button"
                            class="dd-type-picker__cat"
                            t-att-class="{'is-active': state.category === cat.id}"
                            t-att-data-cat="cat.id"
                            t-on-click="() => this.setCategory(cat.id)"
                            t-att-disabled="props.readonly"
                            t-att-title="cat.label">
                        <i t-attf-class="fa {{ cat.icon }}"/>
                        <span t-esc="cat.label"/>
                    </button>
                </t>
            </div>

            <div class="dd-type-picker__grid">
                <t t-foreach="filteredTypes" t-as="type" t-key="type.id">
                    <button type="button"
                            class="dd-type-card"
                            t-att-class="{
                                'is-selected': isSelected(type.id),
                                'is-disabled': props.readonly,
                            }"
                            t-att-data-cat="type.category"
                            t-on-click="() => this.selectType(type.id)"
                            t-att-title="type.hint"
                            t-att-disabled="props.readonly"
                            t-att-aria-pressed="isSelected(type.id) ? 'true' : 'false'">
                        <span class="dd-type-card__check" t-if="isSelected(type.id)">
                            <i class="fa fa-check"/>
                        </span>
                        <span class="dd-type-card__glyph" t-att-data-cat="type.category">
                            <i t-attf-class="fa {{ type.icon }}"/>
                            <svg class="dd-type-card__spark" viewBox="0 0 40 18" aria-hidden="true">
                                <t t-if="type.category === 'bars'">
                                    <rect x="2" y="10" width="5" height="6" rx="1"/>
                                    <rect x="10" y="6" width="5" height="10" rx="1"/>
                                    <rect x="18" y="3" width="5" height="13" rx="1"/>
                                    <rect x="26" y="8" width="5" height="8" rx="1"/>
                                    <rect x="34" y="5" width="4" height="11" rx="1"/>
                                </t>
                                <t t-elif="type.category === 'lines'">
                                    <polyline fill="none" stroke-width="1.6" stroke-linecap="round"
                                              stroke-linejoin="round"
                                              points="2,14 10,9 16,11 24,4 32,7 38,3"/>
                                </t>
                                <t t-elif="type.category === 'circular'">
                                    <circle cx="20" cy="9" r="6.5" fill="none" stroke-width="2.2"
                                            stroke-dasharray="14 28"/>
                                    <circle cx="20" cy="9" r="3.2" fill="currentColor" opacity="0.25"/>
                                </t>
                                <t t-elif="type.category === 'hierarchy'">
                                    <rect x="2" y="2" width="16" height="14" rx="1.5"/>
                                    <rect x="20" y="2" width="8" height="7" rx="1"/>
                                    <rect x="30" y="2" width="8" height="7" rx="1"/>
                                    <rect x="20" y="11" width="18" height="5" rx="1"/>
                                </t>
                                <t t-elif="type.category === 'flow'">
                                    <path fill="none" stroke-width="1.8" stroke-linecap="round"
                                          d="M2,4 C12,4 12,14 22,14 C30,14 32,8 38,8"/>
                                    <path fill="none" stroke-width="1.4" stroke-linecap="round" opacity="0.55"
                                          d="M2,14 C10,14 12,6 22,6 C30,6 34,12 38,12"/>
                                </t>
                                <t t-elif="type.category === 'map'">
                                    <ellipse cx="20" cy="9" rx="14" ry="7" fill="none" stroke-width="1.5"/>
                                    <path fill="none" stroke-width="1.2"
                                          d="M12,5 Q16,10 14,14 M26,4 Q24,9 28,14 M6,9 H34"/>
                                </t>
                                <t t-elif="type.category === 'cards'">
                                    <rect x="4" y="3" width="32" height="12" rx="2" fill="none" stroke-width="1.5"/>
                                    <rect x="8" y="6" width="10" height="2.5" rx="0.8" fill="currentColor" opacity="0.55"/>
                                    <rect x="8" y="11" width="18" height="1.8" rx="0.6" fill="currentColor" opacity="0.3"/>
                                </t>
                                <t t-else="">
                                    <rect x="4" y="3" width="14" height="2" rx="1" fill="currentColor" opacity="0.45"/>
                                    <rect x="4" y="8" width="28" height="2" rx="1" fill="currentColor" opacity="0.35"/>
                                    <rect x="4" y="13" width="20" height="2" rx="1" fill="currentColor" opacity="0.25"/>
                                </t>
                            </svg>
                        </span>
                        <span class="dd-type-card__label"><t t-esc="type.label"/></span>
                    </button>
                </t>
                <div class="dd-type-picker__empty" t-if="!filteredTypes.length">
                    <i class="fa fa-search"/>
                    <span>No types match your search</span>
                </div>
            </div>

            <div class="dd-type-picker__footer">
                <span><t t-esc="filteredTypes.length"/> shown</span>
                <span t-if="state.category !== 'all' or state.query">of <t t-esc="allTypes.length"/></span>
            </div>
        </div>
    `;

    static props = {
        ...standardFieldProps,
    };

    setup() {
        this.state = useState({
            category: "all",
            query: "",
        });
        this.categories = CATEGORIES;
    }

    get allTypes() {
        return Object.entries(TYPE_META).map(([id, meta]) => ({
            id,
            label: meta.label,
            icon: meta.icon || FALLBACK_ICON,
            category: meta.category,
            hint: meta.hint || meta.label,
        }));
    }

    get filteredTypes() {
        const q = (this.state.query || "").trim().toLowerCase();
        return this.allTypes.filter((type) => {
            // Search always spans every category so users aren't trapped in a filter
            if (!q && this.state.category !== "all" && type.category !== this.state.category) {
                return false;
            }
            if (!q) {
                return true;
            }
            return (
                type.label.toLowerCase().includes(q) ||
                type.id.toLowerCase().includes(q) ||
                type.hint.toLowerCase().includes(q) ||
                type.category.toLowerCase().includes(q)
            );
        });
    }

    get selectedType() {
        const id = this.props.record.data[this.props.name];
        if (!id || !TYPE_META[id]) {
            return null;
        }
        const meta = TYPE_META[id];
        return {
            id,
            label: meta.label,
            icon: meta.icon || FALLBACK_ICON,
            category: meta.category,
            hint: meta.hint || meta.label,
        };
    }

    isSelected(typeId) {
        return this.props.record.data[this.props.name] === typeId;
    }

    setCategory(categoryId) {
        if (this.props.readonly) {
            return;
        }
        this.state.category = categoryId;
    }

    onSearchInput(ev) {
        this.state.query = ev.target.value || "";
    }

    clearSearch() {
        this.state.query = "";
    }

    selectType(typeId) {
        if (this.props.readonly) {
            return;
        }
        this.props.record.update({ [this.props.name]: typeId });
        // Jump category to the selected type's family for nicer context
        const meta = TYPE_META[typeId];
        if (meta && this.state.category !== "all" && this.state.category !== meta.category) {
            this.state.category = meta.category;
        }
    }
}

registry.category("fields").add("dynamic_dashboard_ai_nexgen_item_type", {
    component: DynamicDashboardItemType,
});

// -------------------------------------------------------------------------
// Tile / KPI / Scorecard layout picker (Appearance tab)
// -------------------------------------------------------------------------

const TILE_LAYOUTS = [
    { id: "layout1", label: "Accent Left", hint: "Clean metric with a bold left rail" },
    { id: "layout2", label: "Icon Left", hint: "Icon-led row with value on the right" },
    { id: "layout3", label: "Centered", hint: "Stacked, centered hero metric" },
    { id: "layout4", label: "Gradient Hero", hint: "Full-bleed gradient with glass icon" },
    { id: "layout5", label: "Split Band", hint: "Colored side band with icon" },
    { id: "layout6", label: "Soft Float", hint: "Floating glow with corner icon" },
    { id: "layout7", label: "Value First", hint: "Oversized number, minimal chrome" },
    { id: "layout8", label: "Pill Header", hint: "Gradient pill title over the value" },
];

export class DynamicDashboardTileLayoutPicker extends Component {
    static template = xml`
        <div class="dd-layout-picker" t-att-class="{'dd-layout-picker--readonly': props.readonly}">
            <div class="dd-layout-picker__grid">
                <t t-foreach="layouts" t-as="layout" t-key="layout.id">
                    <button type="button"
                            t-attf-class="dd-layout-card {{isSelected(layout.id) ? 'is-selected' : ''}}"
                            t-on-click="() => this.selectLayout(layout.id)"
                            t-att-disabled="props.readonly"
                            t-att-title="layout.hint">
                        <div t-attf-class="dd-layout-mini dd-layout-mini--{{layout.id}}">
                            <div class="dd-layout-mini__rail"/>
                            <div class="dd-layout-mini__band"/>
                            <div class="dd-layout-mini__pill">
                                <span class="dd-layout-mini__pill-text"/>
                                <span class="dd-layout-mini__pill-dot"/>
                            </div>
                            <div class="dd-layout-mini__body">
                                <span class="dd-layout-mini__label"/>
                                <span class="dd-layout-mini__value"/>
                                <span class="dd-layout-mini__bar"/>
                            </div>
                            <div class="dd-layout-mini__icon"/>
                            <div class="dd-layout-mini__glow"/>
                        </div>
                        <div class="dd-layout-card__meta">
                            <span class="dd-layout-card__label"><t t-esc="layout.label"/></span>
                            <span class="dd-layout-card__hint"><t t-esc="layout.hint"/></span>
                        </div>
                    </button>
                </t>
            </div>
        </div>
    `;

    static props = {
        ...standardFieldProps,
    };

    setup() {
        this.layouts = TILE_LAYOUTS;
    }

    isSelected(layoutId) {
        return (this.props.record.data[this.props.name] || "layout1") === layoutId;
    }

    selectLayout(layoutId) {
        if (this.props.readonly) {
            return;
        }
        this.props.record.update({ [this.props.name]: layoutId });
    }
}

registry.category("fields").add("dynamic_dashboard_ai_nexgen_tile_layout", {
    component: DynamicDashboardTileLayoutPicker,
});
