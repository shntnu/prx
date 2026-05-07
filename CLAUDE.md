# CLAUDE.md - prx

Project-specific guidance for Claude Code working in this repository. This is the **public, runnable catalog** of marimo notebooks for PROSPECT chemical-genetics analysis. Planning, progress, and dated artifacts live in the sibling private repo `../prx-dev/`.

`README.md` is the human entry point. The two skills under `.claude/skills/` are the agent entry points: `getting-started` for first-run setup, `compose-notebook` for adding a new analysis (it carries the catalog table - read it before composing).

## The non-negotiable rule: render before done

After composing or editing any notebook in `notebooks/`, **launch it in a marimo sandbox kernel and run all cells before reporting the task complete.** `ruff check` and `marimo check` only catch static problems; they don't catch wrong outputs, NaN-filled tables, broken altair encodings, empty plots, or silently-zero pivots. Show the user the live URL.

The pattern (also written up in `compose-notebook/SKILL.md`):

```bash
# from prx/
PORT=$(python3 -c "import socket; s=socket.socket(); s.bind(('127.0.0.1',0)); print(s.getsockname()[1])")
uvx marimo edit --sandbox --no-token --port $PORT notebooks/nbNN_*.py
```

Run in the background, then either ask the user to open `http://localhost:$PORT` or attach via the `marimo-pair` skill and queue all cells with `ctx.run_cell` over `list(ctx.cells.keys())`. Inspect a few key runtime values (shapes, headline tables) to confirm the analysis actually produced sensible numbers, then report URL + numbers to the user.

This rule has bitten twice (nb04, nb05) - hence the prominence here.

## Settled decisions - do not re-propose

1. **Catalog over library.** Helpers live as `@app.function`-hoistable cells inside numbered notebooks. No Python package, no Snakemake. See `compose-notebook/SKILL.md` for the composition pattern.
2. **No pyproject in this repo.** Notebook deps are PEP 723 inline headers; `uv` provisions a per-notebook sandbox venv. The validated header (Python 3.13 ceiling, common deps) is in `compose-notebook/SKILL.md` section 0 - copy it; don't deviate without reason.
3. **No Nix.** A previous `flake.nix` was removed. `uv` alone is the runtime contract for users.
4. **Smoke-test the PEP 723 header** with `uv run --no-project --python 3.13 --with ...` before launching marimo. Always pass `--no-project` - prx has no `pyproject.toml`, but if cwd is a sibling (e.g. `prx-dev`) that does, uv will try to install it as editable and the smoke-test fails before your deps resolve.

## Conventions

- Notebooks: `nbNN_<short_description>.py`, two-digit zero-padded. Each one defines `@app.function` helpers that downstream notebooks import.
- Top-level variable names must be unique across cells (marimo reactivity). Use `_chart`, `_summary` for cell-private locals; rename when the value is genuinely consumed downstream. `marimo check` flags violations as `critical[multiple-definitions]`.
- Don't `.to_pandas()` for altair - pass polars frames directly via narwhals. The `.to_pandas()` path drags in pandas + pyarrow that aren't otherwise needed.
- Conventional Commits (`feat:`, `fix:`, `docs:`, `refactor:`, `chore:`).
- ASCII-only glyphs in code, comments, and docs - hyphen `-` only, no em-dashes / en-dashes / arrows.
- Cell Painting is title-case (proper noun). Domain vocab (mAP, perturbation, sGR, CGI, PCL, MOA, ORF, CRISPRi, JUMP, sphering, batch effects, knockdown, mutant-selective, hypomorph) is assumed understood; don't define it back to the user.
- Raw data is never edited. Pulled artifacts go to `data/raw/` or `data/external/<source>/`; transformations land in `data/interim/` or `data/processed/<analysis-name>/`. Pin SHA-256 on every pooch fetch.

## When the question fits the catalog

Almost every PROSPECT analysis request - "MOA of compound X", "sGR matrix shape", "PCL neighborhood of Y", "compare CGI profile against the reference set" - is answerable by composing existing helpers, not writing a fresh pipeline. Read the catalog table in `compose-notebook/SKILL.md` first. If a helper does what you need, import it; if not, add a new `@app.function` to the right notebook (or a new `nbNN_*.py`) and update the catalog table.
