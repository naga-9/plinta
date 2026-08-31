---
name: add-topbar-item
description: Put a control in the topbar — a notification bell, a task counter, an environment badge. Use when your app needs chrome on every screen rather than a screen of its own. Not for a sidebar entry; that is a shell link.
---

# Add a topbar item

The topbar draws whatever is registered and names no package. An app that
wants a control there says so from its own `AppConfig`:

```python
# yourapp/apps.py
class AlertsConfig(AppConfig):
    name = "yourapp.alerts"

    def ready(self):
        from plinta.shell.topbar import register_topbar_item

        register_topbar_item(
            "alerts",
            template="alerts/topbar_badge.html",
            permission="alerts.view_alert",
            order=20,
        )
```

This is the whole reason the registry exists. A bell hard-coded into the shell
template would be core naming a package that may not be installed — and every
consumer who removed that package would be editing core's chrome to get rid of
a control pointing at nothing.

## The template renders with the request

Your template is included with the request in context, so it can count its own
rows:

```html
{% load alert_tags %}
<a class="{{ cls.btn }} {{ cls.btn_ghost }} {{ cls.btn_sm }}"
   href="{% url 'alerts:list' %}">
    <span aria-hidden="true">!</span>
    {% with n=request.user|unread_alert_count %}
        {% if n %}<span class="{{ cls.chip }}">{{ n }}</span>{% endif %}
    {% endwith %}
</a>
```

**Class names come from `cls`, not typed in.** It is the style vocabulary
(§10.9), so a project running a Bootstrap style pack gets your control drawn in
Bootstrap's classes without you knowing. Typing `pl-btn` works today and stops
working for them.

**That query runs on every page.** The topbar is chrome, so whatever it costs
is charged to every screen in the product — count with a single aggregate, and
cache it if it is not one.

## Draw nothing rather than nothing-to-do

An item with a zero count should render empty, not render a control that says
zero. The topbar is the most expensive real estate in the shell; a badge that
is usually blank is worth less than the space it holds.

## Rules

**Register from your own `AppConfig.ready()`.** Anywhere else and the shell is
importing a package it does not own.

**Name a permission unless everyone should see it.** An item with no permission
draws for anybody signed in. One naming a permission draws only for a holder,
so your app's chrome disappears with its access rather than showing a control
that refuses when clicked.

**Anonymous viewers get nothing at all**, whatever you register — the topbar
is empty before sign-in.

**One name, one item.** A second registration under the same name raises rather
than replacing.

**`order` decides placement**, ties broken by name. Core reserves nothing.
`contrib.notifications` uses 10 for its bell, so a control that belongs to its
left wants a smaller number.

## Not a shell link

| You want | Use |
|---|---|
| a control on every screen | this |
| an entry in the sidebar to a view | `add-shell-link` |
| an entry in the sidebar to a dashboard | seed a `Page`; the menu finds it |

## Verifying

```python
def test_the_badge_is_gated(topbar_registry):
    register_topbar_item("alerts", template="alerts/topbar_badge.html",
                         permission="alerts.view_alert")
    assert visible_items(without_permission) == []
    assert [i.name for i in visible_items(with_permission)] == ["alerts"]
```

Worth writing, because an item that draws for everyone is a control that
refuses most of them — and the permission string is not checked against
anything until somebody holds it.

Use the `topbar_registry` fixture so a test's registration does not leak.
