/* ============================================================================
   Desktop "Đăng ký thi" — Figma WJ_Exam_PC v1.2 · 02_Create + 03/04 modal +
   07_UIStates. WIRED (Sprint 46): dùng chung 3 endpoint đã có với mobile —
   /portal/exam/calendar, /portal/exam/slots (mỗi slot mang session_id),
   /portal/exam/register (submit; server-resolve franchise/member/requester,
   backend tự capacity-lock). Người tham gia nhập tay qua modal → append/replace
   <tr> mang dữ liệu thật + ảnh base64; submit gom session_id + các dòng → POST.
   Lỗi validate/hết chỗ hiện trong alert 07_UIStates thay vì toast giả.
   Không đụng mobile (portal_exam_wizard.js) hay phần đọc PC.
   ========================================================================== */
(function () {
    "use strict";

    var MAX_PHOTO_BYTES = 5 * 1024 * 1024;
    var PHOTO_MIME_RE = /^image\/(png|jpe?g)$/i;
    /* Giống hệt PHONE_RE của model — regex cũ nới hơn server nên lọt tới submit. */
    var PHONE_RE = /^(0|\+84)[0-9]{8,10}$/;

    function qs(root, sel) { return root ? root.querySelector(sel) : null; }
    function qsa(root, sel) {
        return root ? Array.prototype.slice.call(root.querySelectorAll(sel)) : [];
    }
    function show(el) { if (el) { el.hidden = false; } }
    function hide(el) { if (el) { el.hidden = true; } }

    /* Loading của atom Button: giữ bề rộng, khoá bấm lặp khi request chưa về. */
    function setBusy(btn, on) {
        if (!btn) { return; }
        btn.disabled = on;
        btn.classList.toggle("is-loading", on);
        btn.setAttribute("aria-busy", on ? "true" : "false");
    }

    function jsonRpc(url, params) {
        return fetch(url, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            credentials: "include",
            body: JSON.stringify({
                jsonrpc: "2.0", method: "call", params: params || {},
            }),
        }).then(function (r) { return r.json(); })
          .then(function (j) { return j.result || {}; });
    }

    function isoToDMY(iso) {
        if (!iso) { return "—"; }
        var p = iso.split("-");
        return p.length === 3 ? (p[2] + "/" + p[1] + "/" + p[0]) : iso;
    }

    /* map trạng thái ngày backend (available/full/none/out) → class Figma. */
    function dayStateClass(state) {
        return { available: "available", full: "blocked",
                 none: "none", out: "out" }[state] || "none";
    }

    /* Câu dịch chèn vào HTML dựng tay (aria-label) — thoát ký tự đặc biệt. */
    function escAttr(text) {
        return String(text).replace(/&/g, "&amp;").replace(/"/g, "&quot;")
            .replace(/</g, "&lt;").replace(/>/g, "&gt;");
    }

    function init(root) {
        /* J-V3 — câu hiển thị lấy từ data-wj-msg-* trên root (dịch bằng .po); fallback tiếng Anh. */
        function m(key, fallback, arg) {
            var text = window.wjMsg ? window.wjMsg(root, key, fallback) : fallback;
            return arg === undefined ? text : text.replace("%s", arg);
        }
        /* ---- element refs ---- */
        var courseSelect = qs(root, "[data-wj-exam-course]");
        var calEl        = qs(root, "[data-wj-exam-cal]");
        var calLabel     = qs(root, ".wj-exam-pc-cal__label");
        var calBody      = qs(root, "[data-wj-exam-cal-body]");
        var calSkel      = qs(root, "[data-wj-exam-cal-skel]");
        var calEmpty     = qs(root, "[data-wj-exam-cal-empty]");
        var dayGrid      = qsa(root, "[data-wj-exam-cal-body] .wj-exam-pc-cal__grid")
            .filter(function (g) {
                return !g.classList.contains("wj-exam-pc-cal__grid--wd");
            })[0] || null;
        var slotList     = qs(root, "[data-wj-exam-slot-list]");
        var slotEmpty    = qs(root, "[data-wj-exam-slot-empty]");
        var slotEmptyTtl = qs(root, "[data-wj-exam-slot-empty-title]");
        var slotEmptyBtn = qs(root, "[data-wj-exam-pick-other-day]");
        /* D3 (wj_card_header) bỏ class .wj-exam-pc-slots__title ⇒ selector cũ ra null, tiêu đề kẹt "—" (sửa J-V4). */
        var slotTitle    = qs(root, ".wj-exam-pc-slots__head .wj-card-header__title");
        var conflict     = qs(root, "[data-wj-exam-conflict]");
        var sendHint     = qs(root, "[data-wj-exam-send-hint]");
        var partBody     = qs(root, "[data-wj-exam-part-body]");
        var noteInput    = qs(root, "#wj_exam_note");

        var sumValues    = qsa(root, ".wj-exam-pc-sumkv__value");   // 0 course·1 dt·2 loc·3 hạn·4 store
        var helpText     = qs(root, "[data-wj-exam-help]");
        var quotaChip    = qs(root, ".wj-exam-pc-quota .wj-exam-pc-chip--primary");
        var seatChip     = qs(root, ".wj-exam-pc-quota .wj-exam-pc-chip--green");

        var kvValues     = qsa(root, ".wj-exam-pc-kv__value");      // submit modal: 0 course·1 dt·2 loc·3 hạn
        var mQuotaChip   = qs(root, ".wj-exam-pc-modal__chips .wj-exam-pc-chip--primary");
        var mSeatChip    = qs(root, ".wj-exam-pc-modal__chips .wj-exam-pc-chip--green");
        var sumBody      = qs(root, "[data-wj-exam-sum-body]");
        var noteBox      = qs(root, ".wj-exam-pc-notebox");
        var sendBtn      = qs(root, "[data-wj-exam-send]");

        var partModal    = qs(root, '[data-wj-exam-modal="participant"]');
        var nameInput    = qs(root, "#wj_exam_p_name");
        var phoneInput   = qs(root, "#wj_exam_p_phone");
        var birthInput   = qs(root, "#wj_exam_p_birth");
        var jobInput     = qs(root, "#wj_exam_p_job");
        var phoneErr     = qs(root, "[data-wj-exam-phone-err]");
        var fieldHelp    = qs(root, "[data-wj-exam-field-help]");
        var modalTitle   = qs(partModal, ".wj-exam-pc-modal__title");
        var saveBtn      = qs(root, "[data-wj-exam-part-save]");
        var thumb        = qs(root, ".wj-exam-pc-thumb");
        var fileNameEl   = qs(root, ".wj-exam-pc-photobox__file");
        var photoBox     = qs(root, ".wj-exam-pc-photobox");
        var photoTitle   = qs(root, ".wj-exam-pc-photobox__title");
        var photoPickBtn = qs(root, ".wj-exam-pc-photobtn:not(.wj-exam-pc-photobtn--del)");
        var photoDelBtn  = qs(root, ".wj-exam-pc-photobtn--del");

        /* ---- state ---- */
        var editingRow = null;      // <tr> đang sửa, null = chế độ thêm
        var modalPhoto = "";        // dataURL ảnh hiện tại của modal
        var chosen = freshChosen();
        var maxPer = parseMax();    // sức chứa mỗi phiếu (course default → slot khi chọn)

        function freshChosen() {
            return { sessionId: 0, iso: "", dateLabel: "", time: "",
                     loc: "—", seats: 0, deadline: "—" };
        }
        function parseMax() {
            // Giới hạn của khóa đang chọn; chọn ca thi thì ca ghi đè (selectSlot).
            if (!courseSelect || courseSelect.selectedIndex < 0) { return 0; }
            var opt = courseSelect.options[courseSelect.selectedIndex];
            return parseInt(opt.getAttribute("data-wj-exam-course-max"), 10) || 0;
        }
        function currentCourseId() {
            return courseSelect ? (parseInt(courseSelect.value, 10) || 0) : 0;
        }
        function courseName() {
            if (!courseSelect || courseSelect.selectedIndex < 0) { return "—"; }
            return (courseSelect.options[courseSelect.selectedIndex].textContent || "").trim();
        }

        /* hidden file input dùng chung cho ảnh modal. */
        var fileInput = document.createElement("input");
        fileInput.type = "file";
        fileInput.accept = "image/png,image/jpeg";
        fileInput.hidden = true;
        root.appendChild(fileInput);

        /* ================= Lịch (calendar) ================= */
        function getYM() {
            return {
                year: parseInt(calEl && calEl.getAttribute("data-exam-year"), 10) || 0,
                month: parseInt(calEl && calEl.getAttribute("data-exam-month"), 10) || 0,
            };
        }
        function setYM(y, m) {
            if (!calEl) { return; }
            calEl.setAttribute("data-exam-year", y);
            calEl.setAttribute("data-exam-month", m);
        }
        function renderGrid(cal) {
            if (!dayGrid) { return; }
            var html = "";
            (cal.weeks || []).forEach(function (week) {
                week.forEach(function (d) {
                    var avail = d.state === "available";
                    html += '<button type="button" class="wj-exam-pc-day wj-exam-pc-day--'
                        + dayStateClass(d.state) + '" data-wj-exam-day="' + d.day + '"'
                        + ' data-exam-iso="' + (d.date || "") + '"'
                        + (avail ? "" : ' disabled="disabled"') + ">" + d.day
                        + (avail ? '<i class="wj-exam-pc-day__dot"></i>' : "")
                        + "</button>";
                });
            });
            dayGrid.innerHTML = html;
        }
        function loadCalendar(year, month) {
            var cid = currentCourseId();
            if (!cid) { showMonthEmpty(); return; }
            hide(calBody); hide(calEmpty); show(calSkel);
            jsonRpc("/portal/exam/calendar", {
                course_id: cid, year: year, month: month,
            }).then(function (res) {
                hide(calSkel);
                if (!res || res.error || !res.calendar) { showMonthEmpty(); return; }
                renderGrid(res.calendar);
                if (calLabel) { calLabel.textContent = res.calendar.label || ""; }
                setYM(res.calendar.year, res.calendar.month);
                hide(calEmpty); show(calBody);
            }).catch(function () { hide(calSkel); showMonthEmpty(); });
        }
        function showMonthEmpty() {
            hide(calBody); show(calEmpty);
            // đổi tháng/khóa → xoá slot đã tải + reset chọn.
            clearSlots(m("pick-day", "Pick a day with sessions to see its time slots."));
        }

        /* ================= Khung giờ (slots) ================= */
        function clearSlots(msg) {
            if (slotList) { slotList.innerHTML = ""; }
            if (slotEmptyTtl) { slotEmptyTtl.textContent = msg || m("pick-day", "Pick a day with sessions to see its time slots."); }
            hide(slotEmptyBtn);
            show(slotEmpty);
        }
        function renderSlots(slots) {
            if (!slotList) { return; }
            slotList.innerHTML = "";
            if (!slots || !slots.length) {
                if (slotEmptyTtl) { slotEmptyTtl.textContent = m("no-slots", "No time slots available."); }
                show(slotEmptyBtn); show(slotEmpty);
                return;
            }
            hide(slotEmpty);
            slots.forEach(function (s) {
                var avail = !!s.available;
                var btn = document.createElement("button");
                btn.type = "button";
                btn.className = "wj-exam-pc-slot" + (avail ? " wj-exam-pc-slot--open" : "");
                if (!avail) {
                    btn.setAttribute("disabled", "disabled");
                } else {
                    btn.setAttribute("data-wj-exam-slot-session", s.session_id);
                    btn.setAttribute("data-wj-exam-slot-max", s.max_per_reg);
                    btn.setAttribute("data-wj-exam-slot-loc", s.location || "—");
                    btn.setAttribute("data-wj-exam-slot-seats", s.seats);
                    btn.setAttribute("data-wj-exam-slot-deadline", s.deadline || "—");
                    btn.setAttribute("data-wj-exam-slot-time", s.time);
                }
                btn.innerHTML =
                    '<i class="feather icon-clock wj-exam-pc-slot__icon"></i>'
                    + '<span class="wj-exam-pc-slot__time"></span>'
                    + '<span class="wj-exam-pc-slot__chip wj-exam-pc-slot__chip--'
                    + (avail ? "open" : "overdue") + '"></span>'
                    + '<i class="feather icon-check-circle wj-exam-pc-slot__check"></i>';
                qs(btn, ".wj-exam-pc-slot__time").textContent = s.time;
                qs(btn, ".wj-exam-pc-slot__chip").textContent = s.status;
                slotList.appendChild(btn);
            });
        }
        function loadSlots(iso) {
            var cid = currentCourseId();
            if (!cid || !iso) { return; }
            if (slotList) { slotList.innerHTML = ""; }
            if (slotEmptyTtl) { slotEmptyTtl.textContent = m("loading-slots", "Loading time slots…"); }
            hide(slotEmptyBtn); show(slotEmpty);
            jsonRpc("/portal/exam/slots", {
                course_id: cid, exam_date: iso,
            }).then(function (res) {
                if (res && res.error) {
                    if (slotEmptyTtl) { slotEmptyTtl.textContent = res.message || m("load-failed", "Could not load time slots."); }
                    return;
                }
                renderSlots(res && res.slots);
            }).catch(function () {
                if (slotEmptyTtl) { slotEmptyTtl.textContent = m("load-error", "Connection error while loading time slots."); }
            });
        }

        /* ================= Chọn ngày / khung giờ ================= */
        function selectDay(day) {
            qsa(root, ".wj-exam-pc-day").forEach(function (d) {
                d.classList.remove("is-selected");
                if (d.classList.contains("wj-exam-pc-day--available")
                    && !qs(d, ".wj-exam-pc-day__dot")) {
                    var i = document.createElement("i");
                    i.className = "wj-exam-pc-day__dot";
                    d.appendChild(i);
                }
            });
            day.classList.add("is-selected");
            var dot = qs(day, ".wj-exam-pc-day__dot");
            if (dot) { dot.remove(); }
            chosen = freshChosen();
            chosen.iso = day.getAttribute("data-exam-iso") || "";
            chosen.dateLabel = isoToDMY(chosen.iso);
            if (slotTitle) { slotTitle.textContent = m("slot-title", "Time slots on %s", chosen.dateLabel); }
            hideConflict();
            syncSummary();
            loadSlots(chosen.iso);
        }
        function selectSlot(slot) {
            qsa(root, ".wj-exam-pc-slot").forEach(function (s) { s.classList.remove("is-selected"); });
            slot.classList.add("is-selected");
            chosen.sessionId = parseInt(slot.getAttribute("data-wj-exam-slot-session"), 10) || 0;
            chosen.time = slot.getAttribute("data-wj-exam-slot-time") || "";
            chosen.loc = slot.getAttribute("data-wj-exam-slot-loc") || "—";
            chosen.seats = parseInt(slot.getAttribute("data-wj-exam-slot-seats"), 10) || 0;
            chosen.deadline = slot.getAttribute("data-wj-exam-slot-deadline") || "—";
            maxPer = parseInt(slot.getAttribute("data-wj-exam-slot-max"), 10) || maxPer;
            hideConflict();
            syncSummary();
        }

        /* ================= Tóm tắt (cột phải) ================= */
        function realRows() { return qsa(partBody, "tr[data-wj-exam-part-row]"); }

        function syncSummary() {
            if (sumValues[0]) { sumValues[0].textContent = courseName(); }
            if (sumValues[1]) {
                sumValues[1].textContent = (chosen.dateLabel && chosen.time)
                    ? (chosen.dateLabel + " · " + chosen.time) : "—";
            }
            if (sumValues[2]) { sumValues[2].textContent = chosen.sessionId ? chosen.loc : "—"; }
            if (sumValues[3]) { sumValues[3].textContent = chosen.sessionId ? chosen.deadline : "—"; }
            // sumValues[4] = cửa hàng (server, không đổi).
            if (seatChip) {
                seatChip.textContent = chosen.sessionId ? m("seats-left", "Seats left in slot: %s", chosen.seats) : "—";
            }
            updateQuota();
        }
        function updateQuota() {
            var txt = realRows().length + " / " + maxPer;
            if (quotaChip) { quotaChip.textContent = txt; }
            if (mQuotaChip) { mQuotaChip.textContent = txt; }
            // WJ-EXAM-007: hướng dẫn đi cùng chip, nếu không ca thi có quota khác
            // khóa sẽ để lại câu cũ.
            if (helpText) {
                helpText.textContent = maxPer
                    ? m("max-hint", "Each registration allows at most %s people.", maxPer)
                    : m("max-hint-none", "Choose an exam course to see the limit of people per registration.");
            }
        }

        /* ================= Người tham gia (bảng + modal) ================= */
        function togglePlaceholder() {
            var ph = qs(partBody, "[data-wj-exam-part-empty]");
            if (ph) { ph.hidden = realRows().length > 0; }
        }
        function renderRowCells(tr) {
            var p = tr._wjPart || {}, hasPhoto = !!tr._wjPhoto;
            tr.innerHTML =
                '<td><span class="wj-exam-pc-photo"><span class="wj-exam-pc-avatar'
                + (hasPhoto ? "" : " wj-exam-pc-avatar--empty")
                + '"><i class="feather icon-user"></i></span><span class="wj-exam-pc-photo__tag'
                + (hasPhoto ? "" : " wj-exam-pc-photo__tag--empty") + '"></span></span></td>'
                + '<td class="wj-exam-pc-td--name"></td>'
                + "<td></td>"
                + '<td class="wj-pc-td--muted"></td>'
                + '<td class="wj-pc-td--muted"></td>'
                + '<td><span class="wj-exam-pc-rowacts">'
                + '<button type="button" class="wj-iconbtn wj-iconbtn--ghost wj-iconbtn--sm" data-wj-exam-line-edit="1" aria-label="' + escAttr(m("edit-row", "Edit this participant")) + '">'
                + '<i class="feather icon-edit-2"></i></button>'
                + '<button type="button" class="wj-iconbtn wj-iconbtn--ghost wj-iconbtn--sm" data-wj-exam-line-remove="1" aria-label="' + escAttr(m("remove-row", "Delete participant")) + '">'
                + '<i class="feather icon-trash-2"></i></button></span></td>';
            qs(tr, ".wj-exam-pc-photo__tag").textContent = hasPhoto ? m("photo-uploaded", "Uploaded") : m("photo-missing", "No photo");
            var td = tr.querySelectorAll("td");
            td[1].textContent = p.employee_name || "";
            td[2].textContent = p.phone || "";
            td[3].textContent = p.birth_year || "";
            td[4].textContent = p.job_position || "";
        }
        function buildRow(part, photo) {
            var tr = document.createElement("tr");
            tr.setAttribute("data-wj-exam-part-row", "1");
            tr._wjPart = part;
            tr._wjPhoto = photo || "";
            renderRowCells(tr);
            return tr;
        }

        /* WJ-EXAM-008 — nơi DUY NHẤT vẽ trạng thái ảnh từ modalPhoto: chưa chọn / đã chọn loại trừ nhau.
           fileLabel: tên tệp vừa chọn; error: câu lỗi khi tệp không hợp lệ (vẫn là trạng thái chưa chọn). */
        function resetPhotoPreview(fileLabel, error) {
            var has = !!modalPhoto;
            if (photoBox) { photoBox.classList.toggle("is-empty", !has); }
            if (photoTitle) {
                photoTitle.textContent = has ? m("photo-selected", "Photo selected") : m("photo-none", "No photo selected");
            }
            if (photoPickBtn) {
                photoPickBtn.textContent = has ? m("photo-change", "Change photo") : m("photo-choose", "Choose photo");
            }
            if (photoDelBtn) { photoDelBtn.hidden = !has; }
            if (fileNameEl) {
                fileNameEl.textContent = error || (has ? (fileLabel || m("photo-chosen", "Photo chosen")) : "");
                fileNameEl.hidden = !fileNameEl.textContent;
            }
            if (thumb) {
                if (modalPhoto) {
                    thumb.innerHTML = "";
                    var img = document.createElement("img");
                    img.src = modalPhoto;
                    img.alt = "";
                    img.style.cssText = "width:100%;height:100%;object-fit:cover;border-radius:inherit;";
                    thumb.appendChild(img);
                } else {
                    thumb.innerHTML = '<i class="feather icon-user"></i>';
                }
            }
        }
        function clearFieldInvalid() {
            qsa(root, ".wj-exam-pc-formgrid .wj-pc-field").forEach(function (f) {
                f.classList.remove("is-invalid");
            });
        }
        function openParticipantModal(row) {
            editingRow = row || null;
            var p = row ? (row._wjPart || {}) : {};
            if (nameInput) { nameInput.value = p.employee_name || ""; }
            if (phoneInput) { phoneInput.value = p.phone || ""; }
            if (birthInput) { birthInput.value = p.birth_year || ""; }
            if (jobInput) { jobInput.value = p.job_position || ""; }
            modalPhoto = row ? (row._wjPhoto || "") : "";
            fileInput.value = "";
            resetPhotoPreview();
            hide(phoneErr); hide(fieldHelp); clearFieldInvalid();
            if (modalTitle) { modalTitle.textContent = row ? m("modal-edit", "Edit participant") : m("modal-add", "Add participant"); }
            if (saveBtn) { saveBtn.textContent = row ? m("save", "Save") : m("add-person", "Add person"); }
            openModal("participant");
        }
        function saveParticipant() {
            var name = nameInput ? nameInput.value.trim() : "";
            var phone = phoneInput ? phoneInput.value.trim() : "";
            var phoneOk = PHONE_RE.test(phone);
            if (!name || !phoneOk) {
                if (phoneInput) { phoneInput.closest(".wj-pc-field").classList.toggle("is-invalid", !phoneOk); }
                if (nameInput) { nameInput.closest(".wj-pc-field").classList.toggle("is-invalid", !name); }
                if (!phoneOk) { show(phoneErr); } else { hide(phoneErr); }
                if (fieldHelp) { fieldHelp.textContent = m("name-phone-required", "Name and phone number are required."); }
                show(fieldHelp);
                return;
            }
            var part = {
                employee_name: name, phone: phone,
                birth_year: birthInput ? birthInput.value.trim() : "",
                job_position: jobInput ? jobInput.value.trim() : "",
            };
            if (editingRow) {
                editingRow._wjPart = part;
                editingRow._wjPhoto = modalPhoto || "";
                renderRowCells(editingRow);
            } else {
                if (maxPer && realRows().length >= maxPer) {
                    if (fieldHelp) { fieldHelp.textContent = m("max-people", "At most %s people per registration.", maxPer); }
                    show(fieldHelp);
                    return;
                }
                partBody.appendChild(buildRow(part, modalPhoto));
            }
            hide(fieldHelp); hide(phoneErr); clearFieldInvalid();
            togglePlaceholder(); updateQuota(); closeModals();
        }

        /* ---- ảnh modal ---- */
        function onPhotoPick() {
            var file = fileInput.files && fileInput.files[0];
            if (!file) { return; }
            if (!PHOTO_MIME_RE.test(file.type) || file.size > MAX_PHOTO_BYTES) {
                modalPhoto = ""; fileInput.value = "";
                resetPhotoPreview("", m("photo-invalid", "Invalid photo (JPG/PNG, ≤ 5 MB)."));
                return;
            }
            var reader = new FileReader();
            reader.onload = function () {
                modalPhoto = reader.result || "";
                resetPhotoPreview(file.name + " · " + ((file.type.split("/")[1] || "").toUpperCase()));
            };
            reader.readAsDataURL(file);
        }

        /* ================= Modal ================= */
        function openModal(name) {
            var modal = qs(root, '[data-wj-exam-modal="' + name + '"]');
            if (!modal) { return; }
            show(modal);
            document.body.style.overflow = "hidden";
            var first = qs(modal, "input, select, textarea");
            if (first) { first.focus(); }
        }
        function closeModals() {
            qsa(root, "[data-wj-exam-modal]").forEach(hide);
            document.body.style.overflow = "";
        }

        /* ================= Alert xung đột ================= */
        function showConflict(title, text) {
            if (conflict) {
                var t = qs(conflict, ".wj-exam-pc-alert__title");
                var x = qs(conflict, ".wj-exam-pc-alert__text");
                if (t && title) { t.textContent = title; }
                if (x && text) { x.textContent = text; }
                show(conflict);
                conflict.scrollIntoView({ behavior: "smooth", block: "center" });
            }
        }
        function hideConflict() { hide(conflict); }

        /* ================= Xác nhận (modal submit) ================= */
        function buildSubmitSummary() {
            if (kvValues[0]) { kvValues[0].textContent = courseName(); }
            if (kvValues[1]) {
                kvValues[1].textContent = (chosen.dateLabel && chosen.time)
                    ? (chosen.dateLabel + " · " + chosen.time) : "—";
            }
            if (kvValues[2]) { kvValues[2].textContent = chosen.loc || "—"; }
            if (kvValues[3]) { kvValues[3].textContent = chosen.deadline || "—"; }
            if (mSeatChip) { mSeatChip.textContent = m("seats-left", "Seats left in slot: %s", chosen.seats); }
            updateQuota();
            if (sumBody) {
                sumBody.innerHTML = "";
                realRows().forEach(function (tr) {
                    var p = tr._wjPart || {}, hasPhoto = !!tr._wjPhoto;
                    var r = document.createElement("tr");
                    r.innerHTML =
                        '<td><span class="wj-exam-pc-avatar wj-exam-pc-avatar--sm'
                        + (hasPhoto ? "" : " wj-exam-pc-avatar--empty")
                        + '"><i class="feather icon-user"></i></span></td>'
                        + '<td class="wj-exam-pc-td--name"></td>'
                        + "<td></td>"
                        + '<td class="wj-pc-td--muted"></td>'
                        + '<td class="wj-pc-td--muted"></td>';
                    var td = r.querySelectorAll("td");
                    td[1].textContent = p.employee_name || "";
                    td[2].textContent = p.phone || "";
                    td[3].textContent = p.birth_year || "—";
                    td[4].textContent = p.job_position || "—";
                    sumBody.appendChild(r);
                });
            }
            if (noteBox) {
                var note = noteInput ? noteInput.value.trim() : "";
                noteBox.textContent = note || "—";
            }
        }
        function openCheck() {
            hideConflict();
            if (!chosen.sessionId) {
                showConflict(m("no-slot-title", "No exam time slot selected."),
                    m("no-slot-text", "Pick a day and a time slot with seats left before submitting."));
                return;
            }
            if (realRows().length === 0) {
                showConflict(m("no-people-title", "No participants yet."),
                    m("no-people-text", "Add at least 1 participant."));
                return;
            }
            buildSubmitSummary();
            openModal("submit");
        }

        /* ================= Gửi (submit thật) ================= */
        function collectParticipants() {
            return realRows().map(function (tr) {
                var p = tr._wjPart || {};
                var out = {
                    employee_name: p.employee_name, phone: p.phone,
                    birth_year: p.birth_year || "", job_position: p.job_position || "",
                };
                if (tr._wjPhoto) { out.photo = tr._wjPhoto; }
                return out;
            });
        }
        function submitRegistration() {
            var participants = collectParticipants();
            if (!chosen.sessionId || !participants.length) {
                closeModals();
                showConflict(m("missing-title", "Missing information"),
                    m("missing-text", "A time slot and at least 1 participant are required."));
                return;
            }
            setBusy(sendBtn, true);
            show(sendHint);
            function fail(title, text) {
                setBusy(sendBtn, false);
                hide(sendHint); closeModals();
                showConflict(title, text);
            }
            jsonRpc("/portal/exam/register", {
                session_id: chosen.sessionId,
                note: noteInput ? noteInput.value.trim() : "",
                participants: participants,
            }).then(function (res) {
                if (res && res.success && res.redirect) {
                    window.location = res.redirect;
                    return;
                }
                var msg = (res && res.message) || m("submit-failed", "Could not submit the request. Please try again.");
                if (res && res.error === "not_found") {
                    fail(msg, m("keep-data", "Your participants and photos are kept. Please choose the time slot again."));
                } else {
                    fail(m("submit-failed-title", "Could not submit the request"), msg);
                }
            }).catch(function () {
                fail(m("conn-error", "Connection error"),
                    m("submit-failed", "Could not submit the request. Please try again."));
            });
        }

        /* ================= Event delegation ================= */
        root.addEventListener("click", function (ev) {
            var t = ev.target;

            // Modal backdrop → đóng.
            if (t.hasAttribute && t.hasAttribute("data-wj-exam-modal")) {
                closeModals(); return;
            }
            if (t.closest("[data-wj-exam-close]")) { closeModals(); return; }

            var monthBtn = t.closest("[data-wj-exam-month]");
            if (monthBtn) {
                var ym = getYM();
                var delta = monthBtn.getAttribute("data-wj-exam-month") === "prev" ? -1 : 1;
                var mo = ym.month + delta, y = ym.year;
                if (mo < 1) { mo = 12; y -= 1; } else if (mo > 12) { mo = 1; y += 1; }
                loadCalendar(y, mo);
                return;
            }

            var day = t.closest(".wj-exam-pc-day");
            if (day && !day.disabled && day.classList.contains("wj-exam-pc-day--available")) {
                selectDay(day); return;
            }

            var slot = t.closest(".wj-exam-pc-slot");
            if (slot && !slot.disabled) { selectSlot(slot); return; }

            if (t.closest("[data-wj-exam-pick-other-day]")
                || t.closest("[data-wj-exam-pick-other-slot]")) {
                hideConflict();
                if (calEl) { calEl.scrollIntoView({ behavior: "smooth", block: "center" }); }
                return;
            }

            var edit = t.closest("[data-wj-exam-line-edit]");
            if (edit) { openParticipantModal(edit.closest("tr")); return; }

            var rm = t.closest("[data-wj-exam-line-remove]");
            if (rm) {
                var row = rm.closest("tr");
                if (row) { row.remove(); }
                togglePlaceholder(); updateQuota();
                return;
            }

            if (t.closest('[data-wj-exam-open="participant"]')) {
                openParticipantModal(null); return;
            }

            // ảnh: xóa trước, đổi sau (--del là subset của photobtn).
            if (t.closest(".wj-exam-pc-photobtn--del")) {
                modalPhoto = ""; fileInput.value = ""; resetPhotoPreview();
                return;
            }
            if (t.closest(".wj-exam-pc-photobtn")) { fileInput.click(); return; }

            if (t.closest("[data-wj-exam-part-save]")) { saveParticipant(); return; }
            if (t.closest("[data-wj-exam-check]")) { openCheck(); return; }
            if (t.closest("[data-wj-exam-send]")) { submitRegistration(); return; }
        });

        root.addEventListener("change", function (ev) {
            if (ev.target === courseSelect) {
                chosen = freshChosen();
                maxPer = parseMax();
                clearSlots(m("pick-day", "Pick a day with sessions to see its time slots."));
                if (slotTitle) { slotTitle.textContent = m("slot-title-empty", "Time slot"); }
                var ym = getYM();
                loadCalendar(ym.year, ym.month);
                syncSummary();
                return;
            }
            if (ev.target === fileInput) { onPhotoPick(); return; }
        });

        document.addEventListener("keydown", function (ev) {
            if (ev.key === "Escape") { closeModals(); }
        });

        /* ---- initial sync (lịch đã do server render sẵn) ---- */
        syncSummary();
        togglePlaceholder();
    }

    document.addEventListener("DOMContentLoaded", function () {
        qsa(document, '[data-wj-exam-pc="register"]').forEach(init);
    });
})();
