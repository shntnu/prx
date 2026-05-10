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
| `nb03_hypomorph_correlation` | `fetch_sgr_archive() -> Path`, `parse_gct(path) -> (matrix np.float32, row_meta pl.DataFrame, col_meta pl.DataFrame)`, `strain_correlation(matrix) -> np.ndarray`; globals `SGR_FILE_ID`, `SGR_ARCHIVE_HASH`, `SGR_GCT_NAME` | Pulls `sGR_for_pcls` (309 MB, 9,427 conditions x 340 strains) from the Bond 2025 Figshare bundle, parses the GCT v1.3 directly, computes the 340 x 340 strain x strain Pearson, and surfaces top neighbors per strain. The *strain-axis* view of the same matrix Bond et al. used for PCL clustering on the condition axis. |
| `nb04_pretrained_baseline` | `fetch_clusters_archive() -> Path`, `per_compound_labels(clusters_tbl) -> pl.DataFrame`, `compound_cgi_profiles(clusters_tbl, sgr_matrix, sgr_col_meta, broad_ids) -> (np.ndarray, list[str])` (median per compound), `compound_condition_features(clusters_tbl, sgr_matrix, sgr_col_meta, broad_ids) -> (np.ndarray, np.ndarray)` (one row per (compound, dose, wave)), `smiles_to_morgan(smiles, radius, nbits) -> (np.ndarray, list[bool])`, `loocv_1nn_predictions(features, moas, metric) -> np.ndarray`, `loocv_per_condition_predictions(features, compound_ids, metric) -> (np.ndarray, np.ndarray)` (best-match across all-of-other-compound's conditions), `score_predictions(predictions, primary_moas, moa_sets) -> dict`, `same_moa_tanimoto_distribution(fps, primary_moas) -> pl.DataFrame`; globals `CLUSTERS_FILE_ID`, `CLUSTERS_ARCHIVE_HASH`, `MORGAN_RADIUS`, `MORGAN_NBITS` | Structure-only baseline vs two CGI baselines (per-dose best-match, and median-aggregated) for MOA classification on the Bond 2025 reference set, all under LOO 1-NN. Companion diagnostic: same-MOA vs cross-MOA Tanimoto distribution over Morgan FPs to surface within-MOA structural redundancy that biases the structure baseline upward. Adds rdkit + scikit-learn to the dep set. |
| `nb05_collapse_diagnostic` | `pairwise_tanimoto(fps) -> np.ndarray`, `pairwise_pearson(profiles) -> np.ndarray`, `pair_table(broad_ids, primary_moas, tanimoto_sim, cgi_corr) -> pl.DataFrame` (upper-triangle long-format with same-MOA flag and Tanimoto bin); globals `TANIMOTO_DISTANT_CUTOFF`, `TANIMOTO_BIN_EDGES`, `TANIMOTO_BIN_LABELS` | Companion to nb04. For every pair of Bond reference compounds, contrasts pairwise Tanimoto over Morgan FPs against pairwise Pearson over median CGI profiles, stratified by same vs cross primary MOA. Headline: among chemistry-distant pairs (Tanimoto<0.30), is same-MOA CGI similarity above the cross-MOA background? If yes, CGI carries MOA info beyond chemistry; if no, the reference-set CGI signal collapses to chemistry. Reuses nb03 + nb04 helpers; no new deps. |
| `nb06_cgi_shape_diversity` | `fetch_pcls_archive() -> Path`, `pcl_compound_table(pcls_long, clusters_tbl) -> pl.DataFrame` (one row per (pcl, condition, broad_id) triple), `rarefaction(triples, unit, sample_sizes, n_seeds, seed) -> pl.DataFrame`, `rarefaction_envelope(curve) -> pl.DataFrame`, `hill_numbers(counts) -> dict`; globals `PCLS_FILE_ID`, `PCLS_ARCHIVE_HASH`, `RAREFACTION_SEEDS` | Public-data floor for "how many CGI shapes does PROSPECT actually see". Joins Bond's authoritative PCL labels (1,140 PCLs across 5,847 condition-PCL pairs) to compound metadata, then runs rarefaction over PCL coverage at both condition and compound granularity, plus Hill numbers (N0, N1=exp Shannon, N2=inv Simpson) for effective-cluster counts under different evenness assumptions. Reuses nb02 (`parse_gmt`) + nb04 (`fetch_clusters_archive`); transitively inherits nb04's rdkit + scikit-learn deps even though nb06 itself uses neither (gotcha noted). |

When the question isn't obviously answered by an existing helper, **read
the catalog file itself** (not just this table) before inventing new code.
Helpers carry short docstrings; UI cells are worked examples.

Concrete next-notebook candidates (Bond et al. 2025 Figshare bundle: <https://doi.org/10.6084/m9.figshare.28373561>):

- `nb07_pcl_similarity.py` - pull the large `pcl_cluster_similarity_scores`
  archive, lazy-scan it, expose `load_pcl_similarity()` and
  `top_k_pcls(condition_id, k)`, then connect a query condition to its
  nearest PCLs.
- `nb08_loocv_replay.py` - replay one leave-one-out PCL prediction against
  the published high-confidence similarity thresholds. This is the
  correctness check before building broader MOA-calling notebooks.
- `nb09_reference_moa_browser.py` - turn the reference-set spine from nb02
  plus the labels and CGI baselines from nb04 into an interactive compound
  browser: query compound -> annotated MOA -> nearest structure/CGI/PCL
  neighbors.

## The composition pattern

A composed notebook is a new file in `notebooks/` (e.g.,
`nb02_figshare_pull.py`) that imports catalog helpers as plain Python and
glues them together. Four things matter: the **PEP 723 header**,
**imports**, **interactive UI**, and **caching**.

### 0. The PEP 723 header - get it right the first time

Sandbox-mode marimo provisions a venv from the PEP 723 header at the top
of the notebook file *before any cell runs*. If the header is wrong, the
first sign is an `ImportError` on kernel boot or the first run of a cell.
Marimo's UI offers to install missing packages, but the sandbox venv is
locked to one notebook, so you have to click through *and* kill + relaunch
the server (the failed import is cached in `sys.modules`). Each
round-trip eats 30-60 seconds of the user's time. Get the header right
up front and the whole class of failures disappears.

**Two issues hit every notebook in this repo if you don't pin against them:**

- **`requires-python = ">=3.12"` is too loose.** uv defaults to the
  newest interpreter it can find - on this machine that's currently
  Python 3.14. Several current libraries (notably `altair==5.5.0`, and
  any other lib using PEP 728's `TypedDict(closed=True)` syntax) are
  still catching up to 3.14 and raise `TypeError: _TypedDictMeta.__new__()
  got an unexpected keyword argument 'closed'` on import. Pin the upper
  bound to keep uv on 3.13: `requires-python = ">=3.12,<3.14"`. Bump
  the upper bound when the ecosystem catches up, not before.
- **Don't `.to_pandas()` for altair - pass the polars DataFrame
  directly.** altair 5.5+ accepts polars DataFrames natively via
  narwhals: `alt.Chart(df).mark_bar()...` works as-is. The older
  `alt.Chart(df.to_pandas())` pattern drags in *two* heavy deps that
  are not in the standard set: `pyarrow` (for the arrow-to-pandas
  bridge) AND `pandas` itself. Neither is pulled in transitively by
  `polars` or `marimo`. Drop the `.to_pandas()` call and altair just
  works on the polars DF. If some other API genuinely needs pandas,
  add *both* `pyarrow==24.0.0` and a `pandas` pin to the deps - one
  without the other still fails.

**Validated header for the current dep set in this repo:**

```python
# /// script
# requires-python = ">=3.12,<3.14"
# dependencies = [
#     "marimo",
#     "polars==1.40.1",
#     "pooch==1.9.0",
#     "tqdm==4.67.3",
#     # add only as needed:
#     # "numpy==2.2.0",
#     # "altair==5.5.0",      # pass polars DataFrames directly - skip pyarrow + pandas
# ]
# ///
```

Other catalog notebooks use this set; copying it gives you a known-good
baseline.

**Smoke-test the header before launching marimo.** A 5-second `uv run`
catches dep mistakes against an ad-hoc venv, instead of paying the cost
of a sandbox provision + a UI install prompt + a kernel restart. Run from
the prx repo root, listing every dep in your header *and* exercising the
runtime path your notebook actually takes. Always pass `--no-project` so
`uv` treats the command as an ad-hoc dependency smoke test rather than a
project install. This also protects you when the agent's cwd is a sibling
repo with its own package metadata.

```bash
cd /path/to/prx && uv run --no-project --python 3.13 \
    --with marimo --with polars==1.40.1 --with pooch==1.9.0 \
    --with altair==5.5.0 \
    python3 -c "
import polars as pl, altair as alt
chart = alt.Chart(pl.DataFrame({'a':[1,2],'b':[3,4]})).mark_bar().encode(x='a:Q', y='b:Q')
chart.to_dict()  # forces narwhals to actually walk the polars frame
print('ok')"
```

A bare `import altair` only catches *static* import errors. Building a
chart from a polars DF and calling `.to_dict()` exercises the narwhals
conversion path and catches missing-bridge errors (e.g., a stray
`.to_pandas()` somewhere that needs pandas + pyarrow). If it prints
`ok`, the sandbox will too. If not, fix the header or the chart code
*first*; only then launch marimo.

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
   Follow the imports / UI / caching patterns above. **Start from the
   PEP 723 header in section 0** - it has been validated against the
   current dep set; deviating costs time later.
4. **Smoke-test the deps** with the `uv run --python 3.13 --with ...`
   one-liner from section 0. Cheaper than a sandbox restart.
5. **Lint and check:**
       cd /path/to/prx
       uvx ruff format notebooks/nbNN_*.py
       uvx ruff check notebooks/nbNN_*.py
       uv run --no-project --python 3.13 --with marimo marimo check notebooks/nbNN_*.py
   `marimo check` exits 0 silently on success; non-zero with a list of
   `critical[multiple-definitions]` errors if you've reused a top-level
   variable name across cells (see the gotcha below). prx has no pixi
   env -- earlier versions of this skill said `pixi run ...`; that was
   wrong.
6. **Open the new notebook** in the running kernel via marimo-pair (or
   ask the user to navigate to it).
7. **Add a row to the catalog table** in this SKILL.md describing the new
   notebook's `@app.function` helpers. The catalog table is the contract
   for the *next* composition; if you don't update it, the next session
   has to re-read the file.

## Gotchas

- **`from nbNN_other import helper` inherits the whole module's deps.**
  Importing a helper executes the module top-level, which runs the
  `with app.setup:` block - that block's imports must all resolve in
  the *consumer* notebook's sandbox. Practical effect: if you import
  any helper from `nb04_pretrained_baseline`, your notebook's PEP 723
  header needs `rdkit` and `scikit-learn` even if your code doesn't
  touch either, because nb04's setup imports them at top level. Match
  the deps exactly when importing across notebooks; smoke-test the
  full transitive set with `uv run --no-project --with ...` before
  launching marimo. (nb06 hit this on first launch.)
- **Top-level variable names must be unique across cells.** Marimo's
  reactivity model needs a single definition per name in the global
  namespace; reusing common names like `chart`, `summary`, `df`, `result`
  across cells fails `marimo check` with a `critical[multiple-definitions]`
  error. Two fixes: rename the shadowing var (`per_moa_chart`,
  `redundancy_summary`), or prefix it with an underscore to make it
  cell-private (`_chart`, `_summary`). Underscore-prefix is the right
  move for purely-rendering locals; rename when the value is genuinely
  consumed by a downstream cell.
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
  dep.

  This is a *recovery* path, not a workflow. The proactive fix is to
  start from the validated PEP 723 header and run the smoke-test
  one-liner *before* launching marimo - see "0. The PEP 723 header"
  above. A 5-second `uv run` is much cheaper than a sandbox provision +
  install-prompt + kernel restart cycle.
- **Snapshot `ctx.cells` before bulk run/mutate loops.** Iterating
  `for cid in ctx.cells: ctx.run_cell(cid)` raises `RuntimeError:
  dictionary changed size during iteration` because the reactive runtime
  mutates `ctx.cells` while running. Use
  `for cid in list(ctx.cells.keys()): ctx.run_cell(cid)`. Same applies
  to any loop that creates, deletes, or runs cells - snapshot first.
- **Molab session snapshots are matched by `code_hash`, not by position.**
  Each cell in `notebooks/__marimo__/session/*.json` carries the hash of the
  cell source it was generated from; molab attaches the stored output to a
  source cell only if the hashes match, otherwise that cell renders empty
  in the public preview. A whitespace-only `ruff format` pass shifts every
  hash. Always run `marimo export session --sandbox` **after** the final
  source edit / formatter pass, and commit the refreshed `.json` files in
  the same change that touched the `.py` files. If a molab preview looks
  emptier than the live editor, suspect a stale snapshot first.
