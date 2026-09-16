// Dragging a row into place, by SortableJS.
//
// The order is the DOM order: a browser posts repeated controls in the order
// they appear, so moving a row is the whole of reordering — nothing tracks
// an index and nothing has to be kept in step with anything. That is true of
// the column chooser and of the sort builder alike, which is why one
// compiler serves both.
//
// A vendor, for a reason neither list has on its own: the kanban component
// will drag between lists, on a touch screen, with a drop animation, and it
// should not be the second place in the project that reorders by drag. One
// library, every caller.
//
// The attribute names what in the list is a row; `data-plinta-sortable-handle`
// names what in a row is the grip. A list with no grip drags by the row.

(function () {
    'use strict';

    if (!window.Sortable) {
        // Vendored and loaded before this, so the only way here is a failed
        // asset. Saying so beats a list that silently will not move.
        console.warn('[plinta] SortableJS did not load; the lists stay put.');
        return;
    }

    up.compiler('[data-plinta-sortable]', function (list) {
        var sortable = new window.Sortable(list, {
            draggable: list.dataset.plintaSortable || undefined,
            handle: list.dataset.plintaSortableHandle || undefined,
            animation: 150
        });
        return function () {
            sortable.destroy();
        };
    });
})();
