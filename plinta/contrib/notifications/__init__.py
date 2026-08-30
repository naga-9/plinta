"""In-app notifications and queued email, built entirely by listening.

Every sideways dependency in v1 pointed here: comments called it, actions
called it, the workflow mixin called it, the write pipeline called it. Four
contrib apps and one core module reached in directly, which is what made this
app effectively mandatory.

All four are emitters of core signals now, and this app subscribes. Nothing
imports it, and every one of those paths runs with it uninstalled.
"""
