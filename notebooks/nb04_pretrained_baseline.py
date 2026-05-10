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
    from rdkit import Chem, RDLogger
    from rdkit.Chem.rdFingerprintGenerator import GetMorganGenerator
    from sklearn.metrics import pairwise_distances

    NOTEBOOK_DIR = Path(__file__).parent
    PROJ_ROOT = NOTEBOOK_DIR.parent
    EXTERNAL_DATA_DIR = PROJ_ROOT / "data" / "external"
    FIGSHARE_DIR = EXTERNAL_DATA_DIR / "figshare_28373561"

    if str(NOTEBOOK_DIR) not in sys.path:
        sys.path.insert(0, str(NOTEBOOK_DIR))

    from nb03_hypomorph_correlation import fetch_sgr_archive, parse_gct  # noqa: E402

    CLUSTERS_FILE_ID = 57955132
    CLUSTERS_ARCHIVE_NAME = "clusters_spectral_clustering_tbl_archive.tar.gz"
    CLUSTERS_ARCHIVE_HASH = "sha256:bfb304ea5680dc8deffa4bb2473ee47fee99166618685d8918ee7ba48d02e0b9"
    CLUSTERS_TXT_NAME = "clusters_spectral_clust_tbl.txt"

    MORGAN_RADIUS = 2
    MORGAN_NBITS = 2048

    RDLogger.DisableLog("rdApp.*")


@app.cell(hide_code=True)
def _():
    mo.md(r"""
    # nb04 - pretrained baseline

    **Diagnostic.** Does a structure-only nearest-neighbor baseline already
    recover MOA on the Bond et al. 2025 reference set, comparably to a
    CGI-profile-based nearest-neighbor baseline?

    **Why it matters.** Any model that predicts CGI profiles (or MOA
    labels) from chemistry should be evaluated against the simplest
    chemistry-only baseline first. If raw structure features already
    classify MOA on the reference set at high accuracy, a more complex
    learned representation has to clear that bar before its added compute
    can be justified. If the structure baseline is materially worse than a
    CGI baseline, that's evidence the CGI signal carries MOA information
    beyond what chemistry alone provides.

    **Method.**

    1. Pull the Bond reference-set spine (`clusters_spectral_clust_tbl`):
       compound -> annotated MOA + canonical SMILES + condition ids.
    2. Pull the per-condition sGR matrix (9,427 conditions x 340 strains).
       Two CGI feature views per compound: a single median-across-doses
       profile and the full set of per-(dose, wave) profiles.
    3. Compute Morgan fingerprints (radius 2, 2,048 bits) per compound.
    4. Leave-one-out 1-NN on Morgan fingerprints (Tanimoto distance) -> the
       structure baseline.
    5. Two CGI baselines, both 1-NN:
       (a) **CGI per-dose**: for each held-out compound, find its single
           closest condition->condition match in any other compound, then
           predict that other compound's primary MOA. This is the closer
           analogue of PCL-style profile matching.
       (b) **CGI median**: kNN on one median-aggregated profile per
           compound. Surfaces the cost of throwing away dose-response.
    6. Compare top-line accuracy and per-MOA precision / sensitivity, and
       quantify the within-MOA structural redundancy of the reference set
       (so the structure baseline's gap can be interpreted).

    **Scope.** Public Bond reference-set data only. The numbers here set
    the bar that any structure-to-MOA model on a larger compound set
    should clear; downstream notebooks can apply the same recipe to other
    datasets.
    """)
    return


@app.cell(hide_code=True)
def _():
    mo.md(r"""
    ## Pull the reference-set spine and the sGR matrix
    """)
    return


@app.function
def fetch_clusters_archive() -> Path:
    """Download and extract the Bond clusters_spectral_clust_tbl archive."""
    archive = Path(
        pooch.retrieve(
            url=f"https://ndownloader.figshare.com/files/{CLUSTERS_FILE_ID}",
            known_hash=CLUSTERS_ARCHIVE_HASH,
            fname=CLUSTERS_ARCHIVE_NAME,
            path=FIGSHARE_DIR,
            progressbar=True,
        )
    )
    extract_dir = FIGSHARE_DIR / "clusters_tbl"
    txt_path = extract_dir / CLUSTERS_TXT_NAME
    if not txt_path.exists():
        extract_dir.mkdir(exist_ok=True)
        with tarfile.open(archive, "r:gz") as t:
            t.extractall(extract_dir, filter="data")
    return txt_path


@app.cell
def _():
    clusters_tbl = pl.read_csv(
        fetch_clusters_archive(),
        separator="\t",
        infer_schema_length=10_000,
    )
    sgr_matrix, sgr_row_meta, sgr_col_meta = parse_gct(fetch_sgr_archive())
    mo.md(
        f"- `clusters_tbl`: shape `{clusters_tbl.shape}` "
        f"({clusters_tbl['broad_id'].n_unique():,} unique compounds, "
        f"{clusters_tbl['moa_class'].n_unique()} MOAs)\n"
        f"- `sgr_matrix`: shape `{sgr_matrix.shape}` "
        f"(strains x conditions)\n"
        f"- `sgr_col_meta`: shape `{sgr_col_meta.shape}` (one row per condition)"
    )
    return clusters_tbl, sgr_col_meta, sgr_matrix


@app.cell(hide_code=True)
def _():
    mo.md(r"""
    ## Build per-compound table

    For each `broad_id`, pick the most-frequent annotated `moa_class` as the
    primary label, keep the full set of annotated MOAs for permissive
    scoring, and join the SMILES (constant per `broad_id`).
    """)
    return


@app.function
def per_compound_labels(clusters_tbl: pl.DataFrame) -> pl.DataFrame:
    """Collapse clusters_tbl to one row per broad_id with primary + full MOA set."""
    base = clusters_tbl.filter(
        pl.col("broad_id").is_not_null() & pl.col("canonical_smiles").is_not_null() & pl.col("moa_class").is_not_null()
    )
    smiles = base.group_by("broad_id").agg(pl.col("canonical_smiles").first().alias("smiles"))
    moa_counts = (
        base.group_by(["broad_id", "moa_class"])
        .len()
        .rename({"len": "n"})
        .sort(["broad_id", "n"], descending=[False, True])
    )
    primary = moa_counts.group_by("broad_id").agg(pl.col("moa_class").first().alias("primary_moa"))
    moa_set = base.group_by("broad_id").agg(pl.col("moa_class").unique().alias("moa_set"))
    return smiles.join(primary, on="broad_id").join(moa_set, on="broad_id")


@app.cell
def _(clusters_tbl):
    compound_labels = per_compound_labels(clusters_tbl)
    n_multi = compound_labels.filter(pl.col("moa_set").list.len() > 1).height
    mo.md(f"`compound_labels`: shape `{compound_labels.shape}` ({n_multi} compounds carry more than one annotated MOA)")
    return (compound_labels,)


@app.cell(hide_code=True)
def _():
    mo.md(r"""
    ## Aggregate sGR to one CGI profile per compound

    Each `broad_id` shows up at multiple doses and across multiple screening
    waves; the sGR matrix has one column (`cid`) per (wave, broad_id, dose).
    The mapping `cid -> broad_id` lives in `clusters_tbl`. Take the median
    sGR vector across all conditions for a given `broad_id` to get a single
    340-vector per compound.
    """)
    return


@app.function
def compound_cgi_profiles(
    clusters_tbl: pl.DataFrame,
    sgr_matrix: np.ndarray,
    sgr_col_meta: pl.DataFrame,
    broad_ids: list[str],
) -> tuple[np.ndarray, list[str]]:
    """Median sGR vector per broad_id across all matching conditions in sgr_matrix."""
    cid_to_broad = (
        clusters_tbl.select("cid", "broad_id").unique(subset="cid").filter(pl.col("broad_id").is_in(broad_ids))
    )
    cid_index = {cid: i for i, cid in enumerate(sgr_col_meta["cid"].to_list())}
    by_compound: dict[str, list[int]] = {}
    for cid, bid in cid_to_broad.iter_rows():
        idx = cid_index.get(cid)
        if idx is not None:
            by_compound.setdefault(bid, []).append(idx)
    kept = [b for b in broad_ids if b in by_compound]
    profiles = np.stack(
        [np.median(sgr_matrix[:, by_compound[b]], axis=1) for b in kept],
        axis=0,
    )
    return profiles, kept


@app.function
def compound_condition_features(
    clusters_tbl: pl.DataFrame,
    sgr_matrix: np.ndarray,
    sgr_col_meta: pl.DataFrame,
    broad_ids: list[str],
) -> tuple[np.ndarray, np.ndarray]:
    """Per-condition sGR vectors for compounds in broad_ids.

    Unlike `compound_cgi_profiles` (one median row per compound), this keeps every
    matching (compound, dose, wave) row as its own feature vector. Returns
    (features (n_conditions, n_strains), compound_ids (n_conditions,)).
    """
    cid_to_broad = (
        clusters_tbl.select("cid", "broad_id").unique(subset="cid").filter(pl.col("broad_id").is_in(broad_ids))
    )
    cid_index = {cid: i for i, cid in enumerate(sgr_col_meta["cid"].to_list())}
    rows: list[tuple[int, str]] = []
    for cid, bid in cid_to_broad.iter_rows():
        idx = cid_index.get(cid)
        if idx is not None:
            rows.append((idx, bid))
    indices = np.array([i for i, _ in rows], dtype=np.int64)
    bids = np.array([b for _, b in rows], dtype=object)
    return sgr_matrix[:, indices].T, bids


@app.function
def loocv_per_condition_predictions(
    features: np.ndarray,
    compound_ids: np.ndarray,
    metric: str,
) -> tuple[np.ndarray, np.ndarray]:
    """For each unique compound, find its single best condition->condition match in any other compound.

    Excludes all of the held-out compound's own conditions (not just the single
    held-out row). Returns (unique_compound_ids, predicted_compound_ids).
    Compounds with no eligible neighbor get a `None` prediction.
    """
    dist = pairwise_distances(features, metric=metric)
    np.fill_diagonal(dist, np.inf)
    unique = np.unique(compound_ids)
    predicted = np.empty(len(unique), dtype=object)
    for i, c in enumerate(unique):
        own = compound_ids == c
        other = ~own
        if not other.any():
            predicted[i] = None
            continue
        sub = dist[own][:, other]
        flat = int(np.argmin(sub))
        _, j = np.unravel_index(flat, sub.shape)
        other_global = int(np.where(other)[0][j])
        predicted[i] = compound_ids[other_global]
    return unique, predicted


@app.function
def same_moa_tanimoto_distribution(fps: np.ndarray, primary_moas: np.ndarray) -> pl.DataFrame:
    """Pairwise Tanimoto over Morgan FPs labeled by same vs different primary MOA."""
    sim = 1.0 - pairwise_distances(fps.astype(bool), metric="jaccard")
    n = len(primary_moas)
    iu = np.triu_indices(n, k=1)
    same = primary_moas[iu[0]] == primary_moas[iu[1]]
    return pl.DataFrame({"tanimoto": sim[iu], "same_moa": same})


@app.cell
def _(clusters_tbl, compound_labels, sgr_col_meta, sgr_matrix):
    profiles, profile_broad_ids = compound_cgi_profiles(
        clusters_tbl,
        sgr_matrix,
        sgr_col_meta,
        compound_labels["broad_id"].to_list(),
    )
    mo.md(
        f"`profiles`: shape `{profiles.shape}` (compounds x strains).  "
        f"{len(compound_labels) - len(profile_broad_ids)} compound(s) had no matching "
        f"sGR column and were dropped."
    )
    return profile_broad_ids, profiles


@app.cell(hide_code=True)
def _():
    mo.md(r"""
    ## Compute Morgan fingerprints

    Radius 2, 2,048-bit folded counts (binarized). Tracks the standard
    chemoinformatics baseline.
    """)
    return


@app.function
def smiles_to_morgan(smiles: list[str], radius: int, nbits: int) -> tuple[np.ndarray, list[bool]]:
    """Morgan fingerprint matrix; returns (fp_matrix, valid_mask)."""
    gen = GetMorganGenerator(radius=radius, fpSize=nbits)
    fps = np.zeros((len(smiles), nbits), dtype=np.uint8)
    valid = [False] * len(smiles)
    for i, smi in enumerate(smiles):
        mol = Chem.MolFromSmiles(smi)
        if mol is None:
            continue
        fps[i] = gen.GetFingerprintAsNumPy(mol)
        valid[i] = True
    return fps, valid


@app.cell
def _(compound_labels, profile_broad_ids):
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
    n_valid = sum(fps_valid)
    mo.md(f"`fps_all`: shape `{fps_all.shape}`  ({n_valid}/{len(fps_valid)} SMILES parsed cleanly)")
    return aligned, fps_all, fps_valid


@app.cell(hide_code=True)
def _():
    mo.md(r"""
    ## Align tables

    Drop compounds that lost their fingerprint (bad SMILES) or their CGI
    profile (no matching sGR column). The structure features, the CGI
    features, and the labels all need to share the same row index for the
    LOO comparison to be apples-to-apples.
    """)
    return


@app.cell
def _(aligned, fps_all, fps_valid, profile_broad_ids, profiles):
    valid_mask = np.array(fps_valid, dtype=bool)
    aligned_kept = aligned.filter(pl.Series("valid", valid_mask))
    fps = fps_all[valid_mask]
    profile_index = {b: i for i, b in enumerate(profile_broad_ids)}
    profile_idx = np.array([profile_index[b] for b in aligned_kept["broad_id"].to_list()])
    cgi = profiles[profile_idx]
    primary_moa = aligned_kept["primary_moa"].to_numpy()
    moa_sets = [set(s) for s in aligned_kept["moa_set"].to_list()]
    n_per_moa = aligned_kept.group_by("primary_moa").len().rename({"len": "n"}).sort("n", descending=True)
    mo.md(
        f"Aligned set: **{len(aligned_kept)} compounds**, "
        f"**{aligned_kept['primary_moa'].n_unique()} primary MOAs**, "
        f"feature shapes: structure `{fps.shape}`, CGI `{cgi.shape}`."
    )
    return aligned_kept, cgi, fps, moa_sets, n_per_moa, primary_moa


@app.cell(hide_code=True)
def _(n_per_moa):
    mo.md("### MOA support")
    mo.ui.table(n_per_moa, page_size=15)
    return


@app.cell(hide_code=True)
def _():
    mo.md(r"""
    ## Filter to MOAs with at least 3 compounds

    LOO 1-NN on a singleton MOA can't possibly succeed; n=2 is so noisy that
    a single coincidence dominates the per-MOA number. Keep MOAs with at
    least 3 compounds for the headline; full table is shown above.
    """)
    return


@app.cell
def _(aligned_kept, cgi, fps, moa_sets, n_per_moa, primary_moa):
    keep_moas = set(n_per_moa.filter(pl.col("n") >= 3)["primary_moa"].to_list())
    keep_mask = np.array([m in keep_moas for m in primary_moa], dtype=bool)
    fps_k = fps[keep_mask]
    cgi_k = cgi[keep_mask]
    primary_moa_k = primary_moa[keep_mask]
    moa_sets_k = [s for s, k in zip(moa_sets, keep_mask, strict=True) if k]
    aligned_k = aligned_kept.filter(pl.Series("k", keep_mask))
    mo.md(f"After dropping MOAs with n<3: **{len(aligned_k)} compounds** across **{len(keep_moas)} MOAs**.")
    return aligned_k, cgi_k, fps_k, moa_sets_k, primary_moa_k


@app.cell(hide_code=True)
def _():
    mo.md(r"""
    ## Leave-one-out 1-NN classification

    For each compound, find the nearest other compound by the chosen
    distance metric and predict its primary MOA. A prediction is *strict*
    correct if the predicted MOA equals the held-out compound's primary MOA;
    *permissive* correct if the predicted MOA is in the held-out compound's
    full MOA set.
    """)
    return


@app.function
def loocv_1nn_predictions(
    features: np.ndarray,
    moas: np.ndarray,
    metric: str,
) -> np.ndarray:
    """1-NN leave-one-out predictions. Returns predicted MOA per compound."""
    dist = pairwise_distances(features, metric=metric)
    np.fill_diagonal(dist, np.inf)
    nn_idx = np.argmin(dist, axis=1)
    return moas[nn_idx]


@app.function
def score_predictions(
    predictions: np.ndarray,
    primary_moas: np.ndarray,
    moa_sets: list[set[str]],
) -> dict[str, float]:
    """Strict and permissive accuracy + macro precision/sensitivity over MOAs."""
    strict = predictions == primary_moas
    permissive = np.array([p in s for p, s in zip(predictions, moa_sets, strict=True)])
    moas_unique = np.unique(primary_moas)
    sens = []
    prec = []
    for m in moas_unique:
        true_mask = primary_moas == m
        pred_mask = predictions == m
        tp = np.sum(true_mask & pred_mask)
        sens.append(tp / max(true_mask.sum(), 1))
        prec.append(tp / max(pred_mask.sum(), 1))
    return {
        "accuracy_strict": float(strict.mean()),
        "accuracy_permissive": float(permissive.mean()),
        "macro_sensitivity": float(np.mean(sens)),
        "macro_precision": float(np.mean(prec)),
    }


@app.cell
def _(
    aligned_k,
    cgi_k,
    clusters_tbl,
    fps_k,
    moa_sets_k,
    primary_moa_k,
    sgr_col_meta,
    sgr_matrix,
):
    aligned_broad_ids = aligned_k["broad_id"].cast(pl.String).to_list()
    compound_to_primary = dict(zip(aligned_broad_ids, aligned_k["primary_moa"].to_list(), strict=True))

    pred_struct = loocv_1nn_predictions(fps_k.astype(bool), primary_moa_k, metric="jaccard")
    pred_cgi_median = loocv_1nn_predictions(cgi_k, primary_moa_k, metric="correlation")

    cond_features, cond_compound_ids = compound_condition_features(
        clusters_tbl, sgr_matrix, sgr_col_meta, aligned_broad_ids
    )
    unique_compounds, predicted_compound = loocv_per_condition_predictions(
        cond_features, cond_compound_ids, metric="correlation"
    )
    pred_by_compound = dict(zip(unique_compounds, predicted_compound, strict=True))
    pred_cgi_perdose = np.array(
        [compound_to_primary.get(pred_by_compound.get(b)) for b in aligned_broad_ids],
        dtype=object,
    )

    score_struct = score_predictions(pred_struct, primary_moa_k, moa_sets_k)
    score_cgi_perdose = score_predictions(pred_cgi_perdose, primary_moa_k, moa_sets_k)
    score_cgi_median = score_predictions(pred_cgi_median, primary_moa_k, moa_sets_k)
    return (
        pred_cgi_perdose,
        pred_struct,
        score_cgi_median,
        score_cgi_perdose,
        score_struct,
    )


@app.cell(hide_code=True)
def _(score_cgi_median, score_cgi_perdose, score_struct):
    metric_keys = ["accuracy_strict", "accuracy_permissive", "macro_sensitivity", "macro_precision"]
    summary = pl.DataFrame(
        {
            "metric": metric_keys,
            "structure": [score_struct[k] for k in metric_keys],
            "cgi_per_dose": [score_cgi_perdose[k] for k in metric_keys],
            "cgi_median": [score_cgi_median[k] for k in metric_keys],
        }
    ).with_columns(
        (pl.col("cgi_per_dose") - pl.col("structure")).alias("delta_perdose_minus_struct"),
        (pl.col("cgi_per_dose") - pl.col("cgi_median")).alias("delta_perdose_minus_median"),
    )
    mo.md("### Headline numbers")
    mo.ui.table(summary, page_size=10)
    return


@app.cell(hide_code=True)
def _():
    mo.md(r"""
    ### Reading the numbers

    - **Strict accuracy** is the harshest test: predicted MOA must equal the
      held-out compound's *primary* MOA exactly. **Permissive accuracy**
      gives the prediction credit if it matches *any* of the compound's
      annotated MOAs (relevant for compounds with two annotated mechanisms).
    - **Macro sensitivity / precision** average per-MOA, treating each MOA
      as equally important regardless of size; this is the right summary
      when MOA imbalance is large (a few big MOAs would otherwise drown
      out the rare ones).
    - **`delta_perdose_minus_struct` is the main comparison.** Both methods
      get one prediction per compound; both are 1-NN; the only difference
      is the feature view (chemistry vs CGI). Small / negative delta means
      chemistry alone is doing most of the work; large positive delta
      means CGI carries MOA information chemistry can't see.
    - **`delta_perdose_minus_median` is the cost of aggregation.** Same CGI
      data, different unit. If this is large and positive, median-aggregating
      across doses is throwing away signal a per-dose matcher recovers --
      a structural argument for working at the (compound, dose) level
      rather than collapsing to compound-level profiles.
    """)
    return


@app.cell(hide_code=True)
def _():
    mo.md(r"""
    ## Per-MOA breakdown

    Where do the two methods agree, and where do they disagree? A scatter
    of per-MOA strict accuracy on structure-only vs CGI-only highlights
    MOAs where chemistry alone already nails it (top-right) and MOAs that
    are CGI-specific (top-left).
    """)
    return


@app.cell
def _(pred_cgi_perdose, pred_struct, primary_moa_k):
    moas_unique = np.unique(primary_moa_k)
    rows = []
    for m in moas_unique:
        mask = primary_moa_k == m
        rows.append(
            (
                m,
                int(mask.sum()),
                float((pred_struct[mask] == m).mean()),
                float((pred_cgi_perdose[mask] == m).mean()),
            )
        )
    per_moa = pl.DataFrame(rows, schema=["moa", "n", "struct_acc", "cgi_acc"], orient="row")
    return (per_moa,)


@app.cell(hide_code=True)
def _(per_moa):
    chart = (
        alt.Chart(per_moa)
        .mark_circle(size=80, opacity=0.7)
        .encode(
            x=alt.X("struct_acc:Q", title="structure strict accuracy", scale=alt.Scale(domain=[-0.05, 1.05])),
            y=alt.Y("cgi_acc:Q", title="CGI per-dose strict accuracy", scale=alt.Scale(domain=[-0.05, 1.05])),
            size=alt.Size("n:Q", title="n compounds"),
            tooltip=["moa", "n", "struct_acc", "cgi_acc"],
        )
        .properties(width=520, height=520)
    )
    diag = (
        alt.Chart(pl.DataFrame({"x": [0, 1], "y": [0, 1]}))
        .mark_line(strokeDash=[4, 4], color="gray")
        .encode(x="x:Q", y="y:Q")
    )
    mo.ui.altair_chart(diag + chart)
    return


@app.cell(hide_code=True)
def _(per_moa):
    mo.md("### Per-MOA table")
    mo.ui.table(per_moa.sort("n", descending=True), page_size=20)
    return


@app.cell(hide_code=True)
def _():
    mo.md(r"""
    ## Agreement quadrants

    Of the held-out compounds, how do structure and CGI per-dose partition?
    Both right, both wrong, only structure right, only CGI per-dose right.
    """)
    return


@app.cell(hide_code=True)
def _(pred_cgi_perdose, pred_struct, primary_moa_k):
    s = pred_struct == primary_moa_k
    c = pred_cgi_perdose == primary_moa_k
    quad = pl.DataFrame(
        {
            "quadrant": [
                "both correct",
                "only structure correct",
                "only CGI per-dose correct",
                "both wrong",
            ],
            "n": [
                int(np.sum(s & c)),
                int(np.sum(s & ~c)),
                int(np.sum(~s & c)),
                int(np.sum(~s & ~c)),
            ],
        }
    ).with_columns((pl.col("n") / pl.col("n").sum()).alias("frac"))
    mo.ui.table(quad, page_size=10)
    return


@app.cell(hide_code=True)
def _():
    mo.md(r"""
    ## Structural redundancy in the reference set

    The Bond reference set is curated to span MOAs with *known* chemistry,
    so within an MOA there are often multiple structurally similar
    compounds (tetracyclines under "30S ribosome", fluoroquinolones under
    "DNA gyrase", etc). That redundancy biases a structure-only NN
    classifier upward: a held-out compound's nearest structural neighbor
    is often a near-twin from the same MOA. Quantify it directly: pairwise
    Tanimoto over Morgan FPs, split by whether the pair shares a primary
    MOA. If same-MOA Tanimoto is much higher than across-MOA Tanimoto, the
    structure baseline benefits from class-internal redundancy and won't
    generalize to compound libraries lacking that structure.
    """)
    return


@app.cell
def _(fps_k, primary_moa_k):
    moa_sim_df = same_moa_tanimoto_distribution(fps_k, primary_moa_k)
    _summary = moa_sim_df.group_by("same_moa").agg(
        pl.col("tanimoto").mean().alias("mean"),
        pl.col("tanimoto").median().alias("median"),
        pl.col("tanimoto").std().alias("std"),
        pl.col("tanimoto").quantile(0.95).alias("p95"),
        pl.len().alias("n_pairs"),
    )
    mo.md("### Pairwise Tanimoto, same-MOA vs different-MOA")
    mo.ui.table(_summary, page_size=5)
    return (moa_sim_df,)


@app.cell(hide_code=True)
def _(moa_sim_df):
    _chart = (
        alt.Chart(moa_sim_df)
        .transform_density(
            "tanimoto",
            groupby=["same_moa"],
            as_=["tanimoto", "density"],
            extent=[0.0, 1.0],
            steps=80,
        )
        .mark_area(opacity=0.45)
        .encode(
            x=alt.X("tanimoto:Q", title="pairwise Morgan-FP Tanimoto"),
            y=alt.Y("density:Q", stack=None, title="density"),
            color=alt.Color("same_moa:N", title="same primary MOA?"),
        )
        .properties(width=520, height=300)
    )
    mo.ui.altair_chart(_chart)
    return


@app.cell(hide_code=True)
def _():
    mo.md(r"""
    ## What this notebook does *not* do

    - Reproduce the full PCL pipeline. The CGI baseline here is a 1-NN
      stand-in, not a cluster-based PCL similarity score. Bond et al.
      report ~70% sensitivity / ~75% precision on PCL-based MOA inference
      under a more involved scoring scheme; this notebook's CGI number is
      a simpler comparison anchor matched to its structure-only
      counterpart, so the *delta* between the two is the meaningful
      output, not the absolute level.
    - Test alternative chemistry representations. Morgan fingerprints are
      the simplest non-trivial baseline; richer learned representations
      (graph neural nets, contrastively pre-trained chemistry encoders)
      could be plugged into the same pipeline by swapping the feature
      block.
    - Test chemistry-similarity-thresholded variants. A natural follow-up:
      restrict structure-only NN matches to neighbors with Tanimoto > 0.5
      and ask "of compounds with a chemically similar neighbor, how often
      does that neighbor share MOA?" - which is closer to what a virtual
      screen actually relies on.
    """)
    return


if __name__ == "__main__":
    app.run()
