/* ==========================================================================
   Wujia Franchise - Supervision Inspection Report Scripts
   ========================================================================== */

(function () {
  "use strict";

  function getFormattedPdfName() {
    const storeEl = document.querySelector(".store-name-sub");
    const dateEl = document.querySelector(".report-date-text strong");

    let reportPrefix = "Báo cáo Khảo sát Giám sát";
    let storeCode = "";
    if (storeEl) {
      const rawText = storeEl.innerText.trim();
      const match = rawText.match(/\((.*?)\)/);
      if (match && match[1] && match[1] !== "---") {
        storeCode = match[1].trim();
      } else {
        storeCode = rawText.replace(/\(.*?\)/g, "").trim();
      }
    }
    let dateStr = "";
    if (dateEl) {
      dateStr = dateEl.innerText.trim().replace(/\//g, "-");
    }
    if (storeCode && dateStr) {
      return `${reportPrefix} [${storeCode}] [${dateStr}]`;
    }
    return document.title || reportPrefix;
  }

  function applyDynamicTitle() {
    const formattedTitle = getFormattedPdfName();
    document.title = formattedTitle;
    try {
      if (window.parent && window.parent.document) {
        window.parent.document.title = formattedTitle;
      }
      if (window.top && window.top.document) {
        window.top.document.title = formattedTitle;
      }
    } catch (e) {}
  }

  function maskUrl() {
    try {
      if (window.history && window.history.replaceState) {
        window.history.replaceState({}, "", "/wujiateavn");
      }
    } catch (e) {}
  }

  function setupEvents() {
    applyDynamicTitle();

    window.addEventListener("beforeprint", function () {
      maskUrl();
      applyDynamicTitle();
    });

    const btnPrint = document.getElementById("btnPrintReport");
    if (btnPrint) {
      btnPrint.onclick = function () {
        maskUrl();
        applyDynamicTitle();
        window.print();
      };
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", setupEvents);
  } else {
    setupEvents();
  }
})();
