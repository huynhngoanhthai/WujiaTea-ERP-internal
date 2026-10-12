/* WujiaTea header notification bell.
   - On load: poll unread count → header badge(s) + bottom-nav badge.
     Endpoint: POST /portal/notification/unread-count → {result:{count:N}}.
   - Desktop (≥992px): click bell → toggle popup, lazy-fetch recent 5.
     Endpoint: POST /portal/notification/recent → {result:{notifications,total_unread,total}}.
     Mobile: bell stays a plain link (no interception). */
(function () {
    "use strict";

    // Mirror controller PC_TYPE_TONE (keep in sync).
    var TYPE_TONE = {
        URG: ["wj-pc-noti-type--red", "icon-alert-triangle"],
        GEN: ["wj-pc-noti-type--cyan", "icon-bell"],
        PROMO: ["wj-pc-noti-type--amber", "icon-gift"],
        SYS: ["wj-pc-noti-type--violet", "icon-settings"],
        OTH: ["wj-pc-noti-type--green", "icon-info"],
    };
    // Nhãn lấy từ priority_label backend trả (BA: FE không tự suy diễn label); đây chỉ là màu badge.
    var PRIORITY_CLASS = {
        urgent: "wj-pc-badge--done",
        important: "wj-pc-badge--transit",
        normal: "wj-pc-badge--confirmed",
    };

    function jsonRpc(url, params) {
        return fetch(url, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            credentials: "include",
            body: JSON.stringify({ jsonrpc: "2.0", method: "call", params: params || {} }),
        })
            .then(function (r) { return r.json(); })
            .then(function (j) { return (j && j.result) || {}; });
    }

    function escHtml(s) {
        return String(s == null ? "" : s)
            .replace(/&/g, "&amp;").replace(/</g, "&lt;")
            .replace(/>/g, "&gt;").replace(/"/g, "&quot;");
    }

    function updateBadges(n) {
        document.querySelectorAll(".wujia-header-noti-count").forEach(function (b) {
            b.textContent = n;
            // WJ-ORD-020: template render badge với `hidden` (không còn số 0 chờ
            // CSS ẩn) → gỡ `hidden` khi có thông báo chưa đọc.
            b.hidden = !(n > 0);
            b.classList.toggle("is-active", n > 0);
        });
        // Sprint 11: same count feeds the portal-wide bottom-nav badge.
        var bnav = document.querySelector(".wujia-bnav-noti-badge");
        if (bnav) {
            bnav.textContent = n;
            bnav.style.display = n > 0 ? "" : "none";
        }
    }

    // Câu hiển thị: data-wj-msg-* trên #wj-noti-popup (dịch bằng .po, J-V7); fallback tiếng Anh.
    function m(key, fallback, arg) {
        var popup = document.getElementById("wj-noti-popup");
        var text = window.wjMsg ? window.wjMsg(popup, key, fallback) : fallback;
        return arg === undefined ? text : text.replace("%s", arg);
    }

    function renderPopup(data) {
        var list = document.getElementById("wj-noti-popup-list");
        var sub = document.getElementById("wj-noti-popup-sub");
        var badge = document.getElementById("wj-noti-popup-unread-badge");
        if (!list) return;
        var total = data.total || 0;
        var unread = data.total_unread || 0;
        var items = data.notifications || [];
        if (sub) {
            sub.textContent = (total === 1 ? m("total-one", "%s notification", total)
                                           : m("total-n", "%s notifications", total)) +
                " • " + m("unread-n", "%s unread", unread);
        }
        if (badge) {
            badge.textContent = m("unread-n", "%s unread", unread);
            badge.style.display = unread > 0 ? "inline-flex" : "none";
        }
        if (!items.length) {
            list.innerHTML = '<div class="wj-pc-noti-popup__empty">' + escHtml(m("empty", "No notifications.")) + "</div>";
            return;
        }
        list.innerHTML = items.map(function (n) {
            var tone = TYPE_TONE[n.type_code] || TYPE_TONE.GEN;
            var ptagCls = PRIORITY_CLASS[n.priority] || PRIORITY_CLASS.normal;
            var ptag = n.priority_label
                ? '<span class="wj-pc-badge wj-pc-badge--sm ' + ptagCls + '">' + escHtml(n.priority_label) + "</span>"
                : "";
            var meta = escHtml(n.type_name) + (n.dispatch_number ? " • " + escHtml(n.dispatch_number) : "");
            var fileChip = n.has_file
                ? '<span class="wj-pc-badge wj-pc-badge--sm wj-pc-badge--confirmed">' + escHtml(m("has-file", "Has file")) + "</span>" : "";
            var dot = n.is_read ? "" : '<span class="wj-pc-noti-popup__item-dot"></span>';
            return '<a href="' + n.url + '" class="wj-pc-noti-popup__item' +
                (n.is_read ? "" : " wj-pc-noti-popup__item--unread") + '">' +
                '<span class="wj-pc-noti-popup__item-icon ' + tone[0] + '">' +
                '<i class="feather ' + tone[1] + '"></i></span>' +
                '<span class="wj-pc-noti-popup__item-main">' +
                '<span class="wj-pc-noti-popup__item-title">' + escHtml(n.name) + '</span>' +
                '<span class="wj-pc-noti-popup__item-meta">' + meta + '</span>' +
                '<span class="wj-pc-noti-popup__item-tags">' + ptag + fileChip +
                '</span>' +
                '</span>' +
                '<span class="wj-pc-noti-popup__item-side">' + dot +
                '<span class="wj-pc-noti-popup__item-date">' + escHtml(n.date) + '</span>' +
                '</span>' +
                '</a>';
        }).join("");
    }

    document.addEventListener("DOMContentLoaded", function () {
        // 1) Badge poll on load (runs only in portal where a badge exists).
        if (document.querySelector(".wujia-header-noti-count") ||
            document.querySelector(".wujia-bnav-noti-badge")) {
            jsonRpc("/portal/notification/unread-count", {})
                .then(function (res) { updateBadges(res.count || 0); })
                .catch(function () {});
        }

        // 2) Popup toggle — desktop only.
        var bell = document.querySelector("[data-wj-noti-bell]");
        var popup = document.getElementById("wj-noti-popup");
        if (!bell || !popup) return;
        var fetched = false;
        function isDesktop() { return window.matchMedia("(min-width: 992px)").matches; }
        function setOpen(open) {
            popup.classList.toggle("is-open", open);
            popup.setAttribute("aria-hidden", open ? "false" : "true");
            bell.setAttribute("aria-expanded", open ? "true" : "false");
        }
        function close() { setOpen(false); }

        bell.addEventListener("click", function (e) {
            if (!isDesktop()) return; // mobile → let the link navigate
            e.preventDefault();
            var open = !popup.classList.contains("is-open");
            setOpen(open);
            if (open && !fetched) {
                fetched = true;
                jsonRpc("/portal/notification/recent", {})
                    .then(function (data) { renderPopup(data); updateBadges(data.total_unread || 0); })
                    .catch(function () {
                        var list = document.getElementById("wj-noti-popup-list");
                        if (list) list.innerHTML = '<div class="wj-pc-noti-popup__empty">' + escHtml(m("load-failed", "Could not load notifications.")) + "</div>";
                    });
            }
        });

        document.addEventListener("click", function (e) {
            if (popup.classList.contains("is-open") &&
                !popup.contains(e.target) && !bell.contains(e.target)) {
                close();
            }
        });
        document.addEventListener("keydown", function (e) {
            if (e.key === "Escape" && popup.classList.contains("is-open")) {
                close();
                bell.focus();
            }
        });
    });
})();
