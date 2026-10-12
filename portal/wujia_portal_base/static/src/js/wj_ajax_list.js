/* Wujia Portal — lọc/phân trang danh sách không reload cả trang (dùng chung mọi trang).
 *
 * Chip trạng thái, pager và form lọc vốn là điều hướng thật: server dựng lại nguyên shell
 * portal (navbar, sidebar, chuông) dù chỉ có danh sách đổi. Ở đây bắt click/submit, tải nội
 * dung mới rồi thay đúng vài khối đã đánh dấu + pushState để URL vẫn share/F5/Back được.
 *
 * Trang khai báo bằng `wujia_portal_base.wj_ajax_list_config` (1 thẻ ẩn), 2 chế độ:
 *   - có `data-wj-fragment` → tải route fragment (chỉ các khối kết quả). Nhanh nhất, nhưng
 *     trang phải tách template + thêm 1 route.
 *   - không có            → tải chính URL danh sách rồi bóc khối theo id. Không đụng
 *     controller; người dùng vẫn hết reload, chỉ là server vẫn dựng shell.
 *
 * Không có JS (hoặc fetch lỗi) → rơi về điều hướng thường, hành vi y như trước.
 */
(function () {
    "use strict";

    var cfg = null;      // {listPath, fragmentPath, slots[], scroll}
    var pending = null;

    function readConfig() {
        var node = document.querySelector("[data-wj-list]");
        if (!node) {
            return null;
        }
        var slots = (node.getAttribute("data-wj-slots") || "")
            .split(",").map(function (s) { return s.trim(); }).filter(Boolean);
        if (!slots.length) {
            return null;
        }
        return {
            listPath: node.getAttribute("data-wj-list"),
            fragmentPath: node.getAttribute("data-wj-fragment") || "",
            slots: slots,
            scroll: node.getAttribute("data-wj-scroll") !== "false",
        };
    }

    function isListUrl(url) {
        return url.pathname === cfg.listPath;
    }

    function eachSlot(fn) {
        cfg.slots.forEach(function (id) {
            var el = document.getElementById(id);
            if (el) {
                fn(el);
            }
        });
    }

    function setBusy(busy) {
        eachSlot(function (el) {
            el.setAttribute("aria-busy", busy ? "true" : "false");
            el.classList.toggle("wj-ajax-busy", busy);
        });
    }

    /* Form lọc thường nằm NGOÀI vùng swap → đồng bộ tay theo URL để lần submit sau không
       mang trạng thái cũ. Chạy trên mọi control có `name` trong form lọc của trang; control
       không xuất hiện trong URL thì trả về rỗng (đúng nghĩa "bỏ lọc"). */
    function syncFilterControls(params) {
        document.querySelectorAll("form").forEach(function (form) {
            if (!isFilterForm(form)) {
                return;
            }
            form.querySelectorAll("input[name], select[name], textarea[name]").forEach(function (el) {
                if (el.type === "checkbox" || el.type === "radio") {
                    el.checked = params.getAll(el.name).indexOf(el.value) !== -1;
                } else if (el.type !== "submit" && el.type !== "button") {
                    el.value = params.get(el.name) || "";
                }
            });
        });
    }

    function isFilterForm(form) {
        if ((form.getAttribute("method") || "get").toLowerCase() !== "get") {
            return false;
        }
        // Base = URL hiện tại (không phải origin): action/href tương đối như "?page=2"
        // phải resolve theo trang đang đứng, nếu không sẽ ra '/' và trượt listPath.
        var action = new URL(form.getAttribute("action") || "", window.location.href);
        return isListUrl(action);
    }

    function swap(html) {
        var doc = new DOMParser().parseFromString(html, "text/html");
        var swapped = 0;
        cfg.slots.forEach(function (id) {
            var target = document.getElementById(id);
            var fresh = doc.getElementById(id);
            if (target && fresh) {
                target.replaceWith(fresh);
                swapped += 1;
            }
        });
        return swapped > 0;
    }

    /* Khoá chống bấm lặp CMP-BTN-001 (`wujia_button_loading.js`) cắm cờ lên form lúc submit và
       chỉ tự gỡ khi trang tải lại — ở đây trang không tải lại nên phải báo xong, cả khi bị lượt
       sau huỷ ngang. Thiếu bước này thì form lọc chỉ gửi được MỘT lần (WJ-ORD-027). */
    function releaseForm(form) {
        if (form) {
            form.dispatchEvent(new CustomEvent("wj:form:release", { bubbles: true }));
        }
    }

    function load(url, push, form) {
        if (pending) {
            pending.abort();
        }
        var controller = new AbortController();
        pending = controller;
        setBusy(true);

        // Chế độ fragment: cùng querystring, đổi path. Chế độ nhẹ: chính URL danh sách.
        var target = url;
        if (cfg.fragmentPath) {
            target = new URL(cfg.fragmentPath, window.location.origin);
            target.search = url.search;
        }

        fetch(target.toString(), {
            credentials: "same-origin",
            headers: { "X-Requested-With": "XMLHttpRequest" },
            signal: controller.signal,
        })
            .then(function (res) {
                if (!res.ok) {
                    throw new Error("HTTP " + res.status);
                }
                return res.text();
            })
            .then(function (html) {
                if (!swap(html)) {
                    throw new Error("no slot");
                }
                pending = null;
                setBusy(false);
                releaseForm(form);
                syncFilterControls(url.searchParams);
                if (push) {
                    window.history.pushState({ wjList: true }, "", url.pathname + url.search);
                }
                if (cfg.scroll) {
                    window.scrollTo({ top: 0, behavior: "smooth" });
                }
                // Widget nằm trong vùng swap (chart, date picker, tooltip) tự rebind ở đây.
                document.dispatchEvent(new CustomEvent("wj:list:swapped", {
                    detail: { url: url.toString(), slots: cfg.slots },
                }));
            })
            .catch(function (err) {
                if (err && err.name === "AbortError") {
                    releaseForm(form);
                    return;
                }
                pending = null;
                setBusy(false);
                window.location.assign(url.toString()); // fallback: điều hướng như cũ
            });
    }

    /* Link được nhận: nằm trong vùng swap (chip, pager), hoặc mang data-wj-nav (nút "Xóa
       lọc" ngoài vùng swap). Link ra trang khác (chi tiết) không khớp listPath → bỏ qua. */
    function isNavLink(link) {
        if (link.hasAttribute("data-wj-nav")) {
            return true;
        }
        return cfg.slots.some(function (id) {
            var slot = document.getElementById(id);
            return slot && slot.contains(link);
        });
    }

    function onClick(ev) {
        var link = ev.target.closest("a[href]");
        if (!link || ev.defaultPrevented || ev.button !== 0 ||
            ev.metaKey || ev.ctrlKey || ev.shiftKey || ev.altKey) {
            return;
        }
        if (link.target && link.target !== "_self") {
            return;
        }
        if (!isNavLink(link)) {
            return;
        }
        var url = new URL(link.getAttribute("href"), window.location.href);
        if (!isListUrl(url)) {
            return;
        }
        ev.preventDefault();
        load(url, true);
    }

    function onSubmit(ev) {
        var form = ev.target.closest("form");
        if (!form || ev.defaultPrevented || !isFilterForm(form)) {
            return;
        }
        var url = new URL(cfg.listPath, window.location.origin);
        new FormData(form).forEach(function (value, key) {
            if (value !== "") {
                url.searchParams.set(key, value); // bỏ tham số rỗng cho URL gọn
            }
        });
        ev.preventDefault();
        load(url, true, form);
    }

    function onPopState() {
        var url = new URL(window.location.href);
        if (isListUrl(url)) {
            load(url, false);
        }
    }

    function init() {
        cfg = readConfig();
        if (!cfg) {
            return; // không phải trang danh sách đã khai báo
        }
        document.addEventListener("click", onClick);
        document.addEventListener("submit", onSubmit);
        window.addEventListener("popstate", onPopState);
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", init);
    } else {
        init();
    }
})();
