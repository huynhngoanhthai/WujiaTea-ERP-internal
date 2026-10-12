/** Copyright (C) NexGen Solutions */
/** @odoo-module **/

import { loadJS } from "@web/core/assets";

const HTML2CANVAS_PRO_JS =
    "/dynamic_dashboard_ai_nexgen/static/lib/html2canvas/html2canvas-pro.min.js";

const UNSUPPORTED_COLOR_RE =
    /(?:^|[,\s])(?:color|color-mix|oklch|oklab|lab|lch|hwb)\s*\(/i;

/**
 * Resolve modern CSS Color Level 4 values to rgb()/hex for older parsers.
 * Used as a safety net when html2canvas still sees unsupported functions.
 */
function sanitizeCssColor(value) {
    if (typeof value !== "string" || !UNSUPPORTED_COLOR_RE.test(value)) {
        return value;
    }
    try {
        const ctx =
            sanitizeCssColor._ctx ||
            (sanitizeCssColor._ctx = document.createElement("canvas").getContext("2d", {
                willReadFrequently: true,
            }));
        if (ctx) {
            ctx.fillStyle = "#000000";
            ctx.fillStyle = value;
            const resolved = ctx.fillStyle;
            if (resolved && !UNSUPPORTED_COLOR_RE.test(resolved)) {
                return resolved;
            }
        }
    } catch (_err) {
        // fall through
    }
    return "rgb(0, 0, 0)";
}

function wrapComputedStyle(originalGetComputedStyle) {
    return function patchedGetComputedStyle(el, pseudoElt) {
        const style = originalGetComputedStyle.call(window, el, pseudoElt);
        return new Proxy(style, {
            get(target, prop) {
                if (prop === "getPropertyValue") {
                    return (name) => sanitizeCssColor(target.getPropertyValue(name));
                }
                const val = target[prop];
                if (typeof val === "string") {
                    return sanitizeCssColor(val);
                }
                if (typeof val === "function") {
                    return val.bind(target);
                }
                return val;
            },
        });
    };
}

/**
 * Load html2canvas-pro (supports color()/oklch()/lab()) and capture an element.
 */
export async function captureElementToCanvas(element, options = {}) {
    if (!element) {
        throw new Error("Capture element not found");
    }
    if (!window.html2canvas || !window.html2canvas.__ddPro) {
        await loadJS(HTML2CANVAS_PRO_JS);
        if (window.html2canvas) {
            window.html2canvas.__ddPro = true;
        }
    }
    if (!window.html2canvas) {
        throw new Error("html2canvas failed to load");
    }

    const originalGetComputedStyle = window.getComputedStyle;
    window.getComputedStyle = wrapComputedStyle(originalGetComputedStyle);
    try {
        return await window.html2canvas(element, {
            scale: 2,
            useCORS: true,
            logging: false,
            backgroundColor: "#ffffff",
            ...options,
        });
    } finally {
        window.getComputedStyle = originalGetComputedStyle;
    }
}
