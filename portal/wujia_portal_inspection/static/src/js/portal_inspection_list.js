/** @odoo-module **/

/**
 * SPA-like AJAX navigation for Portal Inspection List page.
 *
 * Intercepts tab clicks, search form submissions, reset buttons,
 * and pagination links to fetch content via AJAX and swap the DOM
 * without a full page reload. Supports browser history (back/forward).
 */
(function () {
    'use strict';

    // --------------- State ---------------
    var _currentTab = 'all';
    var _currentSearch = '';
    var _currentPage = 1;
    var _isFetching = false;

    // --------------- Helpers ---------------

    /** Read initial state from the current URL query params. */
    function readStateFromUrl() {
        var params = new URLSearchParams(window.location.search);
        _currentTab = params.get('tab') || 'all';
        _currentSearch = params.get('search') || '';
        _currentPage = parseInt(params.get('page'), 10) || 1;
    }

    /** Build query string from current state. */
    function buildQueryString(tab, search, page) {
        var parts = [];
        parts.push('tab=' + encodeURIComponent(tab || 'all'));
        if (search) {
            parts.push('search=' + encodeURIComponent(search));
        }
        if (page && page > 1) {
            parts.push('page=' + encodeURIComponent(page));
        }
        return parts.join('&');
    }

    // --------------- Core fetch + swap ---------------

    function fetchContent(tab, search, page, pushState) {
        if (_isFetching) return;
        _isFetching = true;

        tab = tab || 'all';
        search = search || '';
        page = parseInt(page, 10) || 1;
        if (page < 1) page = 1;

        var container = document.getElementById('wj-inspection-content');
        if (!container) {
            _isFetching = false;
            return;
        }

        // Fade out
        container.classList.add('wj-content-fading');

        var qs = buildQueryString(tab, search, page);
        var ajaxUrl = '/portal/inspection/ajax?' + qs;

        fetch(ajaxUrl, {
            headers: {
                'Accept': 'application/json',
            },
            credentials: 'same-origin',
        })
        .then(function (response) {
            if (!response.ok) {
                window.location.href = '/portal/inspection?' + qs;
                return null;
            }
            var ct = response.headers.get('content-type') || '';
            if (ct.indexOf('application/json') === -1) {
                window.location.href = '/portal/inspection?' + qs;
                return null;
            }
            return response.json();
        })
        .then(function (data) {
            if (!data) return;

            // Update state
            _currentTab = data.active_tab || tab;
            _currentSearch = data.search_q || '';
            _currentPage = data.page || 1;

            // Swap content
            container.innerHTML = data.html;

            // Re-bind events on new DOM
            bindEvents();

            // Push browser history
            if (pushState !== false) {
                var newQs = buildQueryString(_currentTab, _currentSearch, _currentPage);
                var newUrl = '/portal/inspection?' + newQs;
                window.history.pushState(
                    { tab: _currentTab, search: _currentSearch, page: _currentPage },
                    '',
                    newUrl
                );
            }

            // Fade in
            requestAnimationFrame(function () {
                container.classList.remove('wj-content-fading');
            });

            // Scroll content area into view smoothly
            container.scrollIntoView({ behavior: 'smooth', block: 'start' });

            _isFetching = false;
        })
        .catch(function () {
            window.location.href = '/portal/inspection?' + qs;
            _isFetching = false;
        });
    }

    // --------------- Event Binding ---------------

    function bindEvents() {
        // --- Tab clicks ---
        var tabs = document.querySelectorAll('.wj-ajax-tab');
        tabs.forEach(function (el) {
            if (el._wjBound) return;
            el._wjBound = true;
            el.addEventListener('click', function (e) {
                e.preventDefault();
                var tab = el.getAttribute('data-tab') || 'all';
                fetchContent(tab, _currentSearch, 1, true);
            });
        });

        // --- Search forms ---
        var searchForms = document.querySelectorAll('.wj-ajax-search-form');
        searchForms.forEach(function (form) {
            if (form._wjBound) return;
            form._wjBound = true;
            form.addEventListener('submit', function (e) {
                e.preventDefault();
                var input = form.querySelector('input[name="search"]');
                var tabInput = form.querySelector('input[name="tab"]');
                var q = input ? input.value.trim() : '';
                var tab = tabInput ? tabInput.value : _currentTab;
                fetchContent(tab, q, 1, true);
            });
        });

        // --- Reset buttons ---
        var resets = document.querySelectorAll('.wj-ajax-reset');
        resets.forEach(function (el) {
            if (el._wjBound) return;
            el._wjBound = true;
            el.addEventListener('click', function (e) {
                e.preventDefault();
                var tab = el.getAttribute('data-tab') || _currentTab;
                fetchContent(tab, '', 1, true);
            });
        });

        // --- Pagination links ---
        var pageLinks = document.querySelectorAll('.wj-ajax-page');
        pageLinks.forEach(function (el) {
            if (el._wjBound) return;
            el._wjBound = true;
            el.addEventListener('click', function (e) {
                e.preventDefault();
                if (el.classList.contains('is-disabled') || el.classList.contains('disabled')) return;
                var pg = parseInt(el.getAttribute('data-page'), 10) || 1;
                fetchContent(_currentTab, _currentSearch, pg, true);
            });
        });
    }

    // --------------- Browser History ---------------

    function onPopState(e) {
        if (e.state && e.state.tab !== undefined) {
            fetchContent(e.state.tab, e.state.search || '', e.state.page || 1, false);
        } else {
            readStateFromUrl();
            fetchContent(_currentTab, _currentSearch, _currentPage, false);
        }
    }

    // --------------- Init ---------------

    function init() {
        var container = document.getElementById('wj-inspection-content');
        if (!container) return;

        readStateFromUrl();

        window.history.replaceState(
            { tab: _currentTab, search: _currentSearch, page: _currentPage },
            '',
            window.location.href
        );

        bindEvents();
        window.addEventListener('popstate', onPopState);
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
