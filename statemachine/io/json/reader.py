"""JSON format adapter: parse a JSON statechart document into the neutral IR."""

import json

from ..model import StateMachineDefinition
from ..native import native_dict_to_definition
from ..ports import FormatSpec
from ..ports import register_format


class JSONReader:
    """Format adapter that parses JSON documents (stdlib :mod:`json`) into the IR."""

    def parse_document(self, text: str) -> dict:
        return json.loads(text)  # type: ignore[no-any-return]

    def read(self, text: str, *, source_name: "str | None" = None) -> StateMachineDefinition:
        return native_dict_to_definition(self.parse_document(text), source_name=source_name)


register_format(
    FormatSpec(
        name="json",
        extensions=(".json",),
        reader_factory=JSONReader,
    )
)
