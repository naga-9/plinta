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

    /** A plinta column as Tabulator wants it. */
    function toColumn(column, config) {
        return {
            field: column.name,
            title: column.label,
            // Values arrive formatted, and a column declaring a field renderer
            // sends markup — so the cell is HTML either way.
            formatter: 'html',
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
            width: column.width || undefined,
            hozAlign: column.align,
            variableHeight: !!column.wrap
        };
    }

    /** Tabulator's sort array, in the client's spelling. */
    function toSort(sorters) {
        return (sorters || []).map(function (s) {
            return (s.dir === 'desc' ? '-' : '') + s.field;
        });
    }

    /** Tabulator's header filters, as plain column filters. */
    function toFilters(filters) {
        var out = {};
        (filters || []).forEach(function (f) {
            out[f.field] = f.value;
        });
        return out;
    }

    window.plinta.registerAdapter('table_tabulator', {
        mount: function (el, ctx) {
            var config = ctx.config || {};
            var local = !!ctx.rows;
            //: The column set the header is currently drawn from.
            var drawn = null;

            var options = {
                layout: 'fitColumns',
                placeholder: config.empty_text || 'No records',
                columns: (ctx.columns || []).map(function (c) {
                    return toColumn(c, config);
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
                                        return toColumn(c, config);
                                    })
                                );
                            }
                            return { data: body.rows, last_page: body.page.count };
                        });
                };
            }

            var table = new window.Tabulator(el, options);
        }
    });
})();
