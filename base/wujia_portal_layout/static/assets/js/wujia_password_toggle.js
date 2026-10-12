/* Wujia mobile — password eye-toggle (Sprint 18, Figma Mobile_Account_Info màn 03).
   Vanilla, no dep. Click nút [data-wujia-pwd-toggle] → đổi type password/text của
   input cùng cụm .wujia-maccount-pwd + đổi icon eye/eye-off. Mobile-only markup,
   nhưng JS attach toàn trang (selector chỉ khớp khi có nút). */
(function () {
    "use strict";

    function msg(el, key, fallback) {
        return window.wjMsg ? window.wjMsg(el, key, fallback) : fallback;
    }

    function toggle(btn) {
        // Mobile eye-icon wrapper (.wujia-maccount-pwd) + PC text toggle (.wj-pc-acct-pw-input)
        // + màn auth Figma v3 (.wj-auth-pwd, Sprint 39).
        var wrap = btn.closest(".wujia-maccount-pwd, .wj-pc-acct-pw-input, .wj-auth-pwd");
        if (!wrap) return;
        var input = wrap.querySelector("input");
        if (!input) return;
        var icon = btn.querySelector("i");
        var show = input.getAttribute("type") === "password";
        input.setAttribute("type", show ? "text" : "password");
        if (icon) {
            icon.classList.toggle("icon-eye", !show);
            icon.classList.toggle("icon-eye-off", show);
        } else {
            // PC text toggle Show ↔ Hide — câu dịch lấy từ #wj-msgs (wj_msg.js, J-V1).
            btn.textContent = show ? msg(btn, "hide", "Hide") : msg(btn, "show", "Show");
        }
        btn.classList.toggle("is-active", show);
    }

    document.addEventListener("click", function (ev) {
        var btn = ev.target.closest("[data-wujia-pwd-toggle]");
        if (btn) {
            ev.preventDefault();
            toggle(btn);
        }
    });
})();
