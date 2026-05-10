# AGENTS.md - prx

Project-specific guidance for agents working in this repository. This is the
public, runnable catalog of marimo notebooks for PROSPECT chemical-genetics
analysis. Planning, progress, and dated artifacts live in the sibling private
repo `../prx-dev/`; cross-instance coordination lives in the primary
[`jx`](https://github.com/broadinstitute/jx) repo.

`README.md` is the human entry point. The skills under `.claude/skills/` are
the operational entry points: `getting-started` for first-run setup and
`compose-notebook` for adding a new analysis.

## Validation Rule

After composing or editing any notebook in `notebooks/`, launch it in a
marimo sandbox kernel and run all cells before reporting the task complete.
`ruff check` and `marimo check` only catch static problems; they do not catch
wrong outputs, NaN-filled tables, broken altair encodings, empty plots, or
silently-zero pivots. Show the user the live URL when working interactively.

Minimal launch:

```bash
PORT=$(python -c "import socket; s=socket.socket(); s.bind(('127.0.0.1',0)); print(s.getsockname()[1])")
env -u PYTHONPATH uvx marimo edit --sandbox --headless --no-token --port $PORT notebooks/nbNN_*.py
```

For notebooks that can export reliably, refresh the molab session snapshot:

```bash
env -u PYTHONPATH uvx marimo export session --sandbox notebooks/nbNN_*.py
```

Then run static checks:

```bash
uvx ruff format --check notebooks/
uvx ruff check notebooks/
uvx marimo check notebooks/*.py
```

## Architecture

- Catalog over library. Helpers live as `@app.function` cells in numbered
  notebooks. Later notebooks import from earlier notebooks by adding
  `notebooks/` to `sys.path`.
- Notebook deps are PEP 723 inline headers; `uv` provisions a per-notebook
  sandbox venv.
- `uv` is the runtime contract for users. Do not add Nix unless there is a
  concrete reason.
- Smoke-test PEP 723 headers with `uv run --no-project --python 3.13 --with
  ...` before launching marimo, especially when importing helpers across
  notebooks.
- Raw data is never edited. Pulled artifacts go to `data/raw/` or
  `data/external/<source>/`; transformations land in `data/interim/` or
  `data/processed/<analysis-name>/`. Pin SHA-256 on every `pooch` fetch.
- Do not add a Python package until repeated cross-notebook imports make the
  notebook-as-library pattern painful.

## Conventions

- Notebooks: `nbNN_<short_description>.py`, two-digit zero-padded.
- Top-level variable names must be unique across cells. Use `_chart`,
  `_summary`, and similar names for cell-private locals; rename values that
  are consumed downstream.
- Do not call `.to_pandas()` for altair; pass polars frames directly via
  narwhals.
- Use Conventional Commits (`feat:`, `fix:`, `docs:`, `refactor:`, `chore:`).
- Use ASCII-only glyphs in code, comments, and docs.

## When the Question Fits the Catalog

Almost every PROSPECT request should compose existing helpers:

- orientation and public resources -> `nb01_orientation`
- Figshare pull and reference-set spine -> `nb02_figshare_pull`
- sGR GCT parsing and strain correlation -> `nb03_hypomorph_correlation`
- structure-only and CGI-profile baselines -> `nb04_pretrained_baseline`
- same-MOA CGI signal after chemistry control -> `nb05_collapse_diagnostic`
- PCL rarefaction and CGI-shape diversity -> `nb06_cgi_shape_diversity`

Read `.claude/skills/compose-notebook/SKILL.md` before writing new analysis
code.
