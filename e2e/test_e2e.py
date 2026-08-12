"""Test suite for PDF output."""

from pathlib import Path

import pymupdf
import pytest

from conftest import FIXTURES_DIR


@pytest.mark.parametrize("source", sorted(FIXTURES_DIR.glob("*.rst")))
def test_no_text_overlap(source: Path, open_pdf):
    """Test that PDF output has no overlapping text blocks.

    Verify that no two text blocks on the same page overlap each other.
    """
    doc: pymupdf.Document = open_pdf(source)
    for page in doc:
        blocks = [b for b in page.get_text("blocks") if b[6] == 0]
        for i, b1 in enumerate(blocks):
            r1 = pymupdf.Rect(b1[:4])
            for b2 in blocks[i + 1 :]:
                r2 = pymupdf.Rect(b2[:4])
                assert (r1 & r2).is_empty, (
                    f"Text blocks overlap on page {page.number + 1}:\n"
                    f"  Block 1: {b1[4]!r} at {r1}\n"
                    f"  Block 2: {b2[4]!r} at {r2}"
                )
