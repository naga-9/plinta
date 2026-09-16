# The front-end rewrite: Unpoly, no-JS, and the hand-written scripts

A plan, not a decision record. Three changes that were discussed together
because they share one premise: **plinta is not deployed anywhere yet, so
nothing here needs a compatibility path.** Each part is a sequence of
commits, and the site works after every one.

**Status.** Parts 1 and 2 have landed, one commit per step, with these
departures from the text below: the server closes a layer
(`X-Up-Accept-Layer` from `page_view` when asked from inside one) rather
than the opener matching a URL pattern, which a mounting prefix would have
broken; the cascade is `up-validate` on the bar rather than `up-watch` on
each control; the bell polls its own `bell/` URL rather than the page; the
tabs stay links, since `role="tab"` without arrow keys is a promise the
keyboard cannot keep; and the client keeps `aria-busy` on a mount while
its own fetch is in flight, which is not a request Unpoly sees. Parts 3
and 4 have landed too: `sort-builder.js` stays for its add and remove
buttons, which were never the drag; Tom Select has no server search to
keep, since no options endpoint ever existed; GridStack (13.3) is
fetched on the first *Edit layout* click from URLs the template hands
over, not registered as an asset, and two cards of a size swap rather
than push when one is dropped on the other, which is its collision rule.
The spec changes in part 5 are still to do, beyond the §12.4 and §17.3
lines that would otherwise have been false.

What this document changes in `SPEC.md` when it lands is listed at the end.

## Contents

1. [Unpoly replaces the reload](#1-unpoly-replaces-the-reload)
2. [JavaScript-disabled stops being a supported configuration](#2-javascript-disabled-stops-being-a-supported-configuration)
3. [Libraries for the hand-written scripts](#3-libraries-for-the-hand-written-scripts)
4. [GridStack for the composer, and the composer into core](#4-gridstack-for-the-composer-and-the-composer-into-core)
5. [Spec changes](#5-spec-changes)
6. [Later: other reductions, not yet decided](#6-later-other-reductions-not-yet-decided)

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
`up-poll up-interval="30000"`. `composer.js`: superseded by part 4. Add-block in `page_composer`:
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
| `composer.js` | 178 | GridStack | **GridStack, and the composer moves to core** — part 4 |

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

## 4. GridStack for the composer, and the composer into core

### Why GridStack

`composer.js` moves only the card being dragged. Drop it on another and
they overlap; the other does not react, and somebody has to move it by
hand. A dashboard editor is expected to do **collision handling**: while a
card is dragged, the cards it would land on slide out of the way and the
ones below them follow, so nothing overlaps; remove a card and the ones
below rise to fill the gap; a placeholder shows where the drop will land.
That is a couple of hundred lines of not-obvious code on a twelve-column
grid with variable-height cards, and it is the bulk of what GridStack is.
Page composition should feel like a product feature, so it is taken.

The earlier objection — GridStack renders the layout its own way, while
view mode renders the same four integers with CSS grid, and two renderers
drift — dissolves once every drop is followed by a server re-render. With
Unpoly that is `up.reload('#pl-grid')` on *Done*: GridStack is used for
the gesture and never for the resting layout. The geometry it uses during
the gesture reads from the same tokens the CSS grid does
(`--pl-grid-cell`, `--pl-grid-gap`), so the placeholder lands where the
card will be drawn.

### Why core

The composer was contrib for one reason: §12.4, *"Core owns the four
integers; dragging is contrib… Uninstall it and the screen still composes
pages, with numbers typed instead of dragged."* `composer.js` carries no
vendor and was pushed out anyway — the "no vendor in core" instinct had
become "no interaction in core", which is the discipline over-applied.
Nobody composes a dashboard by typing four integers; the numbers form is
a fixture, not a fallback. Composition is authoring, authoring is a core
chapter (§12), and the drag is the feature. It moves to core.

### Steps

1. Vendor `gridstack-all.js` and `gridstack.min.css` (~150 KB + 10 KB) in
   `plinta/shell/static/plinta/vendor/`. Registered on the *Edit layout*
   page action, which is permission-gated, so a viewer downloads nothing.
2. Move `contrib/composer/`: the page action into `plinta/pages/actions.py`,
   `edit_layout.html` into the shell's templates, `composer.js` into
   `plinta/shell/static/plinta/js/`. Delete the package and its `apps.py`.
3. Rewrite `composer.js` (178 → ~60). Gone: pointer capture, `cell()`
   arithmetic, `place()`, clamping, the resize-handle `<span>`. Stays: the
   toggle button and `save()` through `plinta.post`. New: on *Edit*,
   `GridStack.init({column: 12, cellHeight, margin, float: false}, '.pl-grid')`
   with `cellHeight` and `margin` read from the tokens; one `change`
   listener posting every node GridStack moved; on *Done*,
   `grid.destroy(false)` then `up.reload('#pl-grid')`.
4. `page.html`: each `.pl-grid__item` also carries `gs-x gs-y gs-w gs-h`
   from the same four integers, and the card takes GridStack's content
   class (or one CSS rule maps it).
5. CSS: GridStack's stylesheet, and a `.pl-composing .pl-grid` rule handing
   positioning to GridStack for the session. View-mode CSS is untouched.
6. Below the stacking breakpoint (`plinta.css` ~799), the *Edit layout*
   action is not offered; a one-column drag has no stored meaning.
7. `pages/composition.py::positions()` already takes a dict of many
   placements, so a collision that moves five cards is one POST. **No
   server change.** The numbers form in `page_composer` stays as the
   precise-adjust path.
8. `test_composer.py` becomes core tests: the action registers, it needs
   `change_pageblock`, it is absent on a detail page. Optional browser test:
   drag one card onto another and assert both moved server-side.

### Decisions to make while doing it

- **`float: false`** (cards pack upward, no gaps — Grafana's behaviour) or
  **`float: true`** (cards stay where dropped). `false` rewrites `row` on
  every drop, which `positions()` handles. Start with `false`.
- **Loading**: on the action's asset registration, or injected on the
  first *Edit* click (~8 lines) if 150 KB per composer-capable page load
  turns out to matter.

### Impact

| | Lines |
|---|---|
| `composer.js` | −120 |
| `page.html`, CSS | +20 |
| Python | 0, minus the contrib `apps.py` and package |
| Vendor added | GridStack, ~160 KB, in core, loaded only behind `change_pageblock` |

GridStack moves fast (v12 at the time of writing). Core absorbs that
major-version burden for this one vendor, knowingly: the composer is the
one screen where the vendor is the feature.

---

## 5. Spec changes

When the above lands, `SPEC.md` changes in these places:

| Section | Change |
|---|---|
| §2.6 | Core's front end: Unpoly, Tom Select, SortableJS, GridStack, Bootstrap Icons. Remove Luxon, which is not on disk. "A minimal install is eleven packages" stays true; they are heavier. |
| §7.4 | The client's mount walk is a compiler; `plinta.mount` and `plinta:content` are gone. |
| §7.12 | Retitle: *A filter change updates the grid.* Keep the three-level table as the history of the decision; the answer is now the second row, with compilers making the cards inside survive. |
| §11.2 | Drop "works with JavaScript disabled". |
| §12.4 | Drop "dragging is contrib" and the uninstall sentence. Core owns the four integers *and* the drag; the numbers form is the precise-adjust path. "View mode is CSS grid with no JavaScript" stays. |
| §14 | Remove `filters_tomselect` and `composer`; both are core's. |
| ADR 0005 | Amend: core carries vendors for **shell chrome** — navigation, dialogs, a select control, a sortable list, the layout editor — and none for **components**. The upgrade-burden argument applies to components, which is where it came from. |
| New ADR | *JavaScript-disabled is not a supported configuration*, with part 2's rule as the text. |

---

## 6. Later: other reductions, not yet decided

Surveyed alongside the above and parked. Each is a question to answer
when its turn comes, not a plan. Numbers are from the tree at the time of
writing: 16.4k lines of production Python (about a third prose), 16.7k of
tests, 1.9k of templates, 1.2k of CSS, a 5.4k-line spec, 26 skills.

### 6.1 Style packs

332 `{{ cls.* }}` substitutions in templates, the `classes()` registry, the
`styles` context processor and `contrib/styles_bootstrap5` exist so a
consumer with Bootstrap can have plinta's screens carry Bootstrap class
names. Every template line reads `class="{{ cls.btn }} {{ cls.btn_sm }}"`
instead of `class="pl-btn pl-btn--sm"`.

**Question:** will anyone run plinta's screens inside somebody else's CSS
framework? If not, drop the indirection: templates read plainly, the
Bootstrap pack and the `add-style-pack` skill go, and theming is what it
already is — `tokens.json`. Tokens cover colours and spacing; packs cover
only class names, which is the weaker feature.
**Impact if yes:** ~−150 Python, ~−300 template substitutions, −1 contrib
package, −1 skill.

### 6.2 `shell/views.py`

1,062 lines, 25 views. Three things:

- `"cls": _classes()` is passed by hand in 11 views while the `styles`
  context processor already supplies it. One of the two is dead.
- 18 occurrences of `if not can(user, "view", x): raise Http404("no such …")`.
  A `visible(user, action, obj)` helper that raises.
- Split into `views/pages.py`, `views/blocks.py`, `views/authoring.py`.
  Same lines; a thousand-line file is where duplication hides.

### 6.3 Notification channels → apprise

`builtin_channels.py` and the transport half of `delivery.py` become
configuration; the queue and preferences stay. The
`add-notification-channel` skill becomes a line in the settings docs.
**Impact:** ~−150 prod, −1 skill.

### 6.4 Audit → django-auditlog

Of `contrib/audit`'s 422 lines, the diff capture — m2m, FK labels, bulk —
is what a library does better. Keep the policy and the screen.
**Impact:** ~−200.

### 6.5 Test fixtures

Tests run 1:1 with production, which is healthy, but `shell` alone is
3,372 test lines and `User.objects.create_user(…)`, a local `grant(…)`,
`Page.objects.create(…)` repeat in nearly every file. A `conftest.py` with
shared fixtures (`author`, `viewer`, `page_with_table`) — factory-boy or
plain functions.
**Impact:** ~−400 test lines, and the next 400 are not written.

### 6.6 Spec-recorded dead weight

The spec marks "0 uses" from v1's usage data and says it is evidence, not
proof. A judgement pass over `pages/models.py` (465 lines: page types,
tabs, filter sets, filter preferences, placement defaults) and
`permissions/rules.py` (333 lines, eleven rules): anything v1 never
exercised and `example/` does not exercise either is a candidate. No
number without reading them.

### 6.7 Skills

26, each naming code paths. Parts 1–4 touch `add-block-action`,
`add-page-action`, `add-topbar-item`, `add-component`, `add-filter-widget`,
`add-style-pack`, `add-notification-channel` at least. Half are "add a
registry entry of kind X" and could collapse into one skill with a table,
or defer to the `docs/` pages they duplicate. A maintenance cost rather
than a line count.

### 6.8 The spec

5,398 lines, much of it "v1 did X, and here is why that changed". That
history belongs in the decision records (§24); the sections would then say
only what is. Halving it is realistic.

### Not touched

Comment density — a third of the code being prose is the house style and
is why the code is easy to reason about. The permissions engine,
datasources, renderers and the write pipeline — they are the product. The
public API — small and correct.

Ranked by value: 6.1 and 6.5 change how every future line is written;
6.2 is an afternoon; 6.3 and 6.4 are library swaps inside contrib;
6.6–6.8 are judgement passes.
