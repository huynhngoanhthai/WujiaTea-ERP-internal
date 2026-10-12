/* WujiaTea PC notification list — nút "Mark as read" (BA row 6).
   Server tự đánh dấu TẤT CẢ thông báo còn hiệu lực chưa đọc của user tại cửa hàng hiện tại
   (không gửi ids/filter) → toast "Marked N notifications as read." → reload.
   Câu toast: data-wj-msg-* trên nút (dịch bằng .po, J-V7); fallback tiếng Anh. */
(function () {
    "use strict";
    // Delegation: nút nằm trong vùng swap của wj_ajax_list — bind trực tiếp sẽ mất
    // listener sau lần lọc đầu tiên (node cũ đã bị thay).
    document.addEventListener("click", function (ev) {
        var btn = ev.target.closest ? ev.target.closest("#wj-noti-bulk-read") : null;
        if (!btn || btn.disabled) return;
        function m(key, fallback, arg) {
            var text = window.wjMsg ? window.wjMsg(btn, key, fallback) : fallback;
            return arg === undefined ? text : text.replace("%s", arg);
        }
        btn.disabled = true;
        fetch("/portal/notification/mark-all-read", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            credentials: "include",
            body: JSON.stringify({ jsonrpc: "2.0", method: "call", params: {} }),
        })
            .then(function (r) { return r.json(); })
            .then(function (res) {
                var out = (res && res.result) || {};
                if (out.error) {
                    // Ví dụ chưa chọn cửa hàng — hiện message nghiệp vụ, không reload.
                    window.wjToast(out.message || m("mark-failed", "Could not mark as read. Please try again."),
                                   { type: "error" });
                    btn.disabled = false;
                    return;
                }
                var n = out.updated_count || 0;
                window.wjToast(n === 1 ? m("marked-one", "Marked %s notification as read.", n)
                                       : m("marked-n", "Marked %s notifications as read.", n));
                setTimeout(function () { window.location.reload(); }, 600);
            })
            .catch(function () { btn.disabled = false; });
    });
})();
