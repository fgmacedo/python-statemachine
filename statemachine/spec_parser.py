import ast
import operator
import re
from collections.abc import Callable
from functools import reduce
from inspect import isawaitable

replacements = {"!": "not ", "^": " and ", "v": " or "}

pattern = re.compile(r"\!(?!=)|\^|\bv\b")

comparison_repr = {
    operator.eq: "==",
    operator.ne: "!=",
    operator.gt: ">",
    operator.ge: ">=",
    operator.lt: "<",
    operator.le: "<=",
}


def _unique_key(left, right, operator) -> str:
    left_key = getattr(left, "unique_key", "")
    right_key = getattr(right, "unique_key", "")
    return f"{left_key} {operator} {right_key}"


def replace_operators(expr: str) -> str:
    # preprocess the expression adding support for classical logical operators
    def match_func(match):
        return replacements[match.group(0)]

    return pattern.sub(match_func, expr)


def custom_not(predicate: Callable) -> Callable:
    def decorated(*args, **kwargs):
        result = predicate(*args, **kwargs)
        if isawaitable(result):

            async def _negate():
                return not await result

            return _negate()
        return not result

    decorated.__name__ = f"not({predicate.__name__})"
    unique_key = getattr(predicate, "unique_key", "")
    decorated.unique_key = f"not({unique_key})"  # type: ignore[attr-defined]
    return decorated


def custom_and(left: Callable, right: Callable) -> Callable:
    def decorated(*args, **kwargs):
        left_result = left(*args, **kwargs)
        if isawaitable(left_result):

            async def _async_and():
                lr = await left_result
                if not lr:
                    return lr
                rr = right(*args, **kwargs)
                if isawaitable(rr):
                    return await rr
                return rr

            return _async_and()
        if not left_result:
            return left_result
        right_result = right(*args, **kwargs)
        if isawaitable(right_result):
            return right_result
        return right_result

    decorated.__name__ = f"({left.__name__} and {right.__name__})"
    decorated.unique_key = _unique_key(left, right, "and")  # type: ignore[attr-defined]
    return decorated


def custom_or(left: Callable, right: Callable) -> Callable:
    def decorated(*args, **kwargs):
        left_result = left(*args, **kwargs)
        if isawaitable(left_result):

            async def _async_or():
                lr = await left_result
                if lr:
                    return lr
                rr = right(*args, **kwargs)
                if isawaitable(rr):
                    return await rr
                return rr

            return _async_or()
        if left_result:
            return left_result
        right_result = right(*args, **kwargs)
        if isawaitable(right_result):
            return right_result
        return right_result

    decorated.__name__ = f"({left.__name__} or {right.__name__})"
    decorated.unique_key = _unique_key(left, right, "or")  # type: ignore[attr-defined]
    return decorated


def build_constant(constant) -> Callable:
    def decorated(*args, **kwargs):
        return constant

    decorated.__name__ = str(constant)
    decorated.unique_key = str(constant)  # type: ignore[attr-defined]
    return decorated


class Functions:
    registry: dict[str, Callable] = {}

    @classmethod
    def register(cls, id) -> Callable:
        def register(func):
            cls.registry[id] = func
            return func

        return register

    @classmethod
    def get(cls, func_id):
        func_id = func_id.lower()
        if func_id not in cls.registry:
            raise ValueError(f"Unsupported function: {func_id}")
        return cls.registry[func_id]


class InState:
    def __init__(self, machine):
        self.machine = machine

    def __call__(self, *state_ids: str):
        return set(state_ids).issubset({s.id for s in self.machine.configuration})


@Functions.register("in")
def build_in_call(*state_ids: str) -> Callable:
    state_ids_set = set(state_ids)

    def decorated(*args, **kwargs):
        machine = kwargs["machine"]
        return InState(machine)(*state_ids)

    decorated.__name__ = f"in({state_ids_set})"
    decorated.unique_key = f"in({state_ids_set})"  # type: ignore[attr-defined]
    return decorated


def build_custom_operator(operator) -> Callable:
    operator_repr = comparison_repr[operator]

    def custom_comparator(left: Callable, right: Callable) -> Callable:
        def decorated(*args, **kwargs):
            left_result = left(*args, **kwargs)
            right_result = right(*args, **kwargs)
            if isawaitable(left_result) or isawaitable(right_result):

                async def _async_compare():
                    lr = (await left_result) if isawaitable(left_result) else left_result
                    rr = (await right_result) if isawaitable(right_result) else right_result
                    return bool(operator(lr, rr))

                return _async_compare()
            return bool(operator(left_result, right_result))

        decorated.__name__ = f"({left.__name__} {operator_repr} {right.__name__})"
        decorated.unique_key = _unique_key(left, right, operator_repr)  # type: ignore[attr-defined]
        return decorated

    return custom_comparator


def build_binop(op_fn, left: Callable, right: Callable) -> Callable:
    def decorated(*args, **kwargs):
        return op_fn(left(*args, **kwargs), right(*args, **kwargs))

    decorated.__name__ = f"({left.__name__} {op_fn.__name__} {right.__name__})"
    return decorated


def build_unaryop(op_fn, operand: Callable) -> Callable:
    def decorated(*args, **kwargs):
        return op_fn(operand(*args, **kwargs))

    decorated.__name__ = f"{op_fn.__name__}({operand.__name__})"
    return decorated


def build_collection(factory, item_exprs: "list[Callable]") -> Callable:
    def decorated(*args, **kwargs):
        return factory(item(*args, **kwargs) for item in item_exprs)

    decorated.__name__ = f"{factory.__name__}(...)"
    return decorated


def build_dict(key_exprs: "list[Callable]", value_exprs: "list[Callable]") -> Callable:
    def decorated(*args, **kwargs):
        return {
            key(*args, **kwargs): value(*args, **kwargs)
            for key, value in zip(key_exprs, value_exprs, strict=True)
        }

    decorated.__name__ = "dict(...)"
    return decorated


def build_subscript(value_expr: Callable, slice_expr: Callable) -> Callable:
    def decorated(*args, **kwargs):
        return value_expr(*args, **kwargs)[slice_expr(*args, **kwargs)]

    decorated.__name__ = f"{value_expr.__name__}[{slice_expr.__name__}]"
    return decorated


def build_attribute(value_expr: Callable, attr: str) -> Callable:
    def decorated(*args, **kwargs):
        return getattr(value_expr(*args, **kwargs), attr)

    decorated.__name__ = f"{value_expr.__name__}.{attr}"
    return decorated


def build_expression(  # noqa: C901
    node, variable_hook, operator_mapping, allow_value_nodes: bool = False
):
    """Build a callable from an AST node using a whitelist of allowed structures.

    Args:
        allow_value_nodes: when ``True``, value-producing structures (arithmetic,
            collections, subscript, attribute read) are also accepted. The DSL
            boolean-guard parser keeps this ``False`` so non-boolean expressions
            (e.g. ``a * b``, ``{}``) remain rejected; the SCXML datamodel parser
            (:func:`parse_expr`) sets it ``True``.
    """

    def recurse(child):
        return build_expression(child, variable_hook, operator_mapping, allow_value_nodes)

    match node:
        case ast.BoolOp():
            # `and` / `or` operations
            operator_fn = operator_mapping[type(node.op)]
            left_expr = recurse(node.values[0])
            for right in node.values[1:]:
                right_expr = recurse(right)
                left_expr = operator_fn(left_expr, right_expr)
            return left_expr
        case ast.Compare():
            # `==` / `!=` / `>` / `<` / `>=` / `<=` operations
            expressions = []
            left_expr = recurse(node.left)
            for right_op, right in zip(node.ops, node.comparators, strict=True):
                right_expr = recurse(right)
                operator_fn = operator_mapping[type(right_op)]
                expression = operator_fn(left_expr, right_expr)
                left_expr = right_expr
                expressions.append(expression)
            return reduce(custom_and, expressions)
        case ast.Call(func=ast.Name(id=func_id)):
            # Only whitelisted functions from the registry (e.g. ``In(...)``) are
            # callable. Method calls (``obj.method()``) have an ``ast.Attribute``
            # func and fall through to the ``case _`` guard below — this prevents
            # using calls as a sandbox-escape vector.
            constructor = Functions.get(func_id)
            params = [arg.value for arg in node.args if isinstance(arg, ast.Constant)]
            return constructor(*params)
        case ast.UnaryOp(op=ast.Not()):
            return operator_mapping[type(node.op)](recurse(node.operand))
        case ast.UnaryOp(op=(ast.USub() | ast.UAdd())) if allow_value_nodes:
            return build_unaryop(unary_operators[type(node.op)], recurse(node.operand))
        case ast.BinOp() if allow_value_nodes and type(node.op) in binary_operators:
            return build_binop(
                binary_operators[type(node.op)], recurse(node.left), recurse(node.right)
            )
        case ast.List(elts=elts) if allow_value_nodes:
            return build_collection(list, [recurse(e) for e in elts])
        case ast.Tuple(elts=elts) if allow_value_nodes:
            return build_collection(tuple, [recurse(e) for e in elts])
        case ast.Set(elts=elts) if allow_value_nodes:
            return build_collection(set, [recurse(e) for e in elts])
        case ast.Dict(keys=keys, values=values) if allow_value_nodes and all(
            key is not None for key in keys
        ):
            # ``key is not None`` rejects dict unpacking (``{**other}``), whose key
            # node is ``None``.
            return build_dict([recurse(key) for key in keys], [recurse(value) for value in values])
        case ast.Subscript() if allow_value_nodes:
            return build_subscript(recurse(node.value), recurse(node.slice))
        case ast.Attribute(attr=attr) if allow_value_nodes:
            # Block dunder/private attribute access (``__class__``, ``__globals__``,
            # ...), the classic sandbox-escape chain. Subscript is allowed because,
            # without underscore-attribute access or method calls, it cannot reach
            # type objects.
            if attr.startswith("_"):
                raise ValueError(f"Attribute access to '{attr}' is not allowed")
            return build_attribute(recurse(node.value), attr)
        case ast.Name(id=name):
            return variable_hook(name)
        case ast.Constant(value=value):
            return build_constant(value)
        case _:
            raise ValueError(f"Unsupported expression structure: {node.__class__.__name__}")


def parse_boolean_expr(expr, variable_hook, operator_mapping):
    """Parses the expression into an AST and build a custom expression tree"""
    if expr.strip() == "":
        raise SyntaxError("Empty expression")

    # Optimization trying to avoid parsing the expression if not needed
    if "!" not in expr and " " not in expr and "In(" not in expr:
        return variable_hook(expr)
    expr = replace_operators(expr)
    tree = ast.parse(expr, mode="eval")
    return build_expression(tree.body, variable_hook, operator_mapping)


def parse_expr(expr: str, variable_hook: Callable) -> Callable:
    """Parse a value expression into a callable using the restricted AST whitelist.

    Unlike :func:`parse_boolean_expr`, this does not apply the DSL operator
    replacement (``!``/``^``/``v``) and does not coerce the top-level result to
    ``bool`` — it returns the raw evaluated value. Used to safely evaluate SCXML
    datamodel expressions (``<assign>``, ``<send>``, ``<foreach>``, ``<data>``)
    without :func:`eval`.

    Raises:
        ValueError: if the expression uses a structure outside the whitelist
            (e.g. attribute access to dunders, method calls, lambdas).
        SyntaxError: if the expression is empty or not valid Python.
    """
    if expr.strip() == "":
        raise SyntaxError("Empty expression")
    tree = ast.parse(expr, mode="eval")
    compiled: Callable = build_expression(
        tree.body, variable_hook, operator_mapping, allow_value_nodes=True
    )
    return compiled


operator_mapping = {
    ast.Or: custom_or,
    ast.And: custom_and,
    ast.Not: custom_not,
    ast.GtE: build_custom_operator(operator.ge),
    ast.Gt: build_custom_operator(operator.gt),
    ast.LtE: build_custom_operator(operator.le),
    ast.Lt: build_custom_operator(operator.lt),
    ast.Eq: build_custom_operator(operator.eq),
    ast.NotEq: build_custom_operator(operator.ne),
}

binary_operators = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
}

unary_operators = {
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
}
