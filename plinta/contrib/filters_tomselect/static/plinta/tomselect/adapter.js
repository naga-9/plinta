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
        var control = new window.TomSelect(select, {
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
        return control;
    }

    if (!window.TomSelect) {
        // Vendored and registered before this, so the only way here is a
        // failed asset. Saying so beats a filter bar that silently does
        // nothing.
        console.warn('[plinta] Tom Select did not load; the native select stands.');
        return;
    }

    // A compiler, so a bar that arrives by fragment swap — which is how the
    // cascade redraws it — is enhanced the same as one that arrived with the
    // page. The destructor takes Tom Select's own markup down with the
    // select, rather than leaving a control that answers to nothing.
    up.compiler('select[data-plinta-tomselect]', function (select) {
        var control = enhance(select);
        return function () {
            if (control) {
                control.destroy();
            }
        };
    });
})();
