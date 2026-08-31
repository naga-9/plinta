---
name: add-notification-channel
description: Add a way of reaching people — Discord, Slack, SMS, a webhook, push. Use when notifications should arrive somewhere the two built-in channels do not reach. Requires plinta.contrib.notifications.
---

# Add a notification channel

**Requires `plinta.contrib.notifications` in `INSTALLED_APPS`.**

Two channels ship — the in-app list and the email queue — and both register
themselves through this same call, so there is no private path for them to keep
working on when the public one rots.

```python
# yourapp/apps.py
def ready(self):
    from plinta.contrib.notifications.channels import register_channel
    from yourapp.discord import enqueue_discord

    register_channel(
        "discord",
        "Discord",
        deliver=lambda user, notification, **kw: enqueue_discord(
            user.discord_webhook, notification.title, notification.url
        ),
        available=lambda user, **kw: bool(getattr(user, "discord_webhook", "")),
        on_by_default=False,
    )
```

A channel is a **name and a delivery callable**. It does not decide who hears
anything — that is a subscription's job (`add-notification-type`) — and keeping
the two apart is what lets one subscription reach a person on whichever
channels they have asked for.

## Deliver without blocking

`deliver` runs inside the write that caused the notification. A channel that
posts to an HTTP API on that thread makes every save wait for someone else's
server, and makes a slow API look like a slow application.

**Enqueue, don't post.** The built-in `email` channel is the worked example,
and it queues rather than sending.

## `available` decides whether to offer it

Return False when this person cannot be reached on your channel at all — no
linked account, no phone number — and the channel is not offered in their
preferences. A checkbox that can never deliver is worse than an absent one,
because they will tick it and wait.

It is a probe over a consumer's data, so it is called defensively: raising is
logged and read as unavailable.

## `on_by_default` is off unless you are sure

**A channel that mails the world on install is a channel that gets
uninstalled.** New channels appear in everyone's preferences the moment you
register them; whether they are ticked is what you decide here, and off is
almost always right.

The exception is a channel that is the only way to reach someone at all.

## Preferences are automatic

Registering a channel adds it to every user's preferences with your default.
You do not write a migration, a screen, or a settings row — and unregistering
removes it, so an uninstalled channel leaves no stale checkbox.

## Failures are contained

`send` never raises. A channel that fails is logged and the others still
deliver, because one broken webhook must not swallow somebody's email — and
none of them may fail the write that caused the notification.

This means **a silently broken channel looks like nothing happening.** Log
enough inside `deliver` to tell "nobody was notified" from "the notification
never reached the queue".

## Rules

**Register from your own `AppConfig.ready()`.**

**Lowercase `[a-z][a-z0-9_]*`.** The name is a preferences key; renaming one
later orphans everybody's setting for it.

**One name, one channel.** A second registration raises rather than replacing.
To change how `email` delivers, replace the sender it calls, not the channel.

**Do not read `notification.recipient`'s permissions inside `deliver`.**
Whether this person should hear about this was settled before you were called.

## Verifying

```python
def test_discord_is_offered_only_to_linked_accounts(channel_registry):
    register_channel("discord", deliver=noop,
                     available=lambda user, **kw: bool(user.discord_webhook))
    assert not reachable(user_without_webhook, get("discord"))
    assert reachable(user_with_webhook, get("discord"))


def test_a_failing_channel_does_not_stop_the_others(channel_registry):
    register_channel("broken", deliver=raises)
    notify(...)
    assert Notification.objects.filter(user=user).exists()   # in-app still landed
```

The second is the one worth writing. Use the `channel_registry` fixture so a
test's registration does not leak.
