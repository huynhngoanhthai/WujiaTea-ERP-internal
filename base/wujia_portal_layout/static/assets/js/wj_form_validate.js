/* Kiểm form trước khi gửi, thay bong bóng của trình duyệt: form có `data-wj-validate`,
   control sai ⇒ aria-invalid + hiện ô lỗi `#<id>-err` (wujia_portal_layout.wj_field_error)
   + hộp tổng `[data-wj-error-summary]` (wujia_portal_layout.wj_error_summary). */
(function () {
    "use strict";

    var MB = 1024 * 1024;

    function errorEl(ctrl) {
        return ctrl.id ? document.getElementById(ctrl.id + "-err") : null;
    }

    // Control ẩn (input file sau vùng kéo thả) chỉ tới phần tử nhận focus qua `data-wj-focus`.
    function focusEl(ctrl) {
        var id = ctrl.getAttribute("data-wj-focus");
        return (id && document.getElementById(id)) || ctrl;
    }

    function describedBy(ctrl, errId, on) {
        var ids = (ctrl.getAttribute("aria-describedby") || "").split(/\s+/).filter(function (x) {
            return x && x !== errId;
        });
        if (on) {
            ids.push(errId);
        }
        if (ids.length) {
            ctrl.setAttribute("aria-describedby", ids.join(" "));
        } else {
            ctrl.removeAttribute("aria-describedby");
        }
    }

    function mark(ctrl, invalid) {
        var err = errorEl(ctrl);
        var targets = focusEl(ctrl) === ctrl ? [ctrl] : [ctrl, focusEl(ctrl)];
        targets.forEach(function (el) {
            if (invalid) {
                el.setAttribute("aria-invalid", "true");
            } else {
                el.removeAttribute("aria-invalid");
            }
            if (err) {
                describedBy(el, err.id, invalid);
            }
        });
        if (err) {
            err.hidden = !invalid;
        }
    }

    // Phạm vi kiểm: form `data-wj-validate`, hoặc khối `data-wj-validate-scope` (wizard gửi JSON, không có <form>).
    function scopeOf(el) {
        return el.closest && el.closest("form[data-wj-validate], [data-wj-validate-scope]");
    }

    function controls(root) {
        var els = root.tagName === "FORM" ? root.elements : root.querySelectorAll("input, select, textarea");
        return Array.prototype.filter.call(els, function (el) {
            return el.willValidate && el.type !== "hidden" && scopeOf(el) === root;
        });
    }

    function num(el, attr) {
        var v = parseFloat(el.getAttribute(attr));
        return isNaN(v) ? null : v;
    }

    function accepts(input, file) {
        var tokens = (input.getAttribute("accept") || "").split(",").map(function (t) {
            return t.trim().toLowerCase();
        }).filter(Boolean);
        if (!tokens.length) {
            return true;
        }
        var name = (file.name || "").toLowerCase();
        var type = (file.type || "").toLowerCase();
        return tokens.some(function (t) {
            if (t.charAt(0) === ".") {
                return name.slice(-t.length) === t;
            }
            if (t.slice(-2) === "/*") {
                return type.indexOf(t.slice(0, -1)) === 0;
            }
            return type === t;
        });
    }

    function groupBytes(input) {
        var group = input.getAttribute("data-wj-total-group");
        var inputs = group && input.form
            ? input.form.querySelectorAll('input[type=file][data-wj-total-group="' + group + '"]')
            : [input];
        return Array.prototype.reduce.call(inputs, function (sum, el) {
            return sum + Array.prototype.reduce.call(el.files || [], function (s, f) { return s + f.size; }, 0);
        }, 0);
    }

    // Luật số tệp / dung lượng / loại chạy qua setCustomValidity ⇒ checkValidity() bắt chung.
    function checkFiles(input) {
        if (input.type !== "file") {
            return;
        }
        var files = Array.prototype.slice.call(input.files || []);
        var min = num(input, "data-wj-min-files");
        var max = num(input, "data-wj-max-files");
        var maxMb = num(input, "data-wj-max-mb");
        var totalMb = num(input, "data-wj-total-mb");
        var bad = (min !== null && files.length < min)
            || (max !== null && files.length > max)
            || files.some(function (f) {
                return (maxMb !== null && f.size > maxMb * MB) || !accepts(input, f);
            })
            || (totalMb !== null && groupBytes(input) > totalMb * MB);
        input.setCustomValidity(bad ? "invalid" : "");
    }

    function checkMatch(ctrl) {
        var other = ctrl.hasAttribute("data-wj-match") && document.getElementById(ctrl.getAttribute("data-wj-match"));
        if (other) {
            ctrl.setCustomValidity(ctrl.value && ctrl.value !== other.value ? "invalid" : "");
        }
    }

    function checkRules(ctrl) {
        checkFiles(ctrl);
        checkMatch(ctrl);
    }

    function labelOf(ctrl) {
        var lab = ctrl.id && document.querySelector('label[for="' + ctrl.id + '"]');
        var text = lab ? lab.textContent : (ctrl.getAttribute("aria-label") || ctrl.name || "");
        return text.replace(/\s+/g, " ").replace(/\s*\*\s*$/, "").trim();
    }

    function renderSummary(form, bad) {
        var box = form.querySelector("[data-wj-error-summary]");
        if (!box) {
            return;
        }
        var list = box.querySelector(".wj-error-summary__list");
        var title = box.querySelector(".wj-error-summary__title");
        list.textContent = "";
        bad.forEach(function (ctrl) {
            var err = errorEl(ctrl);
            var msg = err ? err.textContent.replace(/\s+/g, " ").trim() : "";
            var li = document.createElement("li");
            var a = document.createElement("a");
            a.href = "#" + focusEl(ctrl).id;
            a.setAttribute("data-wj-error-target", focusEl(ctrl).id);
            a.textContent = msg ? labelOf(ctrl) + ": " + msg : labelOf(ctrl);
            li.appendChild(a);
            list.appendChild(li);
        });
        title.textContent = bad.length ? (box.getAttribute("data-wj-msg-title") || "").replace("{n}", bad.length) : "";
        box.hidden = !bad.length;
    }

    function invalidControls(form) {
        return controls(form).filter(function (el) {
            return el.getAttribute("aria-invalid") === "true";
        });
    }

    function visible(el) {
        return !!(el.offsetWidth || el.offsetHeight || el.getClientRects().length);
    }

    function init() {
        document.querySelectorAll("form[data-wj-validate]").forEach(function (form) {
            form.noValidate = true;
            controls(form).forEach(checkRules);
            // Lỗi do server render sẵn (fe_show): nối aria + dựng hộp tổng + focus ô đầu ở khổ đang hiện.
            var bad = controls(form).filter(function (el) {
                var err = errorEl(el);
                return err && !err.hidden;
            });
            bad.forEach(function (el) { mark(el, true); });
            renderSummary(form, bad);
            if (bad.length && visible(form)) {
                focusEl(bad[0]).focus();
            }
        });
    }

    // Kiểm cả phạm vi: đánh dấu + hộp tổng + focus ô sai đầu; trả số ô sai.
    function validate(root) {
        var bad = controls(root).filter(function (el) {
            checkRules(el);
            var invalid = !el.checkValidity();
            mark(el, invalid);
            return invalid;
        });
        renderSummary(root, bad);
        if (bad.length) {
            focusEl(bad[0]).focus();
        }
        return bad.length;
    }

    function reset(root) {
        controls(root).forEach(function (el) { mark(el, false); });
        renderSummary(root, []);
    }

    window.wjFormValidate = {
        check: function (root) {
            root.setAttribute("data-wj-validate-scope", "1");
            return validate(root);
        },
        reset: reset,
    };

    document.addEventListener("submit", function (ev) {
        var form = ev.target;
        if (!form || form.tagName !== "FORM" || !form.hasAttribute("data-wj-validate")) {
            return;
        }
        if (!validate(form)) {
            return;
        }
        ev.preventDefault();
        ev.stopImmediatePropagation();
        form.dispatchEvent(new CustomEvent("wj:form:release", { bubbles: true }));
    }, true);

    document.addEventListener("click", function (ev) {
        var a = ev.target.closest && ev.target.closest("a[data-wj-error-target]");
        var ctrl = a && document.getElementById(a.getAttribute("data-wj-error-target"));
        if (ctrl) {
            ev.preventDefault();
            ctrl.scrollIntoView({ block: "center" });
            ctrl.focus();
        }
    });

    function recheck(ev) {
        var root = ev.target && scopeOf(ev.target);
        if (!root) {
            return;
        }
        var changed = false;
        controls(root).forEach(function (el) {
            checkRules(el);
            if (el.getAttribute("aria-invalid") === "true" && el.checkValidity()) {
                mark(el, false);
                changed = true;
            }
        });
        var box = root.querySelector("[data-wj-error-summary]");
        if (changed && box && !box.hidden) {
            renderSummary(root, invalidControls(root));
        }
    }
    document.addEventListener("input", recheck);
    document.addEventListener("change", recheck);

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", init);
    } else {
        init();
    }
})();
