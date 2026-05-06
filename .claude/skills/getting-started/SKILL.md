---
name: getting-started
description: >-
  Walk a first-time prx user from a fresh clone to a running marimo kernel
  with agent composition enabled. Trigger when the user says "help me get
  started", "onboard me", "set me up", "I'm new to prx", "first time using
  prx", "what do I do next", or asks any PROSPECT-composition question
  before a marimo kernel is running and marimo-pair is connected. Sets up
  uv, prompts the user to install the marimo-notebook and marimo-pair
  skills, launches the marimo server on nb01_orientation. Use before
  compose-notebook: once setup is verified, hand off to that skill for
  the actual analysis.
---

# Getting started with prx

Your job: get this user from a cold clone to a live marimo kernel, then hand
off to the `compose-notebook` skill for the actual composition.

## Setup flow

### 1. Verify uv is installed

Run `uv --version`. If it fails, tell the user to run:

    curl -LsSf https://astral.sh/uv/install.sh | sh

Then have them source their shell profile (`. ~/.zshrc`) or open a new
terminal. Re-check `uv --version`.

### 2. Install the marimo-notebook and marimo-pair skills

Both are upstream skills from `marimo-team`, distributed via
[skills.sh](https://skills.sh). Neither is vendored in this repo
(both are gitignored under `.claude/skills/`); install them globally
for the user:

    npx skills add marimo-team/skills -g --agent claude-code -y
    npx skills add marimo-team/marimo-pair -g --agent claude-code -y

The first installs `marimo-notebook` (authoring guidance for `@app.cell`
patterns, reactivity, anywidget, etc.); the second installs `marimo-pair`
(bundled `scripts/` for executing code against a running kernel).

Skills installed globally via `-g` usually register live - you can
proceed without restarting the session. If a later step reports the
skill missing (e.g. marimo-pair's `scripts/execute-code.sh` not in
the allowed tools), have the user restart Claude Code and re-run
`/getting-started`; it'll skip ahead since the prior steps are
idempotent.

### 3. Launch the marimo server

From the prx repo root, pick a free port and start `nb01_orientation` in
`--sandbox` mode so the PEP 723 header at the top of the file provisions
a venv automatically:

    PORT=$(python -c "import socket; s=socket.socket(); s.bind(('127.0.0.1',0)); print(s.getsockname()[1])")
    env -u PYTHONPATH uvx marimo edit --sandbox --headless --no-token \
        --port $PORT notebooks/nb01_orientation.py

Use `run_in_background=true` on the Bash call so you can poll while
deps install. First launch installs marimo + its deps (~30 sec - 2 min
depending on network); subsequent launches are near-instant. Verify
the server is up with:

    curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:$PORT/

Expect HTTP 200. Tell the user the URL so they can open the browser UI
alongside your session if they want to watch cells render.

### 4. Hand off to compose-notebook

Once the kernel is live and marimo-pair is connected:

1. Ask the user what they want to explore. The typical first move in
   this project is pulling the Bond et al. 2025 Figshare bundle (sGR +
   PCL similarity tables) and looking at table shapes - that's what
   `nb02_figshare_pull.py` does.
2. Invoke the `compose-notebook` skill and follow its "Process for a
   new composition" checklist against the running kernel.

## Gotchas

- **Nix shells poison PYTHONPATH** with a bad websockets shim that
  crashes `marimo edit` on startup. The `env -u PYTHONPATH` prefix in
  step 3 avoids this. Apply it to any marimo invocation on Nix.
- **`--sandbox` is required.** Without it, `uvx marimo edit` opens the
  file picker but does not provision a venv from the PEP 723 header -
  opening any notebook then fails with `ModuleNotFoundError`.
- **Ports 2718-2720 are often taken** on shared machines. The step-3
  picker grabs a random free port. Don't hardcode.
- **Sandbox locks one notebook per kernel.** Each `marimo edit --sandbox
  <file>` provisions a venv from that file's PEP 723 header only. To
  run a different notebook (e.g. nb02 alongside nb01), launch a second
  server on a fresh port - don't try to switch files in a running
  sandbox kernel. Track the port-per-notebook (e.g. write to
  `/tmp/prx_port_nbNN.txt`) so you can address each one later.

## Don't

- Don't write PROSPECT analysis code before setup is verified - you'll
  burn the user's time debugging import errors and missing deps.
- Don't vendor `marimo-notebook` or `marimo-pair` into this repo.
  They're upstream at `marimo-team/skills` and `marimo-team/marimo-pair`;
  installing via `npx skills add` keeps users current with fixes.
- Don't bypass `compose-notebook` after setup completes. The whole
  point is composition from the catalog; writing ad-hoc queries
  defeats the skill's purpose.
