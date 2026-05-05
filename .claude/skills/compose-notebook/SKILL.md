---
name: compose-notebook
description: >-
  Compose a new marimo notebook in the prx repo by reusing @app.function
  helpers from the existing notebook catalog (notebooks/nb01_*.py onward) to
  answer a PROSPECT chemical-genetics question end-to-end - e.g. "pull the
  Bond 2025 sGR table and look at the shape", "find compounds with similar
  PCL profiles to X", "annotate hits with target/MOA from the reference
  set", "compare CGI profile against the 437-compound reference". Trigger
  whenever the user asks for a notebook, analysis, figure, or vignette that
  touches PROSPECT CGI profiles, sGR tables, PCL similarity, MOA inference,
  Figshare/Dryad data from Bond et al. 2025, or compound/mutant metadata -
  even if they don't explicitly say "marimo" or "reuse the catalog". Use
  this instead of writing standalone analysis code from scratch, and instead
  of duplicating helpers that already exist in the catalog.
---

# Compose a new marimo notebook from the prx catalog

## What this skill is for

The `prx` repo holds a catalog of numbered marimo notebooks under
`notebooks/`. Each defines top-level `@app.function` helpers (loaders for
public datasets, parsers for sGR / PCL tables, plotting utilities, ...) plus
UI cells that exercise them. The functions are the contract; the UI cells
are illustrative.

When a user wants to answer a PROSPECT question - "what's the MOA of this
compound?", "show me the sGR matrix for the reference set", "how does
compound X cluster in PCL space?" - the right move is almost always to
**compose an existing notebook from these helpers**, not to write a new
pipeline from scratch. This skill tells you how.

If the question is answerable as a single SQL query against
metadata/compound tables, prefer adding a `.gsql` file under `queries/`
(jx-style) over spinning up a marimo notebook. Use this skill when the
question genuinely needs Python glue: pooch downloads, polars wrangling,
CGI matrix work, plotting.

## The catalog at a glance

The catalog is currently small. Add a row here whenever a new `nbNN_*.py`
exposes a stable helper.

| Module | Reusable functions / globals | What they do |
|---|---|---|
| `nb01_orientation` | (no helpers; markdown landing page) | Working questions, foundational papers, public data resources, first concrete next steps. Read first. |
| `nb02_figshare_pull` | `figshare_url(file_id)`, `fetch(slug, files, known_hashes)`; globals `FIGSHARE_DIR`, `SMALL_FILES`, `KNOWN_HASHES`, `EXTRACTED_DIRS`, `clusters_tbl` (8,317 x 25), `moas_long` (11,081 x 2 across 71 MOAs), `pcls_long` (5,847 x 2 across 1,140 PCL clusters); `parse_gmt(path)` for .gmt-style files | Pulls Bond et al. 2025 Figshare bundle (the small annotation/cluster archives only - big similarity matrices deferred). Provides the *reference-set spine*: every condition (`<screen-wave>:<broad_id>:<concentration>uM`) joined to its MOA and PCL cluster. SHA-256 pinned in `KNOWN_HASHES`. |

When the question isn't obviously answered by an existing helper, **read
the catalog file itself** (not just this table) before inventing new code.
Helpers carry short docstrings; UI cells are worked examples.

Concrete next-notebook candidates (Bond et al. 2025 Figshare bundle: <https://doi.org/10.6084/m9.figshare.28373561>):

- `nb03_pcl_similarity.py` - pull the (large) `pcl_cluster_similarity_scores`
  archive, lazy-scan via polars/pyarrow, expose `load_pcl_similarity()`,
  `top_k_pcls(condition_id, k)`. This is where the MOA-prediction logic
  starts.
- `nb04_reference_set_join.py` - given Bond 2025 Supplementary Data 1 + 5
  (compound -> annotated MOA), expose `load_reference_set()` and join it
  to `nb02.clusters_tbl` + `nb02.moas_long` for sanity checks against the
  paper's headline counts (437 compounds, 71 MOAs, 1,140 PCLs).
- `nb05_loocv_replay.py` - replay the leave-one-out PCL prediction for a
  single reference compound, against the published thresholds in
  `by_pcl_high_confidence_similarity_score_thresholds_*`. Correctness
  check before doing anything fancier.

## The composition pattern

A composed notebook is a new file in `notebooks/` (e.g.,
`nb02_figshare_pull.py`) that imports catalog helpers as plain Python and
glues them together. Three things matter: **imports**, **interactive UI**,
and **caching**.

### 1. The setup cell - plain Python imports

Each catalog file uses an `nbNN_` prefix precisely so the file is a valid
Python module name. Import them by adding `notebooks/` to `sys.path` and
using a regular `from ...` line. No `importlib`, no dynamic loading -
marimo's `@app.function` decorator exposes the functions at module top
level, so a normal import is all you need.

```python
with app.setup:
    import os
    import sys
    from pathlib import Path

    import marimo as mo
    import polars as pl

    NOTEBOOK_DIR = Path(__file__).parent
    if str(NOTEBOOK_DIR) not in sys.path:
        sys.path.insert(0, str(NOTEBOOK_DIR))

    from nb01_orientation import (
        DATA_DIR,
        EXTERNAL_DATA_DIR,
        PROJ_ROOT,
        RAW_DATA_DIR,
    )
    # from nb02_figshare_pull import load_sgr, load_pcl_similarity   # once it exists
```

Why this works: marimo notebooks are just Python files, and their
`@app.function`-decorated helpers are ordinary top-level `def`s. Python
can't import a module whose filename starts with a digit, which is why
the catalog uses the `nb0N_` prefix - the boring constraint that makes
marimo's "reusing functions" pattern work.

### 2. Interactive UI - widgets, not raw prints

The point of a composed notebook is to let the user **explore** - change
the query, click a different neighbor, regenerate a plot - not to produce
a single static figure. Lean on marimo's widgets:

- **Sidebar for controls.** Consolidate inputs in `mo.sidebar([...])` so
  they stay visible while scrolling.
- **`mo.ui.dropdown`, `mo.ui.text`, `mo.ui.slider`** for typed inputs.
- **`mo.ui.table(df, selection="single")`** for result tables; its
  `.value` is the selected row(s) as a polars DataFrame, which a
  downstream cell reads to drive the next view.
- **`mo.ui.plotly(fig, render_mode="webgl")`** for interactive scatter
  plots over large point clouds (e.g., compound x mutant heatmaps,
  PCL neighborhoods).

**Guard expensive steps with a run button.** Marimo re-runs downstream
cells on every upstream change, which is exactly wrong for things like
fetching a multi-MB Figshare archive or computing a similarity matrix.
Wrap those cells behind `mo.ui.run_button()` + `mo.stop(not run_button.value)`
so they only execute on explicit user click:

```python
@app.cell
def _(mo):
    run_button = mo.ui.run_button(label="Fetch Figshare bundle")
    run_button
    return (run_button,)

@app.cell
def _(mo, run_button):
    mo.stop(not run_button.value)
    sgr = load_sgr()
    return (sgr,)
```

### 3. Caching downloads with pooch

External data (Figshare archives, Dryad RNA-seq, ...) goes to
`data/external/<source>/` and is fetched once with `pooch`. Always pin a
known SHA-256 - even if the first load has to print and copy it; an
unpinned download is a future "why did this analysis change" mystery.

```python
@app.function
def load_sgr() -> pl.DataFrame:
    """Fetch Bond et al. 2025 sGR table from Figshare and return a polars DF."""
    archive = pooch.retrieve(
        url="https://figshare.com/ndownloader/files/<id>",
        known_hash="sha256:<paste-after-first-run>",
        path=EXTERNAL_DATA_DIR / "figshare_28373561",
        progressbar=True,
    )
    return pl.read_parquet(archive)
```

### 4. Conventions

- Notebooks numbered `nb<NN>_<short_description>.py`, two-digit
  zero-padded.
- Helpers stay close to API primitives (polars, duckdb, pooch). Don't
  factor anything out into a separate library - the catalog is the library
  by design (see `CLAUDE.md`).
- Raw data is never edited. Pulled artifacts go to `data/raw/` or
  `data/external/`; transformations land in `data/interim/` or
  `data/processed/<analysis-name>/`.
- ASCII-only glyphs (hyphen `-` only, no em-dashes, en-dashes, or
  arrows) in code, comments, and docstrings.
- Conventional Commits (`feat:`, `fix:`, `docs:`, `refactor:`, `chore:`).

## Process for a new composition

1. **Confirm a kernel is running.** If not, defer to the
   `getting-started` skill first.
2. **Read the catalog table above + the relevant source notebook.** Don't
   guess at helper signatures; the UI cells are worked examples.
3. **Write the new notebook in `notebooks/nbNN_<short_description>.py`.**
   Follow the imports / UI / caching patterns above.
4. **Lint and check:**
       pixi run ruff check notebooks/nbNN_*.py
       pixi run marimo check notebooks/nbNN_*.py
5. **Open the new notebook** in the running kernel via marimo-pair (or
   ask the user to navigate to it).
6. **Add a row to the catalog table** in this SKILL.md describing the new
   notebook's `@app.function` helpers. The catalog table is the contract
   for the *next* composition; if you don't update it, the next session
   has to re-read the file.

## Gotchas

- **Don't add cells whose only output is `print(...)`** - marimo only
  renders the final expression; the print goes to the kernel log, not the
  notebook.
- **Don't wrap markdown cells in `if` guards.** Marimo's reactivity means
  cells only run when their dependencies are ready; an extra guard
  prevents the markdown from rendering at all. (See marimo-notebook skill
  for more.)
- **Pooch + Figshare URLs.** Figshare's per-file download URLs sometimes
  302-redirect through a CDN; pin the SHA-256 to the final content so a
  CDN swap can't silently change the data.
- **PCL "similarity" sign convention.** In the Bond et al. 2025 outputs,
  a higher PCL similarity score means "more like a member of this class"
  - sort descending. Always sanity-check the sign before drawing
  conclusions; don't trust column names blindly.
- **`ctx.packages.add()` after a cell already failed: restart the kernel.**
  When a sandbox cell raises on a missing import (e.g. `pooch` complaining
  about `tqdm`), calling `ctx.packages.add("tqdm")` from marimo-pair
  installs the wheel into the venv *and* edits the notebook's PEP 723
  header - both durable. But the running Python process has already
  cached the import miss in `sys.modules` (or in the offending library's
  internal lazy-import shim), so re-running the cell raises the same
  error. Kill the `marimo edit --sandbox` server and relaunch on a fresh
  port; the new kernel imports cleanly because the header now has the
  dep. Use `ctx.packages.add()` *prophylactically* (before the first
  run) and you can skip the restart.
- **Snapshot `ctx.cells` before bulk run/mutate loops.** Iterating
  `for cid in ctx.cells: ctx.run_cell(cid)` raises `RuntimeError:
  dictionary changed size during iteration` because the reactive runtime
  mutates `ctx.cells` while running. Use
  `for cid in list(ctx.cells.keys()): ctx.run_cell(cid)`. Same applies
  to any loop that creates, deletes, or runs cells - snapshot first.
