# Clinical Note Review

A local portfolio application for reviewing structured notes derived from synthetic clinical transcripts. Python/FastAPI backend, vanilla JavaScript frontend, SQLite revision storage, local Ollama/Qwen3 integration, and optional OpenAI Responses API integration. Demo mode uses extractive rules, not an LLM. No React build step or external frontend assets are required.

## Start and sign in

Run `./run.sh` from this directory, then open http://127.0.0.1:8765. The launcher installs dependencies into a virtual environment on first run. Python 3.12 or newer is recommended; local tests used 3.14.

The browser asks for a username and password:

- Username: `adeel`
- Password: the contents of `data/.local-password` (generated randomly on first import).

Open the password file locally; do not share it or commit it. Browser Basic authentication may remain cached until the browser is closed. This login is for a single-user loopback application, not internet hosting. Processes running as your operating-system user can read the password and data.

## Run the local LLM (no API key)

Ollama is installed with Homebrew and Qwen3 4B has been downloaded on this Mac.

1. In one terminal, run `./run-ollama.sh` from this directory.
2. In another terminal, run `./run.sh`.
3. Open http://127.0.0.1:8765, log in, and select **Local LLM · Qwen3 4B**.
4. Generate a synthetic draft. The first request may take longer while the model loads.

For a fresh machine: install Ollama from its official distribution, start `./run-ollama.sh`, then run `ollama pull qwen3:4b` once. The download is approximately 2.5 GB. The model files live under `data/models` and are excluded from the source archive.

The launcher binds Ollama to localhost, disables Ollama cloud features, and limits concurrency. The app uses a fixed localhost endpoint and fixed local model; it does not send OpenAI credentials to Ollama. Local requests have no provider API fee. They consume your device's memory, compute, and power. Do not expose Ollama's port to other devices; its API does not share this app's password protection.

Stop each terminal with Ctrl+C when finished. Native Ollama is used to access the Mac GPU; the Docker configuration does not connect to host Ollama.

## Optional OpenAI provider

1. Create an API key at https://platform.openai.com/api-keys. Configure API billing and spending controls in your account as needed.
2. Open `.env` locally (or copy `.env.example` if it does not exist).
3. Set `OPENAI_API_KEY` to your key. Set `OPENAI_MODEL` to a model available to your account that supports Responses structured outputs. Keep the optional pricing fields blank unless you supply verified prices.
4. Stop the server with Ctrl+C and run `./run.sh` again.
5. Reload the page and select Live LLM. Generate one synthetic note before running a batch evaluation. Each live evaluation case makes a provider request.

The key stays server-side. Never put it in browser code, a screenshot, a resume, or GitHub. The launcher reads `.env` as shell configuration: only edit it yourself and do not paste untrusted shell content. Official setup: https://developers.openai.com/api/docs/quickstart. Structured outputs: https://developers.openai.com/api/docs/guides/structured-outputs.

## Walkthrough

1. Select the synthetic routine visit, confirm synthetic input, and generate a demo draft.
2. Click source citations and compare each statement with the transcript.
3. Edit a statement, enter a reviewer name, and save a revision.
4. Review all flags, confirm review, and approve. Approved records are immutable; JSON export includes history.
5. In Evaluations, compare baseline-v1 and grounded-v2 across 30 synthetic cases. Inspect the correction failures rather than treating the score as medical accuracy.
6. Activity shows recent generation counts, latency, failures, and usage. Evaluation requests are excluded from these generation metrics.

## Architecture and scope

Transcript → labeled turns → demo extractor or live model → schema and reference validation → draft → human edits/approval → SQLite history/export.

The live model is instructed to preserve negation, attribution, and explicit corrections. Validation checks structure and source IDs, not semantic truth. This is a bounded LLM workflow, not an autonomous agent, retrieval/RAG system, audio transcription product, or EHR integration.

## Verification

Run `.venv/bin/python -m pytest -q`.

Run `.venv/bin/python -m evaluations.run --provider demo --version grounded-v2 --output evaluations/latest.json`.

Verified locally: 29 automated tests pass, including authentication and security regression tests. Before authentication was added, browser interaction checks covered generation, citation navigation, edits, saved revisions, approval, and evaluation results. Full browser interaction after authentication remains to be verified.

Recorded demo results: baseline 10/30 cases; grounded 25/30, with five correction failures. Dataset assertions use substrings and section placement. Cases are templated synthetic examples, not an independent clinical benchmark. Live provider behavior is mocked in automated tests; OpenAI has not been tested against its live service. Local Qwen3 has successfully generated a real source-linked note through the running app (approximately 9 seconds for the first tested request). Docker files are provided but Docker is unavailable locally and execution is untested.

## Security boundaries

See [SECURITY.md](SECURITY.md). Synthetic data only. No clinical validation, HIPAA compliance claim, multi-user access control, or encrypted database is provided. Do not expose this server to a network or enter actual patient data.

Local Qwen3 regression run: 25/30 cases, 70/75 assertions passed. See evaluations/qwen3-local.json. This measures literal regression expectations, not clinical accuracy.
