# Project Codex Guidance

Use Chinese by default unless the requested deliverable clearly needs English.

## Output Preferences

- Any plan or proposal must include: 开展目的, 开展原因, 开展方案, 开展步骤, 验证标准, 验收门槛, 注意事项, and 潜在问题.

## Project Boundary

- This repository is the active single base: `D:\空\water_erosion_mvp`.
- Keep the Streamlit app as the only frontend entry point. Do not create a second HTML/Vue/React frontend.
- Keep shared access explicit through `scripts/start_shared.ps1`; do not make ordinary local preview listen on `0.0.0.0` by default.
- Do not describe the raw Streamlit server as providing account login, role permissions, HTTPS, rate limiting, audit logging, or multi-tenant isolation.
- Main application files:
  - `app.py`: Streamlit UI shell, workflow navigation, session state, assistant panel, and UI action binding.
  - `agent.py`: local optional LLM wrapper and tool-calling agent.
  - `tools.py`: scientific workflow tools for upload inspection, feature building, model training, prediction, explanations, gates, and exports.
  - `utils/raster_io.py`: raster reading, reprojection, alignment, and sample TIF helpers.
  - `utils/viz.py`: plotting, map, and thumbnail helpers.

## Commands

| Purpose | Command | Status |
|---|---|---|
| Project venv | `D:\codex\envs\water_erosion_mvp_py313\Scripts\python.exe` | Verified Python 3.13.12 |
| Install deps | `D:\codex\envs\water_erosion_mvp_py313\Scripts\python.exe -m pip install -r requirements.txt` | Verified installed successfully |
| Run app | `D:\codex\envs\water_erosion_mvp_py313\Scripts\streamlit.exe run app.py` | Verified by temporary smoke run: `http://localhost:8501` returned HTTP 200 |
| Dependency consistency | `D:\codex\envs\water_erosion_mvp_py313\Scripts\python.exe -m pip check` | Verified: no broken requirements |
| Compile core Python | `D:\codex\envs\water_erosion_mvp_py313\Scripts\python.exe -m py_compile app.py agent.py tools.py utils\raster_io.py utils\viz.py` | Verified |
| UI/design tests | `D:\codex\envs\water_erosion_mvp_py313\Scripts\python.exe -m unittest test_ui_design_assets.py` | Verified: 10 tests passed |
| P0-P3 upgrade tests | `D:\codex\envs\water_erosion_mvp_py313\Scripts\python.exe -m unittest test_p0_p3_upgrade.py` | Verified: 32 tests passed, 1 skipped |
| Full unittest discovery | `D:\codex\envs\water_erosion_mvp_py313\Scripts\python.exe -m unittest discover -p "test_*.py"` | Verified: 42 tests passed, 1 skipped |
| P0-P3 + global risk regression | `D:\codex\envs\water_erosion_mvp_py313\Scripts\python.exe -m unittest -v test_p0_p3_upgrade.py test_global_risk_fixes.py` | Verified: 74 tests passed |

## Directory Map

- `.streamlit/config.toml`: Streamlit theme and server settings.
- `config/llm.toml`: optional assistant LLM runtime config. OpenAI API mode is allowed only as a backend-only flow using environment variables; never expose API keys in Streamlit UI or source files. Local `transformers` mode remains supported.
- `data/uploads`: sample/input rasters and uploaded files.
- `data/features`, `data/models`, `data/predictions`, `data/runs`: generated scientific artifacts and run evidence. Treat existing artifacts as evidence; avoid manual edits unless the task is explicitly about generated outputs.
- `docs/UI_DESIGN_SYSTEM.md`: UI design system and non-negotiable frontend constraints.
- `docs/homepage_final_structure_board_2026-06-06.md`: homepage scope, allowed content, and acceptance criteria.
- `docs/figma_handoff`: design handoff assets covered by UI tests.
- `scripts`: QA, Figma handoff, and visual audit helpers.
- `workflow-log` and `Workflow-Logs`: historical decisions, error logs, and execution notes. Read relevant logs before substantial changes.
- `prompts`: system prompt and tool descriptions used by the local agent.

## Implementation Rules

- Preserve the single-base workflow: data access -> quality gate -> feature table -> model training/ranking -> explanations/spatial artifacts -> prediction/report/evidence bundle.
- Every UI action should map to `handle_action()` and a real tool call, state transition, or explicit non-compute action.
- Do not display invented metrics, maps, downloads, gate verdicts, or evidence paths. Empty states are preferable to fake evidence.
- Keep homepage content within the structure board: hero, three research cognition cards, and one collapsed reading expander. Do not put workflow, gate, metric, or result details back on the homepage.
- Assistant LLM behavior may use backend-only OpenAI API mode or local `transformers` mode. API keys must come from `.env` or process environment variables and must never be stored in frontend state, source files, docs examples with real values, logs, tests, or recap files. API failures must degrade to a non-blocking fallback and must not interrupt the scientific workflow.
- External assistant context must be built through a metadata-only whitelist summary; never serialize full Streamlit/session state into an external LLM prompt.
- Assistant external request timeouts must stay shorter than the Streamlit UI assistant timeout so fallback responses do not leave long-running external calls behind.
- When updating the selected/best model, keep in-memory state, the current run evidence directory, and `data/models` legacy compatibility artifacts consistent.
- Evidence bundle ZIP export must redact every text-like deliverable it writes, including JSON, Markdown, CSV, TXT, JSONL, HTML, log, XML, YAML/YML, and TOML files.
- Manual hyperparameter widgets and backend validation must accept the same default values; UI-visible defaults such as sklearn `max_features="sqrt"` must train, optimize, and retrain without being treated as invalid.
- Do not read or print `.env` unless the task specifically requires it; it may contain sensitive local configuration.
- Be careful with file encodings. `app.py` previously contained a duplicate UTF-8 BOM that broke `py_compile`; verify byte prefixes if syntax errors mention `U+FEFF`.

## Verification Expectations

- Run the smallest relevant verification before claiming completion.
- For Python/UI changes, start with:
  - `D:\codex\envs\water_erosion_mvp_py313\Scripts\python.exe -m py_compile app.py agent.py tools.py utils\raster_io.py utils\viz.py`
- For homepage, UI assets, local LLM contract, or design-system changes, also run:
  - `D:\codex\envs\water_erosion_mvp_py313\Scripts\python.exe -m unittest test_ui_design_assets.py`
- For P0-P3 tool binding, run context, model ranking, or evidence export changes, also run:
  - `D:\codex\envs\water_erosion_mvp_py313\Scripts\python.exe -m unittest test_p0_p3_upgrade.py`
- If dependencies are missing, report the exact missing module and command that failed instead of claiming tests passed.

## Known Environment Notes

- This directory is not currently a Git repository; `.git` was not present during onboarding.
- The `git` executable was not available in this environment during onboarding.
- The active Python found during onboarding was `D:\program\python3.13\python.exe`.
- The configured project environment is `D:\codex\envs\water_erosion_mvp_py313`.
- Required packages from `requirements.txt` are installed in that environment.
- `catboost` 1.2.10 and `shap` 0.52.0 are installed and listed in `requirements.txt`; CatBoost training/optimization/retrain and small-run real SHAP explanation paths are verified in tests.
- `transformers` is installed, but PyTorch is not installed. This is acceptable for the required scientific workflow because local LLM model inference is optional; install a matching PyTorch build only when local model execution is explicitly needed.
- Test output may warn that `wmic` is unavailable for physical core detection; current tests still pass and joblib falls back to logical cores.
- Streamlit 1.58.0 emits deprecation warnings for `st.components.v1.html`; tests currently pass, but UI maintenance should eventually migrate those embeds to `st.iframe`.
- A temporary Streamlit run smoke was verified on port 8501 and then stopped. Start the app explicitly with the documented command when an interactive session is needed.
