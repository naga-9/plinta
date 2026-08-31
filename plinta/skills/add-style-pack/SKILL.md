---
name: add-style-pack
description: Make plinta's screens carry somebody else's class names — Bootstrap, Tailwind, Bulma, your own design system. Use when a project already has a CSS framework and the screens should match it. Not for changing colours or spacing; those are design tokens.
---

# Add a style pack

A pack swaps the class names the markup emits. Plinta draws `pl-btn`; your
pack says it is `btn btn-outline-secondary`.

```python
# yourapp/apps.py
def ready(self):
    from plinta.utils.styles import register_style_pack

    register_style_pack("acme", {
        "btn": "acme-button",
        "table": "acme-table acme-table--striped",
        "card": "acme-panel",
    })
```

```python
# settings.py
PLINTA_STYLE_PACK = "acme"
```

Overrides merge over the defaults, so a pack lists only what it changes — one
that restyles buttons is four lines, not a hundred.

## Try tokens first

**If you only want different colours, spacing, radii or fonts, you do not want
a pack.** Redefine the custom properties:

```css
:root { --pl-accent: #7c3aed; --pl-radius: 10px; }
```

That keeps every class name, so nothing here applies and nothing can drift. A
pack is for when the class names themselves must be somebody else's — because
their CSS is already loaded and you want the screens to use it.

## What a pack cannot do

**It renames; it cannot reshape.** Frameworks disagree about markup, not just
naming:

| Framework | Pagination |
|---|---|
| Bootstrap 5 | `ul.pagination > li.page-item > a.page-link` |
| Bulma | `nav.pagination > a.pagination-previous` **+** a separate `ul.pagination-list` |
| Fomantic | `div.ui.pagination.menu > a.item` — no list |
| Tailwind | none — utilities on whatever markup exists |

Plinta's markup is chosen for its own semantics: a pager and a menu are lists
of links because that is what they are. **Tailwind needs no structure at all,
so a Tailwind pack is pure mapping.** Bootstrap mostly lines up. Fomantic does
not, and no mapping will make it.

**Write down what you cannot reach**, and override those templates instead:

```python
RESIDUE = {
    "plinta/shell/topbar.html": "the navbar wants .navbar > .container-fluid",
}
```

A pack that maps something a class cannot fix produces a screen that looks
broken with no error to explain it. Naming the gap is the difference between
an incomplete pack and a wrong one.

## Ship no stylesheet

**A pack is a mapping, not a vendored framework.** Where Bootstrap comes from
— a CDN, npm, your own build — is the consumer's decision, and shipping a copy
makes it for them, then leaves them on your upgrade schedule.

Load it in the template block that exists for it:

```html
{% block plinta_css %}
    <link rel="stylesheet" href="{% static 'vendor/bootstrap.min.css' %}">
{% endblock %}
```

Note this **replaces** plinta's own stylesheet. That is usually what you want
with a full framework — and is why a partial pack should extend the block
rather than replace it, keeping plinta's layout CSS underneath.

## Rules

**Register from your own `AppConfig.ready()`.**

**Every key must be in the vocabulary.** `plinta.utils.styles.DEFAULT` is the
list; an unknown key raises rather than being ignored, because a misspelled
one would silently leave our class in place — which looks exactly like the
pack not being installed.

**Never map a key to an empty string.** That is how an element loses its
styling with nothing to show for it. If a framework has no equivalent, keep
plinta's class by leaving the key out.

**One name, one pack.** A second registration raises. To adjust somebody
else's pack, register your own naming theirs as its base:
`{**their.CLASSES, "btn": "…"}`.

**A pack named by the setting but never registered raises** at first use. It
does not fall back — the screens would render in plinta's classes against a
stylesheet that does not define them.

## Verifying

```python
def test_nothing_maps_to_nothing(style_registry):
    register_style_pack("acme", CLASSES)
    assert all(classes("acme")[key].strip() for key in DEFAULT)


def test_the_pager_renders_your_markup(settings, style_registry):
    register_style_pack("acme", CLASSES)
    settings.PLINTA_STYLE_PACK = "acme"
    html = HtmlRenderer().pager(page, {"next": "?page=2"})
    assert 'class="acme-pagination"' in html
    assert "pl-pager__list" not in html
```

The second is the one worth writing. A pack that registers cleanly and never
reaches the markup is the failure to expect, and it is invisible until
somebody looks at a screen.

`plinta.contrib.styles_bootstrap5` is a complete worked example, including
its `RESIDUE`.

Use the `style_registry` fixture so a test's registration does not leak.
