# /// script
# requires-python = ">=3.12,<3.14"
# dependencies = [
#     "marimo",
#     "altair==5.5.0",
#     "numpy==2.2.0",
#     "polars==1.40.1",
#     "pooch==1.9.0",
#     "rdkit==2024.9.6",
#     "scikit-learn==1.6.1",
#     "tqdm==4.67.3",
# ]
# ///

import marimo

__generated_with = "0.23.5"
app = marimo.App(width="medium")

with app.setup:
    import sys
    import tarfile
    from pathlib import Path

    import altair as alt
    import marimo as mo
    import numpy as np
    import polars as pl
    import pooch

    NOTEBOOK_DIR = Path(__file__).parent
    PROJ_ROOT = NOTEBOOK_DIR.parent
    EXTERNAL_DATA_DIR = PROJ_ROOT / "data" / "external"
    FIGSHARE_DIR = EXTERNAL_DATA_DIR / "figshare_28373561"

    if str(NOTEBOOK_DIR) not in sys.path:
        sys.path.insert(0, str(NOTEBOOK_DIR))

    from nb02_figshare_pull import parse_gmt  # noqa: E402
    from nb04_pretrained_baseline import fetch_clusters_archive  # noqa: E402

    PCLS_FILE_ID = 57955897
    PCLS_ARCHIVE_NAME = "pcls_archive.tar.gz"
    PCLS_ARCHIVE_HASH = "sha256:abe99e71a47baa301ed5ccc17277d495db2a60a5f49a61a0e1081ddf6de80c11"
    PCLS_TXT_NAME = "pcls.txt"

    RAREFACTION_SEEDS = 50


@app.cell(hide_code=True)
def _():
    mo.md(r"""
    # nb06 - CGI shape diversity

    **Diagnostic.** How many distinct CGI shapes does the public Bond data
    actually cover, and is the curve saturating? If it is, expanding the
    compound library yields diminishing returns on shape coverage; if it's
    still rising, more compounds buy real new biology. Public-data floor
    for Deb's "how many shapes does PROSPECT actually see" question.

    **Why it matters.** Any chemistry-only model that predicts CGI shapes
    can only generalize to shapes the training data covers. Bond et al.
    spectrally cluster their 9,427 conditions into 1,140 PCLs (Perturbagen
    CLasses). PCLs are the authoritative public-data shape labels - more
    informative than re-clustering on our side. The question is whether
    the public 5,847-condition / ~1,000-compound subset already saturates
    those 1,140 shape classes (-> chemistry diversity is the bottleneck,
    not shape diversity) or whether the curve is still climbing
    (-> bigger libraries genuinely sample more shapes).

    **Method.**

    1. Pull the Bond `pcls.txt` (.gmt-style) and join to `clusters_tbl`
       to get a long table of (PCL, condition, broad_id) triples.
    2. Headline counts; PCL size distribution (per-PCL n_conditions and
       n_compounds).
    3. Rarefaction at condition granularity: for sample size N from 100
       to all conditions, sample N conditions without replacement (50
       seeds), count distinct PCLs they cover.
    4. Rarefaction at compound granularity: same idea, but unit is
       broad_id - all of a compound's conditions are pulled together.
       This is the more relevant axis for "what does my N-compound
       library cover?"
    5. Hill diversity numbers from the per-PCL frequency vector:
       N0 (raw count), N1 (exp Shannon), N2 (inverse Simpson). The
       gap between N0 and N1/N2 quantifies how skewed the PCL
       distribution is.

    **Scope.** Public Bond reference-set PCL assignments only. The
    ~5,847 conditions / ~1,000 compounds covered by `pcls.txt` are a
    subset of the full 9,427-condition spectral clustering output -
    these are the PCLs that survived the predictive-cluster filter and
    are the right set for the "how many *useful* shapes" question.
    """)
    return


@app.cell(hide_code=True)
def _():
    mo.md(r"""
    ## Pull PCL assignments and join to compound metadata
    """)
    return


@app.function
def fetch_pcls_archive() -> Path:
    """Download and extract the Bond pcls.txt archive."""
    archive = Path(
        pooch.retrieve(
            url=f"https://ndownloader.figshare.com/files/{PCLS_FILE_ID}",
            known_hash=PCLS_ARCHIVE_HASH,
            fname=PCLS_ARCHIVE_NAME,
            path=FIGSHARE_DIR,
            progressbar=True,
        )
    )
    extract_dir = FIGSHARE_DIR / "pcls"
    txt_path = extract_dir / PCLS_TXT_NAME
    if not txt_path.exists():
        extract_dir.mkdir(exist_ok=True)
        with tarfile.open(archive, "r:gz") as t:
            t.extractall(extract_dir, filter="data")
    return txt_path


@app.function
def pcl_compound_table(pcls_long: pl.DataFrame, clusters_tbl: pl.DataFrame) -> pl.DataFrame:
    """Join pcls_long (set_name=pcl_id, condition_id) with clusters_tbl (cid, broad_id).

    Returns one row per (pcl, condition, broad_id) triple. Rows where the
    condition has no broad_id mapping in clusters_tbl are dropped.
    """
    cid_to_broad = clusters_tbl.select("cid", "broad_id").filter(pl.col("broad_id").is_not_null()).unique(subset="cid")
    return (
        pcls_long.rename({"set_name": "pcl_id", "condition_id": "cid"})
        .join(cid_to_broad, on="cid", how="inner")
        .select("pcl_id", "cid", "broad_id")
    )


@app.cell
def _():
    pcls_long = parse_gmt(fetch_pcls_archive())
    clusters_tbl = pl.read_csv(
        fetch_clusters_archive(),
        separator="\t",
        infer_schema_length=10_000,
    )
    triples = pcl_compound_table(pcls_long, clusters_tbl)
    n_pcls = triples["pcl_id"].n_unique()
    n_conditions = triples["cid"].n_unique()
    n_compounds = triples["broad_id"].n_unique()
    mo.md(
        f"- `pcls_long`: {pcls_long.height:,} (pcl, condition) rows across "
        f"{pcls_long['set_name'].n_unique():,} PCLs (raw .gmt)\n"
        f"- after joining to `clusters_tbl`: **{triples.height:,} triples** spanning "
        f"**{n_pcls:,} PCLs**, **{n_conditions:,} conditions**, **{n_compounds:,} compounds**"
    )
    return n_compounds, n_conditions, n_pcls, triples


@app.cell(hide_code=True)
def _():
    mo.md(r"""
    ## PCL size distribution

    Per PCL: how many distinct conditions and distinct compounds populate
    it? The shape of this distribution drives diversity - a few huge PCLs
    plus a long tail of singletons looks very different from a flat
    distribution, even at the same raw count.
    """)
    return


@app.cell
def _(triples):
    pcl_sizes = (
        triples.group_by("pcl_id")
        .agg(
            pl.col("cid").n_unique().alias("n_conditions"),
            pl.col("broad_id").n_unique().alias("n_compounds"),
        )
        .sort("n_conditions", descending=True)
    )
    pcl_size_summary = pl.DataFrame(
        {
            "metric": ["n_conditions", "n_compounds"],
            "min": [pcl_sizes["n_conditions"].min(), pcl_sizes["n_compounds"].min()],
            "median": [pcl_sizes["n_conditions"].median(), pcl_sizes["n_compounds"].median()],
            "p95": [pcl_sizes["n_conditions"].quantile(0.95), pcl_sizes["n_compounds"].quantile(0.95)],
            "max": [pcl_sizes["n_conditions"].max(), pcl_sizes["n_compounds"].max()],
            "mean": [pcl_sizes["n_conditions"].mean(), pcl_sizes["n_compounds"].mean()],
        }
    )
    mo.md("### Per-PCL size distribution")
    mo.ui.table(pcl_size_summary, page_size=5)
    return (pcl_sizes,)


@app.cell(hide_code=True)
def _(pcl_sizes):
    _hist = (
        alt.Chart(pcl_sizes)
        .mark_bar()
        .encode(
            x=alt.X("n_compounds:Q", bin=alt.Bin(maxbins=40), title="compounds per PCL"),
            y=alt.Y("count():Q", title="number of PCLs"),
            tooltip=["count():Q"],
        )
        .properties(width=520, height=240, title="PCL size distribution (compounds per PCL)")
    )
    mo.ui.altair_chart(_hist)
    return


@app.cell(hide_code=True)
def _():
    mo.md(r"""
    ## Rarefaction

    The core diagnostic. For each candidate sample size N, randomly draw
    N units (conditions or compounds) without replacement and count the
    distinct PCLs covered. Repeat across many seeds, take the mean and
    the 5th / 95th percentiles for an envelope. Curve saturates -> shape
    coverage is data-bounded, not sampling-bounded; curve is still
    rising at the largest N -> more units would yield more shapes.
    """)
    return


@app.function
def rarefaction(
    triples: pl.DataFrame,
    unit: str,
    sample_sizes: np.ndarray,
    n_seeds: int = 50,
    seed: int = 0,
) -> pl.DataFrame:
    """Rarefaction over PCL coverage as the unit count grows.

    `triples` has columns (`pcl_id`, `cid`, `broad_id`); `unit` selects
    `cid` or `broad_id` as the sampling unit. For each (n, seed), draws
    n unique units without replacement and counts the number of distinct
    pcls covered by the union of their PCL memberships.

    Returns long df: (unit, n, seed, n_pcls, frac_pcls).
    """
    grouped = triples.group_by(unit).agg(pl.col("pcl_id").unique().alias("pcls"))
    units = grouped[unit].to_numpy()
    pcl_lists = grouped["pcls"].to_list()
    total_pcls = triples["pcl_id"].n_unique()
    rng = np.random.default_rng(seed)
    rows: list[dict] = []
    sample_sizes = np.asarray(sample_sizes, dtype=np.int64)
    for s in range(n_seeds):
        perm = rng.permutation(len(units))
        covered: set = set()
        next_idx = 0
        for n in sample_sizes:
            n = int(min(n, len(units)))
            while next_idx < n:
                covered.update(pcl_lists[perm[next_idx]])
                next_idx += 1
            rows.append(
                {
                    "unit": unit,
                    "n": int(n),
                    "seed": int(s),
                    "n_pcls": len(covered),
                    "frac_pcls": len(covered) / total_pcls,
                }
            )
    return pl.DataFrame(rows)


@app.function
def rarefaction_envelope(curve: pl.DataFrame) -> pl.DataFrame:
    """Mean / p05 / p95 of n_pcls and frac_pcls per (unit, n) across seeds."""
    return (
        curve.group_by(["unit", "n"])
        .agg(
            pl.col("n_pcls").mean().alias("mean_n_pcls"),
            pl.col("n_pcls").quantile(0.05).alias("p05_n_pcls"),
            pl.col("n_pcls").quantile(0.95).alias("p95_n_pcls"),
            pl.col("frac_pcls").mean().alias("mean_frac"),
        )
        .sort(["unit", "n"])
    )


@app.cell
def _(n_compounds, n_conditions, triples):
    cond_sizes = np.unique(
        np.concatenate(
            [
                np.array([1, 2, 5, 10, 20, 50, 100, 200, 500, 1000, 2000, n_conditions], dtype=np.int64),
                np.geomspace(50, n_conditions, num=20).astype(np.int64),
            ]
        )
    )
    cond_sizes = cond_sizes[(cond_sizes >= 1) & (cond_sizes <= n_conditions)]
    comp_sizes = np.unique(
        np.concatenate(
            [
                np.array([1, 2, 5, 10, 20, 50, 100, 200, 500, n_compounds], dtype=np.int64),
                np.geomspace(20, n_compounds, num=20).astype(np.int64),
            ]
        )
    )
    comp_sizes = comp_sizes[(comp_sizes >= 1) & (comp_sizes <= n_compounds)]

    cond_curve = rarefaction(triples, unit="cid", sample_sizes=cond_sizes, n_seeds=RAREFACTION_SEEDS, seed=0)
    comp_curve = rarefaction(triples, unit="broad_id", sample_sizes=comp_sizes, n_seeds=RAREFACTION_SEEDS, seed=1)
    curve = pl.concat([cond_curve, comp_curve])
    envelope = rarefaction_envelope(curve)
    return (envelope,)


@app.cell(hide_code=True)
def _(envelope, n_pcls):
    band = (
        alt.Chart(envelope)
        .mark_area(opacity=0.25)
        .encode(
            x=alt.X("n:Q", title="sampled units (log)", scale=alt.Scale(type="log")),
            y=alt.Y("p05_n_pcls:Q", title="distinct PCLs covered"),
            y2="p95_n_pcls:Q",
            color=alt.Color("unit:N", title="unit"),
        )
    )
    line = (
        alt.Chart(envelope)
        .mark_line(point=True)
        .encode(
            x=alt.X("n:Q", scale=alt.Scale(type="log")),
            y=alt.Y("mean_n_pcls:Q"),
            color=alt.Color("unit:N"),
            tooltip=["unit", "n", "mean_n_pcls", "p05_n_pcls", "p95_n_pcls"],
        )
    )
    ceiling = (
        alt.Chart(pl.DataFrame({"n_pcls": [n_pcls]})).mark_rule(strokeDash=[4, 4], color="gray").encode(y="n_pcls:Q")
    )
    mo.ui.altair_chart((band + line + ceiling).properties(width=620, height=380))
    return


@app.cell(hide_code=True)
def _():
    mo.md(r"""
    ### Saturation diagnostic

    For each unit, what fraction of all PCLs is covered at the largest
    sampled N, and what's the marginal coverage rate (delta n_pcls per
    delta N) over the last 10% of the curve? A flat tail with low
    marginal rate -> saturated; a tail still climbing at non-trivial
    slope -> not saturated.
    """)
    return


@app.cell
def _(envelope):
    saturation = []
    for unit_name, sub in envelope.group_by("unit"):
        sub_sorted = sub.sort("n")
        last = sub_sorted.tail(1).row(0, named=True)
        tail_start_n = sub_sorted["n"].quantile(0.90)
        tail = sub_sorted.filter(pl.col("n") >= tail_start_n)
        if tail.height >= 2:
            n_a, n_b = tail["n"][0], tail["n"][-1]
            p_a, p_b = tail["mean_n_pcls"][0], tail["mean_n_pcls"][-1]
            slope = (p_b - p_a) / max(n_b - n_a, 1)
        else:
            slope = float("nan")
        saturation.append(
            {
                "unit": unit_name[0],
                "max_n": last["n"],
                "max_n_pcls": last["mean_n_pcls"],
                "max_frac_pcls": last["mean_frac"],
                "tail_slope_pcls_per_unit": slope,
            }
        )
    saturation_df = pl.DataFrame(saturation)
    mo.ui.table(saturation_df, page_size=5)
    return


@app.cell(hide_code=True)
def _():
    mo.md(r"""
    ## Hill diversity numbers

    Raw PCL count overstates effective diversity when the distribution is
    skewed - a long tail of near-singleton PCLs inflates N0 without adding
    much usable signal. The Hill numbers are a one-parameter family:

    - **N0 = K** (total distinct PCLs)
    - **N1 = exp(Shannon entropy)** - effective number weighted by typical members
    - **N2 = 1 / Simpson** - effective number weighted by abundant members

    `N1 / N0` and `N2 / N0` are the "evenness" lift; values close to 1
    mean an even distribution; values much smaller than 1 mean a few
    PCLs dominate. Computed both at the condition level (each
    triple-row is one weight unit) and at the compound level (each
    (compound, pcl) is one unit).
    """)
    return


@app.function
def hill_numbers(counts: np.ndarray) -> dict[str, float]:
    """N0, N1, N2 from a count vector (one entry per group)."""
    counts = counts[counts > 0]
    p = counts / counts.sum()
    return {
        "N0": float(len(counts)),
        "N1": float(np.exp(-np.sum(p * np.log(p)))),
        "N2": float(1.0 / np.sum(p**2)),
    }


@app.cell
def _(triples):
    cond_counts = triples.group_by("pcl_id").agg(pl.col("cid").n_unique().alias("n")).sort("n", descending=True)
    comp_counts = triples.group_by("pcl_id").agg(pl.col("broad_id").n_unique().alias("n")).sort("n", descending=True)
    cond_hill = hill_numbers(cond_counts["n"].to_numpy())
    comp_hill = hill_numbers(comp_counts["n"].to_numpy())
    hill_table = pl.DataFrame(
        {
            "weighting": ["per-condition", "per-compound"],
            "N0": [cond_hill["N0"], comp_hill["N0"]],
            "N1_exp_shannon": [cond_hill["N1"], comp_hill["N1"]],
            "N2_inv_simpson": [cond_hill["N2"], comp_hill["N2"]],
            "N1_over_N0": [cond_hill["N1"] / cond_hill["N0"], comp_hill["N1"] / comp_hill["N0"]],
            "N2_over_N0": [cond_hill["N2"] / cond_hill["N0"], comp_hill["N2"] / comp_hill["N0"]],
        }
    )
    mo.md("### Hill diversity")
    mo.ui.table(hill_table, page_size=5)
    return


@app.cell(hide_code=True)
def _():
    mo.md(r"""
    ## What this notebook does *not* do

    - **Re-cluster the sGR matrix.** Bond et al. spectral clustering with
      their predictive-cluster filter is the public-data authoritative
      label set; re-running spectral clustering on top would just be a
      validation exercise and would not change the diversity story
      meaningfully. nb03 is the place to look at the underlying
      strain-axis structure of the matrix; nb06 takes their PCL labels
      as ground truth.
    - **Extrapolate to larger compound libraries.** The public data
      covers ~1,000 compounds; whether a 6K, 15K, or 100K library
      already saturates the same shape space is a question only that
      library's data can answer. The right read here is the *shape* of
      the public-data rarefaction curve - if it flattens at 1,000
      compounds, even a saturated PCL coverage doesn't preclude
      finer-grained shape structure that more compounds could reveal;
      if it's still rising at 1,000, that's evidence the curve at 6K
      and 100K is also still rising.
    - **Distinguish "shape diversity" from "MOA diversity."** PCLs are a
      finer partition than annotated MOAs but they are not orthogonal
      to chemistry; some PCLs are dominated by a single chemotype.
      The collapse-vs-denoising question (nb05) is the one to read
      together with this notebook before drawing strong conclusions.
    - **Use any per-strain weighting.** Conditions are uniformly
      weighted within each PCL. A weighting by sGR magnitude or by
      replicate quality could change the effective Hill numbers.
    """)
    return


if __name__ == "__main__":
    app.run()
