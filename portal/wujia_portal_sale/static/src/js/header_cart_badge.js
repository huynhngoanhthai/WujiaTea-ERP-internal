/* WujiaTea Header Cart badge (UI-13, Sprint 9.14, 2026-05-28).
   Fetches cart line count after DOMContentLoaded and toggles .is-active.
   Endpoint: POST /portal/order/cart/count → {result: {count: N}}.
   Runs only when .wujia-header-cart-count is present (i.e. user is in portal).
   Sprint 12 (2026-06-07): querySelectorAll — giờ có 2 badge cùng class
   (.wujia-header-cart-count): navbar desktop (ẩn <992px) + mobile header
   (WJ_Mobile_Header_Primary). 1 poll cập nhật cả hai. */
(function () {
    "use strict";
    document.addEventListener("DOMContentLoaded", function () {
        var badges = document.querySelectorAll(".wujia-header-cart-count");
        if (!badges.length) return;
        fetch("/portal/order/cart/count", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            credentials: "include",
            body: JSON.stringify({ jsonrpc: "2.0", method: "call", params: {} }),
        })
            .then(function (r) { return r.json(); })
            .then(function (j) {
                var n = (j && j.result && j.result.count) || 0;
                badges.forEach(function (badge) {
                    badge.textContent = n;
                    // WJ-ORD-020: template render badge với `hidden` (không còn số 0
                    // chờ CSS ẩn) → gỡ `hidden` khi có hàng.
                    badge.hidden = !(n > 0);
                    badge.classList.toggle("is-active", n > 0);
                });
            })
            .catch(function () {});
    });
})();
