import pytest

from statemachine.callbacks import CallbackGroup
from statemachine.callbacks import CallbackSpec
from statemachine.dispatcher import Listener
from statemachine.dispatcher import Listeners
from statemachine.dispatcher import resolver_factory_from_objects
from statemachine.exceptions import InvalidDefinition
from statemachine.state import State
from statemachine.statemachine import StateMachine


def _take_first_callable(iterable):
    _key, builder = next(iterable)
    return builder()


class Person:
    def __init__(self, first_name, last_name, legal_document=None):
        self.first_name = first_name
        self.last_name = last_name
        self.legal_document = legal_document

    def get_full_name(self):
        return f"{self.first_name} {self.last_name}"


class Organization:
    def __init__(self, name, legal_document):
        self.name = name
        self.legal_document = legal_document

    def get_full_name(self):
        return self.name


class TestEnsureCallable:
    @pytest.fixture(
        params=[
            pytest.param([], id="no-args"),
            pytest.param([24, True, "Go!"], id="with-args"),
        ]
    )
    def args(self, request):
        return request.param

    @pytest.fixture(
        params=[
            pytest.param({}, id="no-kwargs"),
            pytest.param({"a": "x", "b": "y"}, id="with-kwargs"),
        ]
    )
    def kwargs(self, request):
        return request.param

    def test_return_same_object_if_already_a_callable(self):
        model = Person("Frodo", "Bolseiro")
        expected = model.get_full_name
        actual = _take_first_callable(
            resolver_factory_from_objects([]).search(
                CallbackSpec(model.get_full_name, group=CallbackGroup.ON)
            )
        )
        assert actual.__name__ == expected.__name__
        assert actual.__doc__ == expected.__doc__

    def test_retrieve_a_method_from_its_name(self, args, kwargs):
        model = Person("Frodo", "Bolseiro")
        expected = model.get_full_name
        method = _take_first_callable(
            Listeners.from_listeners([Listener.from_obj(model)]).search(
                CallbackSpec("get_full_name", group=CallbackGroup.ON),
            )
        )

        assert method.__name__ == expected.__name__
        assert method.__doc__ == expected.__doc__
        assert method(*args, **kwargs) == "Frodo Bolseiro"

    def test_retrieve_a_callable_from_a_property_name(self, args, kwargs):
        model = Person("Frodo", "Bolseiro")

        method = _take_first_callable(
            Listeners.from_listeners([Listener.from_obj(model)]).search(
                CallbackSpec("first_name", group=CallbackGroup.ON),
            )
        )

        assert method(*args, **kwargs) == "Frodo"

    def test_retrieve_callable_from_a_property_name_that_should_keep_reference(self, args, kwargs):
        model = Person("Frodo", "Bolseiro")

        method = _take_first_callable(
            Listeners.from_listeners([Listener.from_obj(model)]).search(
                CallbackSpec("first_name", group=CallbackGroup.ON),
            )
        )

        model.first_name = "Bilbo"

        assert method(*args, **kwargs) == "Bilbo"


class TestResolverFactory:
    @pytest.mark.parametrize(
        ("attr", "expected_value"),
        [
            ("first_name", "Frodo"),
            ("last_name", "Bolseiro"),
            ("legal_document", "cnpj"),
            ("get_full_name", "The Lord fo the Rings"),
        ],
    )
    def test_should_chain_resolutions(self, attr, expected_value):
        person = Person("Frodo", "Bolseiro", "cpf")
        org = Organization("The Lord fo the Rings", "cnpj")

        resolver = resolver_factory_from_objects(org, person)
        resolved_method = _take_first_callable(
            resolver.search(CallbackSpec(attr, group=CallbackGroup.ON))
        )
        assert resolved_method() == expected_value

    @pytest.mark.parametrize(
        ("attr", "expected_value"),
        [
            ("first_name", "Frodo"),
            ("last_name", "Bolseiro"),
            ("legal_document", "cnpj"),
            ("get_full_name", "Frodo Bolseiro"),
        ],
    )
    def test_should_ignore_list_of_attrs(self, attr, expected_value):
        person = Person("Frodo", "Bolseiro", "cpf")
        org = Organization("The Lord fo the Rings", "cnpj")

        org_config = Listener.from_obj(org, {"get_full_name"})

        resolver = resolver_factory_from_objects(org_config, person)
        resolved_method = _take_first_callable(
            resolver.search(CallbackSpec(attr, group=CallbackGroup.ON))
        )
        assert resolved_method() == expected_value


class TestSearchProperty:
    def test_not_found_property_with_same_name(self):
        class StrangeObject:
            @property
            def can_change_to_start(self):
                return False

        class StartMachine(StateMachine):
            created = State(initial=True)
            started = State(final=True)

            start = created.to(started, cond=StrangeObject.can_change_to_start)

            def can_change_to_start(self):
                return True

        with pytest.raises(InvalidDefinition, match="not found name"):
            StartMachine()
