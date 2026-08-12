"""Test suite for end-to-end."""

import subprocess
from pathlib import Path

import pymupdf
import pytest

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def pytest_collect_file(parent, file_path: Path):
    if file_path.suffix == ".rst" and file_path.parent == FIXTURES_DIR:
        return None


@pytest.fixture(scope="session")
def build_pdf(tmp_path_factory):
    caches: dict[Path, Path] = {}
    out_dir = tmp_path_factory.mktemp("pdfs")

    def _build(source_path: Path) -> Path:
        if source_path in caches:
            return caches[source_path]

        dest_path = out_dir / source_path.with_suffix(".pdf").name
        subprocess.run(
            ["rst2typstpdf", str(source_path), str(dest_path)],
            check=True,
        )
        caches[source_path] = dest_path

        return dest_path

    return _build


@pytest.fixture(scope="session")
def open_pdf(build_pdf):
    def _open(rst_path: Path) -> pymupdf.Document:
        pdf_path = build_pdf(rst_path)
        return pymupdf.open(str(pdf_path))

    return _open
