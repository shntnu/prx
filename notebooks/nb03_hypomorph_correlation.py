# /// script
# requires-python = ">=3.12,<3.14"
# dependencies = [
#     "marimo",
#     "altair==5.5.0",
#     "numpy==2.2.0",
#     "polars==1.40.1",
#     "pooch==1.9.0",
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

    SGR_FILE_ID = 57954952
    SGR_ARCHIVE_NAME = "sGR_for_pcls_archive.tar.gz"
    SGR_ARCHIVE_HASH = "sha256:a86dbfd05f48c57ecbf0ea30dae2bd20843d9eddd42a4efe6254f239964a1c2c"
    SGR_GCT_NAME = "sGR_for_pcls_n9427x340.gct"


@app.cell(hide_code=True)
def _():
    mo.md(r"""
    # nb03 - hypomorph correlation

    Which hypomorphs respond *similarly* across the 437-compound reference set?
    Strain pairs with high Pearson correlation across the sGR matrix are
    candidates for shared pathway membership, complex co-membership, or shared
    sensitivity to a class of perturbations.

    Pulls the `sGR_for_pcls` matrix (9,427 conditions x 340 strains) from the
    Bond et al. 2025 Figshare bundle, computes the 340 x 340 strain-strain
    Pearson correlation, and surfaces top neighbors for any chosen strain.

    The matrix is the same one Bond et al. used to construct PCL clusters - so
    the correlations here are the raw substrate behind their MOA inference,
    just looked at from the *strain* axis instead of the *condition* axis.
    """)
    return


@app.cell(hide_code=True)
def _():
    mo.md(r"""
    ## Pull sGR matrix
    """)
    return


@app.function
def fetch_sgr_archive() -> Path:
    """Download the sGR_for_pcls archive (309 MB) and extract on first run."""
    archive = Path(
        pooch.retrieve(
            url=f"https://ndownloader.figshare.com/files/{SGR_FILE_ID}",
            known_hash=SGR_ARCHIVE_HASH,
            fname=SGR_ARCHIVE_NAME,
            path=FIGSHARE_DIR,
            progressbar=True,
        )
    )
    extract_dir = FIGSHARE_DIR / "sGR_for_pcls"
    gct_path = extract_dir / SGR_GCT_NAME
    if not gct_path.exists():
        extract_dir.mkdir(exist_ok=True)
        with tarfile.open(archive, "r:gz") as t:
            t.extractall(extract_dir, filter="data")
    return gct_path


@app.function
def parse_gct(path: Path) -> tuple[np.ndarray, pl.DataFrame, pl.DataFrame]:
    """Parse a GCT v1.3 file into (matrix, row_meta, col_meta).

    matrix: float32 ndarray, shape (n_rows, n_cols)
    row_meta: polars DataFrame, n_rows rows, includes 'rid' as first column
    col_meta: polars DataFrame, n_cols rows, includes 'cid' as first column
    """
    with path.open() as f:
        version = f.readline().rstrip()
        if not version.startswith("#1.3"):
            raise ValueError(f"Expected GCT v1.3, got: {version!r}")
        nrow, ncol, nrhd, nchd = (int(x) for x in f.readline().split())
        header = f.readline().rstrip("\n").split("\t")
        row_meta_names = header[1 : 1 + nrhd]
        cids = header[1 + nrhd :]
        if len(cids) != ncol:
            raise ValueError(f"Expected {ncol} cids in header, got {len(cids)}")

        col_meta_rows: dict[str, list[str]] = {}
        for _ in range(nchd):
            parts = f.readline().rstrip("\n").split("\t")
            col_meta_rows[parts[0]] = parts[1 + nrhd :]

        rids: list[str] = []
        row_meta_cols: dict[str, list[str]] = {n: [] for n in row_meta_names}
        matrix = np.empty((nrow, ncol), dtype=np.float32)
        for i in range(nrow):
            parts = f.readline().rstrip("\n").split("\t")
            rids.append(parts[0])
            for j, name in enumerate(row_meta_names):
                row_meta_cols[name].append(parts[1 + j])
            matrix[i] = np.fromstring("\t".join(parts[1 + nrhd :]), sep="\t", dtype=np.float32)

    row_meta = pl.DataFrame({"rid": rids, **row_meta_cols})
    col_meta = pl.DataFrame({"cid": cids, **col_meta_rows})
    return matrix, row_meta, col_meta


@app.cell
def _():
    gct_path = fetch_sgr_archive()
    matrix, row_meta, col_meta = parse_gct(gct_path)
    mo.md(
        f"matrix shape: `{matrix.shape}`  "
        f"row_meta cols: `{row_meta.columns[:5]}...`  "
        f"col_meta cols: `{col_meta.columns[:5]}...`"
    )
    return matrix, row_meta


@app.cell(hide_code=True)
def _():
    mo.md(r"""
    ## Compute strain x strain correlation

    340 x 340 Pearson across 9,427 conditions. Trivially small after the
    download.
    """)
    return


@app.function
def strain_correlation(matrix: np.ndarray) -> np.ndarray:
    """Pearson correlation between rows of an (n_strains, n_conditions) matrix."""
    centered = matrix - matrix.mean(axis=1, keepdims=True)
    norms = np.linalg.norm(centered, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return (centered @ centered.T) / (norms @ norms.T)


@app.cell
def _(matrix):
    corr = strain_correlation(matrix)
    mo.md(f"correlation matrix shape: `{corr.shape}`  dtype: `{corr.dtype}`")
    return (corr,)


@app.cell(hide_code=True)
def _():
    mo.md(r"""
    ## Pick a strain, see its neighbors

    Strain labels combine the gene name and the strain identifier. Hypomorphs
    live in `strain_category == "hypomorph"`; WT controls and other categories
    are kept so you can sanity-check that they don't dominate the neighborhoods.
    """)
    return


@app.cell(hide_code=True)
def _(row_meta):
    label_df = row_meta.select(
        pl.col("rid"),
        pl.col("strain_gene"),
        pl.col("strain_category"),
        pl.when(pl.col("strain_gene") == pl.col("rid"))
        .then(pl.col("strain_gene"))
        .otherwise(pl.col("strain_gene") + " (" + pl.col("rid") + ")")
        .alias("label"),
    )
    label_to_idx = {lab: i for i, lab in enumerate(label_df["label"].to_list())}
    options = sorted(label_to_idx.keys())
    return label_df, label_to_idx, options


@app.cell
def _(options):
    strain_picker = mo.ui.dropdown(
        options=options,
        value="rpoB" if "rpoB" in options else options[0],
        label="Strain",
        searchable=True,
    )
    top_k = mo.ui.slider(start=5, stop=50, step=5, value=15, label="Top K neighbors")
    mo.sidebar([mo.md("### Controls"), strain_picker, top_k])
    return strain_picker, top_k


@app.cell
def _(corr, label_df, label_to_idx, strain_picker, top_k):
    selected_idx = label_to_idx[strain_picker.value]
    correlations = corr[selected_idx]
    neighbors = (
        label_df.with_columns(pl.Series("pearson_r", correlations))
        .filter(pl.col("rid") != label_df["rid"][selected_idx])
        .sort("pearson_r", descending=True)
        .head(top_k.value)
        .select("label", "strain_gene", "strain_category", "pearson_r")
    )
    mo.md(f"### Top {top_k.value} neighbors of **{strain_picker.value}**")
    return (neighbors,)


@app.cell(hide_code=True)
def _(neighbors):
    mo.ui.table(neighbors, page_size=20)
    return


@app.cell(hide_code=True)
def _():
    mo.md(r"""
    ### Bar chart - correlation strength across the neighborhood
    """)
    return


@app.cell(hide_code=True)
def _(neighbors):
    chart = (
        alt.Chart(neighbors)
        .mark_bar()
        .encode(
            x=alt.X("pearson_r:Q", title="Pearson r"),
            y=alt.Y("label:N", sort="-x", title=None),
            color=alt.Color("strain_category:N"),
            tooltip=["label", "strain_gene", "strain_category", "pearson_r"],
        )
        .properties(height=alt.Step(18))
    )
    mo.ui.altair_chart(chart)
    return


@app.cell(hide_code=True)
def _():
    mo.md(r"""
    ## Global view - distribution of pairwise correlations

    Sanity check: most random strain pairs should be near zero. Heavy upper
    tail = real co-regulated structure (or shared dose-response shape).
    """)
    return


@app.cell(hide_code=True)
def _(corr):
    iu = np.triu_indices(corr.shape[0], k=1)
    pairwise = corr[iu]
    hist_df = pl.DataFrame({"pearson_r": pairwise})
    hist = (
        alt.Chart(hist_df)
        .mark_bar()
        .encode(
            x=alt.X("pearson_r:Q", bin=alt.Bin(maxbins=80), title="Pearson r"),
            y=alt.Y("count():Q", title="strain pairs"),
        )
        .properties(width=520, height=200)
    )
    mo.ui.altair_chart(hist)
    return


@app.cell(hide_code=True)
def _():
    mo.md(r"""
    ## What this gives downstream notebooks

    `strain_correlation(matrix)` and `parse_gct(path)` are both top-level
    helpers; later notebooks (e.g., a clustering pass over hypomorphs, or a
    target-pathway enrichment over the neighborhoods) can import them and
    skip the GCT parsing boilerplate.
    """)
    return


if __name__ == "__main__":
    app.run()
