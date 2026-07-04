import pytest


def pytest_addoption(parser):
    parser.addoption(
        "--specs",
        action="store",
        default=None,
        help="Target specs from '/docs/spec' directory.",
    )
    parser.addoption(
        "--render-pdfs",
        action="store_true",
        default=False,
        help=(
            "Also render each spec/composite case to a PDF next to its .pxml "
            "file, for visual inspection (requires the 'pdf' extra, e.g. "
            "`uv sync --extra pdf`)."
        ),
    )


@pytest.fixture(scope="session")
def render_pdfs(request) -> bool:
    return request.config.getoption("--render-pdfs")
