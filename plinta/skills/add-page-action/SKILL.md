---
name: add-page-action
description: Put a control in a page's own header, beside its title — an "Edit layout" toggle, an export button, a subscribe link. Use when the control is about the page it sits on. Not for chrome on every screen; that is a topbar item.
---

# Add a page action

A page's header draws whatever is registered and names no package. An app that
wants a control there says so from its own `AppConfig`:

```python
# yourapp/apps.py
class ComposerConfig(AppConfig):
    name = "yourapp.composer"

    def ready(self):
        from plinta.pages.actions import register_page_action
        from plinta.pages.models import PageType

        register_page_action(
            "composer",
            template="composer/edit_layout.html",
            permission="plinta_pages.change_pageblock",
            page_types=(PageType.DASHBOARD,),
            order=20,
        )
```

Import the models **inside `ready()`**, never at the top of `apps.py`:
`ready()` runs during app loading, and a model import at module scope is a
circular import waiting to happen.

## What it is for

This is what lets a feature about a page live outside core. `contrib.composer`
is the worked example: core stores a placement's four integers and owns the
rule that writes them, and the app supplies dragging — so core never names
GridStack, or the composer, or anything else.

If your control needs to address one card, the grid markup carries
`data-plinta-placement`. Core never reads it; it is there so something else
can.

## The template renders with the page

Your template is included with `page` and the request in context:

```html
<button type="button" class="{{ cls.btn }} {{ cls.btn_sm }}"
        data-plinta-subscribe="{% url 'alerts:subscribe' page.pk %}">
    Notify me
</button>
```

**Build URLs in the template, never in JavaScript.** A page's address carries
a decorative slug (`/pages/6-catalog/`), so a script deriving an endpoint from
`location.pathname` gets a 404. Hand the URL over in a data attribute — the
same rule §9.0 states for every URL a component is given.

**Class names come from `cls`, not typed in.** It is the style vocabulary
(§10.9), so a project running a Bootstrap style pack gets your control drawn
in Bootstrap's classes. Typing `pl-btn` works today and stops working for them.

## Narrow it to the pages it suits

```python
page_types=(PageType.DASHBOARD,)
```

Empty means every type, which is right for an action about the page itself and
wrong for one about a grid — a `detail` page and a `custom-template` page have
no placements to arrange. A control that appears and then refuses is worse than
one that is absent.

## Rules

**Register from your own `AppConfig.ready()`.** Anywhere else and core is
importing a package it does not own.

**Name the permission the write checks.** Drawing a control whose action the
server would refuse is the failure this exists to avoid. If your endpoint asks
for `change_pageblock`, so does the control.

**Anonymous viewers get nothing**, whatever you register.

**One name, one action.** A second registration under the same name raises
rather than replacing.

**Degrade, do not depend.** Core must be complete without you. The composer's
test is that `/pages/<pk>/compose/` still arranges a page by typing numbers
when the app is uninstalled.

## Not a topbar item

| You want | Use |
|---|---|
| a control about *this page* | this |
| a control on every screen | `add-topbar-item` |
| an entry in the sidebar | `add-shell-link` |
| a control on one *card* | `add-block-action` |

## Verifying

```python
def test_the_control_is_gated(page_action_registry):
    register_page_action("composer", template="composer/edit_layout.html",
                         permission="plinta_pages.change_pageblock")
    assert visible_actions(page, without_permission) == []
    assert [a.name for a in visible_actions(page, with_permission)] == ["composer"]
```

Use the `page_action_registry` fixture so a test's registration does not leak.

If your action ships JavaScript, test it in the **browser** suite. The one bug
in the composer that no Python test could see was exactly the URL mistake
above: every assertion passed while the drag posted to a 404.
