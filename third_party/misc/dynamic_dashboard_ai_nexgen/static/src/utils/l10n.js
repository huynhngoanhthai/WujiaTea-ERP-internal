/** Copyright (C) NexGen Solutions */
/** @odoo-module **/

import { _t } from "@web/core/l10n/translation";
import { user } from "@web/core/user";
import { session } from "@web/session";

/** Languages that use right-to-left scripts (ISO 639-1 prefixes). */
const RTL_LANG_PREFIXES = ["ar", "fa", "he", "ur", "yi", "ps", "sd", "ug", "dv"];

/**
 * Current user language code (e.g. en_US, ar_001).
 */
export function getUserLang() {
    return user.lang || session.user_context?.lang || "en_US";
}

/**
 * BCP 47 locale for Intl (en_US → en-US).
 */
export function getUserLocale() {
    return String(getUserLang()).replace(/_/g, "-");
}

/**
 * Whether the given language code is RTL.
 */
export function isLangRtl(lang = getUserLang()) {
    const code = String(lang || "").toLowerCase().split(/[_-]/)[0];
    return RTL_LANG_PREFIXES.includes(code);
}

/**
 * Resolve effective dashboard direction.
 * layout_direction: auto | ltr | rtl
 * is_rtl (legacy): force RTL when true
 */
export function resolveDashboardRtl(dashboard) {
    if (!dashboard) {
        return isLangRtl();
    }
    if (dashboard.is_rtl) {
        return true;
    }
    const dir = dashboard.layout_direction || "auto";
    if (dir === "rtl") {
        return true;
    }
    if (dir === "ltr") {
        return false;
    }
    return isLangRtl();
}

/**
 * Global date filter options (labels are translated).
 */
export function getDateFilterOptions() {
    return [
        { value: "none", label: _t("No Global Date Filter") },
        { value: "today", label: _t("Today") },
        { value: "yesterday", label: _t("Yesterday") },
        { value: "tomorrow", label: _t("Tomorrow") },
        { value: "this_week", label: _t("This Week") },
        { value: "this_month", label: _t("This Month") },
        { value: "this_quarter", label: _t("This Quarter") },
        { value: "this_year", label: _t("This Year") },
        { value: "week_to_date", label: _t("Week to Date") },
        { value: "month_to_date", label: _t("Month to Date") },
        { value: "year_to_date", label: _t("Year to Date") },
        { value: "last_7_days", label: _t("Last 7 Days") },
        { value: "last_30_days", label: _t("Last 30 Days") },
        { value: "last_90_days", label: _t("Last 90 Days") },
        { value: "last_week", label: _t("Last Week") },
        { value: "last_month", label: _t("Last Month") },
        { value: "last_quarter", label: _t("Last Quarter") },
        { value: "last_year", label: _t("Last Year") },
        { value: "past_until_now", label: _t("Past Until Now") },
        { value: "future_starting_now", label: _t("Future Starting Now") },
        { value: "next_week", label: _t("Next Week") },
        { value: "next_month", label: _t("Next Month") },
        { value: "next_quarter", label: _t("Next Quarter") },
        { value: "next_year", label: _t("Next Year") },
    ];
}

/**
 * Format a number for dashboard tiles/charts using locale + optional currency.
 * @param {number} value
 * @param {object} data item payload (currency, data_format, number_system, …)
 * @param {string} [locale]
 */
export function formatDashboardNumber(value, data = {}, locale = getUserLocale()) {
    if (value === undefined || value === null || Number.isNaN(Number(value))) {
        return "";
    }
    const num = Number(value);
    const precision = data.precision_digits != null ? data.precision_digits : 2;
    const unit = data.unit;
    // Explicit unit from Display tab takes priority over default company currency
    const useCurrency = !unit && data.currency?.name;

    if (data.number_system && data.number_system.length) {
        const abs = Math.abs(num);
        const sign = num < 0 ? "-" : "";
        for (const line of data.number_system) {
            if (abs >= line.threshold && line.divisor) {
                const formatted = (abs / line.divisor)
                    .toFixed(Math.min(precision, 1))
                    .replace(/\.0$/, "");
                const withSuffix = `${sign}${formatted}${line.suffix || ""}`;
                if (unit) {
                    return data.unit_position === "prefix"
                        ? `${unit} ${withSuffix}`
                        : `${withSuffix} ${unit}`;
                }
                return withSuffix;
            }
        }
    }

    const format = data.data_format || "exact";
    const currency = data.currency;

    if (format === "english") {
        const compact = new Intl.NumberFormat(locale, {
            notation: "compact",
            compactDisplay: "short",
            maximumFractionDigits: Math.min(precision, 2),
        }).format(num);
        if (unit) {
            return data.unit_position === "prefix" ? `${unit} ${compact}` : `${compact} ${unit}`;
        }
        if (currency?.name) {
            try {
                const sym = currency.symbol || currency.name;
                return currency.position === "after" ? `${compact} ${sym}` : `${sym} ${compact}`;
            } catch (e) {
                return compact;
            }
        }
        return compact;
    }

    if (format === "indian") {
        const formattedStr = new Intl.NumberFormat("en-IN", {
            minimumFractionDigits: 0,
            maximumFractionDigits: precision,
        }).format(num);
        if (unit) {
            return data.unit_position === "prefix"
                ? `${unit} ${formattedStr}`
                : `${formattedStr} ${unit}`;
        }
        if (currency?.symbol || currency?.name) {
            const sym = currency.symbol || currency.name;
            return currency.position === "after" ? `${formattedStr} ${sym}` : `${sym} ${formattedStr}`;
        }
        return formattedStr;
    }

    // Prefer ISO currency formatting when we have a currency code and no unit
    if (useCurrency) {
        try {
            return new Intl.NumberFormat(locale, {
                style: "currency",
                currency: currency.name,
                minimumFractionDigits: currency.decimal_places ?? 0,
                maximumFractionDigits: currency.decimal_places ?? precision,
            }).format(num);
        } catch (e) {
            // Invalid currency code — fall through to symbol formatting
        }
    }

    let formattedStr = new Intl.NumberFormat(locale, {
        minimumFractionDigits: 0,
        maximumFractionDigits: precision,
    }).format(num);

    if (unit) {
        if (data.unit_position === "prefix") {
            return `${unit} ${formattedStr}`;
        }
        return `${formattedStr} ${unit}`;
    }

    if (currency?.symbol) {
        return currency.position === "after"
            ? `${formattedStr} ${currency.symbol}`
            : `${currency.symbol} ${formattedStr}`;
    }
    return formattedStr;
}
