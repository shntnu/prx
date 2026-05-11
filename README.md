# prx — PROSPECT eXplore

An experiment in agent-driven scientific data exploration, built around [PROSPECT](https://doi.org/10.1038/s41586-019-1315-z) chemical-genetics data and [Bond et al. 2025](https://doi.org/10.1038/s41467-025-64662-x) — the reference-based MOA inference method that turns PROSPECT primary-screen data into mechanism-of-action assignments.

prx is a curated catalog of [marimo](https://marimo.io) notebooks for chemical-genetics analysis, plus a thin skill that lets an agent compose new analyses from them.
Each notebook is both a runnable demonstration and a source of pure functions other notebooks can [import and reuse](https://docs.marimo.io/guides/reusing_functions/) directly.
Given a new chemical-genetics question, the agent picks relevant notebooks, composes their functions into a new notebook, executes it in a live kernel, and hands back a self-contained, re-runnable result.

PROSPECT generates chemical-genetic interaction (CGI) profiles by screening compound libraries against pooled hypomorphic Mtb strains; Bond et al. 2025 introduced PCL (Perturbagen CLass) analysis — predict MOA for an unknown compound by comparing its CGI profile against a 437-compound annotated reference set.

## The catalog

Each notebook ships with a committed session snapshot under [`notebooks/__marimo__/session/`](notebooks/__marimo__/session/) so the molab preview renders cell outputs without re-executing.

| Notebook | Role | Preview |
|---|---|---|
| [`nb01_orientation.py`](notebooks/nb01_orientation.py) | Landing page, orientation, what's where | [![Open in molab](https://marimo.io/molab-shield.svg)](https://molab.marimo.io/github/broadinstitute/prx/blob/main/notebooks/nb01_orientation.py) |
| [`nb02_figshare_pull.py`](notebooks/nb02_figshare_pull.py) | Pull Bond et al. 2025 Figshare bundle, parse MOA and PCL annotations, build the reference-set spine | [![Open in molab](https://marimo.io/molab-shield.svg)](https://molab.marimo.io/github/broadinstitute/prx/blob/main/notebooks/nb02_figshare_pull.py) |
| [`nb03_hypomorph_correlation.py`](notebooks/nb03_hypomorph_correlation.py) | Load sGR GCT matrix, inspect strain-strain correlation across the 340-d CGI space | [![Open in molab](https://marimo.io/molab-shield.svg)](https://molab.marimo.io/github/broadinstitute/prx/blob/main/notebooks/nb03_hypomorph_correlation.py) |
| [`nb04_pretrained_baseline.py`](notebooks/nb04_pretrained_baseline.py) | Structure-only vs CGI-profile 1-NN baselines for MOA classification on the Bond reference set | [![Open in molab](https://marimo.io/molab-shield.svg)](https://molab.marimo.io/github/broadinstitute/prx/blob/main/notebooks/nb04_pretrained_baseline.py) |
| [`nb05_collapse_diagnostic.py`](notebooks/nb05_collapse_diagnostic.py) | Test whether same-MOA CGI similarity survives after controlling for pairwise chemical similarity | [![Open in molab](https://marimo.io/molab-shield.svg)](https://molab.marimo.io/github/broadinstitute/prx/blob/main/notebooks/nb05_collapse_diagnostic.py) |
| [`nb06_cgi_shape_diversity.py`](notebooks/nb06_cgi_shape_diversity.py) | PCL coverage, rarefaction, and effective CGI-shape diversity in the public Bond data | [![Open in molab](https://marimo.io/molab-shield.svg)](https://molab.marimo.io/github/broadinstitute/prx/blob/main/notebooks/nb06_cgi_shape_diversity.py) |

The agent-facing catalog table in `.claude/skills/compose-notebook/SKILL.md` is the detailed contract: it lists reusable helpers, import patterns, and current gotchas.

Related public catalogs of the same pattern: [jx](https://github.com/broadinstitute/jx) for JUMP Cell Painting, [fgx](https://github.com/broadinstitute/fgx) for FinnGenie human genetics, and [dmx](https://github.com/broadinstitute/dmx) for DepMap Breadbox.

## Getting started

Clone this repo, open Claude Code inside it, and ask: *help me get started*.
The `getting-started` skill installs prereqs ([uv](https://docs.astral.sh/uv/) and the [marimo-pair](https://github.com/marimo-team/marimo-pair) skill), launches `nb01_orientation` in a live marimo kernel, and hands off to the `compose-notebook` skill for the actual analysis.

If you prefer to run setup by hand:

```bash
uv --version  # or: curl -LsSf https://astral.sh/uv/install.sh | sh
AGENT=claude-code  # or: codex
npx skills add marimo-team/marimo-pair -g --agent "$AGENT" -y
uvx marimo edit --sandbox notebooks/nb01_orientation.py
```

The skills reference in-repo notebooks and assets, so they only work in the cloned repo — there's no `npx skills add broadinstitute/prx` flow.

## License

BSD 3-Clause — see [LICENSE](LICENSE).
