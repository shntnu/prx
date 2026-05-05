---
name: getting-started
description: >-
  Walk a first-time prx user from a fresh clone to a running marimo kernel
  with agent composition enabled. Trigger when the user says "help me get
  started", "onboard me", "set me up", "I'm new to prx", "first time using
  prx", "what do I do next", or asks any PROSPECT-composition question
  before a marimo kernel is running and marimo-pair is connected. Sets up
  uv, prompts the user to install the marimo-pair skill, launches the
  marimo server on nb01_orientation. Use before compose-notebook: once
  setup is verified, hand off to that skill for the actual analysis.
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

(Nix users with `direnv allow`-ed in this repo get `uv` from the flake;
no separate install needed.)

### 2. Install the marimo-pair skill

marimo-pair is a self-contained skill (SKILL.md + bundled `scripts/`)
distributed via [skills.sh](https://skills.sh). Install it globally for
the user:

    npx skills add marimo-team/marimo-pair -g --agent claude-code -y

After install, the user should restart their Claude Code session so the
skill loads. On the next session, marimo-pair's tools (e.g. running
`scripts/execute-code.sh`) are available via its `allowed-tools`
frontmatter. If you don't see the skill, it isn't loaded yet.

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

## Don't

- Don't write PROSPECT analysis code before setup is verified - you'll
  burn the user's time debugging import errors and missing deps.
- Don't vendor marimo-pair into this repo. It's upstream at
  `marimo-team/marimo-pair`; installing via `npx skills add` keeps
  users current with fixes.
- Don't bypass `compose-notebook` after setup completes. The whole
  point is composition from the catalog; writing ad-hoc queries
  defeats the skill's purpose.
