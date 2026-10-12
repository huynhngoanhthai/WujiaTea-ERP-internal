/* ============================================================================
   Sprint 14 (2026-06-11): "Thêm" bottom sheet toggle (Figma WJ_MoreBottom
   4477:242). Replaces the Sprint 12 interim sidebar toggle on the footer tab.
   ---------------------------------------------------------------------------
   Markup lives in wujia_portal_layout.mobile_bottomnav (shared shell, every
   portal page, d-lg-none). This script only flips classes:
     - .wujia-msheet / .wujia-msheet-backdrop get .is-open
     - body gets .wujia-msheet-open (scroll lock, CSS side)
     - footer "Thêm" tab gets .is-active while open (Figma
       WJ_Mobile_FooterActionBar_MORE_ACTIVE), restored on close to whatever
       the server rendered for the current route.
   Close paths: tab re-tap, backdrop tap, close button, Escape. Menu anchors
   are plain links — navigation reloads the page, no JS needed to close.
   ============================================================================ */
(function (window, document) {
    'use strict';

    function init() {
        var sheet = document.querySelector('.wujia-msheet');
        var backdrop = document.querySelector('.wujia-msheet-backdrop');
        var toggleTab = document.querySelector('[data-wujia-more="toggle"]');
        if (!sheet || !backdrop || !toggleTab) {
            return;
        }
        var tabWasActive = toggleTab.classList.contains('is-active');

        function isOpen() {
            return sheet.classList.contains('is-open');
        }

        // WJ-PORTAL-UI-004: sheet là dialog modal — focus vào nút đóng khi mở,
        // Tab/Shift+Tab quay vòng trong sheet, đóng thì trả focus về nút Thêm.
        function focusables() {
            return sheet.querySelectorAll('button, a[href]');
        }

        function open() {
            sheet.classList.add('is-open');
            backdrop.classList.add('is-open');
            document.body.classList.add('wujia-msheet-open');
            toggleTab.classList.add('is-active');
            toggleTab.setAttribute('aria-expanded', 'true');
            var closeBtn = sheet.querySelector('.wujia-msheet-close');
            if (closeBtn) {
                closeBtn.focus();
            }
        }

        function close() {
            sheet.classList.remove('is-open');
            backdrop.classList.remove('is-open');
            document.body.classList.remove('wujia-msheet-open');
            if (!tabWasActive) {
                toggleTab.classList.remove('is-active');
            }
            toggleTab.setAttribute('aria-expanded', 'false');
            toggleTab.focus();
        }

        toggleTab.addEventListener('click', function (ev) {
            ev.preventDefault();
            if (isOpen()) {
                close();
            } else {
                open();
            }
        });

        document.querySelectorAll('[data-wujia-more="close"]').forEach(function (el) {
            el.addEventListener('click', function (ev) {
                ev.preventDefault();
                close();
            });
        });

        document.addEventListener('keydown', function (ev) {
            if (!isOpen()) {
                return;
            }
            if (ev.key === 'Escape') {
                close();
                return;
            }
            if (ev.key !== 'Tab') {
                return;
            }
            var items = focusables();
            if (!items.length) {
                return;
            }
            var first = items[0];
            var last = items[items.length - 1];
            var active = document.activeElement;
            // Focus đang ngoài sheet (vd còn trên nút Thêm) → kéo vào trong.
            if (!sheet.contains(active)) {
                ev.preventDefault();
                (ev.shiftKey ? last : first).focus();
            } else if (ev.shiftKey && active === first) {
                ev.preventDefault();
                last.focus();
            } else if (!ev.shiftKey && active === last) {
                ev.preventDefault();
                first.focus();
            }
        });
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})(window, document);
