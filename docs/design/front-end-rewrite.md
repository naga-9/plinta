# The front-end rewrite: Unpoly, no-JS, and the hand-written scripts

A plan, not a decision record. Three changes that were discussed together
because they share one premise: **plinta is not deployed anywhere yet, so
nothing here needs a compatibility path.** Each part is a sequence of
commits, and the site works after every one.

What this document changes in `SPEC.md` when it lands is listed at the end.

## Contents

1. [Unpoly replaces the reload](#1-unpoly-replaces-the-reload)
2. [JavaScript-disabled stops being a supported configuration](#2-javascript-disabled-stops-being-a-supported-configuration)
3. [Libraries for the hand-written scripts](#3-libraries-for-the-hand-written-scripts)
4. [Open: `composer.js`](#4-open-composerjs)
5. [Spec changes](#5-spec-changes)

---

## 1. Unpoly replaces the reload

### Why

§7.12 decided that a filter change, a saved-view switch, a form save and a
workflow transition each reload the whole page. The argument was that
nothing server-rendered is lost. It was true and it was the wrong answer to
the second case: switching one card's view rebuilds every other card, whose
state was still meaningful. §7.12's last paragraph concedes this.

Unpoly fixes it without changing the server's shape. Every link stays a
link and every form stays a form — Unpoly intercepts, fetches the page the
link or form would have loaded, and swaps in the fragment it was told to
keep. A Django view that renders a page and redirects after a POST is
already an Unpoly endpoint.

Chosen over Datastar because plinta's screens are navigation and dialogs
more than they are client state, and Unpoly's layers, history and
compilers cover those directly. Datastar's server push is the one thing
given up; polling stands in until it matters.

### Ground rules

- **Every interaction has a URL and a form behind it.** Unpoly enhances;
  nothing becomes JavaScript-only. This is the discipline that made §11.2's
  server-rendered table right, kept as a discipline rather than as a
  guarantee (see part 2).
- **Vendored, never a CDN.** `unpoly.min.js` and `unpoly.min.css` in
  `plinta/shell/static/plinta/vendor/`, served from `static/` (§17).
- **Opt-in at first.** `up.link.config.followSelectors` and
  `up.form.config.submitSelectors` start empty; attributes are added one
  screen at a time so each step is testable alone.

### Steps

Each is one commit. Order matters for 1–3; 4–8 are independent.

**Step 1 — vendor Unpoly with nothing changed.**
Add the two files, load the script in `base.html` before `client.js` as a
classic script (§7.5's ordering rule). Configure it to follow nothing.
All four suites green.

**Step 2 — compilers are the lifecycle seam.**
The one change everything else depends on.

- `client.js`: replace the `DOMContentLoaded` walk and `plinta.mount(root)`
  with `up.compiler('[data-plinta-mount]', mountOne)`. `mountOne` returns a
  destructor that calls the adapter's `destroy` if it has one.
- `tabulator/adapter.js` and `tomselect/adapter.js` gain `destroy`.
- `tag-select.js`, `column-order.js`, `sort-builder.js` each become a
  compiler on their own selector.
- Delete the `plinta:content` custom event and its listeners (`modal.js`,
  `view-default.js`, `tag-select.js`). Compilers run on every inserted
  fragment, which is what the event was for.
- Browser test: swap a fragment holding a mount; the widget re-initialises.

**Step 3 — ids on the fragments that will be targeted.**
`id="card-{{ slot.placement.pk }}"` on `pages/block.html`; `id="pl-grid"`
on the block grid and `id="pl-filters"` on the bar in `page.html`.
Optionally, in `page_view`: when `X-Up-Target` names one card, render only
that slot — one `render_block` instead of eight.

**Step 4 — saved-view picker.**
`view_picker.html`: `up-submit up-autosubmit up-target="#card-N"
up-history="false"`; drop `onchange`. Delete `keep-scroll.js` and its
`data-plinta-keep-scroll` attributes. Test: switching a view on card A
leaves card B's Tabulator page intact.

**Step 5 — dialogs become layers.**
Every `data-plinta-open-form` trigger →
`up-layer="new modal" up-accept-location="/pages/*"`. `view_editor.html`,
`form.html`, `filter_set_editor.html`, `manage_views.html` lose any
dialog-shaped wrapper and become plain templates. `_save_view` and
`page_filters` are unchanged: their redirect is what closes the layer.
`block_write` sets `X-Up-Accept-Layer` with the record id on success; its
existing 4xx response renders into the layer. Delete `modal.js`.
Test: open → validation error stays in the modal → save → modal closes →
card reloads.

**Step 6 — forms.**
`form.html` / `form_body.html`: `up-submit up-disable`, and `up-validate`
on fields the server can check alone. `block_form` / `block_write` gain an
`X-Up-Validate` branch that validates without saving.
`form_plinta` becomes a real form post; `block_write` accepts form-encoded
alongside JSON, both into the same pipeline. `form.js` shrinks to what the
JSON write shape still needs, or goes. `view-default.js` →
`up-switch` / `up-show-for`; delete it.

`saver()` in `client.js` **stays**: it is the write contract for adapters
that own their DOM (a Tabulator cell, a dragged kanban card) and have no
form to submit. The client owns the shape of a write; an adapter owns when
one happens (§8.11).

**Step 7 — filter bar and tabs.**
`filter_bar.html`: `up-submit up-target="#pl-grid, #pl-filters"`. History
stays on, so the URL still carries the filters. Cascade: `up-watch` on each
control targeting `#pl-filters`; the server already narrows options on
re-render. Delete `filter-cascade.js` and, if nothing else uses it, the
`filter_options` view. Tabs: `up-follow up-target="#pl-grid"`, and they may
now honestly carry `role="tab"`.

**Step 8 — everything else that redirects.**
`table_plinta` sort and page links: `up-follow up-target="#card-N"`.
`workflow/section.html`: `up-submit up-target` on the transition forms.
Notification actions: `up-submit up-target`; the bell:
`up-poll up-interval="30000"`. `composer.js`: `up.reload('#card-N')` on
refusal instead of `location.reload()`. Add-block in `page_composer`:
`up-submit up-target="#placements"`. Toasts: `up-hungry` on `#pl-toasts`.

**Step 9 — delete and clean.**
Gone: `modal.js`, `keep-scroll.js`, `view-default.js`,
`filter-cascade.js`, most of `form.js`, the `plinta:content` machinery, the
ready-state dance and `aria-busy` handling in `client.js` (Unpoly's
`up-loading` class covers it). `tests/test_import_boundary.py` allows
`up.*` in the client and keeps forbidding `fetch` outside it. Update the
skills that mention `data-plinta-open-form` or `plinta.mount`.

**Step 10 — verify.**
All suites. Browser suite gains: fragment swap remounts widgets; layer
accept closes and reloads; filter submit keeps sidebar and scroll state;
back button after a tab, a filter and a view switch lands where expected.

### Impact

| | Lines |
|---|---|
| JavaScript removed | ~575 of 1,911 (−30%) |
| Python touched | ~+25 (`X-Up-Target`, `X-Up-Validate`, `X-Up-Accept-Layer`) |
| Templates | ~+40 attributes, −20 dialog wrappers |
| Vendor added | Unpoly, ~50 KB JS + 10 KB CSS |

Steps 1–3 are a day and unlock the rest. 4–8 are an hour or two each.
9–10 a day.

---

## 2. JavaScript-disabled stops being a supported configuration

### Why

The spec makes two different claims that read as one. The first is a
discipline: the server is the authority, every screen is links and forms,
JavaScript changes *how* those happen and never *whether*. That is cheap,
it is why part 1 costs so little, and it stays.

The second is a guarantee: §11.2 says `table_plinta` "works with JavaScript
disabled", and `view_picker.html` carries a `<noscript>` button. The
guarantee was only ever true for the core table and the filter bar — every
interactive component needs JavaScript regardless — and a guarantee that
holds for a third of the product is not one. Nobody runs a dashboard with
JavaScript off.

### What changes

The whole of it, counted:

| | Where | Lines |
|---|---|---|
| Markup | the `<noscript>` button in `view_picker.html` | 1 |
| Comments | `view-default.js`, `tag-select.js`, `menu-groups.js`, `filter-cascade.js`, `tomselect/multiselect.html`, `composer/edit_layout.html` — sentences defending the no-JS path | ~10 |
| Tests | none run with JavaScript disabled | 0 |
| Spec | §11.2's sentence; the `view_picker` and `filter_bar` template comments | ~4 |

No second code path exists anywhere. `filter_options` serves the live
cascade, not a fallback; `onchange="this.form.submit()"` was the primary
mechanism, not a degraded one.

### The replacement rule

> Core renders every screen as HTML the server drew. Links navigate, forms
> submit, layout is CSS. JavaScript changes how those happen — in place,
> without a reload, with a widget — never whether they can. JS-disabled is
> not a supported configuration.

§12.4's "view mode is CSS grid with no JavaScript" is a performance
statement, not an accessibility one, and stays as written.

### Steps

One commit, alongside step 9 of part 1: remove the button, reword the
comments, amend §11.2.

---

## 3. Libraries for the hand-written scripts

### Why

Five scripts carry a comment saying "no vendor, because core carries none"
(ADR 0005). Part 1 puts a vendor in core, so that reason is gone and each
script is re-asked on its merits: is the library smaller than the problem?

| Script | Lines | Was avoiding | Decision |
|---|---|---|---|
| `modal.js` | 101 | — | **Unpoly layers** (part 1, step 5) |
| `tag-select.js` | 191 | Tom Select | **Tom Select to core** |
| `column-order.js` | 54 | SortableJS | **SortableJS to core** |
| `sort-builder.js` | 34 | SortableJS | **SortableJS to core** |
| `composer.js` | 178 | GridStack / interact.js | **open** — part 4 |

### Tom Select

`tag-select.js` is a lesser Tom Select: chips over a `<select multiple>`,
with the comment itself pointing at `contrib.filters_tomselect` for the
version that searches the server. §2.6 already lists Tom Select among
core's vendored libraries; ADR 0005's pass pushed it out to contrib. This
restores it.

Steps:
1. Move `tom-select.complete.min.js` and `tom-select.min.css` from
   `contrib/filters_tomselect/static/` to `shell/static/plinta/vendor/`.
2. Move `tomselect/adapter.js` into the shell as a compiler on
   `[data-plinta-tags]` — the selector `tag-select.js` owned — keeping the
   server-search behaviour behind `data-options-url`.
3. Move `tomselect/multiselect.html` over the core `filters/multiselect.html`.
4. Delete `tag-select.js`, delete `contrib.filters_tomselect`, remove its
   entry from §14 and the `enhances` table.

Net: −191 lines, −1 contrib package, +40 KB vendor in core.

### SortableJS

`column-order.js` and `sort-builder.js` are each a list where DOM order is
the answer. Both are small and native drag-and-drop suffices for a
settings editor on a desktop. SortableJS is taken anyway, for a reason
neither script has: **the kanban component will need drag between lists,
touch support and drop animation**, and it should not be the second
place in the project that reorders by drag. One library, three callers.

Steps:
1. Vendor `Sortable.min.js` (~40 KB) in `shell/static/plinta/vendor/`.
2. One compiler, `up.compiler('[data-plinta-sortable]', …)`, replacing both
   scripts: `new Sortable(el, {handle, animation: 150})`. The two templates
   swap `data-plinta-reorder` / `data-plinta-sort` for the one attribute.
   Sort-builder's per-row direction toggle stays as it is — it was never
   the drag.
3. Delete `column-order.js` and `sort-builder.js`.
4. When `contrib.components.kanban` lands, its adapter uses the same
   vendored file with `group` set, and `ctx.save` on drop.

Net: −88 lines now, +40 KB vendor; the kanban adapter is smaller later.

### The comment rewording

Where a script still says "no vendor, because core carries none", it now
says why *this* one earns none. That is the rule as it should have been
stated: a judgement per case, not a ban.

---

## 4. Open: `composer.js`

Not decided. The earlier objection was compressed to "GridStack decides
what our markup looks like", which is the conclusion without the argument.
The argument, for discussion:

**What `composer.js` does.** Pointer capture, cell arithmetic from the
rendered grid's computed style, live updates to four custom properties
(`--col`, `--row`, `--w`, `--h`), clamping, and one `plinta.post` on
release. 178 lines. The view mode draws the same four properties with no
script at all (§12.4).

**What GridStack wants.** It owns the container: its own grid engine, its
own item markup (`gs-x`, `gs-y`, `gs-w`, `gs-h` attributes; a
`grid-stack-item-content` wrapper), its own positioning (absolute
transforms, not CSS grid), its own CSS. The stored `column/row/width/height`
would still be the source of truth, but view mode and edit mode would
render the layout two different ways — CSS grid when reading, GridStack
when editing — and drift between the two is a bug nobody sees until a
card lands somewhere other than where it was dropped. It is also ~150 KB
for a screen that opens rarely.

**What interact.js wants.** Less: it does drag and resize on any element
and leaves the markup alone, so the four custom properties can stay as
the model. ~100 KB, and the snapping-to-grid and clamping — which is most
of `composer.js` — is still written by hand on top of it. It saves the
pointer-event plumbing (~50 lines) and adds touch and inertia.

**The case for keeping the script.** It is the only thing in the project
where the interesting state is on the client during a gesture; it is
already small; and the model it manipulates is the one the page renders
from, so there is nothing to keep in step.

**The case for a library.** Touch — a pointer-events drag works on a
phone but with no gesture feel — and the collision/float behaviour a real
dashboard editor has (drop a card and the others move out of the way),
which `composer.js` does not do and which is real work to add by hand.

If the second case matters, GridStack is the one that has it; interact.js
does not. So the real question is whether cards should push each other
around, not which library. To be talked through.

---

## 5. Spec changes

When the above lands, `SPEC.md` changes in these places:

| Section | Change |
|---|---|
| §2.6 | Core's front end: Unpoly, Tom Select, SortableJS, Bootstrap Icons. Remove Luxon and GridStack, which are not on disk. |
| §7.4 | The client's mount walk is a compiler; `plinta.mount` and `plinta:content` are gone. |
| §7.12 | Retitle: *A filter change updates the grid.* Keep the three-level table as the history of the decision; the answer is now the second row, with compilers making the cards inside survive. |
| §11.2 | Drop "works with JavaScript disabled". |
| §12.4 | Unchanged. |
| §14 | Remove `filters_tomselect`; the multiselect is core's. |
| ADR 0005 | Amend: core carries vendors for **shell chrome** — navigation, dialogs, a select control, a sortable list — and none for **components**. The upgrade-burden argument applies to components, which is where it came from. |
| New ADR | *JavaScript-disabled is not a supported configuration*, with part 2's rule as the text. |
