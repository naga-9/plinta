---
name: add-shell-link
description: Put a screen in the sidebar that is not a Page — an editor, a console, a report builder. Use when your app ships a view rather than a composition. Not for a dashboard; seed a Page and it appears in the menu on its own.
---

# Add a shell link

The sidebar is built from the pages a viewer may open. A screen that is a
**view** rather than a composition has no `Page` row, so it declares itself:

```python
# yourapp/apps.py
class ReportsConfig(AppConfig):
    name = "yourapp.reports"

    def ready(self):
        from plinta.shell.links import register_shell_link

        register_shell_link(
            "report_builder",
            "Report Builder",
            url_name="reports:builder",
            permission="reports.add_reportdefinition",
            section="Reports",
            group="Tools",
            order=300,
        )
```

The link draws only for a holder of that permission, and disappears entirely
when your package is uninstalled — no guard anywhere in the shell, and no dead
entry pointing at a URL that no longer resolves.

## Say where it goes

`section` and `group` name a place in the menu, using the same names a
`MenuGroup` uses. A link naming a group that already holds pages **joins it**;
one naming a group nothing else uses **creates it**, so an app shipping only a
view needs no `MenuGroup` row. Naming neither puts it at the top.

Without this a link had nowhere to say where it belonged and landed under a
hard-coded heading — so an app shipping a *page* chose its place and one
shipping a *view* did not.

**`order` is the only coordination between apps that never see each other**,
so keep to the convention:

| Range | Whose |
|---|---|
| 0–99 | the consumer's own screens |
| 100–899 | contrib |
| 900+ | administration |

**A section is optional.** A group with none sits at the top of the menu, so a
small installation is two levels rather than three.

## Prefer a Page

Most screens should not use this. A dashboard, a list, a detail view composed
of blocks — all of those are `Page` records, and a page:

- appears in the menu through the ordinary permission-filtered path
- can be shared, one row at a time, with `InstancePerm`
- can be rearranged in the browser without a deploy
- travels with the rest of the configuration when it is exported

**Reach for a shell link only when there is no composition to record** — a
wizard, a console, a builder. `contrib.reports` seeds a `Page` for its list and
registers a link for its builder, which is the right split.

## The permission is a plain check

`has_perm`, not the policy engine. These screens are not rows, so there is
nothing for a policy to narrow: the question is only whether this viewer may
open the screen at all.

Name a permission that already exists. A codename nothing minted is held by
nobody, so the link never appears — which looks exactly like the registration
having failed.

## Rules

**Register from your own `AppConfig.ready()`.** A link registered anywhere else
is the shell naming a package it does not own, which is the defect this
registry removes.

**Use a URL name, not a path.** The sidebar reverses it, so your URLs stay
yours to move.

**One name, one link.** A second registration under the same name raises rather
than replacing.

**`order` decides placement**, ties broken by label. Core reserves nothing;
pick a number that puts your screen where it belongs among the others.

## Verifying

```python
def test_the_link_is_gated(shell_link_registry):
    register_shell_link("builder", "Builder",
                        url_name="reports:builder",
                        permission="reports.add_reportdefinition")
    assert visible_links(without_permission) == []
    assert [link.name for link in visible_links(with_permission)] == ["builder"]
```

Worth writing, because a link that draws for everyone is a screen that refuses
most of them — and the permission string is not checked against anything until
somebody holds it.

Use the `shell_link_registry` fixture so a test's registration does not leak.
