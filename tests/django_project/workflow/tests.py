import pytest

from statemachine.exceptions import TransitionNotAllowed
from workflow.models import WorkflowSteps
from workflow.statemachines import WorfklowStateMachine

pytestmark = [
    pytest.mark.django_db,
]


@pytest.fixture()
def Workflow():
    from workflow.models import Workflow

    return Workflow


@pytest.fixture()
def User():
    from django.contrib.auth import get_user_model

    return get_user_model()


@pytest.fixture()
def one(Workflow):
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

    def test_async_with_db_operation(self, one, User, Workflow):
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

    def test_should_publish(self, one):
        one.is_active = True
        one.publish()
        one.save()

        assert one.state == "published"
        assert one.wf.current_state_value == "published"
        assert one.wf.current_state_value == WorkflowSteps.PUBLISHED
