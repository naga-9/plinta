"""Who may see and change a page or a saved filter set.

The same shape blocks use: a viewer sees their own, public ones, and ones
shared with them; only the owner and a grantee may change one.

There is no `is_system` flag. A page nobody should delete is protected by not
granting `delete_page`, which is the permission system doing its own job.
"""
from plinta.pages.models import FilterSet, Page
from plinta.permissions.policies import PermissionPolicy, register_policy
from plinta.permissions.rules import InstancePerm, Owner, Public


class PagePolicy(PermissionPolicy):
    view = Owner() | Public() | InstancePerm("plinta_pages", "page", "view")
    change = Owner() | InstancePerm("plinta_pages", "page", "change")
    delete = Owner()


class FilterSetPolicy(PermissionPolicy):
    view = Owner() | Public() | InstancePerm("plinta_pages", "filterset", "view")
    change = Owner() | InstancePerm("plinta_pages", "filterset", "change")
    delete = Owner()


register_policy(Page, PagePolicy)
register_policy(FilterSet, FilterSetPolicy)
