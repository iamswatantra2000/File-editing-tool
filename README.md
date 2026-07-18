# Document Editing Agent

An LLM-powered system that edits `.docx` and `.xlsx` files from natural-language instructions.
You upload a document, describe what you want changed, and a Claude-driven agent plans and applies
the edits — with original formatting preserved and the modified file ready for download.

> The LLM **plans**; a constrained, validated tool layer **executes**.
> The model never writes raw file bytes. That separation is what makes edits safe, reversible, and testable.

---

## Table of Contents

1. [Stack](#stack)
2. [Repository Layout](#repository-layout)
3. [How It Was Built — Step by Step](#how-it-was-built--step-by-step)
   - [Backend](#backend-build-order)
   - [Frontend](#frontend-build-order)
4. [How the Agent Works](#how-the-agent-works)
5. [Running the App](#running-the-app)
6. [Running Tests](#running-tests)
7. [Offline Demo](#offline-demo)
8. [API Reference](#api-reference)
9. [Roadmap](#roadmap)

---

## Stack

| Layer | Tech |
|---|---|
| Frontend | React 18, Vite, Tailwind CSS v3 |
| API / orchestration | FastAPI, Pydantic v2, Uvicorn |
| Agent | Anthropic Claude API (tool use) + deterministic mock mode |
| Document tools | python-docx, openpyxl, matplotlib |
| Storage | Local filesystem, versioned per job |
| Tests | pytest, FastAPI TestClient, httpx |

---

## Repository Layout

```
file-editing-agent-tool/
├── backend/
│   ├── app/
│   │   ├── main.py            # FastAPI app + CORS + router registration
│   │   ├── config.py          # Env vars via Pydantic Settings
│   │   ├── models.py          # Job, JobStatus, ChangeEntry Pydantic schemas
│   │   ├── storage.py         # Versioned file store (original / working / result)
│   │   ├── jobs.py            # In-memory job store + run_job() background task
│   │   ├── agent/
│   │   │   ├── prompts.py     # System prompt given to Claude
│   │   │   ├── tools.py       # Tool JSON schemas + dispatch()
│   │   │   └── orchestrator.py  # Plan → call → execute → observe loop (real + mock)
│   │   ├── docops/
│   │   │   ├── session.py     # DocumentSession: opens .docx / .xlsx
│   │   │   ├── outline.py     # Builds compact JSON summary for the agent prompt
│   │   │   ├── docx_ops.py    # python-docx: insert, replace, table, image, heading
│   │   │   ├── xlsx_ops.py    # openpyxl: read/write cell, range, sheet ops
│   │   │   └── charts.py      # matplotlib → PNG (pie, bar) using Agg backend
│   │   ├── routes/
│   │   │   └── jobs.py        # POST /api/jobs, GET /api/jobs/{id}, GET /api/jobs/{id}/result
│   │   └── demo.py            # Offline end-to-end demo (no API key needed)
│   ├── tests/
│   │   ├── conftest.py        # Shared fixtures (docx_session, xlsx_session)
│   │   ├── test_docops.py     # Unit tests for all docops operations
│   │   ├── test_mock_agent.py # Integration tests for mock agent flows
│   │   └── test_api.py        # HTTP-level tests via TestClient
│   ├── pytest.ini             # pythonpath = . so pytest finds the app package
│   ├── requirements.txt
│   └── .env.example
└── frontend/
    ├── index.html
    ├── vite.config.js         # Dev server + /api proxy to :8000
    ├── tailwind.config.js     # Stone/orange dark theme, Montserrat + Inter fonts
    ├── postcss.config.js
    ├── package.json
    └── src/
        ├── main.jsx           # React entry point
        ├── index.css          # Tailwind directives + Google Fonts import
        ├── api.js             # submitJob(), pollJob(), resultUrl()
        ├── App.jsx            # Root component: form + polling state machine
        └── components/
            ├── Uploader.jsx   # Drag-and-drop file picker (.docx / .xlsx)
            └── JobStatus.jsx  # Status badge, live change list, download button
```

---

## How It Was Built — Step by Step

### Backend Build Order

#### Step 1 — Scaffold (`requirements.txt`, `config.py`, `models.py`, `main.py`)

The first thing created was the bare skeleton:

- **`requirements.txt`** — pinned all dependencies: FastAPI, Uvicorn, Anthropic SDK, python-docx, openpyxl, matplotlib, Pydantic, pytest, httpx.
- **`.env.example`** — template with `ANTHROPIC_API_KEY`, `AGENT_MODE`, `STORAGE_DIR`.
- **`app/config.py`** — loads env vars via `pydantic-settings`. Contains `resolved_agent_mode` property that auto-selects `real` or `mock` based on whether an API key is present.
- **`app/models.py`** — defines all Pydantic schemas: `Job`, `JobStatus` (enum: pending/running/done/failed), `ChangeEntry`, `JobResponse`.
- **`app/main.py`** — FastAPI app with CORS configured for the Vite dev server (`localhost:5173`) and a `/health` endpoint.

#### Step 2 — Storage Layer (`storage.py`)

Handles all file I/O for jobs. Three-directory layout per job:

```
storage/{job_id}/
    original/   ← uploaded file, never mutated
    working/    ← working copy the agent edits
    result/     ← final validated output served for download
```

Key functions: `save_upload()`, `make_working_copy()`, `get_working_path()`, `save_result()`, `get_result_path()`, `cleanup_job()`.

The design invariant: **the original upload is never touched after being saved**.

#### Step 3 — DocOps Layer (`app/docops/`)

The only layer allowed to touch document bytes. Five files:

- **`session.py`** — `DocumentSession` class. Opens a `.docx` with python-docx or `.xlsx` with openpyxl based on file extension. Exposes `.docx`, `.workbook`, `save()`, and `reload()` (used during output validation).

- **`outline.py`** — `build_outline(session)` produces a compact JSON summary of the document sent to the agent: headings (level + text), paragraph previews (capped at 120 chars each), table dimensions and headers for `.docx`; sheet names, dimensions, and 5-row data preview for `.xlsx`. Keeps token usage low.

- **`docx_ops.py`** — python-docx mutations. All functions take a `DocumentSession`, mutate the working copy, call `session.save_docx()`, and return a short description string.
  - `insert_paragraph_after(anchor_text, new_text, style)` — uses `_p.addnext()` since python-docx has no native insert-at-index
  - `replace_text(old_text, new_text)` — searches all paragraphs and table cells
  - `insert_image_after(anchor_text, image_path, width_inches, caption)` — embeds a PNG
  - `insert_table_after(anchor_text, headers, rows, style)` — inserts a formatted table
  - `insert_heading_after(anchor_text, heading_text, level)` — inserts a heading (level 1–6)

- **`charts.py`** — renders matplotlib charts to a temporary PNG file and returns the path. Sets `matplotlib.use("Agg")` at import (no display required). Supports `pie_chart()` and `bar_chart()`. `build_chart(chart_type, **kwargs)` is the single dispatch entry.

- **`xlsx_ops.py`** — openpyxl mutations: `read_cell`, `write_cell`, `write_range`, `append_row`, `add_sheet`, `delete_sheet`, `rename_sheet`, `edit_table_cell` (1-based row/col).

#### Step 4 — Tool Layer (`app/agent/tools.py`)

Defines the catalog of operations Claude is allowed to call. Two parts:

- **`TOOL_SCHEMAS`** — list of 10 JSON schemas passed to the Claude API as `tools=`. Each schema has a name, description, and `input_schema` (JSON Schema object). Tools: `insert_chart`, `replace_text`, `insert_paragraph`, `insert_heading`, `insert_table` (docx), `write_cell`, `write_range`, `append_row`, `add_sheet`, `edit_table_cell` (xlsx).

- **`dispatch(tool_name, tool_input, session)`** — single entry point that maps a tool name to the correct docops function call. Returns the short description string that feeds back to Claude as `tool_result` and is also stored in the job's change list.

#### Step 5 — Agent Layer (`app/agent/`)

Two files:

- **`prompts.py`** — system prompt that tells Claude to respond only with tool calls (no prose), how to read the outline JSON, and rules: use exact anchor text, don't repeat identical calls, stop when done.

- **`orchestrator.py`** — `run_agent(session, prompt, on_change)` is the public entry point. Dispatches to `_real_loop` or `_mock_loop` based on `config.resolved_agent_mode`.
  - **Real loop**: builds outline → calls Claude with `tools=TOOL_SCHEMAS` → collects `tool_use` blocks → runs `dispatch()` for each → feeds `tool_result` back → repeats up to `MAX_STEPS=10`.
  - **Mock loop**: deterministic offline planner. Handles pie chart, bar chart, replace text, xlsx cell write. Falls back to inserting a note paragraph for unrecognised prompts.
  - `on_change(tool_name, description)` callback fires after each tool — used by the job runner to stream change entries into the job record.

#### Step 6 — Job Runner (`app/jobs.py`)

- **In-memory store** — `dict[str, Job]` with `create_job()`, `get_job()`, `list_jobs()`.
- **`run_job(job_id)`** — background task called by FastAPI's `BackgroundTasks`. Lifecycle: `pending → running` → open working copy → run agent → `_validate()` (calls `session.reload()` to confirm file integrity) → `save_result()` → `running → done`. Any exception sets `running → failed` with the error message.

#### Step 7 — API Routes (`app/routes/jobs.py`)

Four endpoints registered under `/api/jobs`:

| Method | Path | Description |
|---|---|---|
| `POST` | `/api/jobs` | Accept `multipart/form-data` (file + prompt). Validates extension (.docx/.xlsx only), saves upload, creates job, fires `run_job` as background task. Returns 202. |
| `GET` | `/api/jobs/{id}` | Poll job — returns current status and change list. |
| `GET` | `/api/jobs/{id}/result` | Download the edited file. Returns 409 if not done yet. Sets correct `Content-Type` for Word/Excel. |
| `GET` | `/api/jobs` | List all jobs (dev/debug). |

#### Step 8 — Tests (`backend/tests/`)

- **`conftest.py`** — shared `docx_session` and `xlsx_session` fixtures built with real files in pytest `tmp_path`.
- **`test_docops.py`** — unit tests for every docops function: outline, all docx ops, all xlsx ops, chart PNG generation. 23 tests.
- **`test_mock_agent.py`** — integration tests for the mock orchestrator: pie chart, bar chart, replace text, `on_change` callback, fallback, xlsx write. 7 tests.
- **`test_api.py`** — full HTTP tests via `TestClient`: job creation, extension rejection, empty file rejection, polling, 409/404 responses, result download. 10 tests.
- All tests use `monkeypatch` to force `agent_mode=mock` — no API key needed.
- **40/40 tests pass** on Python 3.13.

#### Step 9 — Demo Script (`app/demo.py`)

Runs the full pie-chart flow offline without a server:
```bash
cd backend && python -m app.demo
```
Builds a sample `.docx`, prints the document outline, runs the mock agent, saves result to `demo_output/edited_report.docx`.

---

### Frontend Build Order

#### Step 1 — Project Setup (`package.json`, `vite.config.js`, `index.html`)

- **`package.json`** — React 18, Vite 5, Tailwind CSS 3, PostCSS, Autoprefixer as dependencies.
- **`vite.config.js`** — Vite dev server configured to proxy all `/api` requests to `http://localhost:8000`. This eliminates CORS issues during development.
- **`index.html`** — Minimal HTML shell mounting `<div id="root">`.

#### Step 2 — Tailwind Setup (`tailwind.config.js`, `postcss.config.js`, `index.css`)

- **`tailwind.config.js`** — content paths set to `./src/**/*.{js,jsx}`. Custom font families added: `montserrat` and `inter`.
- **`postcss.config.js`** — wires Tailwind and Autoprefixer into the Vite build pipeline.
- **`index.css`** — imports Montserrat + Inter from Google Fonts, then `@tailwind base/components/utilities`. Defines `body` as `bg-stone-950` dark background with Montserrat as default font. Adds `.spinner` utility class.

**Theme:** dark stone (stone-950 page, stone-900 cards, stone-800 inputs), light stone text (stone-100/400/500), orange accents (orange-500 buttons, orange-400 tool tags, orange-500 drag-over border). Montserrat for headings/body, Inter for buttons and badges.

#### Step 3 — API Module (`src/api.js`)

Single file for all HTTP calls:
- `submitJob(file, prompt)` — `POST /api/jobs` with `multipart/form-data`
- `pollJob(jobId)` — `GET /api/jobs/{id}`
- `resultUrl(jobId)` — returns the download URL string (used as an `<a href>`)

#### Step 4 — Uploader Component (`src/components/Uploader.jsx`)

Drag-and-drop file picker:
- Validates `.docx` / `.xlsx` extension before accepting
- Drag-over state changes border to orange-500 and adds a subtle background tint
- On mobile: "or drag a file here" text is hidden (drag isn't available on touch); file size is hidden to save space
- Selected file shown in a chip with truncated filename and a clear (✕) button
- `min-w-0 flex-1 truncate` ensures long filenames never overflow on small screens

#### Step 5 — JobStatus Component (`src/components/JobStatus.jsx`)

Displays job state after submission:
- Status badge (pending/running/done/failed) with colour-coded styles and a CSS spinner for `running`
- Job ID shown in full on desktop, truncated to 8 chars on mobile
- Live change list: tool name in an orange monospace tag + description text. Stacks vertically on mobile, inline on sm+.
- Error box (red) shown on failure
- On `done`: orange "Download edited file" `<a>` tag pointing to the result URL
- On `done` or `failed`: "Edit another document" link that resets all state
- Action buttons stack full-width on mobile, inline on sm+

#### Step 6 — App Root (`src/App.jsx`)

Orchestrates the full user flow:
- Holds state: `file`, `prompt`, `submitting`, `submitError`, `job`
- `useEffect` with `setInterval` polls `GET /api/jobs/{id}` every 1.5 seconds while status is `pending` or `running`; clears the interval on `done`/`failed` or component cleanup
- Form is hidden once a job exists (replaced by `<JobStatus>`)
- "Edit another document" resets all state and brings the form back
- Fully responsive: `px-4 py-10 sm:px-6 sm:py-14 lg:px-8`, card padding `p-4 sm:p-6`, button tap target larger on mobile

---

## How the Agent Works

```
User prompt + file
       │
       ▼
  build_outline()          ← compact JSON of headings/paragraphs/tables/sheets
       │
       ▼
  Claude (tool_use)        ← receives outline + prompt + tool schemas
       │
       ▼
  dispatch(tool, input)    ← validated call into docops layer
       │
       ▼
  docops mutates           ← working copy only, original untouched
  working copy
       │
       ▼
  tool_result → Claude     ← description of what changed
       │
       ▼
  repeat until done        ← or MAX_STEPS (10) reached
       │
       ▼
  session.reload()         ← integrity check: can the file be re-opened?
       │
       ▼
  save_result()            ← promote working copy → result/
       │
       ▼
  job.status = done        ← frontend polls, shows changes, enables download
```

---

## Running the App

### Requirements

- Python 3.13
- Node.js 18+

### Backend

```bash
cd backend
python3.13 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env        # add your ANTHROPIC_API_KEY
uvicorn app.main:app --reload --port 8000
```

Without an API key the agent runs in **mock mode** automatically — the full pipeline runs offline, supporting the pie-chart, bar-chart, replace-text, and xlsx cell-write flows.

Interactive API docs: `http://localhost:8000/docs`

### Frontend

```bash
cd frontend
npm install
npm run dev                 # http://localhost:5173
```

The Vite dev server proxies `/api` → `http://localhost:8000`.

---

## Running Tests

```bash
cd backend
source .venv/bin/activate
pytest -v
```

Expected output: **40 passed** across 3 test files (docops unit tests, mock agent integration tests, API HTTP tests). No API key required.

---

## Offline Demo

```bash
cd backend
source .venv/bin/activate
python -m app.demo
```

Builds a sample `.docx`, prints the document outline, runs the mock pie-chart flow, and writes the result to `demo_output/edited_report.docx`. No server or API key needed.

---

## API Reference

| Endpoint | Method | Body | Response |
|---|---|---|---|
| `/health` | GET | — | `{"status": "ok"}` |
| `/api/jobs` | POST | `multipart/form-data`: `file` + `prompt` | `202` Job object |
| `/api/jobs/{id}` | GET | — | Job object (poll for status) |
| `/api/jobs/{id}/result` | GET | — | File download (`409` if not done) |
| `/api/jobs` | GET | — | Array of all jobs |

**Job object fields:** `id`, `status` (pending/running/done/failed), `prompt`, `filename`, `created_at`, `updated_at`, `changes` (list of `{tool, description}`), `error`, `result_filename`.

---

## Roadmap

| Priority | Item |
|---|---|
| Next | Broader docx/xlsx operations (more tools) |
| Next | Plan-preview — show the planned tool calls and require confirmation before destructive edits |
| Next | Richer diff — side-by-side before/after view in the UI |
| Later | Replace in-memory job store with SQLite or Redis for persistence across restarts |
| Later | `.pptx` support via python-pptx |
| Later | Prompt caching of the document outline to cut token cost |
| Later | Hosted deploy |
