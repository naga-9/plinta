// Keep the filter bar's options in step with what is already chosen.
//
// The server does the same narrowing on a reload, so this changes *when* the
// cascade happens, not what it decides: choose a title, see which shops sold
// it, then choose one. Applying first in order to find out what to apply is
// the wrong way round.
//
// With JavaScript off, the cascade still happens — on Apply, as before. This
// is an enhancement to the moment, not the mechanism.

(function () {
    'use strict';

    var BAR = '.pl-filters';

    /** Every value currently in the bar, as the server's own parser wants it. */
    function chosen(form) {
        var params = new URLSearchParams();
        new FormData(form).forEach(function (value, key) {
            params.append(key, value);
        });
        return params;
    }

    /** Replace a select's options, keeping any selection still on offer. */
    function repopulate(select, options) {
        var was = new Set(
            Array.prototype.filter.call(select.options, function (o) {
                return o.selected;
            }).map(function (o) {
                return o.value;
            })
        );
        select.replaceChildren();
        options.forEach(function (pair) {
            var option = document.createElement('option');
            option.value = pair[0];
            option.textContent = pair[1];
            // A value no longer on offer is dropped rather than kept: it now
            // matches nothing, and leaving it selected would filter the page
            // to nothing while looking like a live choice.
            option.selected = was.has(pair[0]);
            select.appendChild(option);
        });
        // Whoever enhanced this select redraws itself. The cascade does not
        // know what a chip or a Tom Select is, and should not.
        select.dispatchEvent(new CustomEvent('plinta:options', { bubbles: true }));
    }

    function wire(form) {
        var url = form.dataset.optionsUrl;
        if (!url) {
            return;
        }
        var pending = null;

        function refresh(changed) {
            if (pending) {
                // The last choice is the one that matters; an earlier reply
                // arriving late would overwrite it.
                pending.abort();
            }
            pending = new AbortController();
            fetch(url + '?' + chosen(form).toString(), {
                signal: pending.signal,
                headers: { 'X-Requested-With': 'XMLHttpRequest' },
            })
                .then(function (response) {
                    return response.ok ? response.json() : null;
                })
                .then(function (data) {
                    if (!data) {
                        return;
                    }
                    form.querySelectorAll('select[name]').forEach(function (select) {
                        // Never the one just used. Narrowing a control by its
                        // own selection removes the alternatives from its own
                        // list, and the choice could not be changed.
                        if (select === changed) {
                            return;
                        }
                        if (data[select.name]) {
                            repopulate(select, data[select.name]);
                        }
                    });
                })
                .catch(function (error) {
                    if (error.name !== 'AbortError') {
                        // The bar still works: Apply asks the server, which
                        // narrows the same way.
                        console.warn('[plinta] could not refresh filter options', error);
                    }
                });
        }

        form.addEventListener('change', function (event) {
            if (event.target.matches('select[name]')) {
                refresh(event.target);
            }
        });
    }

    function init() {
        document.querySelectorAll(BAR).forEach(wire);
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
