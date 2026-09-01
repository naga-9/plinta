// Tabulator, told what the client fetched.
//
// The glue only. The client owns the URL, the parameter names and the errors;
// this owns *when* to ask and how to turn columns and rows into a grid.
//
// `ajaxRequestFunc` is the hinge §7.4 describes: Tabulator decides that page
// three is needed, and delegates the asking to load(). It never learns what a
// URL looks like, and the client never learns what a page of a grid is.

(function () {
    'use strict';

    if (!window.plinta || !window.Tabulator) {
        // Vendored and registered before this, so the only way here is an
        // asset that failed. Saying so beats a card that stays empty.
        console.warn('[plinta] Tabulator or the client did not load.');
        return;
    }

    //: The editor each kind of value gets. A text box for everything was
    //: what shipped first: a boolean cell reading "No" offered the word back
    //: and was told it was not a boolean, and a relation sent its label and
    //: raised out of the assignment. A relation gets a picker instead, built
    //: below, because what it may be set to is a list and not a string.
    var EDITORS = {
        string: 'input',
        number: 'number',
        boolean: 'tickCross',
        date: 'date',
        datetime: 'datetime',
        time: 'time',
        relation: 'list',
        // The same picker, taking more than one answer.
        relations: 'list'
    };

    /**
     * What a relation editor is given: the choices, or a way to ask for them.
     *
     * A short list came with the column and costs no round trip. A long one
     * could not, so the picker asks as the writer types — and asks the same
     * endpoint the write resolves against, so it cannot offer what the save
     * would refuse.
     */
    function pickerParams(column, ask) {
        var params = column.type === 'relations'
            // A many-to-many takes several, and clearing it is a write like
            // any other — so the list must be emptiable.
            ? { multiselect: true, clearable: true }
            : {};
        if (column.picker === 'list') {
            params.values = column.options || [];
            return params;
        }
        params.autocomplete = true;
        params.filterRemote = true;
        params.valuesLookup = function (cell, filterTerm) {
            return ask(column.name, filterTerm);
        };
        return params;
    }

    /** A plinta column as Tabulator wants it. */
    function toColumn(column, config, ask) {
        var editor = column.editable ? EDITORS[column.type] : false;
        return {
            // An editable column is read from `_edit`, which carries the
            // value the field holds. The cell shows the formatted one, and a
            // formatted value cannot be edited: an editor seeded with "£8.75"
            // sends "£8.75" back.
            field: editor ? '_edit.' + column.name : column.name,
            title: column.label,
            // Values arrive formatted, and a column declaring a field renderer
            // sends markup — so the cell is HTML either way. An editable
            // column reads its display value back off the row, since its own
            // field now points at the unformatted one.
            formatter: editor
                ? function (cell) {
                      return cell.getRow().getData()[column.name];
                  }
                : 'html',
            sorter: column.type === 'number' ? 'number' : 'string',
            headerSort: column.sortable !== false,
            // The block says whether headers filter at all; the column says
            // with what. A column the server will not filter on gets no box,
            // so no control is offered that does nothing.
            headerFilter:
                config.header_filters && column.filterable
                    ? column.filter || 'input'
                    : false,
            resizable: config.resizable !== false,
            // An editor only where the server said this viewer may write, so
            // a cell never offers an edit the write would refuse.
            editor: editor || false,
            editorParams: editor === 'list'
                ? pickerParams(column, ask)
                : undefined,
            width: column.width || undefined,
            hozAlign: column.align,
            variableHeight: !!column.wrap
        };
    }

    /**
     * The column's own name, whatever the grid reads it from.
     *
     * An editable column is bound to `_edit.<name>`, and the server knows
     * only `<name>` — so sorting or filtering one would name a column the
     * server has never heard of and be dropped without a word.
     */
    function plain(field) {
        return String(field || '').replace(/^_edit\./, '');
    }

    /** Tabulator's sort array, in the client's spelling. */
    function toSort(sorters) {
        return (sorters || []).map(function (s) {
            return (s.dir === 'desc' ? '-' : '') + plain(s.field);
        });
    }

    /** Tabulator's header filters, as plain column filters. */
    function toFilters(filters) {
        var out = {};
        (filters || []).forEach(function (f) {
            out[plain(f.field)] = f.value;
        });
        return out;
    }

    /** Put a cell back to what it was, and say why it would not stick. */
    function reject(cell, error) {
        cell.restoreOldValue();
        var message = (error.fields && error.fields[cell.getField()])
            ? error.fields[cell.getField()].join(' ')
            : error.message;
        cell.getElement().setAttribute('title', message);
        cell.getElement().classList.add('pl-tabulator__cell--rejected');
    }

    window.plinta.registerAdapter('table_tabulator', {
        mount: function (el, ctx) {
            var config = ctx.config || {};
            var local = !!ctx.rows;
            //: The column set the header is currently drawn from.
            var drawn = null;
            //: How a searching picker asks. The client owns the request; the
            //: adapter owns when one is needed.
            var ask = ctx.options;

            var options = {
                layout: 'fitColumns',
                placeholder: config.empty_text || 'No records',
                columns: (ctx.columns || []).map(function (c) {
                    return toColumn(c, config, ask);
                }),
                pagination: true,
                paginationSize: config.page_size || 50
            };

            if (local) {
                // Inline: the rows came with the page, so nothing is asked for
                // and Tabulator pages what it already has.
                options.data = ctx.rows;
                options.paginationMode = 'local';
            } else {
                options.paginationMode = 'remote';
                options.sortMode = 'remote';
                options.filterMode = 'remote';
                options.ajaxURL = 'plinta';  // unused; ajaxRequestFunc answers
                options.ajaxRequestFunc = function (url, cfg, params) {
                    return ctx
                        .load({
                            page: params.page,
                            size: params.size,
                            sort: toSort(params.sort),
                            filters: toFilters(params.filter)
                        })
                        .then(function (body) {
                            // Columns come every time, because they vary by
                            // viewer: a saved view changes them, so a grid
                            // holding its first set would show stale headers.
                            // Redrawn only when they actually changed, though
                            // — setColumns rebuilds the header, which discards
                            // the sort direction and the filter boxes with it.
                            // Doing it on every response means a second click
                            // on a column starts from ascending again and
                            // descending is unreachable.
                            var signature = JSON.stringify(body.columns || []);
                            if (body.columns && signature !== drawn) {
                                drawn = signature;
                                table.setColumns(
                                    body.columns.map(function (c) {
                                        return toColumn(c, config, ask);
                                    })
                                );
                            }
                            return { data: body.rows, last_page: body.page.count };
                        });
                };
            }

            var table = new window.Tabulator(el, options);

            if (ctx.writable) {
                // `on`, not an option: the callback was a constructor option
                // in Tabulator 4 and is an event from 5 onwards, and passing
                // it as an option is ignored without a word — the edit lands
                // in the grid, nothing is sent, and the row reverts on the
                // next fetch.
                //
                // One cell, one field, one row: the same write a dragged card
                // sends, which is why neither the endpoint nor the client has
                // any notion of a cell.
                table.on('cellEdited', function (cell) {
                    var values = {};
                    // `_edit.title` is where the grid keeps it; `title` is
                    // what the server calls it.
                    values[plain(cell.getField())] = cell.getValue();
                    ctx.save(cell.getRow().getData()._record, values)
                        .then(function (body) {
                            // The saved row, because the write may have moved
                            // a column the database derived.
                            cell.getRow().update(body.row);
                            cell.getElement().classList.remove(
                                'pl-tabulator__cell--rejected'
                            );
                        })
                        .catch(function (error) {
                            reject(cell, error);
                        });
                });
            }
        }
    });
})();
