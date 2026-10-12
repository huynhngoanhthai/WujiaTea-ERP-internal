/* CMP-BPH-001 — cảnh báo khi rời form còn thay đổi chưa lưu.
   Opt-in: chỉ form gắn `data-wj-dirty-guard`. So snapshot giá trị lúc load nên
   form không đổi thì Back đi thẳng (rủi ro BA nêu rõ). */
(function () {
    "use strict";

    function snapshot(form) {
        return new URLSearchParams(new FormData(form)).toString();
    }

    // Câu dịch theo ngôn ngữ user: lấy từ data-wj-msg-unsaved-changes (wj_msg.js, J-V1).
    function message(el) {
        const fallback = "You have unsaved changes. Leave this page?";
        return window.wjMsg ? window.wjMsg(el, "unsaved-changes", fallback) : fallback;
    }

    function init() {
        const forms = document.querySelectorAll("form[data-wj-dirty-guard]");
        if (!forms.length) return;

        const initial = new Map();
        forms.forEach(function (form) {
            initial.set(form, snapshot(form));
            // Submit hợp lệ thì không được hỏi lại
            form.addEventListener("submit", function () {
                initial.set(form, null);
            });
        });

        function isDirty() {
            for (const [form, before] of initial) {
                if (before !== null && snapshot(form) !== before) return true;
            }
            return false;
        }

        document.querySelectorAll(".wj-page-header__back").forEach(function (link) {
            link.addEventListener("click", function (ev) {
                if (isDirty() && !window.confirm(message(link))) {
                    ev.preventDefault();
                }
            });
        });
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", init);
    } else {
        init();
    }
})();
