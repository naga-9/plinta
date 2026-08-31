// A multi-select drawn as removable chips.
//
// Progressive enhancement over a real `<select multiple>`: the select is what
// the form submits, and this only changes how it looks and how it is operated.
// With JavaScript off, or before this runs, the native control is there and
// works — which is why the markup is a select rather than a div this has to
// fill in.
//
// No vendor. Searching the *server* as you type needs an endpoint to search
// against, and that is what `contrib.filters_tomselect` is for.

(function () {
    'use strict';

    var ATTRIBUTE = 'data-plinta-tags';

    function labelOf(option) {
        return option.textContent.trim();
    }

    /** Draw the chips for whatever is selected, and the input beside them. */
    function paint(box, select, input) {
        // Only the chips. Clearing everything that is not the input would take
        // the menu with it, since the menu lives in the same box.
        box.querySelectorAll('.pl-tags__chip').forEach(function (chip) {
            chip.remove();
        });
        var chosen = Array.prototype.filter.call(select.options, function (o) {
            return o.selected;
        });
        chosen.forEach(function (option) {
            var chip = document.createElement('span');
            // Its own hook as well as the style pack's chip class, so removing
            // chips never depends on what a pack renamed them to.
            chip.className = 'pl-tags__chip ' + (box.dataset.chipClass || 'pl-chip');
            chip.textContent = labelOf(option);

            var remove = document.createElement('button');
            remove.type = 'button';
            remove.className = 'pl-tags__remove';
            // The chip already carries the label, so the button must say what
            // it does rather than repeat it — "Remove" alone, read out of
            // order, is a list of identical buttons.
            remove.setAttribute('aria-label', 'Remove ' + labelOf(option));
            remove.textContent = '×';
            remove.addEventListener('click', function () {
                option.selected = false;
                select.dispatchEvent(new Event('change', { bubbles: true }));
                input.focus();
            });

            chip.appendChild(remove);
            box.insertBefore(chip, input);
        });
        input.placeholder = chosen.length ? '' : (box.dataset.placeholder || 'Add…');
    }

    /** The options not already chosen, matching what has been typed. */
    function matches(select, typed) {
        var needle = typed.trim().toLowerCase();
        return Array.prototype.filter.call(select.options, function (o) {
            return !o.selected && o.value &&
                (!needle || labelOf(o).toLowerCase().indexOf(needle) !== -1);
        });
    }

    function enhance(select) {
        if (select.dataset.plintaTagsReady) {
            return;
        }
        select.dataset.plintaTagsReady = '1';

        var box = document.createElement('div');
        box.className = 'pl-tags';
        box.dataset.chipClass = select.dataset.chipClass || 'pl-chip';
        box.dataset.placeholder = select.dataset.placeholder || 'Add…';

        var input = document.createElement('input');
        input.type = 'text';
        input.className = 'pl-tags__input';
        input.setAttribute('role', 'combobox');
        input.setAttribute('aria-expanded', 'false');
        input.setAttribute('aria-autocomplete', 'list');
        if (select.id) {
            // The <label> points at the select; move it to what is focusable.
            var label = document.querySelector('label[for="' + select.id + '"]');
            input.id = select.id + '-tags';
            if (label) {
                label.setAttribute('for', input.id);
            }
        }

        var list = document.createElement('ul');
        list.className = 'pl-tags__menu';
        list.hidden = true;
        list.setAttribute('role', 'listbox');

        box.appendChild(input);
        select.parentNode.insertBefore(box, select);
        box.appendChild(list);

        // Kept in the DOM and out of the way: it is still what submits, and a
        // display:none control is skipped by some browsers' form handling.
        select.classList.add('pl-visually-hidden');
        select.setAttribute('tabindex', '-1');
        select.setAttribute('aria-hidden', 'true');

        function close() {
            list.hidden = true;
            input.setAttribute('aria-expanded', 'false');
        }

        function open() {
            var found = matches(select, input.value);
            list.replaceChildren();
            found.forEach(function (option) {
                var item = document.createElement('li');
                item.className = 'pl-tags__option';
                item.setAttribute('role', 'option');
                item.textContent = labelOf(option);
                item.addEventListener('mousedown', function (event) {
                    // mousedown, not click: blur would close the menu first.
                    event.preventDefault();
                    option.selected = true;
                    input.value = '';
                    select.dispatchEvent(new Event('change', { bubbles: true }));
                });
                list.appendChild(item);
            });
            list.hidden = found.length === 0;
            input.setAttribute('aria-expanded', String(!list.hidden));
        }

        select.addEventListener('change', function () {
            paint(box, select, input);
            open();
        });

        // The cascade replaced our options. Redraw from whatever is there now
        // rather than from what we remember — it may have gone.
        select.addEventListener('plinta:options', function () {
            paint(box, select, input);
            if (document.activeElement === input) {
                open();
            }
        });
        input.addEventListener('input', open);
        input.addEventListener('focus', open);
        input.addEventListener('blur', close);

        input.addEventListener('keydown', function (event) {
            if (event.key === 'Escape') {
                close();
                return;
            }
            // Backspace on an empty box removes the last chip, the way every
            // token field behaves.
            if (event.key === 'Backspace' && input.value === '') {
                var chosen = Array.prototype.filter.call(select.options, function (o) {
                    return o.selected;
                });
                if (chosen.length) {
                    chosen[chosen.length - 1].selected = false;
                    select.dispatchEvent(new Event('change', { bubbles: true }));
                }
                return;
            }
            if (event.key === 'Enter') {
                var first = list.querySelector('.pl-tags__option');
                if (first && !list.hidden) {
                    // Enter picks the first match; without this it submits the
                    // form with whatever was typed and nothing chosen.
                    event.preventDefault();
                    first.dispatchEvent(new MouseEvent('mousedown'));
                }
            }
        });

        paint(box, select, input);
    }

    function init() {
        document.querySelectorAll('select[' + ATTRIBUTE + ']').forEach(enhance);
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
