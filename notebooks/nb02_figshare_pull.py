# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "marimo",
#     "polars==1.40.1",
#     "pooch==1.9.0",
#     "tqdm==4.67.3",
# ]
# ///

import marimo

__generated_with = "0.23.5"
app = marimo.App(width="medium")

with app.setup:
    from pathlib import Path

    import marimo as mo
    import polars as pl
    import pooch

    NOTEBOOK_DIR = Path(__file__).parent
    PROJ_ROOT = NOTEBOOK_DIR.parent
    EXTERNAL_DATA_DIR = PROJ_ROOT / "data" / "external"
    FIGSHARE_DIR = EXTERNAL_DATA_DIR / "figshare_28373561"


@app.cell(hide_code=True)
def _():
    mo.md(r"""
    # nb02 - figshare pull

    Pull the Bond et al. 2025 Figshare bundle (the "TB PROSPECT" archive at
    <https://doi.org/10.6084/m9.figshare.28373561>) and peek at table shapes.

    The bundle is huge (~7 GB across 26 archives), so this notebook starts
    with just the small files that give us the spine: the README, MOA
    annotations, the PCL definitions, and the spectral-clustering outputs.
    The big similarity matrices (`pearson_corr_for_pcls`, `pcl_cluster_similarity_scores`,
    ...) are deferred to a later notebook where we actually need them.

    Files land in `data/external/figshare_28373561/` and pooch caches by
    SHA-256. After the first run, paste the printed hashes into the
    `KNOWN_HASHES` registry below to pin them.
    """)
    return


@app.cell(hide_code=True)
def _():
    mo.md(r"""
    ## File registry
    """)
    return


@app.function
def figshare_url(file_id: int) -> str:
    """Return the Figshare ndownloader URL for a given file id."""
    return f"https://ndownloader.figshare.com/files/{file_id}"


@app.cell
def _():
    SMALL_FILES = {
        "readme": (57954730, "Data files-README.md", 13_464),
        "moas": (57955021, "moas_archive.tar.gz", 77_236),
        "moas_k_values": (57955024, "moas_spectral_clustering_k_values_archive.tar.gz", 3_226),
        "clusters": (57955120, "clusters_spectral_clustering_archive.tar.gz", 89_331),
        "clusters_tbl": (57955132, "clusters_spectral_clustering_tbl_archive.tar.gz", 741_029),
        "pcls": (57955897, "pcls_archive.tar.gz", 64_612),
        "pcl_high_conf_thresholds": (
            57955993,
            "by_pcl_high_confidence_similarity_score_thresholds_from_training_on_reference_set_archive.tar.gz",
            39_368,
        ),
        "replicate_correlation": (57954937, "replicate_correlation_archive.tar.gz", 179_906),
        "fraction_gr": (57954940, "fraction_gr_archive.tar.gz", 114_637),
        "max_dose_min_gr": (57954946, "max_dose_min_gr_archive.tar.gz", 62_985),
        "any_dose_min_gr": (57954949, "any_dose_min_gr_archive.tar.gz", 308_693),
    }

    KNOWN_HASHES: dict[str, str] = {
        "readme": "sha256:ac2a1fc953e9bfde34bb3b6598dc0114c921d3034e19a3ec328b87e92e653c6b",
        "moas": "sha256:1e698da47cf6241e96cd6cce6f77cfa47899ee51aff88f6872ef3bf3cae2e034",
        "pcls": "sha256:abe99e71a47baa301ed5ccc17277d495db2a60a5f49a61a0e1081ddf6de80c11",
        "clusters_tbl": "sha256:bfb304ea5680dc8deffa4bb2473ee47fee99166618685d8918ee7ba48d02e0b9",
    }
    return KNOWN_HASHES, SMALL_FILES


@app.cell(hide_code=True)
def _():
    mo.md(r"""
    ## Fetch helper

    `pooch.retrieve` with `known_hash=None` downloads and prints the SHA-256;
    once we paste those into `KNOWN_HASHES`, subsequent runs verify against
    the pin instead of trusting the URL.
    """)
    return


@app.function
def fetch(slug: str, files: dict, known_hashes: dict[str, str]) -> Path:
    """Fetch a Figshare file by slug; cached under data/external/figshare_28373561/."""
    file_id, filename, _size = files[slug]
    return Path(
        pooch.retrieve(
            url=figshare_url(file_id),
            known_hash=known_hashes.get(slug),
            fname=filename,
            path=FIGSHARE_DIR,
            progressbar=True,
        )
    )


@app.cell
def _():
    mo.md(r"""
    ## Pull README + small annotation archives

    The README and small annotation archives total well under 5 MB. We pull
    them unconditionally - no run-button gate. The big similarity matrices
    (hundreds of MB) come later in their own notebook.
    """)
    return


@app.cell
def _(KNOWN_HASHES: dict[str, str], SMALL_FILES):
    SMALL_SLUGS = ["readme", "moas", "pcls", "clusters_tbl"]
    fetched = {slug: fetch(slug, SMALL_FILES, KNOWN_HASHES) for slug in SMALL_SLUGS}
    mo.md("\n".join(f"- `{slug}` -> `{p.name}` ({p.stat().st_size:,} bytes)" for slug, p in fetched.items()))
    return (fetched,)


@app.cell
def _(fetched):
    import tarfile

    EXTRACTED_DIRS = {}
    for slug, archive in fetched.items():
        if archive.suffix == ".gz":
            out = FIGSHARE_DIR / slug
            out.mkdir(exist_ok=True)
            with tarfile.open(archive, "r:gz") as t:
                t.extractall(out, filter="data")
            EXTRACTED_DIRS[slug] = out
        else:
            EXTRACTED_DIRS[slug] = archive
    mo.md("\n".join(f"- `{slug}` -> `{p}`" for slug, p in EXTRACTED_DIRS.items()))
    return (EXTRACTED_DIRS,)


@app.cell(hide_code=True)
def _():
    mo.md(r"""
    ## Cluster table

    `clusters_spectral_clust_tbl.txt` is the rich annotation: one row per
    (condition, cluster) pairing with compound metadata (broad_id, SMILES,
    target, MOA class, etc.). 8,317 rows, 25 columns.
    """)
    return


@app.cell(hide_code=True)
def _(EXTRACTED_DIRS):
    clusters_tbl = pl.read_csv(
        EXTRACTED_DIRS["clusters_tbl"] / "clusters_spectral_clust_tbl.txt",
        separator="\t",
        infer_schema_length=1000,
    )
    mo.md(f"shape: `{clusters_tbl.shape}`")
    return (clusters_tbl,)


@app.cell(hide_code=True)
def _(clusters_tbl):
    mo.ui.table(clusters_tbl.head(20), page_size=20)
    return


@app.cell(hide_code=True)
def _():
    mo.md(r"""
    ## Parse the .gmt files (MOAs and PCLs)

    `moas.txt` and `pcls.txt` are variable-width tab-separated:
    `set_name<tab>set_name<tab>condition_id_1<tab>condition_id_2<tab>...`
    We melt them into long DataFrames.
    """)
    return


@app.function(hide_code=True)
def parse_gmt(path: Path) -> pl.DataFrame:
    """Parse a .gmt-style file into a long DataFrame: (set_name, condition_id)."""
    rows = []
    for line in path.read_text().splitlines():
        if not line.strip():
            continue
        parts = line.split("\t")
        for cond in parts[2:]:
            rows.append((parts[0], cond))
    return pl.DataFrame(rows, schema=["set_name", "condition_id"], orient="row")


@app.cell(hide_code=True)
def _(EXTRACTED_DIRS):
    moas_long = parse_gmt(EXTRACTED_DIRS["moas"] / "moas.txt")
    moas_summary = (
        moas_long.group_by("set_name").len().rename({"len": "n_conditions"}).sort("n_conditions", descending=True)
    )
    mo.md(
        f"**MOAs:** {moas_long.shape[0]:,} (MOA, condition) pairs across **{moas_long['set_name'].n_unique()}** MOAs."
    )
    return (moas_summary,)


@app.cell(hide_code=True)
def _(moas_summary):
    mo.ui.table(moas_summary, page_size=15)
    return


@app.cell(hide_code=True)
def _(EXTRACTED_DIRS):
    pcls_long = parse_gmt(EXTRACTED_DIRS["pcls"] / "pcls.txt")
    pcls_summary = (
        pcls_long.group_by("set_name").len().rename({"len": "n_conditions"}).sort("n_conditions", descending=True)
    )
    mo.md(
        f"**PCL clusters:** {pcls_long.shape[0]:,} (cluster, condition) pairs "
        f"across **{pcls_long['set_name'].n_unique()}** PCL clusters "
        f"(subset of spectral clusters that survived the predictive-cluster filter)."
    )
    return (pcls_summary,)


@app.cell(hide_code=True)
def _(pcls_summary):
    mo.ui.table(pcls_summary, page_size=15)
    return


@app.cell(hide_code=True)
def _():
    mo.md(r"""
    ## What this gives downstream notebooks

    These three DataFrames - `clusters_tbl`, `moas_long`, `pcls_long` - are the
    *reference-set spine*. They map every condition (`screen-wave : broad_id :
    concentration`) to its annotated MOA and PCL cluster membership. Later
    notebooks join compound-level results back through `condition_id` or
    `broad_id` to answer "what MOA does this compound look like?"

    The big similarity matrices in the same Figshare bundle (PCL similarity
    scores, sGR matrices) are deferred - those land in nb03+.
    """)
    return


if __name__ == "__main__":
    app.run()
