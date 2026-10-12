/* WujiaTea Portal Order — Add-to-cart (catalog + product detail).

   Thêm vào giỏ → server tăng theo bước min_qty (BA row 6) → reconcile realtime qua
   WujiaCartSync (badge/floatbar/panel, không reload). Tương tác TRONG giỏ (stepper/
   xoá/ghi chú) + đồng bộ cross-session nằm ở portal_cart_sync.js. */
(function () {
    "use strict";

    function jsonRpc(url, params) {
        return fetch(url, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            credentials: "include",
            body: JSON.stringify({ jsonrpc: "2.0", method: "call", params: params || {} }),
        }).then(function (r) { return r.json(); })
          .then(function (j) { return j.result || {}; });
    }

    function toast(msg, ok) {
        window.wjToast(msg, { type: ok ? "success" : "error" });
    }

    /* J-V4: câu hiển thị lấy từ data-wj-msg-* trên #wj-cart-sync (dịch bằng .po), fallback EN. */
    function m(key, fallback, arg) {
        const root = document.getElementById("wj-cart-sync");
        const text = window.wjMsg ? window.wjMsg(root, key, fallback) : fallback;
        return arg === undefined ? text : text.replace("%s", arg);
    }

    function errText(res) {
        return res.message || m("error-code", "Error: %s", res.error);
    }

    /* Reconcile giỏ (badge/floatbar/panel) qua module realtime — không reload. */
    function syncCart() {
        if (window.WujiaCartSync) {
            window.WujiaCartSync.refresh();
        }
    }

    document.addEventListener("DOMContentLoaded", function () {
        // Catalog: Add-to-cart (desktop + mobile) — server tự tăng theo bước min_qty.
        // Delegation: nút nằm trong vùng swap của wj_ajax_list (lọc/phân trang thay DOM),
        // bind trực tiếp sẽ mất listener sau lần lọc đầu.
        document.addEventListener("click", function (ev) {
            const btn = ev.target.closest ? ev.target.closest(".btn-add-cart") : null;
            if (!btn || btn.disabled) return;
            ev.preventDefault();
            const productId = parseInt(btn.dataset.productId, 10);
            btn.disabled = true;
            jsonRpc("/portal/order/cart/add", { product_id: productId })
                .then(function (res) {
                    btn.disabled = false;
                    if (res.error) {
                        toast(errText(res), false);
                        return;
                    }
                    if (res.warning) toast(res.message, false);
                    else toast(m("added", "Added to cart (%s)", res.qty), true);
                    syncCart();
                })
                .catch(function () {
                    btn.disabled = false;
                    toast(m("conn-error", "Connection error"), false);
                });
        });

        // Product detail: Add-to-cart (có ô nhập số lượng).
        document.querySelectorAll(".btn-add-cart-detail").forEach(function (btn) {
            btn.addEventListener("click", function (ev) {
                ev.preventDefault();
                const productId = parseInt(btn.dataset.productId, 10);
                const step = parseInt(btn.dataset.minQty, 10) || 1;
                const max = parseInt(btn.dataset.maxQty, 10) || 0; // 0 = không giới hạn
                const qtyEl = document.getElementById("product-detail-qty");
                const msgEl = document.getElementById("product-detail-msg");
                const raw = qtyEl ? String(qtyEl.value).trim() : "";
                const qty = Number(raw);
                // WJ-ORD-001: validate ngay tại client — KHÔNG gửi request khi
                // quantity invalid; lỗi (theo ngôn ngữ user) cạnh input.
                let err = null;
                if (raw === "" || !Number.isFinite(qty)) {
                    err = m("qty-invalid", "Please enter a valid quantity.");
                } else if (!Number.isInteger(qty)) {
                    err = m("qty-integer", "Quantity must be a whole number.");
                } else if (qty < step) {
                    err = m("qty-min", "The minimum quantity is %s.", step);
                } else if (qty % step !== 0) {
                    err = m("qty-step", "Quantity must be in steps of %s.", step);
                } else if (max && qty > max) {
                    err = m("qty-max", "The maximum quantity is %s.", max);
                }
                if (err) {
                    if (msgEl) msgEl.innerHTML = '<div class="alert alert-danger">' + err + "</div>";
                    if (qtyEl) { qtyEl.classList.add("is-invalid"); qtyEl.focus(); }
                    return;
                }
                if (qtyEl) qtyEl.classList.remove("is-invalid");
                btn.disabled = true;
                jsonRpc("/portal/order/cart/add", { product_id: productId, qty: qty })
                    .then(function (res) {
                        btn.disabled = false;
                        if (res.error) {
                            if (msgEl) msgEl.innerHTML = '<div class="alert alert-danger">' + errText(res) + "</div>";
                            return;
                        }
                        if (msgEl) msgEl.innerHTML = '<div class="alert alert-success">' + m("in-cart", "Quantity in cart: %s.", res.qty) +
                            ' <a href="/portal/order/cart">' + m("view-cart", "View cart") + ' →</a></div>';
                        syncCart();
                    })
                    .catch(function () {
                        btn.disabled = false;
                        if (msgEl) msgEl.innerHTML = '<div class="alert alert-danger">' + m("conn-error", "Connection error") + '</div>';
                    });
            });
        });

        /* WJ-ORD-028 — "Gửi đơn đặt hàng" chỉ MỞ hộp xác nhận; "Xác nhận gửi đơn" mới gửi form.

           Chống gửi lặp có 3 lớp: (1) khoá chung CMP-BTN-001 (`wujia_button_loading.js`, pha capture)
           cắm cờ lên form ⇒ submit thứ hai bị chặn; (2) nút Xác nhận tự khoá; (3) server khoá giỏ
           NOWAIT, lần lặp gặp giỏ trống thì được dẫn về đơn vừa tạo. Ở đây KHÔNG tự kiểm cờ
           `wjSubmitting` nữa: khoá chung đã cắm cờ TRƯỚC listener này nên kiểm lại là tự chặn
           chính lần gửi đầu (lỗi làm nút gửi mobile chết từ E6a).
           Delegation trên document vì panel giỏ bị cart-sync thay innerHTML. */
        const FORM_SEL = "form[data-wj-confirm-form]";
        const overlay = document.getElementById("wj-order-submitting");
        const modal = document.getElementById("wjOrderConfirm");
        let openFor = null;      // {mobile, sig} của form đang được xác nhận
        let lastFocus = null;

        function setOverlay(show) {
            if (!overlay) return;
            overlay.classList.toggle("wujia-msubmit--show", show);
            overlay.setAttribute("aria-hidden", show ? "false" : "true");
        }

        function isMobileForm(form) {
            // Luồng mobile có hidden flow=m (màn kết quả riêng); form PC dùng chung route.
            return !!form.querySelector("input[name='flow'][value='m']");
        }

        /* Panel có thể đã bị cart-sync thay ⇒ form cũ rời DOM. Luôn lấy form HIỆN TẠI cùng kênh. */
        function liveForm(mobile) {
            const forms = document.querySelectorAll(FORM_SEL);
            for (let i = 0; i < forms.length; i++) {
                if (isMobileForm(forms[i]) === mobile) return forms[i];
            }
            return null;
        }

        function summary(form) {
            const note = form.querySelector("textarea[name='portal_note']");
            return {
                store: form.dataset.ocStore || "—",
                lines: form.dataset.ocLines || "0",
                qty: form.dataset.ocQty || "0",
                total: form.dataset.ocTotal || "—",
                note: (note && note.value.trim()) || "—",
            };
        }

        function sig(s) {
            return [s.lines, s.qty, s.total].join("|");
        }

        function fill(s) {
            ["store", "lines", "qty", "total", "note"].forEach(function (k) {
                const el = modal.querySelector("[data-wj-oc='" + k + "']");
                if (el) el.textContent = s[k];
            });
        }

        function actions() {
            return modal.querySelectorAll("[data-wj-oc-action]");
        }

        function setBusy(busy) {
            actions().forEach(function (b) {
                b.disabled = busy;
                b.classList.toggle("is-loading", busy && b.dataset.wjOcAction === "confirm");
            });
        }

        function openConfirm(form, opener) {
            const s = summary(form);
            fill(s);
            openFor = { mobile: isMobileForm(form), sig: sig(s) };
            modal.querySelector("[data-wj-oc='changed']").hidden = true;
            setBusy(false);
            lastFocus = opener;
            modal.removeAttribute("hidden");
            document.body.classList.add("wj-order-confirm-open");
            // Focus nút Hủy: Enter/Space bấm vội không thể tạo đơn.
            modal.querySelector("[data-wj-oc-action='cancel']").focus();
        }

        function closeConfirm() {
            if (!modal || modal.hidden) return;
            modal.setAttribute("hidden", "hidden");
            document.body.classList.remove("wj-order-confirm-open");
            openFor = null;
            if (lastFocus && lastFocus.isConnected) lastFocus.focus();
        }

        function confirmSubmit() {
            if (!openFor) return;
            const form = liveForm(openFor.mobile);
            if (!form) { closeConfirm(); return; }
            const s = summary(form);
            if (sig(s) !== openFor.sig) {
                // Giỏ đổi (user khác cùng cửa hàng / tab khác) trong lúc hộp đang mở ⇒ cho xem lại.
                fill(s);
                openFor.sig = sig(s);
                modal.querySelector("[data-wj-oc='changed']").hidden = false;
                return;
            }
            setBusy(true);
            if (openFor.mobile) setOverlay(true);
            form.requestSubmit();
        }

        document.addEventListener("click", function (ev) {
            const t = ev.target;
            const opener = t.closest ? t.closest("[data-wj-confirm-open]") : null;
            if (opener && modal) {
                const form = opener.form;
                if (!form || opener.disabled) return;
                ev.preventDefault(); // chặn submit mặc định của nút — chưa tạo đơn
                openConfirm(form, opener);
                return;
            }
            if (!modal || modal.hidden) return;
            const act = t.closest ? t.closest("[data-wj-oc-action]") : null;
            if (act) {
                if (act.dataset.wjOcAction === "confirm") confirmSubmit();
                else closeConfirm();
            } else if (t === modal) {
                closeConfirm(); // bấm nền ngoài hộp = Hủy
            }
        });

        document.addEventListener("keydown", function (ev) {
            if (!modal || modal.hidden) return;
            const busy = modal.querySelector("[data-wj-oc-action='confirm']").disabled;
            if (ev.key === "Escape" && !busy) {
                ev.preventDefault();
                closeConfirm();
            } else if (ev.key === "Tab") {
                // Giữ focus trong hộp: chỉ có 2 nút.
                const btns = Array.prototype.filter.call(actions(), function (b) { return !b.disabled; });
                if (!btns.length) { ev.preventDefault(); return; }
                const i = btns.indexOf(document.activeElement);
                const next = ev.shiftKey ? (i <= 0 ? btns.length - 1 : i - 1) : (i + 1) % btns.length;
                ev.preventDefault();
                btns[next].focus();
            }
        });

        document.addEventListener("submit", function (ev) {
            const form = ev.target.closest ? ev.target.closest(FORM_SEL) : null;
            if (!form || ev.defaultPrevented) return;
            // Nút submit không có attribute name → disable không làm mất payload;
            // portal_note vẫn gửi vì nằm cùng form (FUNC-MOB-ORDER-005).
            form.querySelectorAll("[data-wj-confirm-open]").forEach(function (b) { b.disabled = true; });
            if (isMobileForm(form)) setOverlay(true);
        });

        // WJ-ORD-003: back/forward khôi phục trang từ BFCache → hộp/overlay/nút bị
        // đóng băng ở trạng thái "đang gửi". Reset lại để giỏ dùng được ngay.
        window.addEventListener("pageshow", function (ev) {
            if (!ev.persisted) return;
            setOverlay(false);
            if (modal) { setBusy(false); closeConfirm(); }
            document.querySelectorAll(FORM_SEL + " [data-wj-confirm-open]").forEach(function (b) {
                // Chỉ mở lại nút mà CHÍNH ta đã khoá — nút bị server disable vì
                // ngoài khung giờ (WJ-ORD-006) mang cờ riêng, giữ nguyên.
                if (!b.hasAttribute("data-wj-window-closed")) b.disabled = false;
            });
        });
    });
})();
