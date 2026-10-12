/* CMP-SN-001 (E8b) — drawer sidebar ở 992–1199.
   Đóng mặc định; mở bằng hamburger; đóng bằng nút Đóng, Escape, bấm backdrop; đóng xong
   trả focus về hamburger. Bắt click ở pha capture để handler ủy quyền của Vuexy
   (app.js `.menu-toggle`, `.sidenav-overlay` → $.app.menu.*, đã no-op init) không chạy. */
(function (window, document) {
    'use strict';

    var DRAWER = window.matchMedia('(min-width: 992px) and (max-width: 1199.98px)');
    var lastToggle = null;

    function toggles() {
        return document.querySelectorAll('.wj-menu-toggle');
    }

    function setExpanded(value) {
        toggles().forEach(function (btn) {
            btn.setAttribute('aria-expanded', value ? 'true' : 'false');
        });
    }

    function isOpen() {
        return document.body.classList.contains('menu-open');
    }

    // Transition của Vuexy giữ drawer ở visibility:hidden thêm vài khung hình sau khi
    // mở; focus() lúc đó bị trình duyệt bỏ qua ⇒ chờ tới khi phần tử hiện thật.
    function focusWhenVisible(el, frames) {
        if (window.getComputedStyle(el).visibility === 'visible') {
            el.focus();
        } else if (frames > 0 && isOpen()) {
            window.requestAnimationFrame(function () { focusWhenVisible(el, frames - 1); });
        }
    }

    function open(trigger) {
        lastToggle = trigger || toggles()[0] || null;
        document.body.classList.remove('menu-hide');
        document.body.classList.add('menu-open');
        setExpanded(true);
        var closeBtn = document.querySelector('#wj-main-menu .wj-sidebar__close');
        if (closeBtn) {
            focusWhenVisible(closeBtn, 30);
        }
    }

    function close(restoreFocus) {
        document.body.classList.remove('menu-open', 'menu-expanded');
        document.body.classList.add('menu-hide');
        setExpanded(false);
        if (restoreFocus && lastToggle) {
            lastToggle.focus();
        }
    }

    document.addEventListener('click', function (ev) {
        if (!DRAWER.matches) {
            return;
        }
        var toggle = ev.target.closest('.wj-menu-toggle');
        var dismiss = ev.target.closest('#wj-main-menu .wj-sidebar__close, .sidenav-overlay');
        if (!toggle && !dismiss) {
            return;
        }
        ev.preventDefault();
        ev.stopImmediatePropagation();
        if (toggle && !isOpen()) {
            open(toggle);
        } else {
            close(true);
        }
    }, true);

    document.addEventListener('keydown', function (ev) {
        if (ev.key === 'Escape' && DRAWER.matches && isOpen()) {
            close(true);
        }
    });

    function sync() {
        if (DRAWER.matches) {
            close(false);
        } else {
            setExpanded(false);
        }
    }

    if (DRAWER.addEventListener) {
        DRAWER.addEventListener('change', sync);
    } else if (DRAWER.addListener) {
        DRAWER.addListener(sync);
    }
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', sync);
    } else {
        sync();
    }
})(window, document);
