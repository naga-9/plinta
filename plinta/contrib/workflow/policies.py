"""Who may read a workflow's definition.

The definition is configuration, not data: knowing that an order can move from
open to closed tells you nothing about any order. So reading is the model
permission's question alone, and changing one is an administrator's.
"""
from plinta.contrib.workflow.models import Workflow, WorkflowState, WorkflowTransition
from plinta.permissions.policies import PermissionPolicy, register_policy
from plinta.permissions.rules import AllowAll


class DefinitionPolicy(PermissionPolicy):
    """Every row, to anyone holding the model permission."""

    view = AllowAll()


for model in (Workflow, WorkflowState, WorkflowTransition):
    register_policy(model, DefinitionPolicy)
