// Sorting by one column or several: adding a row, and taking one away.
//
// Rows are read in the order they appear — a browser posts repeated controls
// in document order — so moving a row is the priority and there is no number
// to keep in step with anything. The moving itself is `sortable.js`; this is
// the add and remove buttons, which were never the drag.

(function () {
    'use strict';

    // One compiler per builder, wherever it is drawn — a layer or a plain
    // page. The listener is the builder's own, so it leaves with it.
    up.compiler('[data-plinta-sort]', function (builder) {
        builder.addEventListener('click', function (event) {
            var add = event.target.closest('[data-plinta-sort-add]');
            if (add) {
                var template = builder.querySelector('[data-plinta-sort-template]');
                builder.insertBefore(
                    template.content.cloneNode(true), template
                );
                return;
            }

            var remove = event.target.closest('[data-plinta-sort-remove]');
            if (remove) {
                // The last row may go: sorting by nothing is a real answer,
                // and the table then falls back to its own ordering.
                remove.closest('.pl-sort__row').remove();
            }
        });
    });
}());
