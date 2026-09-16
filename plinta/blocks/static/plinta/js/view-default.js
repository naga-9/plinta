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

    // A compiler: the editor arrives in a layer after the page has loaded,
    // and a compiler runs on whatever Unpoly inserts, whenever that is.
    up.compiler('[data-plinta-default-scope]', function (line) {
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
})();
