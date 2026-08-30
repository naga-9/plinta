"""Who may read a comment, and who may change one.

A comment is as visible as the row it is attached to — the policy cannot say
so directly, since a rule reads fields on the comment rather than on its
target, so visibility is gated where the thread is fetched (`services.thread`)
and this policy governs the comment itself.
"""
from plinta.contrib.comments.models import Comment
from plinta.permissions.policies import PermissionPolicy, register_policy
from plinta.permissions.rules import AllowAll, Owner


class CommentPolicy(PermissionPolicy):
    """Readable by anyone who may reach the thread; editable by its author.

    `view` admits every row because the narrowing that matters happened one
    step earlier: a thread is fetched for a target the viewer may see, and a
    comment on a row they cannot see is a row they never ask for.

    `change` and `delete` are the author's alone. An administrator who must
    remove one has `delete_comment` and a superuser bypass; a moderation
    workflow beyond that is a consumer's to build.
    """

    view = AllowAll()
    change = Owner("author")
    delete = Owner("author")


register_policy(Comment, CommentPolicy)
