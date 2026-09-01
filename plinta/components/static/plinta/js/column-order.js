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

    var LIST = '[data-plinta-reorder]';
    var dragged = null;

    function itemOf(target) {
        return target && target.closest ? target.closest('li') : null;
    }

    document.addEventListener('dragstart', function (event) {
        var item = itemOf(event.target);
        if (!item || !item.closest(LIST)) {
            return;
        }
        dragged = item;
        event.dataTransfer.effectAllowed = 'move';
        // Firefox will not start a drag without data set.
        event.dataTransfer.setData('text/plain', '');
        item.classList.add('is-dragging');
    });

    document.addEventListener('dragover', function (event) {
        var over = itemOf(event.target);
        if (!dragged || !over || over === dragged) {
            return;
        }
        if (over.closest(LIST) !== dragged.closest(LIST)) {
            return;  // a different list is not a drop target
        }
        event.preventDefault();
        // Above or below, by which half of the row the pointer is over — so a
        // row can be dropped at either end without a separate target.
        var box = over.getBoundingClientRect();
        var after = event.clientY > box.top + box.height / 2;
        over.parentNode.insertBefore(dragged, after ? over.nextSibling : over);
    });

    document.addEventListener('dragend', function () {
        if (dragged) {
            dragged.classList.remove('is-dragging');
            dragged = null;
        }
    });
})();
