"""Sphinx extension providing the ``statemachine-diagram`` directive.

Usage in MyST Markdown::

    ```{statemachine-diagram} mypackage.module.MyMachine
    :events: start, ship
    :caption: After shipping
    ```

The directive imports the state machine class, optionally instantiates it and
sends events, then renders an SVG diagram inline in the documentation.
"""

from __future__ import annotations

import hashlib
import html as html_mod
import os
import re
from typing import TYPE_CHECKING
from typing import Any
from typing import ClassVar

from docutils import nodes
from docutils.parsers.rst import directives
from sphinx.util.docutils import SphinxDirective

if TYPE_CHECKING:
    from sphinx.application import Sphinx


def _align_spec(argument: str) -> str:
    return str(directives.choice(argument, ("left", "center", "right")))


def _parse_events(value: str) -> list[str]:
    """Parse a comma-separated list of event names."""
    return [e.strip() for e in value.split(",") if e.strip()]


# Match the outer <svg ...>...</svg> element, stripping XML prologue/DOCTYPE.
_SVG_TAG_RE = re.compile(r"(<svg\b.*</svg>)", re.DOTALL)

# Match fixed width/height attributes (e.g. width="702pt" height="170pt").
_SVG_WIDTH_RE = re.compile(r'\bwidth="([^"]*(?:pt|px))"')
_SVG_HEIGHT_RE = re.compile(r'\bheight="([^"]*(?:pt|px))"')


class StateMachineDiagram(SphinxDirective):
    """Render a state machine diagram from an importable class path.

    Supports the same layout options as the standard ``image`` and ``figure``
    directives (``width``, ``height``, ``scale``, ``align``, ``target``,
    ``class``, ``name``), plus state-machine-specific options (``events``,
    ``caption``, ``figclass``).
    """

    has_content: ClassVar[bool] = False
    required_arguments: ClassVar[int] = 1
    optional_arguments: ClassVar[int] = 0
    option_spec: ClassVar[dict[str, Any]] = {
        # State-machine options
        "events": directives.unchanged,
        "format": directives.unchanged,
        # Standard image/figure options
        "caption": directives.unchanged,
        "alt": directives.unchanged,
        "width": directives.unchanged,
        "height": directives.unchanged,
        "scale": directives.unchanged,
        "align": _align_spec,
        "target": directives.unchanged,
        "class": directives.class_option,
        "name": directives.unchanged,
        "figclass": directives.class_option,
    }

    def run(self) -> list[nodes.Node]:
        qualname = self.arguments[0]

        try:
            from statemachine.contrib.diagram import formatter
            from statemachine.contrib.diagram import import_sm

            sm_class = import_sm(qualname)
        except (ImportError, ValueError) as exc:
            return [
                self.state_machine.reporter.warning(
                    f"statemachine-diagram: could not import {qualname!r}: {exc}",
                    line=self.lineno,
                )
            ]

        if "events" in self.options:
            machine = sm_class()
            for event_name in _parse_events(self.options["events"]):
                machine.send(event_name)
        else:
            machine = sm_class

        output_format = self.options.get("format", "").strip().lower()

        if output_format == "mermaid":
            return self._run_mermaid(machine, formatter, qualname)

        try:
            svg_text = formatter.render(machine, "svg")
        except Exception as exc:
            return [
                self.state_machine.reporter.warning(
                    f"statemachine-diagram: failed to generate diagram for {qualname!r}: {exc}",
                    line=self.lineno,
                )
            ]

        svg_tag, intrinsic_width, intrinsic_height = self._prepare_svg(svg_text)
        svg_styles = self._build_svg_styles(intrinsic_width, intrinsic_height)
        svg_tag = svg_tag.replace("<svg ", f"<svg {svg_styles} ", 1)

        alt_text = html_mod.escape(self.options.get("alt", qualname.rsplit(".", 1)[-1]))
        target = self._resolve_target(svg_text)

        img_html = f'<div role="img" aria-label="{alt_text}">{svg_tag}</div>'
        if target:
            img_html = f'<a href="{target}" target="_blank" rel="noopener">{img_html}</a>'

        wrapper_classes = self._build_wrapper_classes()
        class_attr = f' class="{" ".join(wrapper_classes)}"'

        if "caption" in self.options:
            caption = html_mod.escape(self.options["caption"])
            figclass = self.options.get("figclass", [])
            if figclass:
                class_attr = f' class="{" ".join(wrapper_classes + figclass)}"'
            html = (
                f"<figure{class_attr}>\n"
                f"  {img_html}\n"
                f"  <figcaption>{caption}</figcaption>\n"
                f"</figure>"
            )
        else:
            html = f"<div{class_attr}>{img_html}</div>"

        raw_node = nodes.raw("", html, format="html")

        if "name" in self.options:
            self.add_name(raw_node)

        return [raw_node]

    def _run_mermaid(self, machine: object, formatter: Any, qualname: str) -> list[nodes.Node]:
        """Render a Mermaid diagram using sphinxcontrib-mermaid's node type."""
        try:
            mermaid_src = formatter.render(machine, "mermaid")
        except Exception as exc:
            return [
                self.state_machine.reporter.warning(
                    f"statemachine-diagram: failed to generate mermaid for {qualname!r}: {exc}",
                    line=self.lineno,
                )
            ]

        try:
            from sphinxcontrib.mermaid import (  # type: ignore[import-untyped]
                mermaid as MermaidNode,
            )
        except ImportError:
            # Fallback: emit a raw code block if sphinxcontrib-mermaid is not installed
            code_node = nodes.literal_block(mermaid_src, mermaid_src)
            code_node["language"] = "mermaid"
            return [code_node]

        node = MermaidNode()
        node["code"] = mermaid_src
        node["options"] = {}

        caption = self.options.get("caption")
        if caption:
            figure_node = nodes.figure()
            figure_node += node
            figure_node += nodes.caption(caption, caption)
            if "name" in self.options:
                self.add_name(figure_node)
            return [figure_node]

        if "name" in self.options:
            self.add_name(node)
        return [node]

    def _prepare_svg(self, svg_text: str) -> tuple[str, str, str]:
        """Extract the ``<svg>`` element and its intrinsic dimensions."""
        match = _SVG_TAG_RE.search(svg_text)
        svg_tag = match.group(1) if match else svg_text

        width_match = _SVG_WIDTH_RE.search(svg_tag)
        height_match = _SVG_HEIGHT_RE.search(svg_tag)
        intrinsic_width = width_match.group(1) if width_match else ""
        intrinsic_height = height_match.group(1) if height_match else ""

        # Remove fixed dimensions — sizing is controlled via inline styles.
        svg_tag = _SVG_WIDTH_RE.sub("", svg_tag)
        svg_tag = _SVG_HEIGHT_RE.sub("", svg_tag)

        return svg_tag, intrinsic_width, intrinsic_height

    def _build_svg_styles(self, intrinsic_width: str, intrinsic_height: str) -> str:
        """Build an inline ``style`` attribute for the ``<svg>`` element."""
        parts: list[str] = []

        # Width: explicit > scaled intrinsic > intrinsic as max-width.
        user_width = self.options.get("width", "")
        scale = self.options.get("scale", "")
        if user_width:
            parts.append(f"width: {user_width}")
        elif scale and intrinsic_width:
            factor = int(scale.rstrip("%")) / 100
            value, unit = _split_length(intrinsic_width)
            parts.append(f"width: {value * factor:.1f}{unit}")
        elif intrinsic_width:
            parts.append(f"max-width: {intrinsic_width}")

        # Height: explicit > scaled intrinsic > auto.
        user_height = self.options.get("height", "")
        if user_height:
            parts.append(f"height: {user_height}")
        elif scale and intrinsic_height:
            factor = int(scale.rstrip("%")) / 100
            value, unit = _split_length(intrinsic_height)
            parts.append(f"height: {value * factor:.1f}{unit}")
        else:
            parts.append("height: auto")

        return f'style="{"; ".join(parts)}"'

    def _resolve_target(self, svg_text: str) -> str:
        """Return the href for the wrapper ``<a>`` tag, if any.

        When ``:target:`` is given without a value (or as empty string), the
        raw SVG is written to ``_images/`` and linked so the user can open
        the full diagram in a new browser tab for zooming.
        """
        if "target" not in self.options:
            return ""
        target = (self.options["target"] or "").strip()
        if target:
            return target

        # Auto-generate a standalone SVG file for zoom.
        qualname = self.arguments[0]
        events_key = self.options.get("events", "")
        identity = f"{qualname}:{events_key}"
        digest = hashlib.sha1(identity.encode()).hexdigest()[:8]
        filename = f"statemachine-{digest}.svg"

        outdir = os.path.join(self.env.app.outdir, "_images")
        os.makedirs(outdir, exist_ok=True)
        outpath = os.path.join(outdir, filename)
        with open(outpath, "w", encoding="utf-8") as f:
            f.write(svg_text)

        return f"/_images/{filename}"

    def _build_wrapper_classes(self) -> list[str]:
        """Build CSS class list for the outer wrapper element."""
        css_classes: list[str] = self.options.get("class", [])
        align = self.options.get("align", "center")
        return ["statemachine-diagram", f"align-{align}"] + css_classes


def _split_length(value: str) -> tuple[float, str]:
    """Split a CSS length like ``'702pt'`` into ``(702.0, 'pt')``."""
    match = re.match(r"([0-9.]+)(.*)", value)
    if match:
        return float(match.group(1)), match.group(2)
    return 0.0, value


def setup(app: "Sphinx") -> dict[str, Any]:
    app.add_directive("statemachine-diagram", StateMachineDiagram)
    return {"version": "0.1", "parallel_read_safe": True, "parallel_write_safe": True}
