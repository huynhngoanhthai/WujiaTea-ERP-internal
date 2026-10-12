/* Button CMP-BTN-001 — trạng thái loading khi gửi form (BA acceptance #5:
   "loading giữ width và chặn request lặp").

   Chặn ở tầng FORM chứ không tầng nút: người dùng còn Enter trong ô nhập, và
   một form có thể có nhiều nút submit (Lưu nháp / Gửi) — nút nào bấm thì nút đó
   quay, các nút còn lại khoá theo. Bề rộng không đổi vì CSS chỉ làm nhãn tàng
   hình tại chỗ rồi vẽ spinner đè lên. */
(function () {
    "use strict";

    function actionButtons(form) {
        return Array.prototype.slice.call(
            form.querySelectorAll(".wj-btn, .wj-iconbtn")
        );
    }

    document.addEventListener("submit", function (ev) {
        var form = ev.target;
        if (!form || form.tagName !== "FORM" || form.hasAttribute("data-wj-no-loading")) {
            return;
        }
        if (form.dataset.wjSubmitting === "1") {
            ev.preventDefault();
            return;
        }
        form.dataset.wjSubmitting = "1";
        var pressed = document.activeElement;
        actionButtons(form).forEach(function (btn) {
            if (btn === pressed || (btn.type === "submit" && !pressed)) {
                btn.classList.add("is-loading");
            } else {
                btn.classList.add("is-disabled");
            }
        });
    }, true);

    function release(form) {
        delete form.dataset.wjSubmitting;
        actionButtons(form).forEach(function (btn) {
            btn.classList.remove("is-loading", "is-disabled");
        });
    }

    /* Form gửi bằng JS rồi Ở LẠI trang (lọc không reload `wj_ajax_list`) phải tự báo xong
       bằng sự kiện này, nếu không cờ dính mãi và mọi lần submit sau bị chặn im (WJ-ORD-027). */
    document.addEventListener("wj:form:release", function (ev) {
        if (ev.target && ev.target.tagName === "FORM") {
            release(ev.target);
        }
    });

    /* Quay lại bằng nút Back của trình duyệt thì trang lấy từ bfcache, form vẫn
       mang cờ cũ ⇒ mọi nút chết. Gỡ cờ khi trang hiện lại. */
    window.addEventListener("pageshow", function () {
        document.querySelectorAll("form[data-wj-submitting]").forEach(release);
    });
})();
