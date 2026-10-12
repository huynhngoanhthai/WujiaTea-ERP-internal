/**
 * JavaScript Controller for Wujia Franchise Inspection Standalone Web Survey
 */

(function () {
  "use strict";
  function _t(key, defVal) {
    return (window.SURVEY_TRANS && window.SURVEY_TRANS[key]) || defVal || key;
  }

  function escapeHtml(str) {
    if (!str) return '';
    return String(str)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#039;');
  }

  document.addEventListener("DOMContentLoaded", function () {
    const app = document.getElementById("surveyApp");
    if (!app) return;

    const inspectionId = parseInt(app.dataset.inspectionId);
    const maxScore = parseFloat(app.dataset.maxChecklistScore || "95");
    let isExamSubmitted = app.dataset.isExamSubmitted === "true";
    let isInspectionClosed = app.dataset.isInspectionClosed === "true";

    // Auto trim leading/trailing whitespace caused by IDE XML auto-formatters
    function cleanExamTextareas() {
      document.querySelectorAll(".exam-ans").forEach(function (el) {
        if (el.value) {
          el.value = el.value.trim();
        }
      });
    }

    cleanExamTextareas();

        function safeParseArray(val) {
      if (!val) return [];
      if (Array.isArray(val)) return val;
      if (typeof val === 'string') {
        try {
          return JSON.parse(val);
        } catch (e) {
          try {
            return JSON.parse(val.replace(/'/g, '"').replace(/None/g, 'null').replace(/True/g, 'true').replace(/False/g, 'false'));
          } catch (e2) {
            return [];
          }
        }
      }
      return [];
    }

    // Format submitted exam row into green / red dashed inline answers (portal inspection style)
    function renderSubmittedExamRow(row, userAnswers, correctAnswers, isCorrect) {
      const titleEl = row.querySelector(".exam-quest-title");
      if (!titleEl) return;
      
      const originalText = row.dataset.originalQuestion || titleEl.textContent || "";
      row.dataset.originalQuestion = originalText;

      const parsedCorrect = safeParseArray(correctAnswers);

      let blankIndex = 0;
      const formattedHtml = originalText.replace(/_{2,}/g, function (match) {
        const uAns = (userAnswers && userAnswers[blankIndex] !== undefined) ? String(userAnswers[blankIndex]).trim() : "";
        let blankIsCorrect = false;

        const correctForBlank = parsedCorrect[blankIndex];
        if (correctForBlank !== undefined && correctForBlank !== null) {
          if (Array.isArray(correctForBlank)) {
            blankIsCorrect = correctForBlank.some(function (c) {
              const cStr = String(c).trim().toLowerCase();
              const uStr = uAns.toLowerCase();
              if (!uStr) return false;
              return cStr === uStr || (cStr.replace(/[^\w\d]/g, '') === uStr.replace(/[^\w\d]/g, '') && uStr.replace(/[^\w\d]/g, '') !== '');
            });
          } else {
            const cStr = String(correctForBlank).trim().toLowerCase();
            const uStr = uAns.toLowerCase();
            if (uStr) {
              blankIsCorrect = (cStr === uStr || (cStr.replace(/[^\w\d]/g, '') === uStr.replace(/[^\w\d]/g, '') && uStr.replace(/[^\w\d]/g, '') !== ''));
            }
          }
        } else if (isCorrect && uAns) {
          blankIsCorrect = true;
        }

        const displayAns = uAns || "...";
        blankIndex++;
        if (blankIsCorrect) {
          return '<span style="color: #16a34a; font-weight: bold; text-decoration: none; border-bottom: 2px dashed #16a34a; padding: 0 4px; margin: 0 4px;">' + escapeHtml(displayAns) + '</span>';
        } else {
          return '<span style="color: #dc2626; font-weight: bold; text-decoration: line-through; border-bottom: 2px dashed #dc2626; padding: 0 4px; margin: 0 4px;">' + escapeHtml(displayAns) + '</span>';
        }
      });

      titleEl.innerHTML = formattedHtml;
      const textarea = row.querySelector(".exam-ans");
      if (textarea) textarea.style.display = "none";
    }

    // Convert question blanks (____) into interactive inline input fields
    function initExamBlankInputs() {
      document.querySelectorAll(".exam-row").forEach(function (row) {
        const titleEl = row.querySelector(".exam-quest-title");
        const textarea = row.querySelector(".exam-ans");
        if (!titleEl || !textarea) return;

        const originalText = titleEl.textContent || "";
        row.dataset.originalQuestion = originalText;
        const blankRegex = /_{2,}/g;
        if (!blankRegex.test(originalText)) return;

        // Split existing answer lines
        const existingAns = (textarea.value || "").trim();
        let ansList = [];
        if (existingAns) {
          if (existingAns.includes("\n")) {
            ansList = existingAns.split("\n").map(s => s.trim());
          } else {
            ansList = existingAns.split(/[\n,;]+/).map(s => s.trim());
          }
        }

        // If exam is already submitted, render the portal style directly
        if (isExamSubmitted) {
          const correctAnswers = safeParseArray(row.dataset.correctAnswers);
          const isCorrect = row.dataset.isCorrect === "true";
          renderSubmittedExamRow(row, ansList, correctAnswers, isCorrect);
          return;
        }

        // Replace underscores with input fields
        let blankIndex = 0;
        const html = originalText.replace(blankRegex, function (match) {
          const val = ansList[blankIndex] !== undefined ? escapeHtml(ansList[blankIndex]) : "";
          const inputHtml = `<input type="text" class="exam-blank-input" data-blank-index="${blankIndex}" value="${val}" placeholder="..." autocomplete="off" />`;
          blankIndex++;
          return inputHtml;
        });

        titleEl.innerHTML = html;
        textarea.style.display = "none";

        // Bind input events on blank inputs to sync into hidden textarea
        const blankInputs = titleEl.querySelectorAll(".exam-blank-input");
        function syncToTextarea() {
          const vals = [];
          blankInputs.forEach(function (inp) {
            vals.push(inp.value.trim());
          });
          textarea.value = vals.join("\n");
          textarea.dispatchEvent(new Event("input", { bubbles: true }));
        }

        blankInputs.forEach(function (inp, idx) {
          inp.addEventListener("input", syncToTextarea);
          inp.addEventListener("keydown", function (e) {
            if (e.key === "Enter") {
              e.preventDefault();
              if (idx + 1 < blankInputs.length) {
                blankInputs[idx + 1].focus();
                blankInputs[idx + 1].select();
              }
            }
          });
        });
      });
    }

    initExamBlankInputs();


    // Clean when focus or input on textareas
    document.querySelectorAll(".exam-ans").forEach(function (el) {
      el.addEventListener("focus", function () {
        if (this.value) this.value = this.value.trim();
      });
    });

    function lockExamTab(examResults) {
      isExamSubmitted = true;
      app.dataset.isExamSubmitted = "true";

      const nameInput = document.getElementById("testEmployeeName");
      if (nameInput) {
        nameInput.readOnly = true;
        nameInput.style.backgroundColor = "#f8fafc";
      }
      const tenureInput = document.getElementById("tenure");
      if (tenureInput) {
        tenureInput.readOnly = true;
        tenureInput.style.backgroundColor = "#f8fafc";
      }
      document.querySelectorAll(".exam-ans").forEach(function (textarea) {
        textarea.readOnly = true;
        textarea.style.backgroundColor = "#f8fafc";
        textarea.style.display = "none";
      });

      const lockBadge = document.getElementById("examLockStatusBadge");
      if (lockBadge) {
        lockBadge.style.display = "inline-flex";
      }

      // Render Correct / Incorrect results directly in question text (portal style)
      document.querySelectorAll(".exam-row").forEach(function (row) {
        const rowId = parseInt(row.dataset.id);
        const res = (examResults && (examResults[rowId] || examResults[String(rowId)])) || null;
        let isCorrect = false;
        let point = 0;
        let correctAnswers = [];

        if (res) {
          isCorrect = Boolean(res.is_correct);
          point = res.point || 0;
          correctAnswers = safeParseArray(res.correct_answers);
        } else {
          isCorrect = row.dataset.isCorrect === "true";
          point = parseFloat(row.dataset.point || "0");
          correctAnswers = safeParseArray(row.dataset.correctAnswers);
        }

        row.dataset.isCorrect = isCorrect ? "true" : "false";
        row.dataset.point = String(point);

        row.classList.remove("exam-card-correct", "exam-card-incorrect");
        if (isCorrect) {
          row.classList.add("exam-card-correct");
        } else {
          row.classList.add("exam-card-incorrect");
        }

        // Remove any badge
        const badge = row.querySelector(".exam-result-badge");
        if (badge) badge.remove();

        // Format question text with green / red answer spans
        const textarea = row.querySelector(".exam-ans");
        const ansRaw = textarea ? textarea.value.trim() : "";
        let userAnswers = [];
        if (ansRaw) {
          if (ansRaw.includes("\n")) {
            userAnswers = ansRaw.split("\n").map(s => s.trim());
          } else {
            userAnswers = ansRaw.split(/[\n,;]+/).map(s => s.trim());
          }
        }
        renderSubmittedExamRow(row, userAnswers, correctAnswers, isCorrect);
      });
    }

    function lockEntireInspection() {
      isInspectionClosed = true;
      lockExamTab();

      document.querySelectorAll(".line-check").forEach(function (chk) {
        chk.disabled = true;
      });
      document.querySelectorAll(".line-note").forEach(function (input) {
        input.readOnly = true;
        input.style.backgroundColor = "#f8fafc";
      });
      document.querySelectorAll(".btn-trigger-upload").forEach(function (btn) {
        btn.style.display = "none";
      });
      document.querySelectorAll(".line-file").forEach(function (input) {
        input.disabled = true;
      });

      const submitBtn = document.getElementById("btnFinishSurvey");
      if (submitBtn) {
        submitBtn.disabled = true;
        submitBtn.innerHTML =
          '<i class="fa fa-lock"></i> ' +
          _t(
            "Completed",
            "Completed &amp; Locked",
          );
        submitBtn.style.background = "#64748b";
        submitBtn.style.boxShadow = "none";
        submitBtn.style.cursor = "not-allowed";
      }
    }

    if (isInspectionClosed) {
      lockEntireInspection();
    } else if (isExamSubmitted) {
      lockExamTab();
    }

    // Tab Switching
    const tabChecklistBtn = document.getElementById("tabChecklistBtn");
    const tabExamBtn = document.getElementById("tabExamBtn");
    const tabNotesBtn = document.getElementById("tabNotesBtn");
    const tabConfirmationBtn = document.getElementById("tabConfirmationBtn");
    const tabChecklistContent = document.getElementById("tabChecklistContent");
    const tabExamContent = document.getElementById("tabExamContent");
    const tabNotesContent = document.getElementById("tabNotesContent");
    const tabConfirmationContent = document.getElementById(
      "tabConfirmationContent",
    );

    function switchTab(tab) {
      sessionStorage.setItem("wujia_survey_active_tab_" + inspectionId, tab);
      if (tabChecklistContent)
        tabChecklistContent.style.display =
          tab === "checklist" ? "block" : "none";
      if (tabExamContent)
        tabExamContent.style.display = tab === "exam" ? "block" : "none";
      if (tabNotesContent)
        tabNotesContent.style.display = tab === "notes" ? "block" : "none";
      if (tabRevenueContent)
        tabRevenueContent.style.display = tab === "revenue" ? "block" : "none";
      if (tabConfirmationContent)
        tabConfirmationContent.style.display =
          tab === "confirmation" ? "block" : "none";
      if (tabChecklistBtn)
        tabChecklistBtn.classList.toggle("active", tab === "checklist");
      if (tabExamBtn) tabExamBtn.classList.toggle("active", tab === "exam");
      if (tabNotesBtn) tabNotesBtn.classList.toggle("active", tab === "notes");
      if (tabRevenueBtn)
        tabRevenueBtn.classList.toggle("active", tab === "revenue");
      if (tabConfirmationBtn)
        tabConfirmationBtn.classList.toggle("active", tab === "confirmation");
      if (tab === "confirmation") {
        setTimeout(function () {
          if (typeof resizeCanvas === "function") resizeCanvas();
        }, 60);
      }
    }

    const savedTab = sessionStorage.getItem(
      "wujia_survey_active_tab_" + inspectionId,
    );
    const hash = window.location.hash;
    if (hash && hash.includes("tab=confirmation")) {
      switchTab("confirmation");
    } else if (hash && hash.includes("tab=revenue")) {
      switchTab("revenue");
    } else if (hash && hash.includes("tab=notes")) {
      switchTab("notes");
    } else if (hash && hash.includes("tab=exam")) {
      switchTab("exam");
    } else if (
      savedTab &&
      ["checklist", "exam", "notes", "revenue", "confirmation"].includes(savedTab)
    ) {
      switchTab(savedTab);
    }

    if (tabChecklistBtn) {
      tabChecklistBtn.addEventListener("click", function () {
        switchTab("checklist");
      });
    }
    if (tabExamBtn) {
      tabExamBtn.addEventListener("click", function () {
        switchTab("exam");
      });
    }
    if (tabNotesBtn) {
      tabNotesBtn.addEventListener("click", function () {
        switchTab("notes");
      });
    }
    if (tabRevenueBtn) {
      tabRevenueBtn.addEventListener("click", function () {
        switchTab("revenue");
      });
    }
    if (tabConfirmationBtn) {
      tabConfirmationBtn.addEventListener("click", function () {
        switchTab("confirmation");
      });
    }

    // Attendance present counter
    function updatePresentCount() {
      let count = 0;
      document.querySelectorAll(".att-present-check").forEach(function (chk) {
        if (chk.checked) count++;
      });
      const el = document.getElementById("livePresentCount");
      if (el) el.innerText = count;
    }
    document.querySelectorAll(".att-present-check").forEach(function (chk) {
      chk.addEventListener("change", updatePresentCount);
    });

    // Toast notifications (Fixed overlay & smooth transition)
    let toastTimeout = null;
    function showToast(msg, isError) {
      const t = document.getElementById("toast");
      if (!t) return;
      if (toastTimeout) clearTimeout(toastTimeout);
      
      const translatedMsg = _t(msg, msg);
      t.className = isError ? "show toast-error" : "show toast-success";
      t.innerHTML = (isError ? '<i class="fa fa-circle-exclamation me-1" style="color: #fca5a5;"></i>' : '<i class="fa fa-circle-check me-1" style="color: #4ade80;"></i>') + `<span>${escapeHtml(translatedMsg)}</span>`;
      t.style.display = "inline-flex";
      
      toastTimeout = setTimeout(function () {
        t.classList.remove("show");
        setTimeout(function() {
          t.style.display = "none";
        }, 250);
      }, 3500);
    }

    // Custom Alert Modal
    const customAlertModalOverlay = document.getElementById(
      "customAlertModalOverlay",
    );
    const customAlertMessage = document.getElementById("customAlertMessage");
    const customAlertClose = document.getElementById("customAlertClose");
    const customAlertBtnOk = document.getElementById("customAlertBtnOk");
    let alertCallback = null;

    function showCustomAlert(msg, callback) {
      if (customAlertMessage) customAlertMessage.innerText = msg;
      alertCallback = callback || null;
      if (customAlertModalOverlay)
        customAlertModalOverlay.style.display = "flex";
    }

    function hideCustomAlert() {
      if (customAlertModalOverlay)
        customAlertModalOverlay.style.display = "none";
      if (alertCallback) {
        const cb = alertCallback;
        alertCallback = null;
        cb();
      }
    }

    if (customAlertClose)
      customAlertClose.addEventListener("click", hideCustomAlert);
    if (customAlertBtnOk)
      customAlertBtnOk.addEventListener("click", hideCustomAlert);
    if (customAlertModalOverlay) {
      customAlertModalOverlay.addEventListener("click", function (e) {
        if (e.target === customAlertModalOverlay) hideCustomAlert();
      });
    }

    function openPrevModal(data) {
      // Prev modal removed
    }

    // Click "Đợt trước" badge handler
    document.querySelectorAll(".btn-prev-info").forEach(function (btn) {
      btn.addEventListener("click", function () {
        const rawJson = this.dataset.prevInfo;
        if (rawJson && rawJson !== "null") {
          try {
            const data = JSON.parse(rawJson);
            openPrevModal(data);
          } catch (err) {
            alert(
              _t(
                "No previous inspection data available for this criterion.",
                "No previous inspection data available for this criterion.",
              ),
            );
          }
        } else {
          alert(
            _t(
              "No previous inspection data available for this criterion.",
              "No previous inspection data available for this criterion.",
            ),
          );
        }
      });
    });

    // Real-time Checklist Live Score, Total Score & Grade calculation
    const surveyGrades = window.SURVEY_GRADES || [];

    function updateLiveScore() {
      let deductions = 0;
      document.querySelectorAll(".item-row").forEach(function (row) {
        const chk = row.querySelector(".line-check");
        if (chk && !chk.checked) {
          deductions += parseFloat(row.dataset.deduction || "0");
        }
      });
      const currentChecklistScore = Math.max(0, maxScore - deductions);

      // 1. Update Checklist Score
      const liveChecklistScoreEl =
        document.getElementById("liveChecklistScore");
      if (liveChecklistScoreEl) {
        const formattedChecklist = Number.isInteger(currentChecklistScore)
          ? currentChecklistScore
          : currentChecklistScore.toFixed(1);
        liveChecklistScoreEl.innerText = formattedChecklist + " / " + maxScore;
      }

      // 2. Read Exam Score
      const appEl = document.getElementById("surveyApp");
      const examScore = parseFloat(
        appEl ? appEl.dataset.examScore || "0" : "0",
      );
      const currentTotalScore = currentChecklistScore + examScore;

      // 3. Update Total Score
      const liveTotalScoreEl = document.getElementById("liveTotalScore");
      if (liveTotalScoreEl) {
        liveTotalScoreEl.innerText = Number.isInteger(currentTotalScore)
          ? currentTotalScore
          : currentTotalScore.toFixed(1);
      }

      // 4. Update Grade (Xếp loại A, B, C, D...)
      const liveGradeEl = document.getElementById("liveGrade");
      if (liveGradeEl) {
        let matchedGrade = "---";
        for (let i = 0; i < surveyGrades.length; i++) {
          const g = surveyGrades[i];
          if (
            currentTotalScore >= g.min_score &&
            currentTotalScore <= g.max_score
          ) {
            matchedGrade = g.name;
            break;
          }
        }
        liveGradeEl.innerText = matchedGrade;
      }

      // 5. Update each Section's Earned / Total score badge in real time
      document.querySelectorAll(".section-row").forEach(function (secRow) {
        const secId = secRow.dataset.sectionId;
        if (!secId) return;
        let secTotal = 0;
        let secEarned = 0;
        const secItems = document.querySelectorAll(
          '.item-row[data-section-id="' + secId + '"]',
        );
        secItems.forEach(function (item) {
          const deduction = parseFloat(item.dataset.deduction || "0");
          secTotal += deduction;
          const chk = item.querySelector(".line-check");
          if (chk && chk.checked) {
            secEarned += deduction;
          }
        });
        const earnedEl = secRow.querySelector(".sec-earned");
        const totalEl = secRow.querySelector(".sec-total");
        const badgeEl = secRow.querySelector(".section-score-badge");
        if (earnedEl) {
          earnedEl.innerText = Number.isInteger(secEarned)
            ? secEarned
            : secEarned.toFixed(1);
        }
        if (totalEl) {
          totalEl.innerText = Number.isInteger(secTotal)
            ? secTotal
            : secTotal.toFixed(1);
        }
        if (badgeEl) {
          if (secEarned === secTotal && secTotal > 0) {
            badgeEl.style.background = "#dcfce7";
            badgeEl.style.color = "#15803d";
            badgeEl.style.borderColor = "#86efac";
          } else {
            badgeEl.style.background = "#ffffff";
            badgeEl.style.color = "#1e293b";
            badgeEl.style.borderColor = "#cbd5e1";
          }
        }
      });
    }

    document.querySelectorAll(".line-check").forEach(function (chk) {
      chk.addEventListener("change", updateLiveScore);
    });

    // Run initial calculation
    updateLiveScore();

    // Image file upload preview
    document.querySelectorAll(".item-row").forEach(function (row) {
      const fileInput = row.querySelector(".line-file");
      const triggerBtn = row.querySelector(".btn-trigger-upload");
      const previewImg = row.querySelector(".img-preview");

      if (triggerBtn && fileInput) {
        triggerBtn.addEventListener("click", function () {
          if (!isInspectionClosed) fileInput.click();
        });
      }
      if (previewImg && fileInput) {
        previewImg.addEventListener("click", function () {
          if (!isInspectionClosed) fileInput.click();
        });
      }

      if (fileInput) {
        fileInput.addEventListener("change", function () {
          if (this.files && this.files[0]) {
            const reader = new FileReader();
            reader.onload = function (e) {
              if (previewImg) {
                previewImg.src = e.target.result;
                previewImg.style.display = "block";
              }
              if (triggerBtn) {
                triggerBtn.style.display = "none";
              }
              row.dataset.b64Image = e.target.result;
              const photoInd = row.querySelector(".photo-indicator");
              if (photoInd) photoInd.style.display = "inline-flex";
            };
            reader.readAsDataURL(this.files[0]);
          }
        });
      }
    });

    // Collect survey payload (lines, exam_lines, attendance, appearance, revenue report, signature)
    function collectSurveyPayload(isFinish) {
      const lines = [];
      document.querySelectorAll(".item-row").forEach(function (row) {
        const id = row.dataset.id;
        const chk = row.querySelector(".line-check");
        const noteInput = row.querySelector(".line-note");
        const isPass = chk ? chk.checked : true;
        const note = noteInput ? noteInput.value : "";
        const b64 = row.dataset.b64Image || null;

        const item = { id: parseInt(id), is_pass: isPass, note: note };
        if (b64 !== null && b64 !== undefined) item.evidence_image = b64;
        lines.push(item);
      });

      const examLines = [];
      document.querySelectorAll(".exam-row").forEach(function (row) {
        const id = row.dataset.id;
        const ansInput = row.querySelector(".exam-ans");
        const blankInputs = row.querySelectorAll(".exam-blank-input");
        let ans = "";
        if (blankInputs && blankInputs.length > 0) {
          const vals = [];
          blankInputs.forEach(function (inp) {
            vals.push(inp.value.trim());
          });
          ans = vals.join("\n");
          if (ansInput) ansInput.value = ans;
        } else if (ansInput) {
          ans = ansInput.value.trim();
        }
        examLines.push({ id: parseInt(id), answer: ans });
      });

      const attendanceLines = [];
      document.querySelectorAll(".attendance-row").forEach(function (row) {
        const id = row.dataset.id;
        const nameInput = row.querySelector(".att-name-input");
        const roleSelect = row.querySelector(".att-role-select");
        const phoneInput = row.querySelector(".att-phone-input");
        const isPresentChk = row.querySelector(".att-present-check");
        const noteInput = row.querySelector(".att-note-input");

        const isPresent = isPresentChk ? isPresentChk.checked : true;
        const note = noteInput ? noteInput.value : "";
        const name = nameInput ? nameInput.value : "";
        const role = roleSelect ? roleSelect.value : "staff";
        const phone = phoneInput ? phoneInput.value : "";

        attendanceLines.push({
          id: parseInt(id),
          employee_name: name,
          role: role,
          phone: phone,
          is_present: isPresent,
          note: note,
        });
      });

      const confirmedMemberSelect = document.getElementById(
        "confirmedMemberSelect",
      );
      const confirmedMemberId = confirmedMemberSelect
        ? confirmedMemberSelect.value || false
        : false;

      const nameInput = document.getElementById("testEmployeeName");
      const tenureInput = document.getElementById("tenure");
      const empName = nameInput ? nameInput.value.trim() : "";
      const empTenure = tenureInput ? tenureInput.value.trim() : "";

      const reportLines = (function () {
        const revList = [];
        const rows = document.querySelectorAll("#revenueTbody .revenue-row");
        rows.forEach((r) => {
          const id = r.dataset.id ? parseInt(r.dataset.id) : null;
          const mSel = r.querySelector(".rev-month-sel");
          const ySel = r.querySelector(".rev-year-sel");
          const revInp = r.querySelector(".rev-amount-input");
          const avgInp = r.querySelector(".rev-avg-input");
          const goodsInp = r.querySelector(".rev-goods-input");
          const appInp = r.querySelector(".rev-app-sale-input");
          const pctInp = r.querySelector(".rev-percent-input");
          const mVal = mSel ? mSel.value : "01";
          const yVal = ySel ? ySel.value : "2026";
          revList.push({
            id: id,
            date_month: `${yVal}-${mVal}-01`,
            revenue: revInp ? parseFloat(revInp.value || 0) : 0,
            revenue_avg: avgInp ? parseFloat(avgInp.value || 0) : 0,
            percent_goods: goodsInp ? parseFloat(goodsInp.value || 0) : 0,
            total_app_sale: appInp ? parseInt(appInp.value || 0) : 0,
            percent_app_sale: pctInp ? parseFloat(pctInp.value || 0) : 0,
          });
        });
        return revList;
      })();

      return {
        inspection_id: inspectionId,
        lines: lines,
        exam_lines: examLines,
        test_employee_name: empName,
        tenure: empTenure,
        store_appearance_issues: document.getElementById("storeAppearanceIssues")
          ? document.getElementById("storeAppearanceIssues").value
          : "",
        confirmed_member_id: confirmedMemberId,
        attendance_lines: attendanceLines,
        signature_image: document.getElementById("signatureDataInput")
          ? document.getElementById("signatureDataInput").value
          : "",
        report_lines: reportLines,
        finish: Boolean(isFinish),
      };
    }

    // Save survey draft without exam lock
    async function saveSurveyDraft() {
      if (isInspectionClosed) return;
      const payload = collectSurveyPayload(false);
      try {
        const res = await fetch(
          "/franchise/inspection/do/" + inspectionId + "/save",
          {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              jsonrpc: "2.0",
              method: "call",
              params: payload,
            }),
          },
        );
        const data = await res.json();
        if (data.result && data.result.success) {
          if (data.result.checklist_score !== undefined) {
            const lcs = document.getElementById("liveChecklistScore");
            if (lcs)
              lcs.innerText = data.result.checklist_score + " / " + maxScore;
          }
          if (data.result.total_score !== undefined) {
            const lts = document.getElementById("liveTotalScore");
            if (lts) lts.innerText = data.result.total_score;
          }
          return data.result;
        }
      } catch (e) {
        console.error("Survey draft save error:", e);
      }
      return null;
    }

    // Save survey data via AJAX (only lock exam tab on finish save)
    async function saveDataAndEvaluate() {
      if (isInspectionClosed) return;

      const nameInput = document.getElementById("testEmployeeName");
      const empName = nameInput ? nameInput.value.trim() : "";

      // MUST REQUIRE Nhân viên được kiểm tra (test_employee_name)
      if (!isExamSubmitted && !empName) {
        showCustomAlert(
          _t(
            "Please enter Tested Employee name!",
            "Please enter Tested Employee name before saving!",
          ),
          function () {
            switchTab("exam");
            if (nameInput) {
              nameInput.scrollIntoView({ behavior: "smooth", block: "center" });
              nameInput.focus();
              nameInput.style.borderColor = "#ef4444";
              nameInput.style.boxShadow = "0 0 0 3px rgba(239, 68, 68, 0.3)";
            }
          },
        );
        return false;
      } else if (nameInput) {
        nameInput.style.borderColor = "#cbd5e1";
        nameInput.style.boxShadow = "none";
      }

      const saveLoadingOverlay = document.getElementById("saveLoadingOverlay");
      const btnFinishSurvey = document.getElementById("btnFinishSurvey");
      let origSaveBtnHtml = "";

      if (saveLoadingOverlay) {
        saveLoadingOverlay.style.display = "flex";
      }
      if (btnFinishSurvey) {
        origSaveBtnHtml = btnFinishSurvey.innerHTML;
        btnFinishSurvey.disabled = true;
        btnFinishSurvey.style.pointerEvents = "none";
        btnFinishSurvey.style.opacity = "0.75";
        btnFinishSurvey.innerHTML = `<i class="fa fa-spinner fa-spin me-2"></i> ${_t("Saving...", "Saving...")}`;
      }

      const payload = collectSurveyPayload(true);

      try {
        const res = await fetch(
          "/franchise/inspection/do/" + inspectionId + "/save",
          {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              jsonrpc: "2.0",
              method: "call",
              params: payload,
            }),
          },
        );
        const data = await res.json();
        if (data.result && data.result.success) {
          showToast(
            _t(
              "Results saved successfully!",
              "Results saved successfully!",
            ),
            false,
          );
          if (data.result.checklist_score !== undefined) {
            const lcs = document.getElementById("liveChecklistScore");
            if (lcs)
              lcs.innerText = data.result.checklist_score + " / " + maxScore;

            const les = document.getElementById("liveExamScore");
            if (les && data.result.exam_score !== undefined) {
              les.innerText = data.result.exam_score;
            }

            const lts = document.getElementById("liveTotalScore");
            if (lts) lts.innerText = data.result.total_score;

            const lg = document.getElementById("liveGrade");
            if (lg) lg.innerText = data.result.grade || "---";
          }
          // Lock only the Exam tab after saving!
          lockExamTab(data.result ? data.result.exam_results : null);
        } else {
          showCustomAlert(
            data.result
              ? data.result.error
              : _t(
                  "An error occurred while saving!",
                  "An error occurred while saving!",
                ),
          );
        }
      } catch (err) {
        showToast(
          _t(
            "Server connection error!",
            "Server connection error!",
          ),
          true,
        );
      } finally {
        if (saveLoadingOverlay) {
          saveLoadingOverlay.style.display = "none";
        }
        if (btnFinishSurvey) {
          btnFinishSurvey.disabled = false;
          btnFinishSurvey.style.pointerEvents = "auto";
          btnFinishSurvey.style.opacity = "1";
          if (origSaveBtnHtml) btnFinishSurvey.innerHTML = origSaveBtnHtml;
        }
      }
    }


    const btnFinishSurvey = document.getElementById("btnFinishSurvey");
    if (btnFinishSurvey) {
      btnFinishSurvey.addEventListener("click", function (e) {
        e.preventDefault();
        e.stopPropagation();
        saveDataAndEvaluate();
      });
    }

    // Line Detail Modal Logic (iPad optimization)
    const lineDetailModalOverlay = document.getElementById(
      "lineDetailModalOverlay",
    );
    const lineModalClose = document.getElementById("lineModalClose");
    const lineModalBtnDone = document.getElementById("lineModalBtnDone");
    const lineModalTitle = document.getElementById("lineModalTitle");
    const lineModalContentText = document.getElementById(
      "lineModalContentText",
    );
    const lineModalPrevBadge = document.getElementById("lineModalPrevBadge");
    const lineModalPrevInspector = document.getElementById(
      "lineModalPrevInspector",
    );
    const lineModalPrevNote = document.getElementById("lineModalPrevNote");
    const lineModalPrevEvidenceWrap = document.getElementById(
      "lineModalPrevEvidenceWrap",
    );
    const lineModalPrevEvidenceImg = document.getElementById(
      "lineModalPrevEvidenceImg",
    );
    const lineModalNoteInput = document.getElementById("lineModalNoteInput");
    const lineModalTriggerUpload = document.getElementById(
      "lineModalTriggerUpload",
    );
    const lineModalImgContainer = document.getElementById(
      "lineModalImgContainer",
    );
    const lineModalImgPreview = document.getElementById("lineModalImgPreview");
    const lineModalCheck = document.getElementById("lineModalCheck");
    const lineModalCheckStatus = document.getElementById(
      "lineModalCheckStatus",
    );

    let activeRow = null;

    function compressImage(file, maxWidth, maxHeight, quality) {
      maxWidth = maxWidth || 1280;
      maxHeight = maxHeight || 1280;
      quality = quality || 0.75;
      return new Promise(function (resolve, reject) {
        const reader = new FileReader();
        reader.onload = function (e) {
          const img = new Image();
          img.onload = function () {
            let width = img.width;
            let height = img.height;
            if (width > height) {
              if (width > maxWidth) {
                height = Math.round((height * maxWidth) / width);
                width = maxWidth;
              }
            } else {
              if (height > maxHeight) {
                width = Math.round((width * maxHeight) / height);
                height = maxHeight;
              }
            }
            const canvas = document.createElement("canvas");
            canvas.width = width;
            canvas.height = height;
            const ctx = canvas.getContext("2d");
            ctx.drawImage(img, 0, 0, width, height);
            const dataUrl = canvas.toDataURL("image/jpeg", quality);
            resolve(dataUrl);
          };
          img.onerror = function () {
            resolve(e.target.result);
          };
          img.src = e.target.result;
        };
        reader.onerror = reject;
        reader.readAsDataURL(file);
      });
    }



    function openLineDetailModal(row) {
      if (
        activeRow === row &&
        lineDetailModalOverlay &&
        lineDetailModalOverlay.style.display === "flex"
      ) {
        return; // Dang mo cho dung tieu chi nay, khong ghi de mat ghi chu dang go
      }

      // Luu ghi chu cua hang truoc do neu doi hang
      if (activeRow && activeRow !== row) {
        const prevNoteInput = activeRow.querySelector(".line-note");
        if (prevNoteInput && lineModalNoteInput) {
          prevNoteInput.value = lineModalNoteInput.value;
          const noteInd = activeRow.querySelector(".note-indicator");
          if (noteInd) {
            noteInd.style.display = lineModalNoteInput.value.trim()
              ? "inline-flex"
            : "none";
          }
        }
      }

      activeRow = row;
      const contentTd = row.querySelector(".col-content");
      const contentText = contentTd ? contentTd.innerText.trim() : "";
      if (lineModalContentText) lineModalContentText.innerText = contentText;

      // Prev info
      const rawJson = row.dataset.prevInfo;
      if (rawJson && rawJson !== "null") {
        try {
          const prevData = JSON.parse(rawJson);
          if (prevData.is_pass) {
            lineModalPrevBadge.className = "badge-pass";
            lineModalPrevBadge.innerHTML = '<i class="fa fa-check"></i>';
          } else {
            lineModalPrevBadge.className = "badge-fail";
            lineModalPrevBadge.innerHTML = '<i class="fa fa-xmark"></i>';
          }
          lineModalPrevInspector.innerText =
            (prevData.planned_date || "") +
            " - " +
            (prevData.inspector || "---");
          const noteText = (prevData.note || "").trim();
          const hasNote =
            prevData.has_note ||
            (noteText &&
              noteText !== "No violation note" &&
              noteText !== "No violation note" && noteText !== "Chưa có ghi chú" &&
              noteText !== "-");
          if (hasNote && noteText) {
            lineModalPrevNote.innerHTML = `
              <div style="display: inline-flex; align-items: flex-start; gap: 8px; background: #fffbeb; border: 1px solid #fde68a; color: #b45309; padding: 8px 12px; border-radius: 8px; font-weight: 500; font-size: 13px; line-height: 1.5; width: 100%;">
                <i class="fa fa-note-sticky" style="color: #f59e0b; font-size: 16px; margin-top: 2px; flex-shrink: 0;"></i>
                <span style="word-break: break-word;">${noteText}</span>
              </div>
            `;
          } else {
            lineModalPrevNote.innerHTML =
              '<span style="color: #94a3b8; font-style: italic;">' +
              _t(
                "No previous violation notes recorded.",
                "No violation note",
              ) +
              "</span>";
          }
          if (prevData.has_evidence && prevData.evidence_url) {
            lineModalPrevEvidenceImg.src = prevData.evidence_url;
            lineModalPrevEvidenceWrap.style.display = "block";
          } else {
            lineModalPrevEvidenceWrap.style.display = "none";
          }
        } catch (e) {
          lineModalPrevBadge.className = "badge-none";
          lineModalPrevBadge.innerText = "-";
          lineModalPrevInspector.innerText = "---";
          lineModalPrevNote.innerHTML =
            '<span style="color: #94a3b8; font-style: italic;">' +
            _t(
              "No previous inspection data available for this criterion.",
              "No previous inspection data",
            ) +
            "</span>";
          lineModalPrevEvidenceWrap.style.display = "none";
        }
      } else {
        lineModalPrevBadge.className = "badge-none";
        lineModalPrevBadge.innerText = "-";
        lineModalPrevInspector.innerText = "---";
        lineModalPrevNote.innerHTML =
          '<span style="color: #94a3b8; font-style: italic;">' +
          _t(
            "No previous inspection data available for this criterion.",
            "No previous inspection data",
          ) +
          "</span>";
        lineModalPrevEvidenceWrap.style.display = "none";
      }

      // Note
      const noteInput = row.querySelector(".line-note");
      if (lineModalNoteInput && noteInput) {
        lineModalNoteInput.value = noteInput.value || "";
        lineModalNoteInput.readOnly = isInspectionClosed;
      }

      // Image
      const rowImgB64 = row.dataset.b64Image;
      const existingImg = row.querySelector(".img-preview");
      let imgSrc = "";
      if (rowImgB64 === "REMOVE") {
        imgSrc = "";
      } else if (rowImgB64 && rowImgB64.length > 20) {
        imgSrc = rowImgB64;
      } else if (existingImg && existingImg.src && existingImg.src.length > 20) {
        imgSrc = existingImg.src;
      }

      if (imgSrc) {
        if (lineModalImgPreview) lineModalImgPreview.src = imgSrc;
        if (lineModalImgContainer) lineModalImgContainer.style.display = "flex";
        if (lineModalUploadDropzone) lineModalUploadDropzone.style.display = "none";
      } else {
        if (lineModalImgPreview) lineModalImgPreview.src = "";
        if (lineModalImgContainer) lineModalImgContainer.style.display = "none";
        if (lineModalUploadDropzone) {
          lineModalUploadDropzone.style.display = isInspectionClosed ? "none" : "block";
        }
      }

      if (lineModalBtnChangePhoto) {
        lineModalBtnChangePhoto.style.display = isInspectionClosed ? "none" : "inline-flex";
      }
      if (lineModalBtnDeletePhoto) {
        lineModalBtnDeletePhoto.style.display = isInspectionClosed ? "none" : "inline-flex";
      }

      // Evaluation Checkbox
      const lineChk = row.querySelector(".line-check");
      if (lineModalCheck && lineChk) {
        lineModalCheck.checked = lineChk.checked;
        lineModalCheck.disabled = isInspectionClosed;
        lineModalCheckStatus.innerText = lineChk.checked
          ? _t("Pass", "Pass")
          : _t("Fail", "Fail");
        lineModalCheckStatus.style.color = lineChk.checked
          ? "#15803d"
          : "#ef4444";
      }

      if (lineDetailModalOverlay) lineDetailModalOverlay.style.display = "flex";
    }

    function closeLineDetailModal() {
      if (!activeRow) {
        if (lineDetailModalOverlay)
          lineDetailModalOverlay.style.display = "none";
        return;
      }
      // Save modal edits back to activeRow
      const noteInput = activeRow.querySelector(".line-note");
      if (noteInput && lineModalNoteInput) {
        noteInput.value = lineModalNoteInput.value;
        const noteInd = activeRow.querySelector(".note-indicator");
        if (noteInd) {
          noteInd.style.display = lineModalNoteInput.value.trim()
            ? "inline-flex"
            : "none";
        }
      }

      const lineChk = activeRow.querySelector(".line-check");
      if (lineChk && lineModalCheck) {
        if (lineChk.checked !== lineModalCheck.checked) {
          lineChk.checked = lineModalCheck.checked;
          updateLiveScore();
        }
      }

      if (lineDetailModalOverlay) lineDetailModalOverlay.style.display = "none";
      activeRow = null;
    }

    if (lineModalClose)
      lineModalClose.addEventListener("click", closeLineDetailModal);
    if (lineModalBtnDone)
      lineModalBtnDone.addEventListener("click", closeLineDetailModal);
    if (lineDetailModalOverlay) {
      lineDetailModalOverlay.addEventListener("click", function (e) {
        if (e.target === lineDetailModalOverlay) closeLineDetailModal();
      });
    }

    if (lineModalCheck) {
      lineModalCheck.addEventListener("change", function () {
        lineModalCheckStatus.innerText = this.checked
          ? _t("Pass", "Pass")
          : _t("Fail", "Fail");
        lineModalCheckStatus.style.color = this.checked ? "#15803d" : "#ef4444";
      });
    }

    // Dong bo tuc thi ghi chu vi pham khi nguoi dung dang go (Real-time 2-way sync)
    if (lineModalNoteInput) {
      lineModalNoteInput.addEventListener("input", function () {
        if (activeRow) {
          const noteInput = activeRow.querySelector(".line-note");
          if (noteInput) {
            noteInput.value = this.value;
          }
          const noteInd = activeRow.querySelector(".note-indicator");
          if (noteInd) {
            noteInd.style.display = this.value.trim()
              ? "inline-flex"
            : "none";
          }
        }
      });
    }

    const handleModalUpload = function (e) {
      if (e) {
        e.preventDefault();
        e.stopPropagation();
      }
      if (!activeRow || isInspectionClosed) return;
      const noteInput = activeRow.querySelector(".line-note");
      if (noteInput && lineModalNoteInput) {
        noteInput.value = lineModalNoteInput.value;
        const noteInd = activeRow.querySelector(".note-indicator");
        if (noteInd) {
          noteInd.style.display = lineModalNoteInput.value.trim() ? "inline-flex" : "none";
        }
      }
      const fileInput = activeRow.querySelector(".line-file");
      if (fileInput) fileInput.click();
    };

    if (lineModalUploadDropzone) {
      lineModalUploadDropzone.addEventListener("click", handleModalUpload);
    }
    if (lineModalBtnChangePhoto) {
      lineModalBtnChangePhoto.addEventListener("click", handleModalUpload);
    }
    if (lineModalBtnDeletePhoto) {
      lineModalBtnDeletePhoto.addEventListener("click", function (e) {
        e.preventDefault();
        e.stopPropagation();
        if (!activeRow || isInspectionClosed) return;
        activeRow.dataset.b64Image = "REMOVE";
        const fileInput = activeRow.querySelector(".line-file");
        if (fileInput) fileInput.value = "";
        const photoInd = activeRow.querySelector(".photo-indicator");
        if (photoInd) photoInd.style.display = "none";
        const previewImg = activeRow.querySelector(".img-preview");
        if (previewImg) {
          previewImg.src = "";
          previewImg.style.display = "none";
        }
        const triggerBtn = activeRow.querySelector(".btn-trigger-upload");
        if (triggerBtn) {
          triggerBtn.style.display = "inline-flex";
        }

        if (lineModalImgPreview) lineModalImgPreview.src = "";
        if (lineModalImgContainer) lineModalImgContainer.style.display = "none";
        if (lineModalUploadDropzone) lineModalUploadDropzone.style.display = "block";
      });
    }
    // Image Lightbox Viewer Setup (Available globally on window)
    const imageLightboxModalOverlay = document.getElementById(
      "imageLightboxModalOverlay",
    );
    const imageLightboxImg = document.getElementById("imageLightboxImg");
    const imageLightboxCaption = document.getElementById(
      "imageLightboxCaption",
    );
    const imageLightboxClose = document.getElementById("imageLightboxClose");

    window.openImageLightbox = function (imgSrc, caption) {
      if (!imgSrc || imgSrc === "REMOVE" || imgSrc.length < 5) return;
      const overlay = document.getElementById("imageLightboxModalOverlay");
      const img = document.getElementById("imageLightboxImg");
      const cap = document.getElementById("imageLightboxCaption");
      if (overlay && img) {
        img.src = imgSrc;
        if (cap) cap.textContent = caption || "";
        overlay.style.display = "flex";
      }
    };

    window.closeImageLightbox = function () {
      const overlay = document.getElementById("imageLightboxModalOverlay");
      const img = document.getElementById("imageLightboxImg");
      if (overlay) {
        overlay.style.display = "none";
        if (img) img.src = "";
      }
    };

    function openImageLightbox(imgSrc, caption) {
      window.openImageLightbox(imgSrc, caption);
    }

    function closeImageLightbox() {
      window.closeImageLightbox();
    }

    if (imageLightboxClose) {
      imageLightboxClose.addEventListener("click", function (e) {
        e.stopPropagation();
        closeImageLightbox();
      });
    }

    if (imageLightboxModalOverlay) {
      imageLightboxModalOverlay.addEventListener("click", function (e) {
        if (e.target === imageLightboxModalOverlay) {
          closeImageLightbox();
        }
      });
    }

    document.addEventListener("keydown", function (e) {
      if (
        e.key === "Escape" &&
        imageLightboxModalOverlay &&
        imageLightboxModalOverlay.style.display === "flex"
      ) {
        closeImageLightbox();
      }
    });

    // Click vào ảnh bằng chứng kỳ trước để xem chi tiết
    if (lineModalPrevEvidenceWrap) {
      lineModalPrevEvidenceWrap.addEventListener("click", function (e) {
        e.stopPropagation();
        if (lineModalPrevEvidenceImg && lineModalPrevEvidenceImg.src) {
          const note = lineModalPrevNote ? lineModalPrevNote.textContent.trim() : "";
          const cap = note && note !== "-" ? `Previous Note: ${note}` : "Previous Evidence Photo";
          openImageLightbox(lineModalPrevEvidenceImg.src, cap);
        }
      });
    }

    // Click vào ảnh đính kèm hiện tại để xem chi tiết
    if (lineModalImgPreviewWrap) {
      lineModalImgPreviewWrap.addEventListener("click", function (e) {
        e.stopPropagation();
        if (lineModalImgPreview && lineModalImgPreview.src) {
          const note = lineModalNoteInput ? lineModalNoteInput.value.trim() : "";
          const cap = note ? `Violation Note: ${note}` : "Violation Evidence Photo";
          openImageLightbox(lineModalImgPreview.src, cap);
        }
      });
    }

    // Bind both button and item-row click to open Line Detail Modal
    document.querySelectorAll(".item-row").forEach(function (row) {
      row.addEventListener("click", function (e) {
        // Bo qua neu nhan vao checkbox hoac file input
        if (
          e.target.closest(".col-eval") ||
          e.target.classList.contains("line-check") ||
          e.target.classList.contains("line-file")
        ) {
          return;
        }
        openLineDetailModal(row);
      });

      const fileInput = row.querySelector(".line-file");
      if (fileInput) {
        fileInput.addEventListener("click", function (e) {
          e.stopPropagation();
        });
        fileInput.addEventListener("change", async function (e) {
          e.stopPropagation();
          if (this.files && this.files[0]) {
            try {
              const compressedB64 = await compressImage(this.files[0]);
              row.dataset.b64Image = compressedB64;
              const photoInd = row.querySelector(".photo-indicator");
              if (photoInd) photoInd.style.display = "inline-flex";
              const previewImg = row.querySelector(".img-preview");
              if (previewImg) {
                previewImg.src = compressedB64;
                previewImg.style.display = "block";
              }
              const triggerBtn = row.querySelector(".btn-trigger-upload");
              if (triggerBtn) {
                triggerBtn.style.display = "none";
              }
              if (activeRow === row) {
                if (lineModalImgPreview) lineModalImgPreview.src = compressedB64;
                if (lineModalImgContainer) lineModalImgContainer.style.display = "flex";
                if (lineModalUploadDropzone) lineModalUploadDropzone.style.display = "none";
              }
            } catch (err) {
              console.error("Loi nen anh:", err);
            }
          }
        });
      }
    });

    document.querySelectorAll(".btn-open-line-detail").forEach(function (btn) {
      btn.addEventListener("click", function (e) {
        e.stopPropagation();
        const row = this.closest(".item-row");
        if (row) openLineDetailModal(row);
      });
    });
    // Attendance Management (Add, Save Member, Deactivate, Delete)
    const addStaffModalOverlay = document.getElementById(
      "addStaffModalOverlay",
    );
    const btnAddAttendanceStaff = document.getElementById(
      "btnAddAttendanceStaff",
    );
    const addStaffModalClose = document.getElementById("addStaffModalClose");
    const btnAddStaffCancel = document.getElementById("btnAddStaffCancel");
    const btnAddStaffSubmit = document.getElementById("btnAddStaffSubmit");
    const newStaffName = document.getElementById("newStaffName");
    const newStaffRole = document.getElementById("newStaffRole");
    const newStaffPhone = document.getElementById("newStaffPhone");
    const attendanceTbody = document.getElementById("attendanceTbody");
    const attendanceEmptyState = document.getElementById(
      "attendanceEmptyState",
    );

    function refreshConfirmedMemberSelect(storeMembers) {
      const select = document.getElementById("confirmedMemberSelect");
      if (!select) return;

      const currentVal = select.value;
      const roleLabels = {
        staff: _t("Staff", "Staff"),
        manager: _t("Manager", "Manager"),
        owner: _t("Store Owner", "Store Owner")
      };
      const placeholderText = _t("--- Select Store Manager ---", "--- Select Store Manager ---");

      if (Array.isArray(storeMembers)) {
        let html = `<option value="">${escapeHtml(placeholderText)}</option>`;
        storeMembers.forEach(function (m) {
          const roleText = roleLabels[m.role] || roleLabels.staff;
          const phoneText = m.phone ? (" - " + m.phone) : "";
          const label = m.name + " (" + roleText + ")" + phoneText;
          const isSelected = (String(m.id) === String(currentVal)) ? 'selected="selected"' : '';
          html += `<option value="${m.id}" ${isSelected}>${escapeHtml(label)}</option>`;
        });
        select.innerHTML = html;
        if (currentVal) {
          select.value = currentVal;
        }
      }
    }

    function updateOrAddConfirmedMemberOption(member) {
      if (!member || !member.id) return;
      const select = document.getElementById("confirmedMemberSelect");
      if (!select) return;

      const roleLabels = {
        staff: _t("Staff", "Staff"),
        manager: _t("Manager", "Manager"),
        owner: _t("Store Owner", "Store Owner")
      };
      const roleText = roleLabels[member.role] || roleLabels.staff;
      const phoneText = member.phone ? (" - " + member.phone) : "";
      const label = member.name + " (" + roleText + ")" + phoneText;

      let existingOpt = select.querySelector('option[value="' + member.id + '"]');
      if (existingOpt) {
        existingOpt.textContent = label;
      } else {
        const opt = document.createElement("option");
        opt.value = member.id;
        opt.textContent = label;
        select.appendChild(opt);
      }
    }

    function removeConfirmedMemberOption(memberId) {
      if (!memberId) return;
      const select = document.getElementById("confirmedMemberSelect");
      if (!select) return;
      const opt = select.querySelector('option[value="' + memberId + '"]');
      if (opt) {
        if (select.value === String(memberId)) {
          select.value = "";
        }
        opt.remove();
      }
    }

    function openAddStaffModal() {
      if (newStaffName) newStaffName.value = "";
      if (newStaffRole) newStaffRole.value = "staff";
      if (newStaffPhone) newStaffPhone.value = "";
      if (addStaffModalOverlay) addStaffModalOverlay.style.display = "flex";
      if (newStaffName) newStaffName.focus();
    }

    function closeAddStaffModal() {
      if (addStaffModalOverlay) addStaffModalOverlay.style.display = "none";
    }

    if (btnAddAttendanceStaff)
      btnAddAttendanceStaff.addEventListener("click", openAddStaffModal);
    if (addStaffModalClose)
      addStaffModalClose.addEventListener("click", closeAddStaffModal);
    if (btnAddStaffCancel)
      btnAddStaffCancel.addEventListener("click", closeAddStaffModal);

    if (btnAddStaffSubmit) {
      btnAddStaffSubmit.addEventListener("click", async function () {
        const name = newStaffName ? newStaffName.value.trim() : "";
        if (!name) {
          showCustomAlert(
            _t(
              "Notice",
              "Notice",
            ),
            _t(
              "Please enter Tested Employee name!",
              "Please enter staff full name!",
            ),
          );
          return;
        }
        const role = newStaffRole ? newStaffRole.value : "staff";
        const phone = newStaffPhone ? newStaffPhone.value.trim() : "";
        const note = "";

        const origAddStaffHtml = btnAddStaffSubmit.innerHTML;
        btnAddStaffSubmit.disabled = true;
        btnAddStaffSubmit.style.pointerEvents = "none";
        btnAddStaffSubmit.innerHTML = `<i class="fa fa-spinner fa-spin me-1"></i> ${_t("Adding...", "Adding...")}`;

        const saveLoadingOverlay = document.getElementById("saveLoadingOverlay");
        if (saveLoadingOverlay) {
          const loadingTextEl = saveLoadingOverlay.querySelector("div:nth-child(2)");
          if (loadingTextEl) loadingTextEl.innerText = _t("Adding employee...", "Adding employee...");
          saveLoadingOverlay.style.display = "flex";
        }

        try {
          const res = await fetch(
            "/franchise/inspection/do/" + inspectionId + "/attendance/add",
            {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({
                jsonrpc: "2.0",
                method: "call",
                params: {
                  inspection_id: inspectionId,
                  employee_name: name,
                  role: role,
                  phone: phone,
                  note: note,
                  is_present: true,
                },
              }),
            },
          );
          const data = await res.json();
          if (data.result && data.result.success && data.result.line) {
            closeAddStaffModal();
            const newLine = data.result.line;
            const tr = document.createElement("tr");
            tr.className = "attendance-row";
            tr.dataset.id = newLine.id;
            tr.dataset.memberId = newLine.member_id || "";
            tr.style.borderBottom = "1px solid #f1f5f9";

            const roleLabels = {
              staff: _t("Staff", "Staff"),
              manager: _t("Manager", "Manager"),
              owner: _t("Store Owner", "Store Owner")
            };

            tr.innerHTML = `
              <td style="padding: 8px 6px; font-weight: 600; color: #1e293b;">
                  <input type="text" class="att-name-input note-input" style="padding: 6px 8px; font-size: 13px; font-weight: 600; width: 100%; min-width: 120px;"
                      value="${escapeHtml(newLine.employee_name)}"
                      placeholder="Enter employee name..." />
                  <input type="hidden" class="att-phone-input" value="${escapeHtml(newLine.phone || '')}" />
              </td>
              <td style="padding: 8px 6px;">
                  <select class="att-role-select note-input" style="padding: 6px 4px; font-size: 12px; width: 100%;">
                      <option value="staff" ${newLine.role === "staff" ? "selected" : ""}>${roleLabels.staff}</option>
                      <option value="manager" ${newLine.role === "manager" ? "selected" : ""}>${roleLabels.manager}</option>
                      <option value="owner" ${newLine.role === "owner" ? "selected" : ""}>${roleLabels.owner}</option>
                  </select>
              </td>
              <td style="padding: 8px 6px; text-align: center;">
                  <input type="checkbox" class="att-present-check custom-checkbox"
                      style="width: 20px; height: 20px; cursor: pointer; accent-color: #3b82f6;"
                      ${newLine.is_present ? "checked" : ""} />
              </td>
              <td style="padding: 8px 6px; text-align: center; white-space: nowrap;">
                  <div class="att-actions-wrap">
                      <button type="button" class="btn-att-action btn-save-member"
                          title="${_t("Save or update to Franchise Members", "Save or update to Franchise Members")}">
                          <i class="fa fa-arrow-right"></i>
                      </button>
                      <button type="button" class="btn-att-action btn-deactivate-member"
                          title="${_t("Mark employee as resigned (is_working = False)", "Mark employee as resigned (is_working = False)")}"
                          style="${newLine.member_id ? "" : "display: none;"}">
                          <i class="fa fa-circle-info"></i>
                      </button>
                  </div>
              </td>
            `;
            if (attendanceTbody) {
              attendanceTbody.appendChild(tr);
            }
            bindAttendanceRowEvents(tr);
            if (data.result.store_members) {
              refreshConfirmedMemberSelect(data.result.store_members);
            } else if (data.result.member) {
              updateOrAddConfirmedMemberOption(data.result.member);
            }
            if (attendanceEmptyState) attendanceEmptyState.style.display = "none";
            updatePresentCount();
            showToast(
              _t(
                "Employee added to list successfully!",
                "Staff member added successfully!",
              ),
              false,
            );
          } else {
            showToast(
              data.result ? data.result.error : "Error adding staff",
              true,
            );
          }
        } catch (e) {
          showToast("Network error", true);
        } finally {
          btnAddStaffSubmit.disabled = false;
          btnAddStaffSubmit.style.pointerEvents = "auto";
          btnAddStaffSubmit.innerHTML = origAddStaffHtml;
          if (saveLoadingOverlay) saveLoadingOverlay.style.display = "none";
        }
      });
    }

    function bindAttendanceRowEvents(row) {
      const chk = row.querySelector(".att-present-check");
      if (chk) chk.addEventListener("change", updatePresentCount);

      // Save to Member (->) and save all other survey progress without exam
      const btnSaveMember = row.querySelector(".btn-save-member");
      if (btnSaveMember) {
        btnSaveMember.addEventListener("click", async function () {
          const origHtml = btnSaveMember.innerHTML;
          btnSaveMember.disabled = true;
          btnSaveMember.innerHTML = '<i class="fa fa-spinner fa-spin"></i>';
          const lineId = row.dataset.id;
          const nameInput = row.querySelector(".att-name-input");
          const roleSelect = row.querySelector(".att-role-select");
          const phoneInput = row.querySelector(".att-phone-input");
          const name = nameInput ? nameInput.value.trim() : "";
          const role = roleSelect ? roleSelect.value : "staff";
          const phone = phoneInput ? phoneInput.value.trim() : "";

          if (!name) {
            showCustomAlert(
              _t(
                "Notice",
                "Notice",
              ),
              _t(
                "Please enter Tested Employee name!",
                "Please enter staff name before saving!",
              ),
            );
            btnSaveMember.disabled = false;
            btnSaveMember.innerHTML = origHtml;
            return;
          }

          try {
            // 1. Lưu nhân viên vào danh sách Thành viên cửa hàng
            const res = await fetch(
              "/franchise/inspection/do/" +
                inspectionId +
                "/attendance/save_member",
              {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                  jsonrpc: "2.0",
                  method: "call",
                  params: {
                    inspection_id: inspectionId,
                    line_id: lineId,
                    employee_name: name,
                    role: role,
                    phone: phone,
                  },
                }),
              },
            );
            const data = await res.json();
            if (data.result && data.result.success) {
              row.dataset.memberId = data.result.member_id || "";
              const btnDeact = row.querySelector(".btn-deactivate-member");
              if (btnDeact && data.result.member_id)
                btnDeact.style.display = "inline-flex";

              if (data.result.store_members) {
                refreshConfirmedMemberSelect(data.result.store_members);
              } else if (data.result.member) {
                updateOrAddConfirmedMemberOption(data.result.member);
              }

              // 2. Lưu luôn toàn bộ các tiêu chí khảo sát, điểm danh, diện mạo mà không lưu/khóa bài kiểm tra
              await saveSurveyDraft();

              showToast(
                _t(
                  "Member and all survey progress saved successfully!",
                  "Staff member and survey criteria saved successfully!",
                ),
                false,
              );
            } else {
              showToast(
                data.result ? data.result.error : "Error saving member",
                true,
              );
            }
          } catch (e) {
            showToast("Network error", true);
          } finally {
            btnSaveMember.disabled = false;
            btnSaveMember.innerHTML = origHtml;
          }
        });
      }

      // Deactivate Member (i)
      const btnDeactMember = row.querySelector(".btn-deactivate-member");
      if (btnDeactMember) {
        btnDeactMember.addEventListener("click", async function () {
          const confirmMsg = _t(
            "Are you sure this employee has resigned (is_working = False)? This row will be removed from the survey.",
            "Are you sure this employee has left the job (is_working = False)? This row will be removed from the inspection survey.",
          );
          if (!confirm(confirmMsg)) return;

          const origHtml = btnDeactMember.innerHTML;
          btnDeactMember.disabled = true;
          btnDeactMember.innerHTML = '<i class="fa fa-spinner fa-spin"></i>';
          const lineId = row.dataset.id;

          const saveLoadingOverlay = document.getElementById("saveLoadingOverlay");
          if (saveLoadingOverlay) {
            const loadingTextEl = saveLoadingOverlay.querySelector("div:nth-child(2)");
            if (loadingTextEl) loadingTextEl.innerText = _t("Processing resignation...", "Processing resignation...");
            saveLoadingOverlay.style.display = "flex";
          }

          try {
            const res = await fetch(
              "/franchise/inspection/do/" +
                inspectionId +
                "/attendance/deactivate_member",
              {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                  jsonrpc: "2.0",
                  method: "call",
                  params: {
                    inspection_id: inspectionId,
                    line_id: lineId,
                  },
                }),
              },
            );
            const data = await res.json();
            if (data.result && data.result.success) {
              if (data.result.store_members) {
                refreshConfirmedMemberSelect(data.result.store_members);
              } else {
                const memIdToRemove = data.result.member_id || row.dataset.memberId;
                if (memIdToRemove) {
                  removeConfirmedMemberOption(memIdToRemove);
                }
              }
              row.remove();
              updatePresentCount();
              const remainingRows = attendanceTbody
                ? attendanceTbody.querySelectorAll(".attendance-row")
                : [];
              if (remainingRows.length === 0 && attendanceEmptyState) {
                attendanceEmptyState.style.display = "block";
              }
              showToast(
                _t(
                  "Employee resignation status updated successfully!",
                  "Employee resignation status updated successfully!",
                ),
                false,
              );
            } else {
              showToast(
                data.result ? data.result.error : "Error deactivating member",
                true,
              );
            }
          } catch (e) {
            showToast("Network error", true);
          } finally {
            if (saveLoadingOverlay) saveLoadingOverlay.style.display = "none";
            btnDeactMember.disabled = false;
            btnDeactMember.innerHTML = origHtml;
          }
        });
      }
    }

    document
      .querySelectorAll(".attendance-row")
      .forEach(bindAttendanceRowEvents);

    // ==========================================
    // Clean Pixel-Perfect Signature Pad Engine
    // ==========================================
    const signModal = document.getElementById("signModal");
    const btnOpenSignModal = document.getElementById("btnOpenSignModal");
    const sigPreviewContainer = document.getElementById("sigPreviewContainer");
    const btnCloseSignModal = document.getElementById("btnCloseSignModal");
    const btnCancelSignModal = document.getElementById("btnCancelSignModal");
    const btnSaveSignModal = document.getElementById("btnSaveSignModal");
    const btnClearModalCanvas = document.getElementById("btnClearModalCanvas");
    const btnClearSignature = document.getElementById("btnClearSignature");
    const sigCanvas = document.getElementById("signatureCanvas");
    const sigModalPlaceholder = document.getElementById("sigModalPlaceholder");
    const signaturePreviewImg = document.getElementById("signaturePreviewImg");
    const sigEmptyPrompt = document.getElementById("sigEmptyPrompt");
    const sigDataInput = document.getElementById("signatureDataInput");
    const sigStatusBadge = document.getElementById("sigStatusBadge");
    const sigDateText = document.getElementById("sigDateText");

    let isDrawing = false;
    let hasDrawn = false;
    let sigCtx = null;
    let currentDpr = 1;

    if (sigCanvas) {
      sigCtx = sigCanvas.getContext("2d");

      function initCanvasSize() {
        const rect = sigCanvas.getBoundingClientRect();
        currentDpr = window.devicePixelRatio || 1;
        if (rect.width > 0 && rect.height > 0) {
          sigCanvas.width = Math.round(rect.width * currentDpr);
          sigCanvas.height = Math.round(rect.height * currentDpr);
          sigCtx.strokeStyle = "#000080"; // Navy blue ink
          sigCtx.lineWidth = 2.4 * currentDpr;
          sigCtx.lineCap = "round";
          sigCtx.lineJoin = "round";
        }
      }

      function openModal() {
        if (isInspectionClosed) return;
        if (signModal) {
          signModal.style.display = "flex";
          initCanvasSize();
          hasDrawn = false;
          if (sigModalPlaceholder) sigModalPlaceholder.style.display = "block";
          setTimeout(initCanvasSize, 50);
          setTimeout(initCanvasSize, 150);
        }
      }

      function closeModal() {
        if (signModal) signModal.style.display = "none";
      }

      if (btnOpenSignModal) btnOpenSignModal.addEventListener("click", openModal);
      if (sigPreviewContainer) sigPreviewContainer.addEventListener("click", openModal);
      if (btnCloseSignModal) btnCloseSignModal.addEventListener("click", closeModal);
      if (btnCancelSignModal) btnCancelSignModal.addEventListener("click", closeModal);

      function getPos(e) {
        const rect = sigCanvas.getBoundingClientRect();
        let clientX = e.clientX;
        let clientY = e.clientY;
        if (e.touches && e.touches.length > 0) {
          clientX = e.touches[0].clientX;
          clientY = e.touches[0].clientY;
        } else if (e.changedTouches && e.changedTouches.length > 0) {
          clientX = e.changedTouches[0].clientX;
          clientY = e.changedTouches[0].clientY;
        }

        const scaleX = rect.width > 0 ? (sigCanvas.width / rect.width) : 1;
        const scaleY = rect.height > 0 ? (sigCanvas.height / rect.height) : 1;

        return {
          x: (clientX - rect.left) * scaleX,
          y: (clientY - rect.top) * scaleY,
        };
      }

      function startDraw(e) {
        isDrawing = true;
        hasDrawn = true;
        if (sigModalPlaceholder) sigModalPlaceholder.style.display = "none";
        const pos = getPos(e);
        sigCtx.beginPath();
        sigCtx.moveTo(pos.x, pos.y);
        e.preventDefault();
      }

      function draw(e) {
        if (!isDrawing) return;
        const pos = getPos(e);
        sigCtx.lineTo(pos.x, pos.y);
        sigCtx.stroke();
        e.preventDefault();
      }

      function endDraw(e) {
        if (!isDrawing) return;
        isDrawing = false;
      }

      sigCanvas.addEventListener("mousedown", startDraw);
      sigCanvas.addEventListener("mousemove", draw);
      window.addEventListener("mouseup", endDraw);

      sigCanvas.addEventListener("touchstart", startDraw, { passive: false });
      sigCanvas.addEventListener("touchmove", draw, { passive: false });
      window.addEventListener("touchend", endDraw);

      if (btnClearModalCanvas) {
        btnClearModalCanvas.addEventListener("click", function () {
          initCanvasSize();
          hasDrawn = false;
          if (sigModalPlaceholder) sigModalPlaceholder.style.display = "block";
        });
      }

      function exportSafePaddedCanvas(sourceCanvas) {
        const w = sourceCanvas.width;
        const h = sourceCanvas.height;
        const outCanvas = document.createElement("canvas");
        outCanvas.width = w;
        outCanvas.height = h;
        const outCtx = outCanvas.getContext("2d");
        
        // Scale content by 92% and center to guarantee zero edge cropping
        const scale = 0.92;
        const offX = (w * (1 - scale)) / 2;
        const offY = (h * (1 - scale)) / 2;
        outCtx.drawImage(sourceCanvas, offX, offY, w * scale, h * scale);
        return outCanvas.toDataURL("image/png");
      }

      if (btnSaveSignModal) {
        btnSaveSignModal.addEventListener("click", function () {
          if (!hasDrawn) {
            showCustomAlert(_t("Notice", "Notice"), _t("Please draw signature before confirming!", "Please draw signature before confirming!"));
            return;
          }
          const dataUrl = exportSafePaddedCanvas(sigCanvas);
          if (sigDataInput) sigDataInput.value = dataUrl;
          if (signaturePreviewImg) {
            signaturePreviewImg.src = dataUrl;
            signaturePreviewImg.style.display = "block";
          }
          if (sigEmptyPrompt) sigEmptyPrompt.style.display = "none";
          if (btnClearSignature) btnClearSignature.style.display = "inline-flex";
          if (sigStatusBadge) sigStatusBadge.style.display = "inline-block";
          if (sigDateText) sigDateText.innerText = _t("Just signed (not saved)", "Just signed (not saved)");
          closeModal();
          showToast(_t("Signature recorded! Click Save to complete.", "Signature recorded! Click Save to complete."), false);
        });
      }

      if (btnClearSignature) {
        btnClearSignature.addEventListener("click", function () {
          if (sigDataInput) sigDataInput.value = "CLEAR";
          if (signaturePreviewImg) {
            signaturePreviewImg.src = "";
            signaturePreviewImg.style.display = "none";
          }
          if (sigEmptyPrompt) sigEmptyPrompt.style.display = "block";
          if (btnClearSignature) btnClearSignature.style.display = "none";
          if (sigStatusBadge) sigStatusBadge.style.display = "none";
          showToast(_t("Signature cleared. Click Save to update.", "Signature cleared. Click Save to update."), false);
        });
      }
    }

    // ==========================================
    // 3-Month Revenue Table Engine
    // ==========================================
    const revenueTbody = document.getElementById("revenueTbody");
    const btnAddRevenueRow = document.getElementById("btnAddRevenueRow");
    const revenueEmptyState = document.getElementById("revenueEmptyState");

    function getDaysInMonth(year, month) {
      return new Date(year, month, 0).getDate();
    }

    function calculateRowAvg(row) {
      const monthSel = row.querySelector(".rev-month-sel");
      const yearSel = row.querySelector(".rev-year-sel");
      const revInp = row.querySelector(".rev-amount-input");
      const avgInp = row.querySelector(".rev-avg-input");
      if (!revInp || !avgInp) return;

      const revVal = parseFloat(revInp.value) || 0;
      const now = new Date();
      let y = now.getFullYear(), m = now.getMonth() + 1;
      if (yearSel && monthSel) {
        y = parseInt(yearSel.value) || now.getFullYear();
        m = parseInt(monthSel.value) || (now.getMonth() + 1);
      }
      const days = getDaysInMonth(y, m);
      if (days > 0 && revVal > 0) {
        avgInp.value = Math.round(revVal / days);
      } else {
        avgInp.value = "0";
      }
    }

    function bindRevenueRowEvents(row) {
      const monthSel = row.querySelector(".rev-month-sel");
      const yearSel = row.querySelector(".rev-year-sel");
      const revInp = row.querySelector(".rev-amount-input");
      const delBtn = row.querySelector(".btn-delete-rev-row");

      if (monthSel) monthSel.addEventListener("change", () => calculateRowAvg(row));
      if (yearSel) yearSel.addEventListener("change", () => calculateRowAvg(row));
      if (revInp) revInp.addEventListener("input", () => calculateRowAvg(row));

      if (delBtn) {
        delBtn.addEventListener("click", function () {
          row.remove();
          if (
            revenueTbody &&
            revenueTbody.children.length === 0 &&
            revenueEmptyState
          ) {
            revenueEmptyState.style.display = "block";
          }
        });
      }
    }

    if (revenueTbody) {
      revenueTbody
        .querySelectorAll(".revenue-row")
        .forEach(bindRevenueRowEvents);
    }

        function getMonthOptionsHtml(selectedMonth) {
      const existingSelect = document.querySelector(".rev-month-sel");
      if (existingSelect && existingSelect.options.length > 0) {
        let html = "";
        for (let i = 0; i < existingSelect.options.length; i++) {
          const opt = existingSelect.options[i];
          const isSel = (opt.value === selectedMonth) ? 'selected="selected"' : "";
          html += `<option value="${opt.value}" ${isSel}>${opt.text}</option>`;
        }
        return html;
      }
      let html = "";
      for (let i = 1; i <= 12; i++) {
        const val = String(i).padStart(2, "0");
        const isSel = (val === selectedMonth) ? 'selected="selected"' : "";
        html += `<option value="${val}" ${isSel}>${val}</option>`;
      }
      return html;
    }

    function getYearOptionsHtml(selectedYear) {
      const existingSelect = document.querySelector(".rev-year-sel");
      if (existingSelect && existingSelect.options.length > 0) {
        let html = "";
        for (let i = 0; i < existingSelect.options.length; i++) {
          const opt = existingSelect.options[i];
          const isSel = (opt.value === String(selectedYear)) ? 'selected="selected"' : "";
          html += `<option value="${opt.value}" ${isSel}>${opt.text}</option>`;
        }
        return html;
      }
      const curY = new Date().getFullYear();
      let html = "";
      for (let y = curY - 3; y <= curY + 2; y++) {
        const isSel = (String(y) === String(selectedYear || curY)) ? 'selected="selected"' : "";
        html += `<option value="${y}" ${isSel}>${y}</option>`;
      }
      return html;
    }

    const btnSyncPosApp = document.getElementById("btnSyncPosApp");
    if (btnSyncPosApp) {
      btnSyncPosApp.addEventListener("click", async function () {
        const origHtml = btnSyncPosApp.innerHTML;
        btnSyncPosApp.disabled = true;
        btnSyncPosApp.innerHTML = `<i class="fa fa-spinner fa-spin me-1"></i> ${_t("Syncing...", "Syncing...")}`;
        try {
          const res = await fetch(`/franchise/inspection/do/${inspectionId}/sync_posapp`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ jsonrpc: "2.0", params: {} })
          });
          const data = await res.json();
          if (data.result && data.result.success) {
            const fetchedLines = data.result.report_lines || [];
            if (revenueTbody) {
              revenueTbody.innerHTML = "";
              if (revenueEmptyState) revenueEmptyState.style.display = "none";
              
              fetchedLines.forEach((item) => {
                const tr = document.createElement("tr");
                tr.className = "revenue-row";
                tr.style.borderBottom = "1px solid #f1f5f9";
                tr.innerHTML = `
                  <td style="padding: 8px 10px;">
                    <div style="display: flex; gap: 4px; align-items: center;">
                      <select class="rev-month-sel note-input" style="padding: 6px 4px; font-size: 12px; font-weight: 600; min-width: 95px; background: #fff;">
                        ${getMonthOptionsHtml(item.month_val)}
                      </select>
                      <select class="rev-year-sel note-input" style="padding: 6px 4px; font-size: 12px; font-weight: 600; min-width: 68px; background: #fff;">
                        ${getYearOptionsHtml(item.year_val)}
                      </select>
                    </div>
                  </td>
                  <td style="padding: 8px 10px;">
                    <input type="number" step="any" class="rev-amount-input note-input" value="${item.revenue || 0}" style="padding: 6px 8px; font-size: 13px; width: 100%; font-weight: 600; text-align: right;" />
                  </td>
                  <td style="padding: 8px 10px;">
                    <input type="number" step="any" class="rev-avg-input note-input" value="${item.revenue_avg || 0}" style="padding: 6px 8px; font-size: 13px; width: 100%; background: #f8fafc; font-weight: 600; text-align: right;" />
                  </td>
                  <td style="padding: 8px 10px;">
                    <div style="display: flex; align-items: center; gap: 4px;">
                      <input type="number" step="any" class="rev-goods-input note-input" value="${item.percent_goods || 0}" style="padding: 6px 8px; font-size: 13px; width: 100%; font-weight: 600; text-align: right;" />
                      <span style="font-weight: 700; color: #64748b;">%</span>
                    </div>
                  </td>
                  <td style="padding: 8px 10px;">
                    <input type="number" step="1" class="rev-app-sale-input note-input" value="${item.total_app_sale || 0}" style="padding: 6px 8px; font-size: 13px; width: 100%; font-weight: 600; text-align: right;" />
                  </td>
                  <td style="padding: 8px 10px;">
                    <div style="display: flex; align-items: center; gap: 4px;">
                      <input type="number" step="any" class="rev-percent-input note-input" value="${item.percent_app_sale || 0}" style="padding: 6px 8px; font-size: 13px; width: 100%; font-weight: 600; text-align: right;" />
                      <span style="font-weight: 700; color: #64748b;">%</span>
                    </div>
                  </td>
                  <td style="padding: 8px 4px; text-align: center;">
                    <button type="button" class="btn btn-sm text-danger btn-delete-rev-row" style="background: transparent; border: none; font-size: 14px; cursor: pointer;" title="Delete Row">
                      <i class="fa fa-trash-can"></i>
                    </button>
                  </td>
                `;
                revenueTbody.appendChild(tr);
                bindRevenueRowEvents(tr);
              });
            }
            showToast(data.result.message || _t("Synced from PosApp successfully. Click Save to record.", "Synced from PosApp successfully. Click Save to record."), false);
          } else {
            showToast((data.result && data.result.error) || _t("PosApp sync error", "PosApp sync error"), true);
          }
        } catch (err) {
          showToast(_t("Connection error during PosApp sync", "Connection error during PosApp sync"), true);
        } finally {
          btnSyncPosApp.disabled = false;
          btnSyncPosApp.innerHTML = origHtml;
        }
      });
    }

    if (btnAddRevenueRow) {
      btnAddRevenueRow.addEventListener("click", function () {
        if (!revenueTbody) return;
        if (revenueEmptyState) revenueEmptyState.style.display = "none";

        // Default to current or previous month
        const now = new Date();
        const curMonthStr = now.toISOString().slice(0, 7);

        const tr = document.createElement("tr");
        tr.className = "revenue-row";
        tr.style.borderBottom = "1px solid #f1f5f9";
        tr.innerHTML = `
          <td style="padding: 8px 10px;">
            <div style="display: flex; gap: 4px; align-items: center;">
              <select class="rev-month-sel note-input" style="padding: 6px 4px; font-size: 12px; font-weight: 600; min-width: 95px; background: #fff;">
                ${getMonthOptionsHtml(curMonthStr.slice(5, 7))}
              </select>
              <select class="rev-year-sel note-input" style="padding: 6px 4px; font-size: 12px; font-weight: 600; min-width: 68px; background: #fff;">
                ${getYearOptionsHtml(curMonthStr.slice(0, 4))}
              </select>
            </div>
          </td>
          <td style="padding: 8px 10px;">
            <input type="number" step="any" class="rev-amount-input note-input" placeholder="0" style="padding: 6px 8px; font-size: 13px; width: 100%; font-weight: 600; text-align: right;" />
          </td>
          <td style="padding: 8px 10px;">
            <input type="number" step="any" class="rev-avg-input note-input" placeholder="0" style="padding: 6px 8px; font-size: 13px; width: 100%; background: #f8fafc; font-weight: 600; text-align: right;" />
          </td>
          <td style="padding: 8px 10px;">
            <div style="display: flex; align-items: center; gap: 4px;">
              <input type="number" step="any" class="rev-goods-input note-input" placeholder="0" style="padding: 6px 8px; font-size: 13px; width: 100%; font-weight: 600; text-align: right;" />
              <span style="font-weight: 700; color: #64748b;">%</span>
            </div>
          </td>
          <td style="padding: 8px 10px;">
            <input type="number" step="1" class="rev-app-sale-input note-input" placeholder="0" style="padding: 6px 8px; font-size: 13px; width: 100%; font-weight: 600; text-align: right;" />
          </td>
          <td style="padding: 8px 10px;">
            <div style="display: flex; align-items: center; gap: 4px;">
              <input type="number" step="any" class="rev-percent-input note-input" placeholder="0" style="padding: 6px 8px; font-size: 13px; width: 100%; font-weight: 600; text-align: right;" />
              <span style="font-weight: 700; color: #64748b;">%</span>
            </div>
          </td>
          <td style="padding: 8px 4px; text-align: center;">
            <button type="button" class="btn btn-sm text-danger btn-delete-rev-row" style="background: transparent; border: none; font-size: 14px; cursor: pointer;" title="Delete Row">
              <i class="fa fa-trash-can"></i>
            </button>
          </td>
        `;
        revenueTbody.appendChild(tr);
        bindRevenueRowEvents(tr);
      });
    }
  });
})();
