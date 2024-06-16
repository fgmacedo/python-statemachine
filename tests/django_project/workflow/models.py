from django.contrib.auth import get_user_model
from django.db import models

from statemachine.mixins import MachineMixin

User = get_user_model()


class Workflow(models.Model, MachineMixin):
    state_machine_name = "workflow.statemachines.WorfklowStateMachine"
    state_machine_attr = "wf"

    state = models.CharField(max_length=30, blank=True, null=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True)
    is_active = models.BooleanField(default=False)
