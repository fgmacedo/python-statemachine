"""Format ports & adapters: the reader Protocol and the format registry.

A :class:`FormatReader` is the *port* every format adapter implements: it turns
raw text into the neutral IR (:class:`~statemachine.io.model.StateMachineDefinition`).
Each format also declares which file extensions it owns and which processor builds
its IR into a :class:`~statemachine.statemachine.StateChart` class.

Adapters register themselves with :func:`register_format` (see the ``scxml``,
``json`` and ``yaml`` reader modules). The high-level :func:`statemachine.io.load`
facade uses :func:`detect_format` and :func:`get_format` to wire everything up.
"""

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from typing import Protocol
from typing import runtime_checkable

from .model import StateMachineDefinition


@runtime_checkable
class FormatReader(Protocol):
    """A format adapter: parses text of one format into the neutral IR."""

    def read(
        self, text: str, *, source_name: "str | None" = None
    ) -> StateMachineDefinition:  # pragma: no cover - structural Protocol
        ...


@dataclass(frozen=True)
class FormatSpec:
    """Describes a supported serialization format.

    The runtime is the format-neutral :class:`~statemachine.io.interpreter.Interpreter`;
    a format only needs to provide a reader (text -> neutral IR).

    Args:
        name: the canonical format name (e.g. ``"scxml"``, ``"json"``, ``"yaml"``).
        extensions: file extensions (with leading dot) that map to this format.
        reader_factory: builds a :class:`FormatReader` for this format.
    """

    name: str
    extensions: "tuple[str, ...]"
    reader_factory: "Callable[..., Any]"


_FORMATS: "dict[str, FormatSpec]" = {}
_EXTENSIONS: "dict[str, str]" = {}


def register_format(spec: FormatSpec) -> None:
    """Register a format spec, indexing it by name and by each of its extensions."""
    _FORMATS[spec.name] = spec
    for ext in spec.extensions:
        _EXTENSIONS[ext] = spec.name


def get_format(name: str) -> FormatSpec:
    """Return the :class:`FormatSpec` registered under ``name``."""
    try:
        return _FORMATS[name]
    except KeyError:
        available = ", ".join(sorted(_FORMATS)) or "(none registered)"
        raise ValueError(f"Unknown format: {name!r}. Available formats: {available}.") from None


def detect_format(path: Path, explicit: "str | None" = None) -> str:
    """Resolve the format name from an explicit override or the file extension."""
    if explicit is not None:
        return explicit
    ext = path.suffix.lower()
    try:
        return _EXTENSIONS[ext]
    except KeyError:
        known = ", ".join(sorted(_EXTENSIONS)) or "(none registered)"
        raise ValueError(
            f"Cannot detect format from extension {ext!r}. Known extensions: "
            f"{known}. Pass an explicit format=... argument."
        ) from None
