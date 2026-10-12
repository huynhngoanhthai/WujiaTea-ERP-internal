/* Wujia Portal — Công nợ & thanh toán.
 *
 * Hành vi (Figma không có tương tác nào khác):
 *   1. Bộ lọc tuần/kỳ: <select> phủ kín card → đổi là submit luôn, khỏi nút "Xem".
 *   2. Nút copy số tài khoản / nội dung chuyển khoản (màn 07 + modal PC), có phản hồi
 *      thành công/thất bại nhìn thấy được (WJ-DEBT-005).
 *   3. PC (STT10): mở/đóng modal "Thanh toán số còn lại" (open-pay / close-pay /
 *      click backdrop / phím Esc). Nút "PDF" là <button type="button"> không handler
 *      ⇒ no-op MVP (chưa có endpoint — đúng ghi chú BA).
 *
 * Vanilla + delegation trên document: trang render server-side, không có OWL
 * component nào ở đây, và cùng pattern với các script portal khác của Wujia.
 */
(function () {
    'use strict';

    document.addEventListener('change', function (ev) {
        var select = ev.target.closest ? ev.target.closest('[data-wj-debt="filter"]') : null;
        if (!select) {
            return;
        }
        var form = select.form;
        if (!form) {
            return;
        }
        // requestSubmit (KHÔNG phải submit): submit() bỏ qua listener 'submit' nên
        // wj_ajax_list.js không bắt được, đổi kỳ lại reload cả trang như cũ.
        if (form.requestSubmit) {
            form.requestSubmit();
        } else {
            form.submit();
        }
    });

    /* J-V5: câu hiển thị lấy từ `data-wj-msg-*` trên khối ngân hàng (dịch bằng .po);
       fallback tiếng Anh khi helper chưa nạp. */
    function copyMsg(el, key, fallback) {
        return window.wjMsg ? window.wjMsg(el, key, fallback) : fallback;
    }

    /* ---- Modal QR (PC): mở/đóng thuần bằng thuộc tính [hidden] ---- */
    function payModal() {
        return document.querySelector('[data-wj-debt-modal="pay"]');
    }
    function openModal() {
        var modal = payModal();
        if (modal) {
            modal.removeAttribute('hidden');
        }
    }
    function closeModal() {
        var modal = payModal();
        if (modal) {
            modal.setAttribute('hidden', 'hidden');
        }
    }

    document.addEventListener('click', function (ev) {
        if (!ev.target.closest) {
            return;
        }

        if (ev.target.closest('[data-wj-debt="open-pay"]')) {
            ev.preventDefault();
            openModal();
            return;
        }
        // Nút X / "Đóng", hoặc click ra nền tối (chính backdrop, không phải panel con).
        if (ev.target.closest('[data-wj-debt="close-pay"]') ||
            ev.target.matches('[data-wj-debt-modal="pay"]')) {
            ev.preventDefault();
            closeModal();
            return;
        }

        var btn = ev.target.closest('[data-wj-debt="copy"]');
        if (!btn) {
            return;
        }
        ev.preventDefault();
        var value = btn.getAttribute('data-wj-debt-value') || '';
        if (!value) {
            flash(btn, false, copyMsg(btn, 'copy-empty', 'Nothing to copy yet.'));
            return;
        }
        copyText(value).then(function (ok) {
            flash(btn, ok, ok ? copyMsg(btn, 'copied', 'Copied') :
                copyMsg(btn, 'copy-failed', "Couldn't copy — press and hold the value to copy it manually."));
        });
    });

    /* Phản hồi tại chỗ: đổi màu nút + chữ trong ô role="status" của chính block ngân
       hàng đang bấm (mobile hay modal PC). Trước đây thất bại là im lặng hoàn toàn. */
    function flash(btn, ok, message) {
        var block = btn.closest('.wj-debt-bank, .wj-debt-pc-bank');
        var msg = block ? block.querySelector('.wj-debt-copy-msg') : null;
        btn.classList.toggle('is-copied', ok);
        if (msg) {
            msg.textContent = message;
            msg.classList.toggle('is-error', !ok);
        }
        window.setTimeout(function () {
            btn.classList.remove('is-copied');
            if (msg) {
                msg.textContent = '';
                msg.classList.remove('is-error');
            }
        }, 2500);
    }

    document.addEventListener('keydown', function (ev) {
        if (ev.key === 'Escape') {
            var modal = payModal();
            if (modal && !modal.hasAttribute('hidden')) {
                closeModal();
            }
        }
    });

    /* navigator.clipboard chỉ có trên secure context; UAT hiện chạy http →
       fallback execCommand để nút vẫn dùng được. */
    function copyText(value) {
        if (!value) {
            return Promise.resolve(false);
        }
        if (navigator.clipboard && window.isSecureContext) {
            return navigator.clipboard.writeText(value).then(function () {
                return true;
            }).catch(function () {
                return legacyCopy(value);
            });
        }
        return Promise.resolve(legacyCopy(value));
    }

    function legacyCopy(value) {
        var ta = document.createElement('textarea');
        ta.value = value;
        ta.setAttribute('readonly', 'readonly');
        ta.style.position = 'fixed';
        ta.style.top = '0';
        ta.style.opacity = '0';
        document.body.appendChild(ta);
        ta.focus();
        ta.select();
        ta.setSelectionRange(0, value.length);   // iOS/Safari bỏ qua select() trần
        var ok = false;
        try {
            ok = document.execCommand('copy');
        } catch (err) {
            ok = false;
        }
        document.body.removeChild(ta);
        return ok;
    }
})();
