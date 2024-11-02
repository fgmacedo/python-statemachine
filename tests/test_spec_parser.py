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


def test_simple_or():
    expr = "frodo_has_ring or sauron_alive"
    parsed_expr = parse_boolean_expr(expr, variable_hook, operator_mapping)
    assert parsed_expr() is True  # frodo_has_ring is True


def test_simple_and():
    expr = "frodo_has_ring and gandalf_present"
    parsed_expr = parse_boolean_expr(expr, variable_hook, operator_mapping)
    assert parsed_expr() is True  # both frodo_has_ring and gandalf_present are True


def test_not_operator():
    expr = "not sauron_alive"
    parsed_expr = parse_boolean_expr(expr, variable_hook, operator_mapping)
    assert parsed_expr() is True  # sauron_alive is False, so not makes it True


def test_combined_and_or():
    expr = "frodo_has_ring and (gandalf_present or sauron_alive)"
    parsed_expr = parse_boolean_expr(expr, variable_hook, operator_mapping)
    assert (
        parsed_expr() is True
    )  # (gandalf_present or sauron_alive) is True, frodo_has_ring is True


def test_not_expression_with_and():
    expr = "not sauron_alive and orc_army_ready"
    parsed_expr = parse_boolean_expr(expr, variable_hook, operator_mapping)
    assert parsed_expr() is False  # False due to orc_army_ready


def test_negating_compound_false_expression():
    expr = "not (not sauron_alive and orc_army_ready)"
    parsed_expr = parse_boolean_expr(expr, variable_hook, operator_mapping)
    assert parsed_expr() is True
    assert parsed_expr.__name__ == "not((not(sauron_alive) and orc_army_ready))"


def test_complex_expression():
    expr = "(frodo_has_ring and sam_is_loyal) or (not sauron_alive and orc_army_ready)"
    parsed_expr = parse_boolean_expr(expr, variable_hook, operator_mapping)
    assert parsed_expr() is True  # first part is True; second part is False due to orc_army_ready


def test_double_not_expression():
    expr = "not (not frodo_has_ring)"
    parsed_expr = parse_boolean_expr(expr, variable_hook, operator_mapping)
    assert parsed_expr() is True  # double negation, frodo_has_ring is True


def test_not_and_combination():
    expr = "frodo_has_ring and not orc_army_ready"
    parsed_expr = parse_boolean_expr(expr, variable_hook, operator_mapping)
    assert parsed_expr() is True  # frodo_has_ring is True, orc_army_ready is False


def test_nested_expression():
    expr = "frodo_has_ring and (sam_is_loyal or (gandalf_present and not sauron_alive))"
    parsed_expr = parse_boolean_expr(expr, variable_hook, operator_mapping)
    assert parsed_expr() is True  # all conditions within the parentheses are True
    assert (
        parsed_expr.__name__
        == "(frodo_has_ring and (sam_is_loyal or (gandalf_present and not(sauron_alive))))"
    )


def test_or_with_all_false():
    expr = "sauron_alive or orc_army_ready"
    parsed_expr = parse_boolean_expr(expr, variable_hook, operator_mapping)
    assert parsed_expr() is False  # both variables are False


def test_and_with_all_false():
    expr = "sauron_alive and orc_army_ready"
    parsed_expr = parse_boolean_expr(expr, variable_hook, operator_mapping)
    assert parsed_expr() is False  # both variables are False


def test_mixed_truth_values():
    expr = "(frodo_has_ring and gandalf_present) or orc_army_ready"
    parsed_expr = parse_boolean_expr(expr, variable_hook, operator_mapping)
    assert parsed_expr() is True  # first part is True, so expression is True


def test_expression_name_uniqueness():
    expr = "frodo_has_ring or not orc_army_ready"
    parsed_expr = parse_boolean_expr(expr, variable_hook, operator_mapping)
    assert (
        parsed_expr.__name__ == "(frodo_has_ring or not(orc_army_ready))"
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
    # Define an unsupported operator like XOR
    expr = "frodo_has_ring ^ gandalf_present"
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
