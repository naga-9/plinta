// Which default a tick means.
//
// `is_default` is one field with two meanings: on a personal view it is the
// viewer's own default, on a shared one it is everybody's. Which it is
// follows who owns the row, so the help text follows the "everyone can see
// this" box beside it.
//
// Progressive: without this, both lines show, and both are true statements
// about the two cases. The script hides the one that does not apply.

(function () {
    'use strict';

    function label(form) {
        var shared = form.querySelector('[data-plinta-public]');
        var isShared = !!(shared && shared.checked);
        form.querySelectorAll('[data-plinta-default-scope]').forEach(function (line) {
            var wants = line.getAttribute('data-plinta-default-scope');
            line.hidden = wants !== (isShared ? 'shared' : 'personal');
        });
    }

    function wire(root) {
        (root || document)
            .querySelectorAll('[data-plinta-default-scope]')
            .forEach(function (line) {
                var form = line.closest('form');
                if (!form || form.dataset.plintaDefaultWired) {
                    return;
                }
                form.dataset.plintaDefaultWired = '1';
                form.addEventListener('change', function (event) {
                    if (event.target.matches('[data-plinta-public]')) {
                        label(form);
                    }
                });
                label(form);
            });
    }

    // The editor arrives in a dialog after the page has loaded, so the walk
    // at load time finds nothing. Listening for the *click* would be worse:
    // it runs before the answer does.
    document.addEventListener('plinta:content', function (event) {
        wire(event.detail && event.detail.root);
    });

    if (document.readyState === 'complete') {
        wire(document);
    } else {
        document.addEventListener('DOMContentLoaded', function () {
            wire(document);
        });
    }
})();
