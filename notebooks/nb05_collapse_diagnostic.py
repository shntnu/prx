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
    from pathlib import Path

    import altair as alt
    import marimo as mo
    import numpy as np
    import polars as pl
    from sklearn.metrics import pairwise_distances

    NOTEBOOK_DIR = Path(__file__).parent

    if str(NOTEBOOK_DIR) not in sys.path:
        sys.path.insert(0, str(NOTEBOOK_DIR))

    from nb03_hypomorph_correlation import fetch_sgr_archive, parse_gct  # noqa: E402
    from nb04_pretrained_baseline import (  # noqa: E402
        MORGAN_NBITS,
        MORGAN_RADIUS,
        compound_cgi_profiles,
        fetch_clusters_archive,
        per_compound_labels,
        smiles_to_morgan,
    )

    TANIMOTO_DISTANT_CUTOFF = 0.30
    TANIMOTO_BIN_EDGES = (0.0, 0.20, 0.40, 0.60, 1.0001)
    TANIMOTO_BIN_LABELS = ("0.00-0.20", "0.20-0.40", "0.40-0.60", "0.60-1.00")


@app.cell(hide_code=True)
def _():
    mo.md(r"""
    # nb05 - collapse diagnostic

    **Diagnostic.** If you took chemistry away, would the CGI signal still
    partition by MOA? For every pair of compounds in the Bond reference set,
    measure pairwise Tanimoto over Morgan fingerprints and pairwise Pearson
    over median CGI profiles, then compare same-MOA pairs to cross-MOA pairs
    along the Tanimoto axis.

    **Why it matters.** A chemistry-only model that predicts CGI shapes can
    only succeed where CGI shape is itself predictable from chemistry. The
    interesting regime is **same-MOA, chemistry-distant pairs**: if those
    pairs still show high CGI similarity, the reference-set CGI signal
    carries MOA information beyond chemistry, and a chemistry->CGI model
    has a real target. If they don't, the model's training signal is
    largely "compounds with similar structures have similar profiles" -
    a tautology that won't extrapolate to chemistry the model has never
    seen.

    Companion to nb04. nb04 asks whether structure alone classifies MOA;
    nb05 asks whether CGI carries MOA information that survives
    chemistry-stripping.

    **Method.**

    1. Reuse the nb04 aligned set (Bond reference compounds with valid
       SMILES, a matched sGR column, and a primary MOA with at least 3
       compounds in the set).
    2. Pairwise Tanimoto similarity over Morgan fingerprints (radius 2,
       2,048 bits).
    3. Pairwise Pearson over median CGI profiles (one 340-vector per
       compound).
    4. Build a long-format pair table; stratify by Tanimoto bucket x
       same/cross primary MOA; report mean / median / IQR of CGI Pearson
       per stratum.
    5. Headline: among Tanimoto-distant pairs (Tanimoto < 0.30), is the
       same-MOA CGI Pearson distribution materially higher than the
       cross-MOA distribution at the same chemistry distance?
    6. Per-MOA breakdown: which MOAs survive chemistry-stripping (same-MOA,
       Tanimoto-distant pairs still coherent in CGI) and which collapse
       to chemistry-only?

    **Scope.** Public Bond reference-set data only. Same compounds and
    same per-compound CGI feature view as nb04.
    """)
    return


@app.cell(hide_code=True)
def _():
    mo.md(r"""
    ## Pull data and rebuild the nb04 aligned set
    """)
    return


@app.cell
def _():
    clusters_tbl = pl.read_csv(
        fetch_clusters_archive(),
        separator="\t",
        infer_schema_length=10_000,
    )
    sgr_matrix, sgr_row_meta, sgr_col_meta = parse_gct(fetch_sgr_archive())
    mo.md(
        f"- `clusters_tbl`: shape `{clusters_tbl.shape}`\n"
        f"- `sgr_matrix`: shape `{sgr_matrix.shape}` (strains x conditions)"
    )
    return clusters_tbl, sgr_col_meta, sgr_matrix


@app.cell
def _(clusters_tbl, sgr_col_meta, sgr_matrix):
    compound_labels = per_compound_labels(clusters_tbl)
    profiles, profile_broad_ids = compound_cgi_profiles(
        clusters_tbl,
        sgr_matrix,
        sgr_col_meta,
        compound_labels["broad_id"].to_list(),
    )
    aligned = (
        compound_labels.filter(pl.col("broad_id").is_in(profile_broad_ids))
        .with_columns(pl.col("broad_id").cast(pl.Categorical))
        .sort("broad_id")
    )
    fps_all, fps_valid = smiles_to_morgan(
        aligned["smiles"].to_list(),
        radius=MORGAN_RADIUS,
        nbits=MORGAN_NBITS,
    )
    valid_mask = np.array(fps_valid, dtype=bool)
    aligned_kept = aligned.filter(pl.Series("valid", valid_mask))
    fps = fps_all[valid_mask]
    profile_index = {b: i for i, b in enumerate(profile_broad_ids)}
    profile_idx = np.array([profile_index[b] for b in aligned_kept["broad_id"].to_list()])
    cgi = profiles[profile_idx]
    primary_moa = aligned_kept["primary_moa"].to_numpy()
    n_per_moa = aligned_kept.group_by("primary_moa").len().rename({"len": "n"}).sort("n", descending=True)
    keep_moas = set(n_per_moa.filter(pl.col("n") >= 3)["primary_moa"].to_list())
    keep_mask = np.array([m in keep_moas for m in primary_moa], dtype=bool)
    fps_k = fps[keep_mask]
    cgi_k = cgi[keep_mask]
    primary_moa_k = primary_moa[keep_mask]
    aligned_k = aligned_kept.filter(pl.Series("k", keep_mask))
    mo.md(
        f"Aligned set (MOAs with n>=3): **{len(aligned_k)} compounds**, "
        f"**{len(keep_moas)} MOAs**, "
        f"feature shapes: structure `{fps_k.shape}`, CGI `{cgi_k.shape}`."
    )
    return aligned_k, cgi_k, fps_k, primary_moa_k


@app.cell(hide_code=True)
def _():
    mo.md(r"""
    ## Pairwise similarity matrices

    Tanimoto over binarized Morgan FPs (Jaccard distance -> similarity);
    Pearson over median CGI profiles (correlation distance -> similarity).
    Both are upper-triangle-flattened into a long pair table next.
    """)
    return


@app.function
def pairwise_tanimoto(fps: np.ndarray) -> np.ndarray:
    """Pairwise Tanimoto similarity over binarized Morgan fingerprints."""
    return 1.0 - pairwise_distances(fps.astype(bool), metric="jaccard")


@app.function
def pairwise_pearson(profiles: np.ndarray) -> np.ndarray:
    """Pairwise Pearson similarity over compound CGI profiles."""
    return 1.0 - pairwise_distances(profiles, metric="correlation")


@app.function
def pair_table(
    broad_ids: list[str],
    primary_moas: np.ndarray,
    tanimoto_sim: np.ndarray,
    cgi_corr: np.ndarray,
) -> pl.DataFrame:
    """Upper-triangle long-format pair table over compounds.

    One row per unordered pair (i < j), with same-MOA flag, Tanimoto, and
    CGI Pearson. Tanimoto is bucketed using the module-level cutoffs.
    """
    n = len(broad_ids)
    iu = np.triu_indices(n, k=1)
    broad_arr = np.array(broad_ids, dtype=object)
    bin_edges = np.array(TANIMOTO_BIN_EDGES)
    bin_idx = np.clip(np.digitize(tanimoto_sim[iu], bin_edges, right=False) - 1, 0, len(TANIMOTO_BIN_LABELS) - 1)
    bin_labels = np.array(TANIMOTO_BIN_LABELS, dtype=object)[bin_idx]
    return pl.DataFrame(
        {
            "broad_a": broad_arr[iu[0]],
            "broad_b": broad_arr[iu[1]],
            "moa_a": primary_moas[iu[0]],
            "moa_b": primary_moas[iu[1]],
            "same_moa": primary_moas[iu[0]] == primary_moas[iu[1]],
            "tanimoto": tanimoto_sim[iu],
            "tanimoto_bin": bin_labels,
            "cgi_pearson": cgi_corr[iu],
        }
    )


@app.cell
def _(aligned_k, cgi_k, fps_k, primary_moa_k):
    tanimoto_sim = pairwise_tanimoto(fps_k)
    cgi_corr = pairwise_pearson(cgi_k)
    pairs = pair_table(
        aligned_k["broad_id"].cast(pl.String).to_list(),
        primary_moa_k,
        tanimoto_sim,
        cgi_corr,
    )
    n_same = pairs.filter(pl.col("same_moa")).height
    n_cross = pairs.filter(~pl.col("same_moa")).height
    mo.md(f"`pairs`: {pairs.height:,} unordered compound pairs ({n_same:,} same-MOA, {n_cross:,} cross-MOA)")
    return (pairs,)


@app.cell(hide_code=True)
def _():
    mo.md(r"""
    ## Headline: same-MOA vs cross-MOA CGI Pearson, stratified by Tanimoto

    The leftmost Tanimoto bin (0.00-0.20) is the chemistry-distant regime;
    the comparison there is the diagnostic. The rightmost bin contains
    same-MOA structural near-twins (tetracyclines, fluoroquinolones, ...)
    where high CGI similarity is uninformative -- both chemistry and CGI
    can collapse those pairs.
    """)
    return


@app.cell
def _(pairs):
    _bin_order = list(TANIMOTO_BIN_LABELS)
    stratum = (
        pairs.group_by(["tanimoto_bin", "same_moa"])
        .agg(
            pl.col("cgi_pearson").mean().alias("mean"),
            pl.col("cgi_pearson").median().alias("median"),
            pl.col("cgi_pearson").quantile(0.25).alias("q25"),
            pl.col("cgi_pearson").quantile(0.75).alias("q75"),
            pl.len().alias("n_pairs"),
        )
        .with_columns(pl.col("tanimoto_bin").cast(pl.Enum(_bin_order)))
        .sort(["tanimoto_bin", "same_moa"])
    )
    mo.md("### CGI Pearson by Tanimoto bin x same-MOA")
    mo.ui.table(stratum, page_size=12)
    return (stratum,)


@app.cell(hide_code=True)
def _(stratum):
    _bin_order = list(TANIMOTO_BIN_LABELS)
    delta = (
        stratum.select(["tanimoto_bin", "same_moa", "mean", "median", "n_pairs"])
        .pivot(on="same_moa", index="tanimoto_bin", values=["mean", "median", "n_pairs"])
        .with_columns(pl.col("tanimoto_bin").cast(pl.Enum(_bin_order)))
        .sort("tanimoto_bin")
    )
    mean_cols = [c for c in delta.columns if c.startswith("mean_")]
    if len(mean_cols) == 2:
        same_mean = next(c for c in mean_cols if c.endswith("true"))
        cross_mean = next(c for c in mean_cols if c.endswith("false"))
        median_cols = [c for c in delta.columns if c.startswith("median_")]
        same_median = next(c for c in median_cols if c.endswith("true"))
        cross_median = next(c for c in median_cols if c.endswith("false"))
        delta = delta.with_columns(
            (pl.col(same_mean) - pl.col(cross_mean)).alias("delta_mean"),
            (pl.col(same_median) - pl.col(cross_median)).alias("delta_median"),
        )
    mo.md("### Same minus cross at matched Tanimoto")
    mo.ui.table(delta, page_size=12)
    return


@app.cell(hide_code=True)
def _():
    mo.md(r"""
    ### Reading the headline

    - **`mean_true - mean_false` in the leftmost Tanimoto bin is the diagnostic.**
      Sizable positive number: same-MOA pairs are *more* CGI-similar than
      random cross-MOA pairs even when their chemistry has nothing in common.
      That's the regime a chemistry->CGI model would have to learn from
      something other than memorized scaffolds.
    - **A delta near zero** in the leftmost bin means same-MOA CGI similarity
      collapses to background once chemistry is stripped. Whatever shared
      MOA signal the dataset carries lives in chemistry; a chemistry-only
      model can reproduce its training set but its predictions on
      structurally novel chemistry are speculative.
    - **The rightmost bin is mostly a sanity check.** Same-MOA pairs there
      are class scaffolds (e.g. multiple tetracyclines); high CGI Pearson
      is expected and uninformative.
    """)
    return


@app.cell(hide_code=True)
def _():
    mo.md(r"""
    ## Pairwise scatter

    Each point is one unordered compound pair. Two clouds: same-MOA (blue)
    vs cross-MOA (gray). The cross-MOA cloud is the chemistry-only
    expectation; the relevant signal is how much the same-MOA cloud sits
    above it at low Tanimoto.
    """)
    return


@app.cell
def _(pairs):
    sample_n = min(8000, pairs.height)
    sampled = pairs.sample(n=sample_n, seed=0)
    scatter = (
        alt.Chart(sampled)
        .mark_circle(size=18, opacity=0.35)
        .encode(
            x=alt.X("tanimoto:Q", title="pairwise Tanimoto", scale=alt.Scale(domain=[0, 1])),
            y=alt.Y("cgi_pearson:Q", title="pairwise CGI Pearson", scale=alt.Scale(domain=[-1, 1])),
            color=alt.Color("same_moa:N", title="same primary MOA?"),
            tooltip=["broad_a", "broad_b", "moa_a", "moa_b", "tanimoto", "cgi_pearson"],
        )
        .properties(width=560, height=400)
    )
    mo.ui.altair_chart(scatter)
    return


@app.cell(hide_code=True)
def _():
    mo.md(r"""
    ## CGI Pearson density at low Tanimoto

    Restrict to chemistry-distant pairs (Tanimoto < 0.30) and overlay the
    same-MOA vs cross-MOA CGI Pearson densities. Visually: how separated
    are the two distributions where chemistry is uninformative?
    """)
    return


@app.cell
def _(pairs):
    distant = pairs.filter(pl.col("tanimoto") < TANIMOTO_DISTANT_CUTOFF)
    distant_summary = distant.group_by("same_moa").agg(
        pl.col("cgi_pearson").mean().alias("mean"),
        pl.col("cgi_pearson").median().alias("median"),
        pl.col("cgi_pearson").quantile(0.95).alias("p95"),
        pl.len().alias("n_pairs"),
    )
    mo.md(f"### Tanimoto < {TANIMOTO_DISTANT_CUTOFF}: {distant.height:,} pairs")
    mo.ui.table(distant_summary, page_size=5)
    return (distant,)


@app.cell(hide_code=True)
def _(distant):
    # Project to just the columns the density transform needs; otherwise the
    # full ~100k-row pair frame (broad_a, broad_b, moa_a, moa_b strings + ...)
    # gets embedded into the vega-lite spec and blows past molab's
    # output_max_bytes ceiling.
    _density_data = distant.select(["cgi_pearson", "same_moa"])
    _density = (
        alt.Chart(_density_data)
        .transform_density(
            "cgi_pearson",
            groupby=["same_moa"],
            as_=["cgi_pearson", "density"],
            extent=[-1.0, 1.0],
            steps=80,
        )
        .mark_area(opacity=0.45)
        .encode(
            x=alt.X("cgi_pearson:Q", title="CGI Pearson (chemistry-distant pairs)"),
            y=alt.Y("density:Q", stack=None, title="density"),
            color=alt.Color("same_moa:N", title="same primary MOA?"),
        )
        .properties(width=560, height=300)
    )
    mo.ui.altair_chart(_density)
    return


@app.cell(hide_code=True)
def _():
    mo.md(r"""
    ## Per-MOA breakdown

    For each MOA with at least 3 same-MOA pairs at Tanimoto < 0.30, report
    the mean CGI Pearson across those chemistry-distant within-MOA pairs.
    MOAs that stay coherent under chemistry-stripping (high mean CGI
    Pearson with low same-MOA Tanimoto) are the ones a chemistry-blind
    profile-matching approach would actually buy you signal on; MOAs
    where the within-MOA pairs are *all* structural near-twins (very few
    rows here, because the Tanimoto<0.30 filter throws them out) are the
    ones where a chemistry-only model is in trouble for a different
    reason -- it can't see anything beyond the obvious twins.
    """)
    return


@app.cell
def _(pairs):
    distant_same = pairs.filter(pl.col("same_moa") & (pl.col("tanimoto") < TANIMOTO_DISTANT_CUTOFF))
    per_moa_distant = (
        distant_same.with_columns(pl.col("moa_a").alias("moa"))
        .group_by("moa")
        .agg(
            pl.col("cgi_pearson").mean().alias("mean_cgi_pearson"),
            pl.col("cgi_pearson").median().alias("median_cgi_pearson"),
            pl.col("tanimoto").mean().alias("mean_tanimoto"),
            pl.len().alias("n_pairs"),
        )
        .filter(pl.col("n_pairs") >= 3)
        .sort("mean_cgi_pearson", descending=True)
    )
    mo.md("### Same-MOA, chemistry-distant pairs per MOA")
    mo.ui.table(per_moa_distant, page_size=20)
    return (per_moa_distant,)


@app.cell(hide_code=True)
def _(per_moa_distant):
    _bars = (
        alt.Chart(per_moa_distant)
        .mark_bar()
        .encode(
            x=alt.X("mean_cgi_pearson:Q", title="mean CGI Pearson, chemistry-distant within-MOA pairs"),
            y=alt.Y("moa:N", sort="-x", title=None),
            color=alt.Color("n_pairs:Q", title="n pairs", scale=alt.Scale(scheme="blues")),
            tooltip=["moa", "n_pairs", "mean_cgi_pearson", "median_cgi_pearson", "mean_tanimoto"],
        )
        .properties(width=520, height=24 * max(per_moa_distant.height, 1))
    )
    mo.ui.altair_chart(_bars)
    return


@app.cell(hide_code=True)
def _():
    mo.md(r"""
    ## What this notebook does *not* do

    - **Test alternative CGI feature views.** This uses median-aggregated
      profiles per compound for the simplest comparison; per-(dose, wave)
      best-match (the second CGI baseline in nb04) would change absolute
      numbers and could be plugged in by swapping `cgi_k` for the
      condition-level features.
    - **Test alternative chemistry representations.** Morgan FPs at
      radius 2 / 2,048 bits is the standard baseline. A learned embedding
      could re-rank pairs as "chemistry-distant" differently; that would
      change the size of each Tanimoto bin but not the structure of the
      diagnostic.
    - **Use Bond et al. PCL-cluster labels** rather than primary annotated
      MOAs. PCL membership is a finer partition than primary MOA, so
      same-PCL chemistry-distant pairs are arguably the more apples-to-
      apples test of "did the model learn MOA-distinguishing CGI shape?"
      Worth a follow-up that swaps `primary_moa` for `pcl_id`.
    - **Resolve causality.** A high same-MOA / low-Tanimoto CGI Pearson is
      consistent with "CGI shape encodes MOA in a chemistry-independent
      way" but also with "the curated reference set was selected for
      compounds that have the canonical MOA-defining CGI shape". Both
      readings raise the bar for a chemistry-only model in different
      ways.
    """)
    return


if __name__ == "__main__":
    app.run()
