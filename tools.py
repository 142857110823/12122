"""
宸ュ叿瀹炵幇灞?- 7涓嫭绔嬪伐鍏峰嚱鏁?
姣忎釜宸ュ叿绾补澶勭悊鏁版嵁鍜屾ā鍨嬶紝涓嶄緷璧朙LM涔熶笉渚濊禆Streamlit
"""
import os
import re
import json
import time
import tempfile
import shutil
import hashlib
import zipfile
import uuid
import warnings
import traceback
from pathlib import Path
from collections import defaultdict
from datetime import datetime
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd
import rasterio
import joblib
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import lightgbm as lgb
import xgboost as xgb
from rasterio.merge import merge as raster_merge
from rasterio.windows import Window, bounds as window_bounds, from_bounds as window_from_bounds
from rasterio.warp import calculate_default_transform, reproject, Resampling, transform_bounds
from sklearn.base import clone
from sklearn.ensemble import RandomForestRegressor, ExtraTreesRegressor, AdaBoostRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.neighbors import KNeighborsRegressor
from sklearn.svm import SVR

warnings.filterwarnings("ignore")

# 瀵煎叆鏈湴妯″潡
from utils.raster_io import (
    read_raster, reproject_raster, align_rasters,
    build_feature_matrix, DEFAULT_CRS, DEFAULT_RESOLUTION_M,
)
from utils.viz import (
    plot_metrics_comparison, plot_feature_importance,
    plot_scatter_prediction, plot_residual_distribution,
    create_folium_map, fig_to_base64, ALGORITHM_COLORS,
)


# ============================================================
# 宸ュ叿Schema瀹氫箟锛圤penAI Function Calling鏍煎紡锛?
# ============================================================
def load_tool_schemas() -> list:
    """Auto-generated doc."""
    import json
    schema_path = os.path.join(os.path.dirname(__file__), "prompts", "tool_descriptions.json")
    with open(schema_path, "r", encoding="utf-8") as f:
        return json.load(f)


# ============================================================
# 鍛藉悕绾﹀畾瑙ｆ瀽
# ============================================================
VALID_VARIABLES = {"label", "R", "K", "LS", "C", "P", "NDVI", "LST", "DEM"}


def parse_filename(filename: str) -> Optional[Dict[str, str]]:
    """Auto-generated doc."""
    name = filename.replace(".tif", "").replace(".TIF", "")
    parts = name.split("_")

    if len(parts) < 1:
        return None

    variable = parts[0]
    if variable not in VALID_VARIABLES:
        return None

    result = {"variable": variable, "filename": filename}

    # 灏濊瘯瑙ｆ瀽year鍜宻cenario
    if len(parts) >= 2:
        # 鍒ゆ柇绗簩閮ㄥ垎鏄惁涓?浣嶆暟瀛楋紙year锛?
        if re.match(r"^\d{4}$", parts[1]):
            result["year"] = parts[1]
            if len(parts) >= 3:
                result["scenario"] = parts[2]
        else:
            # 鍙兘鏄痵cenario
            result["scenario"] = parts[1]

    return result


# ============================================================
# P0-P3 shared constants and helpers
# ============================================================
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
DATA_ROOT = os.path.join(PROJECT_ROOT, "data")
RUNS_ROOT = os.path.join(DATA_ROOT, "runs")
LEGACY_FEATURES_DIR = os.path.join(DATA_ROOT, "features")
LEGACY_MODELS_DIR = os.path.join(DATA_ROOT, "models")
LEGACY_REPORT_PATH = os.path.join(DATA_ROOT, "report.md")
DEFAULT_RUSLE_SOURCE_DIR = r"D:/1.科创开发之ML_Platform/RUSLE-五大因子原始数据"
DEFAULT_DATA_CLASSIFICATION = "research_sensitive"
DEFAULT_DATA_RETENTION_DAYS = 30
SECURITY_AUDIT_LOG = "security_audit.jsonl"
EVIDENCE_BUNDLE_TEXT_EXTENSIONS = (
    ".json",
    ".md",
    ".csv",
    ".txt",
    ".jsonl",
    ".html",
    ".log",
    ".xml",
    ".yaml",
    ".yml",
    ".toml",
)
RUN_EVIDENCE_DIRS = (
    "inputs", "features", "models", "predictions",
    "explanations", "spatial", "gates", "reports", "bundle",
)
DEFAULT_MODEL_POOL = [
    "lightgbm", "xgboost", "random_forest",
    "catboost", "extratrees", "adaboost", "svr", "knn",
]


def _bool_env(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value in (None, ""):
        return default
    return str(value).strip().lower() in {"1", "true", "yes", "y", "on"}


def _int_env(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        return default


def _data_security_metadata() -> dict:
    classification = str(os.getenv("DATA_SECURITY_MODE", DEFAULT_DATA_CLASSIFICATION) or DEFAULT_DATA_CLASSIFICATION).strip().lower()
    retention_days = max(1, _int_env("DATA_RETENTION_DAYS", DEFAULT_DATA_RETENTION_DAYS))
    return {
        "classification": classification,
        "retention_days": retention_days,
        "external_llm_allowed": _bool_env("ALLOW_EXTERNAL_LLM", False),
        "assistant_context_policy": str(os.getenv("ASSISTANT_CONTEXT_POLICY", "metadata_only") or "metadata_only").strip().lower(),
    }


def _path_inside(base: str, target: str) -> bool:
    try:
        return os.path.commonpath([os.path.realpath(base), os.path.realpath(target)]) == os.path.realpath(base)
    except (TypeError, ValueError):
        return False


def _bundle_path_ref(ctx: dict, path: str) -> str:
    if not path:
        return ""
    run_root = ((ctx.get("paths") or {}).get("root")) or ""
    if run_root and _path_inside(run_root, path):
        return os.path.relpath(os.path.realpath(path), os.path.realpath(run_root)).replace(os.sep, "/")
    if _path_inside(DATA_ROOT, path):
        return os.path.relpath(os.path.realpath(path), os.path.realpath(PROJECT_ROOT)).replace(os.sep, "/")
    return "[outside-data-root-redacted]"


def _bundle_path_refs(ctx: dict, paths: list) -> list:
    refs = []
    for path in paths or []:
        ref = _bundle_path_ref(ctx, path)
        if ref and ref not in refs:
            refs.append(ref)
    return refs


def _redact_bundle_payload(ctx: dict, value: Any) -> Any:
    if isinstance(value, dict):
        return {k: _redact_bundle_payload(ctx, v) for k, v in value.items()}
    if isinstance(value, list):
        return [_redact_bundle_payload(ctx, v) for v in value]
    if isinstance(value, str):
        if re.search(r"sk-[A-Za-z0-9_-]{10,}", value):
            return re.sub(r"sk-[A-Za-z0-9_-]{10,}", "[REDACTED_SECRET]", value)
        if os.path.isabs(value):
            return _bundle_path_ref(ctx, value)
    return value


def _redact_bundle_text(ctx: dict, text: str) -> str:
    redacted = re.sub(r"sk-[A-Za-z0-9_-]{10,}", "[REDACTED_SECRET]", text or "")
    redacted = re.sub(
        r"(?i)\b(OPENAI_API_KEY|LLM_API_KEY)\s*=\s*[^\s,;]+",
        r"\1=[REDACTED_SECRET]",
        redacted,
    )
    for path in [
        ((ctx.get("paths") or {}).get("root")),
        PROJECT_ROOT,
        DATA_ROOT,
        os.path.expanduser("~"),
    ]:
        if path:
            redacted = redacted.replace(os.path.realpath(path), _bundle_path_ref(ctx, path))
            redacted = redacted.replace(os.path.realpath(path).replace(os.sep, "/"), _bundle_path_ref(ctx, path))
    redacted = re.sub(r"(?i)\b[A-Z]:\\[^\s\"'`,;)\]}]+", "[absolute-path-redacted]", redacted)
    redacted = re.sub(r"(?i)\b[A-Z]:/[^\s\"'`,;)\]}]+", "[absolute-path-redacted]", redacted)
    redacted = re.sub(r"\\\\[^\s\"'`,;)\]}]+", "[absolute-path-redacted]", redacted)
    redacted = re.sub(r"(?<![\w:])/(home|tmp|var|mnt|opt|Users)/[^\s\"'`,;)\]}]+", "[absolute-path-redacted]", redacted)
    return redacted

# ----------------------------------------------------------------
# 模型注册表：每模型独立默认参数 + 贝叶斯优化边界 + 参数类型
# ----------------------------------------------------------------
MODEL_REGISTRY = {
    "random_forest": {
        "display_name": "随机森林",
        "default_params": {
            "n_estimators": 100, "max_depth": 6, "min_samples_split": 2,
            "min_samples_leaf": 1, "max_features": "sqrt", "bootstrap": True,
        },
        "bayes_opt_bounds": {
            "n_estimators": (50, 500), "max_depth": (3, 20),
            "min_samples_split": (2, 10), "min_samples_leaf": (1, 5),
            "max_features": (0.3, 1.0),
        },
        "param_types": {
            "n_estimators": "int", "max_depth": "int",
            "min_samples_split": "int", "min_samples_leaf": "int",
            "max_features": "float", "bootstrap": "categorical",
        },
    },
    "xgboost": {
        "display_name": "XGBoost",
        "default_params": {
            "n_estimators": 100, "max_depth": 6, "learning_rate": 0.1,
            "subsample": 0.8, "colsample_bytree": 0.8,
            "reg_alpha": 0, "reg_lambda": 1, "gamma": 0,
        },
        "bayes_opt_bounds": {
            "n_estimators": (50, 500), "max_depth": (3, 15),
            "learning_rate": (0.01, 0.3), "subsample": (0.5, 1.0),
            "colsample_bytree": (0.5, 1.0), "reg_alpha": (0, 1),
            "reg_lambda": (0, 10), "gamma": (0, 5),
        },
        "param_types": {
            "n_estimators": "int", "max_depth": "int",
            "learning_rate": "float", "subsample": "float",
            "colsample_bytree": "float", "reg_alpha": "float",
            "reg_lambda": "float", "gamma": "float",
        },
    },
    "lightgbm": {
        "display_name": "LightGBM",
        "default_params": {
            "n_estimators": 100, "max_depth": -1, "num_leaves": 31,
            "learning_rate": 0.1, "feature_fraction": 1.0,
            "bagging_fraction": 1.0, "bagging_freq": 0,
            "min_child_samples": 20, "reg_alpha": 0, "reg_lambda": 0,
        },
        "bayes_opt_bounds": {
            "n_estimators": (50, 500), "max_depth": (3, 15),
            "num_leaves": (20, 150), "learning_rate": (0.01, 0.3),
            "feature_fraction": (0.5, 1.0), "bagging_fraction": (0.5, 1.0),
            "bagging_freq": (0, 5), "min_child_samples": (5, 50),
            "reg_alpha": (0, 1), "reg_lambda": (0, 10),
        },
        "param_types": {
            "n_estimators": "int", "max_depth": "int",
            "num_leaves": "int", "learning_rate": "float",
            "feature_fraction": "float", "bagging_fraction": "float",
            "bagging_freq": "int", "min_child_samples": "int",
            "reg_alpha": "float", "reg_lambda": "float",
        },
    },
    "svr": {
        "display_name": "支持向量机",
        "default_params": {
            "C": 1.0, "kernel": "rbf", "gamma": "scale",
            "epsilon": 0.1, "shrinking": True,
        },
        "bayes_opt_bounds": {
            "C": (0.1, 100), "gamma": (1e-4, 1),
            "epsilon": (0.01, 1.0),
            "kernel": ["rbf", "linear", "poly"],
            "degree": (2, 5),
        },
        "param_types": {
            "C": "float", "kernel": "categorical",
            "gamma": "float", "epsilon": "float",
            "shrinking": "categorical", "degree": "int",
        },
        "conditional_params": {
            "degree": {"when": {"kernel": "poly"}, "default": 3},
        },
    },
    "catboost": {
        "display_name": "CatBoost",
        "default_params": {
            "depth": 8, "learning_rate": 0.05, "n_estimators": 400,
            "l2_leaf_reg": 3, "bagging_temperature": 1,
            "border_count": 254, "random_strength": 1,
        },
        "bayes_opt_bounds": {
            "depth": (4, 12), "learning_rate": (0.01, 0.3),
            "n_estimators": (100, 800), "l2_leaf_reg": (1, 10),
            "bagging_temperature": (0, 2),
            "random_strength": (0.5, 5),
        },
        "param_types": {
            "depth": "int", "learning_rate": "float",
            "n_estimators": "int", "l2_leaf_reg": "float",
            "bagging_temperature": "float",
            "random_strength": "float",
        },
    },
    "extratrees": {
        "display_name": "ExtraTrees",
        "default_params": {
            "n_estimators": 100, "max_depth": 6,
            "min_samples_split": 2, "min_samples_leaf": 1,
            "max_features": "sqrt", "bootstrap": False,
        },
        "bayes_opt_bounds": {
            "n_estimators": (50, 500), "max_depth": (3, 20),
            "min_samples_split": (2, 10), "min_samples_leaf": (1, 5),
            "max_features": (0.3, 1.0),
        },
        "param_types": {
            "n_estimators": "int", "max_depth": "int",
            "min_samples_split": "int", "min_samples_leaf": "int",
            "max_features": "float",
        },
    },
    "adaboost": {
        "display_name": "AdaBoost",
        "default_params": {
            "n_estimators": 250, "learning_rate": 0.05,
        },
        "bayes_opt_bounds": {
            "n_estimators": (50, 500),
            "learning_rate": (0.01, 1.0),
        },
        "param_types": {
            "n_estimators": "int",
            "learning_rate": "float",
        },
    },
    "knn": {
        "display_name": "KNN",
        "default_params": {
            "n_neighbors": 8, "weights": "distance",
        },
        "bayes_opt_bounds": {
            "n_neighbors": (3, 30),
            "weights": ["uniform", "distance"],
            "algorithm": ["auto", "ball_tree", "kd_tree"],
        },
        "param_types": {
            "n_neighbors": "int",
            "weights": "categorical",
            "algorithm": "categorical",
        },
    },
}


def _coerce_bool_param(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, np.integer)):
        if int(value) in {0, 1}:
            return bool(value)
    if isinstance(value, (float, np.floating)):
        if float(value) in {0.0, 1.0}:
            return bool(value)
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "1", "yes", "y", "on"}:
            return True
        if normalized in {"false", "0", "no", "n", "off"}:
            return False
    raise ValueError(f"invalid boolean value: {value!r}")


def _coerce_and_validate_param_override(algo: str, cfg: dict, name: str, value: Any) -> Tuple[bool, Any, str]:
    ptypes = cfg.get("param_types", {})
    ptype = ptypes.get(name)
    default_value = (cfg.get("default_params", {}) or {}).get(name)
    bound = (cfg.get("bayes_opt_bounds", {}) or {}).get(name)
    try:
        if isinstance(default_value, bool):
            coerced = _coerce_bool_param(value)
        elif name == "max_features" and isinstance(value, str) and value.strip().lower() in {"sqrt", "log2"}:
            coerced = value.strip().lower()
        elif ptype == "int":
            coerced = int(value)
        elif ptype == "float":
            try:
                coerced = float(value)
            except (TypeError, ValueError):
                coerced = value
        elif ptype == "categorical":
            coerced = value
        else:
            coerced = value
    except (TypeError, ValueError) as exc:
        return False, None, f"{name}: {exc}"

    if isinstance(bound, list) and bound and coerced not in bound:
        return False, None, f"{name}: expected one of {bound}, got {coerced!r}"

    if name == "max_features" and isinstance(coerced, str):
        if coerced in {"sqrt", "log2"}:
            return True, coerced, ""
        return False, None, f"{name}: expected numeric ratio or one of ['sqrt', 'log2'], got {coerced!r}"

    if ptype in {"int", "float"}:
        if not isinstance(coerced, (int, float, np.integer, np.floating)):
            return False, None, f"{name}: expected numeric value, got {coerced!r}"
        numeric = float(coerced)
        if not np.isfinite(numeric):
            return False, None, f"{name}: expected finite numeric value, got {coerced!r}"

        ratio_params = {"max_features", "subsample", "colsample_bytree", "feature_fraction", "bagging_fraction"}
        positive_int_params = {
            "n_estimators", "min_samples_split", "min_samples_leaf", "min_child_samples",
            "n_neighbors", "num_leaves", "depth", "border_count",
        }
        non_negative_int_params = {"bagging_freq"}
        non_negative_float_params = {"reg_alpha", "reg_lambda", "gamma", "bagging_temperature"}

        if name in ratio_params and (numeric <= 0.0 or numeric > 1.0):
            return False, None, f"{name}: expected value in (0, 1], got {coerced!r}"
        if name in positive_int_params and int(coerced) <= 0:
            return False, None, f"{name}: expected positive integer, got {coerced!r}"
        if name == "max_depth":
            if algo == "lightgbm":
                if int(coerced) == 0 or int(coerced) < -1:
                    return False, None, f"{name}: expected -1 or positive integer, got {coerced!r}"
            elif int(coerced) <= 0:
                return False, None, f"{name}: expected positive integer, got {coerced!r}"
        if name == "degree" and int(coerced) <= 0:
            return False, None, f"{name}: expected positive integer, got {coerced!r}"
        if name in non_negative_int_params and int(coerced) < 0:
            return False, None, f"{name}: expected non-negative integer, got {coerced!r}"
        if name in non_negative_float_params and numeric < 0.0:
            return False, None, f"{name}: expected non-negative value, got {coerced!r}"
        if ptype == "float" and name not in ratio_params | non_negative_float_params and numeric <= 0.0:
            return False, None, f"{name}: expected positive value, got {coerced!r}"

    return True, coerced, ""


def _normalize_param_overrides_with_errors(param_overrides: Optional[dict], algorithms: list[str]) -> Tuple[dict, dict]:
    """Filter/coerce user-provided model parameters and report invalid known parameters."""
    if not param_overrides:
        return {}, {}
    allowed_algos = {str(algo).lower() for algo in (algorithms or [])}
    normalized = {}
    invalid = {}
    for algo, values in (param_overrides or {}).items():
        algo = str(algo).lower()
        if algo not in allowed_algos or algo not in MODEL_REGISTRY or not isinstance(values, dict):
            continue
        cfg = MODEL_REGISTRY[algo]
        allowed_params = set(cfg.get("default_params", {})) | set(cfg.get("bayes_opt_bounds", {}))
        clean = {}
        for name, value in values.items():
            if name not in allowed_params or value is None:
                continue
            ok, coerced, reason = _coerce_and_validate_param_override(algo, cfg, name, value)
            if not ok:
                invalid.setdefault(algo, []).append(reason)
                continue
            clean[name] = coerced
        if clean:
            normalized[algo] = clean
    return normalized, invalid


def _normalize_param_overrides(param_overrides: Optional[dict], algorithms: list[str]) -> dict:
    """Filter and coerce user-provided model parameters against MODEL_REGISTRY."""
    normalized, _invalid = _normalize_param_overrides_with_errors(param_overrides, algorithms)
    return normalized

RUN_LOG_NAME = "run_log.jsonl"
PASS = "PASS"
PASS_WITH_RISKS = "PASS_WITH_RISKS"
BLOCK = "BLOCK"
DEFAULT_OUTPUT_DPI = 300


def _ensure_dir(path: str) -> str:
    os.makedirs(path, exist_ok=True)
    return path


def _json_default(value: Any):
    if isinstance(value, (np.floating, np.float32, np.float64)):
        return float(value)
    if isinstance(value, (np.integer, np.int32, np.int64)):
        return int(value)
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, set):
        return sorted(list(value))
    return str(value)


def _write_json(path: str, payload: dict):
    _ensure_dir(os.path.dirname(path))
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2, default=_json_default)


def _write_text(path: str, content: str):
    _ensure_dir(os.path.dirname(path))
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)


def _append_jsonl(path: str, payload: dict):
    _ensure_dir(os.path.dirname(path))
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(payload, ensure_ascii=False, default=_json_default) + "\n")


def _record_stage_report(state: dict, stage: str, gate: Optional[dict], status: str, summary: str):
    """Append the fixed stage report template required by the P0-P3 evidence chain."""
    ctx = state.get("run_context") or {}
    paths = ctx.get("paths") or {}
    reports_dir = paths.get("reports")
    if not reports_dir:
        return

    gate = gate or {}
    payload = {
        "ts": _now_iso(),
        "stage": str(stage).upper(),
        "event": "stage_report",
        "status": status,
        "run_id": ctx.get("run_id"),
        "template": "stage_report_v1",
        "summary": summary,
        "gate_verdict": gate.get("verdict", ctx.get("gate_verdict", PASS)),
        "block_items": gate.get("block_items", []),
        "evidence_count": len(ctx.get("evidence_paths", [])),
        "next_allowed": gate.get("verdict") != BLOCK and status != "blocked",
    }
    _append_jsonl(os.path.join(reports_dir, RUN_LOG_NAME), payload)


def _now_iso() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _sanitize_run_id(run_id: Optional[str]) -> str:
    if run_id:
        rid = re.sub(r"[^0-9a-zA-Z_-]", "-", str(run_id)).strip("-")
        if rid:
            return rid
    return f"{datetime.now().strftime('run_%Y%m%d_%H%M%S_%f')}_{uuid.uuid4().hex[:8]}"


def _file_hash(filepath: str, max_bytes: int = 4 * 1024 * 1024) -> str:
    h = hashlib.sha256()
    read_bytes = 0
    with open(filepath, "rb") as f:
        while True:
            chunk = f.read(1024 * 1024)
            if not chunk:
                break
            h.update(chunk)
            read_bytes += len(chunk)
            if read_bytes >= max_bytes:
                break
    return h.hexdigest()


def _snapshot_uploads(uploads: Dict[str, dict]) -> List[dict]:
    snapshot = []
    for fname in sorted(uploads.keys()):
        fmeta = uploads.get(fname, {})
        fp = fmeta.get("filepath", "")
        if not fp or not os.path.exists(fp):
            snapshot.append({"filename": fname, "exists": False})
            continue
        stat = os.stat(fp)
        snapshot.append({
            "filename": fname,
            "filepath": fp,
            "size_bytes": int(stat.st_size),
            "mtime": datetime.fromtimestamp(stat.st_mtime).isoformat(),
            "sha256_head": _file_hash(fp),
        })
    return snapshot


def _snapshot_raw_source(source_dir: str) -> List[dict]:
    snapshot = []
    if not source_dir or not os.path.isdir(source_dir):
        return snapshot
    for root, _, files in os.walk(source_dir):
        for name in files:
            if not name.lower().endswith((".tif", ".tiff")):
                continue
            fp = os.path.join(root, name)
            try:
                stat = os.stat(fp)
                snapshot.append({
                    "filename": name,
                    "filepath": fp,
                    "size_bytes": int(stat.st_size),
                    "mtime": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                })
            except Exception:
                continue
    snapshot.sort(key=lambda x: x["filepath"])
    return snapshot


def _manifest_hash(payload: Any) -> str:
    content = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=_json_default)
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def _run_paths(run_id: str) -> Dict[str, str]:
    root = os.path.join(RUNS_ROOT, run_id)
    paths = {"root": root}
    for name in RUN_EVIDENCE_DIRS:
        paths[name] = os.path.join(root, name)
    return paths


def _ensure_run_tree(paths: Dict[str, str]):
    _ensure_dir(paths["root"])
    for name in RUN_EVIDENCE_DIRS:
        _ensure_dir(paths[name])


def _resolve_run_context(state: dict,
                         run_id: Optional[str] = None,
                         run_mode: str = "quick",
                         source_mode: str = "rusle_raw",
                         output_dpi: int = DEFAULT_OUTPUT_DPI,
                         source_dir: Optional[str] = None,
                         force_new: bool = False) -> dict:
    existing = state.get("run_context")
    if existing and not force_new and not run_id:
        return existing

    rid = _sanitize_run_id(run_id)
    paths = _run_paths(rid)
    _ensure_run_tree(paths)
    source_dir = source_dir or DEFAULT_RUSLE_SOURCE_DIR

    uploads = state.get("uploads", {}) or {}
    upload_snapshot = _snapshot_uploads(uploads)
    source_snapshot = _snapshot_raw_source(source_dir) if source_mode == "rusle_raw" else []
    security_meta = _data_security_metadata()

    manifest = {
        "run_id": rid,
        "created_at": _now_iso(),
        "classification": security_meta["classification"],
        "retention_days": security_meta["retention_days"],
        "external_llm_allowed": security_meta["external_llm_allowed"],
        "assistant_context_policy": security_meta["assistant_context_policy"],
        "run_mode": run_mode,
        "source_mode": source_mode,
        "output_dpi": int(output_dpi),
        "source_dir": source_dir,
        "uploads": upload_snapshot,
        "raw_source_files": source_snapshot,
        "model_versions": {
            "lightgbm": getattr(lgb, "__version__", "unknown"),
            "xgboost": getattr(xgb, "__version__", "unknown"),
            "numpy": getattr(np, "__version__", "unknown"),
            "pandas": getattr(pd, "__version__", "unknown"),
        },
    }
    manifest["input_manifest_hash"] = _manifest_hash({
        "uploads": upload_snapshot,
        "raw_source_files": source_snapshot,
        "run_mode": run_mode,
        "source_mode": source_mode,
    })

    manifest_path = os.path.join(paths["inputs"], "run_manifest.json")
    _write_json(manifest_path, manifest)
    _append_jsonl(os.path.join(paths["reports"], RUN_LOG_NAME), {
        "ts": _now_iso(),
        "stage": "P0",
        "event": "prepare_run_context",
        "status": "ok",
        "run_id": rid,
    })

    context = {
        "run_id": rid,
        "run_mode": run_mode,
        "source_mode": source_mode,
        "output_dpi": int(output_dpi),
        "source_dir": source_dir,
        "paths": paths,
        "manifest_path": manifest_path,
        "manifest_hash": manifest["input_manifest_hash"],
        "classification": security_meta["classification"],
        "retention_days": security_meta["retention_days"],
        "external_llm_allowed": security_meta["external_llm_allowed"],
        "gate_verdict": PASS,
        "gate_reports": {},
        "evidence_paths": [manifest_path],
    }
    state["run_context"] = context
    return context


def _get_or_prepare_context(state: dict,
                            run_mode: str = "quick",
                            source_mode: str = "rusle_raw",
                            output_dpi: int = DEFAULT_OUTPUT_DPI,
                            run_id: Optional[str] = None,
                            source_dir: Optional[str] = None) -> dict:
    if state.get("run_context"):
        return state["run_context"]
    return _resolve_run_context(
        state=state,
        run_id=run_id,
        run_mode=run_mode,
        source_mode=source_mode,
        output_dpi=output_dpi,
        source_dir=source_dir,
    )


def _get_complete_run_context(state: dict,
                              source_mode: str = "uploads",
                              required_dirs: Optional[Sequence[str]] = None,
                              run_id: Optional[str] = None,
                              output_dpi: Optional[int] = None) -> dict:
    ctx = state.get("run_context") or {}
    paths = ctx.get("paths") or {}
    required = required_dirs or ("reports", "predictions")
    if not ctx or any(not paths.get(name) for name in required):
        return _resolve_run_context(
            state=state,
            run_id=run_id or ctx.get("run_id"),
            run_mode=ctx.get("run_mode", "quick"),
            source_mode=ctx.get("source_mode", source_mode),
            output_dpi=int(ctx.get("output_dpi", output_dpi or DEFAULT_OUTPUT_DPI)),
            source_dir=ctx.get("source_dir"),
            force_new=True,
        )
    _ensure_run_tree(paths)
    return ctx


def _record_evidence_path(state: dict, path: str):
    if not path:
        return
    ctx = state.get("run_context")
    if not ctx:
        return
    ev = ctx.setdefault("evidence_paths", [])
    if path not in ev:
        ev.append(path)


def _safe_cleanup_runs(max_keep: int = 12) -> dict:
    _ensure_dir(RUNS_ROOT)
    removed = []
    skipped = []
    dirs = [d for d in os.listdir(RUNS_ROOT) if os.path.isdir(os.path.join(RUNS_ROOT, d))]
    dirs_sorted = sorted(dirs, key=lambda x: os.path.getmtime(os.path.join(RUNS_ROOT, x)), reverse=True)
    runs_abs = os.path.realpath(RUNS_ROOT)
    for name in dirs_sorted[max_keep:]:
        raw_target = os.path.join(RUNS_ROOT, name)
        target = os.path.realpath(raw_target)
        try:
            inside_runs = os.path.commonpath([runs_abs, target]) == runs_abs
        except ValueError:
            inside_runs = False
        if not name.startswith("run_") or not inside_runs or os.path.islink(raw_target):
            skipped.append(target)
            continue
        shutil.rmtree(target, ignore_errors=True)
        removed.append(target)
    return {"removed": removed, "skipped": skipped, "kept": max_keep, "cleanup_root": runs_abs}


def _copy_to_legacy(path_from: str, legacy_path: str):
    if not path_from or not os.path.exists(path_from):
        return
    if os.path.realpath(path_from) == os.path.realpath(legacy_path):
        return
    _ensure_dir(os.path.dirname(legacy_path))
    shutil.copy2(path_from, legacy_path)


def _persist_selected_model_artifacts(state: dict,
                                      model,
                                      model_dir: str,
                                      meta_payload: dict) -> dict:
    _ensure_dir(model_dir)
    best_model_path = os.path.join(model_dir, "best_model.joblib")
    best_meta_path = os.path.join(model_dir, "best_model_meta.json")
    joblib.dump(model, best_model_path)
    _write_json(best_meta_path, meta_payload)
    _copy_to_legacy(best_model_path, os.path.join(LEGACY_MODELS_DIR, "best_model.joblib"))
    _copy_to_legacy(best_meta_path, os.path.join(LEGACY_MODELS_DIR, "best_model_meta.json"))
    _record_evidence_path(state, best_model_path)
    _record_evidence_path(state, best_meta_path)
    return {"best_model_path": best_model_path, "best_model_meta_path": best_meta_path}


def _calc_nrmse(rmse: float, y_true: np.ndarray) -> float:
    denom = float(np.mean(y_true)) if len(y_true) else 0.0
    if abs(denom) < 1e-12:
        return float("nan")
    return float(rmse / denom * 100.0)


def _calc_pbias(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    denom = float(np.sum(y_true))
    if abs(denom) < 1e-12:
        return float("nan")
    return float(100.0 * np.sum(y_pred - y_true) / denom)


def _metric_packet(y_true: np.ndarray, y_pred: np.ndarray, train_seconds: float) -> Dict[str, float]:
    from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
    mae = float(mean_absolute_error(y_true, y_pred))
    rmse = float(np.sqrt(mean_squared_error(y_true, y_pred)))
    r2 = float(r2_score(y_true, y_pred))
    return {
        "mae": mae,
        "rmse": rmse,
        "r2": r2,
        "nrmse": _calc_nrmse(rmse, y_true),
        "pbias": _calc_pbias(y_true, y_pred),
        "train_seconds": float(train_seconds),
    }


def _feature_columns_from_df(df: pd.DataFrame, target_col: str = "label") -> List[str]:
    """Select numeric model features while keeping provenance fields as metadata."""
    meta_cols = {
        "grid_id", "year", "x", "y", "row", "col",
        "tile_id", "batch_id", "source", "scenario", "geometry",
    }
    candidates = [c for c in df.columns if c not in meta_cols and c != target_col]
    return [c for c in candidates if pd.api.types.is_numeric_dtype(df[c])]


def build_upload_inventory(state: dict) -> dict:
    """Build a real CSV-ready inventory from uploaded files and raster metadata."""
    uploads = state.get("uploads", {}) or {}
    rows = []
    errors = []
    for name, info in sorted(uploads.items()):
        parsed = parse_filename(name) or {}
        filepath = info.get("filepath", "")
        row = {
            "file": name,
            "variable": parsed.get("variable", "unknown"),
            "year": parsed.get("year", "-"),
            "scenario": parsed.get("scenario", "-"),
            "path": f"data/uploads/{name}",
            "size_bytes": int(info.get("size", 0) or 0),
            "uploaded_at": info.get("uploaded_at", ""),
            "crs": "",
            "width": None,
            "height": None,
            "resolution_x": None,
            "resolution_y": None,
            "nodata": None,
            "valid_pixel_pct": None,
            "min": None,
            "max": None,
            "mean": None,
            "read_status": "missing" if not filepath else "pending",
            "error": "",
        }
        if filepath and os.path.exists(filepath) and name.lower().endswith((".tif", ".tiff")):
            try:
                meta = read_raster(filepath)
                data = np.asarray(meta.get("data"), dtype=np.float32)
                valid = data[np.isfinite(data)]
                total = int(data.size) if data is not None else 0
                resolution = meta.get("resolution") or (None, None)
                shape = meta.get("shape") or data.shape
                row.update({
                    "crs": meta.get("crs") or "",
                    "width": int(shape[1]) if len(shape) >= 2 else None,
                    "height": int(shape[0]) if len(shape) >= 2 else None,
                    "resolution_x": float(resolution[0]) if resolution[0] is not None else None,
                    "resolution_y": float(resolution[1]) if resolution[1] is not None else None,
                    "nodata": meta.get("nodata"),
                    "valid_pixel_pct": round(float(len(valid) / total * 100.0), 4) if total else 0.0,
                    "min": float(np.min(valid)) if len(valid) else None,
                    "max": float(np.max(valid)) if len(valid) else None,
                    "mean": float(np.mean(valid)) if len(valid) else None,
                    "read_status": "ok" if len(valid) else "empty",
                })
            except Exception as exc:
                error_text = _redact_bundle_text({}, str(exc))
                row["read_status"] = "error"
                row["error"] = error_text
                errors.append({"file": name, "error": error_text})
        elif filepath and not os.path.exists(filepath):
            row["error"] = "file path does not exist"
            errors.append({"file": name, "error": row["error"]})
        elif not name.lower().endswith((".tif", ".tiff")):
            row["read_status"] = "non_raster"
        rows.append(row)
    return {
        "status": "ok",
        "rows": rows,
        "total_files": len(rows),
        "readable_rasters": sum(1 for r in rows if r.get("read_status") == "ok"),
        "errors": errors,
        "message": f"Inventory built for {len(rows)} uploaded file(s).",
    }


def _error_corrector_payload(stage: str, checks: List[dict]) -> dict:
    verdict = PASS
    has_risk = False
    block_items = []
    for c in checks:
        status = c.get("status", PASS)
        if status == BLOCK:
            verdict = BLOCK
            block_items.append(c.get("name", "unknown"))
        elif status == PASS_WITH_RISKS:
            has_risk = True
    if verdict != BLOCK and has_risk:
        verdict = PASS_WITH_RISKS
    return {
        "stage": stage,
        "verdict": verdict,
        "checks": checks,
        "block_items": block_items,
        "generated_at": _now_iso(),
    }


# ============================================================
# 宸ュ叿1: inspect_uploads
# ============================================================
def inspect_uploads(state: dict) -> dict:
    """Auto-generated doc."""
    try:
        uploads = state.get("uploads", {}) or {}
        if not uploads:
            return {
                "status": "ok",
                "total_files": 0,
                "message": "No uploaded files found.",
                "variables": {},
                "years": [],
                "can_train": False,
                "can_predict": False,
            }

        parsed = []
        unrecognized = []
        for fname, fmeta in uploads.items():
            info = parse_filename(fname)
            if info:
                info["filepath"] = fmeta.get("filepath", "")
                info["size_kb"] = float(fmeta.get("size", 0)) / 1024.0
                parsed.append(info)
            else:
                unrecognized.append(fname)

        variables = {}
        for p in parsed:
            var = p["variable"]
            if var not in variables:
                variables[var] = {"files": [], "years": set(), "scenarios": set()}
            variables[var]["files"].append(p)
            if "year" in p:
                variables[var]["years"].add(p["year"])
            if "scenario" in p:
                variables[var]["scenarios"].add(p["scenario"])

        label_years = variables.get("label", {}).get("years", set())
        future_scenarios = set()
        for v in variables.values():
            future_scenarios.update(v["scenarios"])

        can_train = len(label_years) >= 1 and any(v not in {"label", "DEM"} for v in variables.keys())
        has_model = bool(state.get("best_model")) or bool(state.get("models"))
        can_predict = bool(future_scenarios) and has_model

        var_summary = {}
        for var, info in variables.items():
            var_summary[var] = {
                "file_count": len(info["files"]),
                "years": ", ".join(sorted(info["years"])) if info["years"] else "none",
                "scenarios": ", ".join(sorted(info["scenarios"])) if info["scenarios"] else "none",
            }

        message_parts = [f"recognized {len(parsed)} files"]
        if label_years:
            message_parts.append(f"label years: {', '.join(sorted(label_years))}")
        if future_scenarios:
            message_parts.append(f"scenarios: {', '.join(sorted(future_scenarios))}")
        if unrecognized:
            message_parts.append(f"unrecognized: {len(unrecognized)}")

        return {
            "status": "ok",
            "total_files": len(parsed),
            "unrecognized_count": len(unrecognized),
            "unrecognized_files": unrecognized,
            "variables": var_summary,
            "label_years": sorted(list(label_years)),
            "future_scenarios": sorted(list(future_scenarios)),
            "can_train": can_train,
            "can_predict": can_predict,
            "message": " | ".join(message_parts),
        }
    except Exception as e:
        return {
            "status": "error",
            "error_type": type(e).__name__,
            "message": str(e),
            "suggested_action": "inspect_uploads failed.",
        }


# ============================================================
# Raw-source adapter (RUSLE source_mode=rusle_raw)
# ============================================================
def _infer_raw_item(filepath: str) -> Optional[dict]:
    name = os.path.basename(filepath)
    lower = name.lower()
    if not lower.endswith((".tif", ".tiff")):
        return None

    # SE labels: SE_Heilongjiang_2018-xxxx-xxxx.tif (multiple tiles per year)
    m_label = re.match(r"^SE_[^_]+_(\d{4})-.*\.(?:tif|tiff)$", name, flags=re.IGNORECASE)
    if m_label:
        return {"variable": "label", "year": m_label.group(1), "filepath": filepath, "filename": name}

    # C-year: C2018_300.tif
    m_c = re.match(r"^C(\d{4})_.*\.(?:tif|tiff)$", name, flags=re.IGNORECASE)
    if m_c:
        return {"variable": "C", "year": m_c.group(1), "filepath": filepath, "filename": name}

    # Optional yearly R like R2018_*.tif
    m_r = re.match(r"^R(\d{4})_.*\.(?:tif|tiff)$", name, flags=re.IGNORECASE)
    if m_r:
        return {"variable": "R", "year": m_r.group(1), "filepath": filepath, "filename": name}

    # Static factors
    if re.match(r"^K_.*\.(?:tif|tiff)$", name, flags=re.IGNORECASE):
        return {"variable": "K", "filepath": filepath, "filename": name}
    if re.match(r"^LS_.*\.(?:tif|tiff)$", name, flags=re.IGNORECASE):
        return {"variable": "LS", "filepath": filepath, "filename": name}
    if re.match(r"^P_.*\.(?:tif|tiff)$", name, flags=re.IGNORECASE):
        return {"variable": "P", "filepath": filepath, "filename": name}

    # R_mean as static fallback
    if lower == "r_mean.tif":
        return {"variable": "R", "filepath": filepath, "filename": name}

    return None


def _collect_rusle_raw_index(source_dir: str) -> dict:
    index = {
        "static": {},
        "dynamic": defaultdict(dict),   # var -> year -> filepath
        "labels": defaultdict(list),    # year -> [tile paths]
        "unmapped": [],
    }
    if not source_dir or not os.path.isdir(source_dir):
        return index

    for root, _, files in os.walk(source_dir):
        for filename in files:
            if not filename.lower().endswith((".tif", ".tiff")):
                continue
            fp = os.path.join(root, filename)
            item = _infer_raw_item(fp)
            if not item:
                index["unmapped"].append(fp)
                continue
            var = item["variable"]
            year = item.get("year")
            if var == "label" and year:
                index["labels"][year].append(fp)
            elif year:
                index["dynamic"][var][year] = fp
            else:
                index["static"][var] = fp
    return index


def _write_raw_source_index_metadata(state: dict,
                                     run_context: dict,
                                     target_resolution_km: float = 5.0,
                                     selected_years: Optional[List[str]] = None,
                                     staged_files: Optional[List[str]] = None,
                                     warnings_list: Optional[List[str]] = None) -> str:
    """Write read-only raw source metadata so all rusle_raw paths have P0 evidence."""
    source_dir = run_context.get("source_dir", DEFAULT_RUSLE_SOURCE_DIR)
    index = _collect_rusle_raw_index(source_dir)
    available_label_years = sorted(index["labels"].keys())
    available_c_years = sorted(index["dynamic"].get("C", {}).keys())
    if selected_years is None:
        year_intersection = sorted(list(set(available_label_years) & set(available_c_years)))
        selected_years = _pick_years_for_mode(
            years=year_intersection if year_intersection else available_label_years,
            run_mode=run_context.get("run_mode", "quick"),
        )
    raw_index = {
        "source_dir": source_dir,
        "run_mode": run_context.get("run_mode", "quick"),
        "target_resolution_km": float(target_resolution_km),
        "selected_years": list(selected_years or []),
        "available_label_years": available_label_years,
        "available_c_years": available_c_years,
        "static_factors": sorted(index["static"].keys()),
        "dynamic_factors": {k: sorted(v.keys()) for k, v in index["dynamic"].items()},
        "label_tile_counts": {k: len(v) for k, v in index["labels"].items()},
        "staged_files": list(staged_files or []),
        "warnings": list(warnings_list or []),
        "source_read_only": True,
        "note": "Raw source index records metadata only unless staged_files is non-empty.",
    }
    index_path = os.path.join(run_context["paths"]["inputs"], "raw_source_index.json")
    _write_json(index_path, raw_index)
    _record_evidence_path(state, index_path)
    return index_path


def _raw_raster_meta(filepath: str) -> dict:
    try:
        with rasterio.open(filepath) as src:
            return {
                "filepath": filepath,
                "filename": os.path.basename(filepath),
                "width": int(src.width),
                "height": int(src.height),
                "pixels": int(src.width * src.height),
                "crs": src.crs.to_string() if src.crs else None,
                "resolution": [float(src.res[0]), float(src.res[1])],
                "nodata": src.nodata,
                "size_bytes": int(os.path.getsize(filepath)),
            }
    except Exception as e:
        return {
            "filepath": filepath,
            "filename": os.path.basename(filepath),
            "error": str(e),
            "size_bytes": int(os.path.getsize(filepath)) if os.path.exists(filepath) else 0,
        }


def _full_resource_preflight(source_dir: str, target_resolution_km: float = 5.0) -> dict:
    index = _collect_rusle_raw_index(source_dir)
    files = []
    for fp in sorted(index["static"].values()):
        files.append(_raw_raster_meta(fp))
    for var_map in index["dynamic"].values():
        for fp in sorted(var_map.values()):
            files.append(_raw_raster_meta(fp))
    for tile_paths in index["labels"].values():
        for fp in sorted(tile_paths):
            files.append(_raw_raster_meta(fp))

    valid = [m for m in files if "pixels" in m]
    total_size_gb = sum(m.get("size_bytes", 0) for m in files) / (1024 ** 3)
    max_pixels = max([m.get("pixels", 0) for m in valid], default=0)
    label_years = sorted(index["labels"].keys())
    c_years = sorted(index["dynamic"].get("C", {}).keys())
    selected_full_years = sorted(list(set(label_years) & set(c_years))) or label_years
    present_static = sorted(index["static"].keys())
    missing_static = [v for v in ("R", "K", "LS", "P") if v not in index["static"]]
    warnings_list = []
    if missing_static:
        warnings_list.append(f"missing static factors: {', '.join(missing_static)}")
    if len(selected_full_years) > 6:
        warnings_list.append(f"full mode includes {len(selected_full_years)} label years")
    if max_pixels > 250_000_000:
        warnings_list.append(f"largest raster has {max_pixels} pixels")
    if total_size_gb > 10:
        warnings_list.append(f"source rasters total {total_size_gb:.2f} GB")

    risk_level = "low"
    if warnings_list:
        risk_level = "medium"
    if max_pixels > 400_000_000 or total_size_gb > 20:
        risk_level = "high"

    return {
        "source_dir": source_dir,
        "target_resolution_km": float(target_resolution_km),
        "file_count": len(files),
        "total_size_gb": round(total_size_gb, 4),
        "max_pixels": int(max_pixels),
        "label_years": label_years,
        "c_years": c_years,
        "selected_full_years": selected_full_years,
        "present_static_factors": present_static,
        "missing_static_factors": missing_static,
        "risk_level": risk_level,
        "warnings": warnings_list,
        "note": "Preflight reads metadata only; it does not prove full-mode runtime success.",
    }


def _plan_full_execution(source_dir: str,
                         target_resolution_km: float = 5.0,
                         year_window_size: int = 2,
                         max_tile_pixels: int = 250_000_000) -> dict:
    """Build a metadata-only full-mode execution plan without touching source rasters."""
    index = _collect_rusle_raw_index(source_dir)
    preflight = _full_resource_preflight(source_dir=source_dir, target_resolution_km=target_resolution_km)
    years = [str(y) for y in preflight.get("selected_full_years", [])]
    year_window_size = max(1, int(year_window_size or 1))
    max_tile_pixels = max(1, int(max_tile_pixels or 1))

    static_plan = []
    for var in ("R", "K", "LS", "P"):
        fp = index["static"].get(var)
        static_plan.append({
            "variable": var,
            "available": bool(fp and os.path.exists(fp)),
            "meta": _raw_raster_meta(fp) if fp and os.path.exists(fp) else None,
        })

    batches = []
    for batch_idx, start in enumerate(range(0, len(years), year_window_size), start=1):
        batch_years = years[start:start + year_window_size]
        batch_items = []
        batch_size = 0
        batch_max_pixels = 0
        incomplete = []
        for year in batch_years:
            c_path = index["dynamic"].get("C", {}).get(year)
            label_tiles = sorted(index["labels"].get(year, []))
            tile_metas = [_raw_raster_meta(p) for p in label_tiles]
            c_meta = _raw_raster_meta(c_path) if c_path and os.path.exists(c_path) else None
            year_size = sum(m.get("size_bytes", 0) for m in tile_metas) + (c_meta or {}).get("size_bytes", 0)
            year_max_pixels = max([m.get("pixels", 0) for m in tile_metas] + [int((c_meta or {}).get("pixels", 0))], default=0)
            batch_size += year_size
            batch_max_pixels = max(batch_max_pixels, year_max_pixels)
            complete = bool(label_tiles) and bool(c_meta)
            if not complete:
                incomplete.append(year)
            batch_items.append({
                "year": year,
                "complete": complete,
                "c_factor": c_meta,
                "label_tile_count": len(label_tiles),
                "label_tiles": tile_metas,
                "estimated_source_size_gb": round(year_size / (1024 ** 3), 4),
                "max_pixels": int(year_max_pixels),
                "action": "mosaic_label_tiles_then_warp_to_analysis_grid",
            })

        risk = "low"
        risk_notes = []
        if incomplete:
            risk = "high"
            risk_notes.append(f"incomplete years: {', '.join(incomplete)}")
        if batch_max_pixels > max_tile_pixels:
            risk = "high"
            risk_notes.append(f"batch max raster pixels {batch_max_pixels} exceeds limit {max_tile_pixels}")
        elif batch_size > 4 * (1024 ** 3):
            risk = "medium"
            risk_notes.append(f"batch source size {batch_size / (1024 ** 3):.2f} GB")

        batches.append({
            "batch_id": f"full_batch_{batch_idx:03d}",
            "years": batch_years,
            "year_count": len(batch_years),
            "estimated_source_size_gb": round(batch_size / (1024 ** 3), 4),
            "max_pixels": int(batch_max_pixels),
            "risk_level": risk,
            "risk_notes": risk_notes,
            "items": batch_items,
        })

    return {
        "source_dir": source_dir,
        "target_resolution_km": float(target_resolution_km),
        "year_window_size": int(year_window_size),
        "max_tile_pixels": int(max_tile_pixels),
        "source_read_only": True,
        "cleanup_scope": "water_erosion_mvp/data/runs only",
        "preflight": preflight,
        "static_factors": static_plan,
        "batches": batches,
        "execution_order": [
            "prepare_run_context(run_mode='full', source_mode='rusle_raw')",
            "prepare_full_resource_preflight(...)",
            "stage static factors once",
            "for each batch: mosaic same-year SE tiles, warp to analysis grid, build batch feature table",
            "append validated batch features under data/runs/<run_id>/features/full_batches",
            "train/evaluate model pool on concatenated validated batches",
            "generate explanations and spatial outputs with sampling/proxy fallback when needed",
            "export evidence bundle and run error_corrector for every stage",
        ],
        "claim_boundary": (
            "This is a metadata execution plan only. It does not prove full-mode runtime success "
            "until each batch is executed and gated."
        ),
    }


def _find_batch_in_plan(plan: dict, batch_id: str) -> Optional[dict]:
    for batch in plan.get("batches", []) or []:
        if batch.get("batch_id") == batch_id:
            return batch
    return None


def _batch_reference_raster(batch: dict) -> Optional[dict]:
    candidates = []
    for item in batch.get("items", []) or []:
        if item.get("c_factor"):
            candidates.append(item["c_factor"])
        candidates.extend(item.get("label_tiles", []) or [])
    valid = [m for m in candidates if m and m.get("width") and m.get("height")]
    if not valid:
        return None
    return max(valid, key=lambda m: int(m.get("pixels", 0) or 0))


def _plan_spatial_tiles_for_batch(batch: dict,
                                  tile_width: int = 4096,
                                  tile_height: int = 4096,
                                  max_tile_pixels: int = 25_000_000) -> dict:
    tile_width = max(1, int(tile_width or 1))
    tile_height = max(1, int(tile_height or 1))
    max_tile_pixels = max(1, int(max_tile_pixels or 1))
    ref = _batch_reference_raster(batch)
    if not ref:
        return {
            "batch_id": batch.get("batch_id"),
            "status": "error",
            "error_type": "NoReferenceRaster",
            "tiles": [],
        }

    width = int(ref["width"])
    height = int(ref["height"])
    total_pixels = max(1, width * height)
    batch_size_gb = float(batch.get("estimated_source_size_gb", 0.0) or 0.0)
    tiles = []
    idx = 1
    for row_off in range(0, height, tile_height):
        h = min(tile_height, height - row_off)
        for col_off in range(0, width, tile_width):
            w = min(tile_width, width - col_off)
            pixels = int(w * h)
            size_gb = batch_size_gb * (pixels / total_pixels)
            risk = "high" if pixels > max_tile_pixels else ("medium" if size_gb > 1.0 else "low")
            tiles.append({
                "tile_id": f"{batch.get('batch_id', 'full_batch')}_tile_{idx:04d}",
                "row_off": int(row_off),
                "col_off": int(col_off),
                "height": int(h),
                "width": int(w),
                "estimated_pixels": pixels,
                "estimated_source_size_gb": round(size_gb, 6),
                "risk_level": risk,
            })
            idx += 1

    return {
        "batch_id": batch.get("batch_id"),
        "years": batch.get("years", []),
        "reference_raster": {
            "filename": ref.get("filename"),
            "filepath": ref.get("filepath"),
            "width": width,
            "height": height,
            "pixels": int(ref.get("pixels", total_pixels)),
            "crs": ref.get("crs"),
            "resolution": ref.get("resolution"),
        },
        "tile_width": int(tile_width),
        "tile_height": int(tile_height),
        "max_tile_pixels": int(max_tile_pixels),
        "tile_count": len(tiles),
        "tiles": tiles,
        "source_read_only": True,
        "claim_boundary": "Spatial tile plans are metadata-only; they do not prove raster-window processing success.",
    }


def _pick_years_for_mode(years: List[str], run_mode: str) -> List[str]:
    years_sorted = sorted([str(y) for y in years])
    if run_mode == "full" or len(years_sorted) <= 1:
        return years_sorted
    # quick: use the latest complete year as a lightweight evidence chain.
    return [years_sorted[-1]]


def _copy_or_link(src: str, dst: str):
    _ensure_dir(os.path.dirname(dst))
    shutil.copy2(src, dst)


def _warp_to_analysis_grid(src_path: str,
                           dst_path: str,
                           target_resolution_m: float,
                           dst_crs: str = DEFAULT_CRS,
                           resampling: Resampling = Resampling.average):
    with rasterio.open(src_path) as src:
        src_crs = src.crs if src.crs else rasterio.crs.CRS.from_epsg(4326)
        dst_crs_obj = rasterio.crs.CRS.from_string(dst_crs)
        dst_transform, dst_width, dst_height = calculate_default_transform(
            src_crs, dst_crs_obj, src.width, src.height, *src.bounds, resolution=float(target_resolution_m)
        )
        if int(dst_width) <= 0 or int(dst_height) <= 0:
            raise RuntimeError(f"invalid dst size for warp: {dst_width}x{dst_height}")

        nodata = src.nodata if src.nodata is not None else -9999.0
        profile = src.profile.copy()
        profile.update({
            "driver": "GTiff",
            "crs": dst_crs_obj,
            "transform": dst_transform,
            "width": int(dst_width),
            "height": int(dst_height),
            "count": 1,
            "dtype": rasterio.float32,
            "compress": "lzw",
            "nodata": nodata,
        })

        _ensure_dir(os.path.dirname(dst_path))
        with rasterio.open(dst_path, "w", **profile) as dst:
            reproject(
                source=rasterio.band(src, 1),
                destination=rasterio.band(dst, 1),
                src_transform=src.transform,
                src_crs=src_crs,
                src_nodata=src.nodata,
                dst_transform=dst_transform,
                dst_crs=dst_crs_obj,
                dst_nodata=nodata,
                resampling=resampling,
                num_threads=1,
            )


def _mosaic_label_tiles(tile_paths: List[str], out_path: str) -> str:
    if len(tile_paths) == 1:
        _copy_or_link(tile_paths[0], out_path)
        return out_path

    srcs = [rasterio.open(p) for p in tile_paths]
    try:
        nodata = srcs[0].nodata
        profile = srcs[0].profile.copy()
        profile.update({"count": 1, "dtype": rasterio.float32, "compress": "lzw", "nodata": nodata if nodata is not None else -9999.0})
        _ensure_dir(os.path.dirname(out_path))
        # Stream merge directly to disk to avoid allocating a full in-memory mosaic array.
        raster_merge(
            srcs,
            method="first",
            dtype=rasterio.float32,
            nodata=profile["nodata"],
            dst_path=out_path,
            dst_kwds=profile,
            mem_limit=256,
        )
        if not os.path.exists(out_path):
            # Compatibility fallback for older rasterio builds without dst_path behavior.
            mosaic, transform = raster_merge(srcs, method="first")
            band = mosaic[0].astype(np.float32)
            profile.update({
                "height": band.shape[0],
                "width": band.shape[1],
                "transform": transform,
            })
            with rasterio.open(out_path, "w", **profile) as dst:
                dst.write(band, 1)
        return out_path
    finally:
        for src in srcs:
            src.close()


def _stage_rusle_raw_as_uploads(state: dict,
                                run_context: dict,
                                target_resolution_km: float = 5.0) -> dict:
    source_dir = run_context.get("source_dir", DEFAULT_RUSLE_SOURCE_DIR)
    index = _collect_rusle_raw_index(source_dir)

    available_label_years = sorted(index["labels"].keys())
    available_c_years = sorted(index["dynamic"].get("C", {}).keys())
    year_intersection = sorted(list(set(available_label_years) & set(available_c_years)))
    selected_years = _pick_years_for_mode(
        years=year_intersection if year_intersection else available_label_years,
        run_mode=run_context.get("run_mode", "quick"),
    )

    staged_dir = _ensure_dir(os.path.join(run_context["paths"]["inputs"], "staged_uploads"))
    uploads = {}
    staged_files = []
    warnings_list = []
    run_mode = str(run_context.get("run_mode", "quick"))
    target_resolution_m = float(target_resolution_km) * 1000.0

    def _stage_factor(src_path: str, dst_path: str, label: str):
        try:
            if run_mode == "quick":
                _warp_to_analysis_grid(
                    src_path=src_path,
                    dst_path=dst_path,
                    target_resolution_m=target_resolution_m,
                    dst_crs=DEFAULT_CRS,
                    resampling=Resampling.average,
                )
            else:
                _copy_or_link(src_path, dst_path)
        except Exception as e:
            # Keep workflow alive by falling back to copy; gate will expose this risk if needed.
            warnings_list.append(f"warp fallback ({label}): {e}")
            _copy_or_link(src_path, dst_path)

    # Static factors: K/LS/P/R if available
    for var in ("R", "K", "LS", "P"):
        src = index["static"].get(var)
        if src and os.path.exists(src):
            dst = os.path.join(staged_dir, f"{var}.tif")
            _stage_factor(src, dst, label=var)
            uploads[os.path.basename(dst)] = {"filepath": dst, "size": os.path.getsize(dst), "source": "rusle_raw"}
            staged_files.append(dst)
        else:
            warnings_list.append(f"static factor missing: {var}")

    # Dynamic C (and optional yearly R)
    for year in selected_years:
        c_src = index["dynamic"].get("C", {}).get(year)
        if c_src and os.path.exists(c_src):
            c_dst = os.path.join(staged_dir, f"C_{year}.tif")
            _stage_factor(c_src, c_dst, label=f"C_{year}")
            uploads[os.path.basename(c_dst)] = {"filepath": c_dst, "size": os.path.getsize(c_dst), "source": "rusle_raw"}
            staged_files.append(c_dst)
        else:
            warnings_list.append(f"missing C year: {year}")

        r_src = index["dynamic"].get("R", {}).get(year)
        if r_src and os.path.exists(r_src):
            r_dst = os.path.join(staged_dir, f"R_{year}.tif")
            _stage_factor(r_src, r_dst, label=f"R_{year}")
            uploads[os.path.basename(r_dst)] = {"filepath": r_dst, "size": os.path.getsize(r_dst), "source": "rusle_raw"}
            staged_files.append(r_dst)

    # Label tiles: full mode mosaics same-year tiles; quick mode uses one light tile
    # to avoid generating multi-GB intermediates before the smoke evidence chain.
    for year in selected_years:
        label_tiles = sorted(index["labels"].get(year, []))
        if not label_tiles:
            warnings_list.append(f"missing label year: {year}")
            continue
        label_out = os.path.join(staged_dir, f"label_{year}.tif")
        if run_mode == "quick" and len(label_tiles) > 1:
            label_src = min(label_tiles, key=lambda p: os.path.getsize(p) if os.path.exists(p) else float("inf"))
            warnings_list.append(
                f"quick label subset for {year}: selected {os.path.basename(label_src)} of {len(label_tiles)} tiles; full mode mosaics all tiles"
            )
            _stage_factor(label_src, label_out, label=f"label_{year}")
        else:
            label_out_raw = os.path.join(staged_dir, f"label_{year}__raw_mosaic.tif")
            _mosaic_label_tiles(label_tiles, label_out_raw)
            _stage_factor(label_out_raw, label_out, label=f"label_{year}")
            try:
                os.remove(label_out_raw)
            except Exception:
                pass
        uploads[os.path.basename(label_out)] = {"filepath": label_out, "size": os.path.getsize(label_out), "source": "rusle_raw"}
        staged_files.append(label_out)

    state["uploads"] = uploads
    index_path = _write_raw_source_index_metadata(
        state=state,
        run_context=run_context,
        target_resolution_km=target_resolution_km,
        selected_years=selected_years,
        staged_files=staged_files,
        warnings_list=warnings_list,
    )

    return {
        "uploads": uploads,
        "selected_years": selected_years,
        "warnings": warnings_list,
        "raw_index_path": index_path,
    }


def _to_crs_obj(crs_value: Any):
    try:
        if crs_value:
            return rasterio.crs.CRS.from_string(str(crs_value))
    except Exception:
        pass
    return rasterio.crs.CRS.from_string(DEFAULT_CRS)


def _safe_nodata(value: Any, fallback: float = -9999.0) -> float:
    try:
        fv = float(value)
        if np.isfinite(fv):
            return fv
    except Exception:
        pass
    return float(fallback)


def _align_meta_to_template(meta: dict,
                            template_transform,
                            template_crs: Any,
                            template_shape: Tuple[int, int],
                            is_label: bool = False) -> dict:
    src_data = np.asarray(meta["data"], dtype=np.float32)
    src_fill = _safe_nodata(meta.get("nodata", None))
    src_arr = np.where(np.isnan(src_data), src_fill, src_data).astype(np.float32)
    dst_arr = np.full(template_shape, src_fill, dtype=np.float32)

    reproject(
        source=src_arr,
        destination=dst_arr,
        src_transform=meta["transform"],
        src_crs=_to_crs_obj(meta.get("crs")),
        src_nodata=src_fill,
        dst_transform=template_transform,
        dst_crs=_to_crs_obj(template_crs),
        dst_nodata=src_fill,
        resampling=Resampling.nearest if is_label else Resampling.average,
        num_threads=1,
        init_dest_nodata=True,
        warp_mem_limit=256,
    )
    dst_arr = np.where(np.isclose(dst_arr, src_fill), np.nan, dst_arr).astype(np.float32)

    out = dict(meta)
    out["data"] = dst_arr
    out["shape"] = template_shape
    out["transform"] = template_transform
    out["crs"] = str(_to_crs_obj(template_crs))
    out["nodata"] = src_fill
    return out


def _clamp_window(window: Window, width: int, height: int) -> Optional[Window]:
    col_off = max(0, int(np.floor(window.col_off)))
    row_off = max(0, int(np.floor(window.row_off)))
    col_end = min(width, int(np.ceil(window.col_off + window.width)))
    row_end = min(height, int(np.ceil(window.row_off + window.height)))
    if col_end <= col_off or row_end <= row_off:
        return None
    return Window(col_off=col_off, row_off=row_off, width=col_end - col_off, height=row_end - row_off)


def _read_window_meta(filepath: str,
                      window: Optional[Window] = None,
                      bounds: Optional[Tuple[float, float, float, float]] = None,
                      bounds_crs: Optional[Any] = None) -> Optional[dict]:
    with rasterio.open(filepath) as src:
        use_window = window
        if bounds is not None:
            src_crs = src.crs if src.crs else rasterio.crs.CRS.from_epsg(4326)
            b = bounds
            if bounds_crs:
                try:
                    bounds_crs_obj = _to_crs_obj(bounds_crs)
                    if bounds_crs_obj != src_crs:
                        b = transform_bounds(bounds_crs_obj, src_crs, *bounds, densify_pts=21)
                except Exception:
                    b = bounds
            use_window = window_from_bounds(*b, transform=src.transform)
        if use_window is None:
            use_window = Window(0, 0, src.width, src.height)
        use_window = _clamp_window(use_window, src.width, src.height)
        if use_window is None:
            return None
        data = src.read(1, window=use_window, boundless=False).astype(np.float32)
        nodata = src.nodata
        if nodata is not None:
            data = np.where(np.isclose(data, nodata), np.nan, data)
        return {
            "data": data,
            "transform": src.window_transform(use_window),
            "crs": src.crs.to_string() if src.crs else None,
            "bounds": window_bounds(use_window, src.transform),
            "shape": data.shape,
            "resolution": (float(src.res[0]), float(src.res[1])),
            "nodata": nodata,
            "filepath": filepath,
        }


def _window_feature_records(arrays: Dict[str, np.ndarray],
                            label: np.ndarray,
                            transform,
                            year: str,
                            max_records: int = 50_000) -> pd.DataFrame:
    names = ["R", "K", "LS", "P", "C"]
    shape = label.shape
    valid = np.isfinite(label)
    for name in names:
        valid &= np.isfinite(arrays[name])
    rows, cols = np.where(valid)
    if len(rows) == 0:
        return pd.DataFrame()
    max_records = max(1, int(max_records or 1))
    if len(rows) > max_records:
        take = np.linspace(0, len(rows) - 1, max_records, dtype=int)
        rows = rows[take]
        cols = cols[take]
    xs, ys = rasterio.transform.xy(transform, rows, cols)
    payload = {
        "grid_id": (rows.astype(np.int64) * int(shape[1]) + cols.astype(np.int64)),
        "year": np.full(len(rows), int(year), dtype=np.int32),
        "x": np.asarray(xs, dtype=float),
        "y": np.asarray(ys, dtype=float),
        "row": rows.astype(np.int32),
        "col": cols.astype(np.int32),
        "label": label[rows, cols].astype(float),
    }
    for name in names:
        payload[name] = arrays[name][rows, cols].astype(float)
    return pd.DataFrame(payload)


def _build_preprocess_audit(source_mode: str,
                            feature_df: pd.DataFrame,
                            feature_cols: List[str],
                            used_years: List[str],
                            staged_warnings: List[str]) -> dict:
    required = ["R", "K", "LS", "C", "P"]
    present = sorted([v for v in required if v in feature_cols])
    missing = sorted([v for v in required if v not in feature_cols])
    coverage = {}
    for c in feature_cols:
        series = feature_df[c]
        coverage[c] = float(np.isfinite(series.values).mean() * 100.0)

    if source_mode == "rusle_raw":
        required_ok = len(missing) == 0
    else:
        required_ok = len(feature_cols) >= 2

    return {
        "source_mode": source_mode,
        "required_rusle_factors": required,
        "present_factors": present,
        "missing_factors": missing,
        "feature_coverage_pct": coverage,
        "used_years": [str(y) for y in used_years],
        "staging_warnings": staged_warnings or [],
        "required_ok": bool(required_ok),
    }


# ============================================================
# 宸ュ叿2: build_feature_table
# ============================================================
def build_feature_table(state: dict,
                        target_resolution_km: float = 5.0,
                        run_mode: str = "quick",
                        source_mode: str = "uploads",
                        output_dpi: int = DEFAULT_OUTPUT_DPI,
                        run_id: Optional[str] = None,
                        source_dir: Optional[str] = None) -> dict:
    """
    Build aligned feature table.
    Supports two source modes:
    - uploads: use current state['uploads'] (legacy behavior)
    - rusle_raw: stage files from read-only raw source into run inputs first
    """
    try:
        ctx = _get_or_prepare_context(
            state=state,
            run_mode=run_mode,
            source_mode=source_mode,
            output_dpi=output_dpi,
            run_id=run_id,
            source_dir=source_dir,
        )
        if source_mode == "rusle_raw":
            staged = _stage_rusle_raw_as_uploads(
                state=state,
                run_context=ctx,
                target_resolution_km=target_resolution_km,
            )
        else:
            staged = {"warnings": [], "selected_years": []}

        uploads = state.get("uploads", {}) or {}
        if not uploads:
            return {
                "status": "error",
                "error_type": "NoData",
                "message": "No upload data available after source staging.",
                "suggested_action": "Check source_mode or upload files first.",
            }

        raster_list = []
        for fname, fmeta in uploads.items():
            info = parse_filename(fname)
            if not info:
                continue
            filepath = fmeta.get("filepath", "")
            if not os.path.exists(filepath):
                continue
            meta = read_raster(filepath)
            meta["name"] = fname
            meta["variable"] = info["variable"]
            meta["year"] = info.get("year")
            meta["scenario"] = info.get("scenario")
            raster_list.append(meta)

        if not raster_list:
            return {
                "status": "error",
                "error_type": "NoValidData",
                "message": "No valid parsed rasters found.",
                "suggested_action": "Check naming format and readable files.",
            }

        target_res_m = target_resolution_km * 1000.0
        static_vars = {r["variable"]: r for r in raster_list if r["year"] is None and r["variable"] != "label"}
        dynamic_vars = [r for r in raster_list if r["year"] is not None and r["variable"] != "label"]
        label_vars = [r for r in raster_list if r["variable"] == "label"]

        label_years = sorted(set(r["year"] for r in label_vars if r["year"]))
        if not label_years:
            return {
                "status": "error",
                "error_type": "NoLabel",
                "message": "No label_YYYY raster found.",
                "suggested_action": "Ensure label rasters exist after staging/upload.",
            }

        # quick mode can reduce years even in uploads mode
        used_years = _pick_years_for_mode(label_years, run_mode)

        all_records = []
        ref_transform = None
        for year in used_years:
            year_dynamic = [r for r in dynamic_vars if r.get("year") == year]
            year_label = [r for r in label_vars if r.get("year") == year]
            if not year_label:
                continue

            label_reprojected = align_rasters(
                list(year_label),
                target_crs=DEFAULT_CRS,
                target_resolution=target_res_m,
            )
            if not label_reprojected:
                continue
            label_template = label_reprojected[0]
            aligned_label = _align_meta_to_template(
                meta=label_template,
                template_transform=label_template["transform"],
                template_crs=label_template["crs"],
                template_shape=label_template["shape"],
                is_label=True,
            )

            aligned_dynamic = [aligned_label]
            for rast in year_dynamic:
                aligned_dynamic.append(
                    _align_meta_to_template(
                        meta=rast,
                        template_transform=label_template["transform"],
                        template_crs=label_template["crs"],
                        template_shape=label_template["shape"],
                        is_label=False,
                    )
                )

            aligned_static = {}
            for var_name, rast in static_vars.items():
                aligned_static[var_name] = _align_meta_to_template(
                    meta=rast,
                    template_transform=label_template["transform"],
                    template_crs=label_template["crs"],
                    template_shape=label_template["shape"],
                    is_label=False,
                )

            if ref_transform is None:
                ref_transform = aligned_dynamic[0]["transform"]

            height, width = aligned_dynamic[0]["shape"]
            transform = aligned_dynamic[0]["transform"]

            for row in range(height):
                for col in range(width):
                    x, y = rasterio.transform.xy(transform, row, col)
                    rec = {
                        "grid_id": row * width + col,
                        "year": int(year),
                        "x": x, "y": y, "row": row, "col": col,
                    }
                    has_any = False
                    has_label = False
                    for var_name, rast in aligned_static.items():
                        val = rast["data"][row, col]
                        if not np.isnan(val):
                            rec[var_name] = float(val)
                            has_any = True
                    for rast in aligned_dynamic:
                        var = rast["variable"]
                        val = rast["data"][row, col]
                        if not np.isnan(val):
                            rec[var] = float(val)
                            has_any = True
                            if var == "label":
                                has_label = True
                    if has_any and has_label:
                        all_records.append(rec)

        if not all_records:
            return {
                "status": "error",
                "error_type": "EmptyMatrix",
                "message": "Feature matrix is empty after alignment.",
                "suggested_action": "Check raster overlap and NoData coverage.",
            }

        df = pd.DataFrame(all_records)
        feature_cols = _feature_columns_from_df(df, target_col="label")
        missing_rate = float(df[feature_cols].isnull().mean().mean() * 100.0) if feature_cols else 0.0
        preprocess_audit = _build_preprocess_audit(
            source_mode=source_mode,
            feature_df=df,
            feature_cols=feature_cols,
            used_years=used_years,
            staged_warnings=staged.get("warnings", []),
        )
        preprocess_audit_path = os.path.join(ctx["paths"]["features"], "preprocess_audit.json")
        _write_json(preprocess_audit_path, preprocess_audit)
        _record_evidence_path(state, preprocess_audit_path)
        state["_preprocess_audit"] = {**preprocess_audit, "path": preprocess_audit_path}

        # write to run evidence + legacy compatibility
        run_parquet = os.path.join(ctx["paths"]["features"], "feature_table.parquet")
        _ensure_dir(os.path.dirname(run_parquet))
        df.to_parquet(run_parquet, index=False)
        _record_evidence_path(state, run_parquet)

        _ensure_dir(LEGACY_FEATURES_DIR)
        legacy_parquet = os.path.join(LEGACY_FEATURES_DIR, "feature_table.parquet")
        df.to_parquet(legacy_parquet, index=False)

        manifest_patch_path = os.path.join(ctx["paths"]["features"], "feature_table_meta.json")
        _write_json(manifest_patch_path, {
            "run_id": ctx["run_id"],
            "n_samples": int(len(df)),
            "n_features": int(len(feature_cols)),
            "feature_columns": feature_cols,
            "target_resolution_km": float(target_resolution_km),
            "used_years": used_years,
            "source_mode": source_mode,
            "run_mode": run_mode,
            "staging_warnings": staged.get("warnings", []),
            "missing_rate_pct": round(missing_rate, 4),
            "preprocess_audit_path": preprocess_audit_path,
        })
        _record_evidence_path(state, manifest_patch_path)

        state["feature_table"] = {
            "path": run_parquet,
            "legacy_path": legacy_parquet,
            "n_samples": len(df),
            "n_features": len(feature_cols),
            "columns": feature_cols,
            "transform_str": str(ref_transform) if ref_transform is not None else "",
            "target_resolution_km": target_resolution_km,
            "run_id": ctx["run_id"],
            "source_mode": source_mode,
            "run_mode": run_mode,
            "preprocess_audit_path": preprocess_audit_path,
        }

        _append_jsonl(os.path.join(ctx["paths"]["reports"], RUN_LOG_NAME), {
            "ts": _now_iso(),
            "stage": "P0",
            "event": "build_feature_table",
            "status": "ok",
            "run_id": ctx["run_id"],
            "n_samples": int(len(df)),
            "n_features": int(len(feature_cols)),
        })

        return {
            "status": "ok",
            "n_samples": len(df),
            "n_features": len(feature_cols),
            "feature_columns": feature_cols,
            "missing_rate_pct": round(missing_rate, 2),
            "parquet_path": run_parquet,
            "legacy_parquet_path": legacy_parquet,
            "target_resolution_km": target_resolution_km,
            "run_id": ctx["run_id"],
            "evidence_paths": [run_parquet, manifest_patch_path, preprocess_audit_path],
            "gate_verdict": ctx.get("gate_verdict", PASS),
            "used_years": used_years,
            "source_mode": source_mode,
            "run_mode": run_mode,
            "preprocess_required_ok": preprocess_audit.get("required_ok", False),
            "missing_factors": preprocess_audit.get("missing_factors", []),
            "message": (
                f"Feature table built: {len(df)} samples, {len(feature_cols)} features, "
                f"missing={missing_rate:.1f}% (run_id={ctx['run_id']})"
            ),
        }
    except Exception as e:
        traceback.print_exc()
        return {
            "status": "error",
            "error_type": type(e).__name__,
            "message": str(e),
            "suggested_action": "Feature table build failed. Check raster CRS, overlap and source staging.",
        }


# ============================================================
# 宸ュ叿3: train_candidates
# ============================================================
def train_candidates(state: dict, algorithms: list = None,
                     optuna_trials: int = 30, cv_folds: int = 5,
                     run_mode: str = "quick",
                     source_mode: str = "uploads",
                     output_dpi: int = DEFAULT_OUTPUT_DPI,
                     run_id: Optional[str] = None,
                     param_overrides: Optional[dict] = None,
                     progress_callback=None) -> dict:
    """
    Train candidate models with unified metrics:
    MAE/RMSE/R2/NRMSE/PBIAS/train_seconds.
    Optional dependencies are auto-skipped and recorded.
    """
    try:
        from sklearn.base import clone
        from sklearn.ensemble import RandomForestRegressor, ExtraTreesRegressor, AdaBoostRegressor
        from sklearn.neighbors import KNeighborsRegressor
        from sklearn.svm import SVR

        ctx = _get_or_prepare_context(
            state=state,
            run_mode=run_mode,
            source_mode=source_mode,
            output_dpi=output_dpi,
            run_id=run_id,
        )

        if algorithms is None:
            algorithms = DEFAULT_MODEL_POOL.copy()
        algorithms = [str(a).lower() for a in algorithms]
        param_overrides, invalid_param_overrides = _normalize_param_overrides_with_errors(param_overrides, algorithms)

        ft_info = state.get("feature_table")
        if not ft_info or not os.path.exists(ft_info["path"]):
            return {
                "status": "error",
                "error_type": "NoFeatureTable",
                "message": "Feature table is missing. Run build_feature_table first.",
                "suggested_action": "Execute build_feature_table before training.",
            }

        df = pd.read_parquet(ft_info["path"])
        if "label" not in df.columns:
            return {
                "status": "error",
                "error_type": "NoLabel",
                "message": "Label column is missing in feature table.",
                "suggested_action": "Ensure label rasters are included.",
            }

        feature_cols = _feature_columns_from_df(df, target_col="label")
        if not feature_cols:
            return {
                "status": "error",
                "error_type": "NoNumericFeatures",
                "message": "No numeric feature columns are available for training.",
                "suggested_action": "Check feature table schema and metadata columns.",
            }
        df_clean = df[feature_cols + ["label"]].dropna()
        if len(df_clean) < 50:
            return {
                "status": "error",
                "error_type": "InsufficientData",
                "message": f"Only {len(df_clean)} valid samples after dropna.",
                "suggested_action": "Check overlap and valid pixels in rasters.",
            }

        X = df_clean[feature_cols].values
        y = df_clean["label"].values
        folds = _spatial_cv_split(X, y, cv_folds)

        metrics_rows = []
        models_dict = state.get("models", {}) or {}
        best_rmse = None
        best_algo = None
        skipped = []

        for i, algo in enumerate(algorithms):
            if progress_callback:
                progress_callback(f"Training {algo} ({i+1}/{len(algorithms)})", i / max(len(algorithms), 1))
            if invalid_param_overrides.get(algo):
                skipped.append({
                    "algorithm": algo,
                    "reason": "invalid manual parameters: " + "; ".join(invalid_param_overrides[algo]),
                })
                continue
            try:
                if algo not in MODEL_REGISTRY:
                    raise ValueError(f"unsupported algorithm: {algo}")
                actual_params = dict(MODEL_REGISTRY[algo].get("default_params", {}))
                actual_params.update(param_overrides.get(algo, {}))
                estimator = _build_estimator_from_registry(algo, actual_params)
            except Exception as e:
                skipped.append({"algorithm": algo, "reason": str(e)})
                continue

            # CV metrics
            fold_metrics = []
            cv_start = time.time()
            try:
                for train_idx, test_idx in folds:
                    model_fold = clone(estimator)
                    model_fold.fit(X[train_idx], y[train_idx])
                    pred = model_fold.predict(X[test_idx])
                    fold_metrics.append(_metric_packet(y[test_idx], pred, train_seconds=0.0))
            except Exception as e:
                skipped.append({"algorithm": algo, "reason": str(e)})
                continue
            cv_elapsed = time.time() - cv_start

            # Train final model for deployment
            fit_start = time.time()
            final_model = clone(estimator)
            try:
                final_model.fit(X, y)
            except Exception as e:
                skipped.append({"algorithm": algo, "reason": str(e)})
                continue
            fit_elapsed = time.time() - fit_start

            metrics_dict = {
                "mae": float(np.mean([m["mae"] for m in fold_metrics])),
                "rmse": float(np.mean([m["rmse"] for m in fold_metrics])),
                "r2": float(np.mean([m["r2"] for m in fold_metrics])),
                "nrmse": float(np.mean([m["nrmse"] for m in fold_metrics])),
                "pbias": float(np.mean([m["pbias"] for m in fold_metrics])),
                "train_seconds": float(fit_elapsed),
                "cv_seconds": float(cv_elapsed),
            }

            model_path = os.path.join(ctx["paths"]["models"], f"{algo}_model.joblib")
            joblib.dump(final_model, model_path)
            _copy_to_legacy(model_path, os.path.join(LEGACY_MODELS_DIR, f"{algo}_model.joblib"))
            _record_evidence_path(state, model_path)

            feature_importance = None
            if hasattr(final_model, "feature_importances_"):
                feature_importance = {
                    f: float(v) for f, v in zip(feature_cols, final_model.feature_importances_)
                }

            models_dict[algo] = {
                "model": final_model,
                "metrics": metrics_dict,
                "feature_names": feature_cols,
                "feature_importance": feature_importance,
                "params": actual_params,
                "path": model_path,
                "run_id": ctx["run_id"],
            }

            metrics_rows.append({
                "algorithm": algo,
                "mae": round(metrics_dict["mae"], 4),
                "rmse": round(metrics_dict["rmse"], 4),
                "r2": round(metrics_dict["r2"], 4),
                "nrmse": round(metrics_dict["nrmse"], 4),
                "pbias": round(metrics_dict["pbias"], 4),
                "train_seconds": round(metrics_dict["train_seconds"], 3),
            })

            if best_rmse is None or metrics_dict["rmse"] < best_rmse:
                best_rmse = metrics_dict["rmse"]
                best_algo = algo

        if not metrics_rows:
            return {
                "status": "error",
                "error_type": "NoTrainableAlgorithms",
                "message": "No models were trained. All candidate algorithms were skipped.",
                "skipped_algorithms": skipped,
                "suggested_action": "Install optional dependencies or reduce algorithm list.",
            }

        state["models"] = models_dict
        state["best_model"] = best_algo

        ranking_path = os.path.join(ctx["paths"]["models"], "model_ranking.json")
        _write_json(ranking_path, {
            "run_id": ctx["run_id"],
            "best_algorithm": best_algo,
            "metrics": metrics_rows,
            "skipped_algorithms": skipped,
        })
        _copy_to_legacy(ranking_path, os.path.join(LEGACY_MODELS_DIR, "model_ranking.json"))
        _record_evidence_path(state, ranking_path)

        _append_jsonl(os.path.join(ctx["paths"]["reports"], RUN_LOG_NAME), {
            "ts": _now_iso(),
            "stage": "P1",
            "event": "train_candidates",
            "status": "ok",
            "run_id": ctx["run_id"],
            "best_algorithm": best_algo,
            "n_algorithms": len(metrics_rows),
            "skipped": len(skipped),
        })

        if progress_callback:
            progress_callback("Training complete", 1.0)

        return {
            "status": "ok",
            "sample_count": int(len(df_clean)),
            "n_features": len(feature_cols),
            "metrics": metrics_rows,
            "best_algorithm": best_algo,
            "best_rmse": round(float(best_rmse), 4) if best_rmse is not None else None,
            "best_r2": next((m["r2"] for m in metrics_rows if m["algorithm"] == best_algo), None),
            "run_id": ctx["run_id"],
            "evidence_paths": [ranking_path],
            "gate_verdict": ctx.get("gate_verdict", PASS),
            "skipped_algorithms": skipped,
            "message": f"Trained {len(metrics_rows)} models; best={best_algo} (RMSE={best_rmse:.4f}).",
        }
    except Exception as e:
        traceback.print_exc()
        return {
            "status": "error",
            "error_type": type(e).__name__,
            "message": str(e),
            "suggested_action": "Training failed. Check feature table and dependency availability.",
        }


def _spatial_cv_split(X: np.ndarray, y: np.ndarray, n_folds: int = 5) -> list:
    """Auto-generated doc."""
    n = len(X)
    indices = np.arange(n)
    fold_size = n // n_folds
    folds = []
    for i in range(n_folds):
        start = i * fold_size
        end = start + fold_size if i < n_folds - 1 else n
        test_idx = indices[start:end]
        train_idx = np.concatenate([indices[:start], indices[end:]])
        folds.append((train_idx, test_idx))
    return folds


def _train_lightgbm(X, y, feature_names, n_trials, cv_folds, target_col):
    """Auto-generated doc."""
    from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

    folds = _spatial_cv_split(X, y, cv_folds)

    # 鍥哄畾榛樿鍙傛暟
    default_params = {
        "n_estimators": 300, "learning_rate": 0.05, "max_depth": 6,
        "subsample": 0.8, "colsample_bytree": 0.8,
        "random_state": 42, "n_jobs": 1, "verbosity": 0,
    }

    # 鍏ㄩ噺璁粌鏈€缁堟ā鍨?
    final_model = xgb.XGBRegressor(**default_params)
    final_model.fit(X, y)

    # 绌洪棿鍒嗗潡CV璇勪及
    cv_mae, cv_rmse, cv_r2 = [], [], []
    for train_idx, test_idx in folds:
        fold_model = xgb.XGBRegressor(**default_params)
        fold_model.fit(X[train_idx], y[train_idx])
        pred = fold_model.predict(X[test_idx])
        cv_mae.append(mean_absolute_error(y[test_idx], pred))
        cv_rmse.append(np.sqrt(mean_squared_error(y[test_idx], pred)))
        cv_r2.append(r2_score(y[test_idx], pred))

    return final_model, {
        "mae": float(np.mean(cv_mae)),
        "rmse": float(np.mean(cv_rmse)),
        "r2": float(np.mean(cv_r2)),
    }


def _train_random_forest(X, y, feature_names, n_trials, cv_folds, target_col):
    """Auto-generated doc."""
    from sklearn.ensemble import RandomForestRegressor
    from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

    folds = _spatial_cv_split(X, y, cv_folds)

    # 鍥哄畾榛樿鍙傛暟
    default_params = {
        "n_estimators": 300, "random_state": 42, "n_jobs": 1,
    }

    # 鍏ㄩ噺璁粌鏈€缁堟ā鍨?
    final_model = RandomForestRegressor(**default_params)
    final_model.fit(X, y)

    # 绌洪棿鍒嗗潡CV璇勪及
    cv_mae, cv_rmse, cv_r2 = [], [], []
    for train_idx, test_idx in folds:
        fold_model = RandomForestRegressor(**default_params)
        fold_model.fit(X[train_idx], y[train_idx])
        pred = fold_model.predict(X[test_idx])
        cv_mae.append(mean_absolute_error(y[test_idx], pred))
        cv_rmse.append(np.sqrt(mean_squared_error(y[test_idx], pred)))
        cv_r2.append(r2_score(y[test_idx], pred))

    return final_model, {
        "mae": float(np.mean(cv_mae)),
        "rmse": float(np.mean(cv_rmse)),
        "r2": float(np.mean(cv_r2)),
    }


# ============================================================
# 宸ュ叿3b: optimize_hyperparams
# ============================================================
def optimize_hyperparams(state: dict,
                         algorithms: list = None,
                         target_col: str = "label",
                         n_folds: int = 4,
                         n_trials: int = 30,
                         timeout_sec: int = None,
                         base_param_overrides: Optional[dict] = None,
                         progress_callback=None) -> dict:
    """Compatibility wrapper for the current multi-model Bayesian optimization chain."""
    if target_col != "label":
        return {
            "status": "error",
            "error_type": "UnsupportedTarget",
            "message": "optimize_hyperparams now uses the unified feature table target column 'label'.",
            "suggested_action": "Use target_col='label' or build a feature table with label as the target.",
        }

    target_algorithms = [str(a).lower() for a in (algorithms or DEFAULT_MODEL_POOL)]

    def _compat_progress(payload, pct=None):
        if not progress_callback:
            return
        if isinstance(payload, dict):
            algo = payload.get("algo") or payload.get("stage") or "optimization"
            trial = payload.get("trial")
            total = payload.get("total")
            done = payload.get("done")
            message = f"Optimizing {algo}"
            if trial is not None and total is not None:
                message = f"{message} ({trial}/{total})"
                progress_pct = 0.05 + 0.55 * (float(trial) / max(float(total), 1.0))
            elif done is not None and total is not None:
                message = f"Retraining {payload.get('algo', algo)} ({done}/{total})"
                progress_pct = 0.60 + 0.30 * (float(done) / max(float(total), 1.0))
            else:
                progress_pct = 0.05
            progress_callback(message, min(max(progress_pct, 0.0), 0.95))
        else:
            progress_callback(str(payload), 0.0 if pct is None else pct)

    opt_result = run_stage_two_optimization(
        state=state,
        algorithms=target_algorithms,
        cv_folds=n_folds,
        n_trials=n_trials,
        timeout_sec=timeout_sec,
        base_param_overrides=base_param_overrides,
        progress_callback=_compat_progress,
    )
    if opt_result.get("status") != "ok":
        return opt_result

    retrain_result = run_stage_three_retrain(
        state=state,
        algorithms=list((opt_result.get("optimization_results") or {}).keys()),
        base_param_overrides=base_param_overrides,
        progress_callback=_compat_progress,
    )
    if retrain_result.get("status") != "ok":
        compat_error = dict(retrain_result)
        compat_error["optimization_results"] = opt_result.get("optimization_results", {})
        compat_error["skipped_algorithms"] = opt_result.get("skipped_algorithms", [])
        return compat_error

    optimization_results = opt_result.get("optimization_results", {}) or {}
    metrics_table = retrain_result.get("retrained_metrics", []) or []
    for row in metrics_table:
        algo = row.get("algorithm")
        if algo in state.get("models", {}):
            model_info = state["models"][algo]
            model_info["best_params"] = dict((optimization_results.get(algo) or {}).get("best_params") or {})
            model_info["study_history"] = [
                h.get("r2") for h in (optimization_results.get(algo) or {}).get("history", [])
            ]

    best_algo = retrain_result.get("best_model") or state.get("best_model")
    best_row = next((m for m in metrics_table if m.get("algorithm") == best_algo), {})
    if progress_callback:
        progress_callback("Optimization complete", 1.0)

    return {
        "status": "ok",
        "metrics": metrics_table,
        "best_algorithm": best_algo,
        "best_rmse": best_row.get("rmse"),
        "best_r2": best_row.get("r2"),
        "best_params": {
            algo: dict(result.get("best_params") or {})
            for algo, result in optimization_results.items()
        },
        "study_history": {
            algo: [h.get("r2") for h in (result.get("history") or [])]
            for algo, result in optimization_results.items()
        },
        "optimization_results": optimization_results,
        "skipped_algorithms": opt_result.get("skipped_algorithms", []),
        "report_path": retrain_result.get("report_path"),
        "message": f"Optimization complete. Best={best_algo}",
    }

def select_best(state: dict, metric: str = "rmse") -> dict:
    """Auto-generated doc."""
    try:
        models = state.get("models", {}) or {}
        if not models:
            return {
                "status": "error",
                "error_type": "NoModels",
                "message": "No trained models found.",
                "suggested_action": "Run train_candidates first.",
            }

        ft_info = state.get("feature_table")
        if not ft_info or not os.path.exists(ft_info["path"]):
            return {
                "status": "error",
                "error_type": "NoFeatureTable",
                "message": "Feature table is missing.",
                "suggested_action": "Run build_feature_table first.",
            }

        ctx = state.get("run_context") or {}
        ranking = []
        for algo, info in models.items():
            m = info.get("metrics", {})
            ranking.append({
                "algorithm": algo,
                "mae": float(m.get("mae", np.nan)),
                "rmse": float(m.get("rmse", np.nan)),
                "r2": float(m.get("r2", np.nan)),
                "nrmse": float(m.get("nrmse", np.nan)),
                "pbias": float(m.get("pbias", np.nan)),
                "train_seconds": float(m.get("train_seconds", np.nan)),
            })

        reverse = metric in ("r2",)
        ranking.sort(key=lambda x: x.get(metric, np.inf if not reverse else -np.inf), reverse=reverse)
        best_algo = ranking[0]["algorithm"]
        best_info = models[best_algo]
        best_model = best_info["model"]
        state["best_model"] = best_algo

        df = pd.read_parquet(ft_info["path"])
        if "label" not in df.columns:
            return {
                "status": "error",
                "error_type": "NoLabel",
                "message": "Label column missing from feature table.",
            }
        feature_cols = _feature_columns_from_df(df, target_col="label")
        if not feature_cols:
            return {
                "status": "error",
                "error_type": "NoNumericFeatures",
                "message": "No numeric feature columns are available for selection.",
            }

        df_clean = df[feature_cols + ["label"]].dropna()
        X_all = df_clean[feature_cols].values
        y_all = df_clean["label"].values
        y_pred = best_model.predict(X_all)
        residuals = y_all - y_pred
        full_packet = _metric_packet(y_all, y_pred, train_seconds=float(best_info.get("metrics", {}).get("train_seconds", 0.0)))
        cv_packet = best_info.get("metrics", {}) or {}
        packet = {
            "mae": float(cv_packet.get("mae", full_packet["mae"])),
            "rmse": float(cv_packet.get("rmse", full_packet["rmse"])),
            "r2": float(cv_packet.get("r2", full_packet["r2"])),
            "nrmse": float(cv_packet.get("nrmse", full_packet["nrmse"])),
            "pbias": float(cv_packet.get("pbias", full_packet["pbias"])),
            "train_seconds": float(cv_packet.get("train_seconds", full_packet["train_seconds"])),
        }

        if hasattr(best_model, "feature_importances_"):
            importance = np.asarray(best_model.feature_importances_, dtype=float)
        else:
            importance = np.ones(len(feature_cols), dtype=float) / max(len(feature_cols), 1)
        top_idx = np.argsort(importance)[-5:][::-1]
        top_features = [(feature_cols[i], float(importance[i])) for i in top_idx] if len(feature_cols) else []

        residual_summary = {
            "mean": float(np.mean(residuals)),
            "std": float(np.std(residuals)),
            "min": float(np.min(residuals)),
            "max": float(np.max(residuals)),
        }

        state["_diagnostics"] = {
            "y_true": y_all,
            "y_pred": y_pred,
            "residuals": residuals,
            "feature_names": feature_cols,
            "importance": importance,
            "residual_summary": residual_summary,
            "top_features": top_features,
            "best_metrics_cv": packet,
            "best_metrics_full": full_packet,
        }

        rank_path = None
        selected_artifacts = {}
        if ctx:
            rank_path = os.path.join(ctx["paths"]["models"], "model_ranking_selected.json")
            _write_json(rank_path, {
                "run_id": ctx.get("run_id"),
                "metric": metric,
                "best_algorithm": best_algo,
                "ranking": ranking,
                "selected_metrics": packet,
                "full_fit_metrics_diagnostic": full_packet,
                "residual_summary": residual_summary,
                "top_features": top_features,
            })
            _copy_to_legacy(rank_path, os.path.join(LEGACY_MODELS_DIR, "model_ranking_selected.json"))
            selected_artifacts = _persist_selected_model_artifacts(state, best_model, ctx["paths"]["models"], {
                "run_id": ctx.get("run_id"),
                "best_algorithm": best_algo,
                "metric": metric,
                "selected_metrics": packet,
                "source_model_path": best_info.get("path"),
            })
            _record_evidence_path(state, rank_path)
            _record_evidence_path(state, selected_artifacts.get("best_model_path"))
            _record_evidence_path(state, selected_artifacts.get("best_model_meta_path"))
            _append_jsonl(os.path.join(ctx["paths"]["reports"], RUN_LOG_NAME), {
                "ts": _now_iso(),
                "stage": "P1",
                "event": "select_best",
                "status": "ok",
                "run_id": ctx.get("run_id"),
                "best_algorithm": best_algo,
            })

        return {
            "status": "ok",
            "best_algorithm": best_algo,
            "metrics": {
                "mae": round(packet["mae"], 4),
                "rmse": round(packet["rmse"], 4),
                "r2": round(packet["r2"], 4),
                "nrmse": round(packet["nrmse"], 4),
                "pbias": round(packet["pbias"], 4),
                "train_seconds": round(packet["train_seconds"], 4),
            },
            "ranking": ranking,
            "residual_summary": residual_summary,
            "top_features": top_features,
            "run_id": ctx.get("run_id"),
            "evidence_paths": [
                p for p in [
                    rank_path,
                    selected_artifacts.get("best_model_path"),
                    selected_artifacts.get("best_model_meta_path"),
                ] if p
            ],
            "gate_verdict": (ctx.get("gate_verdict") if ctx else PASS),
            "message": f"Best model: {best_algo} (RMSE={packet['rmse']:.4f}, R2={packet['r2']:.4f})",
        }
    except Exception as e:
        return {
            "status": "error",
            "error_type": type(e).__name__,
            "message": str(e),
            "suggested_action": "select_best failed. Re-train models then retry.",
        }


def set_current_model(state: dict, algorithm: str) -> dict:
    """Switch the current model to a trained algorithm and refresh diagnostics."""
    try:
        ctx = state.get("run_context") or _get_or_prepare_context(state)
        algo = str(algorithm or "").lower().strip()
        models = state.get("models", {}) or {}
        if not algo or algo not in models:
            return {
                "status": "error",
                "error_type": "ModelNotFound",
                "message": f"Model `{algorithm}` is not available in current results.",
                "suggested_action": "Train models first, then choose one from the evaluated results.",
            }

        ft_info = state.get("feature_table") or {}
        ft_path = ft_info.get("path", "")
        if not ft_path or not os.path.exists(ft_path):
            return {
                "status": "error",
                "error_type": "NoFeatureTable",
                "message": "Feature table is missing.",
                "suggested_action": "Rebuild modeling data before switching the current model.",
            }

        model_info = models[algo]
        model_obj = model_info["model"]
        df = pd.read_parquet(ft_path)
        feature_cols = [f for f in model_info.get("feature_names", []) if f in df.columns]
        if "label" not in df.columns or not feature_cols:
            return {
                "status": "error",
                "error_type": "InvalidFeatureTable",
                "message": "Feature table does not contain the required label/features.",
                "suggested_action": "Rebuild modeling data and retrain models.",
            }

        df_clean = df[feature_cols + ["label"]].dropna()
        if len(df_clean) == 0:
            return {
                "status": "error",
                "error_type": "EmptyData",
                "message": "No valid rows are available to refresh diagnostics.",
                "suggested_action": "Check overlap, NoData coverage, and feature completeness.",
            }

        X_all = df_clean[feature_cols].values
        y_all = df_clean["label"].values
        y_pred = model_obj.predict(X_all)
        residuals = y_all - y_pred
        full_packet = _metric_packet(
            y_all,
            y_pred,
            train_seconds=float(model_info.get("metrics", {}).get("train_seconds", 0.0)),
        )
        cv_packet = model_info.get("metrics", {}) or {}
        packet = {
            "mae": float(cv_packet.get("mae", full_packet["mae"])),
            "rmse": float(cv_packet.get("rmse", full_packet["rmse"])),
            "r2": float(cv_packet.get("r2", full_packet["r2"])),
            "nrmse": float(cv_packet.get("nrmse", full_packet["nrmse"])),
            "pbias": float(cv_packet.get("pbias", full_packet["pbias"])),
            "train_seconds": float(cv_packet.get("train_seconds", full_packet["train_seconds"])),
        }

        if hasattr(model_obj, "feature_importances_"):
            importance = np.asarray(model_obj.feature_importances_, dtype=float)
        else:
            importance = np.ones(len(feature_cols), dtype=float) / max(len(feature_cols), 1)
        top_idx = np.argsort(importance)[-5:][::-1]
        top_features = [(feature_cols[i], float(importance[i])) for i in top_idx] if len(feature_cols) else []
        residual_summary = {
            "mean": float(np.mean(residuals)),
            "std": float(np.std(residuals)),
            "min": float(np.min(residuals)),
            "max": float(np.max(residuals)),
        }

        state["best_model"] = algo
        state["_diagnostics"] = {
            "y_true": y_all,
            "y_pred": y_pred,
            "residuals": residuals,
            "feature_names": feature_cols,
            "importance": importance,
            "residual_summary": residual_summary,
            "top_features": top_features,
            "best_metrics_cv": packet,
            "best_metrics_full": full_packet,
        }

        select_path = os.path.join(ctx["paths"]["models"], "current_model_selection.json")
        _write_json(select_path, {
            "run_id": ctx.get("run_id"),
            "best_algorithm": algo,
            "selected_metrics": packet,
            "residual_summary": residual_summary,
            "top_features": top_features,
        })
        _copy_to_legacy(select_path, os.path.join(LEGACY_MODELS_DIR, "current_model_selection.json"))
        _record_evidence_path(state, select_path)
        _append_jsonl(os.path.join(ctx["paths"]["reports"], RUN_LOG_NAME), {
            "ts": _now_iso(),
            "stage": "P1",
            "event": "set_current_model",
            "status": "ok",
            "run_id": ctx.get("run_id"),
            "best_algorithm": algo,
        })

        return {
            "status": "ok",
            "best_algorithm": algo,
            "best_model_display": MODEL_REGISTRY.get(algo, {}).get("display_name", algo),
            "metrics": {
                "mae": round(packet["mae"], 4),
                "rmse": round(packet["rmse"], 4),
                "r2": round(packet["r2"], 4),
                "nrmse": round(packet["nrmse"], 4),
                "pbias": round(packet["pbias"], 4),
                "train_seconds": round(packet["train_seconds"], 4),
            },
            "top_features": top_features,
            "run_id": ctx.get("run_id"),
            "evidence_paths": [select_path],
            "gate_verdict": ctx.get("gate_verdict", PASS),
            "message": f"Current model switched to {MODEL_REGISTRY.get(algo, {}).get('display_name', algo)}.",
        }
    except Exception as e:
        return {
            "status": "error",
            "error_type": type(e).__name__,
            "message": str(e),
            "suggested_action": "set_current_model failed.",
        }


# ============================================================
# 宸ュ叿5: predict_future
# ============================================================
def predict_future(state: dict, scenario: str = "ssp245") -> dict:
    """Predict future raster using selected best model."""
    try:
        ctx = state.get("run_context") or _get_or_prepare_context(state)
        best_algo = state.get("best_model")
        models = state.get("models", {}) or {}
        if not best_algo or best_algo not in models:
            return {
                "status": "error",
                "error_type": "NoBestModel",
                "message": "Best model is not selected.",
                "suggested_action": "Run select_best first.",
            }

        model_info = models[best_algo]
        model = model_info["model"]
        feature_names = [f for f in model_info.get("feature_names", []) if f != "label"]

        ft_info = state.get("feature_table")
        ft_run_mode = str((ft_info or {}).get("run_mode", ""))
        can_replay_feature_table = (
            ctx.get("source_mode") == "rusle_raw"
            and ft_info
            and os.path.exists(ft_info.get("path", ""))
            and (
                ctx.get("run_mode") == "quick"
                or ft_run_mode.startswith("full_tile")
                or ft_run_mode.startswith("full_multi_tile")
            )
        )
        if can_replay_feature_table:
            df_train = pd.read_parquet(ft_info["path"])
            if "year" in df_train.columns:
                latest_year = int(df_train["year"].max())
                df_future = df_train[df_train["year"] == latest_year].copy()
            else:
                latest_year = 0
                df_future = df_train.copy()
            available_features = [c for c in feature_names if c in df_future.columns]
            missing = sorted(list(set(feature_names) - set(available_features)))
            if missing:
                return {
                    "status": "error",
                    "error_type": "FeatureMismatch",
                    "message": f"Missing features at prediction time: {missing}",
                    "suggested_action": "Check quick raw-source feature table.",
                }
            df_valid = df_future.dropna(subset=feature_names + ["row", "col"]).copy()
            if len(df_valid) == 0:
                return {
                    "status": "error",
                    "error_type": "EmptyFutureMatrix",
                    "message": "No valid quick raw-source feature rows to predict.",
                }

            X_future = df_valid[feature_names].values
            pred_values = model.predict(X_future)
            pred_values = np.where(np.isnan(pred_values), np.nan, np.maximum(pred_values, 0))
            max_row = int(df_valid["row"].max()) + 1
            max_col = int(df_valid["col"].max()) + 1
            pred_raster = np.full((max_row, max_col), np.nan, dtype=np.float32)
            uncert_raster = np.full((max_row, max_col), 1.0, dtype=np.float32)
            for i, (_, rec) in enumerate(df_valid.iterrows()):
                pred_raster[int(rec["row"]), int(rec["col"])] = float(pred_values[i])

            prediction_mode = "historical_feature_replay"
            risk_note = (
                "Quick rusle_raw prediction replays the latest historical feature grid; "
                "it is smoke evidence, not a future scenario forecast."
            )
            if ft_run_mode.startswith("full_tile"):
                prediction_mode = "bounded_tile_feature_replay"
                risk_note = (
                    "Bounded full-tile prediction replays an existing tile feature table; "
                    "it verifies P3 delivery artifacts for this tile only and is not a "
                    "future scenario forecast, full-batch prediction, or regional map."
                )
            elif ft_run_mode.startswith("full_multi_tile"):
                prediction_mode = "bounded_multi_tile_feature_replay"
                risk_note = (
                    "Bounded multi-tile prediction replays an existing multi-tile feature table; "
                    "it verifies P3 delivery artifacts for the sampled tiles only and is not a "
                    "future scenario forecast, full-batch prediction, or regional map."
                )

            state["predictions"] = {
                "scenario": scenario,
                "prediction_mode": prediction_mode,
                "risk_note": risk_note,
                "fallback_variables": [],
                "used_fallback_dynamic": True,
                "pred_raster": pred_raster,
                "uncert_raster": uncert_raster,
                "transform": None,
                "crs": DEFAULT_CRS,
                "shape": (max_row, max_col),
                "mean_erosion": float(np.nanmean(pred_raster)),
                "max_erosion": float(np.nanmax(pred_raster)),
                "neg_clipped": 0,
                "high_risk_ratio": 0.0,
                "run_id": ctx.get("run_id"),
            }

            pred_npy = os.path.join(ctx["paths"]["predictions"], f"pred_{scenario}.npy")
            uncert_npy = os.path.join(ctx["paths"]["predictions"], f"uncert_{scenario}.npy")
            pred_csv = os.path.join(ctx["paths"]["predictions"], f"pred_{scenario}_quick_points.csv")
            np.save(pred_npy, pred_raster)
            np.save(uncert_npy, uncert_raster)
            out_cols = ["grid_id", "year", "x", "y", "row", "col"] + feature_names
            out_cols = [c for c in out_cols if c in df_valid.columns]
            df_out = df_valid[out_cols].copy()
            df_out["prediction"] = pred_values
            df_out.to_csv(pred_csv, index=False, encoding="utf-8")
            pred_meta = os.path.join(ctx["paths"]["predictions"], f"pred_{scenario}_meta.json")
            _write_json(pred_meta, {
                "run_id": ctx.get("run_id"),
                "scenario": scenario,
                "prediction_mode": prediction_mode,
                "risk_note": risk_note,
                "fallback_variables": [],
                "used_fallback_dynamic": True,
                "latest_year": int(latest_year),
                "shape": [int(max_row), int(max_col)],
                "mean_erosion": float(np.nanmean(pred_raster)),
                "max_erosion": float(np.nanmax(pred_raster)),
                "neg_clipped": 0,
                "high_risk_ratio_pct": 0.0,
            })
            state["predictions"].update({
                "pred_path": pred_npy,
                "uncertainty_path": uncert_npy,
                "pred_meta_path": pred_meta,
                "pred_points_path": pred_csv,
            })
            _record_evidence_path(state, pred_npy)
            _record_evidence_path(state, uncert_npy)
            _record_evidence_path(state, pred_csv)
            _record_evidence_path(state, pred_meta)
            return {
                "status": "ok",
                "scenario": scenario,
                "prediction_mode": prediction_mode,
                "model_used": best_algo,
                "mean_erosion": round(state["predictions"]["mean_erosion"], 2),
                "max_erosion": round(state["predictions"]["max_erosion"], 2),
                "high_risk_ratio_pct": 0.0,
                "fallback_variables": [],
                "used_fallback_dynamic": True,
                "run_id": ctx.get("run_id"),
                "evidence_paths": [pred_npy, uncert_npy, pred_csv, pred_meta],
                "gate_verdict": PASS_WITH_RISKS,
                "message": f"Raw-source feature replay prediction complete for {latest_year} with {best_algo} ({prediction_mode}).",
            }

        uploads = state.get("uploads", {}) or {}
        raster_list = []
        for fname, fmeta in uploads.items():
            info = parse_filename(fname)
            if not info:
                continue
            fp = fmeta.get("filepath", "")
            if not fp or not os.path.exists(fp):
                continue
            meta = read_raster(fp)
            meta.update({
                "name": fname,
                "variable": info.get("variable"),
                "year": info.get("year"),
                "scenario": info.get("scenario"),
            })
            raster_list.append(meta)

        static_vars = {r["variable"]: r for r in raster_list if r.get("year") is None and r.get("variable") != "label"}
        future_dynamic = [r for r in raster_list if r.get("scenario") == scenario and r.get("variable") != "label"]

        used_fallback = False
        if not future_dynamic:
            # fallback: use latest historical year when no explicit scenario rasters exist
            hist = [r for r in raster_list if r.get("year") is not None and r.get("scenario") is None and r.get("variable") != "label"]
            if not hist:
                return {
                    "status": "error",
                    "error_type": "NoScenarioData",
                    "message": f"No scenario data found for '{scenario}'.",
                    "suggested_action": "Upload scenario rasters or keep historical dynamic factors.",
                }
            latest_year = max(int(r.get("year", 0)) for r in hist)
            future_dynamic = [r for r in hist if int(r.get("year", 0)) == latest_year]
            used_fallback = True

        target_res_m = 5000
        initial_future = align_rasters(future_dynamic[:1], target_crs=DEFAULT_CRS, target_resolution=target_res_m)
        if not initial_future:
            return {
                "status": "error",
                "error_type": "EmptyFutureMatrix",
                "message": "Aligned future feature matrix is empty.",
            }

        height, width = initial_future[0]["shape"]
        ref_transform = initial_future[0]["transform"]
        ref_crs = initial_future[0]["crs"]
        future_year = future_dynamic[0].get("year") if future_dynamic else None

        aligned_future = []
        for rast in future_dynamic:
            aligned = _align_meta_to_template(
                meta=rast,
                template_transform=ref_transform,
                template_crs=ref_crs,
                template_shape=(height, width),
                is_label=False,
            )
            if np.isfinite(aligned["data"]).any():
                aligned_future.append(aligned)
        if not aligned_future:
            return {
                "status": "error",
                "error_type": "EmptyFutureMatrix",
                "message": "Aligned future feature matrix is empty.",
            }

        static_aligned = {}
        for var, rast in static_vars.items():
            aligned = _align_meta_to_template(
                meta=rast,
                template_transform=ref_transform,
                template_crs=ref_crs,
                template_shape=(height, width),
                is_label=False,
            )
            if np.isfinite(aligned["data"]).any():
                static_aligned[var] = aligned

        historical_dynamic = [r for r in raster_list if r.get("year") is not None and r.get("scenario") is None and r.get("variable") != "label"]
        future_var_set = {r["variable"] for r in aligned_future if np.isfinite(r["data"]).any()}
        static_var_set = set(static_aligned.keys())
        missing_var_set = set(feature_names) - future_var_set - static_var_set

        fallback_vars = {}
        for var in sorted(missing_var_set):
            candidates = [r for r in historical_dynamic if r.get("variable") == var]
            if candidates:
                candidates.sort(key=lambda x: int(x.get("year", "0")), reverse=True)
                fallback_vars[var] = candidates[0]

        fallback_aligned = {}
        for var, rast in fallback_vars.items():
            aligned = _align_meta_to_template(
                meta=rast,
                template_transform=ref_transform,
                template_crs=ref_crs,
                template_shape=(height, width),
                is_label=False,
            )
            if np.isfinite(aligned["data"]).any():
                fallback_aligned[var] = aligned

        still_missing = missing_var_set - set(fallback_aligned.keys())
        if still_missing:
            return {
                "status": "error",
                "error_type": "FeatureMismatch",
                "message": f"Missing features: {sorted(still_missing)}",
                "suggested_action": "Ensure all training features have future/static/fallback sources.",
            }

        records = []
        for row in range(height):
            for col in range(width):
                x, y = rasterio.transform.xy(ref_transform, row, col)
                rec = {
                    "grid_id": row * width + col,
                    "year": int(future_year) if future_year else 2050,
                    "x": x,
                    "y": y,
                    "row": row,
                    "col": col,
                }
                has_any = False
                for v, rast in static_aligned.items():
                    val = rast["data"][row, col]
                    if not np.isnan(val):
                        rec[v] = float(val)
                        has_any = True
                for rast in aligned_future:
                    val = rast["data"][row, col]
                    if not np.isnan(val):
                        rec[rast["variable"]] = float(val)
                        has_any = True
                for v, rast in fallback_aligned.items():
                    val = rast["data"][row, col]
                    if not np.isnan(val):
                        rec[v] = float(val)
                        has_any = True
                if has_any:
                    records.append(rec)

        df_future = pd.DataFrame(records)
        if len(df_future) == 0:
            return {
                "status": "error",
                "error_type": "EmptyFutureMatrix",
                "message": "No valid future samples to predict.",
            }

        available_features = [c for c in df_future.columns if c in feature_names]
        missing = set(feature_names) - set(available_features)
        if missing:
            return {
                "status": "error",
                "error_type": "FeatureMismatch",
                "message": f"Missing features at prediction time: {sorted(missing)}",
                "suggested_action": "Check staged factors and fallback mapping.",
            }

        X_future = df_future[feature_names].values
        valid_mask = ~np.isnan(X_future).any(axis=1)
        if valid_mask.sum() == 0:
            return {
                "status": "error",
                "error_type": "AllNaN",
                "message": "All future samples contain NaN features.",
            }

        predictions = np.full(len(df_future), np.nan)
        predictions[valid_mask] = model.predict(X_future[valid_mask])

        uncertainty_map = np.full(len(df_future), np.nan)
        ft_info = state.get("feature_table")
        if ft_info and os.path.exists(ft_info.get("path", "")):
            df_train = pd.read_parquet(ft_info["path"])
            common = [f for f in feature_names if f in df_train.columns]
            X_train = df_train[common].dropna().values
            Xf = df_future[common].values
            if len(X_train) > 0 and X_train.shape[1] == Xf.shape[1]:
                mu = X_train.mean(axis=0)
                std = X_train.std(axis=0)
                std[std == 0] = 1
                zf = (Xf - mu) / std
                zt = (X_train - mu) / std
                dist = np.sqrt((zf ** 2).sum(axis=1))
                dist_train = np.sqrt((zt ** 2).sum(axis=1))
                thr = np.percentile(dist_train, 95)
                uncertainty_map[valid_mask] = np.where(
                    dist[valid_mask] > thr,
                    2.0,
                    1.0 - 0.5 * (dist[valid_mask] / (thr + 1e-10))
                )
                uncertainty_map = np.clip(uncertainty_map, 0, 2)

        ref_raster = aligned_future[0]
        pred_raster = np.full((height, width), np.nan)
        uncert_raster = np.full((height, width), np.nan)
        for idx, rec in enumerate(records):
            r = rec["row"]
            c = rec["col"]
            pred_raster[r, c] = predictions[idx]
            if idx < len(uncertainty_map):
                uncert_raster[r, c] = uncertainty_map[idx]

        neg_count = int(np.sum(pred_raster < 0))
        if neg_count > 0:
            pred_raster = np.where(np.isnan(pred_raster), np.nan, np.maximum(pred_raster, 0))

        fallback_variables = sorted(
            {r.get("variable") for r in future_dynamic if used_fallback and r.get("variable")}
            | set(fallback_aligned.keys())
        )
        used_any_historical_fallback = bool(used_fallback or fallback_variables)
        prediction_mode = "historical_dynamic_fallback" if used_any_historical_fallback else "scenario_raster_prediction"
        risk_note = ""
        gate_verdict = ctx.get("gate_verdict", PASS)
        if used_any_historical_fallback:
            risk_note = (
                "Prediction used latest historical dynamic rasters for missing scenario inputs; "
                "treat this output as risk-labeled fallback evidence, not a complete future scenario forecast."
            )
            gate_verdict = BLOCK if ctx.get("gate_verdict") == BLOCK else PASS_WITH_RISKS
            if ctx.get("gate_verdict") != BLOCK:
                ctx["gate_verdict"] = PASS_WITH_RISKS

        state["predictions"] = {
            "scenario": scenario,
            "prediction_mode": prediction_mode,
            "risk_note": risk_note,
            "fallback_variables": fallback_variables,
            "used_fallback_dynamic": used_any_historical_fallback,
            "pred_raster": pred_raster,
            "uncert_raster": uncert_raster,
            "transform": ref_transform,
            "crs": ref_raster["crs"],
            "shape": (height, width),
            "mean_erosion": float(np.nanmean(pred_raster)),
            "max_erosion": float(np.nanmax(pred_raster)),
            "neg_clipped": neg_count,
            "high_risk_ratio": float((uncert_raster > 1.5).sum() / np.isfinite(uncert_raster).sum() * 100) if np.isfinite(uncert_raster).sum() > 0 else 0,
            "run_id": ctx.get("run_id"),
        }

        pred_npy = os.path.join(ctx["paths"]["predictions"], f"pred_{scenario}.npy")
        uncert_npy = os.path.join(ctx["paths"]["predictions"], f"uncert_{scenario}.npy")
        np.save(pred_npy, pred_raster)
        np.save(uncert_npy, uncert_raster)
        pred_meta = os.path.join(ctx["paths"]["predictions"], f"pred_{scenario}_meta.json")
        _write_json(pred_meta, {
            "run_id": ctx.get("run_id"),
            "scenario": scenario,
            "prediction_mode": prediction_mode,
            "risk_note": risk_note,
            "fallback_variables": fallback_variables,
            "used_fallback_dynamic": used_any_historical_fallback,
            "shape": [int(height), int(width)],
            "mean_erosion": float(np.nanmean(pred_raster)),
            "max_erosion": float(np.nanmax(pred_raster)),
            "neg_clipped": int(neg_count),
            "high_risk_ratio_pct": float(state["predictions"]["high_risk_ratio"]),
        })
        state["predictions"].update({
            "pred_path": pred_npy,
            "uncertainty_path": uncert_npy,
            "pred_meta_path": pred_meta,
        })
        _record_evidence_path(state, pred_npy)
        _record_evidence_path(state, uncert_npy)
        _record_evidence_path(state, pred_meta)

        return {
            "status": "ok",
            "scenario": scenario,
            "prediction_mode": prediction_mode,
            "model_used": best_algo,
            "mean_erosion": round(state["predictions"]["mean_erosion"], 2),
            "max_erosion": round(state["predictions"]["max_erosion"], 2),
            "high_risk_ratio_pct": round(state["predictions"]["high_risk_ratio"], 1),
            "fallback_variables": fallback_variables,
            "used_fallback_dynamic": used_any_historical_fallback,
            "run_id": ctx.get("run_id"),
            "evidence_paths": [pred_npy, uncert_npy, pred_meta],
            "gate_verdict": gate_verdict,
            "risk_note": risk_note,
            "message": f"Prediction complete for {scenario} with {best_algo}.",
        }
    except Exception as e:
        traceback.print_exc()
        return {
            "status": "error",
            "error_type": type(e).__name__,
            "message": str(e),
            "suggested_action": "predict_future failed.",
        }

def visualize(state: dict, target: str) -> dict:
    """Render charts/maps from current state."""
    try:
        if target == "metrics":
            models = state.get("models", {}) or {}
            if not models:
                return {
                    "status": "error",
                    "error_type": "NoData",
                    "message": "No model metrics available.",
                    "suggested_action": "Run train_candidates first.",
                }
            ctx = _get_complete_run_context(state, required_dirs=("reports",))
            reports_dir = ctx["paths"]["reports"]
            output_dpi = int(ctx.get("output_dpi", DEFAULT_OUTPUT_DPI))
            rows = []
            for algo, info in models.items():
                m = info.get("metrics", {})
                rows.append({
                    "algorithm": algo,
                    "mae": m.get("mae", np.nan),
                    "rmse": m.get("rmse", np.nan),
                    "r2": m.get("r2", np.nan),
                })
            fig = plot_metrics_comparison(pd.DataFrame(rows))
            img_b64 = fig_to_base64(fig)
            artifact_path = os.path.join(reports_dir, "viz_metrics.png")
            _save_figure(fig, artifact_path, output_dpi)
            _record_evidence_path(state, artifact_path)
            return {
                "status": "ok",
                "target": "metrics",
                "image_base64": img_b64,
                "artifact_path": artifact_path,
                "evidence_paths": [artifact_path],
                "message": "Metrics chart generated.",
            }

        if target == "importance":
            diag = state.get("_diagnostics", {})
            if not diag:
                return {
                    "status": "error",
                    "error_type": "NoData",
                    "message": "No diagnostics found.",
                    "suggested_action": "Run select_best first.",
                }
            ctx = _get_complete_run_context(state, required_dirs=("reports",))
            reports_dir = ctx["paths"]["reports"]
            output_dpi = int(ctx.get("output_dpi", DEFAULT_OUTPUT_DPI))
            fig = plot_feature_importance(diag["feature_names"], diag["importance"], title=f"Feature Importance ({state.get('best_model', 'model')})")
            img_b64 = fig_to_base64(fig)
            artifact_path = os.path.join(reports_dir, "viz_feature_importance.png")
            _save_figure(fig, artifact_path, output_dpi)
            _record_evidence_path(state, artifact_path)
            return {
                "status": "ok",
                "target": "importance",
                "image_base64": img_b64,
                "artifact_path": artifact_path,
                "evidence_paths": [artifact_path],
                "message": "Feature importance chart generated.",
            }

        if target == "scatter":
            diag = state.get("_diagnostics", {})
            if not diag:
                return {
                    "status": "error",
                    "error_type": "NoData",
                    "message": "No diagnostics found.",
                    "suggested_action": "Run select_best first.",
                }
            ctx = _get_complete_run_context(state, required_dirs=("reports",))
            reports_dir = ctx["paths"]["reports"]
            output_dpi = int(ctx.get("output_dpi", DEFAULT_OUTPUT_DPI))
            fig1 = plot_scatter_prediction(diag["y_true"], diag["y_pred"])
            img1 = fig_to_base64(fig1)
            artifact_path = os.path.join(reports_dir, "viz_scatter.png")
            _save_figure(fig1, artifact_path, output_dpi)
            _record_evidence_path(state, artifact_path)
            fig2 = plot_residual_distribution(diag["residuals"])
            img2 = fig_to_base64(fig2)
            residual_artifact_path = os.path.join(reports_dir, "viz_residual_distribution.png")
            _save_figure(fig2, residual_artifact_path, output_dpi)
            _record_evidence_path(state, residual_artifact_path)
            evidence_paths = [artifact_path, residual_artifact_path]
            return {
                "status": "ok",
                "target": "scatter",
                "image_base64": img1,
                "residual_image_base64": img2,
                "artifact_path": artifact_path,
                "residual_artifact_path": residual_artifact_path,
                "evidence_paths": evidence_paths,
                "message": "Scatter and residual charts generated.",
            }

        if target == "map":
            pred = state.get("predictions") or {}
            if not pred:
                return {
                    "status": "error",
                    "error_type": "NoData",
                    "message": "No prediction raster found.",
                    "suggested_action": "Run predict_future first.",
                }
            ctx = _get_complete_run_context(state, required_dirs=("predictions",))
            predictions_dir = ctx["paths"]["predictions"]
            html_map = create_folium_map(pred["pred_raster"], pred["transform"], crs=pred.get("crs", DEFAULT_CRS), title=f"Future Erosion ({pred.get('scenario','')})")
            from utils.viz import raster_to_thumbnail_base64
            thumb = raster_to_thumbnail_base64(pred["pred_raster"])
            html_path = os.path.join(predictions_dir, "viz_prediction_map.html")
            _write_text(html_path, html_map)
            _record_evidence_path(state, html_path)
            return {
                "status": "ok",
                "target": "map",
                "folium_html": html_map,
                "image_base64": thumb,
                "html_path": html_path,
                "evidence_paths": [html_path],
                "message": "Prediction map generated.",
            }

        if target == "uncertainty":
            pred = state.get("predictions") or {}
            if not pred or pred.get("uncert_raster") is None:
                return {
                    "status": "error",
                    "error_type": "NoData",
                    "message": "No uncertainty raster found.",
                    "suggested_action": "Run predict_future first.",
                }
            ctx = _get_complete_run_context(state, required_dirs=("predictions",))
            predictions_dir = ctx["paths"]["predictions"]
            html_map = create_folium_map(pred["uncert_raster"], pred["transform"], crs=pred.get("crs", DEFAULT_CRS), title="Extrapolation Uncertainty", cmap="RdYlBu_r")
            html_path = os.path.join(predictions_dir, "viz_uncertainty_map.html")
            _write_text(html_path, html_map)
            _record_evidence_path(state, html_path)
            return {
                "status": "ok",
                "target": "uncertainty",
                "folium_html": html_map,
                "html_path": html_path,
                "evidence_paths": [html_path],
                "message": "Uncertainty map generated.",
            }

        return {
            "status": "error",
            "error_type": "InvalidTarget",
            "message": f"Unsupported visualization target: {target}",
            "suggested_action": "Use one of: map, metrics, importance, scatter, uncertainty.",
        }
    except Exception as e:
        traceback.print_exc()
        return {
            "status": "error",
            "error_type": type(e).__name__,
            "message": str(e),
            "suggested_action": "visualize failed.",
        }


def assess_data_quality(state: dict) -> dict:
    """Assess uploaded data quality and RUSLE factor coverage."""
    try:
        uploads = state.get("uploads", {}) or {}
        if not uploads:
            return {
                "status": "error",
                "error_type": "NoData",
                "message": "No uploaded files.",
                "suggested_action": "Upload GeoTIFF files first.",
            }

        inspect_result = inspect_uploads(state)
        if inspect_result.get("status") == "error":
            return inspect_result

        issues = []
        warnings_list = []
        info_items = []

        required_vars = {"R", "K", "LS", "C", "P"}
        available_vars = set(inspect_result.get("variables", {}).keys())
        missing_vars = required_vars - available_vars
        if missing_vars:
            issues.append(f"Missing required RUSLE factors: {', '.join(sorted(missing_vars))}")
        else:
            info_items.append("All RUSLE factors are available.")

        label_years = inspect_result.get("label_years", [])
        if not label_years:
            issues.append("No label_YYYY rasters found.")
        elif len(label_years) < 2:
            warnings_list.append(f"Only {len(label_years)} label year(s); more years are recommended.")
        else:
            info_items.append(f"Label years: {', '.join(label_years)}")

        corrupt_files = []
        value_issues = []
        for fname, fmeta in uploads.items():
            info = parse_filename(fname)
            if not info:
                continue
            fp = fmeta.get("filepath", "")
            if not fp or not os.path.exists(fp):
                corrupt_files.append(fname)
                continue
            try:
                meta = read_raster(fp)
                data = meta["data"]
                valid = data[~np.isnan(data)]
                if len(valid) == 0:
                    corrupt_files.append(fname)
                elif info["variable"] == "label" and float(np.max(valid)) > 500:
                    value_issues.append(f"{fname}: unusually high label max={float(np.max(valid)):.2f}")
                elif info["variable"] in ("K", "C", "P") and float(np.max(valid)) > 1.5:
                    value_issues.append(f"{fname}: {info['variable']} max={float(np.max(valid)):.3f} > 1.5")
            except Exception:
                corrupt_files.append(fname)

        if corrupt_files:
            issues.append(f"Unreadable/invalid files: {len(corrupt_files)}")
        else:
            info_items.append("All uploaded rasters are readable.")
        if value_issues:
            warnings_list.extend(value_issues)

        future_scenarios = inspect_result.get("future_scenarios", [])
        if not future_scenarios:
            warnings_list.append("No scenario rasters found; predict_future may use historical fallback.")
        else:
            info_items.append(f"Scenarios: {', '.join(sorted(future_scenarios))}")

        if issues:
            quality = "poor" if len(issues) >= 2 else "fair"
        elif len(warnings_list) >= 3:
            quality = "fair"
        elif warnings_list:
            quality = "good"
        else:
            quality = "excellent"

        result = {
            "status": "ok",
            "overall_quality": quality,
            "quality_label": quality,
            "quality_icon": {"excellent": "✅", "good": "🟢", "fair": "🟡", "poor": "🔴"}[quality],
            "issues": issues,
            "warnings": warnings_list,
            "info_items": info_items,
            "missing_variables": sorted(list(missing_vars)),
            "label_years": label_years,
            "future_scenarios": future_scenarios,
            "available_variables": sorted(list(available_vars)),
            "can_train": inspect_result.get("can_train", False),
            "can_predict": inspect_result.get("can_predict", False),
            "total_files": inspect_result.get("total_files", 0),
            "variables": inspect_result.get("variables", {}),
            "summary": "\n\n".join([
                "INFO: " + " | ".join(info_items) if info_items else "",
                "WARN: " + " | ".join(warnings_list) if warnings_list else "",
                "ISSUE: " + " | ".join(issues) if issues else "",
            ]).strip(),
            "message": f"Data quality={quality}; issues={len(issues)}, warnings={len(warnings_list)}",
        }
        state["_quality_report"] = result
        return result
    except Exception as e:
        traceback.print_exc()
        return {
            "status": "error",
            "error_type": type(e).__name__,
            "message": str(e),
            "suggested_action": "assess_data_quality failed.",
        }


# ============================================================
# P0-P3 new public tools
# ============================================================
def prepare_run_context(state: dict,
                        run_mode: str = "quick",
                        source_mode: str = "rusle_raw",
                        output_dpi: int = DEFAULT_OUTPUT_DPI,
                        run_id: Optional[str] = None,
                        source_dir: Optional[str] = None,
                        cleanup_history: bool = False,
                        max_keep_runs: int = 12) -> dict:
    """Initialize a new run context and evidence tree under data/runs/<run_id>."""
    try:
        ctx = _resolve_run_context(
            state=state,
            run_id=run_id,
            run_mode=run_mode,
            source_mode=source_mode,
            output_dpi=output_dpi,
            source_dir=source_dir,
            force_new=True,
        )
        cleanup_info = {"removed": [], "kept": max_keep_runs}
        if cleanup_history:
            cleanup_info = _safe_cleanup_runs(max_keep=max_keep_runs)

        summary_path = os.path.join(ctx["paths"]["reports"], "stage_summary.md")
        _write_text(summary_path, (
            "## 阶段回报模板\n"
            "【阶段】\n【已完成】\n【未完成】\n【风险等级】\n【阻断项】\n【证据路径】\n【下一步】\n"
        ))
        _record_evidence_path(state, summary_path)

        raw_index_path = None
        if source_mode == "rusle_raw":
            raw_index_path = _write_raw_source_index_metadata(
                state=state,
                run_context=ctx,
                target_resolution_km=5.0,
            )

        full_preflight_path = None
        full_preflight = None
        if source_mode == "rusle_raw" and run_mode == "full":
            full_preflight = _full_resource_preflight(ctx.get("source_dir", DEFAULT_RUSLE_SOURCE_DIR))
            full_preflight_path = os.path.join(ctx["paths"]["inputs"], "full_resource_preflight.json")
            _write_json(full_preflight_path, full_preflight)
            _record_evidence_path(state, full_preflight_path)
            ctx["full_preflight_path"] = full_preflight_path
            state["_full_resource_preflight"] = {**full_preflight, "path": full_preflight_path}

        return {
            "status": "ok",
            "run_id": ctx["run_id"],
            "run_mode": run_mode,
            "source_mode": source_mode,
            "output_dpi": int(output_dpi),
            "run_root": ctx["paths"]["root"],
            "manifest_path": ctx["manifest_path"],
            "cleanup": cleanup_info,
            "raw_source_index_path": raw_index_path,
            "full_preflight_path": full_preflight_path,
            "full_preflight": full_preflight,
            "evidence_paths": [p for p in [ctx["manifest_path"], summary_path, raw_index_path, full_preflight_path] if p],
            "gate_verdict": ctx.get("gate_verdict", PASS),
            "message": f"Run context ready: {ctx['run_id']}",
        }
    except Exception as e:
        return {
            "status": "error",
            "error_type": type(e).__name__,
            "message": str(e),
            "suggested_action": "prepare_run_context failed.",
        }


def prepare_full_resource_preflight(state: dict,
                                    source_dir: Optional[str] = None,
                                    target_resolution_km: float = 5.0,
                                    run_id: Optional[str] = None) -> dict:
    """Write a metadata-only full-mode resource preflight for raw RUSLE source data."""
    try:
        ctx = _get_or_prepare_context(
            state=state,
            run_mode="full",
            source_mode="rusle_raw",
            output_dpi=DEFAULT_OUTPUT_DPI,
            run_id=run_id,
            source_dir=source_dir,
        )
        source_dir = source_dir or ctx.get("source_dir", DEFAULT_RUSLE_SOURCE_DIR)
        preflight = _full_resource_preflight(source_dir=source_dir, target_resolution_km=target_resolution_km)
        preflight_path = os.path.join(ctx["paths"]["inputs"], "full_resource_preflight.json")
        _write_json(preflight_path, preflight)
        _record_evidence_path(state, preflight_path)
        ctx["full_preflight_path"] = preflight_path
        state["_full_resource_preflight"] = {**preflight, "path": preflight_path}
        return {
            "status": "ok",
            "run_id": ctx.get("run_id"),
            "preflight_path": preflight_path,
            "risk_level": preflight.get("risk_level"),
            "warnings": preflight.get("warnings", []),
            "file_count": preflight.get("file_count"),
            "total_size_gb": preflight.get("total_size_gb"),
            "selected_full_years": preflight.get("selected_full_years", []),
            "evidence_paths": [preflight_path],
            "message": f"Full resource preflight complete: risk={preflight.get('risk_level')}",
        }
    except Exception as e:
        return {
            "status": "error",
            "error_type": type(e).__name__,
            "message": str(e),
            "suggested_action": "prepare_full_resource_preflight failed.",
        }


def plan_full_execution(state: dict,
                        source_dir: Optional[str] = None,
                        target_resolution_km: float = 5.0,
                        year_window_size: int = 2,
                        max_tile_pixels: int = 250_000_000,
                        run_id: Optional[str] = None) -> dict:
    """Write a metadata-only, year-windowed full-mode execution plan."""
    try:
        ctx = _get_or_prepare_context(
            state=state,
            run_mode="full",
            source_mode="rusle_raw",
            output_dpi=DEFAULT_OUTPUT_DPI,
            run_id=run_id,
            source_dir=source_dir,
        )
        source_dir = source_dir or ctx.get("source_dir", DEFAULT_RUSLE_SOURCE_DIR)
        plan = _plan_full_execution(
            source_dir=source_dir,
            target_resolution_km=target_resolution_km,
            year_window_size=year_window_size,
            max_tile_pixels=max_tile_pixels,
        )
        plan_path = os.path.join(ctx["paths"]["inputs"], "full_execution_plan.json")
        _write_json(plan_path, plan)
        _record_evidence_path(state, plan_path)
        state["_full_execution_plan"] = {**plan, "path": plan_path}
        ctx["full_execution_plan_path"] = plan_path
        risk_levels = [b.get("risk_level") for b in plan.get("batches", [])]
        risk_level = "high" if "high" in risk_levels else ("medium" if "medium" in risk_levels else "low")
        return {
            "status": "ok",
            "run_id": ctx.get("run_id"),
            "plan_path": plan_path,
            "batch_count": len(plan.get("batches", [])),
            "year_count": len(plan.get("preflight", {}).get("selected_full_years", [])),
            "risk_level": risk_level,
            "source_read_only": True,
            "evidence_paths": [plan_path],
            "message": (
                f"Full execution plan ready: {len(plan.get('batches', []))} batches, "
                f"risk={risk_level}. This is not a full execution proof."
            ),
        }
    except Exception as e:
        return {
            "status": "error",
            "error_type": type(e).__name__,
            "message": str(e),
            "suggested_action": "plan_full_execution failed.",
        }


def run_full_batch_smoke(state: dict,
                         plan_path: Optional[str] = None,
                         batch_id: str = "full_batch_001",
                         execute: bool = False,
                         max_source_size_gb: float = 2.0,
                         max_pixels: int = 250_000_000,
                         run_id: Optional[str] = None) -> dict:
    """Safety-gated smoke runner for one planned full-mode batch.

    The default is a dry-run safety report. It does not process rasters unless
    execute=True and the batch is within resource limits.
    """
    try:
        ctx = state.get("run_context")
        if not ctx:
            ctx = _get_or_prepare_context(
                state=state,
                run_mode="full",
                source_mode="rusle_raw",
                output_dpi=DEFAULT_OUTPUT_DPI,
                run_id=run_id,
            )

        if not plan_path:
            plan_path = (state.get("_full_execution_plan") or {}).get("path") or ctx.get("full_execution_plan_path")
        if not plan_path or not os.path.exists(plan_path):
            plan_result = plan_full_execution(state, run_id=ctx.get("run_id"))
            if plan_result.get("status") != "ok":
                return plan_result
            plan_path = plan_result.get("plan_path")

        with open(plan_path, "r", encoding="utf-8") as f:
            plan = json.load(f)

        batches = plan.get("batches", []) or []
        batch = next((b for b in batches if b.get("batch_id") == batch_id), None)
        if not batch:
            return {
                "status": "error",
                "error_type": "BatchNotFound",
                "message": f"Batch not found: {batch_id}",
                "suggested_action": "Use a batch_id from full_execution_plan.json.",
            }

        estimated_gb = float(batch.get("estimated_source_size_gb", 0.0) or 0.0)
        batch_pixels = int(batch.get("max_pixels", 0) or 0)
        blockers = []
        if estimated_gb > float(max_source_size_gb):
            blockers.append(f"estimated_source_size_gb {estimated_gb:.4f} > limit {float(max_source_size_gb):.4f}")
        if batch_pixels > int(max_pixels):
            blockers.append(f"max_pixels {batch_pixels} > limit {int(max_pixels)}")

        would_execute = bool(execute and not blockers)
        verdict = PASS if would_execute else (BLOCK if execute and blockers else PASS_WITH_RISKS)
        mode = "execute_allowed" if would_execute else ("blocked_execute" if execute else "dry_run")
        report = {
            "run_id": ctx.get("run_id"),
            "plan_path": plan_path,
            "batch_id": batch_id,
            "years": batch.get("years", []),
            "execute_requested": bool(execute),
            "execution_mode": mode,
            "source_read_only": True,
            "estimated_source_size_gb": estimated_gb,
            "max_pixels": batch_pixels,
            "limits": {
                "max_source_size_gb": float(max_source_size_gb),
                "max_pixels": int(max_pixels),
            },
            "blockers": blockers,
            "verdict": verdict,
            "claim_boundary": (
                "Dry-run or blocked smoke reports do not prove full batch runtime success. "
                "A PASS here only means the batch is under configured metadata limits."
            ),
        }

        report_path = os.path.join(ctx["paths"]["gates"], f"{batch_id}_smoke.json")
        _write_json(report_path, report)
        _record_evidence_path(state, report_path)
        state["_full_batch_smoke"] = {**report, "path": report_path}
        _append_jsonl(os.path.join(ctx["paths"]["reports"], RUN_LOG_NAME), {
            "ts": _now_iso(),
            "stage": "FULL_BATCH_SMOKE",
            "event": "run_full_batch_smoke",
            "run_id": ctx.get("run_id"),
            "batch_id": batch_id,
            "verdict": verdict,
            "execution_mode": mode,
        })

        if verdict == BLOCK:
            ctx["gate_verdict"] = BLOCK
        elif ctx.get("gate_verdict") != BLOCK and verdict == PASS_WITH_RISKS:
            ctx["gate_verdict"] = PASS_WITH_RISKS

        return {
            "status": "ok",
            "run_id": ctx.get("run_id"),
            "batch_id": batch_id,
            "years": batch.get("years", []),
            "execution_mode": mode,
            "verdict": verdict,
            "blockers": blockers,
            "report_path": report_path,
            "evidence_paths": [report_path],
            "gate_verdict": ctx.get("gate_verdict", verdict),
            "message": f"Full batch smoke {batch_id}: {verdict} ({mode})",
        }
    except Exception as e:
        return {
            "status": "error",
            "error_type": type(e).__name__,
            "message": str(e),
            "suggested_action": "run_full_batch_smoke failed.",
        }


def plan_full_spatial_tiles(state: dict,
                            plan_path: Optional[str] = None,
                            batch_id: str = "full_batch_001",
                            tile_width: int = 4096,
                            tile_height: int = 4096,
                            max_tile_pixels: int = 25_000_000,
                            run_id: Optional[str] = None) -> dict:
    """Create a metadata-only spatial tile plan for one full-mode batch."""
    try:
        ctx = state.get("run_context")
        if not ctx:
            ctx = _get_or_prepare_context(
                state=state,
                run_mode="full",
                source_mode="rusle_raw",
                output_dpi=DEFAULT_OUTPUT_DPI,
                run_id=run_id,
            )

        if not plan_path:
            plan_path = (state.get("_full_execution_plan") or {}).get("path") or ctx.get("full_execution_plan_path")
        if not plan_path or not os.path.exists(plan_path):
            plan_result = plan_full_execution(state, run_id=ctx.get("run_id"))
            if plan_result.get("status") != "ok":
                return plan_result
            plan_path = plan_result.get("plan_path")

        with open(plan_path, "r", encoding="utf-8") as f:
            plan = json.load(f)
        batch = _find_batch_in_plan(plan, batch_id)
        if not batch:
            return {
                "status": "error",
                "error_type": "BatchNotFound",
                "message": f"Batch not found: {batch_id}",
                "suggested_action": "Use a batch_id from full_execution_plan.json.",
            }

        tile_plan = _plan_spatial_tiles_for_batch(
            batch=batch,
            tile_width=tile_width,
            tile_height=tile_height,
            max_tile_pixels=max_tile_pixels,
        )
        if tile_plan.get("status") == "error":
            return {
                "status": "error",
                "error_type": tile_plan.get("error_type", "TilePlanError"),
                "message": f"Failed to plan spatial tiles for {batch_id}.",
            }

        out_path = os.path.join(ctx["paths"]["inputs"], f"{batch_id}_spatial_tiles.json")
        _write_json(out_path, tile_plan)
        _record_evidence_path(state, out_path)
        state["_full_spatial_tile_plan"] = {**tile_plan, "path": out_path}
        return {
            "status": "ok",
            "run_id": ctx.get("run_id"),
            "batch_id": batch_id,
            "tile_plan_path": out_path,
            "tile_count": tile_plan.get("tile_count"),
            "source_read_only": True,
            "evidence_paths": [out_path],
            "message": f"Spatial tile plan ready for {batch_id}: {tile_plan.get('tile_count')} tiles.",
        }
    except Exception as e:
        return {
            "status": "error",
            "error_type": type(e).__name__,
            "message": str(e),
            "suggested_action": "plan_full_spatial_tiles failed.",
        }


def run_full_tile_smoke(state: dict,
                        tile_plan_path: Optional[str] = None,
                        tile_id: Optional[str] = None,
                        execute: bool = False,
                        max_tile_source_size_gb: float = 0.75,
                        max_tile_pixels: int = 25_000_000,
                        run_id: Optional[str] = None) -> dict:
    """Safety-gated smoke check for one spatial tile from a full batch plan."""
    try:
        ctx = state.get("run_context")
        if not ctx:
            ctx = _get_or_prepare_context(
                state=state,
                run_mode="full",
                source_mode="rusle_raw",
                output_dpi=DEFAULT_OUTPUT_DPI,
                run_id=run_id,
            )

        if not tile_plan_path:
            tile_plan_path = (state.get("_full_spatial_tile_plan") or {}).get("path")
        if not tile_plan_path or not os.path.exists(tile_plan_path):
            return {
                "status": "error",
                "error_type": "NoTilePlan",
                "message": "Spatial tile plan is missing.",
                "suggested_action": "Run plan_full_spatial_tiles first.",
            }

        with open(tile_plan_path, "r", encoding="utf-8") as f:
            tile_plan = json.load(f)
        tiles = tile_plan.get("tiles", []) or []
        tile = next((t for t in tiles if t.get("tile_id") == tile_id), None) if tile_id else (tiles[0] if tiles else None)
        if not tile:
            return {
                "status": "error",
                "error_type": "TileNotFound",
                "message": f"Tile not found: {tile_id}",
            }

        pixels = int(tile.get("estimated_pixels", 0) or 0)
        size_gb = float(tile.get("estimated_source_size_gb", 0.0) or 0.0)
        blockers = []
        if pixels > int(max_tile_pixels):
            blockers.append(f"estimated_pixels {pixels} > limit {int(max_tile_pixels)}")
        if size_gb > float(max_tile_source_size_gb):
            blockers.append(f"estimated_source_size_gb {size_gb:.6f} > limit {float(max_tile_source_size_gb):.6f}")

        would_execute = bool(execute and not blockers)
        verdict = PASS if would_execute else (BLOCK if execute and blockers else PASS_WITH_RISKS)
        mode = "execute_allowed" if would_execute else ("blocked_execute" if execute else "dry_run")
        report = {
            "run_id": ctx.get("run_id"),
            "tile_plan_path": tile_plan_path,
            "batch_id": tile_plan.get("batch_id"),
            "tile_id": tile.get("tile_id"),
            "tile": tile,
            "execute_requested": bool(execute),
            "execution_mode": mode,
            "source_read_only": True,
            "limits": {
                "max_tile_source_size_gb": float(max_tile_source_size_gb),
                "max_tile_pixels": int(max_tile_pixels),
            },
            "blockers": blockers,
            "verdict": verdict,
            "claim_boundary": "Tile smoke reports do not prove raster-window processing success unless an execute path is implemented and gated.",
        }
        report_path = os.path.join(ctx["paths"]["gates"], f"{tile.get('tile_id')}_smoke.json")
        _write_json(report_path, report)
        _record_evidence_path(state, report_path)
        state["_full_tile_smoke"] = {**report, "path": report_path}
        _append_jsonl(os.path.join(ctx["paths"]["reports"], RUN_LOG_NAME), {
            "ts": _now_iso(),
            "stage": "FULL_TILE_SMOKE",
            "event": "run_full_tile_smoke",
            "run_id": ctx.get("run_id"),
            "tile_id": tile.get("tile_id"),
            "verdict": verdict,
            "execution_mode": mode,
        })
        return {
            "status": "ok",
            "run_id": ctx.get("run_id"),
            "batch_id": tile_plan.get("batch_id"),
            "tile_id": tile.get("tile_id"),
            "execution_mode": mode,
            "verdict": verdict,
            "blockers": blockers,
            "report_path": report_path,
            "evidence_paths": [report_path],
            "message": f"Full tile smoke {tile.get('tile_id')}: {verdict} ({mode})",
        }
    except Exception as e:
        return {
            "status": "error",
            "error_type": type(e).__name__,
            "message": str(e),
            "suggested_action": "run_full_tile_smoke failed.",
        }


def run_full_tile_preprocess(state: dict,
                             plan_path: Optional[str] = None,
                             tile_plan_path: Optional[str] = None,
                             tile_id: str = "full_batch_001_tile_0001",
                             year: Optional[str] = None,
                             max_tile_pixels: int = 1_500_000,
                             max_records: int = 50_000,
                             run_id: Optional[str] = None) -> dict:
    """Read one bounded full-mode spatial tile and build a tile-level feature table."""
    try:
        ctx = state.get("run_context")
        if not ctx:
            ctx = _get_or_prepare_context(
                state=state,
                run_mode="full",
                source_mode="rusle_raw",
                output_dpi=DEFAULT_OUTPUT_DPI,
                run_id=run_id,
            )
        if not plan_path:
            plan_path = (state.get("_full_execution_plan") or {}).get("path") or ctx.get("full_execution_plan_path")
        if not tile_plan_path:
            tile_plan_path = (state.get("_full_spatial_tile_plan") or {}).get("path")
        if not plan_path or not os.path.exists(plan_path):
            return {"status": "error", "error_type": "NoFullPlan", "message": "full_execution_plan.json is missing."}
        if not tile_plan_path or not os.path.exists(tile_plan_path):
            return {"status": "error", "error_type": "NoTilePlan", "message": "spatial tile plan is missing."}

        with open(plan_path, "r", encoding="utf-8") as f:
            full_plan = json.load(f)
        with open(tile_plan_path, "r", encoding="utf-8") as f:
            tile_plan = json.load(f)
        tile = next((t for t in tile_plan.get("tiles", []) if t.get("tile_id") == tile_id), None)
        if not tile:
            return {"status": "error", "error_type": "TileNotFound", "message": f"Tile not found: {tile_id}"}
        pixels = int(tile.get("estimated_pixels", 0) or 0)
        if pixels > int(max_tile_pixels):
            report = {
                "run_id": ctx.get("run_id"),
                "tile_id": tile_id,
                "verdict": BLOCK,
                "blockers": [f"estimated_pixels {pixels} > limit {int(max_tile_pixels)}"],
                "source_read_only": True,
            }
            report_path = os.path.join(ctx["paths"]["gates"], f"{tile_id}_preprocess_gate.json")
            _write_json(report_path, report)
            _record_evidence_path(state, report_path)
            return {
                "status": "ok",
                "run_id": ctx.get("run_id"),
                "tile_id": tile_id,
                "verdict": BLOCK,
                "blockers": report["blockers"],
                "gate_path": report_path,
                "evidence_paths": [report_path],
                "message": f"Tile preprocess blocked: {tile_id}",
            }

        batch = _find_batch_in_plan(full_plan, tile_plan.get("batch_id"))
        if not batch:
            return {"status": "error", "error_type": "BatchNotFound", "message": f"Batch not found: {tile_plan.get('batch_id')}"}
        batch_years = [str(y) for y in batch.get("years", [])]
        target_year = str(year or (batch_years[0] if batch_years else ""))
        item = next((it for it in batch.get("items", []) if str(it.get("year")) == target_year), None)
        if not item:
            return {"status": "error", "error_type": "YearNotFound", "message": f"Year not found in batch: {target_year}"}

        ref_path = tile_plan.get("reference_raster", {}).get("filepath")
        if not ref_path or not os.path.exists(ref_path):
            return {"status": "error", "error_type": "ReferenceMissing", "message": "Reference raster path is missing."}
        ref_window = Window(
            col_off=int(tile["col_off"]),
            row_off=int(tile["row_off"]),
            width=int(tile["width"]),
            height=int(tile["height"]),
        )
        ref_meta = _read_window_meta(ref_path, window=ref_window)
        if not ref_meta:
            return {"status": "error", "error_type": "EmptyReferenceWindow", "message": "Reference window is empty."}
        template_transform = ref_meta["transform"]
        template_crs = ref_meta["crs"]
        template_shape = ref_meta["data"].shape
        template_bounds = ref_meta["bounds"]

        label_tiles = item.get("label_tiles", []) or []
        if not label_tiles:
            return {"status": "error", "error_type": "NoLabelTiles", "message": f"No label tiles for {target_year}."}
        label_arrays = []
        for meta in label_tiles:
            fp = meta.get("filepath")
            if not fp or not os.path.exists(fp):
                continue
            sub = _read_window_meta(fp, bounds=template_bounds, bounds_crs=template_crs)
            if sub is None:
                continue
            aligned = _align_meta_to_template(sub, template_transform, template_crs, template_shape, is_label=True)
            label_arrays.append(aligned["data"])
        if not label_arrays:
            return {"status": "error", "error_type": "NoLabelOverlap", "message": f"No label overlap for tile {tile_id}."}
        label_arr = label_arrays[0].copy()
        for arr in label_arrays[1:]:
            label_arr = np.where(np.isfinite(label_arr), label_arr, arr)

        factor_paths = {
            "C": (item.get("c_factor") or {}).get("filepath"),
        }
        for f in full_plan.get("static_factors", []) or []:
            meta = f.get("meta") or {}
            factor_paths[f.get("variable")] = meta.get("filepath")
        arrays = {}
        warnings_list = []
        for var in ["R", "K", "LS", "P", "C"]:
            fp = factor_paths.get(var)
            if not fp or not os.path.exists(fp):
                warnings_list.append(f"missing factor path: {var}")
                continue
            sub = _read_window_meta(fp, bounds=template_bounds, bounds_crs=template_crs)
            if sub is None:
                warnings_list.append(f"no overlap: {var}")
                continue
            aligned = _align_meta_to_template(sub, template_transform, template_crs, template_shape, is_label=False)
            arrays[var] = aligned["data"]
        missing = [v for v in ["R", "K", "LS", "P", "C"] if v not in arrays]
        out_dir = _ensure_dir(os.path.join(ctx["paths"]["features"], "full_tiles", tile_id))
        if missing:
            report = {
                "run_id": ctx.get("run_id"),
                "tile_id": tile_id,
                "year": target_year,
                "verdict": BLOCK,
                "blockers": [f"missing factors: {', '.join(missing)}"],
                "warnings": warnings_list,
                "source_read_only": True,
            }
            report_path = os.path.join(ctx["paths"]["gates"], f"{tile_id}_preprocess_gate.json")
            _write_json(report_path, report)
            _record_evidence_path(state, report_path)
            return {
                "status": "ok",
                "run_id": ctx.get("run_id"),
                "tile_id": tile_id,
                "verdict": BLOCK,
                "blockers": report["blockers"],
                "warnings": warnings_list,
                "gate_path": report_path,
                "evidence_paths": [report_path],
                "message": f"Tile preprocess blocked: {tile_id}",
            }

        df = _window_feature_records(arrays, label_arr, template_transform, target_year, max_records=max_records)
        if len(df) == 0:
            return {"status": "error", "error_type": "EmptyFeatureTable", "message": f"No valid feature records for {tile_id}."}
        feature_cols = ["R", "K", "LS", "P", "C"]
        audit = _build_preprocess_audit(
            source_mode="rusle_raw",
            feature_df=df,
            feature_cols=feature_cols,
            used_years=[target_year],
            staged_warnings=warnings_list + ["full tile window preprocessing; single spatial tile only"],
        )
        ft_path = os.path.join(out_dir, "feature_table.parquet")
        audit_path = os.path.join(out_dir, "preprocess_audit.json")
        meta_path = os.path.join(out_dir, "feature_table_meta.json")
        df.to_parquet(ft_path, index=False)
        _write_json(audit_path, audit)
        _write_json(meta_path, {
            "run_id": ctx.get("run_id"),
            "tile_id": tile_id,
            "year": target_year,
            "n_samples": int(len(df)),
            "n_features": int(len(feature_cols)),
            "feature_columns": feature_cols,
            "source_read_only": True,
            "max_records": int(max_records),
            "template_shape": [int(template_shape[0]), int(template_shape[1])],
            "tile": tile,
            "preprocess_audit_path": audit_path,
        })
        state["feature_table"] = {
            "path": ft_path,
            "n_samples": int(len(df)),
            "n_features": int(len(feature_cols)),
            "columns": feature_cols,
            "run_id": ctx.get("run_id"),
            "source_mode": "rusle_raw",
            "run_mode": "full_tile",
            "preprocess_audit_path": audit_path,
        }
        state["uploads"] = {"full_tile_window": {"filepath": ref_path, "size": int(os.path.getsize(ref_path)), "source": "rusle_raw"}}
        preflight_payload = full_plan.get("preflight")
        if preflight_payload:
            preflight_path = os.path.join(ctx["paths"]["inputs"], "full_resource_preflight.json")
            if not os.path.exists(preflight_path):
                _write_json(preflight_path, preflight_payload)
                _record_evidence_path(state, preflight_path)
                ctx["full_preflight_path"] = preflight_path
        _record_evidence_path(state, ft_path)
        _record_evidence_path(state, audit_path)
        _record_evidence_path(state, meta_path)
        gate = run_error_corrector(state, stage="P0", run_id=ctx.get("run_id"))
        tile_gate_path = os.path.join(ctx["paths"]["gates"], f"{tile_id}_p0_gate.json")
        tile_gate_payload = {
            **gate,
            "tile_id": tile_id,
            "year": target_year,
            "claim_boundary": "Tile-specific P0 gate copy; global p0_gate.json may be overwritten by later stage checks.",
        }
        _write_json(tile_gate_path, tile_gate_payload)
        _record_evidence_path(state, tile_gate_path)
        return {
            "status": "ok",
            "run_id": ctx.get("run_id"),
            "tile_id": tile_id,
            "year": target_year,
            "n_samples": int(len(df)),
            "n_features": int(len(feature_cols)),
            "feature_table_path": ft_path,
            "preprocess_audit_path": audit_path,
            "meta_path": meta_path,
            "gate_verdict": gate.get("verdict"),
            "gate_path": tile_gate_path,
            "stage_gate_path": gate.get("gate_path"),
            "evidence_paths": [ft_path, audit_path, meta_path, tile_gate_path] + gate.get("evidence_paths", []),
            "message": f"Full tile preprocess complete: {tile_id}, samples={len(df)}, gate={gate.get('verdict')}",
        }
    except Exception as e:
        traceback.print_exc()
        return {
            "status": "error",
            "error_type": type(e).__name__,
            "message": str(e),
            "suggested_action": "run_full_tile_preprocess failed.",
        }


def run_full_tile_coverage_probe(state: dict,
                                 plan_path: Optional[str] = None,
                                 tile_plan_path: Optional[str] = None,
                                 tile_ids: Optional[List[str]] = None,
                                 tile_start_index: int = 1,
                                 tile_count: int = 8,
                                 tile_stride: int = 1,
                                 year: Optional[str] = None,
                                 max_tile_pixels: int = 1_500_000,
                                 max_records_per_tile: int = 20_000,
                                 max_probe_tiles: int = 20,
                                 run_id: Optional[str] = None) -> dict:
    """Probe a bounded set of full-mode tiles and record success/failure coverage."""
    try:
        ctx = state.get("run_context")
        if not ctx:
            ctx = _get_or_prepare_context(
                state=state,
                run_mode="full",
                source_mode="rusle_raw",
                output_dpi=DEFAULT_OUTPUT_DPI,
                run_id=run_id,
            )
        if not tile_plan_path:
            tile_plan_path = (state.get("_full_spatial_tile_plan") or {}).get("path")
        if not tile_plan_path or not os.path.exists(tile_plan_path):
            return {
                "status": "error",
                "error_type": "NoTilePlan",
                "message": "spatial tile plan is missing.",
                "suggested_action": "Run plan_full_spatial_tiles first.",
            }
        with open(tile_plan_path, "r", encoding="utf-8") as f:
            tile_plan = json.load(f)
        all_tiles = tile_plan.get("tiles", []) or []
        known_ids = {t.get("tile_id") for t in all_tiles}

        if tile_ids:
            selected_ids = [str(t) for t in tile_ids if str(t) in known_ids]
            missing_ids = [str(t) for t in tile_ids if str(t) not in known_ids]
        else:
            start = max(1, int(tile_start_index or 1))
            count = max(1, int(tile_count or 1))
            stride = max(1, int(tile_stride or 1))
            indices = [start + i * stride for i in range(count)]
            selected_ids = [f"{tile_plan.get('batch_id', 'full_batch')}_tile_{idx:04d}" for idx in indices]
            missing_ids = [tid for tid in selected_ids if tid not in known_ids]
            selected_ids = [tid for tid in selected_ids if tid in known_ids]

        if not selected_ids:
            return {
                "status": "error",
                "error_type": "NoProbeTiles",
                "message": "No valid tiles selected for coverage probe.",
                "missing_tile_ids": missing_ids,
            }
        selected_ids = selected_ids[:max(1, int(max_probe_tiles or 1))]

        results = []
        for tid in selected_ids:
            res = run_full_tile_preprocess(
                state=state,
                plan_path=plan_path,
                tile_plan_path=tile_plan_path,
                tile_id=tid,
                year=year,
                max_tile_pixels=max_tile_pixels,
                max_records=max_records_per_tile,
                run_id=ctx.get("run_id"),
            )
            results.append({
                "tile_id": tid,
                "status": res.get("status"),
                "error_type": res.get("error_type"),
                "message": res.get("message"),
                "n_samples": res.get("n_samples"),
                "gate_verdict": res.get("gate_verdict") or res.get("verdict"),
                "blockers": res.get("blockers"),
                "feature_table_path": res.get("feature_table_path"),
                "preprocess_audit_path": res.get("preprocess_audit_path"),
                "gate_path": res.get("gate_path"),
            })

        success = [r for r in results if r.get("status") == "ok" and int(r.get("n_samples") or 0) > 0]
        failed = [r for r in results if r not in success]
        by_error: Dict[str, int] = {}
        for r in failed:
            key = r.get("error_type") or r.get("gate_verdict") or "unknown"
            by_error[key] = by_error.get(key, 0) + 1

        payload = {
            "run_id": ctx.get("run_id"),
            "batch_id": tile_plan.get("batch_id"),
            "year": str(year or ""),
            "tile_plan_path": tile_plan_path,
            "selected_tile_ids": selected_ids,
            "missing_tile_ids": missing_ids,
            "limits": {
                "max_tile_pixels": int(max_tile_pixels),
                "max_records_per_tile": int(max_records_per_tile),
                "max_probe_tiles": int(max_probe_tiles),
            },
            "total_planned_tiles": int(tile_plan.get("tile_count", len(all_tiles)) or len(all_tiles)),
            "probed_tiles": len(results),
            "successful_tiles": len(success),
            "failed_tiles": len(failed),
            "success_rate_pct": float(len(success) / max(len(results), 1) * 100.0),
            "total_success_samples": int(sum(int(r.get("n_samples") or 0) for r in success)),
            "failure_counts": by_error,
            "results": results,
            "claim_boundary": (
                "Coverage probe proves only the selected bounded tiles. It does not prove full-batch, "
                "all-tile, all-year, or regional execution."
            ),
        }
        tag = f"{tile_plan.get('batch_id', 'full_batch')}_{selected_ids[0].split('_')[-1]}_{selected_ids[-1].split('_')[-1]}"
        out_path = os.path.join(ctx["paths"]["features"], "full_tiles", f"coverage_probe_{tag}.json")
        _write_json(out_path, payload)
        _record_evidence_path(state, out_path)
        _append_jsonl(os.path.join(ctx["paths"]["reports"], RUN_LOG_NAME), {
            "ts": _now_iso(),
            "stage": "FULL_TILE_COVERAGE_PROBE",
            "event": "run_full_tile_coverage_probe",
            "run_id": ctx.get("run_id"),
            "probed_tiles": len(results),
            "successful_tiles": len(success),
            "failed_tiles": len(failed),
        })
        return {
            "status": "ok",
            "run_id": ctx.get("run_id"),
            "batch_id": tile_plan.get("batch_id"),
            "probed_tiles": len(results),
            "successful_tiles": len(success),
            "failed_tiles": len(failed),
            "success_rate_pct": round(payload["success_rate_pct"], 2),
            "total_success_samples": payload["total_success_samples"],
            "failure_counts": by_error,
            "report_path": out_path,
            "evidence_paths": [out_path],
            "gate_verdict": PASS_WITH_RISKS,
            "message": f"Coverage probe complete: {len(success)}/{len(results)} tiles succeeded.",
        }
    except Exception as e:
        traceback.print_exc()
        return {
            "status": "error",
            "error_type": type(e).__name__,
            "message": str(e),
            "suggested_action": "run_full_tile_coverage_probe failed.",
        }


def run_error_corrector(state: dict, stage: str, run_id: Optional[str] = None) -> dict:
    """Auto-generated doc."""
    try:
        ctx = state.get("run_context")
        if not ctx:
            ctx = _resolve_run_context(state=state, run_id=run_id, force_new=False)

        stage_upper = str(stage).upper()
        checks = []
        checks.append({
            "name": "run_manifest_exists",
            "status": PASS if os.path.exists(ctx.get("manifest_path", "")) else BLOCK,
            "detail": ctx.get("manifest_path", ""),
        })
        checks.append({
            "name": "run_root_exists",
            "status": PASS if os.path.isdir(ctx.get("paths", {}).get("root", "")) else BLOCK,
            "detail": ctx.get("paths", {}).get("root", ""),
        })

        ft = state.get("feature_table") or {}
        models = state.get("models") or {}
        preds = state.get("predictions") or {}
        diag = state.get("_diagnostics") or {}
        uploads = state.get("uploads") or {}
        source_mode = str(ctx.get("source_mode", "uploads"))
        run_mode = str(ctx.get("run_mode", "quick"))

        if stage_upper in ("P0", "P1", "P2", "P3"):
            checks.append({
                "name": "data_gate_inputs_present",
                "status": PASS if bool(uploads) else BLOCK,
                "detail": {"upload_count": int(len(uploads)), "source_mode": source_mode},
            })

            if source_mode == "rusle_raw":
                raw_index_path = os.path.join(ctx["paths"]["inputs"], "raw_source_index.json")
                checks.append({
                    "name": "raw_source_staging_record",
                    "status": PASS if (os.path.exists(raw_index_path) or stage_upper == "P0") else BLOCK,
                    "detail": raw_index_path,
                })
                if run_mode == "full":
                    full_preflight_path = ctx.get("full_preflight_path") or os.path.join(ctx["paths"]["inputs"], "full_resource_preflight.json")
                    full_preflight = {}
                    if os.path.exists(full_preflight_path):
                        try:
                            with open(full_preflight_path, "r", encoding="utf-8") as f:
                                full_preflight = json.load(f) or {}
                        except Exception:
                            full_preflight = {}
                    checks.append({
                        "name": "full_resource_preflight",
                        "status": PASS if full_preflight else BLOCK,
                        "detail": full_preflight_path,
                    })
                    if full_preflight and full_preflight.get("risk_level") in ("medium", "high"):
                        checks.append({
                            "name": "full_resource_risk",
                            "status": PASS_WITH_RISKS,
                            "detail": {
                                "risk_level": full_preflight.get("risk_level"),
                                "warnings": full_preflight.get("warnings", []),
                            },
                        })
            else:
                checks.append({
                    "name": "raw_source_staging_record",
                    "status": PASS,
                    "detail": "skipped(source_mode=uploads)",
                })

            ft_meta_path = os.path.join(ctx["paths"]["features"], "feature_table_meta.json")
            ft_meta = {}
            if os.path.exists(ft_meta_path):
                try:
                    with open(ft_meta_path, "r", encoding="utf-8") as f:
                        ft_meta = json.load(f) or {}
                except Exception:
                    ft_meta = {}
            n_samples_meta = int(ft_meta.get("n_samples", ft.get("n_samples", 0)) or 0)
            n_features_meta = int(ft_meta.get("n_features", ft.get("n_features", 0)) or 0)
            checks.append({
                "name": "preprocess_alignment_ready",
                "status": PASS if (ft.get("path") and os.path.exists(ft["path"]) and n_samples_meta > 0 and n_features_meta > 0) else BLOCK,
                "detail": {
                    "feature_table": ft.get("path"),
                    "meta": ft_meta_path,
                    "n_samples": n_samples_meta,
                    "n_features": n_features_meta,
                },
            })

            preprocess_audit_path = ft.get("preprocess_audit_path") or ft_meta.get("preprocess_audit_path") or os.path.join(ctx["paths"]["features"], "preprocess_audit.json")
            preprocess_audit = {}
            if os.path.exists(preprocess_audit_path):
                try:
                    with open(preprocess_audit_path, "r", encoding="utf-8") as f:
                        preprocess_audit = json.load(f) or {}
                except Exception:
                    preprocess_audit = {}
            checks.append({
                "name": "preprocess_audit_exists",
                "status": PASS if bool(preprocess_audit) else BLOCK,
                "detail": preprocess_audit_path,
            })
            if preprocess_audit:
                required_ok = bool(preprocess_audit.get("required_ok", False))
                missing_factors = preprocess_audit.get("missing_factors", [])
                staged_warnings = preprocess_audit.get("staging_warnings", [])
                feature_coverage = preprocess_audit.get("feature_coverage_pct", {})

                if source_mode == "rusle_raw":
                    factor_status = PASS if required_ok else BLOCK
                else:
                    factor_status = PASS if required_ok else PASS_WITH_RISKS
                checks.append({
                    "name": "preprocess_factor_completeness",
                    "status": factor_status,
                    "detail": {
                        "required_ok": required_ok,
                        "missing_factors": missing_factors,
                    },
                })
                low_coverage = [k for k, v in feature_coverage.items() if float(v) < 50.0]
                checks.append({
                    "name": "preprocess_feature_coverage",
                    "status": PASS if not low_coverage else PASS_WITH_RISKS,
                    "detail": {"low_coverage_features": low_coverage},
                })
                if staged_warnings:
                    checks.append({
                        "name": "staging_warnings",
                        "status": PASS_WITH_RISKS,
                        "detail": staged_warnings,
                    })

        if stage_upper in ("P1", "P2", "P3"):
            checks.append({
                "name": "feature_table_ready",
                "status": PASS if ft.get("path") and os.path.exists(ft["path"]) else BLOCK,
                "detail": ft.get("path"),
            })

        if stage_upper in ("P1", "P2", "P3"):
            required_metric_keys = {"mae", "rmse", "r2", "nrmse", "pbias", "train_seconds"}
            has_metrics = bool(models)
            metric_ok = True
            missing_items = []
            for algo, info in models.items():
                keys = set((info.get("metrics") or {}).keys())
                miss = sorted(list(required_metric_keys - keys))
                if miss:
                    metric_ok = False
                    missing_items.append({algo: miss})
                metric_values = info.get("metrics", {})
                for mk in required_metric_keys:
                    mv = metric_values.get(mk, np.nan)
                    if not np.isfinite(float(mv)):
                        metric_ok = False
                        missing_items.append({algo: [f"{mk}=non_finite"]})
            checks.append({
                "name": "metrics_completeness",
                "status": PASS if has_metrics and metric_ok else BLOCK,
                "detail": missing_items if missing_items else "ok",
            })

        if stage_upper in ("P2", "P3"):
            explain_dir = ctx["paths"]["explanations"]
            spatial_dir = ctx["paths"]["spatial"]
            explain_pngs = [f for f in os.listdir(explain_dir)] if os.path.isdir(explain_dir) else []
            spatial_pngs = [f for f in os.listdir(spatial_dir)] if os.path.isdir(spatial_dir) else []
            checks.append({
                "name": "figure_completeness",
                "status": PASS if len(explain_pngs) >= 4 and len(spatial_pngs) >= 3 else PASS_WITH_RISKS,
                "detail": {"explanations": len(explain_pngs), "spatial": len(spatial_pngs)},
            })
            explain_meta = state.get("_explanation_meta", {})
            if explain_meta.get("explanation_mode") == "proxy":
                checks.append({
                    "name": "proxy_explanation_mode",
                    "status": PASS_WITH_RISKS,
                    "detail": explain_meta.get("shap_risk_note", "proxy contribution figures are not real SHAP values"),
                })
            if explain_meta.get("geoshapley_status") == "degraded":
                checks.append({
                    "name": "geoshapley_degraded",
                    "status": PASS_WITH_RISKS,
                    "detail": explain_meta.get("geoshapley_reason", "missing optional dependency"),
                })

        if stage_upper == "P3":
            report_path = LEGACY_REPORT_PATH
            checks.append({
                "name": "final_report_exists",
                "status": PASS if os.path.exists(report_path) else PASS_WITH_RISKS,
                "detail": report_path,
            })
            bundle_files = [
                os.path.join(ctx["paths"]["bundle"], "bundle_index.json"),
                os.path.join(ctx["paths"]["bundle"], "method_note.md"),
                os.path.join(ctx["paths"]["bundle"], "reproduce.md"),
                os.path.join(ctx["paths"]["bundle"], "gate_summary.json"),
            ]
            missing_bundle = [p for p in bundle_files if not os.path.exists(p)]
            checks.append({
                "name": "repro_evidence_ready",
                "status": PASS if not missing_bundle else BLOCK,
                "detail": {"missing": missing_bundle},
            })
            checks.append({
                "name": "prediction_ready",
                "status": PASS if bool(preds) else BLOCK,
                "detail": list(preds.keys()) if preds else "missing",
            })
            if preds.get("prediction_mode") == "historical_feature_replay":
                checks.append({
                    "name": "quick_prediction_replay_mode",
                    "status": PASS_WITH_RISKS,
                    "detail": "quick rusle_raw prediction replays latest historical feature grid; not a future scenario forecast",
                })
            if preds.get("prediction_mode") == "bounded_tile_feature_replay":
                checks.append({
                    "name": "bounded_tile_prediction_replay_mode",
                    "status": PASS_WITH_RISKS,
                    "detail": "bounded full-tile prediction replays a tile feature table; not a future forecast, full-batch prediction, or regional map",
                })
            if preds.get("prediction_mode") == "bounded_multi_tile_feature_replay":
                checks.append({
                    "name": "bounded_multi_tile_prediction_replay_mode",
                    "status": PASS_WITH_RISKS,
                    "detail": "bounded multi-tile prediction replays a sampled multi-tile feature table; not a future forecast, full-batch prediction, or regional map",
                })
            checks.append({
                "name": "diagnostics_ready",
                "status": PASS if bool(diag) else PASS_WITH_RISKS,
                "detail": "ok" if diag else "missing",
            })
            best_algo = state.get("best_model")
            best_metrics = (models.get(best_algo) or {}).get("metrics", {})
            best_r2 = best_metrics.get("r2", np.nan)
            best_rmse = best_metrics.get("rmse", np.nan)
            n_samples = int(ft.get("n_samples", 0) or 0)
            too_good = np.isfinite(float(best_r2)) and float(best_r2) > 0.995 and n_samples < 500
            checks.append({
                "name": "conclusion_strength_constraint",
                "status": PASS_WITH_RISKS if too_good else PASS,
                "detail": {
                    "best_algorithm": best_algo,
                    "best_r2": float(best_r2) if np.isfinite(float(best_r2)) else None,
                    "best_rmse": float(best_rmse) if np.isfinite(float(best_rmse)) else None,
                    "n_samples": n_samples,
                    "rule": "R2>0.995 and n_samples<500 triggers risk disclosure",
                },
            })

        payload = _error_corrector_payload(stage=stage, checks=checks)
        gate_path = os.path.join(ctx["paths"]["gates"], f"{stage.lower()}_gate.json")
        _write_json(gate_path, payload)
        _record_evidence_path(state, gate_path)

        ctx["gate_reports"][stage] = gate_path
        if payload["verdict"] == BLOCK:
            ctx["gate_verdict"] = BLOCK
        elif ctx.get("gate_verdict") != BLOCK and payload["verdict"] == PASS_WITH_RISKS:
            ctx["gate_verdict"] = PASS_WITH_RISKS

        _append_jsonl(os.path.join(ctx["paths"]["reports"], RUN_LOG_NAME), {
            "ts": _now_iso(),
            "stage": stage,
            "event": "error_corrector",
            "verdict": payload["verdict"],
            "run_id": ctx.get("run_id"),
        })

        return {
            "status": "ok",
            "stage": stage,
            "run_id": ctx.get("run_id"),
            "verdict": payload["verdict"],
            "block_items": payload["block_items"],
            "gate_path": gate_path,
            "gate_verdict": ctx.get("gate_verdict", payload["verdict"]),
            "evidence_paths": [gate_path],
            "message": f"{stage} gate: {payload['verdict']}",
        }
    except Exception as e:
        return {
            "status": "error",
            "error_type": type(e).__name__,
            "message": str(e),
            "suggested_action": "run_error_corrector failed.",
        }


def error_corrector_report(state: dict, stage: str, run_id: Optional[str] = None) -> dict:
    """Compatibility wrapper for stage gate reports requested by the P0-P3 plan."""
    return run_error_corrector(state=state, stage=stage, run_id=run_id)


def _save_figure(fig: plt.Figure, out_path: str, dpi: int):
    _ensure_dir(os.path.dirname(out_path))
    fig.savefig(out_path, dpi=int(dpi), bbox_inches="tight")
    plt.close(fig)


def generate_explanations(state: dict,
                          output_dpi: int = DEFAULT_OUTPUT_DPI,
                          run_id: Optional[str] = None) -> dict:
    """Generate SHAP-like and spatial explanation artifacts."""
    try:
        from sklearn.cluster import MiniBatchKMeans
        ft_info = state.get("feature_table")
        best_algo = state.get("best_model")
        models = state.get("models", {})
        if not ft_info or not best_algo or best_algo not in models:
            return {
                "status": "error",
                "error_type": "MissingPrerequisites",
                "message": "Need feature_table and best model before explanations.",
                "suggested_action": "Run build_feature_table -> train_candidates -> select_best first.",
            }
        ctx = _get_complete_run_context(
            state,
            source_mode="rusle_raw",
            required_dirs=("explanations", "spatial", "reports"),
            run_id=run_id,
            output_dpi=output_dpi,
        )

        df = pd.read_parquet(ft_info["path"])
        feature_cols = _feature_columns_from_df(df, target_col="label")
        if not feature_cols:
            return {"status": "error", "error_type": "NoNumericFeatures", "message": "No numeric feature columns are available for explanations."}
        df_clean = df[feature_cols + ["label", "row", "col", "year"]].dropna()
        if len(df_clean) == 0:
            return {"status": "error", "error_type": "EmptyData", "message": "No valid rows for explanations."}

        model = models[best_algo]["model"]
        X = df_clean[feature_cols]
        max_samples = min(120, len(X))
        background_n = min(50, len(X))
        X_bg = X.sample(n=background_n, random_state=42) if len(X) > background_n else X
        Xs = X.sample(n=max_samples, random_state=42) if len(X) > max_samples else X

        explain_paths = []
        spatial_paths = []
        geoshapley_status = "degraded"
        geoshapley_reason = "GeoShapley optional dependency not available"

        def _model_importance_vector() -> np.ndarray:
            if hasattr(model, "feature_importances_"):
                raw = np.asarray(model.feature_importances_, dtype=float)
                if len(raw) == len(feature_cols) and np.isfinite(raw).all() and np.sum(np.abs(raw)) > 0:
                    return np.abs(raw) / (np.sum(np.abs(raw)) + 1e-12)
            return np.ones(len(feature_cols), dtype=float) / max(len(feature_cols), 1)

        canonical_factors = [f for f in ["R", "K", "LS", "C", "P"] if f in feature_cols]
        explain_focus = canonical_factors or feature_cols[: min(5, len(feature_cols))]

        def _write_proxy_explanations(reason: str):
            # Stable fallback for large raw-source runs where SHAP can exceed practical runtime.
            imp_vec = _model_importance_vector()
            xs_num = Xs.astype(float)
            centered = xs_num - xs_num.mean(axis=0)
            scaled = centered / (xs_num.std(axis=0).replace(0, 1.0))
            proxy_values = scaled.values * imp_vec.reshape(1, -1)
            abs_mean = np.mean(np.abs(proxy_values), axis=0)
            order = np.argsort(abs_mean)[::-1]
            top = order[: min(10, len(feature_cols))]

            fig, ax = plt.subplots(figsize=(10, 6))
            for pos, idx in enumerate(top):
                y = np.full(proxy_values.shape[0], pos) + np.linspace(-0.25, 0.25, proxy_values.shape[0])
                ax.scatter(proxy_values[:, idx], y, s=12, alpha=0.55)
            ax.set_yticks(range(len(top)))
            ax.set_yticklabels([feature_cols[i] for i in top])
            ax.set_title(f"Proxy Contribution Summary ({reason})")
            ax.set_xlabel("standardized contribution proxy")
            p1 = os.path.join(ctx["paths"]["explanations"], "proxy_contribution_summary.png")
            _save_figure(fig, p1, output_dpi)
            explain_paths.append(p1)

            fig, ax = plt.subplots(figsize=(10, 6))
            ax.barh([feature_cols[i] for i in top][::-1], abs_mean[top][::-1])
            ax.set_title(f"Proxy Contribution Bar ({reason})")
            ax.set_xlabel("mean absolute contribution proxy")
            p2 = os.path.join(ctx["paths"]["explanations"], "proxy_contribution_bar.png")
            _save_figure(fig, p2, output_dpi)
            explain_paths.append(p2)

            for feat in explain_focus:
                dep_idx = feature_cols.index(feat)
                fig, ax = plt.subplots(figsize=(8, 6))
                ax.scatter(xs_num.iloc[:, dep_idx], proxy_values[:, dep_idx], s=16, alpha=0.6)
                ax.set_title(f"Proxy Dependence: {feature_cols[dep_idx]}")
                ax.set_xlabel(feature_cols[dep_idx])
                ax.set_ylabel("contribution proxy")
                p_dep = os.path.join(ctx["paths"]["explanations"], f"proxy_dependence_{feature_cols[dep_idx]}.png")
                _save_figure(fig, p_dep, output_dpi)
                explain_paths.append(p_dep)

            heat = np.corrcoef(np.abs(proxy_values).T) if proxy_values.shape[1] > 1 else np.ones((1, 1))
            fig, ax = plt.subplots(figsize=(8, 7))
            im = ax.imshow(heat, cmap="RdBu_r", vmin=-1, vmax=1)
            ax.set_xticks(range(len(feature_cols)))
            ax.set_xticklabels(feature_cols, rotation=90, fontsize=7)
            ax.set_yticks(range(len(feature_cols)))
            ax.set_yticklabels(feature_cols, fontsize=7)
            ax.set_title(f"Proxy Interaction Heatmap ({reason})")
            fig.colorbar(im, ax=ax, shrink=0.8)
            p_heat = os.path.join(ctx["paths"]["explanations"], "proxy_interaction_heatmap.png")
            _save_figure(fig, p_heat, output_dpi)
            explain_paths.append(p_heat)

        shap_ready = False
        explanation_mode = "shap"
        shap_risk_note = ""
        source_mode = str(ctx.get("source_mode", "uploads")).lower()
        run_mode = str(ctx.get("run_mode", "quick")).lower()
        raw_quick_safe_fallback = source_mode == "rusle_raw" and run_mode == "quick"

        if raw_quick_safe_fallback:
            _write_proxy_explanations("raw quick safe fallback")
            explanation_mode = "proxy"
            shap_risk_note = (
                "Quick raw-source run used proxy contribution figures to avoid known SHAP "
                "hard-crash/runtime risk; these are not real SHAP values."
            )
            geoshapley_reason = "SHAP skipped for quick raw-source run; proxy contribution figures generated"
        elif len(X) > 5000:
            _write_proxy_explanations("large-run fallback")
            explanation_mode = "proxy"
            shap_risk_note = "Large run used proxy contribution figures; these are not real SHAP values."
            geoshapley_reason = "SHAP skipped for large run; proxy contribution figures generated"
        else:
            try:
                import shap
                explainer = shap.Explainer(model, X_bg)
                shap_values = explainer(Xs)
                shap_ready = True

                plt.figure(figsize=(10, 6))
                shap.summary_plot(shap_values, Xs, show=False, max_display=min(10, len(feature_cols)))
                p1 = os.path.join(ctx["paths"]["explanations"], "shap_summary.png")
                _save_figure(plt.gcf(), p1, output_dpi)
                explain_paths.append(p1)

                plt.figure(figsize=(10, 6))
                shap.summary_plot(shap_values, Xs, plot_type="bar", show=False, max_display=min(10, len(feature_cols)))
                p2 = os.path.join(ctx["paths"]["explanations"], "shap_beeswarm_bar.png")
                _save_figure(plt.gcf(), p2, output_dpi)
                explain_paths.append(p2)

                top_features = explain_focus
                for feat in top_features:
                    plt.figure(figsize=(8, 6))
                    shap.dependence_plot(feat, shap_values.values, Xs, show=False)
                    fp = os.path.join(ctx["paths"]["explanations"], f"shap_dependence_{feat}.png")
                    _save_figure(plt.gcf(), fp, output_dpi)
                    explain_paths.append(fp)

                values = np.asarray(shap_values.values)
                if values.ndim == 2 and values.shape[1] > 1:
                    heat = np.corrcoef(np.abs(values).T)
                    fig, ax = plt.subplots(figsize=(8, 7))
                    im = ax.imshow(heat, cmap="RdBu_r", vmin=-1, vmax=1)
                    ax.set_xticks(range(len(feature_cols)))
                    ax.set_xticklabels(feature_cols, rotation=90, fontsize=7)
                    ax.set_yticks(range(len(feature_cols)))
                    ax.set_yticklabels(feature_cols, fontsize=7)
                    ax.set_title("SHAP Interaction Heatmap")
                    fig.colorbar(im, ax=ax, shrink=0.8)
                    p3 = os.path.join(ctx["paths"]["explanations"], "shap_interaction_heatmap.png")
                    _save_figure(fig, p3, output_dpi)
                    explain_paths.append(p3)
            except Exception as e:
                _write_proxy_explanations("SHAP unavailable")
                explanation_mode = "proxy"
                shap_risk_note = "SHAP failed or is unavailable; proxy contribution figures are not real SHAP values."
                geoshapley_reason = f"SHAP unavailable; proxy contribution figures generated: {e}"

        # Spatial outputs (dominant factor + cluster + radar + per-factor heatmaps)
        latest_year = int(df_clean["year"].max())
        dfx = df_clean[df_clean["year"] == latest_year].copy()
        imp = None
        if hasattr(model, "feature_importances_"):
            imp = np.asarray(model.feature_importances_, dtype=float)
        if imp is None or len(imp) != len(feature_cols):
            imp = np.ones(len(feature_cols), dtype=float)
        imp = np.abs(imp) / (np.sum(np.abs(imp)) + 1e-12)
        contrib = np.abs(dfx[feature_cols].values * imp.reshape(1, -1))
        dominant_idx = np.argmax(contrib, axis=1)

        max_row = int(dfx["row"].max()) + 1
        max_col = int(dfx["col"].max()) + 1
        dominant_map = np.full((max_row, max_col), np.nan)
        coords = dfx[["row", "col"]].to_numpy(dtype=int)
        dominant_map[coords[:, 0], coords[:, 1]] = dominant_idx

        fig, ax = plt.subplots(figsize=(10, 6))
        im = ax.imshow(dominant_map, cmap="tab20")
        ax.set_title(f"Dominant Factor Map ({latest_year})")
        fig.colorbar(im, ax=ax, shrink=0.8)
        p_dom = os.path.join(ctx["paths"]["spatial"], "dominant_factor_map.png")
        _save_figure(fig, p_dom, output_dpi)
        spatial_paths.append(p_dom)

        factor_spatial_paths = {}
        for feat in explain_focus:
            feat_idx = feature_cols.index(feat)
            feat_map = np.full((max_row, max_col), np.nan, dtype=float)
            feat_map[coords[:, 0], coords[:, 1]] = contrib[:, feat_idx]
            fig, ax = plt.subplots(figsize=(10, 6))
            im = ax.imshow(feat_map, cmap="YlOrRd")
            ax.set_title(f"{feat} Spatial Heatmap ({latest_year})")
            fig.colorbar(im, ax=ax, shrink=0.8)
            fp = os.path.join(ctx["paths"]["spatial"], f"spatial_heatmap_{feat}.png")
            _save_figure(fig, fp, output_dpi)
            spatial_paths.append(fp)
            factor_spatial_paths[feat] = fp

        k = min(4, max(2, len(dfx) // 500 + 1))
        km = MiniBatchKMeans(n_clusters=k, random_state=42, batch_size=2048, n_init=5)
        labels = km.fit_predict(contrib)
        cluster_map = np.full((max_row, max_col), np.nan)
        cluster_map[coords[:, 0], coords[:, 1]] = labels

        fig, ax = plt.subplots(figsize=(10, 6))
        im = ax.imshow(cluster_map, cmap="Set3")
        ax.set_title(f"Spatial Cluster Map ({latest_year})")
        fig.colorbar(im, ax=ax, shrink=0.8)
        p_cluster = os.path.join(ctx["paths"]["spatial"], "spatial_cluster_map.png")
        _save_figure(fig, p_cluster, output_dpi)
        spatial_paths.append(p_cluster)

        # Radar by cluster centers
        centers = km.cluster_centers_
        show_cols = feature_cols[: min(6, len(feature_cols))]
        center_show = centers[:, :len(show_cols)] if centers.shape[1] >= len(show_cols) else centers
        angles = np.linspace(0, 2 * np.pi, len(show_cols), endpoint=False)
        angles = np.concatenate([angles, angles[:1]])
        fig = plt.figure(figsize=(8, 8))
        ax = fig.add_subplot(111, polar=True)
        for i in range(center_show.shape[0]):
            vals = center_show[i]
            vals = np.concatenate([vals, vals[:1]])
            ax.plot(angles, vals, label=f"C{i}")
            ax.fill(angles, vals, alpha=0.1)
        ax.set_xticks(angles[:-1])
        ax.set_xticklabels(show_cols, fontsize=8)
        ax.set_title("Cluster Radar")
        ax.legend(loc="upper right", bbox_to_anchor=(1.2, 1.1))
        p_radar = os.path.join(ctx["paths"]["spatial"], "cluster_radar.png")
        _save_figure(fig, p_radar, output_dpi)
        spatial_paths.append(p_radar)

        geoshapley_status = "degraded"
        geoshapley_reason = geoshapley_reason or "GeoShapley not installed"

        meta_path = os.path.join(ctx["paths"]["explanations"], "explanations_meta.json")
        meta_payload = {
            "run_id": ctx.get("run_id"),
            "output_dpi": int(output_dpi),
            "shap_ready": shap_ready,
            "explanation_mode": explanation_mode,
            "shap_risk_note": shap_risk_note,
            "canonical_factors": explain_focus,
            "geoshapley_status": geoshapley_status,
            "geoshapley_reason": geoshapley_reason,
            "explanation_files": explain_paths,
            "spatial_files": spatial_paths,
            "factor_spatial_paths": factor_spatial_paths,
        }
        _write_json(meta_path, meta_payload)
        _record_evidence_path(state, meta_path)
        for p in explain_paths + spatial_paths:
            _record_evidence_path(state, p)
        state["_explanation_meta"] = meta_payload

        return {
            "status": "ok",
            "run_id": ctx.get("run_id"),
            "output_dpi": int(output_dpi),
            "shap_ready": shap_ready,
            "explanation_mode": explanation_mode,
            "shap_risk_note": shap_risk_note,
            "geoshapley_status": geoshapley_status,
            "geoshapley_reason": geoshapley_reason,
            "explanation_files": explain_paths,
            "spatial_files": spatial_paths,
            "evidence_paths": [meta_path] + explain_paths + spatial_paths,
            "gate_verdict": PASS_WITH_RISKS if geoshapley_status == "degraded" else PASS,
            "message": f"Generated explanations: {len(explain_paths)} explain + {len(spatial_paths)} spatial outputs.",
        }
    except Exception as e:
        return {
            "status": "error",
            "error_type": type(e).__name__,
            "message": str(e),
            "suggested_action": "generate_explanations failed.",
        }


def export_evidence_bundle(state: dict, run_id: Optional[str] = None) -> dict:
    """Auto-generated doc."""
    try:
        ctx = state.get("run_context")
        if not ctx:
            return {"status": "error", "error_type": "NoRunContext", "message": "No run_context found."}
        if run_id and ctx.get("run_id") != run_id:
            return {"status": "error", "error_type": "RunMismatch", "message": "run_id does not match current context."}

        index_path = os.path.join(ctx["paths"]["bundle"], "bundle_index.json")
        method_note_path = os.path.join(ctx["paths"]["bundle"], "method_note.md")
        repro_path = os.path.join(ctx["paths"]["bundle"], "reproduce.md")
        gate_summary_path = os.path.join(ctx["paths"]["bundle"], "gate_summary.json")
        security_audit_path = os.path.join(ctx["paths"]["reports"], SECURITY_AUDIT_LOG)
        bundle_paths = [index_path, method_note_path, repro_path, gate_summary_path]
        raw_evidence_paths = list(ctx.get("evidence_paths", [])) + bundle_paths
        security_meta = _data_security_metadata()

        _append_jsonl(security_audit_path, {
            "ts": _now_iso(),
            "event": "export_evidence_bundle",
            "run_id": ctx.get("run_id"),
            "classification": security_meta["classification"],
            "external_llm_allowed": security_meta["external_llm_allowed"],
            "retention_days": security_meta["retention_days"],
        })

        _write_json(index_path, {
            "run_id": ctx.get("run_id"),
            "generated_at": _now_iso(),
            "classification": security_meta["classification"],
            "retention_days": security_meta["retention_days"],
            "external_llm_allowed": security_meta["external_llm_allowed"],
            "assistant_context_policy": security_meta["assistant_context_policy"],
            "evidence_paths": _bundle_path_refs(ctx, raw_evidence_paths),
            "gate_reports": _redact_bundle_payload(ctx, ctx.get("gate_reports", {})),
        })
        _write_text(method_note_path, (
            "# Method Note\n\n"
            "- Workflow: P0 -> P1 -> P2 -> P3\n"
            "- Metrics: MAE/RMSE/R2/NRMSE/PBIAS/train_seconds\n"
            "- NRMSE = RMSE / mean(y_true) * 100%\n"
            "- PBIAS = 100 * sum(y_pred - y_true) / sum(y_true)\n"
            "- Preprocessing audit: raw RUSLE runs must retain R/K/LS/C/P factors before modeling.\n"
            "- Quick mode: intended for runnable evidence and gate verification.\n"
            "- Quick raw-source prediction: may replay the latest historical feature grid (`historical_feature_replay`) to verify the P3 delivery chain; this is not a future scenario forecast.\n"
            "- Full mode: requires metadata preflight; preflight does not prove full runtime success.\n"
            "- GeoShapley: optional, downgrade to SHAP + spatial aggregation when unavailable.\n"
            "- SHAP large-run policy: when real SHAP is skipped or unavailable, exported proxy contribution figures are evidence of fallback behavior only, not publication-grade SHAP values.\n"
            "- Forbidden conclusion: do not claim robust or publication-ready interpretation from PASS_WITH_RISKS outputs alone.\n"
        ))
        _write_text(repro_path, (
            "# Reproduction\n\n"
            "1. prepare_run_context(run_mode='quick' or 'full', source_mode='rusle_raw').\n"
            "2. run_one_click_pipeline(...).\n"
            "3. inspect data/runs/<run_id>/ for full evidence.\n"
        ))

        _write_json(gate_summary_path, {
            "run_id": ctx.get("run_id"),
            "gate_verdict": ctx.get("gate_verdict", PASS),
            "gate_reports": ctx.get("gate_reports", {}),
        })

        zip_path = os.path.join(ctx["paths"]["bundle"], f"{ctx['run_id']}_bundle.zip")
        with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            run_root = ctx["paths"]["root"]
            for root, _, files in os.walk(run_root):
                for f in files:
                    if f.lower().endswith(".zip"):
                        continue
                    fp = os.path.join(root, f)
                    rel = os.path.relpath(fp, run_root)
                    if f.lower().endswith(EVIDENCE_BUNDLE_TEXT_EXTENSIONS):
                        with open(fp, "r", encoding="utf-8", errors="ignore") as src:
                            zf.writestr(rel, _redact_bundle_text(ctx, src.read()))
                    else:
                        zf.write(fp, arcname=rel)

        _record_evidence_path(state, index_path)
        _record_evidence_path(state, method_note_path)
        _record_evidence_path(state, repro_path)
        _record_evidence_path(state, gate_summary_path)
        _record_evidence_path(state, security_audit_path)
        _record_evidence_path(state, zip_path)
        ctx["bundle_zip"] = zip_path
        ctx["bundle_index"] = index_path
        ctx["method_note"] = method_note_path
        ctx["reproduce_note"] = repro_path
        ctx["gate_summary"] = gate_summary_path
        state["run_context"] = ctx

        return {
            "status": "ok",
            "run_id": ctx.get("run_id"),
            "bundle_zip": zip_path,
            "bundle_index": index_path,
            "method_note": method_note_path,
            "reproduce_note": repro_path,
            "gate_summary": gate_summary_path,
            "evidence_paths": [zip_path, index_path, method_note_path, repro_path, gate_summary_path, security_audit_path],
            "gate_verdict": ctx.get("gate_verdict", PASS),
            "message": f"Evidence bundle exported: {zip_path}",
        }
    except Exception as e:
        return {
            "status": "error",
            "error_type": type(e).__name__,
            "message": str(e),
            "suggested_action": "export_evidence_bundle failed.",
        }


# ============================================================
# 三阶段训练流水线: 默认参数训练 → 贝叶斯优化 → 优化后重训练
# ============================================================
def _build_estimator_from_registry(algo: str, params: dict = None):
    """按 MODEL_REGISTRY 配置构建 estimator，支持自定义参数覆盖。"""
    merged = dict(MODEL_REGISTRY.get(algo, {}).get("default_params", {}))
    if params:
        merged.update(params)

    if algo == "lightgbm":
        max_depth = merged.get("max_depth", -1)
        if not isinstance(max_depth, int) or max_depth < 0:
            max_depth = -1
        return lgb.LGBMRegressor(
            n_estimators=int(merged.get("n_estimators", 100)),
            learning_rate=float(merged.get("learning_rate", 0.1)),
            num_leaves=int(merged.get("num_leaves", 31)),
            max_depth=max_depth,
            min_child_samples=int(merged.get("min_child_samples", 20)),
            subsample=float(merged.get("bagging_fraction", merged.get("subsample", 0.8))),
            subsample_freq=int(merged.get("bagging_freq", 0)),
            colsample_bytree=float(merged.get("feature_fraction", merged.get("colsample_bytree", 0.8))),
            reg_alpha=float(merged.get("reg_alpha", 0)),
            reg_lambda=float(merged.get("reg_lambda", 0)),
            random_state=42, n_jobs=1, verbose=-1,
        )
    if algo == "xgboost":
        return xgb.XGBRegressor(
            n_estimators=int(merged.get("n_estimators", 100)),
            learning_rate=float(merged.get("learning_rate", 0.1)),
            max_depth=int(merged.get("max_depth", 6)),
            subsample=float(merged.get("subsample", 0.8)),
            colsample_bytree=float(merged.get("colsample_bytree", 0.8)),
            reg_alpha=float(merged.get("reg_alpha", 0)),
            reg_lambda=float(merged.get("reg_lambda", 1)),
            gamma=float(merged.get("gamma", 0)),
            random_state=42, n_jobs=1, verbosity=0,
        )
    if algo == "random_forest":
        return RandomForestRegressor(
            n_estimators=int(merged.get("n_estimators", 100)),
            max_depth=int(merged.get("max_depth", 6)),
            min_samples_split=int(merged.get("min_samples_split", 2)),
            min_samples_leaf=int(merged.get("min_samples_leaf", 1)),
            max_features=merged.get("max_features", "sqrt"),
            bootstrap=_coerce_bool_param(merged.get("bootstrap", True)),
            random_state=42, n_jobs=1,
        )
    if algo == "extratrees":
        return ExtraTreesRegressor(
            n_estimators=int(merged.get("n_estimators", 100)),
            max_depth=int(merged.get("max_depth", 6)),
            min_samples_split=int(merged.get("min_samples_split", 2)),
            min_samples_leaf=int(merged.get("min_samples_leaf", 1)),
            max_features=merged.get("max_features", "sqrt"),
            bootstrap=_coerce_bool_param(merged.get("bootstrap", False)),
            random_state=42, n_jobs=1,
        )
    if algo == "adaboost":
        return AdaBoostRegressor(
            n_estimators=int(merged.get("n_estimators", 250)),
            learning_rate=float(merged.get("learning_rate", 0.05)),
            random_state=42,
        )
    if algo == "svr":
        return SVR(
            C=float(merged.get("C", 1.0)),
            kernel=str(merged.get("kernel", "rbf")),
            gamma=merged.get("gamma", "scale"),
            epsilon=float(merged.get("epsilon", 0.1)),
            shrinking=_coerce_bool_param(merged.get("shrinking", True)),
            degree=int(merged.get("degree", 3)),
        )
    if algo == "knn":
        return KNeighborsRegressor(
            n_neighbors=int(merged.get("n_neighbors", 8)),
            weights=str(merged.get("weights", "distance")),
            algorithm=str(merged.get("algorithm", "auto")),
        )
    if algo == "catboost":
        try:
            from catboost import CatBoostRegressor
        except Exception as e_cb:
            raise ImportError(f"catboost unavailable: {e_cb}")
        return CatBoostRegressor(
            depth=int(merged.get("depth", 8)),
            learning_rate=float(merged.get("learning_rate", 0.05)),
            n_estimators=int(merged.get("n_estimators", 400)),
            l2_leaf_reg=float(merged.get("l2_leaf_reg", 3)),
            bagging_temperature=float(merged.get("bagging_temperature", 1)),
            border_count=int(merged.get("border_count", 254)),
            random_strength=float(merged.get("random_strength", 1)),
            loss_function="RMSE", verbose=False, random_seed=42,
        )
    raise ValueError(f"unsupported algorithm: {algo}")


def _single_model_evaluate(estimator, X_train, y_train, X_val, y_val) -> dict:
    """评估单个模型返回指标快照，同时返回训练时间。"""
    t0 = time.time()
    est = clone(estimator)
    est.fit(X_train, y_train)
    t1 = time.time()
    pred = est.predict(X_val)
    packet = _metric_packet(y_val, pred, train_seconds=round(t1 - t0, 2))
    return {
        "r2": float(packet["r2"]),
        "rmse": float(packet["rmse"]),
        "mae": float(packet["mae"]),
        "nrmse": float(packet["nrmse"]),
        "pbias": float(packet["pbias"]),
        "train_seconds": round(t1 - t0, 2),
    }


def _build_optuna_search_space(trial, algo: str) -> dict:
    """根据 MODEL_REGISTRY 为 Optuna 构建搜索空间。"""
    cfg = MODEL_REGISTRY.get(algo)
    if not cfg:
        return {}
    bounds = cfg.get("bayes_opt_bounds", {})
    ptypes = cfg.get("param_types", {})
    trial_params = {}
    for pname, bound in bounds.items():
        pt = ptypes.get(pname, "float")
        if pt == "int":
            trial_params[pname] = trial.suggest_int(pname, int(bound[0]), int(bound[1]))
        elif pt == "categorical":
            if isinstance(bound, (list, tuple)):
                trial_params[pname] = trial.suggest_categorical(pname, list(bound))
            else:
                trial_params[pname] = trial.suggest_categorical(pname, [bound])
        else:
            if bound[0] > 0:
                trial_params[pname] = trial.suggest_float(pname, float(bound[0]), float(bound[1]), log=True)
            else:
                trial_params[pname] = trial.suggest_float(pname, float(bound[0]), float(bound[1]))
    return trial_params


def run_stage_two_optimization(state: dict,
                               algorithms: list = None,
                               cv_folds: int = 4,
                               n_trials: int = 30,
                               timeout_sec: int = None,
                               base_param_overrides: Optional[dict] = None,
                               progress_callback=None) -> dict:
    """
    阶段二：对指定算法执行超参数贝叶斯优化（基于 Optuna TPE）。
    返回每算法的最优参数和优化历史快照。
    """
    try:
        import optuna
        from optuna.samplers import TPESampler
    except ImportError:
        return {"status": "error", "message": "optuna must be installed for hyperparameter optimization."}

    feature_table = state.get("feature_table") or {}
    if not feature_table:
        return {"status": "error", "message": "No feature table found. Run build_feature_table first."}

    df_path = feature_table.get("path")
    if not df_path or not os.path.exists(df_path):
        return {"status": "error", "message": f"Feature table not found: {df_path}"}

    df = pd.read_parquet(df_path)
    if "label" not in df.columns:
        return {"status": "error", "message": "Label column is missing in feature table."}

    feature_cols = _feature_columns_from_df(df, target_col="label")
    if not feature_cols:
        return {"status": "error", "message": "No numeric feature columns are available for optimization."}

    df_clean = df[feature_cols + ["label"]].dropna()
    if len(df_clean) < 50:
        return {"status": "error", "message": f"Insufficient samples: {len(df_clean)} (need >= 50)."}

    y = df_clean["label"].values
    X = df_clean[feature_cols].values

    target_algorithms = [a.lower() for a in (algorithms or DEFAULT_MODEL_POOL)]
    target_algorithms = [a for a in target_algorithms if a in MODEL_REGISTRY]
    if not target_algorithms:
        return {"status": "error", "message": "No supported algorithms for optimization."}

    base_overrides, invalid_base_overrides = _normalize_param_overrides_with_errors(base_param_overrides, target_algorithms)
    opt_results = {}
    skipped = []
    for algo in target_algorithms:
        t0 = time.time()
        if invalid_base_overrides.get(algo):
            skipped.append({
                "algorithm": algo,
                "reason": "invalid manual parameters: " + "; ".join(invalid_base_overrides[algo]),
            })
            continue
        base_params = dict(MODEL_REGISTRY[algo].get("default_params", {}))
        base_params.update(base_overrides.get(algo, {}))
        try:
            _build_estimator_from_registry(algo, base_params)
        except Exception as exc:
            skipped.append({"algorithm": algo, "reason": str(exc)})
            continue
        opt_history = []

        def _objective(trial):
            trial_params = _build_optuna_search_space(trial, algo)
            actual_params = dict(base_params)
            actual_params.update(trial_params)
            try:
                estimator = _build_estimator_from_registry(algo, actual_params)
                folds = _spatial_cv_split(X, y, cv_folds)
                scores = []
                for train_idx, test_idx in folds:
                    cl = clone(estimator)
                    cl.fit(X[train_idx], y[train_idx])
                    pred = cl.predict(X[test_idx])
                    scores.append(r2_score(y[test_idx], pred))
                mean_r2 = float(np.mean(scores))
                opt_history.append({
                    "params": dict(actual_params),
                    "trial_params": dict(trial_params),
                    "r2": mean_r2,
                    "trial": len(opt_history),
                })
                if progress_callback:
                    progress_callback({"algo": algo, "trial": len(opt_history), "total": n_trials, "best_r2": max(h["r2"] for h in opt_history)})
                return mean_r2
            except Exception:
                return -1e10

        sampler = TPESampler(seed=42)
        study = optuna.create_study(direction="maximize", sampler=sampler)
        study.optimize(_objective, n_trials=n_trials, timeout=timeout_sec, show_progress_bar=False)

        best_r2 = float(study.best_value)
        if not np.isfinite(best_r2) or best_r2 <= -1e9:
            skipped.append({"algorithm": algo, "reason": "all optimization trials failed"})
            continue

        best_params = dict(base_params)
        best_params.update(study.best_params)
        opt_results[algo] = {
            "best_params": best_params,
            "trial_best_params": dict(study.best_params),
            "base_params": base_params,
            "best_r2": best_r2,
            "n_trials": len(study.trials),
            "optimization_seconds": round(time.time() - t0, 1),
            "history": [
                {"trial": i, "params": h["params"], "trial_params": h["trial_params"], "r2": h["r2"]}
                for i, h in enumerate(opt_history)
            ],
        }

    if not opt_results:
        result = {
            "status": "error",
            "optimization_results": {},
            "skipped_algorithms": skipped,
            "message": "No algorithms were successfully optimized.",
        }
        state["_optimization_result"] = result
        return result

    result = {
        "status": "ok",
        "optimization_results": opt_results,
        "skipped_algorithms": skipped,
        "feature_names": feature_cols,
        "message": f"Optimized {len(opt_results)} algorithm(s).",
    }
    state["_optimization_result"] = result
    return result


def run_three_stage_training(state: dict,
                             algorithms: list = None,
                             cv_folds: int = 4,
                             n_opt_trials: int = 30,
                             progress_callback=None) -> dict:
    """
    完整三阶段模型训练流水线：
      阶段一：默认超参数初始训练（全模型池）
      阶段二：贝叶斯优化（各模型独立搜索空间）
      阶段三：基于优化参数重新训练并对比

    Returns:
        {
            "status": "ok" | "error",
            "stage_one": { ... 初始训练结果 },
            "stage_two": { ... 优化结果 },
            "stage_three": { ... 最终训练对比 },
            "best_model": str,
            "comparison": { algo: { "default": {...}, "optimized": {...}, "delta": {...} } }
        }
    """
    import optuna
    from sklearn.model_selection import train_test_split

    feature_table = state.get("feature_table") or {}
    if not feature_table:
        return {"status": "error", "message": "No feature table. Run build_feature_table first."}

    df_path = feature_table.get("path")
    if not df_path or not os.path.exists(df_path):
        return {"status": "error", "message": f"Feature table not found: {df_path}"}

    df = pd.read_parquet(df_path)
    meta_cols = {"row", "col", "year", "scenario"}
    feature_cols = [c for c in df.columns if c not in meta_cols and c != "label" and np.issubdtype(df[c].dtype, np.number)]
    y = df["label"].values
    X = df[feature_cols].values
    n_samples = len(y)
    if n_samples < 50:
        return {"status": "error", "message": f"Insufficient samples: {n_samples} (need >= 50)."}

    target_algos = [a.lower() for a in (algorithms or [algo for algo in DEFAULT_MODEL_POOL if algo in MODEL_REGISTRY])]
    target_algos = [a for a in target_algos if a in MODEL_REGISTRY]
    if not target_algos:
        return {"status": "error", "message": "No recognized algorithms."}

    X_train, X_val, y_train, y_val = train_test_split(X, y, test_size=0.20, random_state=42)

    # ---- 阶段一：默认参数训练 ----
    stage_one = {}
    models_state = {}
    best_algo_default = None
    best_rmse_default = float("inf")
    for algo in target_algos:
        try:
            estimator = _build_estimator_from_registry(algo)
            metrics = _single_model_evaluate(estimator, X_train, y_train, X_val, y_val)
            display = MODEL_REGISTRY[algo].get("display_name", algo)
            stage_one[display] = metrics
            models_state[algo] = {"metrics": metrics, "params": MODEL_REGISTRY[algo]["default_params"]}
            if metrics["rmse"] < best_rmse_default:
                best_rmse_default = metrics["rmse"]
                best_algo_default = algo
            if progress_callback:
                progress_callback({"stage": 1, "algo": algo, "done": len(stage_one), "total": len(target_algos)})
        except Exception as e:
            stage_one[MODEL_REGISTRY[algo].get("display_name", algo)] = {"error": str(e)}

    # ---- 阶段二：贝叶斯优化 ----
    stage_two = {}
    for algo in [a for a in target_algos if a in ["lightgbm", "xgboost", "random_forest", "svr", "extratrees", "catboost", "adaboost", "knn"]]:
        try:
            cfg = MODEL_REGISTRY[algo]
            opt_history = []

            def _objective(trial):
                trial_params = _build_optuna_search_space(trial, algo)
                try:
                    estimator = _build_estimator_from_registry(algo, trial_params)
                    folds = _spatial_cv_split(X, y, cv_folds)
                    scores = []
                    for tr_idx, te_idx in folds:
                        cl = clone(estimator)
                        cl.fit(X[tr_idx], y[tr_idx])
                        pred = cl.predict(X[te_idx])
                        scores.append(r2_score(y[te_idx], pred))
                    mean_r2 = float(np.mean(scores))
                    opt_history.append({"params": dict(trial_params), "r2": mean_r2})
                    if progress_callback:
                        progress_callback({"stage": 2, "algo": algo, "trial": len(opt_history), "total": n_opt_trials})
                    return mean_r2
                except Exception:
                    return -1e10

            sampler = optuna.samplers.TPESampler(seed=42)
            study = optuna.create_study(direction="maximize", sampler=sampler)
            study.optimize(_objective, n_trials=n_opt_trials, show_progress_bar=False)
            stage_two[algo] = {"best_params": study.best_params, "best_r2": study.best_value, "n_trials": len(study.trials)}
        except Exception as e:
            stage_two[algo] = {"error": str(e)}

    # ---- 阶段三：优化后重训练 ----
    comparison = {}
    best_algo_final = None
    best_r2_final = -float("inf")
    stage_three = {}
    for algo in target_algos:
        display = MODEL_REGISTRY[algo].get("display_name", algo)
        default_metrics = stage_one.get(display, {})
        try:
            opt_result = stage_two.get(algo, {})
            best_params = opt_result.get("best_params", {})
            if best_params:
                estimator = _build_estimator_from_registry(algo, best_params)
                metrics = _single_model_evaluate(estimator, X_train, y_train, X_val, y_val)
                models_state[algo] = {"metrics": metrics, "params": best_params, "optimized": True}
                comparison[display] = {
                    "default": default_metrics,
                    "optimized": metrics,
                    "improvement": {
                        "r2_delta": round(metrics["r2"] - default_metrics.get("r2", 0), 4),
                        "rmse_reduction_pct": (
                            round((default_metrics.get("rmse", 0) - metrics["rmse"]) / max(default_metrics.get("rmse", 1e-9), 1e-9) * 100, 1)
                        ),
                    },
                }
                stage_three[display] = metrics
                if metrics["r2"] > best_r2_final:
                    best_r2_final = metrics["r2"]
                    best_algo_final = algo
            else:
                comparison[display] = {"default": default_metrics, "optimized": "skipped", "improvement": {"r2_delta": 0, "rmse_reduction_pct": 0}}
                stage_three[display] = default_metrics
                if default_metrics.get("r2", -1) > best_r2_final:
                    best_r2_final = default_metrics.get("r2", -1)
                    best_algo_final = algo
        except Exception as e:
            comparison[display] = {"error": str(e)}
            stage_three[display] = {"error": str(e)}

    state["models"] = models_state
    state["best_model"] = best_algo_final

    # 写优化报告到 run 目录
    run_ctx = state.get("run_context", {})
    evidence_dirs = run_ctx.get("paths", {}) if run_ctx else {}
    reports_dir = evidence_dirs.get("reports", os.path.join(DATA_ROOT, "runs", "latest", "reports"))
    os.makedirs(reports_dir, exist_ok=True)
    opt_report_path = os.path.join(reports_dir, "optimization_report.json")
    opt_payload = {
        "timestamp": _now_iso(),
        "best_model": best_algo_final,
        "best_model_display": MODEL_REGISTRY.get(best_algo_final, {}).get("display_name", best_algo_final),
        "stage_one_summary": stage_one,
        "stage_two_summary": {a: {"best_params": r.get("best_params"), "best_r2": r.get("best_r2")} for a, r in stage_two.items() if "error" not in r},
        "comparison": comparison,
    }
    with open(opt_report_path, "w", encoding="utf-8") as f:
        json.dump(opt_payload, f, ensure_ascii=False, indent=2, default=_json_default)

    return {
        "status": "ok",
        "best_model": best_algo_final,
        "best_model_display": MODEL_REGISTRY.get(best_algo_final, {}).get("display_name", best_algo_final),
        "stage_one": stage_one,
        "stage_two": stage_two,
        "stage_three": stage_three,
        "comparison": comparison,
        "optimization_report_path": opt_report_path,
        "message": f"Three-stage training completed. Best: {MODEL_REGISTRY.get(best_algo_final, {}).get('display_name', best_algo_final)} (R²={best_r2_final:.4f}).",
    }


def run_stage_three_retrain(state: dict,
                            algorithms: list = None,
                            optimization_results: Optional[dict] = None,
                            base_param_overrides: Optional[dict] = None,
                            progress_callback=None) -> dict:
    """
    阶段三：基于阶段二最优参数重新训练，并生成可直接用于后续解释/预测的模型状态。
    依赖 state["_optimization_result"] 中的 optimization_results。
    """
    try:
        from sklearn.base import clone
        from sklearn.model_selection import train_test_split

        feature_table = state.get("feature_table") or {}
        if not feature_table:
            return {"status": "error", "message": "No feature table. Run build_feature_table first."}

        df_path = feature_table.get("path")
        if not df_path or not os.path.exists(df_path):
            return {"status": "error", "message": f"Feature table not found: {df_path}"}

        optimization_state = state.get("_optimization_result") or {}
        if optimization_results is None:
            optimization_results = optimization_state.get("optimization_results") or {}
        else:
            optimization_results = optimization_results or {}
        if not optimization_results:
            return {
                "status": "error",
                "message": "No optimization results found. Run stage-two Bayesian optimization first.",
            }

        df = pd.read_parquet(df_path)
        if "label" not in df.columns:
            return {"status": "error", "message": "Label column is missing in feature table."}

        feature_cols = _feature_columns_from_df(df, target_col="label")
        if not feature_cols:
            return {"status": "error", "message": "No numeric feature columns are available for retraining."}

        df_clean = df[feature_cols + ["label"]].dropna()
        if len(df_clean) < 50:
            return {"status": "error", "message": f"Insufficient samples: {len(df_clean)} (need >= 50)."}

        X = df_clean[feature_cols].values
        y = df_clean["label"].values
        X_train, X_val, y_train, y_val = train_test_split(X, y, test_size=0.20, random_state=42)

        target_algos = [a.lower() for a in (algorithms or list(optimization_results.keys()))]
        target_algos = [a for a in target_algos if a in MODEL_REGISTRY and a in optimization_results]
        if not target_algos:
            return {"status": "error", "message": "No optimized algorithms are available for retraining."}
        base_overrides, invalid_base_overrides = _normalize_param_overrides_with_errors(base_param_overrides, target_algos)

        run_ctx = state.get("run_context") or {}
        model_dir = ((run_ctx.get("paths") or {}).get("models")) or LEGACY_MODELS_DIR
        reports_dir = ((run_ctx.get("paths") or {}).get("reports")) or os.path.join(DATA_ROOT, "runs", "latest", "reports")
        _ensure_dir(model_dir)
        _ensure_dir(reports_dir)

        previous_models = state.get("models", {}) or {}
        comparison = {}
        retrained_models = {}
        metrics_rows = []
        best_algo = None
        best_rmse = None
        skipped = []

        for idx, algo in enumerate(target_algos):
            opt_result = optimization_results.get(algo) or {}
            current_overrides = base_overrides.get(algo, {})
            if invalid_base_overrides.get(algo):
                skipped.append({
                    "algorithm": algo,
                    "reason": "invalid manual parameters: " + "; ".join(invalid_base_overrides[algo]),
                })
                continue
            if "trial_best_params" in opt_result:
                searched_params = opt_result.get("trial_best_params") or {}
            else:
                searched_params = {
                    key: value
                    for key, value in (opt_result.get("best_params") or {}).items()
                    if key not in current_overrides
                }
            if not searched_params and not (opt_result.get("best_params") or current_overrides):
                skipped.append({"algorithm": algo, "reason": "missing best_params"})
                continue

            actual_params = dict(MODEL_REGISTRY[algo].get("default_params", {}))
            actual_params.update(current_overrides)
            actual_params.update(searched_params)
            try:
                estimator = _build_estimator_from_registry(algo, actual_params)
                metrics = _single_model_evaluate(estimator, X_train, y_train, X_val, y_val)
            except Exception as exc:
                skipped.append({"algorithm": algo, "reason": str(exc)})
                continue

            final_model = clone(estimator)
            fit_start = time.time()
            try:
                final_model.fit(X, y)
            except Exception as exc:
                skipped.append({"algorithm": algo, "reason": str(exc)})
                continue
            fit_elapsed = round(time.time() - fit_start, 2)
            metrics["train_seconds"] = fit_elapsed

            model_path = os.path.join(model_dir, f"{algo}_optimized_model.joblib")
            joblib.dump(final_model, model_path)
            _copy_to_legacy(model_path, os.path.join(LEGACY_MODELS_DIR, f"{algo}_optimized_model.joblib"))
            _record_evidence_path(state, model_path)

            feature_importance = None
            if hasattr(final_model, "feature_importances_"):
                feature_importance = {
                    f: float(v) for f, v in zip(feature_cols, final_model.feature_importances_)
                }

            retrained_models[algo] = {
                "model": final_model,
                "metrics": metrics,
                "feature_names": feature_cols,
                "feature_importance": feature_importance,
                "params": actual_params,
                "path": model_path,
                "optimized": True,
            }

            previous_metrics = ((previous_models.get(algo) or {}).get("metrics")) or {}
            display = MODEL_REGISTRY[algo].get("display_name", algo)
            comparison[display] = {
                "default": previous_metrics,
                "optimized": metrics,
                "improvement": {
                    "r2_delta": round(float(metrics.get("r2", 0.0)) - float(previous_metrics.get("r2", 0.0) or 0.0), 4),
                    "rmse_reduction_pct": round(
                        (
                            (float(previous_metrics.get("rmse", 0.0) or 0.0) - float(metrics.get("rmse", 0.0)))
                            / max(float(previous_metrics.get("rmse", 1e-9) or 1e-9), 1e-9)
                        ) * 100.0,
                        1,
                    ) if previous_metrics.get("rmse") is not None else 0.0,
                },
            }
            metrics_rows.append({
                "algorithm": algo,
                "mae": round(float(metrics.get("mae", np.nan)), 4),
                "rmse": round(float(metrics.get("rmse", np.nan)), 4),
                "r2": round(float(metrics.get("r2", np.nan)), 4),
                "nrmse": round(float(metrics.get("nrmse", np.nan)), 4),
                "pbias": round(float(metrics.get("pbias", np.nan)), 4),
                "train_seconds": round(float(metrics.get("train_seconds", 0.0)), 3),
            })

            if best_rmse is None or float(metrics["rmse"]) < best_rmse:
                best_rmse = float(metrics["rmse"])
                best_algo = algo

            if progress_callback:
                progress_callback({"stage": 3, "algo": algo, "done": idx + 1, "total": len(target_algos)})

        if not retrained_models:
            return {
                "status": "error",
                "message": "Retraining failed for all optimized algorithms.",
                "skipped_algorithms": skipped,
            }

        merged_models = dict(previous_models)
        merged_models.update(retrained_models)
        state["models"] = merged_models
        state["best_model"] = best_algo

        selected_rank_path = os.path.join(model_dir, "model_ranking_selected.json")
        best_info = retrained_models[best_algo]
        _write_json(selected_rank_path, {
            "run_id": (run_ctx or {}).get("run_id"),
            "metric": "rmse",
            "best_algorithm": best_algo,
            "selected_metrics": best_info.get("metrics", {}),
            "optimized_retrain": True,
            "source_model_path": best_info.get("path"),
        })
        _copy_to_legacy(selected_rank_path, os.path.join(LEGACY_MODELS_DIR, "model_ranking_selected.json"))
        selected_artifacts = _persist_selected_model_artifacts(state, best_info["model"], model_dir, {
            "run_id": (run_ctx or {}).get("run_id"),
            "best_algorithm": best_algo,
            "metric": "rmse",
            "selected_metrics": best_info.get("metrics", {}),
            "source_model_path": best_info.get("path"),
            "optimized_retrain": True,
        })
        _record_evidence_path(state, selected_rank_path)
        _record_evidence_path(state, selected_artifacts.get("best_model_path"))
        _record_evidence_path(state, selected_artifacts.get("best_model_meta_path"))

        report_path = os.path.join(reports_dir, "optimized_retrain_report.json")
        report_payload = {
            "timestamp": _now_iso(),
            "best_model": best_algo,
            "best_model_display": MODEL_REGISTRY.get(best_algo, {}).get("display_name", best_algo),
            "optimization_results": optimization_results,
            "retrained_metrics": metrics_rows,
            "comparison": comparison,
            "skipped_algorithms": skipped,
        }
        _write_json(report_path, report_payload)
        _record_evidence_path(state, report_path)

        return {
            "status": "ok",
            "best_model": best_algo,
            "best_model_display": MODEL_REGISTRY.get(best_algo, {}).get("display_name", best_algo),
            "optimization_results": optimization_results,
            "retrained_metrics": metrics_rows,
            "comparison": comparison,
            "skipped_algorithms": skipped,
            "report_path": report_path,
            "evidence_paths": [
                selected_rank_path,
                selected_artifacts.get("best_model_path"),
                selected_artifacts.get("best_model_meta_path"),
                report_path,
            ],
            "message": f"Optimized retraining completed. Best: {MODEL_REGISTRY.get(best_algo, {}).get('display_name', best_algo)}.",
        }
    except Exception as e:
        traceback.print_exc()
        return {
            "status": "error",
            "error_type": type(e).__name__,
            "message": str(e),
            "suggested_action": "run_stage_three_retrain failed. Check optimization results and feature table state.",
        }


def run_one_click_pipeline(state: dict,
                           run_mode: str = "quick",
                           source_mode: str = "rusle_raw",
                           output_dpi: int = DEFAULT_OUTPUT_DPI,
                           run_id: Optional[str] = None,
                           target_resolution_km: float = 5.0,
                           algorithms: Optional[List[str]] = None,
                           cleanup_history: bool = False,
                           max_keep_runs: int = 8) -> dict:
    """One-click research workflow: P0 -> P1 -> P2 -> P3 with stage gates."""
    try:
        step_results = []
        ctx_result = prepare_run_context(
            state=state,
            run_mode=run_mode,
            source_mode=source_mode,
            output_dpi=output_dpi,
            run_id=run_id,
            cleanup_history=cleanup_history,
            max_keep_runs=max_keep_runs,
        )
        if ctx_result.get("status") != "ok":
            return ctx_result
        step_results.append({"stage": "P0", "tool": "prepare_run_context", "result": ctx_result})

        p0_feature = build_feature_table(
            state=state,
            target_resolution_km=target_resolution_km,
            run_mode=run_mode,
            source_mode=source_mode,
            output_dpi=output_dpi,
            run_id=ctx_result["run_id"],
        )
        step_results.append({"stage": "P0", "tool": "build_feature_table", "result": p0_feature})
        if p0_feature.get("status") != "ok":
            return {"status": "error", "run_id": ctx_result["run_id"], "steps": step_results, "message": p0_feature.get("message")}
        gate0 = run_error_corrector(state, stage="P0", run_id=ctx_result["run_id"])
        step_results.append({"stage": "P0", "tool": "run_error_corrector", "result": gate0})
        _record_stage_report(state, "P0", gate0, "completed", "P0 preprocessing and data gate finished.")
        if gate0.get("verdict") == BLOCK:
            _record_stage_report(state, "P0", gate0, "blocked", "P0 gate blocked; downstream stages were not executed.")
            return {"status": "error", "run_id": ctx_result["run_id"], "steps": step_results, "message": "P0 gate blocked."}

        p1_train = train_candidates(
            state=state,
            algorithms=algorithms or DEFAULT_MODEL_POOL,
            cv_folds=4 if run_mode == "quick" else 5,
            run_mode=run_mode,
            source_mode=source_mode,
            output_dpi=output_dpi,
            run_id=ctx_result["run_id"],
        )
        step_results.append({"stage": "P1", "tool": "train_candidates", "result": p1_train})
        if p1_train.get("status") != "ok":
            return {"status": "error", "run_id": ctx_result["run_id"], "steps": step_results, "message": p1_train.get("message")}
        p1_best = select_best(state=state)
        step_results.append({"stage": "P1", "tool": "select_best", "result": p1_best})
        if p1_best.get("status") != "ok":
            return {"status": "error", "run_id": ctx_result["run_id"], "steps": step_results, "message": p1_best.get("message")}
        gate1 = run_error_corrector(state, stage="P1", run_id=ctx_result["run_id"])
        step_results.append({"stage": "P1", "tool": "run_error_corrector", "result": gate1})
        _record_stage_report(state, "P1", gate1, "completed", "P1 model ranking, selection, and metric gate finished.")
        if gate1.get("verdict") == BLOCK:
            _record_stage_report(state, "P1", gate1, "blocked", "P1 gate blocked; P2/P3 were not executed.")
            return {"status": "error", "run_id": ctx_result["run_id"], "steps": step_results, "message": "P1 gate blocked."}

        p2_exp = generate_explanations(state=state, output_dpi=output_dpi, run_id=ctx_result["run_id"])
        step_results.append({"stage": "P2", "tool": "generate_explanations", "result": p2_exp})
        if p2_exp.get("status") != "ok":
            return {"status": "error", "run_id": ctx_result["run_id"], "steps": step_results, "message": p2_exp.get("message")}
        gate2 = run_error_corrector(state, stage="P2", run_id=ctx_result["run_id"])
        step_results.append({"stage": "P2", "tool": "run_error_corrector", "result": gate2})
        _record_stage_report(state, "P2", gate2, "completed", "P2 explanation and spatial artifact gate finished.")
        if gate2.get("verdict") == BLOCK:
            _record_stage_report(state, "P2", gate2, "blocked", "P2 gate blocked; P3 delivery was not executed.")
            return {"status": "error", "run_id": ctx_result["run_id"], "steps": step_results, "message": "P2 gate blocked."}

        predict_result = predict_future(state=state, scenario="ssp245")
        step_results.append({"stage": "P3", "tool": "predict_future", "result": predict_result})
        if predict_result.get("status") != "ok":
            return {"status": "error", "run_id": ctx_result["run_id"], "steps": step_results, "message": predict_result.get("message")}
        report_result = export_results(state=state)
        step_results.append({"stage": "P3", "tool": "export_results", "result": report_result})
        if report_result.get("status") != "ok":
            return {"status": "error", "run_id": ctx_result["run_id"], "steps": step_results, "message": report_result.get("message")}
        bundle_result = export_evidence_bundle(state=state, run_id=ctx_result["run_id"])
        step_results.append({"stage": "P3", "tool": "export_evidence_bundle", "result": bundle_result})
        if bundle_result.get("status") != "ok":
            return {"status": "error", "run_id": ctx_result["run_id"], "steps": step_results, "message": bundle_result.get("message")}
        gate3 = run_error_corrector(state, stage="P3", run_id=ctx_result["run_id"])
        step_results.append({"stage": "P3", "tool": "run_error_corrector", "result": gate3})
        _record_stage_report(state, "P3", gate3, "completed", "P3 report, prediction, bundle, and final gate finished.")
        if gate3.get("verdict") == BLOCK:
            _record_stage_report(state, "P3", gate3, "blocked", "P3 final gate blocked; bundle is not accepted as complete evidence.")

        final_bundle_result = export_evidence_bundle(state=state, run_id=ctx_result["run_id"])
        step_results.append({"stage": "P3", "tool": "export_evidence_bundle_final", "result": final_bundle_result})
        if final_bundle_result.get("status") != "ok":
            return {"status": "error", "run_id": ctx_result["run_id"], "steps": step_results, "message": final_bundle_result.get("message")}

        final_status = "ok" if gate3.get("verdict") != BLOCK else "error"
        return {
            "status": final_status,
            "run_id": ctx_result["run_id"],
            "run_mode": run_mode,
            "source_mode": source_mode,
            "output_dpi": int(output_dpi),
            "steps": step_results,
            "gate_verdict": gate3.get("verdict"),
            "bundle_zip": bundle_result.get("bundle_zip"),
            "evidence_paths": (state.get("run_context", {}).get("evidence_paths", [])),
            "message": f"One-click pipeline finished with gate verdict: {gate3.get('verdict')}",
        }
    except Exception as e:
        traceback.print_exc()
        return {
            "status": "error",
            "error_type": type(e).__name__,
            "message": str(e),
            "suggested_action": "run_one_click_pipeline failed.",
        }


# ============================================================
# 宸ュ叿7: export_results
# ============================================================
def export_results(state: dict) -> dict:
    """Export markdown report (legacy + run evidence)."""
    try:
        ctx = state.get("run_context")
        lines = []
        lines.append("# 黑土区水蚀智能预测与证据化评估平台报告")
        lines.append(f"\nGenerated at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

        lines.append("## 1. Data Summary\n")
        uploads = state.get("uploads", {}) or {}
        lines.append(f"- Uploaded files: {len(uploads)}")
        if uploads:
            lines.append("- File list:")
            for fname in sorted(uploads.keys()):
                info = parse_filename(fname)
                if info:
                    lines.append(f"  - {fname} | var={info.get('variable')} | year={info.get('year','-')} | scenario={info.get('scenario','-')}")
                else:
                    lines.append(f"  - {fname}")

        lines.append("\n## 2. Feature Table\n")
        ft = state.get("feature_table") or {}
        if ft:
            lines.append(f"- Samples: {ft.get('n_samples', 'N/A')}")
            lines.append(f"- Features: {ft.get('n_features', 'N/A')}")
            lines.append(f"- Resolution(km): {ft.get('target_resolution_km', 'N/A')}")

        lines.append("\n## 3. Model Ranking\n")
        models = state.get("models", {}) or {}
        if models:
            lines.append("| Algorithm | MAE | RMSE | R2 | NRMSE | PBIAS | train_seconds |")
            lines.append("|---|---:|---:|---:|---:|---:|---:|")
            for algo, info in models.items():
                m = info.get("metrics", {})
                lines.append(
                    f"| {algo} | {m.get('mae', float('nan')):.4f} | {m.get('rmse', float('nan')):.4f} | {m.get('r2', float('nan')):.4f} | "
                    f"{m.get('nrmse', float('nan')):.4f} | {m.get('pbias', float('nan')):.4f} | {m.get('train_seconds', float('nan')):.4f} |"
                )
            lines.append(f"\n- Best model: {state.get('best_model', 'N/A')}")

        lines.append("\n## 4. Prediction Summary\n")
        pred = state.get("predictions") or {}
        if pred:
            lines.append(f"- Scenario: {pred.get('scenario', 'N/A')}")
            lines.append(f"- Mean erosion: {pred.get('mean_erosion', float('nan')):.2f}")
            lines.append(f"- Max erosion: {pred.get('max_erosion', float('nan')):.2f}")
            lines.append(f"- High risk ratio(%): {pred.get('high_risk_ratio', float('nan')):.2f}")

        lines.append("\n## 5. Method Notes\n")
        lines.append("- NRMSE = RMSE / mean(y_true) * 100%")
        lines.append("- PBIAS = 100 * sum(y_pred - y_true) / sum(y_true)")

        report_content = "\n".join(lines)
        report_path = LEGACY_REPORT_PATH
        _write_text(report_path, report_content)

        run_report_path = None
        if ctx:
            run_report_path = os.path.join(ctx["paths"]["reports"], "report.md")
            _write_text(run_report_path, report_content)
            _record_evidence_path(state, run_report_path)
            ctx["report_path"] = run_report_path or report_path
            state["run_context"] = ctx
            _append_jsonl(os.path.join(ctx["paths"]["reports"], RUN_LOG_NAME), {
                "ts": _now_iso(),
                "stage": "P3",
                "event": "export_results",
                "status": "ok",
                "run_id": ctx.get("run_id"),
            })

        best_algo = state.get("best_model")
        best_metrics_raw = ((state.get("models") or {}).get(best_algo) or {}).get("metrics", {})

        def _metric_or_none(key: str) -> Optional[float]:
            v = best_metrics_raw.get(key, np.nan)
            try:
                fv = float(v)
            except Exception:
                return None
            return fv if np.isfinite(fv) else None

        best_metrics = {
            "mae": _metric_or_none("mae"),
            "rmse": _metric_or_none("rmse"),
            "r2": _metric_or_none("r2"),
            "nrmse": _metric_or_none("nrmse"),
            "pbias": _metric_or_none("pbias"),
            "train_seconds": _metric_or_none("train_seconds"),
        }

        return {
            "status": "ok",
            "report_path": report_path,
            "run_report_path": run_report_path,
            "report_preview": report_content[:800] + "..." if len(report_content) > 800 else report_content,
            "best_algorithm": best_algo,
            "best_metrics": best_metrics,
            "mae": best_metrics["mae"],
            "rmse": best_metrics["rmse"],
            "r2": best_metrics["r2"],
            "nrmse": best_metrics["nrmse"],
            "pbias": best_metrics["pbias"],
            "train_seconds": best_metrics["train_seconds"],
            "run_id": ctx.get("run_id") if ctx else None,
            "evidence_paths": [p for p in [report_path, run_report_path] if p],
            "gate_verdict": (ctx.get("gate_verdict") if ctx else PASS),
            "message": f"Report exported to {report_path}",
        }
    except Exception as e:
        traceback.print_exc()
        return {
            "status": "error",
            "error_type": type(e).__name__,
            "message": str(e),
            "suggested_action": "export_results failed.",
        }


# ============================================================
# 宸ュ叿璋冨害鍣?
# ============================================================
TOOL_MAP = {
    "prepare_run_context": prepare_run_context,
    "prepare_full_resource_preflight": prepare_full_resource_preflight,
    "plan_full_execution": plan_full_execution,
    "run_full_batch_smoke": run_full_batch_smoke,
    "plan_full_spatial_tiles": plan_full_spatial_tiles,
    "run_full_tile_smoke": run_full_tile_smoke,
    "run_full_tile_preprocess": run_full_tile_preprocess,
    "run_full_tile_coverage_probe": run_full_tile_coverage_probe,
    "inspect_uploads": inspect_uploads,
    "build_upload_inventory": build_upload_inventory,
    "assess_data_quality": assess_data_quality,
    "build_feature_table": build_feature_table,
    "train_candidates": train_candidates,
    "run_stage_two_optimization": run_stage_two_optimization,
    "run_stage_three_retrain": run_stage_three_retrain,
    "optimize_hyperparams": optimize_hyperparams,
    "select_best": select_best,
    "set_current_model": set_current_model,
    "predict_future": predict_future,
    "visualize": visualize,
    "run_error_corrector": run_error_corrector,
    "error_corrector_report": error_corrector_report,
    "generate_explanations": generate_explanations,
    "export_evidence_bundle": export_evidence_bundle,
    "run_one_click_pipeline": run_one_click_pipeline,
    "export_results": export_results,
}


def execute_tool(tool_name: str, arguments: dict, state: dict,
                 progress_callback=None) -> dict:
    """Execute a tool function by name."""
    if tool_name not in TOOL_MAP:
        return {
            "status": "error",
            "error_type": "UnknownTool",
            "message": f"Unknown tool: {tool_name}",
            "suggested_action": f"Available tools: {list(TOOL_MAP.keys())}",
        }

    tool_fn = TOOL_MAP[tool_name]

    try:
        if tool_name in ("train_candidates", "optimize_hyperparams", "run_stage_two_optimization", "run_stage_three_retrain"):
            arguments["progress_callback"] = progress_callback
        result = tool_fn(state, **arguments)
        if "status" not in result:
            result["status"] = "ok"
        return result
    except Exception as e:
        return {
            "status": "error",
            "error_type": type(e).__name__,
            "message": str(e),
            "suggested_action": "Tool execution failed; retry with adjusted inputs.",
        }
