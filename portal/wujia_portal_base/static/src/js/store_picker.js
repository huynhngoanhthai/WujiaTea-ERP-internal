/* WujiaTea Portal — store picker overlay toggle.
   - Modal đã render SSR trong DOM (luôn có nếu user multi-franchise).
   - Khi must_pick=True: server đã thêm class wujia-store-overlay--show.
   - Click button "Đổi cửa hàng" trên top navbar → toggle class.
   - Click nút × hoặc Hủy → ẩn (chỉ khi user đã pick — lúc must_pick thì
     không có button đóng → không thoát được).
   - Click nền (overlay) ngoài card cũng ẩn (chỉ khi đã pick).
   WJ-PORTAL-UI-005: hộp là dialog modal dùng chung PC + mobile — mở thì focus vào
   nút Đóng (must_pick: cửa hàng đang chọn), nền `inert`, Tab/Shift+Tab quay vòng
   trong hộp, Escape đóng; mọi đường đóng trả focus về nút Current Store. */
(function () {
    "use strict";

    // Nút Current Store (PC: pill top bar, mobile: dải cửa hàng) — đích trả focus
    // khi nút đã mở hộp không còn nhìn thấy (vd mục "Đổi cửa hàng" trong menu tài khoản đã đóng).
    const CURRENT_STORE_SEL = ".wujia-active-store-badge, .wujia-store-mobile-strip--clickable";
    const FOCUSABLE_SEL = 'button:not([disabled]), a[href], input:not([type="hidden"]):not([disabled]), ' +
        'select, textarea, [tabindex]:not([tabindex="-1"])';

    function isVisible(el) {
        return !!(el && el.getClientRects().length);
    }

    function init() {
        const overlay = document.getElementById("wujiaStoreOverlay");
        if (!overlay) return;
        const canClose = overlay.querySelector('[data-action="close-store-picker"]') !== null;
        let lastTrigger = null;
        let inerted = [];

        function isOpen() {
            return overlay.classList.contains("wujia-store-overlay--show");
        }

        function setInert(on) {
            if (on) {
                inerted = Array.prototype.filter.call(document.body.children, function (el) {
                    return el !== overlay && !el.inert && el.tagName !== "SCRIPT" && el.tagName !== "STYLE";
                });
                inerted.forEach(function (el) { el.inert = true; });
            } else {
                inerted.forEach(function (el) { el.inert = false; });
                inerted = [];
            }
        }

        function setExpanded(value) {
            document.querySelectorAll('[data-action="open-store-picker"][aria-haspopup]').forEach(function (btn) {
                btn.setAttribute("aria-expanded", value ? "true" : "false");
            });
        }

        // Radio group = 1 điểm dừng Tab: chỉ radio đang chọn (chưa chọn ⇒ radio đầu).
        function focusables() {
            const radios = overlay.querySelectorAll(".wujia-store-radio");
            const stop = overlay.querySelector(".wujia-store-radio:checked") || radios[0];
            return Array.prototype.filter.call(overlay.querySelectorAll(FOCUSABLE_SEL), function (el) {
                if (el.classList.contains("wujia-store-radio") && el !== stop) return false;
                return isVisible(el);
            });
        }

        function focusInitial() {
            const target = overlay.querySelector(".wujia-store-close") ||
                overlay.querySelector(".wujia-store-radio:checked") ||
                overlay.querySelector(".wujia-store-radio");
            if (target) target.focus();
        }

        function show(trigger) {
            lastTrigger = trigger || null;
            overlay.classList.add("wujia-store-overlay--show");
            setInert(true);
            setExpanded(true);
            focusInitial();
        }

        function hide() {
            overlay.classList.remove("wujia-store-overlay--show");
            setInert(false);
            setExpanded(false);
            let back = isVisible(lastTrigger) ? lastTrigger : null;
            if (!back) {
                back = Array.prototype.find.call(document.querySelectorAll(CURRENT_STORE_SEL), isVisible) || null;
            }
            if (back) back.focus();
            lastTrigger = null;
        }

        // Trigger từ badge top navbar / button "Đổi cửa hàng"
        document.querySelectorAll('[data-action="open-store-picker"]').forEach(function (btn) {
            btn.addEventListener("click", function (ev) {
                ev.preventDefault();
                show(btn);
            });
        });

        // Nút × và Hủy đóng modal (chỉ tồn tại khi must_pick=False)
        overlay.querySelectorAll('[data-action="close-store-picker"]').forEach(function (btn) {
            btn.addEventListener("click", function (ev) {
                ev.preventDefault();
                hide();
            });
        });

        // Click nền (overlay) đóng nếu cho phép — chỉ khi có nút đóng (đã pick).
        if (canClose) {
            overlay.addEventListener("click", function (ev) {
                if (ev.target === overlay) hide();
            });
        }

        document.addEventListener("keydown", function (ev) {
            if (!isOpen()) return;
            if (ev.key === "Escape") {
                if (canClose) {
                    ev.preventDefault();
                    hide();
                }
                return;
            }
            if (ev.key !== "Tab") return;
            const items = focusables();
            if (!items.length) {
                ev.preventDefault();
                return;
            }
            const first = items[0];
            const last = items[items.length - 1];
            const active = document.activeElement;
            if (!overlay.contains(active)) {
                ev.preventDefault();
                (ev.shiftKey ? last : first).focus();
            } else if (ev.shiftKey && active === first) {
                ev.preventDefault();
                last.focus();
            } else if (!ev.shiftKey && active === last) {
                ev.preventDefault();
                first.focus();
            }
        });

        // UX: highlight item theo radio đang chọn — chuột lẫn phím mũi tên (chưa submit ⇒ chưa đổi cửa hàng)
        function syncActive() {
            overlay.querySelectorAll(".wujia-store-item").forEach(function (it) {
                const radio = it.querySelector(".wujia-store-radio");
                it.classList.toggle("wujia-store-item--active", !!(radio && radio.checked));
            });
        }
        overlay.querySelectorAll(".wujia-store-item").forEach(function (item) {
            item.addEventListener("click", function () {
                const radio = item.querySelector(".wujia-store-radio");
                if (radio) radio.checked = true;
                syncActive();
            });
        });
        overlay.addEventListener("change", function (ev) {
            if (ev.target.classList.contains("wujia-store-radio")) syncActive();
        });

        // must_pick: server render sẵn hộp mở ⇒ áp đủ trạng thái dialog ngay.
        if (isOpen()) {
            setInert(true);
            focusInitial();
        }
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", init);
    } else {
        init();
    }
})();
