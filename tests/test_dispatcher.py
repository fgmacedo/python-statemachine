import pytest

from statemachine.dispatcher import ObjectConfig
from statemachine.dispatcher import resolver_factory
from statemachine.dispatcher import search_callable


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
        actual = next(search_callable(expected)).wrap()
        assert actual.__name__ == expected.__name__
        assert actual.__doc__ == expected.__doc__

    def test_retrieve_a_method_from_its_name(self, args, kwargs):
        model = Person("Frodo", "Bolseiro")
        expected = model.get_full_name
        method = next(search_callable("get_full_name", ObjectConfig.from_obj(model))).wrap()

        assert method.__name__ == expected.__name__
        assert method.__doc__ == expected.__doc__
        assert method(*args, **kwargs) == "Frodo Bolseiro"

    def test_retrieve_a_callable_from_a_property_name(self, args, kwargs):
        model = Person("Frodo", "Bolseiro")
        method = next(search_callable("first_name", ObjectConfig.from_obj(model))).wrap()

        assert method(*args, **kwargs) == "Frodo"

    def test_retrieve_callable_from_a_property_name_that_should_keep_reference(self, args, kwargs):
        model = Person("Frodo", "Bolseiro")
        method = next(search_callable("first_name", ObjectConfig.from_obj(model))).wrap()

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

        resolver = resolver_factory(org, person)
        resolved_method = next(resolver(attr)).wrap()
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

        org_config = ObjectConfig.from_obj(org, {"get_full_name"})

        resolver = resolver_factory(org_config, person)
        resolved_method = next(resolver(attr)).wrap()
        assert resolved_method() == expected_value
