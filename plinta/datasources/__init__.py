"""The model registry: which models plinta may show, and how their columns behave.

Nothing is re-exported here. This package defines Django models, and Django
imports an app's package before its models are loadable — so an ``__init__``
that reached them would make the app unimportable. Import from the module:

    from plinta.datasources.services import get_queryset
    from plinta.datasources.modifiers import register_queryset_modifier
"""
