import asyncio
import logging

import pytest

from statemachine.spec_parser import operator_mapping
from statemachine.spec_parser import parse_boolean_expr

logger = logging.getLogger(__name__)
DEBUG = logging.DEBUG


def variable_hook(var_name):
    values = {
        "frodo_has_ring": True,
        "sauron_alive": False,
        "gandalf_present": True,
        "sam_is_loyal": True,
        "orc_army_ready": False,
        "frodo_age": 50,
        "height": 1.75,
        "name": "Frodo",
        "aragorn_age": 87,
        "legolas_age": 2931,
        "gimli_age": 139,
        "ring_power": 100,
        "sword_power": 80,
        "bow_power": 75,
        "axe_power": 85,
    }

    def decorated(*args, **kwargs):
        logger.debug(f"variable_hook({var_name})")
        return values.get(var_name, False)

    decorated.__name__ = var_name
    return decorated


@pytest.mark.parametrize(
    ("expression", "expected", "hooks_called"),
    [
        ("frodo_has_ring", True, ["frodo_has_ring"]),
        ("frodo_has_ring or sauron_alive", True, ["frodo_has_ring"]),
        ("frodo_has_ring and gandalf_present", True, ["frodo_has_ring", "gandalf_present"]),
        ("sauron_alive", False, ["sauron_alive"]),
        ("not sauron_alive", True, ["sauron_alive"]),
        (
            "frodo_has_ring and (gandalf_present or sauron_alive)",
            True,
            ["frodo_has_ring", "gandalf_present"],
        ),
        ("not sauron_alive and orc_army_ready", False, ["sauron_alive", "orc_army_ready"]),
        ("not (not sauron_alive and orc_army_ready)", True, ["sauron_alive", "orc_army_ready"]),
        (
            "(frodo_has_ring and sam_is_loyal) or (not sauron_alive and orc_army_ready)",
            True,
            ["frodo_has_ring", "sam_is_loyal"],
        ),
        (
            "(frodo_has_ring ^ sam_is_loyal) v (!sauron_alive ^ orc_army_ready)",
            True,
            ["frodo_has_ring", "sam_is_loyal"],
        ),
        ("not (not frodo_has_ring)", True, ["frodo_has_ring"]),
        ("!(!frodo_has_ring)", True, ["frodo_has_ring"]),
        ("frodo_has_ring and orc_army_ready", False, ["frodo_has_ring", "orc_army_ready"]),
        ("frodo_has_ring ^ orc_army_ready", False, ["frodo_has_ring", "orc_army_ready"]),
        ("frodo_has_ring and not orc_army_ready", True, ["frodo_has_ring", "orc_army_ready"]),
        ("frodo_has_ring ^ !orc_army_ready", True, ["frodo_has_ring", "orc_army_ready"]),
        (
            "frodo_has_ring and (sam_is_loyal or (gandalf_present and not sauron_alive))",
            True,
            ["frodo_has_ring", "sam_is_loyal"],
        ),
        (
            "frodo_has_ring ^ (sam_is_loyal v (gandalf_present ^ !sauron_alive))",
            True,
            ["frodo_has_ring", "sam_is_loyal"],
        ),
        ("sauron_alive or orc_army_ready", False, ["sauron_alive", "orc_army_ready"]),
        ("sauron_alive v orc_army_ready", False, ["sauron_alive", "orc_army_ready"]),
        (
            "(frodo_has_ring and gandalf_present) or orc_army_ready",
            True,
            ["frodo_has_ring", "gandalf_present"],
        ),
        (
            "orc_army_ready or (frodo_has_ring and gandalf_present)",
            True,
            ["orc_army_ready", "frodo_has_ring", "gandalf_present"],
        ),
        ("orc_army_ready and (frodo_has_ring and gandalf_present)", False, ["orc_army_ready"]),
        (
            "!orc_army_ready and (frodo_has_ring and gandalf_present)",
            True,
            ["orc_army_ready", "frodo_has_ring", "gandalf_present"],
        ),
        (
            "!orc_army_ready and !(frodo_has_ring and gandalf_present)",
            False,
            ["orc_army_ready", "frodo_has_ring", "gandalf_present"],
        ),
        ("frodo_has_ring or True", True, ["frodo_has_ring"]),
        ("sauron_alive or True", True, ["sauron_alive"]),
        ("frodo_age >= 50", True, ["frodo_age"]),
        ("50 <= frodo_age", True, ["frodo_age"]),
        ("frodo_age <= 50", True, ["frodo_age"]),
        ("frodo_age == 50", True, ["frodo_age"]),
        ("frodo_age > 50", False, ["frodo_age"]),
        ("frodo_age < 50", False, ["frodo_age"]),
        ("frodo_age != 50", False, ["frodo_age"]),
        ("frodo_age != 49", True, ["frodo_age"]),
        ("49 < frodo_age < 51", True, ["frodo_age", "frodo_age"]),
        ("49 < frodo_age > 50", False, ["frodo_age", "frodo_age"]),
        (
            "aragorn_age < legolas_age < gimli_age",
            False,
            ["aragorn_age", "legolas_age", "legolas_age", "gimli_age"],
        ),  # 87 < 2931 and 2931 < 139
        (
            "gimli_age > aragorn_age < legolas_age",
            True,
            ["gimli_age", "aragorn_age", "aragorn_age", "legolas_age"],
        ),  # 139 > 87 and 87 < 2931
        (
            "sword_power < ring_power > bow_power",
            True,
            ["sword_power", "ring_power", "ring_power", "bow_power"],
        ),  # 80 < 100 and 100 > 75
        (
            "axe_power > sword_power == bow_power",
            False,
            ["axe_power", "sword_power", "sword_power", "bow_power"],
        ),  # 85 > 80 and 80 == 75
        ("name == 'Frodo'", True, ["name"]),
        ("name != 'Sam'", True, ["name"]),
        ("height == 1.75", True, ["height"]),
        ("height > 1 and height < 2", True, ["height", "height"]),
    ],
)
def test_expressions(expression, expected, caplog, hooks_called):
    caplog.set_level(logging.DEBUG, logger="tests")

    parsed_expr = parse_boolean_expr(expression, variable_hook, operator_mapping)
    assert parsed_expr() is expected, expression

    if hooks_called:
        assert caplog.record_tuples == [
            ("tests.test_spec_parser", DEBUG, f"variable_hook({hook})") for hook in hooks_called
        ]


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


@pytest.mark.parametrize(
    ("expression", "expected", "hooks_called"),
    [
        ("49 < frodo_age < 51", True, ["frodo_age"]),
        ("49 < frodo_age > 50", False, ["frodo_age"]),
        (
            "aragorn_age < legolas_age < gimli_age",
            False,
            ["aragorn_age", "legolas_age", "gimli_age"],
        ),  # 87 < 2931 and 2931 < 139
        (
            "gimli_age > aragorn_age < legolas_age",
            True,
            ["gimli_age", "aragorn_age", "legolas_age"],
        ),  # 139 > 87 and 87 < 2931
        (
            "sword_power < ring_power > bow_power",
            True,
            ["sword_power", "ring_power", "bow_power"],
        ),  # 80 < 100 and 100 > 75
        (
            "axe_power > sword_power == bow_power",
            False,
            ["axe_power", "sword_power", "bow_power"],
        ),  # 85 > 80 and 80 == 75
        ("height > 1 and height < 2", True, ["height"]),
    ],
)
def async_variable_hook(var_name):
    """Variable hook that returns async callables, for testing issue #535."""
    values = {
        "cond_true": True,
        "cond_false": False,
        "val_10": 10,
        "val_20": 20,
    }

    async def decorated(*args, **kwargs):
        return values.get(var_name, False)

    decorated.__name__ = var_name
    return decorated


@pytest.mark.parametrize(
    ("expression", "expected"),
    [
        ("not cond_false", True),
        ("not cond_true", False),
        ("cond_true and cond_true", True),
        ("cond_true and cond_false", False),
        ("cond_false and cond_true", False),
        ("cond_false or cond_true", True),
        ("cond_true or cond_false", True),
        ("cond_false or cond_false", False),
        ("not cond_false and cond_true", True),
        ("not (cond_true and cond_false)", True),
        ("not (cond_false or cond_false)", True),
        ("cond_true and not cond_false", True),
        ("val_10 == 10", True),
        ("val_10 != 20", True),
        ("val_10 < val_20", True),
        ("val_20 > val_10", True),
        ("val_10 >= 10", True),
        ("val_10 <= val_20", True),
    ],
)
def test_async_expressions(expression, expected):
    """Issue #535: condition expressions with async predicates must await results."""
    parsed_expr = parse_boolean_expr(expression, async_variable_hook, operator_mapping)
    result = parsed_expr()
    assert asyncio.iscoroutine(result), f"Expected coroutine for async expression: {expression}"
    assert asyncio.run(result) is expected, expression


def mixed_variable_hook(var_name):
    """Variable hook where some vars are sync and some are async."""
    sync_values = {"sync_true": True, "sync_false": False, "sync_10": 10}
    async_values = {"async_true": True, "async_false": False, "async_20": 20}

    if var_name in async_values:

        async def async_decorated(*args, **kwargs):
            return async_values[var_name]

        async_decorated.__name__ = var_name
        return async_decorated

    def sync_decorated(*args, **kwargs):
        return sync_values.get(var_name, False)

    sync_decorated.__name__ = var_name
    return sync_decorated


@pytest.mark.parametrize(
    ("expression", "expected"),
    [
        # async left, sync right
        ("async_true and sync_true", True),
        ("async_false or sync_true", True),
        # sync left, async right
        ("sync_true and async_true", True),
        ("sync_false or async_true", True),
        ("sync_true and async_false", False),
        ("sync_false or async_false", False),
    ],
)
def test_mixed_sync_async_expressions(expression, expected):
    """Expressions mixing sync and async predicates must handle both correctly."""
    parsed_expr = parse_boolean_expr(expression, mixed_variable_hook, operator_mapping)
    result = parsed_expr()
    if asyncio.iscoroutine(result):
        assert asyncio.run(result) is expected, expression
    else:
        assert result is expected, expression


@pytest.mark.xfail(reason="TODO: Optimize so that expressios are evaluated only once")
def test_should_evaluate_values_only_once(expression, expected, caplog, hooks_called):
    caplog.set_level(logging.DEBUG, logger="tests")

    parsed_expr = parse_boolean_expr(expression, variable_hook, operator_mapping)
    assert parsed_expr() is expected, expression

    if hooks_called:
        assert caplog.record_tuples == [
            ("tests.test_spec_parser", DEBUG, f"variable_hook({hook})") for hook in hooks_called
        ]
