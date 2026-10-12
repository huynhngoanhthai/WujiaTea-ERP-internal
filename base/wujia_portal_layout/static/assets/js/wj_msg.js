/* J-V1 — wjMsg: chuỗi hiển thị cho JS portal, dịch bằng .po như QWeb.
   Odoo chỉ dịch attribute trong TRANSLATED_ATTRS, `data-*` tuỳ ý thì không ⇒ câu đặt trong
   text node <t t-set> rồi gắn ra `data-wj-msg-<key>` (quy ước next-session-clusters-J.md §6).
   Thứ tự tìm: attr trên `el` hoặc tổ tiên gần nhất → khối chung #wj-msgs ở layout → fallback
   (câu tiếng Anh, không để tiếng Việt trong .js).
   Dùng: wjMsg(btn, 'unsaved-changes', 'You have unsaved changes. Leave this page?') */
(function () {
    "use strict";

    window.wjMsg = function (el, key, fallback) {
        var attr = "data-wj-msg-" + key;
        var node = el && el.closest ? el.closest("[" + attr + "]") : null;
        if (!node) {
            var shared = document.getElementById("wj-msgs");
            node = shared && shared.hasAttribute(attr) ? shared : null;
        }
        var text = node ? node.getAttribute(attr) : "";
        return text || fallback || "";
    };
})();
