// The dialog a card opens a form in.
//
// Core chrome, not a component's: a pencil on a table row, a button on a card
// header and — when there is one — a kanban card all open the same thing, and
// each of them owning a dialog is how three of them come to disagree.
//
// `<dialog>`, not a div: the browser already owns the backdrop, Escape, the
// focus trap and returning focus to whatever opened it. Reimplementing those
// is how a modal becomes unusable with a keyboard.

(function () {
    'use strict';

    // What a *trigger* carries, and deliberately not what a mount carries.
    // `closest` walks upwards, so if the two shared a name every click inside
    // a table whose mount knows a form URL would open one — including the
    // click that was opening a cell editor.
    var ATTRIBUTE = 'data-plinta-open-form';
    var dialog = null;

    function element() {
        if (dialog) {
            return dialog;
        }
        dialog = document.createElement('dialog');
        dialog.className = 'pl-modal';
        dialog.innerHTML =
            '<div class="pl-modal__body" data-plinta-modal-body></div>';
        // A click on the backdrop is a click on the dialog itself, since the
        // body covers everything inside it.
        dialog.addEventListener('click', function (event) {
            if (event.target === dialog) {
                dialog.close();
            }
        });
        document.body.appendChild(dialog);
        return dialog;
    }

    function show(html) {
        var box = element();
        box.querySelector('[data-plinta-modal-body]').innerHTML = html;
        if (!box.open) {
            box.showModal();
        }
        // The form arrived as markup, so nothing has mounted it: the client
        // only walks the document once, at load.
        if (window.plinta && window.plinta.mount) {
            window.plinta.mount(box);
        }
    }

    function open(url) {
        show('<p class="pl-modal__loading">Loading…</p>');
        fetch(url, {
            credentials: 'same-origin',
            headers: { 'X-Requested-With': 'XMLHttpRequest' }
        })
            .then(function (response) {
                if (!response.ok) {
                    throw new Error('the server answered ' + response.status);
                }
                return response.text();
            })
            .then(show)
            .catch(function (error) {
                console.error('[plinta]', error);
                show(
                    '<div class="pl-alert pl-alert--danger">' +
                        'This could not be opened. ' +
                        (error && error.message) +
                        '</div>'
                );
            });
    }

    // Delegated, because the thing that opens a form may not exist yet: a
    // table draws its own rows after the page has loaded.
    document.addEventListener('click', function (event) {
        var trigger = event.target.closest('[' + ATTRIBUTE + ']');
        if (!trigger) {
            return;
        }
        event.preventDefault();
        open(trigger.getAttribute(ATTRIBUTE));
    });

    window.plinta = window.plinta || {};
    window.plinta.openForm = open;
    window.plinta.closeModal = function () {
        if (dialog && dialog.open) {
            dialog.close();
        }
    };
})();
