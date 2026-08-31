---
name: add-icon-set
description: Draw menu and link icons from your own set — Font Awesome, Bootstrap Icons, Material Symbols, your brand's. Use when a project already has an icon library and the sidebar should match it. Not for adding one icon; that is a name core already ships.
---

# Add an icon set

Core ships 33 icons as inline SVG. A set of your own is registered beside it,
and a stored value picks between them.

```python
# yourapp/apps.py
def ready(self):
    from django.utils.html import format_html
    from plinta.utils.icons import register_icon_set

    register_icon_set(
        "bi",
        render=lambda name, size=18, css_class="pl-icon", **kw: format_html(
            '<i class="{} bi bi-{}"></i>', css_class, name
        ),
    )
```

```python
Page.objects.filter(slug="sales").update(menu_icon="bi:cart")
```

**`set:name`. Write the prefix** — `"plinta:home"`, not `"home"`. Everything
plinta ships does, so a stored value says which set it came from without the
reader knowing what the default is.

An unprefixed name still resolves to core's set. That is a forgiving read for
what somebody types, not a second spelling to choose between.

## Try core's first

`plinta/design/icons.py` lists what ships: `home`, `dashboard`, `table`,
`chart`, `trend`, `cart`, `package`, `users`, `settings`, `bell`, `file`,
`calendar`, `tag`, `folder`, `search`, `store`, `book` and the rest. They are
inline SVG, so they need **no font, no stylesheet and no request** — and they
take their colour from whatever they sit in, in either theme, because they
draw with `currentColor`.

A set is worth registering when your project **already loads** an icon font
for its own pages and the sidebar should match it. It is not worth registering
to get one more icon.

## Your renderer builds markup, so it escapes

```python
render=lambda name, **kw: format_html('<i class="bi bi-{}"></i>', name)
```

Whatever you return is inserted **unescaped**. The name comes from
configuration written by somebody with `change_page`, and it lands in a class
attribute — `format_html`, never an f-string or concatenation.

## Load your font yourself

Core requests nothing at runtime and will not start on your behalf.
`register_stylesheet` refuses a remote path (§10.10), so either vendor the
font into your own `static/` and register it, or load it in the `plinta_css`
block where the choice is visible.

**An icon font costs a request that can fail and a flash of invisible text
before it arrives.** That is why core's own set is inline, and it is worth
weighing before adding one.

## Rules

**Register from your own `AppConfig.ready()`.**

**Lowercase `[a-z][a-z0-9_]*`.** The prefix is stored on every page that uses
it; renaming a set orphans them.

**One name, one set.** A second registration raises rather than replacing. To
change how core's icons draw, register your own set and point the pages at it.

**Accept `size` and `css_class`, and hide the icon from assistive
technology.** An icon sits beside a label that already says what the thing is,
so it is decoration: `aria-hidden="true"` and, for an SVG,
`focusable="false"`.

**Draw nothing for a name you do not have.** Core does, and so should you — a
gap beside a label reads as a missing icon, where a broken-image box reads as
a broken page.

## Verifying

```python
def test_my_set_draws(icon_registry):
    register_defaults()
    register_icon_set("bi", render=...)
    assert render("bi:house") == '<i class="pl-icon bi bi-house"></i>'
    assert render("home").startswith("<svg")      # core's, still there


def test_an_unknown_name_draws_nothing(icon_registry):
    register_icon_set("bi", render=...)
    assert render("bi:") == ""
```

The second is the one worth writing. A set that renders a box for every
misspelling turns a typo in configuration into a visibly broken sidebar.

Use the `icon_registry` fixture so a test's registration does not leak.
