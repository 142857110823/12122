"""
黑土区水蚀智能预测与证据化评估平台 MVP。
提供数据上传、质量检查、模型训练、解释分析、预测导出等科研操作入口。
"""
import copy
import os
import sys
import json
import time
import traceback
import html
import base64
import re
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from datetime import datetime
from typing import Any, Dict, List, Optional

import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import numpy as np
import rasterio
from rasterio.transform import from_origin

# 纭繚椤圭洰鏍圭洰褰曞湪path涓?
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# ============================================================
# 椤甸潰閰嶇疆
# ============================================================
st.set_page_config(
    page_title="黑土区水蚀智能预测与证据化评估平台",
    page_icon="🌱",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ============================================================
# 鑷畾涔塁SS - 璁捐绯荤粺
# ============================================================
CUSTOM_CSS = """
<style>
:root {
  --color-primary: #1a6b5a;
  --color-primary-light: #2d8f7a;
  --color-primary-dark: #103f34;
  --color-accent: #d9822b;
  --color-surface: rgba(255, 252, 246, 0.96);
  --color-surface-strong: #ffffff;
  --color-bg: #f6f2e8;
  --color-border: #ded6c7;
  --color-text: #20302b;
  --color-muted: #6a716d;
  --color-soft: #eef4f1;
  --color-warning: #d9822b;
  --color-success: #2f8f5b;
  --shadow-sm: 0 8px 24px rgba(18, 52, 45, 0.06);
  --shadow-md: 0 20px 52px rgba(18, 52, 45, 0.10);
  --radius: 16px;
  --radius-lg: 24px;
  --transition: all 0.22s ease;
  --font-sans: "Microsoft YaHei UI", "Microsoft YaHei", "Noto Sans CJK SC", "Segoe UI", sans-serif;
  --font-mono: "Cascadia Mono", "JetBrains Mono", "Consolas", monospace;
}

html, body, [class*="css"] {
  font-family: var(--font-sans);
}

.stApp {
  background:
    radial-gradient(circle at 8% 2%, rgba(217,130,43,0.10), transparent 24%),
    radial-gradient(circle at 94% 4%, rgba(26,107,90,0.11), transparent 24%),
    linear-gradient(180deg, #fbf8f0 0%, #f5efe2 58%, #f7f2e8 100%);
}

.main .block-container {
  padding-top: 0.4rem !important;
  padding-bottom: 4rem !important;
  max-width: 1480px !important;
  padding-left: clamp(1rem, 2vw, 2.4rem) !important;
  padding-right: clamp(1rem, 2vw, 2.4rem) !important;
}

[data-testid="stSidebar"] {
  background: rgba(255, 252, 246, 0.98) !important;
  border-right: 1px solid var(--color-border) !important;
  min-width: 320px !important;
  max-width: 360px !important;
}

[data-testid="stSidebar"] .block-container {
  padding-top: 1.2rem !important;
}

.stButton > button {
  border-radius: 12px !important;
  border: 1px solid var(--color-border) !important;
  background: var(--color-surface-strong) !important;
  color: var(--color-text) !important;
  font-weight: 600 !important;
  transition: var(--transition) !important;
}

.stButton > button:hover {
  transform: translateY(-1px);
  border-color: var(--color-primary) !important;
  box-shadow: var(--shadow-sm) !important;
}

.stButton > button[kind="primary"] {
  background: var(--color-primary) !important;
  border-color: var(--color-primary) !important;
  color: #ffffff !important;
}

[data-testid="stFileUploader"] {
  border: 1.5px dashed var(--color-border) !important;
  border-radius: var(--radius) !important;
  padding: 1.25rem !important;
  background: rgba(255,255,255,0.58) !important;
}

[data-testid="stExpander"] details,
[data-testid="stVerticalBlockBorderWrapper"] {
  border-radius: var(--radius) !important;
}

[data-testid="stVerticalBlockBorderWrapper"] {
  border-color: rgba(26,107,90,0.10) !important;
  background: linear-gradient(180deg, rgba(255,255,255,0.96), rgba(249,245,237,0.94)) !important;
  box-shadow: var(--shadow-sm) !important;
}

[data-testid="stMetric"] {
  background: rgba(255,255,255,0.72);
  border: 1px solid rgba(26,107,90,0.10);
  border-radius: var(--radius);
  padding: 0.9rem 1rem;
  box-shadow: var(--shadow-sm);
}

[data-testid="stMetricLabel"] {
  color: var(--color-muted) !important;
}

[data-testid="stMetricValue"] {
  color: var(--color-primary-dark) !important;
}

.result-empty {
  border: 1px dashed var(--color-border);
  border-radius: var(--radius);
  padding: 1.1rem 1rem;
  color: var(--color-muted);
  background: rgba(255,255,255,0.58);
  font-size: 13px;
}

.dashboard-strip {
  display: grid;
  grid-template-columns: 1.5fr 1fr;
  gap: 14px;
  margin-bottom: 16px;
}

.dashboard-hero,
.dashboard-note {
  background: linear-gradient(180deg, rgba(255,255,255,0.96), rgba(247,242,233,0.94));
  border: 1px solid rgba(26,107,90,0.12);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-sm);
  padding: 18px 20px;
}

.dashboard-hero h1 {
  margin: 0 0 8px;
  color: var(--color-primary-dark);
  font-size: clamp(28px, 3vw, 42px);
  line-height: 1.04;
  letter-spacing: -0.03em;
}

.dashboard-hero p,
.dashboard-note p {
  margin: 0;
  color: var(--color-muted);
  line-height: 1.75;
  font-size: 14px;
}

.dashboard-chip {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 5px 10px;
  margin-bottom: 12px;
  border-radius: 999px;
  border: 1px solid rgba(26,107,90,0.12);
  background: rgba(238,244,241,0.92);
  color: var(--color-primary);
  font-size: 12px;
  font-weight: 700;
}

.panel-title {
  color: var(--color-primary-dark);
  font-size: 18px;
  font-weight: 800;
  margin: 0 0 0.75rem;
}

.panel-caption {
  color: var(--color-muted);
  font-size: 13px;
  line-height: 1.65;
}

::-webkit-scrollbar {
  width: 6px;
}

::-webkit-scrollbar-thumb {
  background: rgba(26,107,90,0.22);
  border-radius: 999px;
}

@media (max-width: 900px) {
  .dashboard-strip {
    grid-template-columns: 1fr;
  }

  [data-testid="stSidebar"] {
    min-width: 280px !important;
    max-width: 330px !important;
  }
}

/* Problem 6.3 corrected page system */
.problem-top-shell {
  position: sticky;
  top: 0.25rem;
  z-index: 9000;
  margin: 0 0 1rem 0;
  padding: 1rem 1.1rem;
  border: 1px solid rgba(26,107,90,0.14);
  border-radius: 24px;
  background: linear-gradient(135deg, rgba(255,252,246,0.98), rgba(238,246,241,0.94));
  box-shadow: var(--shadow-sm);
}
.problem-top-title { font-size: clamp(24px, 2.4vw, 34px); font-weight: 900; color: var(--color-primary-dark); letter-spacing: -0.03em; margin: 0; }
.problem-top-subtitle { margin: 0.35rem 0 0; color: var(--color-muted); line-height: 1.7; font-size: 14px; }
.nav-status-caption { min-height: 1.15rem; }
.page-card { border: 1px solid rgba(26,107,90,0.12); border-radius: 22px; padding: 1rem; background: rgba(255,255,255,0.72); box-shadow: var(--shadow-sm); margin-bottom: 1rem; }
.step-badge { display: inline-flex; align-items: center; gap: 0.35rem; padding: 0.25rem 0.65rem; border-radius: 999px; background: rgba(26,107,90,0.10); color: var(--color-primary-dark); font-size: 12px; font-weight: 800; margin-bottom: 0.5rem; }
.home-hero {
  display: grid;
  grid-template-columns: minmax(0, 1.35fr) minmax(280px, 0.85fr);
  gap: 18px;
  margin-bottom: 1rem;
}
.home-hero-card,
.home-focus-card {
  position: relative;
  overflow: hidden;
  border: 1px solid rgba(26,107,90,0.12);
  border-radius: 24px;
  background: linear-gradient(180deg, rgba(255,255,255,0.95), rgba(247,242,233,0.92));
  box-shadow: var(--shadow-sm);
}
.home-hero-card {
  padding: 1.4rem 1.5rem 1.45rem;
}
.home-kicker {
  display: inline-flex;
  align-items: center;
  gap: 0.45rem;
  padding: 0.34rem 0.75rem;
  border-radius: 999px;
  background: rgba(26,107,90,0.10);
  border: 1px solid rgba(26,107,90,0.10);
  color: var(--color-primary-dark);
  font-size: 12px;
  font-weight: 800;
  letter-spacing: 0.03em;
}
.home-title {
  margin: 0.95rem 0 0.4rem;
  color: var(--color-primary-dark);
  font-size: clamp(2rem, 4vw, 3.4rem);
  line-height: 1.06;
  letter-spacing: -0.04em;
}
.home-subtitle {
  margin: 0;
  max-width: 40rem;
  color: var(--color-muted);
  font-size: 15px;
  line-height: 1.8;
}
.home-chip-row {
  display: flex;
  flex-wrap: wrap;
  gap: 0.65rem;
  margin-top: 1.1rem;
}
.home-chip {
  display: inline-flex;
  align-items: center;
  padding: 0.46rem 0.82rem;
  border-radius: 999px;
  background: rgba(255,255,255,0.82);
  border: 1px solid rgba(26,107,90,0.12);
  color: var(--color-primary-dark);
  font-size: 12px;
  font-weight: 700;
}
.home-hero-meta {
  margin-top: 1rem;
  color: var(--color-muted);
  font-size: 13px;
  line-height: 1.75;
}
.home-visual {
  min-height: 280px;
  padding: 1.1rem;
}
.home-visual::before,
.home-visual::after {
  content: "";
  position: absolute;
  inset: 18px;
  border-radius: 20px;
}
.home-visual::before {
  background:
    radial-gradient(circle at 20% 22%, rgba(217,130,43,0.18), transparent 22%),
    radial-gradient(circle at 78% 18%, rgba(26,107,90,0.16), transparent 28%),
    linear-gradient(145deg, rgba(250,246,238,0.86), rgba(234,243,239,0.86));
}
.home-visual::after {
  inset: 28px;
  background:
    linear-gradient(110deg, transparent 0%, rgba(26,107,90,0.08) 32%, transparent 33%) 0 0/100% 38px,
    linear-gradient(110deg, transparent 0%, rgba(217,130,43,0.06) 52%, transparent 53%) 0 0/100% 64px,
    radial-gradient(circle at 30% 62%, rgba(16,63,52,0.10), transparent 22%),
    radial-gradient(circle at 72% 70%, rgba(45,143,122,0.12), transparent 26%);
  border: 1px solid rgba(26,107,90,0.08);
  box-shadow: inset 0 0 0 1px rgba(255,255,255,0.6);
}
.home-visual-grid {
  position: relative;
  z-index: 1;
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 0.9rem;
  height: 100%;
}
.home-visual-panel {
  min-height: 118px;
  padding: 0.95rem;
  border-radius: 18px;
  background: rgba(255,255,255,0.72);
  border: 1px solid rgba(26,107,90,0.10);
  backdrop-filter: blur(6px);
}
.home-visual-label {
  display: block;
  color: var(--color-muted);
  font-size: 11px;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  margin-bottom: 0.45rem;
}
.home-visual-value {
  color: var(--color-primary-dark);
  font-size: 22px;
  font-weight: 800;
  line-height: 1.15;
}
.home-visual-caption {
  margin-top: 0.5rem;
  color: var(--color-muted);
  font-size: 12px;
  line-height: 1.6;
}
.home-section-title {
  margin: 0.25rem 0 0.35rem;
  color: var(--color-primary-dark);
  font-size: 20px;
  font-weight: 900;
  letter-spacing: -0.02em;
}
.home-section-note {
  margin: 0 0 0.95rem;
  color: var(--color-muted);
  font-size: 14px;
  line-height: 1.75;
}
.home-focus-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 16px;
  margin-bottom: 1rem;
}
.home-focus-card {
  padding: 1.15rem 1.1rem 1rem;
}
.home-focus-index {
  color: rgba(26,107,90,0.32);
  font-size: 12px;
  font-weight: 800;
  letter-spacing: 0.12em;
  text-transform: uppercase;
}
.home-focus-title {
  margin: 0.45rem 0 0.55rem;
  color: var(--color-primary-dark);
  font-size: 19px;
  font-weight: 800;
}
.home-focus-body {
  margin: 0;
  color: var(--color-muted);
  font-size: 14px;
  line-height: 1.72;
}
.home-focus-emphasis {
  margin-top: 0.9rem;
  padding-top: 0.75rem;
  border-top: 1px solid rgba(26,107,90,0.08);
  color: var(--color-primary-dark);
  font-size: 12px;
  font-weight: 700;
  line-height: 1.6;
}
.assistant-drag-handle {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 34px;
  height: 16px;
  border-radius: 10px;
  background: rgba(26,107,90,0.10);
  color: var(--color-primary-dark);
}
.assistant-drag-handle {
  cursor: grab;
  user-select: none;
  margin: 0.15rem 0 0.25rem;
  touch-action: none;
}
.assistant-drag-handle::before {
  content: "";
  width: 18px;
  height: 2px;
  border-radius: 999px;
  background: currentColor;
  box-shadow: 0 5px 0 currentColor;
  opacity: 0.78;
}
.assistant-drag-handle:active { cursor: grabbing; }
.smart-assistant-avatar {
  width: 58px;
  height: 58px;
  border-radius: 18px;
  background:
    radial-gradient(circle at 35% 30%, rgba(255,255,255,0.95), transparent 24%),
    linear-gradient(135deg, #1a6b5a, #235d7f);
  box-shadow: 0 10px 24px rgba(18,52,45,0.16);
  border: 1px solid rgba(255,255,255,0.72);
}
.assistant-icon-button {
  position: absolute;
  inset: 0;
  border-radius: 24px;
  pointer-events: none;
}
.assistant-bubble-avatar {
  position: absolute;
  inset: 3px;
  width: 68px;
  height: 68px;
  object-fit: contain;
  border-radius: 24px;
  background: transparent;
  box-shadow: 0 14px 32px rgba(18,52,45,0.20);
  pointer-events: none;
}
.st-key-assistant_bubble_container {
  position: fixed !important;
  right: 18px;
  bottom: 18px;
  width: 74px !important;
  height: 74px !important;
  z-index: 9998;
}
.st-key-assistant_bubble_container [data-testid="stImage"] {
  margin: 0 !important;
  background: transparent !important;
}
.st-key-assistant_bubble_container [data-testid="stImage"] img {
  width: 68px !important;
  height: 68px !important;
  object-fit: contain;
  border-radius: 24px;
  border: none !important;
  background: transparent !important;
  box-shadow: 0 14px 32px rgba(18,52,45,0.20);
}
.st-key-assistant_bubble_container [data-testid="stButton"] {
  position: absolute;
  inset: 0;
  width: 74px !important;
  height: 74px !important;
  z-index: 2;
}
.st-key-assistant_bubble_container button,
.st-key-assistant_bubble_container [data-testid^="stBaseButton"],
.st-key-assistant-bubble-container button,
.st-key-assistant-bubble-container [data-testid^="stBaseButton"] {
  width: 74px !important;
  height: 74px !important;
  min-height: 74px !important;
  border-radius: 24px !important;
  background: transparent !important;
  background-color: transparent !important;
  color: transparent !important;
  border: none !important;
  box-shadow: none !important;
  font-size: 0 !important;
  padding: 0 !important;
  margin: 0 !important;
}
.st-key-assistant_bubble_container button *,
.st-key-assistant_bubble_container [data-testid^="stBaseButton"] *,
.st-key-assistant-bubble-container button *,
.st-key-assistant-bubble-container [data-testid^="stBaseButton"] * {
  background: transparent !important;
  color: transparent !important;
  border: none !important;
  box-shadow: none !important;
}
.st-key-assistant_bubble_container button:hover,
.st-key-assistant_bubble_container button:focus,
.st-key-assistant-bubble-container button:hover,
.st-key-assistant-bubble-container button:focus {
  background: transparent !important;
  outline: none !important;
}
.st-key-assistant_panel_container {
  position: fixed !important;
  right: 18px;
  bottom: 18px;
  width: min(330px, calc(100vw - 28px)) !important;
  max-height: min(52vh, 460px);
  overflow: auto;
  z-index: 9998;
  padding: 0.7rem;
  border: 1px solid rgba(26,107,90,0.18);
  border-radius: 22px;
  background: rgba(255,252,246,0.98);
  box-shadow: var(--shadow-md);
}
.st-key-assistant_panel_container [data-testid="stVerticalBlockBorderWrapper"] {
  border: 0 !important;
  box-shadow: none !important;
  background: transparent !important;
}
.st-key-assistant_panel_container [data-testid="stImage"],
.st-key-assistant_panel_container [data-testid="stImage"] img {
  background: transparent !important;
  border: none !important;
}

@media (max-width: 640px) {
  .home-hero,
  .home-focus-grid {
    grid-template-columns: 1fr;
  }

  .st-key-assistant_bubble_container,
  .st-key-assistant_panel_container {
    right: 12px;
    bottom: 12px;
  }

  .st-key-assistant_panel_container {
    width: calc(100vw - 24px) !important;
    max-height: 58vh;
  }
}

</style>
"""


def init_css():
    st.markdown(CUSTOM_CSS, unsafe_allow_html=True)


# ============================================================
# 宸ヤ綔娴侀樁娈靛畾涔?
# ============================================================
STAGES = {
    "idle":              {"name": "\u7b49\u5f85\u6570\u636e",  "icon": "\U0001f4c4", "order": 0},
    "data_loaded":       {"name": "\u6570\u636e\u5df2\u52a0\u8f7d", "icon": "\U0001f4e5", "order": 1},
    "quality_assessed":  {"name": "\u8d28\u91cf\u8bc4\u4f30",  "icon": "\U0001f50d", "order": 2},
    "features_built":    {"name": "\u7279\u5f81\u6784\u5efa",  "icon": "\U0001f3d7\ufe0f", "order": 3},
    "models_trained":    {"name": "\u6a21\u578b\u8bad\u7ec3",  "icon": "\U0001f916", "order": 4},
    "models_optimized":  {"name": "\u8d85\u53c2\u4f18\u5316",  "icon": "\u2699\ufe0f", "order": 4.5},
    "explained":         {"name": "\u89e3\u91ca\u5206\u6790",  "icon": "\U0001f9ed", "order": 5},
    "predicted":         {"name": "\u672a\u6765\u9884\u6d4b",  "icon": "\U0001f52e", "order": 6},
    "visualized":        {"name": "\u7a7a\u95f4\u8868\u8fbe",  "icon": "\U0001f5fa\ufe0f", "order": 7},
    "reported":          {"name": "\u8bc1\u636e\u5bfc\u51fa",  "icon": "\U0001f4dd", "order": 8},
}


# ============================================================
# 浼氳瘽鐘舵€佸垵濮嬪寲
# ============================================================
def init_session_state():
    defaults = {
        "messages": [],
        "uploads": {},
        "_upload_inspection": None,
        "feature_table": None,
        "models": {},
        "best_model": None,
        "model_param_overrides": {},
        "predictions": None,
        "_diagnostics": {},
        "_quality_report": None,
        "_optimization_result": None,
        "run_context": None,
        "_explanation_meta": {},
        "workflow_stage": "idle",
        "pending_action": None,
        "active_viz": None,
        "current_layer": "home",
        "layer_last_view": {},
        "layer_snapshots": {},
        "assistant_open": False,
        "global_state": None,
        "_rerun_requested": False,
        "_last_qa_action": "",
        "_last_feature_build_error": None,
    }
    for key, default in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = default
    if not st.session_state.get("global_state"):
        st.session_state["global_state"] = build_global_state()
    _maybe_seed_qa_state()


def _write_tiny_png(path: str):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as f:
        f.write(base64.b64decode(
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/p9sAAAAASUVORK5CYII="
        ))


def _safe_upload_name(raw_name: Any) -> str:
    name = str(raw_name or "").replace("\\", "/")
    base = os.path.basename(name).strip()
    if base in {"", ".", ".."}:
        base = f"upload_{int(time.time())}.dat"
    safe = []
    for ch in base:
        if ch.isalnum() or ch in {".", "_", "-"}:
            safe.append(ch)
        else:
            safe.append("_")
    sanitized = "".join(safe).strip("._")
    return sanitized or f"upload_{int(time.time())}.dat"


def _invalidate_downstream_state_after_upload():
    for key, value in {
        "feature_table": None,
        "models": {},
        "best_model": None,
        "predictions": None,
        "_diagnostics": {},
        "_quality_report": None,
        "_optimization_result": None,
        "_explanation_meta": {},
        "run_context": None,
        "_upload_inventory": None,
    }.items():
        st.session_state[key] = value
    st.session_state["workflow_stage"] = "data_loaded"


def _maybe_seed_qa_state():
    """Seed deterministic UI state only for browser QA; never for normal users."""
    if os.environ.get("WATER_EROSION_UI_QA_SEED") != "1":
        return
    if st.session_state.get("_qa_seeded"):
        return

    seed_root = os.path.join(os.path.dirname(__file__), "data", "runs", "_ui_live_qa_seed")
    explanation_path = os.path.join(seed_root, "explanations", "summary.png")
    spatial_path = os.path.join(seed_root, "spatial", "dominant_factor.png")
    pred_path = os.path.join(seed_root, "predictions", "ssp245.tif")
    report_path = os.path.join(seed_root, "reports", "report.md")
    bundle_path = os.path.join(seed_root, "bundle", "results.zip")
    method_note = os.path.join(seed_root, "reports", "method_note.md")
    reproduce_note = os.path.join(seed_root, "reports", "reproduce.md")

    _write_tiny_png(explanation_path)
    _write_tiny_png(spatial_path)
    os.makedirs(os.path.dirname(pred_path), exist_ok=True)
    os.makedirs(os.path.dirname(report_path), exist_ok=True)
    os.makedirs(os.path.dirname(bundle_path), exist_ok=True)
    seed_input_path = os.path.join(seed_root, "inputs", "R_2024.tif")
    os.makedirs(os.path.dirname(seed_input_path), exist_ok=True)
    if not os.path.exists(seed_input_path) or os.path.getsize(seed_input_path) == 0:
        seed_arr = np.array([[12.0, 13.0], [14.0, 15.0]], dtype=np.float32)
        with rasterio.open(
            seed_input_path,
            "w",
            driver="GTiff",
            height=seed_arr.shape[0],
            width=seed_arr.shape[1],
            count=1,
            dtype="float32",
            crs="EPSG:4326",
            transform=from_origin(126.0, 48.0, 0.01, 0.01),
            nodata=-9999.0,
        ) as dst:
            dst.write(seed_arr, 1)
    if not os.path.exists(pred_path) or os.path.getsize(pred_path) == 0:
        with open(pred_path, "wb") as f:
            f.write(b"UI_QA_ONLY_NOT_RESEARCH_OUTPUT")
    for note_path, text in [
        (report_path, "# UI QA report\n\nThis file is generated only for interface testing.\n"),
        (method_note, "# UI QA method note\n\nNot a scientific method record.\n"),
        (reproduce_note, "# UI QA reproduce note\n\nNot a reproducibility claim.\n"),
    ]:
        if not os.path.exists(note_path):
            with open(note_path, "w", encoding="utf-8") as f:
                f.write(text)
    if not os.path.exists(bundle_path):
        with open(bundle_path, "wb") as f:
            f.write(b"UI_QA_ONLY_NOT_RESEARCH_BUNDLE")

    st.session_state["uploads"] = {
        "R_2024.tif": {
            "filepath": seed_input_path,
            "size": os.path.getsize(seed_input_path),
            "uploaded_at": _now_iso(),
        }
    }
    st.session_state["_quality_report"] = {
        "status": "ok",
        "gate_verdict": "PASS",
        "overall_quality": "good",
        "qa_notice": "UI_QA_ONLY_NOT_RESEARCH_RESULT",
    }
    st.session_state["feature_table"] = {
        "path": os.path.join(seed_root, "features", "feature_table.parquet"),
        "n_samples": 90,
        "n_features": 5,
        "qa_notice": "UI_QA_ONLY_NOT_RESEARCH_RESULT",
    }
    st.session_state["best_model"] = "random_forest"
    st.session_state["models"] = {
        "random_forest": {
            "metrics": {
                "mae": 1.2,
                "rmse": 2.3,
                "r2": 0.82,
                "nrmse": 8.1,
                "pbias": -1.4,
                "train_seconds": 0.5,
            },
            "qa_notice": "UI_QA_ONLY_NOT_RESEARCH_RESULT",
        }
    }
    st.session_state["_explanation_meta"] = {
        "explanation_mode": "SHAP",
        "geoshapley_status": "not_configured",
        "explanation_files": [explanation_path],
        "spatial_files": [spatial_path],
        "qa_notice": "UI_QA_ONLY_NOT_RESEARCH_RESULT",
    }
    st.session_state["predictions"] = {
        "scenario": "ssp245",
        "mean_erosion": 12.5,
        "max_erosion": 41.2,
        "high_risk_ratio": 0.18,
        "pred_path": pred_path,
        "qa_notice": "UI_QA_ONLY_NOT_RESEARCH_RESULT",
    }
    st.session_state["run_context"] = {
        "run_id": "ui_live_qa_seed",
        "report_path": report_path,
        "bundle_zip": bundle_path,
        "method_note": method_note,
        "reproduce_note": reproduce_note,
        "evidence_paths": [report_path, method_note, reproduce_note],
    }
    st.session_state["workflow_stage"] = "reported"
    st.session_state["_qa_seeded"] = True
    sync_global_state()


def handle_uploaded_files(uploaded_files) -> int:
    upload_dir = os.path.join(os.path.dirname(__file__), "data", "uploads")
    os.makedirs(upload_dir, exist_ok=True)
    upload_root = os.path.realpath(upload_dir)
    accepted = 0
    now = _now_iso() if "_now_iso" in globals() else datetime.now().isoformat(timespec="seconds")

    for uploaded in uploaded_files or []:
        if uploaded is None or not getattr(uploaded, "name", None):
            continue
        safe_name = _safe_upload_name(uploaded.name)
        target = os.path.join(upload_dir, safe_name)
        stem, ext = os.path.splitext(safe_name)
        idx = 1
        while os.path.exists(target):
            target = os.path.join(upload_dir, f"{stem}_{idx}{ext}")
            idx += 1
        target = os.path.realpath(target)
        if os.path.commonpath([target, upload_root]) != upload_root:
            continue
        file_bytes = uploaded.getbuffer()
        with open(target, "wb") as f:
            f.write(file_bytes)
        if accepted == 0:
            _invalidate_downstream_state_after_upload()
        stored_name = os.path.basename(target)
        st.session_state["uploads"][stored_name] = {
            "filepath": target,
            "size": int(getattr(uploaded, "size", len(file_bytes))),
            "uploaded_at": now,
            "original_name": str(uploaded.name),
        }
        accepted += 1
    return accepted


def get_upload_status() -> dict:
    from tools import parse_filename

    uploads = st.session_state.get("uploads") or {}
    status = {
        "total": len(uploads),
        "recognized": 0,
        "variables": set(),
        "years": set(),
        "scenarios": set(),
    }

    for name in uploads:
        parsed = parse_filename(name) or {}
        if not parsed:
            continue
        status["recognized"] += 1
        if parsed.get("variable"):
            status["variables"].add(str(parsed["variable"]))
        if parsed.get("year") not in {None, ""}:
            status["years"].add(parsed["year"])
        if parsed.get("scenario"):
            status["scenarios"].add(str(parsed["scenario"]))

    return status


def _current_state_snapshot() -> dict:
    return {
        "uploads": dict(st.session_state.get("uploads") or {}),
        "feature_table": st.session_state.get("feature_table"),
        "models": st.session_state.get("models") or {},
        "best_model": st.session_state.get("best_model"),
        "predictions": st.session_state.get("predictions"),
        "_diagnostics": st.session_state.get("_diagnostics") or {},
        "_quality_report": st.session_state.get("_quality_report"),
        "_optimization_result": st.session_state.get("_optimization_result"),
        "_upload_inspection": st.session_state.get("_upload_inspection"),
        "run_context": st.session_state.get("run_context"),
        "_explanation_meta": st.session_state.get("_explanation_meta") or {},
        "workflow_stage": st.session_state.get("workflow_stage", "idle"),
    }


def sync_state_back(state: dict):
    for key in [
        "uploads",
        "feature_table",
        "models",
        "best_model",
        "predictions",
        "_diagnostics",
        "_quality_report",
        "_optimization_result",
        "_upload_inspection",
        "run_context",
        "_explanation_meta",
        "workflow_stage",
    ]:
        if key in state:
            st.session_state[key] = state[key]


def _clear_modeling_outputs_after_feature_failure():
    """Prevent stale downstream outputs from masquerading as results for a failed build."""
    for key, value in {
        "feature_table": None,
        "models": {},
        "best_model": None,
        "predictions": None,
        "_optimization_result": None,
        "_explanation_meta": {},
    }.items():
        st.session_state[key] = value


def _tool_images_and_maps(tool_result: dict) -> tuple[list, list]:
    images = []
    maps = []
    if tool_result.get("image_base64"):
        images.append(tool_result["image_base64"])
    if tool_result.get("residual_image_base64"):
        images.append(tool_result["residual_image_base64"])
    if tool_result.get("folium_html"):
        maps.append((tool_result.get("target", "map"), tool_result["folium_html"]))
    return images, maps


def _session_agent():
    from agent import Agent

    key = "_smart_assistant_agent"
    if key not in st.session_state:
        st.session_state[key] = Agent()
    return st.session_state[key]


_ASSISTANT_RESPOND_EXECUTOR = ThreadPoolExecutor(max_workers=2)


def _assistant_fallback_response(user_text: str, reason: str) -> str:
    try:
        agent = _session_agent()
        if hasattr(agent, "_deterministic_response"):
            return agent._deterministic_response(user_text, _current_state_snapshot(), reason)
    except Exception:
        pass
    return f"智能小助手：我已收到你的问题：{_sanitize_dialogue_text(user_text)}\n当前助手推理暂时不可用：{reason}"


def _assistant_respond_with_timeout(user_text: str, timeout_seconds: float = 8.0) -> dict:
    future = _ASSISTANT_RESPOND_EXECUTOR.submit(_session_agent().respond, user_text, _current_state_snapshot())
    try:
        return future.result(timeout=timeout_seconds)
    except FuturesTimeoutError:

        future.cancel()
        return {"text": _assistant_fallback_response(user_text, "助手响应超时，已切换为本地兜底响应。"), "error": None}


def execute_tool_and_analyze(tool_name: str, state: dict, tool_kwargs: Optional[dict] = None, analysis_stage: Optional[str] = None) -> dict:
    import tools

    tool_kwargs = tool_kwargs or {}
    tool_fn = getattr(tools, tool_name)
    tool_result = tool_fn(state, **tool_kwargs)
    analysis = _session_agent().analyze(analysis_stage or st.session_state.get("workflow_stage", "idle"), tool_name, tool_result, state=state)
    images, maps = _tool_images_and_maps(tool_result)
    return {
        "tool_result": tool_result,
        "analysis": analysis,
        "images": images,
        "maps": maps,
    }


def _sanitize_dialogue_text(value: Any) -> str:
    text = str(value or "")
    if not text:
        return ""
    text = re.sub(r"sk-[A-Za-z0-9_-]{10,}", "[REDACTED_SECRET]", text)
    key_name_pattern = r"(?:OPENAI|LLM)_" + r"API" + r"_KEY"
    text = re.sub(rf"(?i)\b({key_name_pattern})\s*=\s*[^\s,;，；]+", r"\1=[REDACTED_SECRET]", text)
    text = re.sub(r"[A-Za-z]:\\[^\s,，。；;]+", "[REDACTED_PATH]", text)
    text = re.sub(r"(?<!\w)/(Users|home|mnt|var|tmp)/[^\s,，。；;]+", "[REDACTED_PATH]", text)
    return text


def _push_assistant_message(content: str, metadata: Optional[dict] = None):
    st.session_state.messages.append({
        "role": "assistant",
        "content": _sanitize_dialogue_text(content),
        "metadata": metadata or {},
    })


def _update_stage_after_action(action: str, tool_result: Optional[dict] = None):
    if action == "load_inputs":
        st.session_state.workflow_stage = "data_loaded"
    elif action == "assess_quality" and tool_result and tool_result.get("status") == "ok":
        st.session_state.workflow_stage = "quality_assessed"
    elif action == "build_features" and tool_result and tool_result.get("status") == "ok":
        st.session_state.workflow_stage = "features_built"
    elif action == "train_models" and tool_result and tool_result.get("status") == "ok":
        st.session_state.workflow_stage = "models_trained"
    elif action == "optimize_models" and tool_result and tool_result.get("status") == "ok":
        st.session_state.workflow_stage = "models_optimized"
    elif action == "generate_explanations" and tool_result and tool_result.get("status") == "ok":
        st.session_state.workflow_stage = "explained"
    elif action == "predict" and tool_result and tool_result.get("status") == "ok":
        st.session_state.workflow_stage = "predicted"
    elif action == "show_map" and tool_result and tool_result.get("status") == "ok":
        st.session_state.workflow_stage = "visualized"
    elif action == "show_uncertainty" and tool_result and tool_result.get("status") == "ok":
        st.session_state.workflow_stage = "visualized"
    elif action in {"generate_report", "export_bundle"} and tool_result and tool_result.get("status") == "ok":
        st.session_state.workflow_stage = "reported"


def _find_latest_message_media(kind: str, title_hint: str = ""):
    hint = (title_hint or "").lower()
    for msg in reversed(st.session_state.get("messages", [])):
        metadata = msg.get("metadata") or {}
        items = metadata.get(kind, []) or []
        if not hint:
            if items:
                return items
            continue
        matched = []
        for item in items:
            if not isinstance(item, (list, tuple)) or not item:
                continue
            title = str(item[0]).lower()
            if hint in title:
                matched.append(item)
        if matched:
            return matched
    return []


LAYER_SEQUENCE = [
    ("home", "\u9996\u9875"),
    ("dataWorkshop", "\u6570\u636e\u5904\u7406"),
    ("modelingLab", "\u6a21\u578b\u6784\u5efa"),
    ("explainStudio", "\u7ed3\u679c\u89e3\u91ca"),
    ("predictExport", "\u9884\u6d4b\u5bfc\u51fa"),
]


LAYER_TITLES = dict(LAYER_SEQUENCE)


LAYER_DESCRIPTIONS = {
    "dataWorkshop": "\u4e0a\u4f20\u3001\u8bc6\u522b\u3001\u68c0\u67e5\u6570\u636e\uff0c\u5e76\u5f62\u6210\u6570\u636e\u6e05\u5355\u3002",
    "modelingLab": "\u6784\u5efa\u5efa\u6a21\u6570\u636e\uff0c\u5b8c\u6210\u9ed8\u8ba4\u8bad\u7ec3\u3001\u53c2\u6570\u4f18\u5316\u4e0e\u91cd\u65b0\u8bad\u7ec3\u3002",
    "explainStudio": "\u67e5\u770b SHAP \u503c\u5206\u5e03\u3001\u7a7a\u95f4\u70ed\u529b\u56fe\u548c\u56e0\u5b50\u91cd\u8981\u6027\u3002",
    "predictExport": "\u914d\u7f6e\u9884\u6d4b\u60c5\u666f\uff0c\u751f\u6210\u5730\u56fe\u5e76\u5bfc\u51fa\u7ed3\u679c\u3002",
}


LAYER_BLOCK_STYLE = {
    "dataWorkshop": "none",
    "modelingLab": "none",
    "explainStudio": "hard",
    "predictExport": "hard",
}


LAYER_VIEW_WIDGETS = {
    "dataWorkshop": "data_workshop_view",
    "modelingLab": "modeling_lab_view",
    "explainStudio": "explain_studio_view",
    "predictExport": "predict_export_view",
}


def _now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _make_project_meta(status: dict) -> dict:
    return {
        "id": "local_streamlit_project",
        "name": "当前本地项目",
        "createdAt": st.session_state.get("_project_created_at", _now_iso()),
        "dataSummary": {
            "file_count": status["total"],
            "recognized_count": status["recognized"],
            "variables": sorted(status["variables"]),
            "years": sorted(status["years"]),
            "scenarios": sorted(status["scenarios"]),
        },
    }


def _quality_gate_passed(quality: dict) -> bool:
    if not quality:
        return False
    verdict = str(quality.get("gate_verdict", "")).upper()
    overall = str(quality.get("overall_quality", "")).lower()
    return verdict in {"PASS", "PASS_WITH_RISKS"} or overall in {"excellent", "good"}


def _model_locked(models: dict, best_model: Any) -> bool:
    return bool(models and best_model)


def _explanations_ready(explanation_meta: dict) -> bool:
    return bool(
        explanation_meta
        and (
            explanation_meta.get("explanation_files")
            or explanation_meta.get("spatial_files")
        )
    )


def _predictions_ready(predictions: dict) -> bool:
    return bool(predictions and predictions.get("pred_path"))


def build_global_state() -> dict:
    status = get_upload_status()
    quality = st.session_state.get("_quality_report") or {}
    feature_table = st.session_state.get("feature_table") or {}
    models = st.session_state.get("models") or {}
    best_model = st.session_state.get("best_model")
    explanation_meta = st.session_state.get("_explanation_meta") or {}
    predictions = st.session_state.get("predictions") or {}
    run_context = st.session_state.get("run_context") or {}

    data_passed = _quality_gate_passed(quality)
    locked = _model_locked(models, best_model)
    explained = _explanations_ready(explanation_meta)
    predicted = _predictions_ready(predictions)

    current_layer = st.session_state.get("current_layer", "home")
    history = st.session_state.get("layer_snapshots", {})
    project_meta = _make_project_meta(status)
    st.session_state["_project_created_at"] = project_meta["createdAt"]

    return {
        "project": project_meta,
        "current_layer": current_layer,
        "layers": {
            "dataWorkshop": {
                "status": "completed" if data_passed else ("active" if status["total"] else "idle"),
                "upload": {
                    "files": [
                        {
                            "name": name,
                            "path": info.get("filepath"),
                            "size": info.get("size"),
                            "uploaded_at": info.get("uploaded_at"),
                        }
                        for name, info in sorted((st.session_state.get("uploads") or {}).items())
                    ],
                },
                "qualityCheck": {
                    "status": "passed" if data_passed else ("running" if quality else "pending"),
                    "reports": quality,
                    "gatePassed": data_passed,
                },
                "archive": {
                    "variables": sorted(status["variables"]),
                    "years": sorted(status["years"]),
                    "scenarios": sorted(status["scenarios"]),
                },
                "ui": {
                    "activeTab": st.session_state.get("layer_last_view", {}).get("dataWorkshop", "上传"),
                },
            },
            "modelingLab": {
                "status": "completed" if locked else ("active" if feature_table else "idle"),
                "input": {
                    "featureTableRef": feature_table.get("path"),
                    "featureTableStatus": "ready" if feature_table else "missing",
                },
                "training": {
                    "gatePassed": data_passed,
                    "candidates": list(models.keys()),
                    "lockedModel": best_model,
                },
                "artifacts": {
                    "metrics": models,
                },
                "ui": {
                    "activeTab": st.session_state.get("layer_last_view", {}).get("modelingLab", "建模数据"),
                },
            },
            "explainStudio": {
                "status": "completed" if explained else ("active" if locked else "idle"),
                "prerequisite": {
                    "required": "lockedModel",
                    "satisfied": locked,
                    "ref": best_model,
                },
                "explanations": explanation_meta,
                "ui": {
                    "activeTab": st.session_state.get("layer_last_view", {}).get("explainStudio", "总览"),
                },
            },
            "predictExport": {
                "status": "completed" if predicted else ("active" if locked else "idle"),
                "prerequisites": {
                    "model": {"satisfied": locked, "ref": best_model},
                    "explain": {"satisfied": explained, "ref": explanation_meta.get("run_id")},
                },
                "prediction": predictions,
                "export": {
                    "bundle_path": run_context.get("bundle_zip") or run_context.get("bundle_path"),
                    "report_path": run_context.get("report_path"),
                    "evidence_paths": run_context.get("evidence_paths", []),
                },
                "ui": {
                    "activeTab": st.session_state.get("layer_last_view", {}).get("predictExport", "预测"),
                },
            },
        },
        "shared_artifacts": {
            "feature_table": feature_table,
            "best_model": best_model,
            "explanations": explanation_meta,
            "predictions": predictions,
            "run_context": run_context,
        },
        "ai": {
            "assistant_open": bool(st.session_state.get("assistant_open")),
            "context": {
                "currentLayer": current_layer,
                "currentStep": st.session_state.get("workflow_stage", "idle"),
            },
        },
        "history": history,
        "version": "2.0.0",
        "last_saved": _now_iso(),
    }


def sync_global_state(snapshot_reason: str = ""):
    global_state = build_global_state()
    st.session_state["global_state"] = global_state
    st.session_state["current_layer"] = global_state["current_layer"]
    if snapshot_reason:
        st.session_state["layer_snapshots"][snapshot_reason] = {
            "ts": _now_iso(),
            "reason": snapshot_reason,
            "current_layer": global_state["current_layer"],
            "workflow_stage": st.session_state.get("workflow_stage"),
            "available_layers": list(global_state["layers"].keys()),
            "layer_last_view": dict(st.session_state.get("layer_last_view") or {}),
            "assistant_open": bool(st.session_state.get("assistant_open")),
            "artifact_state": {
                "uploads": copy.deepcopy(st.session_state.get("uploads") or {}),
                "feature_table": copy.deepcopy(st.session_state.get("feature_table")),
                "models": copy.deepcopy(st.session_state.get("models") or {}),
                "best_model": st.session_state.get("best_model"),
                "predictions": copy.deepcopy(st.session_state.get("predictions")),
                "_diagnostics": copy.deepcopy(st.session_state.get("_diagnostics") or {}),
                "_quality_report": copy.deepcopy(st.session_state.get("_quality_report")),
                "_optimization_result": copy.deepcopy(st.session_state.get("_optimization_result")),
                "_upload_inspection": copy.deepcopy(st.session_state.get("_upload_inspection")),
                "run_context": copy.deepcopy(st.session_state.get("run_context")),
                "_explanation_meta": copy.deepcopy(st.session_state.get("_explanation_meta") or {}),
                "active_viz": copy.deepcopy(st.session_state.get("active_viz")),
            },
            "recoveryPoint": {
                "layer": global_state["current_layer"],
                "step": st.session_state.get("workflow_stage"),
                "availableActions": [
                    _next_recommended_action().get("action"),
                ],
            },
        }


def _sorted_snapshot_items() -> list[tuple[str, dict]]:
    snapshots = st.session_state.get("layer_snapshots") or {}
    return sorted(
        snapshots.items(),
        key=lambda item: item[1].get("ts", ""),
        reverse=True,
    )


def _apply_layer_view_state():
    layer_last_view = st.session_state.get("layer_last_view") or {}
    for layer_id, widget_key in LAYER_VIEW_WIDGETS.items():
        if layer_id in layer_last_view:
            st.session_state[widget_key] = layer_last_view[layer_id]


def _restore_snapshot(snapshot_key: str):
    snap = (st.session_state.get("layer_snapshots") or {}).get(snapshot_key)
    if not snap:
        return
    st.session_state["current_layer"] = snap.get("current_layer", "home")
    st.session_state["workflow_stage"] = snap.get("workflow_stage", st.session_state.get("workflow_stage", "idle"))
    st.session_state["layer_last_view"] = dict(snap.get("layer_last_view") or {})
    st.session_state["assistant_open"] = bool(snap.get("assistant_open"))
    artifact_state = snap.get("artifact_state") or {}
    for key in [
        "uploads",
        "feature_table",
        "models",
        "best_model",
        "predictions",
        "_diagnostics",
        "_quality_report",
        "_optimization_result",
        "_upload_inspection",
        "run_context",
        "_explanation_meta",
        "active_viz",
    ]:
        if key in artifact_state:
            st.session_state[key] = copy.deepcopy(artifact_state.get(key))
    _apply_layer_view_state()
    sync_global_state()


def _snapshot_reason_for_stage(stage: str) -> str:
    mapping = {
        "quality_assessed": "quality_passed",
        "features_built": "feature_table_ready",
        "models_trained": "model_locked",
        "models_optimized": "model_locked",
        "explained": "explanations_ready",
        "predicted": "prediction_completed",
        "reported": "export_completed",
    }
    return mapping.get(stage, "")


def set_current_layer(layer_id: str):
    if layer_id not in {item[0] for item in LAYER_SEQUENCE}:
        layer_id = "home"
    st.session_state["current_layer"] = layer_id
    sync_global_state()


def record_platform_open_heartbeat(interval_hours: int = 12):
    """Record platform-open heartbeat at most once per interval."""
    log_dir = os.path.join(os.path.dirname(__file__), "Workflow-Logs")
    os.makedirs(log_dir, exist_ok=True)
    log_path = os.path.join(log_dir, "platform_open_heartbeat.jsonl")
    now_ts = time.time()
    due = True

    if os.path.exists(log_path):
        age_seconds = now_ts - os.path.getmtime(log_path)
        due = age_seconds >= interval_hours * 3600

    if not due:
        st.session_state["_platform_heartbeat_path"] = log_path
        return

    payload = {
        "ts": datetime.now().isoformat(timespec="seconds"),
        "event": "platform_open_heartbeat",
        "interval_hours": int(interval_hours),
        "app": "water_erosion_mvp",
        "cwd": os.getcwd(),
    }
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(payload, ensure_ascii=False) + "\n")
    st.session_state["_platform_heartbeat_path"] = log_path


def _existing_paths(paths: list) -> list:
    return [p for p in paths if isinstance(p, str) and os.path.exists(p)]


def _render_empty_state(text: str):
    st.info(text)


def _fmt_metric(value: Any, digits: int = 4) -> str:
    try:
        if value is None or (isinstance(value, float) and not np.isfinite(value)):
            return "-"
        return f"{float(value):.{digits}f}"
    except Exception:
        return "-"


def _archive_rows() -> list:
    import tools

    result = tools.build_upload_inventory(_current_state_snapshot())
    st.session_state["_upload_inventory"] = result
    return result.get("rows", []) or []


def _layer_block_reason(layer_id: str) -> str:
    quality = st.session_state.get("_quality_report") or {}
    models = st.session_state.get("models") or {}
    best_model = st.session_state.get("best_model")
    explanation_meta = st.session_state.get("_explanation_meta") or {}

    if layer_id == "dataWorkshop":
        return ""
    if layer_id == "explainStudio" and not _model_locked(models, best_model):
        return "请先选定模型，再进入解释分析。"
    if layer_id == "predictExport" and not _model_locked(models, best_model):
        return "请先选定当前使用模型，再进入结果预测。"
    if layer_id == "predictExport" and not _explanations_ready(explanation_meta):
        return "解释结果尚未生成。基础预测可继续，但解释增强视图仍受限。"
    return ""


def _next_recommended_action() -> dict:
    quality = st.session_state.get("_quality_report") or {}
    feature_table = st.session_state.get("feature_table") or {}
    models = st.session_state.get("models") or {}
    explanation_meta = st.session_state.get("_explanation_meta") or {}
    predictions = st.session_state.get("predictions") or {}
    run_context = st.session_state.get("run_context") or {}

    if not st.session_state.get("uploads"):
        return {"label": "\u8fdb\u5165\u6570\u636e\u5904\u7406", "action": "open_layer:dataWorkshop", "desc": "\u5148\u4e0a\u4f20\u6216\u52a0\u8f7d\u6570\u636e\uff0c\u5b8c\u6210\u6587\u4ef6\u8bc6\u522b\u4e0e\u68c0\u67e5\u3002"}
    if not feature_table:
        return {"label": "\u6784\u5efa\u5efa\u6a21\u6570\u636e", "action": "build_features", "desc": "\u751f\u6210\u53ef\u7528\u4e8e\u6a21\u578b\u8bad\u7ec3\u7684\u6570\u636e\u3002"}
    if not models:
        return {"label": "\u5f00\u59cb\u8bad\u7ec3", "action": "train_models", "desc": "\u5148\u5b8c\u6210\u9ed8\u8ba4\u53c2\u6570\u8bad\u7ec3\uff0c\u5f62\u6210\u521d\u59cb\u8bc4\u4f30\u7ed3\u679c\u3002"}
    if not st.session_state.get("_optimization_result"):
        return {"label": "\u8d1d\u53f6\u65af\u4f18\u5316", "action": "optimize_models", "desc": "\u6267\u884c\u8d1d\u53f6\u65af\u53c2\u6570\u641c\u7d22\uff0c\u5e76\u7528\u4f18\u5316\u53c2\u6570\u91cd\u65b0\u8bad\u7ec3\u3002"}
    if not _explanations_ready(explanation_meta):
        return {"label": "\u751f\u6210\u89e3\u91ca\u7ed3\u679c", "action": "generate_explanations", "desc": "\u8f93\u51fa SHAP \u56fe\u4ef6\u4e0e\u7a7a\u95f4\u89e3\u91ca\u7ed3\u679c\u3002"}
    if not _predictions_ready(predictions):
        return {"label": "\u751f\u6210\u9884\u6d4b\u5730\u56fe", "action": "predict", "desc": "\u8fd0\u884c\u5f53\u524d\u60c5\u666f\u7684\u9884\u6d4b\u5e76\u751f\u6210\u5730\u56fe\u7ed3\u679c\u3002"}
    if not (run_context.get("bundle_zip") or run_context.get("bundle_path")):
        return {"label": "\u5bfc\u51fa\u7ed3\u679c", "action": "export_bundle", "desc": "\u5bfc\u51fa\u62a5\u544a\u3001\u5730\u56fe\u548c\u7ed3\u679c\u6587\u4ef6\u3002"}
    return {"label": "\u67e5\u770b\u9996\u9875", "action": "go_home", "desc": "\u56de\u5230\u9996\u9875\u67e5\u770b\u5168\u5c40\u72b6\u6001\u548c\u6700\u8fd1\u64cd\u4f5c\u3002"}


def _recent_timeline() -> list:
    events = []
    uploads = st.session_state.get("uploads") or {}
    if uploads:
        latest_upload = max((info.get("uploaded_at", "") for info in uploads.values()), default="")
        events.append({"ts": latest_upload, "label": "已接收上传文件"})

    snapshot_labels = {
        "quality_passed": "数据质量检查完成",
        "feature_table_ready": "建模数据构建完成",
        "model_locked": "模型训练并选用完成",
        "explanations_ready": "解释分析完成",
        "prediction_completed": "未来预测完成",
        "export_completed": "导出完成",
    }
    for key, snap in (st.session_state.get("layer_snapshots") or {}).items():
        events.append({"ts": snap.get("ts", ""), "label": snapshot_labels.get(key, key)})

    events = [item for item in events if item.get("label")]
    events.sort(key=lambda item: item.get("ts", ""), reverse=True)
    return events[:8]


def _layer_status_text(layer_id: str) -> str:
    global_state = st.session_state.get("global_state") or {}
    if layer_id == "home":
        return "总览"
    layer_state = (global_state.get("layers") or {}).get(layer_id, {})
    status = str(layer_state.get("status", "idle"))
    mapping = {
        "idle": "未开始",
        "active": "进行中",
        "completed": "已完成",
        "error": "异常",
    }
    return mapping.get(status, status)


def _layer_nav_meta(layer_id: str) -> dict:
    models = st.session_state.get("models") or {}
    best_model = st.session_state.get("best_model")
    feature_table = st.session_state.get("feature_table") or {}
    predictions = st.session_state.get("predictions") or {}
    if layer_id == "home":
        return {"label": "\u5f53\u524d", "state": "active"}
    if layer_id == "dataWorkshop":
        return {"label": "\u53ef\u8fdb\u5165", "state": "open"}
    if layer_id == "modelingLab":
        if models:
            return {"label": "\u5df2\u8fd0\u884c", "state": "done"}
        if feature_table:
            return {"label": "\u5df2\u5c31\u7eea", "state": "open"}
        return {"label": "\u53ef\u8fdb\u5165", "state": "open"}
    if layer_id == "explainStudio":
        ok = _model_locked(models, best_model)
        return {"label": "\u5df2\u5b8c\u6210" if ok else "\u5f85\u6a21\u578b", "state": "done" if ok else "locked"}
    if layer_id == "predictExport":
        ready = _predictions_ready(predictions)
        unlocked = _model_locked(models, best_model)
        return {"label": "\u5df2\u5b8c\u6210" if ready else ("\u53ef\u8fdb\u5165" if unlocked else "\u5f85\u6a21\u578b"), "state": "done" if ready else ("open" if unlocked else "locked")}
    return {"label": "\u53ef\u8fdb\u5165", "state": "open"}


def _render_page_header(title: str, subtitle: str, step: str = ""):
    chip = f'<span class="step-badge">{html.escape(step)}</span>' if step else ""
    st.markdown(f"""<div class="page-card">{chip}<h2 style="margin:0;color:var(--color-primary-dark);">{html.escape(title)}</h2><p style="margin:.45rem 0 0;color:var(--color-muted);line-height:1.75;">{html.escape(subtitle)}</p></div>""", unsafe_allow_html=True)


def _render_layer_entry_card(layer_id: str, title: str, description: str):
    block_reason = _layer_block_reason(layer_id)
    with st.container(border=True):
        st.markdown(f"### {title}")
        st.caption(description)
        st.write(f"\u5f53\u524d\u72b6\u6001\uff1a{_layer_status_text(layer_id)}")
        if block_reason:
            st.info(block_reason)
        st.button(f"\u8fdb\u5165{title}", key=f"enter_{layer_id}", width="stretch", on_click=_queue_action, args=(f"open_layer:{layer_id}",))


def _render_header_with_back(title: str, subtitle: str):
    _render_page_header(title, subtitle)


def _render_tiff_feature_help():
    with st.expander("TIFF 可提取特征说明", expanded=False):
        st.markdown("""
- **默认建模字段**：`grid_id`、`row`、`col`、`x`、`y`、`year`，以及可识别的数值因子列。
- **RUSLE 因子特征**：优先识别 `R`、`K`、`LS`、`C`、`P`；上传模式下至少需要能形成两个以上数值特征才适合训练。
- **训练目标**：监督建模必须提供 `label_YYYY.tif`。没有 `label` 时仍可进入模型构建页，但构建建模数据会返回明确缺失原因。
- **清单元数据**：数据清单导出会读取真实 TIFF 的 CRS、分辨率、宽高、nodata、有效像元比例、最小值、最大值、均值。
- **可选扩展**：坡度、坡向、曲率、NDVI、LST、局部均值、标准差、纹理等只在对应输入存在时扩展，不伪造。
""")


def _render_data_archive():
    rows = _archive_rows()
    if not rows:
        _render_empty_state("暂无可导出的上传文件。请先进入“数据处理 -> 上传数据”上传 GeoTIFF 或 CSV 文件。")
        return

    df = pd.DataFrame(rows)
    display_columns = [
        "file", "variable", "year", "scenario", "path", "size_bytes", "uploaded_at",
        "crs", "width", "height", "resolution_x", "resolution_y", "nodata",
        "valid_pixel_pct", "min", "max", "mean", "read_status", "error",
    ]
    for col in display_columns:
        if col not in df.columns:
            df[col] = None
    st.dataframe(df[display_columns], width="stretch", hide_index=True)
    csv_bytes = df[display_columns].to_csv(index=False).encode("utf-8-sig")
    st.download_button(
        "导出数据清单 CSV",
        data=csv_bytes,
        file_name="data_inventory.csv",
        mime="text/csv",
        key="download_data_inventory",
    )
    inventory = st.session_state.get("_upload_inventory") or {}
    st.caption(f"已生成 {inventory.get('total_files', len(rows))} 条清单记录；可读取 TIFF：{inventory.get('readable_rasters', 0)} 个。")


def _model_registry() -> dict:
    import tools

    return getattr(tools, "MODEL_REGISTRY", {})


def _model_display_name(algorithm: Any) -> str:
    registry = _model_registry()
    return registry.get(str(algorithm), {}).get("display_name", str(algorithm))


def _selected_training_algorithms() -> list[str]:
    registry = _model_registry()
    display_to_algo = {
        cfg.get("display_name", algo): algo
        for algo, cfg in registry.items()
    }
    chosen = st.session_state.get("model_algorithm_selection") or []
    resolved = [display_to_algo.get(item, item) for item in chosen]
    return [algo for algo in resolved if algo in registry]


def _manual_param_default(cfg: dict, pname: str, bound: Any):
    defaults = cfg.get("default_params", {}) or {}
    if pname in defaults:
        return defaults[pname]
    conditional = cfg.get("conditional_params", {}) or {}
    if pname in conditional and "default" in conditional[pname]:
        return conditional[pname]["default"]
    if isinstance(bound, list) and bound:
        return bound[0]
    if isinstance(bound, tuple) and bound:
        return bound[0]
    return ""


def _model_param_key(algo: str, pname: str) -> str:
    return f"model_param_{algo}_{pname}"


def _render_model_param_widget(algo: str, pname: str, value: Any, ptype: str, bound: Any):
    key = _model_param_key(algo, pname)
    label = pname
    if isinstance(value, bool):
        return st.checkbox(label, value=bool(value), key=key)
    if ptype == "categorical" or isinstance(bound, list):
        options = list(bound) if isinstance(bound, list) else [value]
        if value not in options:
            options.insert(0, value)
        return st.selectbox(label, options=options, index=options.index(value), key=key)
    if pname == "max_features" and isinstance(value, str):
        options = []
        for option in [value, "sqrt", "log2", "0.3", "0.5", "0.8", "1.0"]:
            if option not in options:
                options.append(option)
        return st.selectbox(label, options=options, index=options.index(value), key=key)
    if ptype == "int":
        number_value = int(value)
        kwargs = {"label": label, "value": number_value, "step": 1, "key": key}
        if isinstance(bound, tuple) and len(bound) == 2:
            kwargs["min_value"] = int(min(bound[0], number_value))
            kwargs["max_value"] = int(max(bound[1], number_value))
        return st.number_input(**kwargs)
    if ptype == "float":
        try:
            number_value = float(value)
        except (TypeError, ValueError):
            return st.text_input(label, value=str(value), key=key)
        kwargs = {"label": label, "value": number_value, "step": 0.01, "format": "%.6f", "key": key}
        if isinstance(bound, tuple) and len(bound) == 2:
            kwargs["min_value"] = float(min(bound[0], number_value))
            kwargs["max_value"] = float(max(bound[1], number_value))
        return st.number_input(**kwargs)
    return st.text_input(label, value=str(value), key=key)


def _render_model_hyperparameter_controls(registry: dict, selected_algorithms: list[str]):
    st.markdown("### 手动超参数")
    st.caption("按模型注册表展示可调整参数；默认训练会直接使用这里的当前取值。")
    if not selected_algorithms:
        _render_empty_state("请选择参与训练的模型后再调整超参数。")
        st.session_state["model_param_overrides"] = {}
        return

    focus_name = st.session_state.get("model_focus_selection")
    display_to_algo = {
        cfg.get("display_name", algo): algo
        for algo, cfg in registry.items()
    }
    focus_algo = display_to_algo.get(focus_name, "")
    overrides = dict(st.session_state.get("model_param_overrides") or {})
    next_overrides = {}

    for algo in selected_algorithms:
        cfg = registry.get(algo) or {}
        display = cfg.get("display_name", algo)
        defaults = cfg.get("default_params", {}) or {}
        bounds = cfg.get("bayes_opt_bounds", {}) or {}
        ptypes = cfg.get("param_types", {}) or {}
        param_names = list(defaults.keys()) + [name for name in bounds.keys() if name not in defaults]
        current = dict(overrides.get(algo) or {})
        with st.expander(f"{display} 手动超参数", expanded=algo == focus_algo):
            if not param_names:
                st.info("该模型暂无可编辑参数。")
                next_overrides[algo] = {}
                continue
            param_cols = st.columns(2)
            for idx, pname in enumerate(param_names):
                bound = bounds.get(pname)
                base_value = current.get(pname, _manual_param_default(cfg, pname, bound))
                with param_cols[idx % 2]:
                    current[pname] = _render_model_param_widget(algo, pname, base_value, ptypes.get(pname, ""), bound)
            next_overrides[algo] = current
    st.session_state["model_param_overrides"] = next_overrides


def _selected_model_param_overrides() -> dict:
    selected = set(_selected_training_algorithms())
    raw = st.session_state.get("model_param_overrides") or {}
    return {
        algo: params
        for algo, params in raw.items()
        if algo in selected and isinstance(params, dict)
    }


def _render_image_grid(paths: list[str], empty_message: str):
    real_paths = _existing_paths(paths)
    if not real_paths:
        _render_empty_state(empty_message)
        return

    grid = st.columns(2)
    for idx, path_item in enumerate(real_paths):
        with grid[idx % 2]:
            st.caption(os.path.basename(path_item))
            st.image(path_item, width="stretch")


def _model_metric_rows() -> list[dict]:
    models = st.session_state.get("models") or {}
    best_model = st.session_state.get("best_model")
    rows = []
    for algo, info in models.items():
        metrics = info.get("metrics", {}) or {}
        rows.append({
            "algorithm": algo,
            "模型": _model_display_name(algo),
            "当前使用": "是" if algo == best_model else "",
            "mae": metrics.get("mae"),
            "rmse": metrics.get("rmse"),
            "r2": metrics.get("r2"),
            "nrmse": metrics.get("nrmse"),
            "pbias": metrics.get("pbias"),
            "train_seconds": metrics.get("train_seconds"),
        })
    rows.sort(key=lambda row: float(row["rmse"]) if row.get("rmse") is not None else float("inf"))
    return rows


def _render_model_choice_cards():
    rows = _model_metric_rows()
    if not rows:
        _render_empty_state("完成训练后，这里会显示每个模型的评估结果和当前使用状态。")
        return

    st.markdown("### 模型结果")
    cols = st.columns(2)
    for idx, row in enumerate(rows):
        with cols[idx % 2]:
            with st.container(border=True):
                st.markdown(f"#### {row['模型']}")
                metric_cols = st.columns(3)
                metric_cols[0].metric("RMSE", _fmt_metric(row.get("rmse")))
                metric_cols[1].metric("R²", _fmt_metric(row.get("r2")))
                metric_cols[2].metric("NRMSE", _fmt_metric(row.get("nrmse")))
                st.caption(
                    f"MAE：{_fmt_metric(row.get('mae'))} | "
                    f"PBIAS：{_fmt_metric(row.get('pbias'))} | "
                    f"训练耗时：{_fmt_metric(row.get('train_seconds'), 2)} 秒"
                )
                if row["当前使用"]:
                    st.success("当前正在使用该模型。")
                st.button(
                    "设为当前使用" if not row["当前使用"] else "当前使用中",
                    key=f"choose_model_{row['algorithm']}",
                    width="stretch",
                    disabled=bool(row["当前使用"]),
                    on_click=_queue_action,
                    args=(f"set_current_model:{row['algorithm']}",),
                )


def _explanation_focus_factors() -> list[str]:
    explanation_meta = st.session_state.get("_explanation_meta") or {}
    canonical = explanation_meta.get("canonical_factors") or []
    if canonical:
        return [str(item) for item in canonical]

    diagnostics = st.session_state.get("_diagnostics") or {}
    top_features = diagnostics.get("top_features") or []
    if top_features:
        return [str(name) for name, _ in top_features[:5]]
    return []


def _render_focus_factor_chips():
    factors = _explanation_focus_factors()
    if not factors:
        st.caption("当前还没有可展示的主导因子。")
        return
    st.caption("当前重点因子：" + " / ".join(factors))


def _render_model_results_section():
    rows = _model_metric_rows()
    if not rows:
        _render_empty_state("尚未生成模型评估结果。")
        return

    best_row = next((row for row in rows if row["当前使用"]), rows[0])
    cols = st.columns(4)
    cols[0].metric("当前使用模型", str(best_row.get("模型", "-")))
    cols[1].metric("RMSE", _fmt_metric(best_row.get("rmse")))
    cols[2].metric("R²", _fmt_metric(best_row.get("r2")))
    cols[3].metric("模型数量", str(len(rows)))
    with st.expander("展开完整评估表", expanded=False):
        st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)

    _render_optimization_comparison()


def _render_optimization_comparison():
    opt = st.session_state.get("_optimization_result") or {}
    if not opt or opt.get("status") != "ok":
        return
    comparison = opt.get("comparison", {})
    optimization_results = opt.get("optimization_results") or {}
    if comparison:
        st.markdown("### 优化前后对比")
        comp_rows = []
        for name, vals in comparison.items():
            if not isinstance(vals, dict):
                continue
            default = vals.get("default", {}) or {}
            optimized = vals.get("optimized", {}) or {}
            improvement = vals.get("improvement", {}) or {}
            comp_rows.append({
                "模型": name,
                "默认 R²": _fmt_metric(default.get("r2")),
                "优化后 R²": _fmt_metric(optimized.get("r2")),
                "R² 提升": f"+{_fmt_metric(improvement.get('r2_delta'))}",
                "默认 RMSE": _fmt_metric(default.get("rmse")),
                "优化后 RMSE": _fmt_metric(optimized.get("rmse")),
                "RMSE 降幅": f"{improvement.get('rmse_reduction_pct', 0):.1f}%",
            })
        if comp_rows:
            st.dataframe(pd.DataFrame(comp_rows), width="stretch", hide_index=True)
    elif optimization_results:
        st.markdown("### 贝叶斯优化结果")
        rows = []
        for algo, detail in optimization_results.items():
            rows.append({
                "模型": _model_display_name(algo),
                "最佳 R²": _fmt_metric(detail.get("best_r2")),
                "试验次数": detail.get("n_trials"),
                "最优参数": json.dumps(detail.get("best_params", {}), ensure_ascii=False),
            })
        if rows:
            st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)
    if opt.get("optimization_report_path"):
        st.caption(f"优化报告：`{opt['optimization_report_path']}`")
    if opt.get("report_path"):
        st.caption(f"重训报告：`{opt['report_path']}`")


def _render_explanation_results_section():
    explanation_meta = st.session_state.get("_explanation_meta") or {}
    explain_paths = _existing_paths(explanation_meta.get("explanation_files", []) or [])
    spatial_paths = _existing_paths(explanation_meta.get("spatial_files", []) or [])
    if not explain_paths and not spatial_paths:
        _render_empty_state("尚未生成解释分析结果。")
        return

    cols = st.columns(4)
    cols[0].metric("SHAP图件", str(len(explain_paths)))
    cols[1].metric("空间图件", str(len(spatial_paths)))
    cols[2].metric("解释模式", str(explanation_meta.get("explanation_mode", "-")))
    cols[3].metric("GeoShapley", str(explanation_meta.get("geoshapley_status", "-")))

    preview_paths = (explain_paths + spatial_paths)[:6]
    if preview_paths:
        _render_image_grid(preview_paths, "尚未找到可显示的解释图件。")
    with st.expander("展开解释路径", expanded=False):
        for path_item in explain_paths + spatial_paths:
            st.code(path_item, language="text")


def _render_prediction_results_section():
    predictions = st.session_state.get("predictions") or {}
    if not predictions:
        _render_empty_state("尚未生成预测结果。")
        return

    cols = st.columns(4)
    cols[0].metric("情景", str(predictions.get("scenario", "-")))
    cols[1].metric("平均侵蚀量", _fmt_metric(predictions.get("mean_erosion"), 2))
    cols[2].metric("最大侵蚀量", _fmt_metric(predictions.get("max_erosion"), 2))
    cols[3].metric("高风险比例", _fmt_metric(predictions.get("high_risk_ratio"), 2))

    action_cols = st.columns(2)
    action_cols[0].button("查看地图", key="layer_show_map", width="stretch", on_click=_queue_action, args=("show_map",))
    action_cols[1].button("查看不确定性", key="layer_show_uncertainty", width="stretch", on_click=_queue_action, args=("show_uncertainty",))

    maps_to_show = _find_latest_message_media("maps", "map") + _find_latest_message_media("maps", "uncertainty")
    shown_titles = set()
    for title, map_html in maps_to_show:
        if title in shown_titles:
            continue
        shown_titles.add(title)
        st.caption(str(title))
        components.html(map_html, height=420, scrolling=False)

    with st.expander("展开预测路径", expanded=False):
        for key in ["pred_path", "uncertainty_path", "pred_meta_path", "scenario"]:
            if predictions.get(key):
                st.code(f"{key}: {predictions.get(key)}", language="text")


def _render_export_results_section():
    run_context = st.session_state.get("run_context") or {}
    evidence_paths = _existing_paths(run_context.get("evidence_paths", []) or [])
    bundle_path = run_context.get("bundle_zip") or run_context.get("bundle_path")
    report_path = run_context.get("report_path")
    method_note = run_context.get("method_note")
    reproduce_note = run_context.get("reproduce_note")

    has_any_export = any([
        report_path and os.path.exists(str(report_path)),
        bundle_path and os.path.exists(str(bundle_path)),
        method_note and os.path.exists(str(method_note)),
        reproduce_note and os.path.exists(str(reproduce_note)),
        bool(evidence_paths),
    ])
    if not has_any_export:
        _render_empty_state("尚未生成导出产物。")
        return

    cols = st.columns(4)
    cols[0].metric("报告", "已就绪" if report_path and os.path.exists(str(report_path)) else "未就绪")
    cols[1].metric("结果包", "已就绪" if bundle_path and os.path.exists(str(bundle_path)) else "未就绪")
    cols[2].metric("方法说明", "已就绪" if method_note and os.path.exists(str(method_note)) else "未就绪")
    cols[3].metric("复现说明", "已就绪" if reproduce_note and os.path.exists(str(reproduce_note)) else "未就绪")

    if report_path and os.path.exists(str(report_path)):
        with open(report_path, "r", encoding="utf-8") as f:
            report_text = f.read()
        st.download_button(
            "下载报告",
            data=report_text,
            file_name=os.path.basename(str(report_path)),
            mime="text/markdown",
            key="download_report_dashboard",
        )
    if bundle_path and os.path.exists(str(bundle_path)):
        with open(bundle_path, "rb") as f:
            st.download_button(
                "下载结果包",
                data=f.read(),
                file_name=os.path.basename(str(bundle_path)),
                mime="application/zip",
                key="download_bundle_dashboard",
            )

    if evidence_paths:
        with st.expander("展开结果文件路径", expanded=False):
            for evidence_path in evidence_paths[:120]:
                st.code(evidence_path, language="text")


def render_results_workbench():
    """Legacy helper retained for compatibility; results are shown inside their own pages."""
    tabs = st.tabs(["\u6a21\u578b\u8bc4\u4f30\u7ed3\u679c", "\u89e3\u91ca\u7ed3\u679c", "\u9884\u6d4b\u7ed3\u679c", "\u5bfc\u51fa\u7ed3\u679c"])
    with tabs[0]:
        _render_model_results_section()
    with tabs[1]:
        _render_explanation_results_section()
    with tabs[2]:
        _render_prediction_results_section()
    with tabs[3]:
        _render_export_results_section()


def render_sidebar():
    with st.sidebar:
        st.markdown("## \u542f\u822a\u9875")
        st.caption("\u4e94\u5927\u9875\u9762\u5728\u6b64\u5207\u6362\uff1b\u6570\u636e\u4e0a\u4f20\u4e0e\u6587\u4ef6\u72b6\u6001\u5df2\u6536\u7eb3\u5230\u201c\u6570\u636e\u5904\u7406\u201d\u6a21\u5757\u3002")
        current_layer = st.session_state.get("current_layer", "home")
        for layer_id, title in LAYER_SEQUENCE:
            meta = _layer_nav_meta(layer_id)
            st.button(
                title,
                key=f"sidebar_nav_{layer_id}",
                width="stretch",
                type="primary" if layer_id == current_layer else "secondary",
                on_click=_queue_action,
                args=("go_home" if layer_id == "home" else f"open_layer:{layer_id}",),
            )


def _render_data_upload_workspace():
    status = get_upload_status()
    left, right = st.columns([1.05, 0.95])
    with left:
        with st.container(border=True):
            st.markdown("### 上传数据")
            st.caption("上传 GeoTIFF 或 CSV 文件，平台会把文件保存到本地工作区，并在后续清单、建模和导出流程中直接调用。")
            uploaded_files = st.file_uploader(
                "上传 GeoTIFF / CSV",
                type=["tif", "tiff", "csv"],
                accept_multiple_files=True,
                key="data_workshop_uploader",
            )
            if uploaded_files:
                count = handle_uploaded_files(uploaded_files)
                if count:
                    st.success(f"已接收 {count} 个文件。")
                sync_global_state()
            st.button("刷新识别结果", key="refresh_inputs", width="stretch", on_click=_queue_action, args=("load_inputs",))
    with right:
        with st.container(border=True):
            st.markdown("### 当前文件状态")
            st.caption(f"文件总数：{status['total']}")
            st.caption(f"已识别：{status['recognized']}")
            st.caption(f"变量：{', '.join(sorted(status['variables'])) if status['variables'] else '无'}")
            st.caption(f"年份：{', '.join(str(v) for v in sorted(status['years'])) if status['years'] else '无'}")
            st.caption(f"情景：{', '.join(sorted(status['scenarios'])) if status['scenarios'] else '无'}")
            if status["total"]:
                st.success("已存在可用于后续检查、建模与导出的真实上传文件。")
            else:
                st.info("当前尚未上传文件。请先在此处上传 GeoTIFF 或 CSV 文件。")

    with st.expander("已上传文件", expanded=False):
        if st.session_state.uploads:
            for fname in sorted(st.session_state.uploads.keys()):
                info = st.session_state.uploads.get(fname) or {}
                size_bytes = info.get("size")
                uploaded_at = info.get("uploaded_at", "-")
                size_text = f"{int(size_bytes)} B" if size_bytes is not None else "-"
                st.caption(f"{fname} | {size_text} | {uploaded_at}")
        else:
            st.caption("尚未上传文件。")

    with st.expander("文件命名说明", expanded=False):
        st.markdown("\n".join([
            "- 建议命名：`<variable>_<year>[_<scenario>].tif`",
            "- 示例：`R_2024.tif`、`label_2024.tif`、`C_2035_ssp245.tif`",
            "- 切换页面不会清空上传状态；上传文件会保留在当前本地工作区。",
        ]))

    with st.expander("会话管理", expanded=False):
        st.caption("如需清空当前上传、建模、解释与预测状态，可在这里重置整个平台会话。")
        if st.button("重置会话", key="reset_session_in_data_workshop", width="stretch"):
            handle_action("restart")


def _status_word(ok: bool, yes: str, no: str) -> str:
    return yes if ok else no


def render_home():
    if os.environ.get("WATER_EROSION_UI_QA_SEED") == "1":
        st.warning("\u754c\u9762\u6d4b\u8bd5\u72b6\u6001\uff1a\u4ee5\u4e0b\u72b6\u6001\u4ec5\u7528\u4e8e\u4ea4\u4e92\u9a8c\u8bc1\uff0c\u4e0d\u4ee3\u8868\u79d1\u7814\u7ed3\u679c\u3002")
    hero_left, hero_right = st.columns([1.35, 0.85], gap="large")
    with hero_left:
        with st.container(border=True):
            st.caption("首页设计基线")
            st.markdown("# 黑土区水蚀智能预测与证据化评估平台")
            st.markdown("面向黑土区水蚀过程认知、因子解释与空间表达的科研分析平台。")
            chip_cols = st.columns(3)
            chip_cols[0].caption("黑土区")
            chip_cols[1].caption("RUSLE 五因子")
            chip_cols[2].caption("空间解释")
            st.caption("首页只承担平台定位与领域认知，不承担建模说明、结果摘要或流程引导。")
    with hero_right:
        with st.container(border=True):
            st.markdown("#### 研究认知框架")
            st.metric("研究重点", "侵蚀风险识别")
            st.caption("聚焦地形、降雨、覆盖与管理共同作用下的侵蚀差异。")
            st.metric("因子体系", "R / K / LS / C / P")
            st.caption("以五大因子组织平台视角、因子理解与后续模型解释。")

    st.caption("\u9996\u9875\u53ea\u627f\u62c5\u5e73\u53f0\u5b9a\u4f4d\u4e0e\u9886\u57df\u8ba4\u77e5\uff0c\u4e0d\u627f\u62c5\u5efa\u6a21\u8bf4\u660e\u3001\u7ed3\u679c\u6458\u8981\u6216\u6d41\u7a0b\u5f15\u5bfc\u3002")
    st.markdown("### \u7814\u7a76\u805a\u7126")
    st.caption("\u9996\u9875\u7684\u4fe1\u606f\u5bc6\u5ea6\u6765\u81ea\u7814\u7a76\u8ba4\u77e5\u7ed3\u6784\uff0c\u800c\u4e0d\u662f\u64cd\u4f5c\u6a21\u5757\u5806\u53e0\u3002")
    focus_cols = st.columns(3)
    with focus_cols[0]:
        with st.container(border=True):
            st.caption("Focus 01")
            st.markdown("#### 研究对象")
            st.markdown("黑土区水蚀研究强调地形起伏、降雨侵蚀力、土地覆盖与耕作管理共同作用下的侵蚀响应，而不是单一因子的静态判断。")
            st.caption("首页只说明研究对象，不提前解释操作流程。")
    with focus_cols[1]:
        with st.container(border=True):
            st.caption("Focus 02")
            st.markdown("#### 五因子体系")
            st.markdown("R、K、LS、C、P 构成平台的核心认知框架，用于组织平台视角、因子理解与后续模型解释的一致口径。")
            st.caption("首页呈现因子框架，不呈现建模参数、指标或运行细节。")
    with focus_cols[2]:
        with st.container(border=True):
            st.caption("Focus 03")
            st.markdown("#### 空间表达")
            st.markdown("科研意义不仅在于预测值本身，还在于识别空间异质性、高风险区域以及不同因子在空间上的主导作用范围。")
            st.caption("真实图件与导出留在结果解释和预测导出模块。")
    with st.expander("\u5c55\u5f00\u6c34\u8680\u7814\u7a76\u80cc\u666f\u8bf4\u660e", expanded=False):
        st.markdown(
            "\n".join([
                "- \u9ed1\u571f\u533a\u6c34\u8680\u5177\u6709\u660e\u663e\u7684\u5730\u5f62\u5dee\u5f02\u3001\u65f6\u5e8f\u53d8\u5316\u548c\u7a7a\u95f4\u5f02\u8d28\u6027\u3002",
                "- \u7814\u7a76\u91cd\u70b9\u901a\u5e38\u5305\u62ec\u4fb5\u8680\u5f3a\u5ea6\u8bc6\u522b\u3001\u4e3b\u5bfc\u56e0\u5b50\u89e3\u91ca\u4ee5\u53ca\u9ad8\u98ce\u9669\u533a\u57df\u8868\u8fbe\u3002",
                "- \u9762\u5411\u79d1\u7814\u5e94\u7528\u7684\u7ed3\u679c\u9700\u8981\u517c\u987e\u7a7a\u95f4\u53ef\u8bfb\u6027\u3001\u89e3\u91ca\u53ef\u4fe1\u5ea6\u548c\u540e\u7eed\u590d\u7528\u3002",
            ])
        )
    return

    st.markdown(
        """
        <div class="home-hero">
          <div class="home-hero-card">
            <span class="home-kicker">首页设计基线</span>
            <h1 class="home-title">黑土区水蚀智能预测与证据化评估平台</h1>
            <p class="home-subtitle">面向黑土区水蚀过程认知、因子解释与空间表达的科研分析平台。</p>
            <div class="home-chip-row">
              <span class="home-chip">黑土区</span>
              <span class="home-chip">RUSLE五因子</span>
              <span class="home-chip">空间解释</span>
            </div>
            <p class="home-hero-meta">首页只承担平台定位与领域认知，不承担建模说明、结果摘要或流程引导。</p>
          </div>
          <div class="home-hero-card home-visual">
            <div class="home-visual-grid">
              <div class="home-visual-panel">
                <span class="home-visual-label">Research Focus</span>
                <div class="home-visual-value">侵蚀风险识别</div>
                <div class="home-visual-caption">聚焦黑土区地形、降雨、覆盖与管理共同作用下的侵蚀差异。</div>
              </div>
              <div class="home-visual-panel">
                <span class="home-visual-label">Factor Frame</span>
                <div class="home-visual-value">R / K / LS / C / P</div>
                <div class="home-visual-caption">以五大因子作为科研认知框架，而不是把结果提前搬回首页。</div>
              </div>
              <div class="home-visual-panel">
                <span class="home-visual-label">Spatial Reading</span>
                <div class="home-visual-value">主导因子与异质性</div>
                <div class="home-visual-caption">强调空间差异、主导驱动区域和后续解释图件的学术价值。</div>
              </div>
              <div class="home-visual-panel">
                <span class="home-visual-label">Interface Rule</span>
                <div class="home-visual-value">专业但不冗杂</div>
                <div class="home-visual-caption">通过主视觉、认知卡片和折叠阅读构建丰富性，而不是堆功能说明。</div>
              </div>
            </div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.caption("\u9996\u9875\u53ea\u627f\u62c5\u5e73\u53f0\u5b9a\u4f4d\u4e0e\u9886\u57df\u8ba4\u77e5\uff0c\u4e0d\u627f\u62c5\u5efa\u6a21\u8bf4\u660e\u3001\u7ed3\u679c\u6458\u8981\u6216\u6d41\u7a0b\u5f15\u5bfc\u3002")
    st.markdown("### \u7814\u7a76\u805a\u7126")
    st.caption("\u9996\u9875\u7684\u4fe1\u606f\u5bc6\u5ea6\u6765\u81ea\u7814\u7a76\u8ba4\u77e5\u7ed3\u6784\uff0c\u800c\u4e0d\u662f\u64cd\u4f5c\u6a21\u5757\u5806\u53e0\u3002")
    st.markdown(
        """
        <div class="home-focus-grid">
          <div class="home-focus-card">
            <div class="home-focus-index">Focus 01</div>
            <h3 class="home-focus-title">研究对象</h3>
            <p class="home-focus-body">黑土区水蚀研究强调地形起伏、降雨侵蚀力、土地覆盖与耕作管理共同作用下的侵蚀响应，而不是单一因子的静态判断。</p>
            <div class="home-focus-emphasis">首页只说明“研究的是什么”，不提前解释“怎么做”。</div>
          </div>
          <div class="home-focus-card">
            <div class="home-focus-index">Focus 02</div>
            <h3 class="home-focus-title">五因子体系</h3>
            <p class="home-focus-body">R、K、LS、C、P 构成黑土区水蚀智能预测与证据化评估平台的核心认知框架，用于组织平台视角、因子理解与后续模型解释的一致口径。</p>
            <div class="home-focus-emphasis">首页呈现因子框架，不呈现建模参数、指标或运行细节。</div>
          </div>
          <div class="home-focus-card">
            <div class="home-focus-index">Focus 03</div>
            <h3 class="home-focus-title">空间表达</h3>
            <p class="home-focus-body">科研意义不仅在于预测值本身，还在于识别空间异质性、高风险区域以及不同因子在空间上的主导作用范围。</p>
            <div class="home-focus-emphasis">首页建立空间认知预期，真实图件与导出留在结果解释和预测导出模块。</div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    with st.expander("\u5c55\u5f00\u6c34\u8680\u7814\u7a76\u80cc\u666f\u8bf4\u660e", expanded=False):
        st.markdown(
            "\n".join([
                "- \u9ed1\u571f\u533a\u6c34\u8680\u5177\u6709\u660e\u663e\u7684\u5730\u5f62\u5dee\u5f02\u3001\u65f6\u5e8f\u53d8\u5316\u548c\u7a7a\u95f4\u5f02\u8d28\u6027\u3002",
                "- \u7814\u7a76\u91cd\u70b9\u901a\u5e38\u5305\u62ec\u4fb5\u8680\u5f3a\u5ea6\u8bc6\u522b\u3001\u4e3b\u5bfc\u56e0\u5b50\u89e3\u91ca\u4ee5\u53ca\u9ad8\u98ce\u9669\u533a\u57df\u8868\u8fbe\u3002",
                "- \u9762\u5411\u79d1\u7814\u5e94\u7528\u7684\u7ed3\u679c\u9700\u8981\u517c\u987e\u7a7a\u95f4\u53ef\u8bfb\u6027\u3001\u89e3\u91ca\u53ef\u4fe1\u5ea6\u548c\u540e\u7eed\u590d\u7528\u3002",
            ])
        )

def render_data_workshop():
    _render_page_header("\u6570\u636e\u5904\u7406", "\u4e0a\u4f20\u6216\u52a0\u8f7d\u6570\u636e\uff0c\u68c0\u67e5\u6587\u4ef6\u8bc6\u522b\u7ed3\u679c\uff0c\u5e76\u5f62\u6210\u6570\u636e\u6e05\u5355\u3002", "\u2460 \u6570\u636e\u5904\u7406")
    _render_tiff_feature_help()
    subview = st.radio("\u5206\u533a", ["\u4e0a\u4f20\u6570\u636e", "\u6570\u636e\u68c0\u67e5", "\u6570\u636e\u6e05\u5355"], horizontal=True, key="data_workshop_view")
    st.session_state["layer_last_view"]["dataWorkshop"] = subview
    if subview == "\u6570\u636e\u68c0\u67e5":
        st.button("\u8fd0\u884c\u6570\u636e\u68c0\u67e5", key="run_quality_check", width="stretch", on_click=_queue_action, args=("assess_quality",))
        quality = st.session_state.get("_quality_report") or {}
        st.json(quality) if quality else _render_empty_state("\u672a\u8fd0\u884c\u6570\u636e\u68c0\u67e5\u3002")
    elif subview == "\u6570\u636e\u6e05\u5355":
        _render_data_archive()
    else:
        _render_data_upload_workspace()


def render_modeling_lab():
    _render_page_header("\u6a21\u578b\u6784\u5efa", "\u5728\u5f53\u524d\u6570\u636e\u57fa\u7840\u4e0a\u5b8c\u6210\u8bad\u7ec3\u3001\u4f18\u5316\u3001\u91cd\u8bad\u548c\u6a21\u578b\u9009\u7528\uff0c\u5e76\u628a\u7ed3\u679c\u76f4\u63a5\u4f20\u9012\u5230\u89e3\u91ca\u5206\u6790\u3002", "\u2461 \u6a21\u578b\u6784\u5efa")
    ft_ready = bool(st.session_state.get("feature_table"))
    models_ready = bool(st.session_state.get("models"))
    optimization = st.session_state.get("_optimization_result") or {}
    optimization_ready = bool(optimization.get("optimization_results"))
    retrain_ready = bool(optimization.get("comparison") or optimization.get("retrained_metrics"))
    feature_error = st.session_state.get("_last_feature_build_error") or {}

    registry = _model_registry()
    algorithm_options = [
        cfg.get("display_name", algo)
        for algo, cfg in registry.items()
        if algo in {"random_forest", "xgboost", "lightgbm", "extratrees", "catboost", "adaboost", "svr", "knn"}
    ]
    default_algorithms = [name for name in ["\u968f\u673a\u68ee\u6797", "XGBoost", "LightGBM"] if name in algorithm_options] or algorithm_options[:3]

    feature_info = st.session_state.get("feature_table") or {}
    summary_cols = st.columns(3)
    summary_cols[0].metric("\u5efa\u6a21\u6570\u636e", "\u5df2\u5c31\u7eea" if ft_ready else "\u672a\u751f\u6210")
    summary_cols[1].metric("\u6a21\u578b\u7ed3\u679c", str(len(st.session_state.get("models") or {})))
    summary_cols[2].metric("\u5f53\u524d\u4f7f\u7528", _model_display_name(st.session_state.get("best_model")) if st.session_state.get("best_model") else "\u672a\u9009\u5b9a")

    top_left, top_right = st.columns([0.95, 1.05])
    with top_left:
        with st.container(border=True):
            st.markdown("### \u5efa\u6a21\u6570\u636e\u51c6\u5907")
            st.caption("\u8fd9\u91cc\u76f4\u63a5\u8c03\u7528\u771f\u5b9e\u540e\u7aef\u6784\u5efa\u5efa\u6a21\u6570\u636e\uff1b\u6ca1\u6709\u6807\u7b7e\u3001\u6ca1\u6709\u6709\u6548\u91cd\u53e0\u6216\u6709\u6548\u50cf\u5143\u4e0d\u8db3\u65f6\uff0c\u4f1a\u8fd4\u56de\u660e\u786e\u539f\u56e0\u3002")
            st.button("\u6784\u5efa\u5efa\u6a21\u6570\u636e", key="build_feature_table_action", width="stretch", on_click=_queue_action, args=("build_features",), disabled=False)
            if feature_error:
                st.error(feature_error.get("message") or "\u5efa\u6a21\u6570\u636e\u6784\u5efa\u5931\u8d25\u3002")
                if feature_error.get("error_type"):
                    st.caption(f"\u9519\u8bef\u7c7b\u578b\uff1a{feature_error.get('error_type')}")
                if feature_error.get("suggested_action"):
                    st.info(feature_error.get("suggested_action"))
            if feature_info:
                st.success(f"\u6837\u672c\u6570\uff1a{feature_info.get('n_samples', '-')} | \u53d8\u91cf\u6570\uff1a{feature_info.get('n_features', '-')}")
                if feature_info.get("path"):
                    st.caption(f"\u6570\u636e\u6587\u4ef6\uff1a`{feature_info.get('path')}`")
            else:
                st.info("\u5f53\u524d\u8fd8\u6ca1\u6709\u53ef\u8bad\u7ec3\u7684\u5efa\u6a21\u6570\u636e\u3002")
    with top_right:
        with st.container(border=True):
            st.markdown("### \u8bad\u7ec3\u65b9\u6848")
            st.caption("\u9009\u62e9\u8981\u53c2\u4e0e\u8bad\u7ec3\u7684\u6a21\u578b\uff0c\u5e76\u8bbe\u7f6e\u4ea4\u53c9\u9a8c\u8bc1\u548c\u8d1d\u53f6\u65af\u4f18\u5316\u8f6e\u6570\u3002")
            st.multiselect(
                "\u9009\u62e9\u53c2\u4e0e\u8bad\u7ec3\u7684\u6a21\u578b",
                options=algorithm_options,
                default=default_algorithms,
                key="model_algorithm_selection",
                help="\u9ed8\u8ba4\u4f1a\u540c\u65f6\u8bad\u7ec3\u591a\u79cd\u6a21\u578b\uff0c\u8bad\u7ec3\u5b8c\u6210\u540e\u53ef\u624b\u52a8\u5207\u6362\u5f53\u524d\u4f7f\u7528\u6a21\u578b\u3002",
            )
            st.selectbox(
                "\u91cd\u70b9\u67e5\u770b\u6a21\u578b",
                options=algorithm_options or ["\u6682\u65e0\u53ef\u9009\u6a21\u578b"],
                index=0 if algorithm_options else None,
                key="model_focus_selection",
            )
            controls = st.columns([1, 1])
            controls[0].select_slider("\u7a7a\u95f4\u4ea4\u53c9\u9a8c\u8bc1\u6298\u6570", options=[3, 4, 5], value=4, key="model_cv_folds")
            controls[1].select_slider("\u8d1d\u53f6\u65af\u4f18\u5316\u8f6e\u6570", options=[10, 20, 30, 40], value=20, key="model_opt_trials")
            _render_model_hyperparameter_controls(registry, _selected_training_algorithms())

    stage_cols = st.columns(3)
    with stage_cols[0]:
        with st.container(border=True):
            st.markdown("### \u9ed8\u8ba4\u8bad\u7ec3")
            st.caption("\u4f7f\u7528\u5f53\u524d\u5efa\u6a21\u6570\u636e\u5b8c\u6210\u7b2c\u4e00\u8f6e\u771f\u5b9e\u8bad\u7ec3\uff0c\u5e76\u81ea\u52a8\u751f\u6210\u6a21\u578b\u8bc4\u4f30\u7ed3\u679c\u3002")
            st.button("\u9ed8\u8ba4\u8bad\u7ec3", key="train_models_action", width="stretch", on_click=_queue_action, args=("train_models",), disabled=not ft_ready or not _selected_training_algorithms())
            st.caption("\u72b6\u6001\uff1a" + ("\u5df2\u5b8c\u6210" if models_ready else "\u672a\u8fd0\u884c"))
            if not ft_ready:
                st.info("\u8bf7\u5148\u6784\u5efa\u5efa\u6a21\u6570\u636e\u3002")
    with stage_cols[1]:
        with st.container(border=True):
            st.markdown("### \u8d1d\u53f6\u65af\u4f18\u5316")
            st.caption("\u5bf9\u5df2\u8bad\u7ec3\u6a21\u578b\u6267\u884c\u8d1d\u53f6\u65af\u4f18\u5316\uff0c\u5f97\u5230\u66f4\u4f18\u8d85\u53c2\u6570\u3002")
            st.button("\u8d1d\u53f6\u65af\u4f18\u5316", key="optimize_models_action", width="stretch", on_click=_queue_action, args=("optimize_models",), disabled=not models_ready or not _selected_training_algorithms())
            st.caption("\u72b6\u6001\uff1a" + ("\u5df2\u5b8c\u6210" if optimization_ready else "\u672a\u8fd0\u884c"))
            if not models_ready:
                st.info("\u8bf7\u5148\u5b8c\u6210\u9ed8\u8ba4\u8bad\u7ec3\u3002")
    with stage_cols[2]:
        with st.container(border=True):
            st.markdown("### \u4f18\u5316\u540e\u91cd\u8bad")
            st.caption("\u7528\u9636\u6bb5\u4e8c\u6700\u4f18\u8d85\u53c2\u6570\u91cd\u65b0\u8bad\u7ec3\uff0c\u5e76\u66f4\u65b0\u5f53\u524d\u4f7f\u7528\u6a21\u578b\u3002")
            st.button("\u4f18\u5316\u540e\u91cd\u8bad", key="retrain_optimized_action", width="stretch", on_click=_queue_action, args=("retrain_optimized",), disabled=not optimization_ready or not _selected_training_algorithms())
            st.caption("\u72b6\u6001\uff1a" + ("\u5df2\u5b8c\u6210" if retrain_ready else "\u672a\u8fd0\u884c"))
            if not optimization_ready:
                st.info("\u8bf7\u5148\u5b8c\u6210\u8d1d\u53f6\u65af\u4f18\u5316\u3002")

    current_cols = st.columns([1.15, 0.85])
    with current_cols[0]:
        _render_model_results_section()
        _render_model_choice_cards()
    with current_cols[1]:
        with st.container(border=True):
            st.markdown("### \u5f53\u524d\u4f7f\u7528")
            if st.session_state.get("best_model"):
                best_algo = st.session_state.get("best_model")
                best_metrics = ((st.session_state.get("models") or {}).get(best_algo) or {}).get("metrics", {})
                st.metric("\u6a21\u578b", _model_display_name(best_algo))
                st.caption(f"R\u00b2\uff1a{_fmt_metric(best_metrics.get('r2'))} | RMSE\uff1a{_fmt_metric(best_metrics.get('rmse'))}")
                st.caption("\u8bad\u7ec3\u5b8c\u6210\u540e\uff0c\u7ed3\u679c\u89e3\u91ca\u9875\u4f1a\u4f18\u5148\u8bfb\u53d6\u5f53\u524d\u4f7f\u7528\u6a21\u578b\u5e76\u81ea\u52a8\u5c55\u793a\u89e3\u91ca\u56fe\u4ef6\u3002")
                st.button("\u8fdb\u5165\u7ed3\u679c\u89e3\u91ca", key="go_to_explain_from_modeling", width="stretch", on_click=_queue_action, args=("open_layer:explainStudio",))
            else:
                _render_empty_state("\u5b8c\u6210\u9ed8\u8ba4\u8bad\u7ec3\u540e\uff0c\u8fd9\u91cc\u4f1a\u663e\u793a\u5f53\u524d\u4f7f\u7528\u6a21\u578b\u3002")
            st.button("\u67e5\u770b\u6a21\u578b\u7ed3\u679c", key="show_model_details_action", width="stretch", on_click=_queue_action, args=("show_model_details",), disabled=not models_ready)
        _render_optimization_comparison()

def render_explain_studio():
    _render_page_header("\u7ed3\u679c\u89e3\u91ca", "\u56f4\u7ed5\u5f53\u524d\u4f7f\u7528\u6a21\u578b\u5c55\u793a\u771f\u5b9e\u89e3\u91ca\u7ed3\u679c\uff0c\u5305\u62ec SHAP \u5206\u5e03\u3001\u4e94\u56e0\u5b50\u7a7a\u95f4\u70ed\u529b\u56fe\u3001\u56e0\u5b50\u91cd\u8981\u6027\u4e0e\u5bfc\u51fa\u3002", "\u2462 \u7ed3\u679c\u89e3\u91ca")
    block_reason = _layer_block_reason("explainStudio")
    if block_reason:
        st.warning(block_reason)

    explanation_meta = st.session_state.get("_explanation_meta") or {}
    best_algo = st.session_state.get("best_model")
    best_metrics = ((st.session_state.get("models") or {}).get(best_algo) or {}).get("metrics", {})

    summary_left, summary_right = st.columns([1.1, 0.9])
    with summary_left:
        with st.container(border=True):
            st.markdown("### \u5f53\u524d\u6a21\u578b")
            if best_algo:
                st.metric("\u6a21\u578b", _model_display_name(best_algo))
                st.caption(f"R\u00b2\uff1a{_fmt_metric(best_metrics.get('r2'))} | RMSE\uff1a{_fmt_metric(best_metrics.get('rmse'))}")
                _render_focus_factor_chips()
                st.caption("\u8bad\u7ec3\u5b8c\u6210\u540e\u4f1a\u81ea\u52a8\u5c1d\u8bd5\u5237\u65b0\u89e3\u91ca\u56fe\u4ef6\uff1b\u8fd9\u91cc\u4e5f\u652f\u6301\u624b\u52a8\u91cd\u65b0\u751f\u6210\u3002")
            else:
                _render_empty_state("\u5f53\u524d\u8fd8\u6ca1\u6709\u53ef\u89e3\u91ca\u7684\u6a21\u578b\u3002")
    with summary_right:
        with st.container(border=True):
            st.markdown("### \u89e3\u91ca\u64cd\u4f5c")
            actions = st.columns(2)
            actions[0].button("\u5237\u65b0\u89e3\u91ca\u7ed3\u679c", key="generate_explanations_action", width="stretch", on_click=_queue_action, args=("generate_explanations",), disabled=bool(block_reason))
            actions[1].button("\u89e3\u91ca\u5f53\u524d\u7ed3\u679c", key="assistant_explain_result_action", width="stretch", on_click=_queue_action, args=("assistant_explain_result",), disabled=bool(block_reason))
            export_actions = st.columns(2)
            export_actions[0].button("\u5bfc\u51fa\u89e3\u91ca\u62a5\u544a", key="generate_report_from_explain", width="stretch", on_click=_queue_action, args=("generate_report",), disabled=not bool(best_algo))
            export_actions[1].button("\u5bfc\u51fa\u7ed3\u679c\u5305", key="export_bundle_from_explain", width="stretch", on_click=_queue_action, args=("export_bundle",), disabled=not bool(best_algo))
            st.button("\u8fdb\u5165\u9884\u6d4b\u5bfc\u51fa", key="go_to_predict_from_explain", width="stretch", on_click=_queue_action, args=("open_layer:predictExport",), disabled=not bool(best_algo))

    stats = st.columns(4)
    stats[0].metric("\u89e3\u91ca\u56fe\u4ef6", str(len(_existing_paths(explanation_meta.get("explanation_files", []) or []))))
    stats[1].metric("\u7a7a\u95f4\u56fe\u4ef6", str(len(_existing_paths(explanation_meta.get("spatial_files", []) or []))))
    stats[2].metric("\u89e3\u91ca\u65b9\u5f0f", str(explanation_meta.get("explanation_mode", "-")))
    stats[3].metric("\u5f53\u524d\u56e0\u5b50\u6570", str(len(_explanation_focus_factors())))

    view_mode = st.radio("\u9009\u62e9\u89e3\u91ca\u65b9\u5f0f", ["SHAP\u503c\u5206\u5e03", "\u4e94\u56e0\u5b50\u7a7a\u95f4\u70ed\u529b\u56fe", "\u56e0\u5b50\u91cd\u8981\u6027"], horizontal=True, key="explain_studio_view")
    shap_paths = _existing_paths(explanation_meta.get("explanation_files", []) or [])
    spatial_paths = _existing_paths(explanation_meta.get("spatial_files", []) or [])
    factor_spatial_paths = explanation_meta.get("factor_spatial_paths") or {}
    if view_mode == "SHAP\u503c\u5206\u5e03":
        preferred = [
            p for p in shap_paths
            if any(key in os.path.basename(p).lower() for key in ["summary", "beeswarm", "dependence", "interaction", "proxy"])
        ]
        _render_image_grid(preferred or shap_paths, "\u5f53\u524d\u8fd8\u6ca1\u6709 SHAP \u56fe\u4ef6\u3002\u8bad\u7ec3\u5b8c\u6210\u540e\u4f1a\u81ea\u52a8\u751f\u6210\uff0c\u6216\u70b9\u51fb\u201c\u5237\u65b0\u89e3\u91ca\u7ed3\u679c\u201d\u3002")
    elif view_mode == "\u4e94\u56e0\u5b50\u7a7a\u95f4\u70ed\u529b\u56fe":
        ordered_factor_maps = [
            factor_spatial_paths[factor]
            for factor in _explanation_focus_factors()
            if factor_spatial_paths.get(factor) and os.path.exists(str(factor_spatial_paths.get(factor)))
        ]
        _render_image_grid(ordered_factor_maps, "\u5f53\u524d\u8fd8\u6ca1\u6709\u4e94\u56e0\u5b50\u7a7a\u95f4\u70ed\u529b\u56fe\u3002\u8bad\u7ec3\u5b8c\u6210\u540e\u4f1a\u81ea\u52a8\u751f\u6210\uff0c\u6216\u70b9\u51fb\u201c\u5237\u65b0\u89e3\u91ca\u7ed3\u679c\u201d\u3002")
        extra_spatial = [p for p in spatial_paths if p not in ordered_factor_maps]
        if extra_spatial:
            with st.expander("\u5c55\u5f00\u5176\u5b83\u7a7a\u95f4\u89e3\u91ca\u56fe\u4ef6", expanded=False):
                _render_image_grid(extra_spatial, "\u6682\u65e0\u5176\u5b83\u7a7a\u95f4\u89e3\u91ca\u56fe\u4ef6\u3002")
    else:
        diag = st.session_state.get("_diagnostics") or {}
        top_features = diag.get("top_features") or []
        if top_features:
            rows = [{"\u56e0\u5b50": name, "\u91cd\u8981\u6027": round(float(value), 4)} for name, value in top_features]
            st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)
        else:
            _render_empty_state("\u5f53\u524d\u8fd8\u6ca1\u6709\u53ef\u7528\u7684\u56e0\u5b50\u91cd\u8981\u6027\u7ed3\u679c\u3002")
        if explanation_meta.get("shap_risk_note"):
            st.info(explanation_meta.get("shap_risk_note"))
        if explanation_meta.get("geoshapley_reason"):
            st.caption(explanation_meta.get("geoshapley_reason"))

    with st.expander("\u5c55\u5f00\u5168\u90e8\u89e3\u91ca\u56fe\u4ef6\u4e0e\u6587\u4ef6\u8def\u5f84", expanded=False):
        _render_explanation_results_section()
    st.markdown("### \u89e3\u91ca\u7ed3\u679c\u5bfc\u51fa")
    _render_export_results_section()

def render_predict_export():
    _render_page_header("\u9884\u6d4b\u5bfc\u51fa", "\u914d\u7f6e\u9884\u6d4b\u60c5\u666f\uff0c\u751f\u6210\u9884\u6d4b\u5730\u56fe\uff0c\u5e76\u5bfc\u51fa GeoTIFF\u3001CSV \u6216\u62a5\u544a\u3002", "\u2463 \u9884\u6d4b\u5bfc\u51fa")
    block_reason = _layer_block_reason("predictExport")
    if block_reason: st.info(block_reason)
    subview = st.radio("\u5206\u533a", ["\u9884\u6d4b\u5730\u56fe", "\u5bfc\u51fa\u7ed3\u679c"], horizontal=True, key="predict_export_view")
    st.session_state["layer_last_view"]["predictExport"] = subview
    model_ready = _model_locked(st.session_state.get("models") or {}, st.session_state.get("best_model"))
    if subview == "\u5bfc\u51fa\u7ed3\u679c":
        c=st.columns(2); c[0].button("\u5bfc\u51fa\u7ed3\u679c", key="export_bundle_action", width="stretch", on_click=_queue_action, args=("export_bundle",), disabled=not model_ready); c[1].button("\u751f\u6210\u62a5\u544a", key="generate_report_action", width="stretch", on_click=_queue_action, args=("generate_report",), disabled=not model_ready); _render_export_results_section()
    else:
        c=st.columns(3); c[0].button("\u751f\u6210\u9884\u6d4b\u5730\u56fe", key="predict_future_action", width="stretch", on_click=_queue_action, args=("predict",), disabled=not model_ready); c[1].button("\u67e5\u770b\u5730\u56fe", key="predict_show_map", width="stretch", on_click=_queue_action, args=("show_map",), disabled=not _predictions_ready(st.session_state.get("predictions") or {})); c[2].button("\u67e5\u770b\u4e0d\u786e\u5b9a\u6027", key="predict_show_uncertainty", width="stretch", on_click=_queue_action, args=("show_uncertainty",), disabled=not _predictions_ready(st.session_state.get("predictions") or {})); _render_prediction_results_section()


def _assistant_status_message() -> str:
    try:
        agent = _session_agent()
        ok, reason = agent.backend.available()
        if ok and getattr(agent.settings, "backend", "") == "openai":
            return "OpenAI API 后端可用。"
        if ok:
            return "\u672c\u5730\u5f00\u6e90\u6a21\u578b\u53ef\u7528\u3002"
        if str(reason).startswith("External LLM disabled"):
            return "智能小助手使用本地兜底响应，科研主链可继续使用。"
        return f"{reason}\u3002\u79d1\u7814\u4e3b\u94fe\u4ecd\u53ef\u7ee7\u7eed\u4f7f\u7528\u3002"
    except Exception:
        return "助手推理暂不可用，科研主链仍可继续使用。"


def _assistant_actions() -> list:
    actions=[_next_recommended_action()["action"]]
    if st.session_state.get("current_layer") == "modelingLab": actions += ["train_models", "optimize_models"]
    elif st.session_state.get("current_layer") == "explainStudio": actions.append("assistant_explain_result")
    elif st.session_state.get("current_layer") == "predictExport": actions.append("show_map")
    return list(dict.fromkeys(actions))[:3]


def _assistant_label(action: str) -> str:
    return {"open_layer:dataWorkshop":"\u8fdb\u5165\u6570\u636e\u5904\u7406", "assess_quality":"\u8fd0\u884c\u6570\u636e\u68c0\u67e5", "build_features":"\u6784\u5efa\u5efa\u6a21\u6570\u636e", "train_models":"\u9ed8\u8ba4\u8bad\u7ec3", "optimize_models":"\u8d1d\u53f6\u65af\u4f18\u5316", "retrain_optimized":"\u4f18\u5316\u540e\u91cd\u8bad", "generate_explanations":"\u751f\u6210\u89e3\u91ca\u7ed3\u679c", "predict":"\u751f\u6210\u9884\u6d4b\u5730\u56fe", "export_bundle":"\u5bfc\u51fa\u7ed3\u679c", "show_model_details":"\u67e5\u770b\u8bc4\u4f30\u7ed3\u679c", "assistant_explain_result":"\u89e3\u91ca\u5f53\u524d\u7ed3\u679c", "show_map":"\u67e5\u770b\u5730\u56fe", "go_home":"\u8fd4\u56de\u9996\u9875"}.get(action, action)


def _push_user_message(content: str):
    st.session_state.messages.append({"role": "user", "content": _sanitize_dialogue_text(content), "metadata": {}})


def _queue_action(action: str):
    st.session_state["pending_action"] = action


def _inject_assistant_drag_script():
    components.html(
        """
        <script>
        (() => {
          const doc = window.parent.document;
          const storagePrefix = "water_erosion_smart_assistant_";

          function clamp(value, min, max) {
            return Math.max(min, Math.min(max, value));
          }

          function restorePosition(el, key) {
            const saved = window.parent.localStorage.getItem(storagePrefix + key);
            if (!saved) return;
            try {
              const pos = JSON.parse(saved);
              if (Number.isFinite(pos.left) && Number.isFinite(pos.top)) {
                el.style.left = clamp(pos.left, 8, window.parent.innerWidth - 80) + "px";
                el.style.top = clamp(pos.top, 8, window.parent.innerHeight - 60) + "px";
                el.style.right = "auto";
                el.style.bottom = "auto";
              }
            } catch (_) {}
          }

          function makeDraggable(el, handle, key) {
            if (!el || !handle || el.dataset.dragReady === "1") return;
            el.dataset.dragReady = "1";
            restorePosition(el, key);

            let dragging = false;
            let offsetX = 0;
            let offsetY = 0;

            handle.addEventListener("pointerdown", (event) => {
              const rect = el.getBoundingClientRect();
              dragging = true;
              offsetX = event.clientX - rect.left;
              offsetY = event.clientY - rect.top;
              el.style.left = rect.left + "px";
              el.style.top = rect.top + "px";
              el.style.right = "auto";
              el.style.bottom = "auto";
              handle.setPointerCapture?.(event.pointerId);
              event.preventDefault();
            });

            doc.addEventListener("pointermove", (event) => {
              if (!dragging) return;
              const nextLeft = clamp(event.clientX - offsetX, 8, window.parent.innerWidth - el.offsetWidth - 8);
              const nextTop = clamp(event.clientY - offsetY, 8, window.parent.innerHeight - el.offsetHeight - 8);
              el.style.left = nextLeft + "px";
              el.style.top = nextTop + "px";
            });

            doc.addEventListener("pointerup", () => {
              if (!dragging) return;
              dragging = false;
              const rect = el.getBoundingClientRect();
              window.parent.localStorage.setItem(storagePrefix + key, JSON.stringify({ left: rect.left, top: rect.top }));
            });
          }

          function init() {
            const panel = doc.querySelector(".st-key-assistant_panel_container");
            const panelHandle = panel?.querySelector(".assistant-drag-handle");
            if (panel && panelHandle) {
              makeDraggable(panel, panelHandle, "panel");
            }
          }

          init();
          new MutationObserver(init).observe(doc.body, { childList: true, subtree: true });
        })();
        </script>
        """,
        height=0,
        width=0,
    )


def _assistant_avatar_path() -> str:
    return os.path.join(os.path.dirname(__file__), "assets", "smart_assistant_avatar.png")


def _assistant_bubble_avatar_html(avatar_path: str) -> str:
    if os.path.exists(avatar_path):
        try:
            with open(avatar_path, "rb") as fh:
                encoded = base64.b64encode(fh.read()).decode("ascii")
            return f'<img class="assistant-bubble-avatar" src="data:image/png;base64,{encoded}" alt="" />'
        except Exception:
            pass
    return '<div class="smart-assistant-avatar assistant-bubble-avatar" aria-hidden="true"></div>'


def _handle_assistant_chat(user_text: str) -> bool:
    user_text = str(user_text or "").strip()
    if not user_text:
        return False
    _push_user_message(user_text)
    try:
        response = _assistant_respond_with_timeout(user_text)
        _push_assistant_message(response.get("text") or response.get("error") or "智能小助手暂不可用。")
    except Exception as exc:
        _push_assistant_message(f"智能小助手暂不可用：{exc}")
    sync_global_state()
    return True


def render_assistant_panel():
    _inject_assistant_drag_script()
    avatar_path = _assistant_avatar_path()
    if not st.session_state.get("assistant_open"):
        with st.container(key="assistant_bubble_container"):
            st.markdown('<div class="assistant-icon-button" aria-hidden="true"></div>', unsafe_allow_html=True)
            st.markdown(_assistant_bubble_avatar_html(avatar_path), unsafe_allow_html=True)
            st.button("打开智能小助手", key="assistant_bubble_button", width="stretch", help="打开智能小助手", on_click=_queue_action, args=("toggle_assistant",))
        return
    with st.container(border=True, key="assistant_panel_container"):
        h = st.columns([0.8, 3.2, 0.7])
        h[1].markdown('<div class="assistant-drag-handle" aria-label="移动"></div>', unsafe_allow_html=True)
        if os.path.exists(avatar_path):
            h[0].image(avatar_path, width=38)
        else:
            h[0].markdown('<div class="smart-assistant-avatar" aria-label="智能小助手形象"></div>', unsafe_allow_html=True)
        h[1].markdown("**智能小助手**")
        h[2].button("收起", key="assistant_close_icon_button", width="stretch", help="关闭", on_click=_queue_action, args=("toggle_assistant",))

        messages_slot = st.container()

        submitted_prompt = st.chat_input(
            "输入问题、代码任务或平台操作需求",
            key="assistant_user_text",
            width="stretch",
        )
        if submitted_prompt:
            _handle_assistant_chat(str(submitted_prompt))

        with messages_slot:
            recent = st.session_state.get("messages", [])[-6:]
            if recent:
                for msg in recent:
                    speaker = "我" if msg.get("role") == "user" else "智能小助手"
                    st.markdown(f"**{speaker}：** {msg.get('content', '')}")


def _mark_for_rerun():
    st.session_state["_rerun_requested"] = True


QA_ACTION_LABELS = {
    "assess_quality": "\u8fd0\u884c\u6570\u636e\u68c0\u67e5",
    "train_models": "\u9ed8\u8ba4\u8bad\u7ec3",
    "optimize_models": "\u8d1d\u53f6\u65af\u4f18\u5316",
    "retrain_optimized": "\u4f18\u5316\u540e\u91cd\u8bad",
    "generate_explanations": "\u5237\u65b0\u89e3\u91ca\u7ed3\u679c",
    "predict": "\u751f\u6210\u9884\u6d4b\u5730\u56fe",
    "show_model_details": "\u67e5\u770b\u8bc4\u4f30\u7ed3\u679c",
    "show_map": "\u67e5\u770b\u5730\u56fe",
    "show_uncertainty": "\u67e5\u770b\u4e0d\u786e\u5b9a\u6027",
    "export_bundle": "\u5bfc\u51fa\u7ed3\u679c",
    "generate_report": "\u751f\u6210\u62a5\u544a",
    "run_one_click_pipeline": "\u4ece\u539f\u59cb\u56e0\u5b50\u6570\u636e\u5f00\u59cb",
}


def _qa_seed_enabled() -> bool:
    return os.environ.get("WATER_EROSION_UI_QA_SEED") == "1" and bool(st.session_state.get("_qa_seeded"))


def _handle_qa_seed_action(action: str) -> bool:
    if not _qa_seed_enabled() or action not in QA_ACTION_LABELS:
        return False
    label = QA_ACTION_LABELS[action]
    st.session_state["_last_qa_action"] = (
        f"界面测试动作已响应：{label}。此提示仅用于交互验证，不代表科研运行结果。"
    )
    _push_assistant_message(st.session_state["_last_qa_action"])
    sync_global_state()
    _mark_for_rerun()
    return True


def _render_qa_action_notice():
    notice = st.session_state.get("_last_qa_action")
    if _qa_seed_enabled() and notice:
        st.success(notice)


def handle_action(action: str):
    import tools

    state = _current_state_snapshot()

    if action == "restart":
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        init_session_state()
        try:
            _session_agent().reset()
        except Exception:
            pass
        _mark_for_rerun()
        return

    if action == "go_home":
        set_current_layer("home")
        _mark_for_rerun()
        return

    if action.startswith("open_layer:"):
        set_current_layer(action.split(":", 1)[1])
        _mark_for_rerun()
        return

    if action.startswith("restore_snapshot:"):
        _restore_snapshot(action.split(":", 1)[1])
        _mark_for_rerun()
        return

    if action == "toggle_assistant":
        st.session_state["assistant_open"] = not bool(st.session_state.get("assistant_open"))
        sync_global_state()
        _mark_for_rerun()
        return

    if action == "assistant_chat":
        pending_text = st.session_state.pop("assistant_pending_text", "")
        user_text = str(pending_text or st.session_state.get("assistant_user_text") or "").strip()
        _handle_assistant_chat(user_text)
        _mark_for_rerun()
        return

    if _handle_qa_seed_action(action):
        return

    if action == "assistant_explain_result":
        models = st.session_state.get("models") or {}
        predictions = st.session_state.get("predictions") or {}
        explanation_meta = st.session_state.get("_explanation_meta") or {}
        if predictions:
            content = (
                f"Current scenario `{predictions.get('scenario', '-')}` has mean erosion "
                f"`{_fmt_metric(predictions.get('mean_erosion'), 2)}`."
            )
        elif explanation_meta:
            content = (
                f"Generated `{len(explanation_meta.get('explanation_files', []) or [])}` explanation files and "
                f"`{len(explanation_meta.get('spatial_files', []) or [])}` spatial files."
            )
        elif models:
            content = f"Model results are available. The locked model is `{st.session_state.get('best_model') or '-'}`."
        else:
            content = "当前还没有可解释结果，请先完成训练、解释或预测。"
        _push_assistant_message(content)
        sync_global_state()
        _mark_for_rerun()
        return

    if action.startswith("set_current_model:"):
        algorithm = action.split(":", 1)[1]
        with st.spinner("Running set_current_model..."):
            tool_result = tools.set_current_model(state, algorithm)
        sync_state_back(state)
        if tool_result.get("status") == "ok":
            explain_result = tools.generate_explanations(state)
            sync_state_back(state)
            detail = tool_result.get("best_model_display") or tool_result.get("best_algorithm") or algorithm
            message = f"\u5df2\u5207\u6362\u5f53\u524d\u4f7f\u7528\u6a21\u578b\uff1a{detail}\u3002"
            if explain_result.get("status") == "ok":
                message += " \u5df2\u81ea\u52a8\u5237\u65b0\u89e3\u91ca\u56fe\u4ef6\u3002"
            _push_assistant_message(message, {"tool_calls": [("set_current_model", tool_result)]})
            _update_stage_after_action("train_models", tool_result)
        else:
            _push_assistant_message(tool_result.get("message", "\u5207\u6362\u5f53\u524d\u4f7f\u7528\u6a21\u578b\u5931\u8d25\u3002"), {"tool_calls": [("set_current_model", tool_result)]})
        sync_global_state(_snapshot_reason_for_stage(st.session_state.get("workflow_stage", "")))
        _mark_for_rerun()
        return

    if action == "load_inputs":
        result = tools.inspect_uploads(state)
        st.session_state["_upload_inspection"] = result
        _update_stage_after_action(action, result)
        _push_assistant_message(result.get("message", "Input files inspected."), {"tool_calls": [("inspect_uploads", result)]})
        sync_global_state(_snapshot_reason_for_stage(st.session_state.get("workflow_stage", "")))
        _mark_for_rerun()
        return

    tool_map = {
        "assess_quality": ("assess_data_quality", {}, "quality_assessed"),
        "build_features": ("build_feature_table", {}, "features_built"),
        "train_models": ("train_candidates", {}, "models_trained"),
        "optimize_models": ("run_stage_two_optimization", {}, "models_optimized"),
        "retrain_optimized": ("run_stage_three_retrain", {}, "models_optimized"),
        "generate_explanations": ("generate_explanations", {}, "explained"),
        "predict": ("predict_future", {}, "predicted"),
        "show_model_details": ("visualize", {"target": "metrics"}, "models_trained"),
        "show_map": ("visualize", {"target": "map"}, "visualized"),
        "show_uncertainty": ("visualize", {"target": "uncertainty"}, "visualized"),
        "export_bundle": ("export_evidence_bundle", {}, "reported"),
        "generate_report": ("export_results", {}, "reported"),
        "run_one_click_pipeline": ("run_one_click_pipeline", {}, "reported"),
    }

    if action not in tool_map:
        _push_assistant_message(f"Unsupported action: {action}")
        _mark_for_rerun()
        return

    tool_name, kwargs, stage = tool_map[action]
    if action == "build_features" and not state.get("run_context"):
        kwargs = {"run_mode": "quick", "source_mode": "uploads"}
    if action == "build_features":
        st.session_state["_last_feature_build_error"] = None
    if action in {"train_models", "optimize_models", "retrain_optimized"}:
        selected_algorithms = _selected_training_algorithms()
        if selected_algorithms:
            kwargs["algorithms"] = selected_algorithms
        manual_params = _selected_model_param_overrides()
        if manual_params:
            if action == "train_models":
                kwargs["param_overrides"] = manual_params
            else:
                kwargs["base_param_overrides"] = manual_params
        if action in {"train_models", "optimize_models"}:
            kwargs["cv_folds"] = int(st.session_state.get("model_cv_folds", 4) or 4)
        if action == "optimize_models":
            kwargs["n_trials"] = int(st.session_state.get("model_opt_trials", 20) or 20)

    with st.spinner(f"Running {tool_name}..."):
        result = execute_tool_and_analyze(tool_name, state, tool_kwargs=kwargs, analysis_stage=stage)

    tool_result = result["tool_result"]
    sync_state_back(state)
    if action == "build_features":
        if tool_result.get("status") == "ok":
            st.session_state["_last_feature_build_error"] = None
        else:
            st.session_state["_last_feature_build_error"] = tool_result
            _clear_modeling_outputs_after_feature_failure()

    if action == "train_models" and tool_result.get("status") == "ok":
        select_result = tools.select_best(state)
        sync_state_back(state)
        tool_result = {**tool_result, "best_algorithm": select_result.get("best_algorithm"), "best_model": state.get("best_model")}
        result["analysis"] = f"{result['analysis']} 当前使用模型：{state.get('best_model', '-')}"
        explain_result = tools.generate_explanations(state)
        sync_state_back(state)
        if explain_result.get("status") == "ok":
            result["analysis"] = f"{result['analysis']}\n已自动生成解释图件。"

    if action == "optimize_models" and tool_result.get("status") == "ok":
        sync_state_back(state)
        merged = dict(st.session_state.get("_optimization_result") or {})
        merged.update(tool_result)
        st.session_state["_optimization_result"] = merged
        optimization_lines = ["**贝叶斯优化完成**"]
        for algo, vals in (tool_result.get("optimization_results") or {}).items():
            optimization_lines.append(
                f"- {_model_display_name(algo)}：最佳 R²={_fmt_metric(vals.get('best_r2'))}，试验次数={vals.get('n_trials', '-')}"
            )
        result["analysis"] = "\n".join(optimization_lines)

    if action == "retrain_optimized" and tool_result.get("status") == "ok":
        sync_state_back(state)
        merged = dict(st.session_state.get("_optimization_result") or {})
        merged.update(tool_result)
        st.session_state["_optimization_result"] = merged
        comparison_lines = [f"**优化后重训完成** — 当前使用模型：{tool_result.get('best_model_display', '-')}"]
        comp = tool_result.get("comparison", {})
        for display_name, vals in comp.items():
            if isinstance(vals, dict) and "improvement" in vals:
                delta = vals["improvement"]
                default_r2 = vals.get('default', {}).get('r2', 0) or 0
                optimized_r2 = vals.get('optimized', {}).get('r2', 0) or 0
                comparison_lines.append(f"- {display_name}：R² {default_r2:.4f} → {optimized_r2:.4f}（+{delta.get('r2_delta', 0):.4f}），RMSE 降低 {delta.get('rmse_reduction_pct', 0):.1f}%")
        result["analysis"] = "\n".join(comparison_lines)
        explain_result = tools.generate_explanations(state)
        sync_state_back(state)
        if explain_result.get("status") == "ok":
            result["analysis"] = f"{result['analysis']}\n已自动刷新解释图件。"

    metadata = {
        "tool_calls": [(tool_name, tool_result)],
        "images": result["images"],
        "maps": result["maps"],
    }
    _push_assistant_message(result["analysis"], metadata)
    _update_stage_after_action(action, tool_result)
    sync_global_state(_snapshot_reason_for_stage(st.session_state.get("workflow_stage", "")))
    _mark_for_rerun()


def render_main():
    if st.session_state.get("_rerun_requested"):
        st.session_state["_rerun_requested"] = False
        st.rerun()

    if st.session_state.pending_action:
        pa = st.session_state.pending_action
        st.session_state.pending_action = None
        handle_action(pa)
        if st.session_state.get("_rerun_requested"):
            st.session_state["_rerun_requested"] = False
            st.rerun()
        return

    if st.session_state.get("uploads") and st.session_state.get("workflow_stage") == "idle":
        st.session_state["workflow_stage"] = "data_loaded"

    sync_global_state()
    current_layer = st.session_state.get("current_layer", "home")

    if current_layer == "home":
        render_home()
    elif current_layer == "dataWorkshop":
        render_data_workshop()
    elif current_layer == "modelingLab":
        render_modeling_lab()
    elif current_layer == "explainStudio":
        render_explain_studio()
    elif current_layer == "predictExport":
        render_predict_export()
    else:
        set_current_layer("home")
        render_home()

    _render_qa_action_notice()
    render_assistant_panel()


def main():
    init_css()
    init_session_state()
    record_platform_open_heartbeat(interval_hours=12)
    render_sidebar()
    render_main()


if __name__ == "__main__":
    main()


