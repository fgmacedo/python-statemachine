import sys

import pytest
from django.contrib.auth import get_user_model

from statemachine.exceptions import TransitionNotAllowed
from workflow.models import Workflow
from workflow.statemachines import WorfklowStateMachine

pytestmark = [
    pytest.mark.django_db,
    pytest.mark.skipif(sys.version_info < (3, 10), reason="Requires Python 3.10"),
]


User = get_user_model()


@pytest.fixture()
def one():
    return Workflow.objects.create()


class TestWorkflow:
    def test_one(self, one):
        with pytest.raises(TransitionNotAllowed):
            one.wf.send("publish")

    def test_two(self, one):
        # Managing this instance works if I call it like this instead.
        # So this test works
        wf = WorfklowStateMachine(one)
        with pytest.raises(TransitionNotAllowed):
            wf.send("publish")

    def test_async_with_db_operation(self, one):
        """Regression test for https://github.com/fgmacedo/python-statemachine/issues/446"""

        user = User.objects.create_user("user")
        one.user = user
        one.save()

        wf = WorfklowStateMachine(one)
        wf.send("notify_user")

        # And clear model cache, casing user to be loaded later on
        one = Workflow.objects.get(pk=one.pk)
        wf = WorfklowStateMachine(one)
        wf.send("notify_user")
