# Reading the code

For somebody with the repository open. Not why the decisions were taken —
that is [`design/SPEC.md`](design/SPEC.md), which is organised by decision and
is a poor way in. This is organised by how a request moves.

Two hours, in this order.

## 1. Follow one page render

`shell/views.py::page_view` is the spine. Every layer appears in it, in
order, and the six functions below are about a thousand lines between them.

| | |
|---|---|
| `shell/views.py::page_view` | who may see this page, which filters are in force, which record it is about |
| `pages/rendering.py::render_page` | one `Placement` per slot, including the empty ones. The **page** owns the URLs and the narrowing, because only it knows which placement a card is |
| `blocks/rendering.py::render_block` | the effective config: the block's, with a saved view's delta over it |
| `components/base.py::Component.render` | config in, HTML out. A component never queries |
| `components/base.py::Component.get_data` | rows and columns from `datasources`, already narrowed by permission |
| `renderers/html.py::cell` | one value, formatted and escaped |

Read those and you know the read path. Three things worth noticing while you
do:

- **`render_page` builds every URL.** A component is handed `data_url`,
  `write_url`, `form_url`, `record_url` rather than constructing them. Only a
  page knows which placement it is drawing, and a card's records may open on a
  different page entirely.
- **`get_data` is where access is decided**, below the block. That is why a
  block cannot widen it: by the time config is applied, the rows and columns
  are already what this viewer may see. `choose_columns` narrows and reorders;
  it can never add.
- **One block failing does not take the page.** `render_block` catches, and
  the slot shows an error while its seven neighbours draw. In `DEBUG` it
  re-raises, because a developer wants the traceback.

## 2. Then one write

The same shape backwards, and a smaller read.

| | |
|---|---|
| `shell/views.py::block_write` | placement-scoped, and shares its resolution with the read half so a write cannot reach a card a read could not |
| `blocks/submit.py::submit` | which columns may be written, and the row reached through the block's own narrowing |
| `blocks/write.py::write` | authorise → validate → emit → save → diff → emit. **The only path by which plinta mutates a consumer's data** |

`write.py` is the file to read closely. Its stage order carries the safety
properties, and its docstring says which.

Three refusals, and they are different answers: **405** the component does not
write at all, **403** this viewer may not, **422** this value will not do.

## 3. The layers, and the rule

```
utils · dates · forms → events → permissions → datasources
    → renderers → components → blocks → pages → shell
```

A layer imports only what is below it, no core module imports `contrib`, and a
contrib package does not import another. The rule is not a convention:
`tests/test_import_boundary.py` walks the AST and fails the build, and it has
a JavaScript half for the same reasons.

If you want to know what a layer may know, read the top of its `__init__.py`
or the module docstring of its main file. Every one states what it must **not**
know, which is usually the more useful half.

## 4. Twenty-seven registries, all the same

Extension points are a registry, and they are identical on purpose:

```python
_registry: dict[str, Thing] = {}

def register_thing(name, ...): ...   # raises if the name is taken
def get(name): ...                   # raises listing what *is* registered
```

Read `components/registry.py` and you have read all of them. Each has a
`conftest.py` fixture that empties and restores it, so a test's registration
never leaks.

They are why core stays small: `table_plinta` and `form_plinta` go through the
same door a third party does, so the door cannot rot.

## 5. The guards

Four suites, and each catches something the others cannot.

```
pytest                        core       — no contrib app installed, deliberately
pytest -c pytest-contrib.ini  contrib    — its own settings, with the apps
pytest -c pytest-browser.ini  browser    — real Chromium, live server
cd example && pytest          demo       — the consumer, as a consumer
```

The browser suite exists because of a specific bug: the client mounted at
`readyState === 'interactive'`, which is when a **deferred** script runs, so it
mounted before the adapters that follow it. Every fetching component reported
that it had no adapter while every Python test passed. jsdom does not model
deferred timing either. If you are changing anything the browser touches, that
suite is the one that will tell you.

Some tests are rules rather than examples, and reading them is faster than
reading prose about them:

| | |
|---|---|
| `tests/test_import_boundary.py` | the layer rule, executable |
| `shell/test_stylesheet.py` | every class the markup emits has a rule defining it |
| `shell/test_tokens.py` | no raw colour outside `design/tokens.json` |
| `blocks/test_saved_views.py` | what a delta is, and why it is not a copy |

## 6. Where the awkward parts are

Honest signposts, so you do not conclude you have misread something.

**`datasources` is the hinge.** `DataSource` and `DataSourceField` are rows,
not code, and a `DataSourceField` is the *only* thing that mints a field
permission. That one fact explains several designs that look odd from outside
— including why plinta registers two of its own models as DataSources
(§6.1b): `FilterSet` and `SavedView` need a permission on their `owner` field,
because publishing one is a change to that field.

**Permissions are two tiers plus fields.** The model permission
(`view_book`), the row policy (`Owner() | Public()`), and the column
(`view_book_price`). All three must hold. `permissions/engine.py` is where
they meet.

**Config is data.** Pages, blocks and their positions are rows, edited in the
admin or the authoring screens. There is no file to grep for the dashboard
you are looking at — which is also the biggest hole in the design, and §16
says so.

**A delta is not a copy.** A saved view stores only what differs from its
block, so a change the author makes later still reaches every view that did
not override that setting. Most of the shape of the view editor follows from
that one sentence.

## Where to go next

- **Extending it** — [`plinta/skills/`](https://github.com/naga-9/plinta/tree/main/plinta/skills), one guide per
  extension point. `add-component` is the widest.
- **Why something is the way it is** — [`design/SPEC.md`](design/SPEC.md).
  Searchable by decision; every section ends in a decisions table.
- **A worked consumer** — [`example/`](https://github.com/naga-9/plinta/tree/main/example). It uses only the
  published extension points, which is what makes it the guard that they are
  real.
