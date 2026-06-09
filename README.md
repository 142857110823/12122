# Black Soil Water Erosion Intelligent Prediction and Evidence-Based Evaluation Platform v0.3

Single-base Streamlit platform for black-soil water erosion research.

## What Changed

- Homepage is now a slim dual-pane workbench.
  - Left: core scientific actions only.
  - Right: real result dashboard only.
- Smart assistant can use a backend-only OpenAI Responses API runtime.
- Local optional LLM backend still supports `transformers` directly.
- Scientific tools in `tools.py` remain usable even when API or local model inference is not configured.

## Start

```bash
cd water_erosion_mvp
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
streamlit run app.py
```

## Shared Access On A Trusted LAN

The default command above is suitable for local preview. To let other users on
the same trusted network open the platform from their browsers, start Streamlit
with the shared launcher:

```powershell
cd D:\空\water_erosion_mvp
.\scripts\start_shared.ps1 -Port 8501
```

The script binds Streamlit to `0.0.0.0` and prints two URLs:

- Local: `http://127.0.0.1:8501/`
- Shared: `http://<this-machine-ip>:8501/`

Other users should open the shared URL from machines that can reach the host.
If Windows Firewall blocks the port, allow inbound TCP traffic for the selected
port only on trusted/private networks. For a server, pass the DNS name or public
reverse-proxy host explicitly:

```powershell
.\scripts\start_shared.ps1 -Port 8501 -PublicHost erosion.example.edu
```

This shared launcher does not add account login, HTTPS, role permissions, rate
limits, backups, or audit controls. Do not expose the raw Streamlit port
directly to the public internet. For public or school-wide use, place it behind
VPN or an HTTPS/authenticated reverse proxy and keep `OPENAI_API_KEY` only in
`.env` or the server environment.

## Assistant LLM Configuration

Configure `.env` or `config/llm.toml`:

```env
LLM_BACKEND=openai
OPENAI_API_KEY=your-server-side-key
OPENAI_MODEL=gpt-5.5
OPENAI_TIMEOUT_SECONDS=30
OPENAI_MAX_OUTPUT_TOKENS=700
ALLOW_EXTERNAL_LLM=false
ASSISTANT_CONTEXT_POLICY=metadata_only
DATA_RETENTION_DAYS=30

# Optional local fallback mode:
# LLM_BACKEND=transformers
LLM_LOCAL_MODEL_PATH=D:/path/to/local/model
LLM_DEVICE=auto
LLM_DTYPE=auto
LLM_MAX_NEW_TOKENS=512
LLM_TEMPERATURE=0.3
```

Supported runtime fields:

- `LLM_BACKEND`
- `OPENAI_API_KEY`
- `OPENAI_MODEL`
- `OPENAI_TIMEOUT_SECONDS`
- `OPENAI_MAX_OUTPUT_TOKENS`
- `ALLOW_EXTERNAL_LLM`
- `ASSISTANT_CONTEXT_POLICY`
- `DATA_RETENTION_DAYS`
- `LLM_LOCAL_MODEL_PATH`
- `LLM_DEVICE`
- `LLM_DTYPE`
- `LLM_MAX_NEW_TOKENS`
- `LLM_TEMPERATURE`

Notes:

- Keep `OPENAI_API_KEY` in `.env` or the system environment only. Do not put it in frontend code, source files, screenshots, test fixtures, logs, or recap documents.
- External LLM calls are disabled by default. Set `ALLOW_EXTERNAL_LLM=true` only for controlled backend use after confirming the data can be sent to an external model.
- If `LLM_BACKEND=openai` but the API key, SDK, network, or model call is unavailable, the assistant falls back to a deterministic local response and the scientific workflow remains available.
- Install a matching PyTorch build separately when needed for your CPU/CUDA environment.
- Local or API LLM is an optional enhancement for free-form explanation. It is not required for data quality checks, feature building, training, explanation export, prediction, or bundle export.
- See `docs/DATA_SECURITY.md` for data storage, export, assistant, and cleanup boundaries.

## Homepage Contract

The homepage should expose only:

- Data upload/load
- Data quality check
- Feature table build
- Model training
- Explanation analysis
- Future prediction
- Result export

The right-side dashboard should expose only real outputs from session state or existing files:

- Model results
- Explanation results
- Prediction results
- Export results

## Data

Use the trusted raw-source directory as configured by the platform workflow when running the quick/full scientific chain.
The source directory must remain read-only.

## Verification

Recommended checks:

```bash
python -m py_compile app.py agent.py tools.py
python -m unittest test_ui_design_assets.py
python -m unittest test_p0_p3_upgrade.py
python scripts/openai_assistant_smoke.py --require-key
```

Use the smoke command without `--require-key` to verify deterministic fallback
behavior when no API key is configured.
