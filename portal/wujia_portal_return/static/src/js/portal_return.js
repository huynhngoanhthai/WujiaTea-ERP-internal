/* Return form — image preview + order→product cascade (single-product, Sprint K1).
   Form submit là multipart standard, không cần JS intercept. */
(function () {
    "use strict";
    document.addEventListener("DOMContentLoaded", function () {
        // Image preview
        const fileInput = document.querySelector('input[name="images"]');
        const grid = document.getElementById("image-preview-grid");
        if (fileInput && grid) {
            fileInput.addEventListener("change", function () {
                grid.innerHTML = "";
                Array.from(fileInput.files).slice(0, 12).forEach(function (file) {
                    if (!file.type.startsWith("image/")) return;
                    const url = URL.createObjectURL(file);
                    const col = document.createElement("div");
                    col.className = "col-3 col-md-2";
                    col.innerHTML = `<img src="${url}" class="img-fluid rounded"/>`;
                    grid.appendChild(col);
                });
            });
        }

        // Cascade: đơn hàng gốc → sản phẩm (dòng đơn). data-lines = JSON {orderId: [{id,label}]}.
        document.querySelectorAll("select.wj-return-order").forEach(function (orderSel) {
            let lineMap = {};
            try {
                lineMap = JSON.parse(orderSel.dataset.lines || "{}");
            } catch (e) {
                lineMap = {};
            }
            const form = orderSel.closest("form");
            const lineSel = form && form.querySelector("select.wj-return-line");
            if (!lineSel) return;

            const full = form.querySelector(".wj-return-line-full");
            // Câu dịch theo ngôn ngữ người xem: data-wj-msg-* trên select đơn (QWeb), fallback EN.
            function msg(key, fallback) {
                return window.wjMsg ? window.wjMsg(orderSel, key, fallback) : fallback;
            }

            // `<select>` cắt tên theo bề rộng ô ⇒ in lại tên đầy đủ ở vùng dưới.
            function showFull() {
                if (!full) return;
                const label = lineSel.selectedOptions.length ? lineSel.selectedOptions[0].dataset.full : "";
                full.textContent = label || "";
                full.hidden = !label;
                lineSel.title = label || "";
            }

            function refill() {
                const lines = lineMap[orderSel.value] || [];
                lineSel.innerHTML = "";
                const ph = document.createElement("option");
                ph.value = "";
                ph.textContent = lines.length
                    ? msg("select-product", "— Select a product —")
                    : msg("no-products", "— Order has no products —");
                lineSel.appendChild(ph);
                lines.forEach(function (l) {
                    const opt = document.createElement("option");
                    opt.value = l.id;
                    opt.textContent = l.label;
                    opt.dataset.full = l.label;
                    lineSel.appendChild(opt);
                });
                showFull();
            }
            orderSel.addEventListener("change", refill);
            lineSel.addEventListener("change", showFull);
            if (orderSel.value) refill();
        });
    });
})();
