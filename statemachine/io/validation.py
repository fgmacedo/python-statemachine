"""Optional JSON Schema validation for the native (JSON/YAML) statechart format.

Requires the optional ``[validation]`` extra (``jsonschema``). The schema itself is
shipped with the package at ``statemachine/io/schemas/statechart.schema.json`` and is
also published so editors/tools can reference it via ``$schema``.
"""

import json
from functools import lru_cache
from importlib.resources import files

from ..exceptions import InvalidDefinition

SCHEMA_RESOURCE = "statechart.schema.json"


@lru_cache(maxsize=1)
def load_schema() -> dict:
    """Load and cache the bundled statechart JSON Schema."""
    resource = files("statemachine.io").joinpath("schemas", SCHEMA_RESOURCE)
    return json.loads(resource.read_text(encoding="utf-8"))  # type: ignore[no-any-return]


def validate_document(doc) -> None:
    """Validate a parsed native document against the statechart JSON Schema.

    Raises:
        InvalidDefinition: if the document does not conform to the schema, or if the
            optional ``jsonschema`` dependency is not installed.
    """
    try:
        import jsonschema  # type: ignore[import-untyped]
    except ModuleNotFoundError as exc:  # pragma: no cover - exercised via import mock
        raise InvalidDefinition(
            "validate=True requires the 'jsonschema' package. Install it with: "
            'pip install "python-statemachine[validation]"'
        ) from exc

    try:
        jsonschema.validate(instance=doc, schema=load_schema())
    except jsonschema.ValidationError as exc:
        raise InvalidDefinition(
            f"Statechart document failed schema validation: {exc.message}"
        ) from exc
