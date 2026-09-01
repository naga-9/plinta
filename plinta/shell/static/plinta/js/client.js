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

            return fetch(url + '?' + query.toString(), {
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

        function fail(error) {
            if (error && error.name === 'AbortError') {
                return;
            }
            console.error('[plinta]', error);
            show(mount, 'pl-alert pl-alert--danger',
                'This could not be loaded. ' + (error && error.message));
        }

        try {
            adapter.mount(mount, {
                config: body.config || {},
                columns: body.columns || null,
                rows: body.rows || null,
                page: body.page || null,
                load: function (params) {
                    return fetchRows(params).catch(function (error) {
                        fail(error);
                        throw error;
                    });
                }
            });
        } catch (error) {
            fail(error);
        }
    }

    function init() {
        document.querySelectorAll('[data-plinta-mount]').forEach(mountOne);
    }

    // Wait for DOMContentLoaded, and note the condition: a deferred script
    // executes at readyState **'interactive'**, not 'loading'. Testing for
    // 'loading' would therefore mount immediately — before the adapters,
    // which are deferred scripts that come after this one, had registered.
    // Every mount would then report "no adapter" for a component that has
    // one. The other shell scripts test 'loading' safely because none of them
    // depends on a later script.
    if (document.readyState === 'complete') {
        init();
    } else {
        document.addEventListener('DOMContentLoaded', init);
    }
})();
