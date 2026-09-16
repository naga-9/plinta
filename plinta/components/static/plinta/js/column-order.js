// Dragging a column into place.
//
// The order is the DOM order: a browser posts checkboxes in the order they
// appear, so moving a row is the whole of reordering — nothing tracks an index
// and nothing has to be kept in step with anything.
//
// Native drag and drop, no vendor: core carries none (ADR 0005), and this is
// one list.

(function () {
    'use strict';

    function itemOf(list, target) {
        var item = target && target.closest ? target.closest('li') : null;
        // A row of another list is not one of ours to move.
        return item && item.closest('[data-plinta-reorder]') === list ? item : null;
    }

    // One compiler per list: the listeners are the list's own, so they go
    // with it when the editor holding it is swapped out.
    up.compiler('[data-plinta-reorder]', function (list) {
        var dragged = null;

        list.addEventListener('dragstart', function (event) {
            var item = itemOf(list, event.target);
            if (!item) {
                return;
            }
            dragged = item;
            event.dataTransfer.effectAllowed = 'move';
            // Firefox will not start a drag without data set.
            event.dataTransfer.setData('text/plain', '');
            item.classList.add('is-dragging');
        });

        list.addEventListener('dragover', function (event) {
            var over = itemOf(list, event.target);
            if (!dragged || !over || over === dragged) {
                return;
            }
            event.preventDefault();
            // Above or below, by which half of the row the pointer is over —
            // so a row can be dropped at either end without a separate
            // target.
            var box = over.getBoundingClientRect();
            var after = event.clientY > box.top + box.height / 2;
            over.parentNode.insertBefore(dragged, after ? over.nextSibling : over);
        });

        list.addEventListener('dragend', function () {
            if (dragged) {
                dragged.classList.remove('is-dragging');
                dragged = null;
            }
        });
    });
})();
