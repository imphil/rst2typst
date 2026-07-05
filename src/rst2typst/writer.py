"""Writer and related classes for docutils."""

from __future__ import annotations

import functools
import re
from importlib import metadata
from pathlib import Path
from typing import TYPE_CHECKING

from docutils import nodes
from docutils.writers import Writer as BaseWriter

from . import transforms
from .frontend import validate_comma_separated_int
from .package import PackageRegistry

if TYPE_CHECKING:
    from typing import Callable, Literal

# Version of the @preview/mitex Typst package to transform LaTeX math syntax
# to Typst.
MITEX_VERSION = "0.2.7"

class Writer(BaseWriter):
    supported = ("typst",)

    settings_spec = BaseWriter.settings_spec + (
        "Typst Writer Options",
        None,
        (
            (
                "Section level for page-break",
                ["--page-break-level"],
                {
                    "metavar": "<int>(,<int>)",
                    "validator": validate_comma_separated_int,
                },
            ),
            (
                "Template for render code.",
                ["--template"],
                {
                    "metavar": "<filepath>",
                },
            ),
            (
                'Disable appending "import" statement for local packages',
                ["--no-import-local-package"],
                {
                    "action": "store_true",
                    "dest": "no_import_local_package",
                    "default": False,
                },
            ),
        ),
    )

    settings_defaults = {
        "page_break_level": [],
        "template": Path(__file__).parent / "template.txt",
    }

    config_section = "typst writer"

    visitor_attributes = {"body", "packages"}

    def __init__(self):
        super().__init__()
        self.translator_class = TypstTranslator
        self.parts = {
            "body": "",
            "imports": "",
            "prologue": "",
            "epilogue": "",
        }

    def get_transforms(self):
        return super().get_transforms() + [
            transforms.AssignLiteralLanguage,
            transforms.RemapFootnotes,
        ]

    def translate(self):
        visitor: TypstTranslator = self.translator_class(self.document)
        self.document.walkabout(visitor)  # type: ignore[possibly-missing-attribute]
        self.parts["body"] = "".join(visitor.body)
        self.parts["imports"] = visitor.packages.code
        self.output = (
            Path(self.document.settings.template).read_text().format(**self.parts)
        )
        self.display_warnings()

    def display_warnings(self):
        if not self.document.settings.no_import_local_package:
            print("NOTE:")
            print(
                'The generated Typst code might fail to compile because it includes an "import" expression for a local package.'
            )
            print(
                'If you want to exclude "import" statements, use the "--no-import-local-package" flag.'
            )


class HanglingIndent(list[str]):
    """Controller for line prefixes.

    This class works to render Typst documents for correctly and human readability.
    """

    def __init__(self):
        super().__init__()
        self.append("")

    def push(self, text: str):
        self.append(text)

    def pop(self) -> str:  # type: ignore[invalid-method-override]]
        return super().pop()

    @property
    def prefix(self) -> str:
        """Retrieve prefix with indent for first line of a block."""
        space = " " * sum(len(s) for s in self[:-1])
        return f"{space}{self[-1]}"

    @property
    def indent(self) -> str:
        """Retrieve hangling indent for subsequent lines of a block."""
        return " " * sum(len(s) for s in self)

    def is_indent_only(self) -> bool:
        return self.prefix == self.indent


def escape(text: str) -> str:
    """Escape special characters in Typst."""
    ANY_ESCAPE_TARGET = ["#", "$", "*", "<", ">", "\\", "_", "`", "~"]
    HEAD_ESCAPE_TARGET = ["+", "-", "="]
    trans = str.maketrans({c: f"\\{c}" for c in ANY_ESCAPE_TARGET})
    text = text.translate(trans)
    if text and text[0] in HEAD_ESCAPE_TARGET:
        text = "\\" + text
    return text


# Conversion factors to Typst units for docutils length units that Typst has
# no literal for. "px" and unitless (docutils' legacy HTML <table width=N>
# convention, i.e. pixels) both use the CSS reference pixel (96px = 1in =
# 72pt); "pc" (pica) is a fixed 12pt; "ex" has no fixed size, so it's
# approximated as half an em, the common CSS convention.
_LENGTH_UNIT_CONVERSION = {
    "": (0.75, "pt"),
    "px": (0.75, "pt"),
    "pc": (12, "pt"),
    "ex": (0.5, "em"),
}


def _typst_length(value: str) -> str:
    """Convert a docutils length/percentage string (e.g. from ``:width:``) to Typst.

    Percentages and the units Typst has a literal for (pt, mm, cm, in, em)
    are passed through unchanged; the rest are converted via
    :data:`_LENGTH_UNIT_CONVERSION`.
    """
    match = re.match(r"^([0-9.]+)([a-z%]*)$", value)
    number, unit = match.group(1), match.group(2)
    if unit not in _LENGTH_UNIT_CONVERSION:
        return value
    factor, typst_unit = _LENGTH_UNIT_CONVERSION[unit]
    return f"{float(number) * factor:g}{typst_unit}"


# Node types whose children hang off an indent that the container itself
# already establishes (a list marker, "#quote(...)[", "#footnote()[", ...).
# Typst needs a blank line between such sibling blocks, but not before the
# first child (the container's own opening already positions it) or after
# the last (its closing does).
_GAP_CONTAINERS_DEFAULT = (
    nodes.list_item,
    nodes.definition,
    nodes.field_body,
    nodes.block_quote,
    nodes.footnote,
    nodes.Admonition,
    nodes.entry,
)

# Node types that render as their own indented block and so participate in
# the gap protocol above, as opposed to purely inline content.
_GAP_ELIGIBLE_DEFAULT = (
    nodes.paragraph,
    nodes.literal_block,
    nodes.doctest_block,
    nodes.math_block,
    nodes.block_quote,
    nodes.Admonition,
    nodes.table,
    nodes.bullet_list,
    nodes.enumerated_list,
)




class TypstTranslator(nodes.NodeVisitor):
    """Translator from docutils to Typst.

    Subclasses can override :meth:`get_gap_containers` and :meth:`get_gap_eligible`
    to extend the gap protocol with custom node types (e.g., Sphinx nodes).
    """

    def __init__(self, document: nodes.document):
        super().__init__(document)
        # Properties that are used by external object.
        self.packages = PackageRegistry()
        self.body = []

        # Properties to handle content for translation.
        self._section_level = 0
        self._hi = HanglingIndent()

    @classmethod
    def get_gap_containers(cls) -> tuple:
        """Node types that are gap containers (hold block-level children).

        Override in subclasses to extend the gap protocol to custom nodes.
        """
        return _GAP_CONTAINERS_DEFAULT

    @classmethod
    def get_gap_eligible(cls) -> tuple:
        """Node types that are gap-eligible (block-level content).

        Override in subclasses to extend the gap protocol to custom nodes.
        """
        return _GAP_ELIGIBLE_DEFAULT

    def needs_leading_gap(self, node: nodes.Element) -> bool:
        """Whether a blank-line gap is needed before ``node``.

        True for a node in :meth:`get_gap_eligible` that is a non-first child of a
        node in :meth:`get_gap_containers`. Subclasses can override
        :meth:`get_gap_containers` and :meth:`get_gap_eligible` to extend.
        """
        parent = node.parent
        return (
            isinstance(node, self.get_gap_eligible())
            and isinstance(parent, self.get_gap_containers())
            and parent.children[0] is not node
        )

    def needs_trailing_gap(self, node: nodes.Element) -> bool:
        """Whether a blank-line gap is needed after ``node``.

        Only paragraphs need this: every other node in :meth:`get_gap_eligible`
        already ends its own markup with a newline, which provides the first half
        of the next gap.
        """
        parent = node.parent
        return (
            isinstance(node, nodes.paragraph)
            and isinstance(parent, self.get_gap_containers())
            and parent.children[-1] is not node
        )

    @functools.cached_property
    def local_package_name(self) -> str:
        version = metadata.version("rst2typst")
        return f"@local/rst2typst:{version}"

    def block_on_structural(func: Callable):
        @functools.wraps(func)
        def _block_on_structural(self, node: nodes.Element):
            if isinstance(node.parent, nodes.Structural):
                self.body.append("\n")

            func(self, node)

        return _block_on_structural

    # =========================================
    # The visitors and departers for plain text
    # =========================================

    def visit_Text(self, node: nodes.Text):
        LITERAL_NODES = (
            nodes.doctest_block,
            nodes.literal,
            nodes.literal_block,
            nodes.math,
            nodes.math_block,
        )

        def _in_literal(node: nodes.Text) -> bool:
            n_ = node
            while n_.parent is not None:
                if isinstance(n_.parent, LITERAL_NODES):
                    return True
                n_ = n_.parent
            return False

        in_literal = _in_literal(node)
        lines = [
            escape(line) if not in_literal else line
            for line in node.astext().split("\n")
        ]
        separator = "\n" if in_literal else f"\n{self._hi.indent}"
        self.body.append(separator.join(lines))

    def depart_Text(self, node: nodes.Text):
        pass

    # ============================================================
    # The visitors and departers for basic reStructuredText syntax
    # ============================================================
    #
    # They are sorted by these rules:
    #
    #   * The order from "Syntax details" of `reStructuredText Markup Specification`_.
    #   * When the node has children node types, write it nearby the parent node type.
    #   * ``visit_`` is first, and ``depart_`` is second if it is exists.
    #
    # .. _reStructuredText Markup Specification: https://docutils.org/docs/ref/rst/restructuredtext.html

    # Document Structure
    # ==================
    def visit_document(self, node: nodes.document):
        pass

    def depart_document(self, node: nodes.document):
        pass

    def visit_section(self, node: nodes.section):
        self._section_level += 1
        if (
            hasattr(self.document.settings, "page_break_level")
            and self._section_level in self.document.settings.page_break_level
        ):
            self.body.append("#pagebreak()\n\n")

    def depart_section(self, node: nodes.section):
        self._section_level -= 1

    # Refs: https://typst.app/docs/reference/model/title/
    def visit_title(self, node: nodes.title):
        if isinstance(node.parent, nodes.document):
            self.body.append("#title([")
        else:
            prefix = "=" * self._section_level
            self.body.append(f"{prefix} ")

    def depart_title(self, node: nodes.title):
        if isinstance(node.parent, nodes.document):
            self.body.append("])\n\n")
        else:
            self.body.append("\n\n")

    def visit_transition(self, node: nodes.transition):
        # NOTE: It controls the line length using an external parameter if needed.
        self.body.append(f"\n{self._hi.indent}#line(100%)\n")
        raise nodes.SkipNode

    # Body Elements
    # =============
    @block_on_structural
    def visit_paragraph(self, node: nodes.paragraph):
        if self.needs_leading_gap(node):
            self.body.append(f"\n{self._hi.indent}")

    @block_on_structural
    def depart_paragraph(self, node: nodes.paragraph):
        if self.needs_trailing_gap(node):
            self.body.append("\n")

    # Bullet Lists and Enumerated Lists
    # ---------------------------------
    # Refs: https://typst.app/docs/reference/model/list/
    @block_on_structural
    def visit_bullet_list(self, node: nodes.bullet_list):
        if self.needs_leading_gap(node):
            self.body.append("\n")
        self._hi.push("- ")

    def depart_bullet_list(self, node: nodes.bullet_list):
        self._hi.pop()

    @block_on_structural
    def visit_enumerated_list(self, node: nodes.enumerated_list):
        if self.needs_leading_gap(node):
            self.body.append("\n")
        self._hi.push("+ ")

    def depart_enumerated_list(self, node: nodes.enumerated_list):
        self._hi.pop()

    def visit_list_item(self, node: nodes.list_item):
        self.body.append(self._hi.prefix)

    def depart_list_item(self, node: nodes.list_item):
        if (
            node.first_child_matching_class((nodes.bullet_list, nodes.enumerated_list))
            is None
        ):
            self.body.append("\n")

    # Definition Lists
    # ----------------
    @block_on_structural
    def visit_definition_list(self, node: nodes.definition_list):
        self._hi.push("/ ")

    def depart_definition_list(self, node: nodes.definition_list):
        self._hi.pop()

    def visit_definition_list_item(self, node: nodes.definition_list_item):
        self.body.append(self._hi.prefix)

    def depart_definition_list_item(self, node: nodes.definition_list_item):
        self.body.append("\n")

    def visit_term(self, node: nodes.term):
        pass

    def depart_term(self, node: nodes.term):
        pass

    def visit_classifier(self, node: nodes.classifier):
        self.body.append(" \\<")

    def depart_classifier(self, node: nodes.classifier):
        self.body.append("\\>")

    def visit_definition(self, node: nodes.definition):
        self.body.append(": \\\n")
        self.body.append(self._hi.indent)
        pass

    def depart_definition(self, node: nodes.definition):
        pass

    # Field Lists
    # -----------
    # Refs: https://typst.app/docs/reference/model/terms/
    @block_on_structural
    def visit_field_list(self, node: nodes.field_list):
        self.body.append("#table(\n")
        self._hi.push("  ")
        self.body.append(f"{self._hi.indent}columns: (auto, 1fr),\n")

    def depart_field_list(self, node: nodes.field_list):
        self._hi.pop()
        self.body.append(")")

    def visit_field(self, node: nodes.field):
        pass

    def depart_field(self, node: nodes.field):
        pass

    def visit_field_name(self, node: nodes.field_name):
        if isinstance(node.parent.parent, nodes.docinfo):  # type: ignore[possibly-missing-attribute]
            self.body.append("/ ")
            return
        self.body.append(self._hi.indent)
        self.body.append("[")

    def depart_field_name(self, node: nodes.field_name):
        if isinstance(node.parent.parent, nodes.docinfo):  # type: ignore[possibly-missing-attribute]
            self.body.append(": ")
            return
        self.body.append("],\n")

    def visit_field_body(self, node: nodes.field_body):
        if isinstance(node.parent.parent, nodes.docinfo):
            return
        self.body.append(self._hi.indent)
        self.body.append("[")

    def depart_field_body(self, node: nodes.field_body):
        if isinstance(node.parent.parent, nodes.docinfo):
            return
        self.body.append("],\n")

    # Bibliographic Fields
    # --------------------
    def visit_docinfo(self, node: nodes.docinfo):
        if not self.document.settings.no_import_local_package:
            self.packages.add(self.local_package_name, "docinfo")
        self.body.append(f"{self._hi.indent}#docinfo()[\n")
        self._hi.push("  / ")

    def depart_docinfo(self, node: nodes.docinfo):
        self._hi.pop()
        self.body.append(f"{self._hi.indent}]\n")

    def _visit_bibliographic(self, node: nodes.Bibliographic):
        title = node.__class__.__name__.title()
        self.body.append(f"{self._hi.prefix}{title}: \\ ")

    def _depart_bibliographic(self, node: nodes.Bibliographic):
        self.body.append("\n")

    # Refs: https://typst.app/docs/reference/model/terms/
    visit_address = _visit_bibliographic
    depart_address = _depart_bibliographic
    visit_author = _visit_bibliographic
    depart_author = _depart_bibliographic
    visit_contact = _visit_bibliographic
    depart_contact = _depart_bibliographic
    visit_copyright = _visit_bibliographic
    depart_copyright = _depart_bibliographic
    visit_date = _visit_bibliographic
    depart_date = _depart_bibliographic
    visit_organization = _visit_bibliographic
    depart_organization = _depart_bibliographic
    visit_revision = _visit_bibliographic
    depart_revision = _depart_bibliographic
    visit_status = _visit_bibliographic
    depart_status = _depart_bibliographic
    visit_version = _visit_bibliographic
    depart_version = _depart_bibliographic

    def visit_authors(self, node: nodes.authors):
        self._visit_bibliographic(node)
        self.body.append(
            " \\ ".join(
                escape(author.astext()) for author in node.findall(nodes.author)
            )
        )
        self._depart_bibliographic(node)
        raise nodes.SkipNode

    # Option Lists
    # ------------
    @block_on_structural
    def visit_option_list(self, node: nodes.option_list):
        self._hi.push("/ ")

    def depart_option_list(self, node: nodes.option_list):
        self._hi.pop()

    def visit_option_list_item(self, node: nodes.option_list_item):
        self.body.append(self._hi.prefix)

    def depart_option_list_item(self, node: nodes.option_list_item):
        self.body.append("\n")

    def visit_option_group(self, node: nodes.option_group):
        text = ", ".join([option.astext() for option in node.findall(nodes.option)])
        self.body.append(f"{text}: \\\n")
        raise nodes.SkipNode

    def visit_description(self, node: nodes.description):
        self.body.append(self._hi.indent)

    def depart_description(self, node: nodes.description):
        pass

    # Line Blocks
    # -----------
    def visit_line_block(self, node: nodes.line_block):
        pass

    def depart_line_block(self, node: nodes.line_block):
        pass

    def visit_line(self, node: nodes.line):
        pass

    def depart_line(self, node: nodes.line):
        self.body.append(" \\\n")

    # Literal Blocks
    # --------------
    # Refs: https://typst.app/docs/reference/text/raw/
    def visit_literal_block(self, node: nodes.literal_block):
        # The hanging indent is only needed for the fence: the first child of
        # a hanging container already sits right after its opening marker,
        # which reserves the same width as the indent would add.
        if self.needs_leading_gap(node):
            self.body.append(f"\n{self._hi.indent}")
        # NOTE: It finds the highlighting language using the "language" attribute set by transforms.
        lang = node.get("language", None)
        # Choose a fence length longer than the longest backtick run in the
        # content so that embedded ``` sequences don't terminate the fence
        # prematurely (Typst, like CommonMark, supports longer opening fences).
        content = node.astext()
        max_run = max(
            (len(m.group()) for m in re.finditer(r"`+", content)),
            default=0,
        )
        fence = "`" * max(3, max_run + 1)
        self._literal_block_fence = fence
        if lang:
            self.body.append(f"{fence}{lang}\n")
            return
        self.body.append(f"{fence}\n")

    def depart_literal_block(self, node: nodes.literal_block):
        fence = getattr(self, "_literal_block_fence", "```")
        self.body.append(f"\n{self._hi.indent}{fence}\n")

    # Math
    # ----
    @block_on_structural
    def visit_math_block(self, node: nodes.math):
        # See visit_literal_block for why this is conditional on position.
        if self.needs_leading_gap(node):
            self.body.append(f"\n{self._hi.indent}")
        self.packages.add(f"@preview/mitex:{MITEX_VERSION}")
        self.body.append("#mitex(`\n")
        self._hi.push("  ")
        self.body.append(self._hi.indent)

    def depart_math_block(self, node: nodes.math):
        self._hi.pop()
        self.body.append(f"\n{self._hi.indent}`)\n")

    # Line Blocks
    # -----------
    # TODO: Implement after

    # Block Quotes
    # ------------
    # Refs: https://typst.app/docs/reference/model/quote/
    @block_on_structural
    def visit_block_quote(self, node: nodes.block_quote):
        if self.needs_leading_gap(node):
            self.body.append(f"\n{self._hi.indent}")
        self._hi.push("  ")
        args = []
        attrs = list(node.findall(nodes.attribution))
        if attrs:
            args.append(f"attribution: [{attrs[0].astext()}]")
            for a in attrs:
                node.remove(a)
        self.body.append(f"#quote({' '.join(args)})[\n")
        self.body.append(self._hi.prefix)

    def depart_block_quote(self, node: nodes.block_quote):
        self._hi.pop()
        self.body.append("\n]\n")

    # Doctest Blocks
    # --------------
    def visit_doctest_block(self, node: nodes.doctest_block):
        # See visit_literal_block for why the indent is conditional.
        if self.needs_leading_gap(node):
            self.body.append(f"\n{self._hi.indent}")
        self.body.append("```python\n")

    def depart_doctest_block(self, node: nodes.doctest_block):
        self.body.append(f"\n{self._hi.indent}```\n")

    # Tables
    # ------
    @block_on_structural
    def visit_table(self, node: nodes.table):
        # See visit_literal_block for why the indent is conditional. Only the
        # first line written (the figure wrapper if present, otherwise the
        # table itself) needs this; a "#table(" following "#figure([" is a
        # continuation line and always needs its own indent.
        if self.needs_leading_gap(node):
            self.body.append(f"\n{self._hi.indent}")
        # Typst's table() has no overall-width parameter (only per-column
        # sizing), so an explicit ":width:" is applied by wrapping the whole
        # thing (figure and all, if captioned) in a sized block.
        if "width" in node:
            self.body.append(f"#block(width: {_typst_length(node['width'])})[\n")
            self._hi.push("  ")
            self.body.append(self._hi.indent)
        figure_opts = {}
        if isinstance(node.children[0], nodes.title):
            figure_opts["caption"] = node.children[0].astext()
            node.remove(node.children[0])
        if figure_opts:
            node["figure_opts"] = figure_opts
            self.body.append("#figure([\n")
            self._hi.push("  ")
            self.body.append(f"{self._hi.indent}#table(\n")
        else:
            self.body.append("#table(\n")
        self._hi.push("  ")

    def depart_table(self, node: nodes.table):
        self._hi.pop()
        self.body.append(f"{self._hi.indent})")
        if "figure_opts" in node:
            opts = node["figure_opts"]
            self.body.append("],")
            if "caption" in opts:
                self.body.append(f"\n{self._hi.indent}caption: [{opts['caption']}],\n")
            self._hi.pop()
            self.body.append(f"{self._hi.indent})")
        if "width" in node:
            self.body.append("\n")
            self._hi.pop()
            self.body.append(f"{self._hi.indent}]")
        self.body.append("\n")

    def visit_tgroup(self, node: nodes.tgroup):
        table_node = node.parent
        colwidths_given = "colwidths-given" in table_node.get("classes", [])

        if colwidths_given:
            # Use explicit fractional widths when the author specified them.
            cols = [
                f"{colspec['colwidth']}fr" for colspec in node.findall(nodes.colspec)
            ]
            self.body.append(f"{self._hi.indent}columns: ({', '.join(cols)}),\n")
        else:
            # Typst defaults to columns: 1, so we must always emit the column
            # count; the integer shorthand sizes all columns automatically.
            self.body.append(f"{self._hi.indent}columns: {node['cols']},\n")

    def depart_tgroup(self, node: nodes.tgroup):
        pass

    def visit_colspec(self, node: nodes.colspec):
        raise nodes.SkipNode

    def visit_thead(self, node: nodes.tbody):
        self.body.append(f"{self._hi.indent}table.header(\n")
        self._hi.push("  ")

    def depart_thead(self, node: nodes.tbody):
        self._hi.pop()
        self.body.append(f"{self._hi.indent}),\n")

    def visit_tbody(self, node: nodes.tbody):
        pass

    def depart_tbody(self, node: nodes.tbody):
        pass

    def visit_row(self, node: nodes.row):
        pass

    def depart_row(self, node: nodes.row):
        pass

    def visit_entry(self, node: nodes.entry):
        morerows = node.get("morerows", 0)
        morecols = node.get("morecols", 0)
        prefix = ""
        if morerows or morecols:
            prefix = "table.cell("
            if morerows:
                prefix += f"rowspan: {morerows + 1},"
            if morecols:
                prefix += f"colspan: {morecols + 1},"
            prefix += ")"

        self.body.append(f"{self._hi.indent}{prefix}[")

    def depart_entry(self, node: nodes.entry):
        self.body.append("],\n")

    # Explicit Markup Blocks
    # ----------------------
    def visit_footnote(self, node: nodes.footnote):
        self._hi.push("  ")
        self.body.append(f"#footnote()[\n{self._hi.indent}")

    def depart_footnote(self, node: nodes.footnote):
        self._hi.pop()
        self.body.append(f"\n{self._hi.indent}]")

    def visit_footnote_reference(self, node: nodes.footnote_reference):
        if isinstance(node.previous_sibling(), nodes.footnote):
            self.body.append(" <")
        else:
            self.body.append("@")

    def depart_footnote_reference(self, node: nodes.footnote_reference):
        if isinstance(node.previous_sibling(), nodes.footnote):
            self.body.append(">")

    def visit_comment(self, node: nodes.comment):
        raise nodes.SkipNode

    #
    # Inline Markup
    # =============
    def _enclose_content(wrapper: str):
        def _enclose(self, node: nodes.Inline):
            self.body.append(wrapper)

        return _enclose, _enclose

    # Refs: https://typst.app/docs/reference/model/emph/
    visit_emphasis, depart_emphasis = _enclose_content("_")
    # Refs: https://typst.app/docs/reference/model/strong/
    visit_strong, depart_strong = _enclose_content("*")

    def _enclose_literal(walk: Literal["visit", "depart"]):
        def _enclose(self, node: nodes.literal):
            closure = "`"
            # NOTE: It finds the highlighting language using the "language" attribute set by transforms.
            if "language" not in node:
                pass
            elif walk == "depart":
                closure = "```"
            else:
                closure = f"```{node['language']} "
            self.body.append(closure)

        return _enclose

    # Refs: https://typst.app/docs/reference/model/raw/
    visit_literal = _enclose_literal("visit")
    depart_literal = _enclose_literal("depart")

    def visit_math(self, node: nodes.math):
        self.packages.add(f"@preview/mitex:{MITEX_VERSION}")
        self.body.append("#mi(`")

    def depart_math(self, node: nodes.math):
        self.body.append("`)")

    def visit_reference(self, node: nodes.reference):
        # TODO: Currently, it doesn't support internal reference.
        if "refuri" in node:
            href = node["refuri"]
            self.body.append(f'#link("{href}")[')
            return
        if "refid" in node:
            self.body.append(f"#link(<{node['refid']}>)[")
            return
        self.body.append("[")

    def depart_reference(self, node: nodes.reference):
        self.body.append("]")

    def visit_target(self, node: nodes.target):
        # Handle internal hyperlink targets
        # External targets (with refuri) are handled separately and don't need labels
        if "refuri" in node:
            # External hyperlink target - skip, handled by reference nodes
            raise nodes.SkipNode

        # Internal target - output as Typst label
        if "refid" in node or "ids" in node:
            # Get the target ID
            target_id = node.get("refid") or (node["ids"][0] if node["ids"] else None)
            if target_id:
                self.body.append(f"<{target_id}>\n")
        raise nodes.SkipNode

    def depart_target(self, node: nodes.target):
        pass

    # ==========================================================
    # The visitors and departers for reStructuredText Directives
    # ==========================================================
    #
    # They are sorted by these rules:
    #
    #   * The order from contents of `reStructuredText Directives`_.
    #   * When the node has children node types, write it nearby the parent node type.
    #   * ``visit_`` is first, and ``depart_`` is second if it is exists.
    #
    # .. _reStructuredText Directives: https://docutils.org/docs/ref/rst/directives.html

    # Admonitions
    # ===========
    def _enclose_admonition(node_name: str, title: str | None = None):
        def _visit(self, node: nodes.Element):
            if not self.document.settings.no_import_local_package:
                self.packages.add(self.local_package_name, "admonition")

            nonlocal title
            if isinstance(node.parent, nodes.Structural):
                self.body.append("\n")
            elif self.needs_leading_gap(node):
                self.body.append(f"\n{self._hi.indent}")

            title_idx = node.first_child_matching_class(nodes.title)
            if title_idx is not None:
                title = node.children[title_idx].astext()
                node.remove(node.children[title_idx])

            self.body.append("#admonition(\n")
            self._hi.push("  ")
            self.body.append(f'{self._hi.indent}"{node_name}", "{title}",\n')
            self.body.append(f"{self._hi.indent}[")

        def _depart(self, node: nodes.Element):
            self.body.append("],\n")
            self._hi.pop()
            self.body.append(f"{self._hi.indent})\n")

        return _visit, _depart

    visit_attention, depart_attention = _enclose_admonition("attention", "Attention")
    visit_caution, depart_caution = _enclose_admonition("caution", "Caution")
    visit_danger, depart_danger = _enclose_admonition("danger", "Danger")
    visit_error, depart_error = _enclose_admonition("error", "Error")
    visit_hint, depart_hint = _enclose_admonition("hint", "Hint")
    visit_important, depart_important = _enclose_admonition("important", "Important")
    visit_note, depart_note = _enclose_admonition("note", "Note")
    visit_tip, depart_tip = _enclose_admonition("tip", "Tip")
    visit_warning, depart_warning = _enclose_admonition("warning", "Warning")
    visit_admonition, depart_admonition = _enclose_admonition("admonition")

    # Images
    # ======
    def visit_image(self, node: nodes.image):
        # FIXME: Implement is too complex.
        prefix = self._hi.indent
        suffix = "\n\n"
        if isinstance(node.parent, nodes.figure):
            prefix = f"{prefix}"
            suffix = "]"
        elif isinstance(node.parent, nodes.reference):
            prefix = f"\n{prefix}"
            suffix = "]"
        self.body.append(f"{prefix}#image(\n")
        self._hi.push("  ")
        self.body.append(f'{self._hi.indent}"{node["uri"]}",\n')
        if "alt" in node:
            self.body.append(f'{self._hi.indent}alt: "{node["alt"]}",\n')
        if "width" in node:
            self.body.append(f"{self._hi.indent}width: {node['width']},\n")
        self._hi.pop()
        self.body.append(f"{self._hi.indent}){suffix}")
        if isinstance(node.parent, nodes.reference):
            self._hi.pop()

    def depart_image(self, node: nodes.image):
        pass

    def visit_figure(self, node: nodes.figure):
        # FIXME: Implement is complex.
        if self._hi.is_indent_only:
            self.body.append(self._hi.prefix)
        self.body.append("#figure([\n")
        self._hi.push("  ")
        if node.first_child_matching_class(nodes.reference) is not None:
            self.body.append(f"{self._hi.indent}")
            self._hi.push("  ")

    def depart_figure(self, node: nodes.figure):
        self._hi.pop()
        self.body.append(f"{self._hi.indent})\n\n")

    def visit_caption(self, node: nodes.caption):
        self.body.append(",\n")
        self.body.append(f"{self._hi.indent}caption: [")

    def depart_caption(self, node: nodes.caption):
        self.body.append("],\n")

    # Body Elements
    # =============
    def visit_topic(self, node: nodes.topic):
        if "contents" in node["classes"]:
            self.body.append(f"{self._hi.indent}#outline(\n")
            self._hi.push("  ")
            titles = list(node.findall(nodes.title))
            if titles:
                title = titles[0]
                self.body.append(f"{self._hi.indent}title: [{title.astext()}],\n")
            self._hi.pop()
            self.body.append(f"{self._hi.indent})\n\n")
            raise nodes.SkipNode

    # NOTE: This node type is used by Sphinx's custom directives.
    def visit_compound(self, node: nodes.compound):
        pass

    def depart_compound(self, node: nodes.compound):
        pass

    # NOTE: This node type is used by Sphinx's custom directives.
    def visit_container(self, node: nodes.container):
        pass

    def depart_container(self, node: nodes.container):
        pass

    # Miscellaneous
    # =============
    def visit_raw(self, node: nodes.raw):
        if "format" in node and node["format"] == "typst":
            # NOTE: ``self.body.append(node.astext())`` does not work as expected.
            for line in node.astext().split("\n"):
                self.body.append(f"{line}\n")
            self.body.append("\n")
        raise nodes.SkipNode

    # =====================================================
    # The visitors and departers for reStructuredText Roles
    # =====================================================
    #
    # They are sorted by these rules:
    #
    #   * The order from contents of `reStructuredText Interpreted Text Roles`_.
    #   * When the node has children node types, write it nearby the parent node type.
    #   * ``visit_`` is first, and ``depart_`` is second if it is exists.
    #
    # .. _reStructuredText Interpreted Text Roles: https://www.docutils.org/docs/ref/rst/roles.html

    # Standard Roles
    # ==============
    # NOTE: Typst doesn't have features for abbreviation.
    def visit_abbreviation(self, node: nodes.abbreviation):
        pass

    def depart_abbreviation(self, node: nodes.abbreviation):
        pass

    # NOTE: Typst doesn't have features for acronyms.
    def visit_acronym(self, node: nodes.acronym):
        pass

    def depart_acronym(self, node: nodes.acronym):
        pass

    def visit_subscript(self, node: nodes.subscript):
        self.body.append("#sub[")

    def depart_subscript(self, node: nodes.subscript):
        self.body.append("]")

    def visit_superscript(self, node: nodes.superscript):
        self.body.append("#super[")

    def depart_superscript(self, node: nodes.superscript):
        self.body.append("]")

    # NOTE: At this time, we have intentionally taken no action for this node. Adjustments will be necessary as needed.
    def visit_title_reference(self, node: nodes.title_reference):
        pass

    def depart_title_reference(self, node: nodes.title_reference):
        pass

    # =============
    # Miscellaneous
    # =============
    def visit_inline(self, node: nodes.inline):
        pass

    def depart_inline(self, node: nodes.inline):
        pass
