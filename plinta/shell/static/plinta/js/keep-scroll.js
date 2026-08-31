// Stay where you were when a control reloads the page.
//
// Choosing a saved view halfway down a dashboard should not throw you back to
// the top: a browser scrolls a fresh navigation to the start, and a GET form
// is a fresh navigation however little changed.
//
// Only forms that ask for it. A filter bar's Apply is a deliberate "show me
// something else" and starting at the top is right there; switching one card's
// view is not.
//
// v1 hid the document and retried the scroll twenty times, because its blocks
// arrived by AJAX and the page grew after load. Ours are server-rendered and
// complete when they arrive, so one restore lands — and hiding the document
// risks leaving it hidden when the restore fails.

(function () {
    'use strict';

    var KEY = 'plinta-scroll';

    function remember() {
        try {
            sessionStorage.setItem(KEY, String(window.scrollY));
        } catch (e) {
            // Private browsing or blocked site data. The page still works;
            // it just starts at the top.
        }
    }

    function restore() {
        var saved;
        try {
            saved = sessionStorage.getItem(KEY);
            sessionStorage.removeItem(KEY);
        } catch (e) {
            return;
        }
        // Read once and cleared immediately, so a later ordinary navigation
        // does not inherit somebody else's position.
        if (saved !== null) {
            window.scrollTo(0, parseInt(saved, 10) || 0);
        }
    }

    function init() {
        document.addEventListener('submit', function (event) {
            if (event.target.closest('[data-plinta-keep-scroll]')) {
                remember();
            }
        });
        restore();
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
