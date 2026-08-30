"""Who may read a comment, and who may change one.

Two gates, and both apply. Whether somebody may reach the **thread** is
decided by whether they may see the row it hangs on (`services.thread`); this
policy then decides which comments *in* that thread they see.
"""
from plinta.contrib.comments.models import Comment
from plinta.permissions.policies import PermissionPolicy, register_policy
from plinta.permissions.rules import GroupOverlap, Owner, Public, UserInM2M


class CommentPolicy(PermissionPolicy):
    """Public unless owned; editable by whoever wrote it.

    An owner-less comment is public — visible to anybody who may reach the
    thread, which is decided one step earlier by whether they may see the row
    it hangs on. An owned one is private to its owner and to the people and
    groups it names.

    `change` and `delete` are the **author's**, not the owner's: making a
    comment private is not the same as having written it. An administrator who
    must remove one holds `delete_comment` and the superuser bypass; a
    moderation workflow beyond that is a consumer's to build.
    """

    view = (
        Public()
        | Owner("owner")
        | Owner("author")
        | UserInM2M("visible_to")
        | GroupOverlap("visible_to_groups")
    )
    change = Owner("author")
    delete = Owner("author")


register_policy(Comment, CommentPolicy)
