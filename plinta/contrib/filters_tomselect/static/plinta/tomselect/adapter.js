// Hand each marked select to Tom Select.
//
// The glue only. Tom Select owns the interaction; this owns which elements it
// is given and what it is told about them, which is the same split the
// component client and its adapters use (§7.4).

(function () {
    'use strict';

    function enhance(select) {
        if (select.tomselect) {
            return;
        }
        new window.TomSelect(select, {
            plugins: ['remove_button'],
            placeholder: select.dataset.placeholder || '',
            // The options are already in the DOM and already scoped to the
            // viewer. Searching them here is searching what they may see;
            // fetching more would need an endpoint under the same obligation.
            maxOptions: null,
            // The bar submits on Apply, so a stray Enter should not send the
            // form with the menu open.
            onKeyDown: function (event) {
                if (event.key === 'Enter' && this.isOpen) {
                    event.preventDefault();
                }
            },
        });
    }

    function init() {
        if (!window.TomSelect) {
            // Vendored and registered before this, so the only way here is a
            // failed asset. Saying so beats a filter bar that silently does
            // nothing.
            console.warn('[plinta] Tom Select did not load; the native select stands.');
            return;
        }
        document.querySelectorAll('select[data-plinta-tomselect]').forEach(enhance);
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
