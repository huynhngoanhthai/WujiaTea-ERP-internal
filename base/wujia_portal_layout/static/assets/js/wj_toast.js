/* wjToast — thẻ báo kết quả dùng chung cho JS portal (thay các toast viết tay từng màn).
   Thẻ nằm NGAY DƯỚI thanh trên: PC góc phải, mobile hết bề ngang; cuộn qua header thì bám mép
   trên. Dáng ở `_components.css` (`.wj-toast*`), câu chữ do nơi gọi đưa vào (đã dịch qua wjMsg).
   Dùng: wjToast(text)  ·  wjToast(text, { type: 'error' }) */
(function () {
    "use strict";

    var LIFE_MS = 3000;
    var MAX_STACK = 3;
    var EDGE = 12;
    var ICONS = { success: "icon-check", error: "icon-alert-circle" };

    function host() {
        var el = document.getElementById("wj-toast-host");
        if (!el) {
            el = document.createElement("div");
            el.id = "wj-toast-host";
            el.className = "wj-toast-host";
            el.setAttribute("aria-live", "polite");
            document.body.appendChild(el);
        }
        return el;
    }

    /* Đáy của thanh trên đang hiển thị (header mobile hoặc navbar PC); đã cuộn khỏi màn thì 0. */
    function topBarBottom() {
        var bars = document.querySelectorAll(".wujia-mheader, .wujia-navbar");
        for (var i = 0; i < bars.length; i++) {
            var r = bars[i].getBoundingClientRect();
            if (r.height > 0) return r.bottom;
        }
        return 0;
    }

    window.wjToast = function (text, opts) {
        if (!text) return null;
        var type = opts && opts.type === "error" ? "error" : "success";
        var box = host();
        box.style.top = Math.max(EDGE, Math.round(topBarBottom()) + EDGE) + "px";

        var el = document.createElement("div");
        el.className = "wj-toast wj-toast--" + type;
        el.setAttribute("role", type === "error" ? "alert" : "status");
        var icon = document.createElement("i");
        icon.className = "wj-toast__icon feather " + ICONS[type];
        icon.setAttribute("aria-hidden", "true");
        var label = document.createElement("span");
        label.className = "wj-toast__text";
        label.textContent = text;
        el.appendChild(icon);
        el.appendChild(label);

        box.appendChild(el);
        while (box.children.length > MAX_STACK) box.removeChild(box.firstChild);
        setTimeout(function () { el.remove(); }, LIFE_MS);
        return el;
    };
})();
