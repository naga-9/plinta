"""Notifications and queued email, built entirely by listening.

Nothing imports this app. A comment, a transition and a write all emit core
signals that it subscribes to, so each of those paths runs with it
uninstalled.
"""
