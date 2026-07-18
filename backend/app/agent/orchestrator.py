"""
Agent orchestrator — plan → call → execute → observe loop.

Modes (controlled by config.resolved_agent_mode):
  real  — uses the Anthropic Claude API with tool use
  mock  — deterministic planner, no API key needed (supports pie-chart flow)
"""

import json
import logging
from typing import Any, Callable, Dict, List, Tuple

import anthropic

from app.agent.prompts import SYSTEM_PROMPT
from app.agent.tools import TOOL_SCHEMAS, dispatch
from app.config import settings
from app.docops.outline import build_outline
from app.docops.session import DocumentSession

log = logging.getLogger(__name__)

MODEL = "claude-sonnet-4-6"
MAX_STEPS = 10


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def run_agent(
    session: DocumentSession,
    prompt: str,
    on_change: Callable[[str, str], None] | None = None,
) -> List[Dict[str, str]]:
    """
    Run the agent loop against `session` for the given `prompt`.

    `on_change(tool_name, description)` is called after each successful tool
    execution — used to stream change entries back to the job runner.

    Returns the list of change dicts: [{tool, description}, ...].
    """
    mode = settings.resolved_agent_mode
    log.info("Agent mode: %s", mode)

    if mode == "real":
        return _real_loop(session, prompt, on_change)
    return _mock_loop(session, prompt, on_change)


# ---------------------------------------------------------------------------
# Real loop (Claude API)
# ---------------------------------------------------------------------------

def _real_loop(
    session: DocumentSession,
    prompt: str,
    on_change: Callable | None,
) -> List[Dict[str, str]]:
    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
    outline = build_outline(session)
    changes: List[Dict[str, str]] = []

    messages: List[Dict[str, Any]] = [
        {
            "role": "user",
            "content": (
                f"Document outline:\n```json\n{json.dumps(outline, indent=2)}\n```\n\n"
                f"Instruction: {prompt}"
            ),
        }
    ]

    for step in range(MAX_STEPS):
        log.debug("Step %d — calling Claude", step + 1)
        response = client.messages.create(
            model=MODEL,
            max_tokens=4096,
            system=SYSTEM_PROMPT,
            tools=TOOL_SCHEMAS,
            messages=messages,
        )

        # Collect tool calls from the response
        tool_uses = [b for b in response.content if b.type == "tool_use"]

        if not tool_uses:
            log.info("No more tool calls — agent finished after %d step(s)", step + 1)
            break

        # Build the assistant turn
        messages.append({"role": "assistant", "content": response.content})

        # Execute each tool call and build the tool_result turn
        tool_results = []
        for tool_use in tool_uses:
            tool_name = tool_use.name
            tool_input = tool_use.input
            log.info("Executing tool: %s %s", tool_name, tool_input)
            try:
                description = dispatch(tool_name, tool_input, session)
                changes.append({"tool": tool_name, "description": description})
                if on_change:
                    on_change(tool_name, description)
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": tool_use.id,
                    "content": description,
                })
            except Exception as exc:
                log.error("Tool %s failed: %s", tool_name, exc)
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": tool_use.id,
                    "content": f"ERROR: {exc}",
                    "is_error": True,
                })

        messages.append({"role": "user", "content": tool_results})

        if response.stop_reason == "end_turn":
            break

    return changes


# ---------------------------------------------------------------------------
# Mock loop (offline / no API key)
# ---------------------------------------------------------------------------

_PIE_CHART_KEYWORDS = {"pie", "donut"}
_BAR_CHART_KEYWORDS = {"bar", "histogram", "column"}


def _parse_pie_data(prompt: str) -> Tuple[List[str], List[float]]:
    """
    Extract label/value pairs from strings like:
      "Product 40, Services 35, Support 25"
    Returns (labels, values). Falls back to a default if parsing fails.
    """
    import re
    pairs = re.findall(r"([A-Za-z][A-Za-z\s]*?)\s+(\d+(?:\.\d+)?)", prompt)
    if pairs:
        labels = [p[0].strip() for p in pairs]
        values = [float(p[1]) for p in pairs]
        return labels, values
    return ["Category A", "Category B", "Category C"], [40.0, 35.0, 25.0]


def _mock_loop(
    session: DocumentSession,
    prompt: str,
    on_change: Callable | None,
) -> List[Dict[str, str]]:
    """
    Deterministic mock agent that handles the canonical pie-chart demo flow
    and a handful of other common patterns. Useful for offline testing.
    """
    changes: List[Dict[str, str]] = []
    outline = build_outline(session)
    lower = prompt.lower()

    def _run(tool_name: str, tool_input: Dict[str, Any]) -> None:
        description = dispatch(tool_name, tool_input, session)
        changes.append({"tool": tool_name, "description": description})
        if on_change:
            on_change(tool_name, description)

    # --- bar / pie chart into docx (bar checked first to avoid pie swallowing it)
    import re
    words = set(lower.split())
    is_bar = bool(_BAR_CHART_KEYWORDS & words)
    is_pie = bool(_PIE_CHART_KEYWORDS & words) or ("pie" in lower)

    if session.ext == ".docx" and (is_bar or is_pie):
        anchor = (
            outline["headings"][0]["text"]
            if outline.get("headings")
            else (outline["paragraphs"][0] if outline.get("paragraphs") else "Introduction")
        )
        labels, values = _parse_pie_data(prompt)
        title_match = re.search(r'titled?\s+"([^"]+)"', prompt, re.IGNORECASE)
        title = title_match.group(1) if title_match else ("Bar Chart" if is_bar else "Chart")
        chart_type = "bar" if is_bar else "pie"

        _run("insert_chart", {
            "anchor_text": anchor,
            "chart_type": chart_type,
            "title": title,
            "labels": labels,
            "values": values,
            "caption": title,
        })
        return changes

    # --- replace text --------------------------------------------------------
    if "replace" in lower and " with " in lower:
        import re
        m = re.search(r'replace\s+"([^"]+)"\s+with\s+"([^"]+)"', prompt, re.IGNORECASE)
        if m:
            _run("replace_text", {"old_text": m.group(1), "new_text": m.group(2)})
            return changes

    # --- xlsx: write cell ----------------------------------------------------
    if session.ext == ".xlsx" and ("set" in lower or "write" in lower or "update" in lower):
        import re
        m = re.search(r'\b([A-Z]\d+)\b', prompt)
        sheet = outline["sheets"][0]["name"] if outline.get("sheets") else "Sheet1"
        cell = m.group(1) if m else "A1"
        val_m = re.search(r'(?:to|=)\s*(["\']?)(.+?)\1\s*$', prompt, re.IGNORECASE)
        value = val_m.group(2).strip() if val_m else "updated"
        _run("write_cell", {"sheet_name": sheet, "cell": cell, "value": value})
        return changes

    # --- fallback: insert a paragraph noting the request --------------------
    if session.ext == ".docx":
        anchor = (
            outline["paragraphs"][0]
            if outline.get("paragraphs")
            else (outline["headings"][0]["text"] if outline.get("headings") else "")
        )
        if anchor:
            _run("insert_paragraph", {
                "anchor_text": anchor,
                "text": f"[Agent note: applied edit — {prompt[:120]}]",
            })

    return changes
