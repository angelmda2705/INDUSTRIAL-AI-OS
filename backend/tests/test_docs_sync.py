"""Generated reference docs must match the code (run `python -m app.cli export-docs` after changes)."""

from pathlib import Path

from app.docs_export import export

DOCS = Path(__file__).resolve().parents[2] / "docs"


def test_generated_docs_are_current(tmp_path):
    for generated in export(tmp_path):
        committed = DOCS / generated.name
        assert committed.exists(), f"{committed} missing: run python -m app.cli export-docs"
        assert committed.read_text(encoding="utf-8") == generated.read_text(encoding="utf-8"), (
            f"{committed.name} is out of date: run python -m app.cli export-docs"
        )
