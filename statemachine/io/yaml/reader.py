"""YAML format adapter: parse a YAML statechart document into the neutral IR.

Requires the optional ``[yaml]`` extra (PyYAML). YAML is always parsed with
``yaml.safe_load`` semantics so a document can never instantiate arbitrary Python
objects.
"""

from ..model import StateMachineDefinition
from ..native import native_dict_to_definition
from ..ports import FormatSpec
from ..ports import register_format

_LOADER = None


def _make_loader(yaml):
    """Build a SafeLoader that does NOT coerce ``on``/``off``/``yes``/``no`` to bool.

    YAML 1.1 turns those tokens into booleans, which silently mangles state ids
    like ``off``/``on`` into ``True``/``False``. We keep ``yaml.safe_load``'s safety
    but restrict the implicit bool resolver to ``true``/``false`` only.
    """
    global _LOADER
    if _LOADER is not None:
        return _LOADER

    class _StatechartSafeLoader(yaml.SafeLoader):
        pass

    _StatechartSafeLoader.yaml_implicit_resolvers = {
        first_char: [
            (tag, regexp)
            for (tag, regexp) in resolvers
            if not (tag == "tag:yaml.org,2002:bool" and first_char not in "tTfF")
        ]
        for first_char, resolvers in yaml.SafeLoader.yaml_implicit_resolvers.items()
    }
    _LOADER = _StatechartSafeLoader
    return _LOADER


class YAMLReader:
    """Format adapter that parses YAML documents (``yaml.safe_load``) into the IR."""

    def parse_document(self, text: str) -> dict:
        try:
            import yaml  # type: ignore[import-untyped]
        except ModuleNotFoundError as exc:  # pragma: no cover - exercised via import mock
            raise ImportError(
                "YAML support requires PyYAML. Install it with: "
                'pip install "python-statemachine[yaml]"'
            ) from exc
        return yaml.load(text, Loader=_make_loader(yaml))  # type: ignore[no-any-return]

    def read(self, text: str, *, source_name: "str | None" = None) -> StateMachineDefinition:
        return native_dict_to_definition(self.parse_document(text), source_name=source_name)


register_format(
    FormatSpec(
        name="yaml",
        extensions=(".yaml", ".yml"),
        reader_factory=YAMLReader,
    )
)
