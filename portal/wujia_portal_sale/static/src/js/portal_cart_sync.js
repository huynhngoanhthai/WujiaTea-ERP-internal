/* WujiaTea Portal — Cart sync (Sprint 31).

   Giỏ chung theo store. Module gom tương tác giỏ (stepper/xoá/ghi chú) qua EVENT
   DELEGATION trên document + reconcile CÙNG-TAB không reload: mỗi mutation → fetch lại
   partial giỏ (server-render `/portal/order/cart/fragment`, 1 nguồn QWeb) → swap DOM +
   cập nhật badge/floatbar/header. Số liệu qty/giá lấy TỪ server (pricelist có bậc).

   CROSS-SESSION realtime (WJ-ORD-002): subscribe bus `wujia_cart_changed` trên channel
   `wujia.franchise_<id>` → tab/thiết bị khác cùng cửa hàng tự cập nhật, không reload. */
import { Interaction } from "@web/public/interaction";
import { registry } from "@web/core/registry";
import { rpc } from "@web/core/network/rpc";

/* Ký hiệu tiền đọc từ `currency_symbol` của server, KHÔNG hardcode 'đ' (WJ-ORD-025) —
   cùng một đơn thì floatbar, giỏ và lịch sử phải ra cùng ký hiệu. */
function formatMoney(n, symbol, decimals) {
    /* Cùng quy tắc với `portal_money` phía server: nghìn '.', thập phân ',' —
       số chữ số thập phân theo currency của đơn (VND 0, USD 2). */
    const d = Number(decimals) || 0;
    const parts = Number(n || 0).toFixed(d).split(".");
    parts[0] = parts[0].replace(/\B(?=(\d{3})+(?!\d))/g, ".");
    const text = parts.join(",");
    return symbol ? `${text} ${symbol}` : text;
}

function debounce(fn, wait) {
    let t;
    return function (...args) {
        clearTimeout(t);
        t = setTimeout(() => fn.apply(this, args), wait);
    };
}

export class WujiaCartSync extends Interaction {
    static selector = "#wj-cart-sync";

    setup() {
        this.franchiseId = parseInt(this.el.dataset.franchiseId, 10) || null;
        this._refreshing = false;
        this._queued = false;
        this._chain = Promise.resolve();
        this._lastRefreshAt = 0;
        // WJ-ORD-002: định danh tab, gửi kèm mọi mutation → server echo lại trong
        // payload bus (`origin`) để tab tự phát bỏ qua event của chính mình.
        this._clientId = `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 10)}`;
        this.saveNote = debounce((val) => rpc("/portal/order/cart/note", { note: val }), 600);
        // Catalog add-to-cart (portal_order.js) gọi refresh() sau khi thêm.
        window.WujiaCartSync = this;
        document.addEventListener("click", this.onClick.bind(this));
        document.addEventListener("input", this.onInput.bind(this));
        // WJ-ORD-003: back/forward KHÔNG chỉ đến từ BFCache. Khi trang được dựng
        // lại từ HTTP cache thường, `pageshow` đã bắn XONG trước lúc interaction
        // kịp đăng ký listener → chỉ nghe pageshow là bắt hụt. Navigation Timing
        // cho biết chắc chắn đây là lần vào bằng back/forward.
        const nav = performance.getEntriesByType("navigation")[0];
        if (nav && nav.type === "back_forward") {
            this.refresh();
        }
        // Vẫn giữ pageshow cho nhánh BFCache (trang sống lại, setup không chạy lại).
        this._onPageShow = () => this.refreshIfStale();
        window.addEventListener("pageshow", this._onPageShow);
        this._onVisibility = () => {
            if (document.visibilityState === "visible") { this.refreshIfStale(); }
        };
        document.addEventListener("visibilitychange", this._onVisibility);
    }

    // WJ-ORD-002: cross-session realtime. Server publish sẵn từ S30
    // (`_publish_cart_event`); channel `wujia.franchise_<id>` authorize theo
    // membership ở wujia_portal_base/models/ir_websocket.py. Không nối được
    // WebSocket thì bus im lặng retry — trang chạy bình thường, chỉ mất realtime.
    async willStart() {
        if (!this.franchiseId) { return; }
        const bus = this.services.bus_service;
        bus.addChannel(`wujia.franchise_${this.franchiseId}`);
        bus.subscribe("wujia_cart_changed", this.onCartChanged.bind(this));
    }

    onCartChanged(payload) {
        if (!payload || payload.franchise_id !== this.franchiseId) { return; }
        // Event do CHÍNH tab này gây ra: _doMutate đã refresh rồi → bỏ qua.
        if (payload.origin && payload.origin === this._clientId) { return; }
        this.refresh();
    }

    // -------- tương tác giỏ (delegation) --------
    onClick(ev) {
        // WJ-ORD-021: DANH SÁCH catalog mobile — nút "Thêm" (qty=0) + stepper
        // "− N +" (qty>0). Delegation: row render 1 lần, không rebind sau mutation.
        const addBtn = ev.target.closest(".wujia-morder-add-btn");
        if (addBtn) {
            ev.preventDefault();
            this.handleCatalogAdd(addBtn);
            return;
        }
        const mstep = ev.target.closest(".wujia-morder-mstep");
        if (mstep) {
            ev.preventDefault();
            this.handleCatalogStep(mstep);
            return;
        }
        const step = ev.target.closest(".wj-pc-cart-step, .wujia-mcart-step");
        if (step) {
            ev.preventDefault();
            this.handleStep(step);
            return;
        }
        const del = ev.target.closest(".wj-pc-cart-del, .wujia-mcart-del");
        if (del) {
            ev.preventDefault();
            this.handleRemove(del);
        }
    }

    onInput(ev) {
        // wj-cart-note = hook chung PC (wj-pc-cart-note) + mobile (wujia-mcart-note).
        const ta = ev.target.closest(".wj-cart-note");
        if (ta) {
            this.saveNote(ta.value || "");
        }
    }

    // WJ-ORD-021: thêm/tăng/giảm ngay trên product row của danh sách mobile.
    handleCatalogAdd(btn) {
        const ctl = btn.closest(".wujia-morder-cartctl");
        if (!ctl) {
            return;
        }
        const pid = parseInt(ctl.dataset.productId, 10);
        // /cart/add tạo dòng + tăng theo bước min_qty (BA row 6).
        this.mutate("/portal/order/cart/add", { product_id: pid });
    }

    handleCatalogStep(btn) {
        const ctl = btn.closest(".wujia-morder-cartctl");
        if (!ctl) {
            return;
        }
        const pid = parseInt(ctl.dataset.productId, 10);
        const isInc = btn.classList.contains("wujia-morder-mstep-plus");
        // Gửi product_id (row không giữ line_id); server cộng ±min_qty NGUYÊN TỬ,
        // giảm ở min = xoá dòng. Queue tuần tự (mutate) chống lost update.
        this.mutate("/portal/order/cart/step", { product_id: pid, direction: isInc ? "inc" : "dec" });
    }

    handleStep(btn) {
        const row = btn.closest(".wj-pc-cart-row, .wujia-mcart-row");
        if (!row) {
            return;
        }
        const lineId = parseInt(row.dataset.lineId, 10);
        const isInc = btn.dataset.action === "inc" || btn.classList.contains("wujia-mcart-step-plus");
        // WJ-ORD-002: gửi HƯỚNG, server cộng delta = ±min_qty NGUYÊN TỬ (không
        // set qty tuyệt đối) → 2 lần giảm gần đồng thời áp tuần tự, không lost
        // update. Bound min/max do server enforce (dưới min → xoá dòng, chạm
        // max → cap + cảnh báo). Giảm ở min = xoá dòng (đồng nhất hành vi cũ).
        this.mutate("/portal/order/cart/step", { line_id: lineId, direction: isInc ? "inc" : "dec" });
    }

    /* J-V4: câu hiển thị từ data-wj-msg-* trên chính root #wj-cart-sync (dịch bằng .po), fallback EN. */
    msg(key, fallback) {
        return window.wjMsg ? window.wjMsg(this.el, key, fallback) : fallback;
    }

    handleRemove(btn) {
        const row = btn.closest(".wj-pc-cart-row, .wujia-mcart-row");
        if (!row) {
            return;
        }
        const lineId = parseInt(row.dataset.lineId, 10);
        const name = row.querySelector(".wj-pc-cart-prod-name, .wujia-mcart-row-name");
        this.askRemove(name ? name.textContent.trim() : "", btn).then((ok) => {
            if (ok) {
                this.mutate("/portal/order/cart/remove", { line_id: lineId });
            }
        });
    }

    // Hỏi bằng hộp của portal (#wjCartRemove, cùng khuôn hộp gửi đơn WJ-ORD-028): Hủy / Esc /
    // bấm nền = không xoá. Trang nào thiếu hộp thì hỏi bằng trình duyệt — không bao giờ xoá
    // mà không hỏi.
    askRemove(name, opener) {
        const modal = document.getElementById("wjCartRemove");
        if (!modal) {
            return Promise.resolve(
                window.confirm(this.msg("remove-confirm", "Remove this product from the cart?"))
            );
        }
        if (!modal.hidden) {
            return Promise.resolve(false);
        }
        return new Promise((resolve) => {
            const buttons = Array.from(modal.querySelectorAll("[data-wj-cr-action]"));
            const close = (ok) => {
                modal.removeEventListener("click", onClick);
                document.removeEventListener("keydown", onKey, true);
                modal.setAttribute("hidden", "hidden");
                document.body.classList.remove("wj-order-confirm-open");
                if (opener.isConnected) {
                    opener.focus();
                }
                resolve(ok);
            };
            const onClick = (ev) => {
                const act = ev.target.closest("[data-wj-cr-action]");
                if (act) {
                    close(act.dataset.wjCrAction === "confirm");
                } else if (ev.target === modal) {
                    close(false);
                }
            };
            const onKey = (ev) => {
                if (ev.key === "Escape") {
                    ev.preventDefault();
                    close(false);
                } else if (ev.key === "Tab") {
                    // Giữ focus trong hộp: chỉ có 2 nút.
                    const i = buttons.indexOf(document.activeElement);
                    const next = ev.shiftKey ? (i <= 0 ? buttons.length - 1 : i - 1) : (i + 1) % buttons.length;
                    ev.preventDefault();
                    buttons[next].focus();
                }
            };
            modal.querySelector("[data-wj-cr='name']").textContent = name;
            modal.addEventListener("click", onClick);
            document.addEventListener("keydown", onKey, true);
            modal.removeAttribute("hidden");
            document.body.classList.add("wj-order-confirm-open");
            // Focus nút Hủy: Enter/Space bấm vội không xoá.
            modal.querySelector("[data-wj-cr-action='cancel']").focus();
        });
    }

    mutate(url, params) {
        // WJ-ORD-002: KHÔNG drop khi đang chạy — NỐI ĐUÔI (queue) để mỗi lần
        // bấm là 1 delta được áp tuần tự (server cộng nguyên tử). _doMutate tự
        // nuốt lỗi nên chain không bao giờ reject/đứt.
        this._chain = this._chain.then(() =>
            this._doMutate(url, { ...params, client_id: this._clientId })
        );
        return this._chain;
    }

    async _doMutate(url, params) {
        try {
            const res = await rpc(url, params);
            if (!res || res.error) {
                this.toast((res && res.message) || this.msg("generic-error", "Something went wrong. Please try again."), false);
                return;
            }
            if (res.removed) {
                // WJ-ORD-021: giảm ở min/xoá → phản hồi rõ.
                this.toast(this.msg("removed", "Removed from cart"), true);
            } else if (res.warning && res.message) {
                this.toast(res.message, false);
            }
            await this.refresh();
        } catch (e) {
            this.toast(this.msg("conn-error", "Connection error"), false);
        }
    }

    // pageshow + visibilitychange hay bắn liền nhau khi quay lại tab → gộp về 1
    // lần fetch. Ngưỡng nhỏ, không che được thay đổi thật (mutation gọi refresh()
    // thẳng, không qua đây).
    refreshIfStale(minGapMs = 1500) {
        if (Date.now() - this._lastRefreshAt < minGapMs) { return; }
        this.refresh();
    }

    // -------- fetch state + swap partial (coalesce overlapping) --------
    async refresh() {
        if (this._refreshing) {
            this._queued = true;
            return;
        }
        this._refreshing = true;
        this._lastRefreshAt = Date.now();
        try {
            const res = await rpc("/portal/order/cart/fragment", {});
            if (res && !res.error) {
                this.apply(res);
            }
        } catch (e) {
            // im lặng — lần refresh sau (hoặc reload) sẽ đồng bộ lại
        } finally {
            this._refreshing = false;
            if (this._queued) {
                this._queued = false;
                this.refresh();
            }
        }
    }

    apply(res) {
        const noteFocused = this.isNoteFocused();
        // Swap panel giỏ (giữ nguyên khi user đang gõ ghi chú → không mất focus/nội dung)
        const pc = document.querySelector(".wj-pc-cart");
        if (pc && res.pc_html && !noteFocused) {
            pc.outerHTML = res.pc_html;
        }
        const mc = document.querySelector(".wujia-mcart");
        if (mc && res.mobile_html && !noteFocused) {
            // FUNC-MOB-ORDER-005: đang gõ ghi chú mobile → hoãn swap (không mất
            // focus/nội dung); applyState vẫn cập nhật badge/floatbar.
            mc.innerHTML = res.mobile_html;
        }
        this.applyState(res);
    }

    applyState(res) {
        const count = res.line_count || 0;
        // Header cart badge (mọi trang portal có header)
        document.querySelectorAll(".wujia-header-cart-count").forEach((b) => {
            b.textContent = count;
            // WJ-ORD-020: `hidden` là lớp ẩn không phụ thuộc CSS ngoài, phải gỡ
            // cùng lúc với .is-active thì badge mới hiện.
            b.hidden = count <= 0;
            b.classList.toggle("is-active", count > 0);
        });
        // Badge nút thêm trên catalog (PC + mobile) + highlight dòng in-cart
        const qmap = res.qty_map || {};
        document.querySelectorAll(".btn-add-cart[data-product-id]").forEach((btn) => {
            const pid = parseInt(btn.dataset.productId, 10);
            const qty = qmap[pid] || 0;
            const badge = btn.querySelector(".wj-pc-order-add-badge, .wujia-morder-row-qty");
            if (badge) {
                badge.textContent = qty;
                badge.classList.toggle("d-none", qty <= 0);
            }
            const pcRow = btn.closest(".wj-pc-order-row");
            if (pcRow) {
                pcRow.classList.toggle("wj-pc-order-row--incart", qty > 0);
            }
        });
        // WJ-ORD-021: morph nút "Thêm" ↔ stepper "− N +" trên danh sách mobile.
        // Row catalog KHÔNG bị fragment swap → cập nhật tại chỗ từ qty_map. CSS
        // [data-qty="0"] ẩn stepper/hiện add, [data-qty>0] ngược lại.
        document.querySelectorAll(".wujia-morder-cartctl[data-product-id]").forEach((ctl) => {
            const pid = parseInt(ctl.dataset.productId, 10);
            const qty = qmap[pid] || 0;
            ctl.dataset.qty = qty;
            const q = ctl.querySelector(".wujia-morder-mstep-qty");
            if (q) {
                q.textContent = qty;
            }
        });
        // Floating cart bar mobile
        const fb = document.querySelector(".wujia-morder-floatbar");
        if (fb) {
            fb.classList.toggle("d-none", count <= 0);
            fb.dataset.cartTotal = Math.round(res.total_amount || 0);
            const c = fb.querySelector(".wujia-morder-floatbar-count");
            if (c) {
                c.textContent = count;
            }
            const t = fb.querySelector(".wujia-morder-floatbar-total");
            if (t) {
                // Tổng thanh toán (đã thuế) = số user thật sự trả. Fallback total_amount
                // để bản JS này không vỡ nếu chạy với payload server cũ.
                const grand =
                    res.total_tax_included !== undefined
                        ? res.total_tax_included
                        : res.total_amount;
                t.textContent = formatMoney(grand, res.currency_symbol, res.currency_decimals);
            }
        }
    }

    isNoteFocused() {
        // wj-cart-note = hook chung PC + mobile → guard swap cả 2 panel khi đang gõ.
        const a = document.activeElement;
        return !!(a && a.classList && a.classList.contains("wj-cart-note"));
    }

    toast(msg, ok) {
        window.wjToast(msg, { type: ok ? "success" : "error" });
    }
}

registry
    .category("public.interactions")
    .add("wujia_portal_sale.cart_sync", WujiaCartSync);
