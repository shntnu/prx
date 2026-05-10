# prx -- PROSPECT eXplore

A marimo notebook catalog for chemical-genetics analysis on [PROSPECT](https://doi.org/10.1038/s41586-019-1315-z) data, built around [Bond et al. 2025](https://doi.org/10.1038/s41467-025-64662-x): the reference-based MOA inference method that turns PROSPECT primary-screen data into mechanism-of-action assignments.

The deliverable is a catalog of numbered marimo notebooks - each a runnable demonstration of a real PROSPECT use case, and a source of pure functions other notebooks can import.
An AI agent ([Claude Code](https://code.claude.com/docs) + [marimo-pair](https://github.com/marimo-team/marimo-pair)) composes new analyses against the catalog in a live kernel.

## The catalog

| Notebook | Role | Preview |
|---|---|---|
| [`nb01_orientation.py`](notebooks/nb01_orientation.py) | Landing page, orientation, what's where | [![Open in molab](https://marimo.io/molab-shield.svg)](https://molab.marimo.io/github/broadinstitute/prx/blob/main/notebooks/nb01_orientation.py) |
| [`nb02_figshare_pull.py`](notebooks/nb02_figshare_pull.py) | Pull Bond et al. 2025 Figshare bundle, parse MOA and PCL annotations, build the reference-set spine | [![Open in molab](https://marimo.io/molab-shield.svg)](https://molab.marimo.io/github/broadinstitute/prx/blob/main/notebooks/nb02_figshare_pull.py) |
| [`nb03_hypomorph_correlation.py`](notebooks/nb03_hypomorph_correlation.py) | Load sGR GCT matrix, inspect strain-strain correlation across the 340-d CGI space | [![Open in molab](https://marimo.io/molab-shield.svg)](https://molab.marimo.io/github/broadinstitute/prx/blob/main/notebooks/nb03_hypomorph_correlation.py) |
| [`nb04_pretrained_baseline.py`](notebooks/nb04_pretrained_baseline.py) | Structure-only vs CGI-profile 1-NN baselines for MOA classification on the Bond reference set | [![Open in molab](https://marimo.io/molab-shield.svg)](https://molab.marimo.io/github/broadinstitute/prx/blob/main/notebooks/nb04_pretrained_baseline.py) |
| [`nb05_collapse_diagnostic.py`](notebooks/nb05_collapse_diagnostic.py) | Test whether same-MOA CGI similarity survives after controlling for pairwise chemical similarity | [![Open in molab](https://marimo.io/molab-shield.svg)](https://molab.marimo.io/github/broadinstitute/prx/blob/main/notebooks/nb05_collapse_diagnostic.py) |
| [`nb06_cgi_shape_diversity.py`](notebooks/nb06_cgi_shape_diversity.py) | PCL coverage, rarefaction, and effective CGI-shape diversity in the public Bond data | [![Open in molab](https://marimo.io/molab-shield.svg)](https://molab.marimo.io/github/broadinstitute/prx/blob/main/notebooks/nb06_cgi_shape_diversity.py) |

The agent-facing catalog table in `.claude/skills/compose-notebook/SKILL.md` is the detailed contract: it lists reusable helpers, globals, dependency gotchas, and the current composition pattern.

Related public catalogs of the same pattern: [jx](https://github.com/broadinstitute/jx) for JUMP Cell Painting, [fgx](https://github.com/broadinstitute/fgx) for FinnGenie human genetics, and [dmx](https://github.com/broadinstitute/dmx) for DepMap Breadbox.

## Getting started

Clone this repo, open Claude Code inside it, and ask: *help me get started*.
The `getting-started` skill (at `.claude/skills/getting-started/SKILL.md`) installs prereqs ([uv](https://docs.astral.sh/uv/) and the [marimo-pair](https://github.com/marimo-team/marimo-pair) skill), launches `nb01_orientation` in a live marimo kernel, and hands off to the `compose-notebook` skill for the actual analysis.
Claude Code auto-loads `.claude/skills/` from the working directory.

If you prefer to run setup by hand:

```bash
# 1. Verify uv is installed
uv --version  # or: curl -LsSf https://astral.sh/uv/install.sh | sh

# 2. Install marimo-pair for your current agent (codex or claude-code)
AGENT=codex  # or: claude-code
npx skills add marimo-team/marimo-pair -g --agent "$AGENT" -y

# 3. Launch a notebook in --sandbox mode (PEP 723 deps auto-provisioned)
uvx marimo edit --sandbox notebooks/nb01_orientation.py
```

## What this is for

PROSPECT generates chemical-genetic interaction (CGI) profiles by screening compound libraries against pooled hypomorphic Mtb strains.
Bond et al. 2025 introduced PCL (Perturbagen CLass) analysis: predict MOA for an unknown compound by comparing its CGI profile against a 437-compound annotated reference set.
The method paper provides downloadable data (Figshare/Dryad).

prx is where you go to actually do that analysis: pull the data, look at it, find similar compounds, infer MOAs, generate figures.
The catalog covers the building blocks; the agent composes new vignettes from them.

## Companion repo

prx (this) is the public deliverable.
A companion private repo (`prx-dev`) holds the planning, progress log, learning log, dated artifacts, and dev-only scaffolding.
The split mirrors [jx](https://github.com/broadinstitute/jx) / [jx-dev](https://github.com/broadinstitute/jx-dev) - public catalog, private working repo.

## License

BSD 3-Clause - see [LICENSE](LICENSE).
