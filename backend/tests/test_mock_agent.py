"""
Integration tests for the mock agent loop.
These run fully offline — no Anthropic API key needed.
"""

import pytest

from app.agent.orchestrator import run_agent
from app.config import settings
from app.docops.outline import build_outline
from app.docops.session import DocumentSession


@pytest.fixture(autouse=True)
def force_mock_mode(monkeypatch):
    """Ensure all tests in this module use mock mode regardless of env."""
    monkeypatch.setattr(settings, "agent_mode", "mock")
    monkeypatch.setattr(settings, "anthropic_api_key", "")


class TestMockAgentDocx:
    def test_pie_chart_flow(self, docx_session):
        changes = run_agent(
            docx_session,
            'insert a pie chart titled "Q2 Revenue" with Product 40, Services 35, Support 25 '
            "after the first heading",
        )
        assert len(changes) >= 1
        assert changes[0]["tool"] == "insert_chart"
        assert "inserted" in changes[0]["description"].lower()

    def test_bar_chart_flow(self, docx_session):
        changes = run_agent(
            docx_session,
            "insert a bar chart with Jan 100, Feb 150, Mar 120 after the introduction",
        )
        assert len(changes) >= 1
        assert changes[0]["tool"] == "insert_chart"

    def test_replace_text_flow(self, docx_session):
        changes = run_agent(
            docx_session,
            'replace "first paragraph" with "opening paragraph"',
        )
        assert len(changes) >= 1
        assert changes[0]["tool"] == "replace_text"

    def test_on_change_callback(self, docx_session):
        seen = []
        run_agent(
            docx_session,
            'insert a pie chart titled "Test" with A 50, B 50 after Introduction',
            on_change=lambda name, desc: seen.append((name, desc)),
        )
        assert len(seen) >= 1
        assert seen[0][0] == "insert_chart"

    def test_fallback_inserts_note(self, docx_session):
        changes = run_agent(docx_session, "do something completely unrecognised")
        # fallback inserts a note paragraph
        assert len(changes) >= 1
        assert changes[0]["tool"] == "insert_paragraph"


class TestMockAgentXlsx:
    def test_write_cell_flow(self, xlsx_session):
        changes = run_agent(xlsx_session, "set B2 to 999")
        assert len(changes) >= 1
        assert changes[0]["tool"] == "write_cell"

    def test_update_cell_flow(self, xlsx_session):
        changes = run_agent(xlsx_session, 'update C3 to "hello"')
        assert len(changes) >= 1
        assert changes[0]["tool"] == "write_cell"
