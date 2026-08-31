---
name: add-component
description: Add a widget type — a heatmap, a timeline, a map, a scorecard. Use when a screen needs a shape core does not draw. Not for changing how one value looks (a field renderer) or for a new output format (a renderer).
---

# Add a component

A component takes a resolved config and returns HTML.

```python
# yourapp/components.py
from plinta.components.base import Component, ComponentConfig, Mode
from plinta.components.registry import register_component

class HeatmapConfig(ComponentConfig):
    value_field: str
    buckets: int = 5
    palette: str = "viridis"

@register_component("heatmap_d3", label="Heat map (D3)")
class HeatmapComponent(Component):
    config_schema = HeatmapConfig
    mode = Mode.INLINE

    def render(self, config, user, **context) -> str:
        rows, fields = self.get_data(
            config, user,
            datasource=context["datasource"],
            narrow=context.get("narrow"),
        )
        return render_to_string("yourapp/heatmap.html", {"rows": rows, "config": config})
```

Import that module from `AppConfig.ready()`. The class is instantiated once at
registration, so a component holds no per-call state.

## The config arriving is already final

**Never merge a saved-view delta.** By the time `render` is called, `blocks` has
already merged the viewer's saved view over the block's config and validated
the result. Your component is handed one shape and cannot tell a saved view was
involved — which is exactly why you write no saved-view code at all.

Whatever keys your schema declares become deltable for free: saved views,
defaults, sharing and validation all work on a config schema they have never
seen. That is the whole reason the merge lives one layer up.

## Declare a schema, and make it strict

`ComponentConfig` sets `extra='forbid'`, so a key you did not declare is
rejected **when the block is saved**, not ignored when it renders. Strictness is
affordable precisely because exactly one shape arrives.

```python
class HeatmapConfig(ComponentConfig):
    value_field: str                       # required
    buckets: int = Field(default=5, gt=0)  # constrained
```

`columns` is on the base class — a list of column names, narrowed against what
the viewer may see. You get it whether you use it or not.

## Use `get_data`, do not query

The base `get_data` asks `datasources` for the permitted fields, collects the
joins their field renderers declared, and applies the block's narrowing. Calling
it is how your component inherits row policy, field permission, prefetch
derivation and computed columns without knowing any of them exist.

```python
# wrong: no permission check, a query per row, and it ignores base_filter
rows = Order.objects.all()

# right
rows, fields = self.get_data(config, user,
                             datasource=context["datasource"],
                             narrow=context.get("narrow"))
```

Overriding `get_data` is fine when you need to narrow further — call `super()`
first and transform what comes back, the way `table` applies its `sort`.

## Choose a mode

| | |
|---|---|
| `Mode.FETCH` | the page returns a mount point and the client asks for the data |
| `Mode.INLINE` | `get_data` runs during page render; rows are embedded in the HTML |

Pick from the interaction model, not the payload. **Fetch** if the client sorts,
filters or pages — a ten-thousand-row table cannot be inlined. **Inline** for a
finished blob or a single number; eight inline KPIs are eight numbers in one
response instead of eight round trips.

A block may override your default, for the genuine exception: a five-row related
table on a detail page, or a chart with 50,000 points.

## Escape your output

Your HTML is inserted as markup. Use a template, or `format_html` — never an
f-string around data:

```python
# wrong: a title containing <script> is now markup
return f"<div>{config.title}</div>"

# right
return format_html("<div>{}</div>", config.title)
```

## Shipping a template and a stylesheet

`render` returns a string; nothing requires `format_html`. Core's table uses it
because it is a hot row loop, not because it is the contract.

```
plinta/contrib/components/heatmap_plinta/
    templates/plinta/heatmap/heatmap.html     namespaced, or someone else's wins
    static/plinta/heatmap/heatmap.css
```

```python
def render(self, config, user, **context) -> str:
    return render_to_string("plinta/heatmap/heatmap.html", {...})
```

The template is found by Django's app-dirs loader because your app is
installed. The stylesheet is not — register it:

```python
# apps.py
def ready(self):
    from plinta.contrib.components.heatmap_plinta import component  # noqa: F401
    from plinta.utils.assets import register_stylesheet

    register_stylesheet("plinta/heatmap/heatmap.css")
```

**Multi-line `{# #}` is not a comment.** Django's lexer matches it without
`DOTALL`, so a comment carrying a newline is *text* and prints on the page.
Nothing warns: the page still returns 200. Use `{% comment %}` when it will
not fit on one line — thirteen of these shipped here at once.

**Draw with `cls`, not typed-in class names.** `{{ cls.card }}`,
`{{ cls.btn }}` — it is the style vocabulary (§10.9), so a project running a
Bootstrap pack gets your component drawn in Bootstrap's classes. Your own
internals (`pl-heatmap__cell`) are yours to name and style.

**Style only what you draw.** Core owns the chrome and the shared primitives —
`pl-card`, `pl-btn`, `pl-table`, `pl-chip`, `pl-stat`. Your sheet is for
`pl-heatmap__cell` and its kind. Redefining a shared class from a component
changes every screen that uses it, including ones your component is not on.

**A static path, never a URL.** A remote stylesheet is refused; loading a
vendor from a CDN is the consumer's decision, in the `plinta_css` block.

## How much room the card gives you

```python
class HeatmapComponent(Component):
    padding = Padding.NONE       # DEFAULT, TIGHT or NONE
```

The card pads its body, and most components want that. Declare `NONE` when
your markup should run to the edge — a table does, because its cells already
carry padding and the card's would double it at the rim while leaving the
middle unchanged.

**Declared rather than styled.** The padding is on the card's body, the
shell's element, which you render *inside* and cannot reach. Wrapping yourself
in a padded div would be a second box competing with the card's own scrolling.

**A name, never a length.** `Padding.TIGHT`, not `padding = "13px"` — a raw
length is the same defect a raw `#f0f0f0` is, and the scale is what keeps one
screen looking like the next.

## A control in your card's header

Anything you want *done to* a block — an export menu, a column chooser, a link
to your own settings screen — is a **block action**, registered separately and
drawn in the card header. See `add-block-action`. Your component does not draw
its own header; the shell does.

## Components that read nothing

A **content** component — text, a static banner — carries its content in its
config and needs no DataSource:

```python
class NoteComponent(Component):
    config_schema = NoteConfig
    needs_data = False
```

`Block.clean()` then requires that the block have **no** DataSource, as firmly
as it requires a table to have one. Both directions, because a content block
carrying one reads as configured while nothing reads it.

Most components are not this. If yours filters, aggregates or repeats over
rows — an alert with a condition, a repeater — it reads a model and the
default is right.

## Rules

**Name it `capability_implementation`.** `heatmap_d3`, not `heatmap` — the
capability says what it draws, the implementation says what draws it. That
leaves the obvious name free for somebody else's, and lets both be installed
while an installation migrates between them. Use your own name where there is
no vendor: `heatmap_acme`.

The label is where the friendliness lives, so a picker still reads well:

```python
@register_component("heatmap_d3", label="Heat map (D3)")
```

**One registry key, one component.** A second registration under the same name
raises rather than replacing, so two packages cannot silently fight over
`heatmap_d3`.

**Ship everything with the package** — the template, the assets, the front-end
adapter and its vendor library. A component whose JavaScript lives in core is
not a plugin.

**Do not import another component.** Components do not compose sideways; a page
places two blocks.

**Removing your package degrades, it does not break.** A block naming an
unregistered type renders an empty slot, so a page that used your component
still loads.

## Verifying

```python
def test_a_typo_is_rejected_at_save_time(component_registry):
    with pytest.raises(ConfigError):
        HeatmapComponent().validate({"buckts": 5})

def test_it_shows_no_column_the_viewer_may_not_see(component_registry):
    out = HeatmapComponent().render(config, user, datasource=ds)
    assert "secret" not in out
```

The second is worth writing for every component: it is the one property a
component can accidentally break, by querying instead of calling `get_data`.

Use the `component_registry` fixture so a test's registration does not leak.
