"""High-level, format-neutral facade for loading statecharts.

:func:`load` is the simple entry point: give it a file path (format detected by
extension) or inline content (with an explicit ``format=``) and it returns the
ready-to-instantiate :class:`~statemachine.statemachine.StateChart` class. It is
**secure by default** — expressions are evaluated by a restricted AST-whitelist
evaluator and ``<script>`` / arbitrary Python is rejected unless ``trusted=True``.

For advanced scenarios (a document declaring several statecharts, or SCXML files
that import/invoke others), use :func:`build_processor` to get the underlying
processor and reach ``.scs`` / ``.start()``.
"""

import os
from contextlib import contextmanager
from pathlib import Path
from typing import cast

from ..statemachine import StateChart
from .evaluators import evaluator_for
from .interpreter import Interpreter
from .json import reader as _json_reader  # noqa: F401
from .ports import detect_format
from .ports import get_format

# Importing the reader modules registers their formats (extensions). None of these
# imports pulls in PyYAML or jsonschema at module load time.
from .scxml import reader as _scxml_reader  # noqa: F401
from .yaml import reader as _yaml_reader  # noqa: F401


@contextmanager
def _chdir(new_dir: Path):
    original = os.getcwd()
    try:
        os.chdir(new_dir)
        yield
    finally:
        os.chdir(original)


def _resolve_source(source: "str | Path", format: "str | None"):
    """Return ``(text, format_name, location_hint, base_dir)`` for a source.

    A :class:`~pathlib.Path`, or a single-line string naming an existing file, is
    read from disk (format detected by extension unless overridden). Any other
    string is treated as inline content and requires an explicit ``format``.
    """
    if isinstance(source, Path):
        path: "Path | None" = source
    elif "\n" not in source and Path(source).is_file():
        path = Path(source)
    else:
        path = None

    if path is not None:
        text = path.read_text()
        fmt = detect_format(path, format)
        return text, fmt, path.stem, path.parent

    fmt = detect_format(Path("<inline>"), format)
    return source, fmt, None, None


def _build(source, *, format, trusted, validate, name):
    """Shared pipeline: read source -> IR -> interpreter (returns ``(interpreter, location)``)."""
    text, fmt, location_hint, base_dir = _resolve_source(source, format)
    spec = get_format(fmt)
    reader = spec.reader_factory()

    parse_document = getattr(reader, "parse_document", None)
    if validate and parse_document is None:
        raise ValueError(
            f"validate=True is not supported for the {fmt!r} format; "
            "validation applies to the native JSON/YAML schema."
        )

    def _read_and_build():
        # Parsing and compilation both run here, inside the file's directory when loading
        # from a file, so a reader that resolves external references (e.g. SCXML
        # ``<data src="...">``) and invoke ``src`` resolve relative to the document.
        if parse_document is not None:
            doc = parse_document(text)
            if validate:
                from .validation import validate_document

                validate_document(doc)
            from .native import native_dict_to_definition

            definition = native_dict_to_definition(doc, source_name=name or location_hint)
        else:
            definition = reader.read(text, source_name=name or location_hint)

        location = name or definition.name or location_hint or "statechart"
        # The runtime is the format-neutral Interpreter, wired with this format's reader
        # (so invoked children compile in the same format) and the chosen evaluator.
        interpreter = Interpreter(reader=reader, evaluator=evaluator_for(trusted))
        interpreter.process_definition(definition, location=location)
        return interpreter, location

    if base_dir is not None:
        with _chdir(base_dir):
            return _read_and_build()
    return _read_and_build()


def build_processor(
    source: "str | Path",
    *,
    format: "str | None" = None,
    trusted: bool = False,
    validate: bool = False,
    name: "str | None" = None,
):
    """Load a statechart and return the underlying interpreter (low-level API).

    Returns the :class:`~statemachine.io.interpreter.Interpreter`. Use it when you need
    access to ``interpreter.scs`` (all compiled classes) or ``interpreter.start(...)`` —
    e.g. documents that invoke/import children. See :func:`load` for the argument semantics.
    """
    interpreter, _location = _build(
        source, format=format, trusted=trusted, validate=validate, name=name
    )
    return interpreter


def load(
    source: "str | Path",
    *,
    format: "str | None" = None,
    trusted: bool = False,
    validate: bool = False,
    name: "str | None" = None,
) -> "type[StateChart]":
    """Load a statechart from a file or inline content and return its class.

    Args:
        source: a file path (``str``/:class:`~pathlib.Path`; format detected from
            the extension) or inline document content (requires ``format``).
        format: explicit format name (``"scxml"``, ``"json"``, ``"yaml"``),
            overriding extension detection and required for inline content.
        trusted: when ``False`` (default), expressions are evaluated by a restricted
            AST-whitelist evaluator and ``<script>`` / arbitrary Python is rejected.
            When ``True``, expressions and scripts are evaluated as arbitrary Python.
        validate: when ``True`` (native JSON/YAML only), validate the document against
            the published JSON Schema before building (requires the ``[validation]``
            extra).
        name: explicit name for the generated class (defaults to the document name
            or the file stem).

    Returns:
        The :class:`~statemachine.statemachine.StateChart` subclass. Instantiate it
        to run the machine (``load("m.yaml")()``).
    """
    interpreter, location = _build(
        source, format=format, trusted=trusted, validate=validate, name=name
    )
    cls = interpreter.scs[location]
    # Keep the interpreter reachable (and alive) from the returned class.
    cls._io_processor = interpreter
    return cast("type[StateChart]", cls)
