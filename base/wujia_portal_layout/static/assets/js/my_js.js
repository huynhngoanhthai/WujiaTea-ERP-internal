/* J-V1 (05/10/2026): đã xoá khối ví/đầu tư/rút tiền của template Vuexy cũ
   (#form_withdraw, #register_investment, payment_confirmation → route /bcore/* không tồn tại,
   không view nào render) — nó là nơi duy nhất gọi _t() của lang.js, file đó cũng đã xoá. */
/* Sprint 4.2: defensive — ensure .show-overlay class is never stuck after
   page load. On the production server, JS init ordering with Odoo's
   web.assets_frontend bundle can leave this class active, which causes
   the content-overlay (rgba(0,0,0,0.5)) to cover the sidebar. */
$(document).ready(function () {
    $('.app-content').removeClass('show-overlay');
});
$(window).on('load', function () {
    $('.app-content').removeClass('show-overlay');
});

/* Sprint 4.2+: force body.menu-expanded on desktop so Vuexy's menu-modern
   CSS shows the sidebar even when app-menu.js init() bails out without
   adding the class. E8b: chỉ ≥1200 (sidebar cố định); 992–1199 là drawer
   đóng mặc định do wujia_sidebar.js điều khiển. */
function _wujiaForceMenuExpanded() {
    if (window.matchMedia('(min-width: 1200px)').matches) {
        $('body').removeClass('menu-hide menu-collapsed').addClass('menu-expanded menu-open');
    }
}
$(document).ready(_wujiaForceMenuExpanded);
$(window).on('load', _wujiaForceMenuExpanded);
$(window).on('resize', _wujiaForceMenuExpanded);

/* Sprint 4.2+: neutralize Vuexy app-menu.js so it doesn't run hide/expand/
   PerfectScrollbar animations at window.load that cause a visible flicker
   ("load twice"). The sidebar has only one static item — we don't need
   accordion, scrollbar, or breakpoint-aware hide. Override before Vuexy's
   $(window).on('load') handler in app.js fires (handlers run in registration
   order, my_js.js is loaded after app-menu.js and app.js so by the time
   app.js's load handler runs, $.app.menu.init is our no-op). */
if (typeof $ !== 'undefined' && $.app && $.app.menu) {
    $.app.menu.init = function () {};
    $.app.menu.change = function () {};
    if ($.app.menu.manualScroller) {
        $.app.menu.manualScroller.init = function () {};
        $.app.menu.manualScroller.update = function () {};
        $.app.menu.manualScroller.updateHeight = function () {};
    }
}

/* i18next của Vuexy đã bỏ ngay trong core/app.js (J-V4): stub ở đây chạy SAU app.js nên không chặn
   được 404 locales/{{lng}}.json. Chữ portal dịch phía server (QWeb + data-wj-msg-*, see wj_msg.js). */
