// Sorting by one column or several.
//
// Rows are read in the order they appear — a browser posts repeated controls
// in document order — so moving a row is the priority and there is no number
// to keep in step with anything.

(function () {
    'use strict';

    var BUILDER = '[data-plinta-sort]';

    function rowsIn(builder) {
        return builder.querySelectorAll('.pl-sort__row');
    }

    document.addEventListener('click', function (event) {
        var add = event.target.closest('[data-plinta-sort-add]');
        if (add) {
            var builder = add.closest(BUILDER);
            var template = builder.querySelector('[data-plinta-sort-template]');
            builder.insertBefore(
                template.content.cloneNode(true), template
            );
            return;
        }

        var remove = event.target.closest('[data-plinta-sort-remove]');
        if (remove) {
            // The last row may go: sorting by nothing is a real answer, and
            // the table then falls back to its own ordering.
            remove.closest('.pl-sort__row').remove();
        }
    });
}());
