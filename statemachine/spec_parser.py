import ast
import re
from typing import Callable

replacements = {"!": "not ", "^": " and ", "v": " or "}

pattern = re.compile(r"\!|\^|\bv\b")


def replace_operators(expr: str) -> str:
    # preprocess the expression adding support for classical logical operators
    def match_func(match):
        return replacements[match.group(0)]

    return pattern.sub(match_func, expr)


def custom_not(predicate: Callable) -> Callable:
    def decorated(*args, **kwargs) -> bool:
        return not predicate(*args, **kwargs)

    decorated.__name__ = f"not({predicate.__name__})"
    unique_key = getattr(predicate, "unique_key", "")
    decorated.unique_key = f"not({unique_key})"  # type: ignore[attr-defined]
    return decorated


def _unique_key(left, right, operator) -> str:
    left_key = getattr(left, "unique_key", "")
    right_key = getattr(right, "unique_key", "")
    return f"{left_key} {operator} {right_key}"


def custom_and(left: Callable, right: Callable) -> Callable:
    def decorated(*args, **kwargs) -> bool:
        return left(*args, **kwargs) and right(*args, **kwargs)  # type: ignore[no-any-return]

    decorated.__name__ = f"({left.__name__} and {right.__name__})"
    decorated.unique_key = _unique_key(left, right, "and")  # type: ignore[attr-defined]
    return decorated


def custom_or(left: Callable, right: Callable) -> Callable:
    def decorated(*args, **kwargs) -> bool:
        return left(*args, **kwargs) or right(*args, **kwargs)  # type: ignore[no-any-return]

    decorated.__name__ = f"({left.__name__} or {right.__name__})"
    decorated.unique_key = _unique_key(left, right, "or")  # type: ignore[attr-defined]
    return decorated


def build_expression(node, variable_hook, operator_mapping):
    if isinstance(node, ast.BoolOp):
        # Handle `and` / `or` operations
        operator_fn = operator_mapping[type(node.op)]
        left_expr = build_expression(node.values[0], variable_hook, operator_mapping)
        for right in node.values[1:]:
            right_expr = build_expression(right, variable_hook, operator_mapping)
            left_expr = operator_fn(left_expr, right_expr)
        return left_expr
    elif isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
        # Handle `not` operation
        operand_expr = build_expression(node.operand, variable_hook, operator_mapping)
        return operator_mapping[type(node.op)](operand_expr)
    elif isinstance(node, ast.Name):
        # Handle variables by calling the variable_hook
        return variable_hook(node.id)
    else:
        raise ValueError(f"Unsupported expression structure: {node.__class__.__name__}")


def parse_boolean_expr(expr, variable_hook, operator_mapping):
    """Parses the expression into an AST and build a custom expression tree"""
    expr = replace_operators(expr)
    tree = ast.parse(expr, mode="eval")
    return build_expression(tree.body, variable_hook, operator_mapping)


operator_mapping = {ast.Or: custom_or, ast.And: custom_and, ast.Not: custom_not}
