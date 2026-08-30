"""plinta — turn Django models into interactive, permission-aware screens.

Being rebuilt layer by layer against ``docs/design/SPEC.md``. The previous
version is the git tag ``v1.0``; nothing is carried across without a decision
recorded in that document.

Layer order (SPEC §2.3) — a layer may import from any layer below it and from
no layer above it, and no core layer may import ``plinta.contrib``::

    9  shell        8  pages       7  blocks      6  components
    5  renderers    4  datasources 3  permissions 2  events
    1  utils · dates · forms

Enforced by ``tests/test_import_boundary.py``, not by discipline.
"""
