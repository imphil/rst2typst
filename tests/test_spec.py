"""Test cases using spec documents.

``spec`` pages in documentation include examples how does it convert from reStructuredText to Typst.
This file run tests using documents as "Spec of translator".

Refs:

* https://rst2typst.attakei.dev/spec/
"""

from pathlib import Path

from docutils.core import publish_parts, publish_string

from rst2typst import writer

SPEC_DIR = (Path(__file__).parent.parent / "docs" / "spec").resolve()


def fetch_cases_from_specs(specs: list[str] | None = None):
    """Fetch all test cases from spec documents."""
    ids = []
    cases = []
    if specs is None:
        specs = ["**"]
    for spec in specs:
        for rst in SPEC_DIR.glob(f"{spec}/*.rst.txt"):
            pxml = rst.parent / f"{rst.name[:-8]}.pxml"
            group = rst.relative_to(SPEC_DIR).parent
            name = rst.name[:-8]
            typ = rst.parent / f"{name}.typ.txt"
            cases.append((rst.read_text(), typ.read_text(), pxml))
            ids.append(f"{group.name}__{name}")
    return ids, cases


def pytest_generate_tests(metafunc):
    if "source" not in metafunc.fixturenames:
        return

    raw = metafunc.config.getoption("--specs", default=None)
    specs = [d.strip() for d in raw.split(",")] if raw else None

    ids, all_cases = fetch_cases_from_specs(specs)
    metafunc.parametrize("source,expected,pxml", all_cases, ids=ids)


def test_translate(source: str, expected: str, pxml: Path, render_pdfs: bool):
    """Test result of translation.

    It checks that contents of ``self.body.append`` results match expected output.

    .. note::

       Some nodes append imports syntax, but this case doesn't check it.
    """
    pxml.write_bytes(publish_string(source, writer_name="pseudoxml"))
    parts = publish_parts(source, writer=writer.Writer())
    assert parts["body"].strip() == expected.strip()

    if render_pdfs:
        from rst2typst.pdf import Writer as PdfWriter

        pdf_bytes = publish_string(source, writer=PdfWriter())
        pxml.with_suffix(".pdf").write_bytes(pdf_bytes)
