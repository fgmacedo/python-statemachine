import pytest

from statemachine.spec_parser import operator_mapping
from statemachine.spec_parser import parse_boolean_expr


def variable_hook(var_name):
    values = {
        "frodo_has_ring": True,
        "sauron_alive": False,
        "gandalf_present": True,
        "sam_is_loyal": True,
        "orc_army_ready": False,
    }

    def decorated(*args, **kwargs):
        return values.get(var_name, False)

    decorated.__name__ = var_name
    return decorated


@pytest.mark.parametrize(
    ("expression", "expected"),
    [
        ("frodo_has_ring", True),
        ("frodo_has_ring or sauron_alive", True),
        ("frodo_has_ring and gandalf_present", True),
        ("sauron_alive", False),
        ("not sauron_alive", True),
        ("frodo_has_ring and (gandalf_present or sauron_alive)", True),
        ("not sauron_alive and orc_army_ready", False),
        ("not (not sauron_alive and orc_army_ready)", True),
        ("(frodo_has_ring and sam_is_loyal) or (not sauron_alive and orc_army_ready)", True),
        ("(frodo_has_ring ^ sam_is_loyal) v (!sauron_alive ^ orc_army_ready)", True),
        ("not (not frodo_has_ring)", True),
        ("!(!frodo_has_ring)", True),
        ("frodo_has_ring and orc_army_ready", False),
        ("frodo_has_ring ^ orc_army_ready", False),
        ("frodo_has_ring and not orc_army_ready", True),
        ("frodo_has_ring ^ !orc_army_ready", True),
        ("frodo_has_ring and (sam_is_loyal or (gandalf_present and not sauron_alive))", True),
        ("frodo_has_ring ^ (sam_is_loyal v (gandalf_present ^ !sauron_alive))", True),
        ("sauron_alive or orc_army_ready", False),
        ("sauron_alive v orc_army_ready", False),
        ("(frodo_has_ring and gandalf_present) or orc_army_ready", True),
        ("orc_army_ready or (frodo_has_ring and gandalf_present)", True),
        ("orc_army_ready and (frodo_has_ring and gandalf_present)", False),
        ("!orc_army_ready and (frodo_has_ring and gandalf_present)", True),
        ("!orc_army_ready and !(frodo_has_ring and gandalf_present)", False),
    ],
)
def test_expressions(expression, expected):
    parsed_expr = parse_boolean_expr(expression, variable_hook, operator_mapping)
    assert parsed_expr() is expected, expression


def test_negating_compound_false_expression():
    expr = "not (not sauron_alive and orc_army_ready)"
    parsed_expr = parse_boolean_expr(expr, variable_hook, operator_mapping)
    assert parsed_expr() is True
    assert parsed_expr.__name__ == "not((not(sauron_alive) and orc_army_ready))"


def test_expression_name_uniqueness():
    expr = "frodo_has_ring or not orc_army_ready"
    parsed_expr = parse_boolean_expr(expr, variable_hook, operator_mapping)
    assert (
        parsed_expr.__name__ == "(frodo_has_ring or not(orc_army_ready))"
    )  # name reflects expression structure


def test_classical_operators_name():
    expr = "frodo_has_ring ^ !orc_army_ready"
    parsed_expr = parse_boolean_expr(expr, variable_hook, operator_mapping)
    assert parsed_expr() is True  # both parts are True
    assert (
        parsed_expr.__name__ == "(frodo_has_ring and not(orc_army_ready))"
    )  # name reflects expression structure


def test_empty_expression():
    expr = ""
    with pytest.raises(SyntaxError):
        parse_boolean_expr(expr, variable_hook, operator_mapping)


def test_whitespace_expression():
    expr = "   "
    with pytest.raises(SyntaxError):
        parse_boolean_expr(expr, variable_hook, operator_mapping)


def test_missing_operator_expression():
    expr = "frodo_has_ring orc_army_ready"
    with pytest.raises(SyntaxError):
        parse_boolean_expr(expr, variable_hook, operator_mapping)


def test_constant_usage_expression():
    expr = "frodo_has_ring or True"
    with pytest.raises(ValueError, match="Unsupported expression structure"):
        parse_boolean_expr(expr, variable_hook, operator_mapping)


def test_dict_usage_expression():
    expr = "frodo_has_ring or {}"
    with pytest.raises(ValueError, match="Unsupported expression structure"):
        parse_boolean_expr(expr, variable_hook, operator_mapping)


def test_unsupported_operator():
    # Define an unsupported operator like MUL
    expr = "frodo_has_ring * gandalf_present"
    with pytest.raises(ValueError, match="Unsupported expression structure"):
        parse_boolean_expr(expr, variable_hook, operator_mapping)


def test_simple_variable_returns_the_original_callback():
    def original_callback(*args, **kwargs):
        return True

    mapping = {"original": original_callback}

    def variable_hook(var_name):
        return mapping.get(var_name, None)

    expr = "original"
    parsed_expr = parse_boolean_expr(expr, variable_hook, operator_mapping)

    assert parsed_expr is original_callback
