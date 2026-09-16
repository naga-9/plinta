// Dragging a dashboard's cards into place, by GridStack.
//
// GridStack is used for the gesture and never for the resting layout. While
// the layout is open it owns the grid: cards a drag would land on slide out
// of the way and the ones below them follow, a placeholder shows where the
// drop will land, and every move it makes is posted — a collision that moves
// five cards is one POST. On *Done* the grid is reloaded from the server,
// which draws the same four integers with CSS grid the way it always has.
// Two renderers of one layout would drift; a gesture and a resting state
// do not.
//
// Off by default, and the vendor is fetched on the first click: a viewer who
// is never offered the control never downloads it.

(function () {
    'use strict';

    var COLUMNS = 12;
    var GRID = '#pl-grid';

    var grid = null;

    /** One of the grid's own tokens, in pixels. */
    function token(name) {
        var value = getComputedStyle(document.documentElement).getPropertyValue(name);
        return parseFloat(value) || 0;
    }

    /** GridStack, once. The URLs are the template's, not this file's. */
    function vendor(toggle) {
        if (window.GridStack) {
            return Promise.resolve();
        }
        var style = document.createElement('link');
        style.rel = 'stylesheet';
        style.href = toggle.dataset.plintaComposeStyle;
        document.head.appendChild(style);
        return new Promise(function (resolve, reject) {
            var script = document.createElement('script');
            script.src = toggle.dataset.plintaComposeScript;
            script.onload = resolve;
            script.onerror = function () {
                reject(new Error('GridStack did not load'));
            };
            document.head.appendChild(script);
        });
    }

    function save(endpoint, nodes) {
        var body = {};
        nodes.forEach(function (node) {
            body[node.el.dataset.plintaPlacement] = {
                column: node.x, row: node.y, width: node.w, height: node.h
            };
        });
        // Through the client, never `fetch` directly. The CSRF token and the
        // error shape live in one place, and this script is not special
        // enough to keep its own copies of them.
        return window.plinta.post(endpoint, body).catch(function () {
            // The server is the authority on where a card may go, so a
            // refusal shows what the database says rather than what the
            // screen hoped.
            stop();
        });
    }

    function start(toggle) {
        var container = document.querySelector(GRID);
        if (!container) {
            return;
        }
        // The geometry the CSS grid draws with, so the placeholder lands
        // where the card will be drawn. GridStack's row is cell plus gap,
        // with the gap taken back as the item's margin.
        var cell = token('--pl-grid-cell');
        var gap = token('--pl-grid-gap');
        grid = window.GridStack.init({
            column: COLUMNS,
            cellHeight: cell + gap,
            margin: gap,
            // Cards pack upward, so a gap left by a move closes and a card
            // dropped on another pushes it down rather than under.
            float: false,
            animate: true,
            draggable: {
                // A card's own controls keep working while the layout is
                // open, and a widget that drags for itself — a grid's
                // columns, a kanban's cards — is not the card being moved.
                cancel: 'a, button, input, select, textarea, [data-plinta-mount]'
            }
        }, container);
        grid.on('change', function (event, nodes) {
            save(toggle.dataset.plintaCompose, nodes || []);
        });
        document.body.classList.add('pl-composing');
        toggle.setAttribute('aria-pressed', 'true');
        toggle.textContent = 'Done';
    }

    function stop() {
        var toggle = document.querySelector('[data-plinta-compose]');
        if (grid) {
            // The element stays; the grid's hold on it goes. Then the server
            // draws it again, which is the only rendering of a layout at
            // rest.
            grid.destroy(false);
            grid = null;
        }
        document.body.classList.remove('pl-composing');
        if (toggle) {
            toggle.setAttribute('aria-pressed', 'false');
            toggle.textContent = 'Edit layout';
        }
        up.reload(GRID);
    }

    up.compiler('[data-plinta-compose]', function (toggle) {
        toggle.addEventListener('click', function () {
            if (grid) {
                stop();
                return;
            }
            vendor(toggle).then(function () {
                start(toggle);
            }, function (error) {
                console.error('[plinta]', error);
            });
        });
    });
})();
