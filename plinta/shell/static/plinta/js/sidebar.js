// Showing and hiding the menu, and remembering the choice.
//
// One button, two behaviours, because the sidebar is two different things:
//
//   wide   — a column in the grid. Collapsing gives the page its width back,
//            and the choice is remembered: somebody who works with the menu
//            shut does not want to shut it on every page.
//   narrow — a drawer over the page. It opens on demand and is *not*
//            remembered: a drawer that restored itself open would cover the
//            screen on arrival, which is the opposite of what it is for.
//
// Loaded as a classic script in <head> rather than a module, deliberately.
// A module is deferred, so the menu would paint open and then vanish — the
// collapse has to be stamped on the shell before the first paint.

(function () {
    'use strict';

    var KEY = 'plinta-sidebar-collapsed';
    var WIDE = '(min-width: 60.0625rem)';
    var COLLAPSED = 'pl-shell--collapsed';

    function wide() {
        return window.matchMedia(WIDE).matches;
    }

    function stored() {
        try {
            return localStorage.getItem(KEY) === '1';
        } catch (e) {
            // Private browsing, or site data blocked. The menu still works;
            // only the memory of the choice is lost.
            return false;
        }
    }

    function remember(collapsed) {
        try {
            localStorage.setItem(KEY, collapsed ? '1' : '0');
        } catch (e) {
            /* as above */
        }
    }

    // Before first paint. `document.documentElement` exists here; the shell
    // does not, so the class is parked on <html> and moved once the body is
    // parsed. Nothing is drawn in between.
    if (stored()) {
        document.documentElement.classList.add(COLLAPSED);
    }

    function shell() {
        return document.querySelector('.pl-shell');
    }

    function sidebar() {
        return document.querySelector('.pl-sidebar');
    }

    function open() {
        var element = sidebar();
        return wide()
            ? !(shell() && shell().classList.contains(COLLAPSED))
            : !!(element && element.classList.contains('is-open'));
    }

    function announce(buttons) {
        var showing = open();
        for (var i = 0; i < buttons.length; i++) {
            buttons[i].setAttribute('aria-expanded', showing ? 'true' : 'false');
        }
    }

    function toggle(buttons) {
        if (wide()) {
            var collapsed = shell().classList.toggle(COLLAPSED);
            remember(collapsed);
        } else {
            sidebar().classList.toggle('is-open');
        }
        announce(buttons);
    }

    function close(buttons) {
        if (!wide() && sidebar()) {
            sidebar().classList.remove('is-open');
            announce(buttons);
        }
    }

    function init() {
        var root = document.documentElement;
        var frame = shell();
        if (frame && root.classList.contains(COLLAPSED)) {
            root.classList.remove(COLLAPSED);
            frame.classList.add(COLLAPSED);
        }

        var buttons = document.querySelectorAll('[data-plinta-sidebar-toggle]');
        for (var i = 0; i < buttons.length; i++) {
            buttons[i].setAttribute('aria-controls', 'pl-sidebar');
            buttons[i].addEventListener('click', function () {
                toggle(buttons);
            });
        }
        announce(buttons);

        // Escape shuts the drawer, the way every other overlay behaves. It
        // does not collapse the wide sidebar: that is a layout preference,
        // not something to dismiss.
        document.addEventListener('keydown', function (event) {
            if (event.key === 'Escape') {
                close(buttons);
            }
        });

        // A tap outside the open drawer shuts it. Ignored on wide screens,
        // where the sidebar is part of the page rather than over it.
        document.addEventListener('click', function (event) {
            var element = sidebar();
            if (!element || wide() || !element.classList.contains('is-open')) {
                return;
            }
            if (element.contains(event.target)) {
                return;
            }
            if (event.target.closest('[data-plinta-sidebar-toggle]')) {
                return;  // its own handler already ran
            }
            close(buttons);
        });

        // Crossing the breakpoint leaves the drawer's class behind, where it
        // would do nothing until the window shrank again.
        window.matchMedia(WIDE).addEventListener('change', function () {
            if (sidebar()) {
                sidebar().classList.remove('is-open');
            }
            announce(buttons);
        });
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
