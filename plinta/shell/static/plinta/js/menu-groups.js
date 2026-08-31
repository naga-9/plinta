// Collapsing a menu group, and remembering it.
//
// Progressive enhancement: the markup is a button beside a list, both usable
// before this runs and if it never does. All this adds is the collapse and
// the memory of it.
//
// **The group holding the current page is always opened**, whatever was
// remembered. Collapsing a group and then following a link into it would
// otherwise hide where you are, which reads as the menu losing your place.

(function () {
    'use strict';

    var KEY = 'plinta-menu-collapsed';
    var COLLAPSED = 'is-collapsed';

    /** The groups shut last time, as a set of their keys. */
    function stored() {
        try {
            return new Set(JSON.parse(localStorage.getItem(KEY) || '[]'));
        } catch (e) {
            // Private browsing, blocked site data, or something that is not
            // JSON. Every group opens, which is the safe way to be wrong.
            return new Set();
        }
    }

    function remember(keys) {
        try {
            localStorage.setItem(KEY, JSON.stringify([...keys]));
        } catch (e) {
            /* the menu still collapses; only the memory is lost */
        }
    }

    function apply(group, collapsed) {
        group.classList.toggle(COLLAPSED, collapsed);
        var button = group.querySelector('[data-plinta-group-toggle]');
        if (button) {
            button.setAttribute('aria-expanded', collapsed ? 'false' : 'true');
        }
    }

    function init() {
        var shut = stored();
        var groups = document.querySelectorAll('[data-plinta-group]');

        groups.forEach(function (group) {
            var key = group.dataset.plintaGroup;
            // Where you are wins over what you remembered.
            var here = group.querySelector('[aria-current="page"]');
            apply(group, shut.has(key) && !here);
            if (here && shut.has(key)) {
                shut.delete(key);
                remember(shut);
            }

            var button = group.querySelector('[data-plinta-group-toggle]');
            if (!button) {
                return;
            }
            button.addEventListener('click', function () {
                var collapsed = !group.classList.contains(COLLAPSED);
                apply(group, collapsed);
                var keys = stored();
                if (collapsed) {
                    keys.add(key);
                } else {
                    keys.delete(key);
                }
                remember(keys);
            });
        });
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
