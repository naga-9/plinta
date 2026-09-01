// The form component's glue.
//
// Reads the controls back out of the DOM, sends them through the client, and
// puts the answer beside the field it belongs to. It never builds a request:
// `ctx.save` owns the URL, the CSRF token and the error path, the same as for
// a dragged card or an edited cell.

(function () {
    'use strict';

    if (!window.plinta) {
        console.warn('[plinta] the client did not load.');
        return;
    }

    /** One control's value, in the shape the field holds. */
    function valueOf(input) {
        var kind = input.dataset.kind;
        if (kind === 'boolean') {
            return input.checked;
        }
        if (kind === 'relations') {
            return Array.prototype.filter
                .call(input.options, function (option) {
                    return option.selected;
                })
                .map(function (option) {
                    return Number(option.value);
                });
        }
        if (input.value === '') {
            // Told apart from "unset": a cleared box means null, and a number
            // box holding nothing is not the number zero.
            return null;
        }
        if (kind === 'number' || kind === 'relation') {
            return Number(input.value);
        }
        return input.value;
    }

    function controls(form) {
        return form.querySelectorAll('[data-kind]');
    }

    function clearErrors(form) {
        form.querySelectorAll('[data-plinta-error]').forEach(function (box) {
            box.textContent = '';
            box.hidden = true;
        });
        form.querySelectorAll('.pl-field').forEach(function (field) {
            field.classList.remove('is-invalid');
        });
    }

    /** Put each message beside the control it is about. */
    function showErrors(form, fields, fallback) {
        var placed = false;
        Object.keys(fields || {}).forEach(function (name) {
            var field = form.querySelector('[data-plinta-field="' + name + '"]');
            if (!field) {
                return;
            }
            var box = field.querySelector('[data-plinta-error]');
            box.textContent = [].concat(fields[name]).join(' ');
            box.hidden = false;
            field.classList.add('is-invalid');
            placed = true;
        });
        if (!placed && fallback) {
            // A refusal names no field, or names one that is not drawn. Said
            // once at the form rather than nowhere.
            var status = form.querySelector('[data-plinta-status]');
            status.textContent = fallback;
            status.hidden = false;
        }
    }

    function say(form, text, saved) {
        var status = form.querySelector('[data-plinta-status]');
        status.textContent = text;
        status.hidden = !text;
        status.classList.toggle('pl-form__status--saved', !!saved);
    }

    window.plinta.registerAdapter('form_plinta', {
        mount: function (el, ctx) {
            var record = (ctx.config && ctx.config.record) || null;
            var button = el.querySelector('button[type="submit"]');

            el.addEventListener('submit', function (event) {
                // The submit is intercepted, not invented: the element is a
                // real form so Enter works and it is announced as one.
                event.preventDefault();
                clearErrors(el);
                say(el, '');

                var values = {};
                controls(el).forEach(function (input) {
                    values[input.name] = valueOf(input);
                });

                button.disabled = true;
                ctx.save(record, values)
                    .then(function (body) {
                        // A create becomes an edit: the next save is of the
                        // row this one made, not a second one.
                        record = body.record;
                        say(
                            el,
                            el.querySelector('[data-plinta-status]').dataset.savedText,
                            true
                        );
                    })
                    .catch(function (error) {
                        showErrors(el, error.fields, error.message);
                    })
                    .then(function () {
                        button.disabled = false;
                    });
            });
        }
    });
})();
