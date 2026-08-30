"""Who may see and change a block or a saved view.

Both are shareable on the same rules: a viewer sees their own, public ones,
and ones shared with them; only the owner and a grantee may change one.
"""
from plinta.blocks.models import Block, SavedView
from plinta.permissions.policies import PermissionPolicy, register_policy
from plinta.permissions.rules import InstancePerm, Owner, Public


class BlockPolicy(PermissionPolicy):
    view = Owner() | Public() | InstancePerm("plinta_blocks", "block", "view")
    change = Owner() | InstancePerm("plinta_blocks", "block", "change")
    delete = Owner()


class SavedViewPolicy(PermissionPolicy):
    view = Owner() | Public() | InstancePerm("plinta_blocks", "savedview", "view")
    change = Owner() | InstancePerm("plinta_blocks", "savedview", "change")
    delete = Owner()


register_policy(Block, BlockPolicy)
register_policy(SavedView, SavedViewPolicy)
