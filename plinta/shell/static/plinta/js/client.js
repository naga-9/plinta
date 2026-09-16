// One client for every component that fetches.
//
// Four widget files in v1 each re-implemented the same plumbing — between them
// nine fetch calls, fourteen catch blocks, four loading indicators and seven
// CSRF handlings, for one behaviour. This is that behaviour, written once.
//
// The split (§7.4):
//
//   the client   finds the mount, reads its payload, builds the request,
//                fetches, and owns loading and error
//   an adapter   turns rows and columns into a widget, and decides *when* to
//                ask for more
//
// `load()` is the hinge. The client owns the URL, the parameter names and the
// errors; the adapter owns the timing. A grid asks again for every page, sort
// and filter its viewer changes; a chart asks once and never again. Both get
// the same parameter building and the same error path, and neither is named
// here — a client that knows one widget is one every other widget works
// around.
//
// Mounting is an Unpoly compiler. A compiler runs on every fragment Unpoly
// inserts — the document at boot, a swapped card, a form fetched into a
// layer — so nothing has to know *when* markup arrived, and its destructor
// runs when the fragment leaves, so nothing has to know when it went.

(function () {
    'use strict';

    var plinta = (window.plinta = window.plinta || {});
    var adapters = {};

    /** Register the glue for one component type. Called by its own script. */
    plinta.registerAdapter = function (name, adapter) {
        if (adapters[name]) {
            console.warn('[plinta] adapter ' + name + ' registered twice');
        }
        adapters[name] = adapter;
    };

    /** The payload rendered beside a mount: config, and rows when inline. */
    function payload(mount) {
        var script = mount.querySelector('script[type="application/json"]');
        if (!script) {
            return {};
        }
        try {
            return JSON.parse(script.textContent) || {};
        } catch (e) {
            console.error('[plinta] a mount carried unreadable JSON', e);
            return {};
        }
    }

    function show(mount, className, message) {
        var box = document.createElement('div');
        box.className = className;
        box.textContent = message;
        mount.replaceChildren(box);
    }

    /**
     * Ask the server for this widget's rows.
     *
     * The one place that knows the parameter names, so an adapter never
     * spells `f.` or `-price` itself and every widget pages the same way.
     */
    function loader(mount, url) {
        var pending = null;

        return function load(params) {
            params = params || {};
            var query = new URLSearchParams();

            // The page's own filters travel first: a widget shows what the
            // screen is filtered to, not what it was filtered to on load.
            // Its own paging and sorting are the widget's, so those are
            // dropped and set below.
            new URLSearchParams(window.location.search).forEach(function (v, k) {
                if (k !== 'page' && k !== 'size' && k !== 'sort') {
                    query.append(k, v);
                }
            });

            if (params.page) {
                query.set('page', params.page);
            }
            if (params.size) {
                query.set('size', params.size);
            }
            if (params.sort && params.sort.length) {
                query.set('sort', params.sort.join(','));
            }
            Object.keys(params.filters || {}).forEach(function (name) {
                var value = params.filters[name];
                if (value !== '' && value !== null && value !== undefined) {
                    query.set('f.' + name, value);
                }
            });

            if (pending) {
                // The last request is the one that matters; an earlier reply
                // arriving late would overwrite it.
                pending.abort();
            }
            pending = new AbortController();
            mount.setAttribute('aria-busy', 'true');

            // The URL may already carry a query — the view the card was
            // drawn with — and the rest joins it.
            var joined = url + (url.indexOf('?') === -1 ? '?' : '&') + query.toString();
            return fetch(joined, {
                signal: pending.signal,
                headers: { 'X-Requested-With': 'XMLHttpRequest' },
                credentials: 'same-origin'
            }).then(function (response) {
                mount.removeAttribute('aria-busy');
                if (!response.ok) {
                    throw new Error('the server answered ' + response.status);
                }
                return response.json();
            }, function (error) {
                mount.removeAttribute('aria-busy');
                throw error;
            });
        };
    }

    /** The CSRF token Django set, for the write half. */
    function token() {
        var match = /(?:^|;\s*)csrftoken=([^;]*)/.exec(document.cookie);
        return match ? decodeURIComponent(match[1]) : '';
    }

    // And for every form Unpoly submits. Django's header, not Unpoly's
    // default one, and read from the cookie rather than a meta tag: a form
    // drawn without a request — the record form is — carries no token of
    // its own, and this is what lets it post anyway.
    up.protocol.config.csrfHeader = 'X-CSRFToken';
    up.protocol.config.csrfToken = token;

    /**
     * Send one write: a record, and the fields being written.
     *
     * The same shape whatever asked for it — a dragged card writing one
     * field, a cell losing focus, a submitted form writing several. An
     * adapter decides *when* a write has happened; what one looks like is
     * decided here, once.
     */
    function saver(mount, url) {
        return function save(record, values) {
            return fetch(url, {
                method: 'POST',
                credentials: 'same-origin',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': token(),
                    'X-Requested-With': 'XMLHttpRequest'
                },
                body: JSON.stringify({
                    record: record === undefined ? null : record,
                    values: values || {}
                })
            }).then(function (response) {
                return response.json().catch(function () {
                    return {};
                }).then(function (body) {
                    if (response.ok) {
                        return body;
                    }
                    // A rejection carries which fields were wrong and can be
                    // answered by changing them; a refusal cannot. An adapter
                    // needs to tell those apart to know whether to keep the
                    // edit on screen.
                    var error = new Error(
                        body.detail || 'the server answered ' + response.status
                    );
                    error.status = response.status;
                    error.refused = response.status === 403;
                    error.fields = body.errors || body.fields || null;
                    throw error;
                });
            });
        };
    }

    /**
     * What a relation column may be set to, for a picker that searches.
     *
     * Here and not in the adapter for the same reason `load` is: an adapter
     * that fetches has its own URL building and its own error path, and the
     * boundary test refuses one.
     */
    function lookup(url) {
        return function options(field, term) {
            if (!url) {
                return Promise.resolve([]);
            }
            return fetch(
                url + encodeURIComponent(field) + '/?q=' +
                    encodeURIComponent(term || ''),
                {
                    credentials: 'same-origin',
                    headers: { 'X-Requested-With': 'XMLHttpRequest' }
                }
            ).then(function (response) {
                if (!response.ok) {
                    throw new Error('the server answered ' + response.status);
                }
                return response.json();
            }).then(function (body) {
                return body.options || [];
            });
        };
    }

    /**
     * Send one JSON POST. For a script that is not a component.
     *
     * `saver` above is the *write pipeline's* shape — a record and the fields
     * being written — and most things that ask the server are that. Some are
     * not: the layout composer posts where cards sit, which is not a write to
     * anybody's data. They still may not call `fetch` themselves, because the
     * CSRF token and the error shape are what the boundary keeps in one place,
     * so they get this instead.
     */
    plinta.post = function (url, body) {
        return fetch(url, {
            method: 'POST',
            credentials: 'same-origin',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': token(),
                'X-Requested-With': 'XMLHttpRequest'
            },
            body: JSON.stringify(body || {})
        }).then(function (response) {
            return response.json().catch(function () {
                return {};
            }).then(function (payload) {
                if (response.ok) {
                    return payload;
                }
                var error = new Error(
                    payload.error || 'the server answered ' + response.status
                );
                error.status = response.status;
                error.refused = response.status === 403;
                throw error;
            });
        });
    };

    /**
     * Mount one widget, and say how to take it down.
     *
     * Returned to Unpoly as the fragment's destructor. An adapter that holds
     * a widget with its own teardown — a grid with listeners on `window`, a
     * chart with a resize observer — declares `destroy`, and gets back what
     * its `mount` returned. One that holds nothing declares nothing.
     */
    function mountOne(mount) {
        var name = mount.dataset.plintaMount;
        var adapter = adapters[name];
        if (!adapter) {
            // The component is installed and its adapter is not — a broken
            // asset, or a package half-installed. Saying so beats a blank
            // card, which reads as a feature that stopped working.
            show(mount, 'pl-alert pl-alert--danger', 'No adapter for ' + name + '.');
            return;
        }

        var body = payload(mount);
        var fetchRows = loader(mount, mount.dataset.plintaUrl || '');
        var sendWrite = saver(mount, mount.dataset.plintaWriteUrl || '');
        var askOptions = lookup(mount.dataset.plintaOptionsUrl || '');

        function fail(error) {
            if (error && error.name === 'AbortError') {
                return;
            }
            console.error('[plinta]', error);
            show(mount, 'pl-alert pl-alert--danger',
                'This could not be loaded. ' + (error && error.message));
        }

        var handle;
        try {
            handle = adapter.mount(mount, {
                config: body.config || {},
                columns: body.columns || null,
                rows: body.rows || null,
                page: body.page || null,
                load: function (params) {
                    return fetchRows(params).catch(function (error) {
                        fail(error);
                        throw error;
                    });
                },
                // No `fail` around this one: a rejected write belongs beside
                // the field that was rejected, which only the adapter knows
                // where to find. Replacing the widget with an alert would
                // throw away the edit the writer is still holding.
                save: sendWrite,
                options: askOptions,
                writable: mount.dataset.plintaWriteUrl ? true : false,
                //: Where one record's form is asked for, or blank. The client
                //: does not fetch it — a link opens it in a layer — so this
                //: is passed on rather than wrapped.
                formUrl: mount.dataset.plintaFormUrl || ""
            });
        } catch (error) {
            fail(error);
            return;
        }

        if (!adapter.destroy) {
            return;
        }
        return function () {
            adapter.destroy(mount, handle);
        };
    }

    // Registered before Unpoly boots, which a deferred script is: the boot
    // happens on DOMContentLoaded, after every deferred script — the
    // adapters included, which come after this one — has run. So the
    // ordering the old ready-state check had to reason about is the
    // browser's, and no longer this file's.
    up.compiler('[data-plinta-mount]', mountOne);
})();
