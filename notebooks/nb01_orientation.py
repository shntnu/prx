# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "marimo",
# ]
# ///

import marimo

__generated_with = "0.23.5"
app = marimo.App(width="medium")


@app.cell(hide_code=True)
def _():
    import marimo as mo

    return (mo,)


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    # nb01 - orientation

    Landing notebook for `prospect`. Sketches the working questions, points at the
    foundational papers and public data, and names the first concrete things worth
    poking at. Later notebooks (`nb02_*`, `nb03_*`, ...) import from here as the
    catalog grows.

    See `references/papers.md` for the annotated bibliography this notebook is
    seeded from, and `CLAUDE.md` for the architectural choice (jx-style notebook
    catalog, no library / no snakemake) that frames how to extend it.
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## What PROSPECT is

    PROSPECT is the Hung lab's chemical-genetic interaction (CGI) profiling
    platform for *Mycobacterium tuberculosis*. The setup:

    - ~500 barcoded TB mutants, each hypomorphic for one essential target
      (SspB-degron knockdown of ~474 essential genes)
    - pooled and screened against 10K-100K compound libraries
    - amplicon sequencing reads out per-mutant abundance, yielding a CGI profile
      (compound x mutant) for each compound
    - a complementary CRISPRi panel paired with expression profiles extends the
      same idea to a transcriptional readout

    Two things fall out of those profiles:

    1. **Mutant-selective hits** - molecules active against specific essential-
       target knockdowns but not wild type. Starting points for new TB chemo.
    2. **MOA inference from the primary screen** - a compound's CGI profile,
       compared against an annotated reference set, suggests target / pathway
       directly from screening data (Bond et al. 2025; the "PCL" approach).
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Working questions

    Three threads to pull on. Each can be opened as its own `nb0X_*` notebook
    later.

    1. **Mutant-selective hits.** Given a compound's CGI profile, when does
       "selective on mutant X" actually mean target engagement vs. a strain-
       specific quirk? What does the false-positive rate look like across the
       full pool, and how does it change with screening concentration?
    2. **MOA from primary screen (PCL).** Reproduce the Bond et al. PCL workflow
       on the public 437-compound reference set: build CGI profiles, compute
       sGR + cluster membership, run leave-one-out, sanity check the 70%/75%
       sens/prec headline. Then ask where it fails.
    3. **CRISPRi + expression as a parallel readout.** A CRISPRi knockdown +
       expression panel is the natural complement to CGI profiles. We do not
       have a clean primary reference for it yet (see `references/papers.md`
       TODO); confirm with collaborators before building on it.
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Foundational papers

    Full bibliography in `references/papers.md`. Three seed papers anchor the
    project:

    | Tag | Citation | Why |
    |-----|----------|-----|
    | Johnson 2019 | *Large-scale chemical-genetics yields new M. tuberculosis inhibitor classes*, Nature 571, 72-78 | Founding PROSPECT paper. Read first - everything else assumes its setup. |
    | Bond 2025 | *Reference-based chemical-genetic interaction profiling...*, Nat Commun | The method paper. PCL analysis, 437-compound reference set, leave-one-out benchmarks. |
    | Scalia 2025 | *Deep-learning-based virtual screening of antibacterial compounds*, Nat Biotechnol | GNEprop trained on a 2M-compound *E. coli* phenotypic screen, virtual-screened 1.4B compounds. The modeling counterpart to PROSPECT. |

    Use the `/paperclip` skill (bioRxiv / medRxiv / PMC) for paper content. The
    PDFs in `references/` are gitignored and along for reference, not for
    parsing. Preprint doc_ids are listed in `references/papers.md`.
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Public data and code

    From the Bond et al. 2025 paper - these are the concrete artifacts to
    download / clone / read first.

    **Data**

    - Figshare (sGR + PCL similarity + PCL confidence + cluster membership for
      reference + GSK + BRD4310 sets):
      <https://doi.org/10.6084/m9.figshare.28373561>
    - Dryad (RNA-seq datasets):
      <https://doi.org/10.5061/dryad.qz612jmrg>
    - Reference-set MOA annotations: Supplementary Data 1 and 5 of Bond 2025

    **Code**

    - `concensusGLM` (R, GLM-based hit-calling):
      <https://github.com/broadinstitute/concensusGLM>
    - `cmapM` (Matlab, Connectivity Map utilities):
      <https://github.com/cmap/cmapM>
    - `cmapR` (Bioconductor, Connectivity Map utilities):
      <https://github.com/cmap/cmapR>
    - PCL analysis code: Code Ocean / GitHub link in the published Bond 2025

    **Viewers**

    - Morpheus heatmap viewer:
      <https://software.broadinstitute.org/morpheus>
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## First concrete things to poke at

    Ordered roughly by "easiest first / least dependency on collaborators":

    1. **Pull the Figshare bundle** with `pooch`, peek at the table shapes, get a
       feel for what one row of an sGR / PCL-similarity table looks like.
       (`nb02_*` candidate.)
    2. **Read the Bond 2025 reference set** (Supplementary Data 1 + 5) and build
       a small polars DataFrame of compound -> annotated MOA. This is the spine
       everything else hangs off.
    3. **Reproduce one PCL leave-one-out call** for a single reference compound
       end-to-end, against the published cluster membership. Useful as a
       correctness check before doing anything fancier.
    4. **Pull one RNA-seq dataset from Dryad** to scope out the CRISPRi /
       expression side - just to know format and size. Don't build on it until
       we have a primary reference.

    Open question to bring to the next collaborator sync: which slice of this
    is most useful right now?
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Catalog conventions (for `nb02_*` and beyond)

    - Notebooks are numbered: `nb<NN>_<short_description>.py`, two-digit zero-
      padded. Later notebooks import from earlier ones - the catalog is a
      cumulative DAG, not a flat collection.
    - Helpers stay close to API primitives (`polars`, `duckdb`, `pooch`) inside
      notebooks. Don't extract a `src/prospect/` module - that scaffolding is
      dormant by design (see `CLAUDE.md`).
    - Raw data is never edited. Pulled artifacts go to `data/raw/` or
      `data/external/`; transformations land in `data/interim/` or
      `data/processed/<analysis-name>/`.
    - The cell below establishes `PROJ_ROOT` and the canonical data subdirs;
      later notebooks should import these rather than re-deriving paths.
    """)
    return


@app.cell
def _():
    from pathlib import Path

    PROJ_ROOT = Path(__file__).resolve().parents[1]
    DATA_DIR = PROJ_ROOT / "data"
    RAW_DATA_DIR = DATA_DIR / "raw"
    EXTERNAL_DATA_DIR = DATA_DIR / "external"
    INTERIM_DATA_DIR = DATA_DIR / "interim"
    PROCESSED_DATA_DIR = DATA_DIR / "processed"
    REFERENCES_DIR = PROJ_ROOT / "references"
    return (
        DATA_DIR,
        EXTERNAL_DATA_DIR,
        INTERIM_DATA_DIR,
        PROCESSED_DATA_DIR,
        PROJ_ROOT,
        RAW_DATA_DIR,
        REFERENCES_DIR,
    )


@app.cell(hide_code=True)
def _(
    DATA_DIR,
    EXTERNAL_DATA_DIR,
    INTERIM_DATA_DIR,
    PROCESSED_DATA_DIR,
    PROJ_ROOT,
    RAW_DATA_DIR,
    REFERENCES_DIR,
    mo,
):
    mo.md(f"""
    Resolved paths for this checkout:

    - `PROJ_ROOT` = `{PROJ_ROOT}`
    - `DATA_DIR` = `{DATA_DIR}`
    - `RAW_DATA_DIR` = `{RAW_DATA_DIR}`
    - `EXTERNAL_DATA_DIR` = `{EXTERNAL_DATA_DIR}`
    - `INTERIM_DATA_DIR` = `{INTERIM_DATA_DIR}`
    - `PROCESSED_DATA_DIR` = `{PROCESSED_DATA_DIR}`
    - `REFERENCES_DIR` = `{REFERENCES_DIR}`
    """)
    return


if __name__ == "__main__":
    app.run()
