"""
Tool catalog for the Document Editing Agent.

Each tool has:
  - A JSON schema (fed to Claude as `tools=`)
  - A case in dispatch() that maps the tool call to a docops function

Adding a new tool:
  1. Add its schema to TOOL_SCHEMAS
  2. Add a case in dispatch()
  3. Add the underlying operation in the relevant docops module
"""

from pathlib import Path
from typing import Any, Dict, List

from app.docops import session as _session_mod
from app.docops import docx_ops, xlsx_ops, charts


# ---------------------------------------------------------------------------
# Tool schemas (passed to Claude)
# ---------------------------------------------------------------------------

TOOL_SCHEMAS: List[Dict[str, Any]] = [
    {
        "name": "insert_chart",
        "description": (
            "Render a chart image (pie or bar) and insert it into the .docx "
            "after the paragraph that contains anchor_text."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "anchor_text": {
                    "type": "string",
                    "description": "Text of the paragraph after which the chart is inserted.",
                },
                "chart_type": {
                    "type": "string",
                    "enum": ["pie", "bar"],
                    "description": "Type of chart to generate.",
                },
                "title": {
                    "type": "string",
                    "description": "Chart title.",
                },
                "labels": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Category labels.",
                },
                "values": {
                    "type": "array",
                    "items": {"type": "number"},
                    "description": "Numeric values corresponding to labels.",
                },
                "caption": {
                    "type": "string",
                    "description": "Optional caption placed below the chart.",
                },
            },
            "required": ["anchor_text", "chart_type", "labels", "values"],
        },
    },
    {
        "name": "replace_text",
        "description": "Replace every occurrence of old_text with new_text in the document.",
        "input_schema": {
            "type": "object",
            "properties": {
                "old_text": {"type": "string", "description": "Exact text to find."},
                "new_text": {"type": "string", "description": "Replacement text."},
            },
            "required": ["old_text", "new_text"],
        },
    },
    {
        "name": "insert_paragraph",
        "description": "Insert a new paragraph after the paragraph containing anchor_text.",
        "input_schema": {
            "type": "object",
            "properties": {
                "anchor_text": {"type": "string", "description": "Text of the anchor paragraph."},
                "text": {"type": "string", "description": "Text for the new paragraph."},
                "style": {
                    "type": "string",
                    "description": "Word paragraph style name (default: Normal).",
                    "default": "Normal",
                },
            },
            "required": ["anchor_text", "text"],
        },
    },
    {
        "name": "insert_heading",
        "description": "Insert a heading after the paragraph containing anchor_text.",
        "input_schema": {
            "type": "object",
            "properties": {
                "anchor_text": {"type": "string", "description": "Text of the anchor paragraph."},
                "heading_text": {"type": "string", "description": "Text for the new heading."},
                "level": {
                    "type": "integer",
                    "description": "Heading level 1-6 (default: 1).",
                    "default": 1,
                },
            },
            "required": ["anchor_text", "heading_text"],
        },
    },
    {
        "name": "insert_table",
        "description": "Insert a table after the paragraph containing anchor_text.",
        "input_schema": {
            "type": "object",
            "properties": {
                "anchor_text": {"type": "string", "description": "Text of the anchor paragraph."},
                "headers": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Column header names.",
                },
                "rows": {
                    "type": "array",
                    "items": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "description": "2-D array of cell values (strings).",
                },
                "style": {
                    "type": "string",
                    "description": "Word table style name (default: Table Grid).",
                    "default": "Table Grid",
                },
            },
            "required": ["anchor_text", "headers", "rows"],
        },
    },
    # --- xlsx tools ----------------------------------------------------------
    {
        "name": "write_cell",
        "description": "Write a value to a single cell in an .xlsx sheet.",
        "input_schema": {
            "type": "object",
            "properties": {
                "sheet_name": {"type": "string", "description": "Worksheet name."},
                "cell": {"type": "string", "description": "Cell address e.g. 'B3'."},
                "value": {"description": "Value to write (string, number, or boolean)."},
            },
            "required": ["sheet_name", "cell", "value"],
        },
    },
    {
        "name": "write_range",
        "description": "Write a 2-D array of values into an .xlsx sheet starting at start_cell.",
        "input_schema": {
            "type": "object",
            "properties": {
                "sheet_name": {"type": "string"},
                "start_cell": {"type": "string", "description": "Top-left cell e.g. 'A1'."},
                "rows": {
                    "type": "array",
                    "items": {"type": "array"},
                    "description": "2-D array of values.",
                },
            },
            "required": ["sheet_name", "start_cell", "rows"],
        },
    },
    {
        "name": "append_row",
        "description": "Append a row of values to the end of the used range in an .xlsx sheet.",
        "input_schema": {
            "type": "object",
            "properties": {
                "sheet_name": {"type": "string"},
                "values": {"type": "array", "description": "List of cell values for the new row."},
            },
            "required": ["sheet_name", "values"],
        },
    },
    {
        "name": "add_sheet",
        "description": "Add a new worksheet to an .xlsx workbook.",
        "input_schema": {
            "type": "object",
            "properties": {
                "sheet_name": {"type": "string", "description": "Name for the new sheet."},
            },
            "required": ["sheet_name"],
        },
    },
    {
        "name": "edit_table_cell",
        "description": "Edit a cell by 1-based row and column index in an .xlsx sheet.",
        "input_schema": {
            "type": "object",
            "properties": {
                "sheet_name": {"type": "string"},
                "row": {"type": "integer", "description": "1-based row number."},
                "col": {"type": "integer", "description": "1-based column number."},
                "value": {"description": "New cell value."},
            },
            "required": ["sheet_name", "row", "col", "value"],
        },
    },
]


# ---------------------------------------------------------------------------
# Dispatch
# ---------------------------------------------------------------------------

def dispatch(tool_name: str, tool_input: Dict[str, Any], session) -> str:
    """
    Execute a tool call against `session` (a DocumentSession).
    Returns a short human-readable description of what changed.
    Raises ValueError for unknown tools or bad inputs.
    """

    if tool_name == "insert_chart":
        chart_path: Path = charts.build_chart(
            chart_type=tool_input["chart_type"],
            labels=tool_input["labels"],
            values=tool_input["values"],
            title=tool_input.get("title", ""),
        )
        return docx_ops.insert_image_after(
            session,
            anchor_text=tool_input["anchor_text"],
            image_path=chart_path,
            caption=tool_input.get("caption"),
        )

    if tool_name == "replace_text":
        return docx_ops.replace_text(
            session,
            old_text=tool_input["old_text"],
            new_text=tool_input["new_text"],
        )

    if tool_name == "insert_paragraph":
        return docx_ops.insert_paragraph_after(
            session,
            anchor_text=tool_input["anchor_text"],
            new_text=tool_input["text"],
            style=tool_input.get("style", "Normal"),
        )

    if tool_name == "insert_heading":
        return docx_ops.insert_heading_after(
            session,
            anchor_text=tool_input["anchor_text"],
            heading_text=tool_input["heading_text"],
            level=tool_input.get("level", 1),
        )

    if tool_name == "insert_table":
        return docx_ops.insert_table_after(
            session,
            anchor_text=tool_input["anchor_text"],
            headers=tool_input["headers"],
            rows=tool_input["rows"],
            style=tool_input.get("style", "Table Grid"),
        )

    if tool_name == "write_cell":
        return xlsx_ops.write_cell(
            session,
            sheet_name=tool_input["sheet_name"],
            cell=tool_input["cell"],
            value=tool_input["value"],
        )

    if tool_name == "write_range":
        return xlsx_ops.write_range(
            session,
            sheet_name=tool_input["sheet_name"],
            start_cell=tool_input["start_cell"],
            rows=tool_input["rows"],
        )

    if tool_name == "append_row":
        return xlsx_ops.append_row(
            session,
            sheet_name=tool_input["sheet_name"],
            values=tool_input["values"],
        )

    if tool_name == "add_sheet":
        return xlsx_ops.add_sheet(session, sheet_name=tool_input["sheet_name"])

    if tool_name == "edit_table_cell":
        return xlsx_ops.edit_table_cell(
            session,
            sheet_name=tool_input["sheet_name"],
            row=tool_input["row"],
            col=tool_input["col"],
            value=tool_input["value"],
        )

    raise ValueError(f"Unknown tool: {tool_name!r}")
