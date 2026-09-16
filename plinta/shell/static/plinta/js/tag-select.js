// A multi-select drawn as removable chips, by Tom Select.
//
// Over a real `<select multiple>`: the select is what the form submits, and
// this only changes how it looks and how it is operated — which is why the
// markup is a select rather than a div this has to fill in, and why the
// server can redraw the bar and this can simply run again.
//
// The glue only. Tom Select owns the interaction; this owns which elements it
// is given and what it is told about them, which is the same split the
// component client and its adapters use (§7.4). The vendor earns its place
// because the hand-written chips it replaced were a lesser copy of it: the
// same select, the same chips, the same menu, without the keyboard handling
// or the search a long list needs.

(function () {
    'use strict';

    if (!window.TomSelect) {
        // Vendored and loaded before this, so the only way here is a failed
        // asset. Saying so beats a filter bar that silently does nothing.
        console.warn('[plinta] Tom Select did not load; the native select stands.');
        return;
    }

    function enhance(select) {
        return new window.TomSelect(select, {
            plugins: ['remove_button'],
            placeholder: select.dataset.placeholder || 'Add…',
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
            }
        });
    }

    // A compiler, so a bar that arrives by fragment swap — which is how the
    // cascade redraws it — is enhanced the same as one that arrived with the
    // page. The destructor takes Tom Select's own markup down with the
    // select, rather than leaving a control that answers to nothing.
    up.compiler('select[data-plinta-tags]', function (select) {
        var control = enhance(select);
        return function () {
            control.destroy();
        };
    });
})();
