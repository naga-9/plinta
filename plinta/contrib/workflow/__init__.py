"""A state machine for a consumer's models.

Registration, not inheritance: a model declares its own state field and says
so. Nothing here is a base class, so a model that opts in stays an ordinary
Django model and keeps its state as a plain column — sortable, filterable and
groupable like any other.
"""
