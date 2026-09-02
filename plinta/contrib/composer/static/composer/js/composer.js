// Dragging a dashboard's cards into place.
//
// No vendor. Core refuses a remote script — an install must work offline and
// under a strict CSP — so a grid library would have to be vendored into this
// package, and a vendored library decides what our markup looks like. The
// grid is twelve CSS columns and four integers per card; that is little
// enough to move ourselves.
//
// Off by default. The page renders its layout from custom properties with no
// JavaScript at all, so this only ever runs after somebody asks for it.

(function () {
    'use strict';

    var COLUMNS = 12;
    var GRID = '.pl-grid';
    var ITEM = '[data-plinta-placement]';

    var editing = false;
    var drag = null;
    var endpoint = '';

    function grid() {
        return document.querySelector(GRID);
    }

    function cell(container) {
        // What one column and one row measure right now, read from the
        // rendered grid rather than from a constant — the page is responsive
        // and the CSS owns the answer.
        var box = container.getBoundingClientRect();
        var styles = getComputedStyle(container);
        var gap = parseFloat(styles.rowGap) || 0;
        var rowHeight = parseFloat(styles.gridAutoRows) || 40;
        return {
            width: (box.width + gap) / COLUMNS,
            height: rowHeight + gap,
            left: box.left,
            top: box.top
        };
    }

    function positionOf(item) {
        var styles = item.style;
        return {
            column: parseInt(styles.getPropertyValue('--col'), 10) || 0,
            row: parseInt(styles.getPropertyValue('--row'), 10) || 0,
            width: parseInt(styles.getPropertyValue('--w'), 10) || 1,
            height: parseInt(styles.getPropertyValue('--h'), 10) || 1
        };
    }

    function place(item, at) {
        item.style.setProperty('--col', at.column);
        item.style.setProperty('--row', at.row);
        item.style.setProperty('--w', at.width);
        item.style.setProperty('--h', at.height);
    }

    function clamp(value, low, high) {
        return Math.max(low, Math.min(high, value));
    }

    document.addEventListener('pointerdown', function (event) {
        if (!editing) {
            return;
        }
        var item = event.target.closest(ITEM);
        if (!item) {
            return;
        }
        // A card's own controls keep working while the layout is open: a
        // drag that starts on a link is a click somebody meant.
        if (event.target.closest('a, button, input, select, textarea')) {
            return;
        }
        var resizing = !!event.target.closest('[data-plinta-resize]');
        drag = {
            item: item,
            resizing: resizing,
            startX: event.clientX,
            startY: event.clientY,
            from: positionOf(item)
        };
        item.classList.add('is-moving');
        item.setPointerCapture(event.pointerId);
        event.preventDefault();
    });

    document.addEventListener('pointermove', function (event) {
        if (!drag) {
            return;
        }
        var size = cell(grid());
        var dx = Math.round((event.clientX - drag.startX) / size.width);
        var dy = Math.round((event.clientY - drag.startY) / size.height);
        var from = drag.from;

        if (drag.resizing) {
            place(drag.item, {
                column: from.column,
                row: from.row,
                width: clamp(from.width + dx, 1, COLUMNS - from.column),
                height: Math.max(1, from.height + dy)
            });
        } else {
            place(drag.item, {
                column: clamp(from.column + dx, 0, COLUMNS - from.width),
                row: Math.max(0, from.row + dy),
                width: from.width,
                height: from.height
            });
        }
    });

    document.addEventListener('pointerup', function () {
        if (!drag) {
            return;
        }
        var item = drag.item;
        var from = drag.from;
        var to = positionOf(item);
        item.classList.remove('is-moving');
        drag = null;

        var same = from.column === to.column && from.row === to.row
            && from.width === to.width && from.height === to.height;
        if (same) {
            return;  // a click, or a drag that ended where it started
        }
        save(item, to);
    });

    function save(item, to) {
        var body = {};
        body[item.dataset.plintaPlacement] = to;

        // Through the client, never `fetch` directly. The CSRF token and the
        // error shape live in one place, and this script is not special
        // enough to keep its own copies of them.
        window.plinta.post(endpoint, body).catch(function () {
            // The server is the authority on where a card may go, so a
            // refusal puts it back rather than leaving the screen showing
            // something the database does not say.
            window.location.reload();
        });
    }

    document.addEventListener('click', function (event) {
        var toggle = event.target.closest('[data-plinta-compose]');
        if (!toggle) {
            return;
        }
        event.preventDefault();
        // Handed over by the template. A page's address carries a decorative
        // slug, so deriving this from the pathname is a 404 (§9.0).
        endpoint = toggle.dataset.plintaCompose;
        editing = !editing;
        document.body.classList.toggle('pl-composing', editing);
        toggle.setAttribute('aria-pressed', editing ? 'true' : 'false');
        toggle.textContent = editing ? 'Done' : 'Edit layout';

        // The resize corner exists only while editing: it is a control, and a
        // control nobody can use should not be on the page.
        document.querySelectorAll(ITEM).forEach(function (item) {
            var handle = item.querySelector('[data-plinta-resize]');
            if (editing && !handle) {
                handle = document.createElement('span');
                handle.setAttribute('data-plinta-resize', '');
                handle.className = 'pl-resize';
                handle.title = 'Drag to resize';
                item.appendChild(handle);
            } else if (!editing && handle) {
                handle.remove();
            }
        });
    });
}());
