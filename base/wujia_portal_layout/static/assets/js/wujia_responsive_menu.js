/* ============================================================================
   Sprint 9.6 (2026-05-25): dynamic body-class swap for responsive menu.
   ---------------------------------------------------------------------------
   V14 portal works because Vuexy's app-menu.js:513 toOverlayMenu() swaps body
   class `vertical-menu-modern` ↔ `vertical-overlay-menu` whenever Unison
   detects a breakpoint change. V19 ships the same wiring (app.js:44
   `Unison.on("change", $.app.menu.change)`) but the chain is fragile —
   Unison's CSS-on-head font-family hack misses fires in DevTools responsive
   mode, on initial paint races, and after our cache-bust reloads. Result:
   body stays on `vertical-menu-modern` at <1200px → Vuexy kill rule
   `(max-width:1199.98px) .vertical-menu-modern .main-menu { width:0; left:-260; opacity:0 }`
   wins → sidebar invisible.

   This shim re-asserts the swap deterministically — pure body class flip,
   reuses Vuexy native CSS, NO per-element !important override. Run on:
     - DOMContentLoaded (covers initial paint before $(window).load).
     - window.resize (debounced) — catches DevTools resize that Unison misses.
   The matchMedia breakpoint matches Bootstrap xl (1200px).
   ============================================================================ */
(function (window, document) {
    'use strict';

    var BP_DESKTOP = '(min-width: 1200px)';
    var DESKTOP_CLASS = 'vertical-menu-modern';
    var OVERLAY_CLASS = 'vertical-overlay-menu';

    function syncMenuClass() {
        var body = document.body;
        if (!body || !body.classList.contains('vertical-layout')) {
            return;
        }
        var isDesktop = window.matchMedia(BP_DESKTOP).matches;
        if (isDesktop) {
            if (body.classList.contains(OVERLAY_CLASS)) {
                body.classList.remove(OVERLAY_CLASS);
                body.classList.add(DESKTOP_CLASS);
                body.classList.remove('menu-open', 'menu-hide');
            }
        } else {
            if (body.classList.contains(DESKTOP_CLASS)) {
                body.classList.remove(DESKTOP_CLASS);
                body.classList.add(OVERLAY_CLASS);
                body.classList.remove('menu-open');
                body.classList.add('menu-hide');
            }
        }
    }

    var debounceTimer = null;
    function onResize() {
        if (debounceTimer) {
            clearTimeout(debounceTimer);
        }
        debounceTimer = setTimeout(syncMenuClass, 100);
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', syncMenuClass);
    } else {
        syncMenuClass();
    }
    window.addEventListener('resize', onResize);
    window.addEventListener('orientationchange', syncMenuClass);
})(window, document);
