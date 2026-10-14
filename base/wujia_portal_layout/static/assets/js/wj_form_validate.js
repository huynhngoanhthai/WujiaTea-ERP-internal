/* Kiểm form trước khi gửi, thay bong bóng của trình duyệt: form có `data-wj-validate`,
   control sai ⇒ aria-invalid + hiện ô lỗi `#<id>-err` (wujia_portal_layout.wj_field_error). */
(function () {
    "use strict";

    function errorEl(ctrl) {
        return ctrl.id ? document.getElementById(ctrl.id + "-err") : null;
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
        if (invalid) {
            ctrl.setAttribute("aria-invalid", "true");
        } else {
            ctrl.removeAttribute("aria-invalid");
        }
        if (err) {
            err.hidden = !invalid;
            describedBy(ctrl, err.id, invalid);
        }
    }

    function controls(form) {
        return Array.prototype.filter.call(form.elements, function (el) {
            return el.willValidate && el.type !== "hidden";
        });
    }

    function init() {
        document.querySelectorAll("form[data-wj-validate]").forEach(function (form) {
            form.noValidate = true;
        });
    }

    document.addEventListener("submit", function (ev) {
        var form = ev.target;
        if (!form || form.tagName !== "FORM" || !form.hasAttribute("data-wj-validate")) {
            return;
        }
        var bad = controls(form).filter(function (el) {
            var invalid = !el.checkValidity();
            mark(el, invalid);
            return invalid;
        });
        if (!bad.length) {
            return;
        }
        ev.preventDefault();
        ev.stopImmediatePropagation();
        form.dispatchEvent(new CustomEvent("wj:form:release", { bubbles: true }));
        bad[0].focus();
    }, true);

    function recheck(ev) {
        var el = ev.target;
        if (el && el.form && el.form.hasAttribute("data-wj-validate")
                && el.getAttribute("aria-invalid") === "true" && el.checkValidity()) {
            mark(el, false);
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
