"""Everything plinta ships that core does not need.

A contrib package registers itself from its own `AppConfig.ready()`, declares
what it requires, and is removable: an installation with none of them is a
working plinta. Core never imports anything here, which a test enforces
(§2.5).
"""
