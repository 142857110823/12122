import json
import os
import re
import tempfile
import unittest
import zipfile

import numpy as np
import pandas as pd
from rasterio.transform import from_bounds

import agent
import tools
from utils.raster_io import create_sample_tif, reproject_raster


class TestGlobalRiskFixes(unittest.TestCase):
    def test_openai_external_llm_is_disabled_by_code_default(self):
        settings = agent.LocalLLMSettings(backend="openai")
        self.assertIs(settings.allow_external_llm, False)

    def test_reproject_raster_preserves_legitimate_zero_values(self):
        src = np.array([[0.0, 1.0], [2.0, 0.0]], dtype=np.float32)
        transform = from_bounds(0, 0, 2, 2, 2, 2)

        result = reproject_raster(
            src,
            transform,
            "EPSG:4326",
            dst_crs="EPSG:4326",
            dst_resolution=1.0,
        )

        data = result["data"]
        self.assertTrue(np.isfinite(data).any())
        self.assertGreaterEqual(int(np.sum(data == 0.0)), 1)

    def test_upload_inventory_exports_relative_path_not_absolute_path(self):
        with tempfile.TemporaryDirectory(dir=os.getcwd()) as td:
            fp = os.path.join(td, "notes.csv")
            with open(fp, "w", encoding="utf-8") as f:
                f.write("name,value\nR,1\n")
            state = {
                "uploads": {
                    "notes.csv": {
                        "filepath": fp,
                        "size": os.path.getsize(fp),
                        "uploaded_at": "2026-06-09T00:00:00",
                    }
                }
            }

            inventory = tools.build_upload_inventory(state)
            serialized = json.dumps(inventory, ensure_ascii=False)

            self.assertNotIn(td, serialized)
            self.assertNotIn(fp, serialized)
            self.assertEqual(inventory["rows"][0]["path"], "data/uploads/notes.csv")

    def test_evidence_bundle_zip_redacts_absolute_paths_in_text_files(self):
        old_runs = tools.RUNS_ROOT
        with tempfile.TemporaryDirectory(dir=os.getcwd()) as td:
            tools.RUNS_ROOT = os.path.join(td, "runs")
            try:
                state = {"uploads": {}, "models": {}, "_diagnostics": {}}
                tools.prepare_run_context(state, run_mode="quick", source_mode="uploads", cleanup_history=False)
                ctx = state["run_context"]
                leak_path = os.path.join(ctx["paths"]["reports"], "leaky_report.md")
                with open(leak_path, "w", encoding="utf-8") as f:
                    f.write(
                        f"local path: {td}\\secret\\raw.tif\n"
                        "api: sk-abcdefghijklmnopqrstuvwxyz\n"
                        "env: OPENAI_API_KEY=unit-test-secret\n"
                        "unc: \\\\server\\share\\raw.tif\n"
                        "linux: /home/user/raw.tif\n"
                    )
                state["run_context"]["evidence_paths"].append(leak_path)

                bundle = tools.export_evidence_bundle(state, run_id=ctx["run_id"])

                self.assertEqual(bundle["status"], "ok")
                with zipfile.ZipFile(bundle["bundle_zip"]) as zf:
                    for name in zf.namelist():
                        if name.lower().endswith((".json", ".md", ".csv", ".txt", ".jsonl")):
                            text = zf.read(name).decode("utf-8", errors="ignore")
                            self.assertNotIn(td, text, name)
                            self.assertNotIn("unit-test-secret", text, name)
                            self.assertNotIn("\\\\server", text, name)
                            self.assertNotIn("/home/user", text, name)
                            self.assertNotRegex(text, r"[A-Za-z]:\\", name)
                            self.assertNotRegex(text, r"sk-[A-Za-z0-9_-]{10,}", name)
            finally:
                tools.RUNS_ROOT = old_runs

    def test_evidence_bundle_zip_redacts_extended_text_artifacts(self):
        old_runs = tools.RUNS_ROOT
        with tempfile.TemporaryDirectory(dir=os.getcwd()) as td:
            tools.RUNS_ROOT = os.path.join(td, "runs")
            try:
                state = {"uploads": {}, "models": {}, "_diagnostics": {}}
                tools.prepare_run_context(state, run_mode="quick", source_mode="uploads", cleanup_history=False)
                ctx = state["run_context"]
                leak_text = (
                    f"path={td}\\secret\\raw.tif\n"
                    "api=sk-abcdefghijklmnopqrstuvwxyz\n"
                    "env=OPENAI_API_KEY=unit-test-secret\n"
                )
                for filename in (
                    "visual_report.html",
                    "runtime.log",
                    "manifest.xml",
                    "settings.yaml",
                    "settings.yml",
                    "config.toml",
                ):
                    fp = os.path.join(ctx["paths"]["reports"], filename)
                    with open(fp, "w", encoding="utf-8") as f:
                        f.write(leak_text)

                bundle = tools.export_evidence_bundle(state, run_id=ctx["run_id"])

                self.assertEqual(bundle["status"], "ok")
                with zipfile.ZipFile(bundle["bundle_zip"]) as zf:
                    for filename in (
                        "reports/visual_report.html",
                        "reports/runtime.log",
                        "reports/manifest.xml",
                        "reports/settings.yaml",
                        "reports/settings.yml",
                        "reports/config.toml",
                    ):
                        text = zf.read(filename).decode("utf-8", errors="ignore")
                        self.assertNotIn(td, text, filename)
                        self.assertNotIn("unit-test-secret", text, filename)
                        self.assertNotRegex(text, r"[A-Za-z]:\\", filename)
                        self.assertNotRegex(text, r"sk-[A-Za-z0-9_-]{10,}", filename)
            finally:
                tools.RUNS_ROOT = old_runs

    def test_upload_inventory_redacts_paths_in_read_errors(self):
        old_read = tools.read_raster
        with tempfile.TemporaryDirectory(dir=os.getcwd()) as td:
            fp = os.path.join(td, "broken.tif")
            with open(fp, "wb") as f:
                f.write(b"broken")
            try:
                tools.read_raster = lambda path: (_ for _ in ()).throw(
                    RuntimeError(f"cannot open {path}; OPENAI_API_KEY=unit-test-secret")
                )
                inventory = tools.build_upload_inventory({
                    "uploads": {"broken.tif": {"filepath": fp, "size": os.path.getsize(fp)}}
                })
                serialized = json.dumps(inventory, ensure_ascii=False)
                self.assertEqual(inventory["rows"][0]["read_status"], "error")
                self.assertNotIn(td, serialized)
                self.assertNotIn(fp, serialized)
                self.assertNotIn("unit-test-secret", serialized)
            finally:
                tools.read_raster = old_read

    def test_copy_to_legacy_noops_when_source_and_target_are_same_file(self):
        with tempfile.TemporaryDirectory() as td:
            fp = os.path.join(td, "best_model.joblib")
            with open(fp, "wb") as f:
                f.write(b"model")

            tools._copy_to_legacy(fp, fp)

            with open(fp, "rb") as f:
                self.assertEqual(f.read(), b"model")

    def test_stage_three_retrain_uses_current_manual_params_and_persists_best_model(self):
        old_runs = tools.RUNS_ROOT
        old_legacy = tools.LEGACY_MODELS_DIR
        with tempfile.TemporaryDirectory() as td:
            tools.RUNS_ROOT = os.path.join(td, "runs")
            tools.LEGACY_MODELS_DIR = os.path.join(td, "legacy_models")
            try:
                rng = np.random.default_rng(20260609)
                n = 72
                df = pd.DataFrame({
                    "grid_id": np.arange(n),
                    "year": np.full(n, 2024),
                    "row": np.arange(n) // 8,
                    "col": np.arange(n) % 8,
                    "R": rng.uniform(80, 220, size=n),
                    "K": rng.uniform(0.15, 0.45, size=n),
                    "LS": rng.uniform(0.4, 2.8, size=n),
                    "C": rng.uniform(0.02, 0.6, size=n),
                    "P": rng.uniform(0.2, 1.0, size=n),
                })
                df["label"] = 0.01 * df["R"] + 4.0 * df["K"] + rng.normal(0, 0.03, size=n)
                state = {"uploads": {}, "models": {}, "best_model": None, "_diagnostics": {}}
                tools.prepare_run_context(state, run_mode="quick", source_mode="uploads", cleanup_history=False)
                ft_path = os.path.join(state["run_context"]["paths"]["features"], "feature_table.parquet")
                df.to_parquet(ft_path, index=False)
                state["feature_table"] = {"path": ft_path, "n_samples": n, "n_features": 5}
                state["_optimization_result"] = {
                    "optimization_results": {
                        "knn": {
                            "best_params": {"n_neighbors": 9, "weights": "uniform", "algorithm": "auto"},
                            "trial_best_params": {"weights": "uniform", "algorithm": "auto"},
                            "base_params": {"n_neighbors": 9, "weights": "distance"},
                            "best_r2": 0.5,
                        }
                    }
                }

                result = tools.run_stage_three_retrain(
                    state,
                    algorithms=["knn"],
                    base_param_overrides={"knn": {"n_neighbors": 3}},
                )

                self.assertEqual(result["status"], "ok")
                self.assertEqual(state["models"]["knn"]["params"]["n_neighbors"], 3)
                self.assertEqual(state["models"]["knn"]["params"]["weights"], "uniform")
                self.assertTrue(os.path.exists(os.path.join(tools.LEGACY_MODELS_DIR, "best_model.joblib")))
                self.assertTrue(os.path.exists(os.path.join(tools.LEGACY_MODELS_DIR, "best_model_meta.json")))
                self.assertTrue(os.path.exists(os.path.join(tools.LEGACY_MODELS_DIR, "model_ranking_selected.json")))
                model_dir = state["run_context"]["paths"]["models"]
                current_best_model = os.path.join(model_dir, "best_model.joblib")
                current_best_meta = os.path.join(model_dir, "best_model_meta.json")
                self.assertTrue(os.path.exists(current_best_model))
                self.assertTrue(os.path.exists(current_best_meta))
                self.assertIn(current_best_model, state["run_context"]["evidence_paths"])
                self.assertIn(current_best_meta, state["run_context"]["evidence_paths"])
                self.assertIn(current_best_model, result["evidence_paths"])
                self.assertIn(current_best_meta, result["evidence_paths"])
            finally:
                tools.RUNS_ROOT = old_runs
                tools.LEGACY_MODELS_DIR = old_legacy

    def test_stage_three_legacy_best_params_do_not_override_current_manual_params(self):
        old_runs = tools.RUNS_ROOT
        with tempfile.TemporaryDirectory() as td:
            tools.RUNS_ROOT = os.path.join(td, "runs")
            try:
                rng = np.random.default_rng(20260610)
                n = 72
                df = pd.DataFrame({
                    "grid_id": np.arange(n),
                    "year": np.full(n, 2024),
                    "row": np.arange(n) // 8,
                    "col": np.arange(n) % 8,
                    "R": rng.uniform(80, 220, size=n),
                    "K": rng.uniform(0.15, 0.45, size=n),
                    "LS": rng.uniform(0.4, 2.8, size=n),
                    "C": rng.uniform(0.02, 0.6, size=n),
                    "P": rng.uniform(0.2, 1.0, size=n),
                })
                df["label"] = 0.01 * df["R"] + 4.0 * df["K"] + rng.normal(0, 0.03, size=n)
                state = {"uploads": {}, "models": {}, "best_model": None, "_diagnostics": {}}
                tools.prepare_run_context(state, run_mode="quick", source_mode="uploads", cleanup_history=False)
                ft_path = os.path.join(state["run_context"]["paths"]["features"], "feature_table.parquet")
                df.to_parquet(ft_path, index=False)
                state["feature_table"] = {"path": ft_path, "n_samples": n, "n_features": 5}
                state["_optimization_result"] = {
                    "optimization_results": {
                        "knn": {
                            "best_params": {"n_neighbors": 9, "weights": "uniform", "algorithm": "auto"},
                            "best_r2": 0.5,
                        }
                    }
                }

                result = tools.run_stage_three_retrain(
                    state,
                    algorithms=["knn"],
                    base_param_overrides={"knn": {"n_neighbors": 3}},
                )

                self.assertEqual(result["status"], "ok")
                self.assertEqual(state["models"]["knn"]["params"]["n_neighbors"], 3)
                self.assertEqual(state["models"]["knn"]["params"]["weights"], "uniform")
            finally:
                tools.RUNS_ROOT = old_runs

    def test_legacy_optimize_hyperparams_delegates_to_multimodel_registry(self):
        old_runs = tools.RUNS_ROOT
        with tempfile.TemporaryDirectory() as td:
            tools.RUNS_ROOT = os.path.join(td, "runs")
            try:
                rng = np.random.default_rng(20260611)
                n = 72
                df = pd.DataFrame({
                    "grid_id": np.arange(n),
                    "year": np.full(n, 2024),
                    "row": np.arange(n) // 8,
                    "col": np.arange(n) % 8,
                    "R": rng.uniform(80, 220, size=n),
                    "K": rng.uniform(0.15, 0.45, size=n),
                    "LS": rng.uniform(0.4, 2.8, size=n),
                    "C": rng.uniform(0.02, 0.6, size=n),
                    "P": rng.uniform(0.2, 1.0, size=n),
                })
                df["label"] = 0.01 * df["R"] + 4.0 * df["K"] + rng.normal(0, 0.03, size=n)
                state = {"uploads": {}, "models": {}, "best_model": None, "_diagnostics": {}}
                tools.prepare_run_context(state, run_mode="quick", source_mode="uploads", cleanup_history=False)
                ft_path = os.path.join(state["run_context"]["paths"]["features"], "feature_table.parquet")
                df.to_parquet(ft_path, index=False)
                state["feature_table"] = {"path": ft_path, "n_samples": n, "n_features": 5}

                result = tools.optimize_hyperparams(state, algorithms=["knn"], n_folds=3, n_trials=1)

                self.assertEqual(result["status"], "ok")
                self.assertEqual(result["best_algorithm"], "knn")
                self.assertIn("knn", result["best_params"])
                self.assertIn("knn", result["study_history"])
                self.assertIn("knn", state["_optimization_result"]["optimization_results"])
            finally:
                tools.RUNS_ROOT = old_runs

    def test_legacy_optimize_hyperparams_accepts_manual_baseline_overrides(self):
        old_runs = tools.RUNS_ROOT
        with tempfile.TemporaryDirectory() as td:
            tools.RUNS_ROOT = os.path.join(td, "runs")
            try:
                rng = np.random.default_rng(20260612)
                n = 72
                df = pd.DataFrame({
                    "grid_id": np.arange(n),
                    "year": np.full(n, 2024),
                    "row": np.arange(n) // 8,
                    "col": np.arange(n) % 8,
                    "R": rng.uniform(80, 220, size=n),
                    "K": rng.uniform(0.15, 0.45, size=n),
                    "LS": rng.uniform(0.4, 2.8, size=n),
                    "C": rng.uniform(0.02, 0.6, size=n),
                    "P": rng.uniform(0.2, 1.0, size=n),
                })
                df["label"] = 0.01 * df["R"] + 4.0 * df["K"] + rng.normal(0, 0.03, size=n)
                state = {"uploads": {}, "models": {}, "best_model": None, "_diagnostics": {}}
                tools.prepare_run_context(state, run_mode="quick", source_mode="uploads", cleanup_history=False)
                ft_path = os.path.join(state["run_context"]["paths"]["features"], "feature_table.parquet")
                df.to_parquet(ft_path, index=False)
                state["feature_table"] = {"path": ft_path, "n_samples": n, "n_features": 5}

                result = tools.optimize_hyperparams(
                    state,
                    algorithms=["random_forest"],
                    n_folds=3,
                    n_trials=1,
                    base_param_overrides={"random_forest": {"bootstrap": False, "n_estimators": 10}},
                )

                self.assertEqual(result["status"], "ok")
                self.assertEqual(result["best_algorithm"], "random_forest")
                self.assertFalse(state["models"]["random_forest"]["params"]["bootstrap"])
                self.assertFalse(state["models"]["random_forest"]["best_params"]["bootstrap"])
            finally:
                tools.RUNS_ROOT = old_runs

    def test_legacy_optimize_hyperparams_schema_exposes_manual_baseline_overrides(self):
        schemas = tools.load_tool_schemas()
        by_name = {entry["function"]["name"]: entry["function"] for entry in schemas}
        props = by_name["optimize_hyperparams"]["parameters"]["properties"]
        self.assertIn("base_param_overrides", props)
        self.assertIn("label", props["target_col"].get("description", ""))

    def test_legacy_optimize_hyperparams_reports_nonzero_progress(self):
        old_runs = tools.RUNS_ROOT
        with tempfile.TemporaryDirectory() as td:
            tools.RUNS_ROOT = os.path.join(td, "runs")
            try:
                rng = np.random.default_rng(20260613)
                n = 72
                df = pd.DataFrame({
                    "grid_id": np.arange(n),
                    "year": np.full(n, 2024),
                    "row": np.arange(n) // 8,
                    "col": np.arange(n) % 8,
                    "R": rng.uniform(80, 220, size=n),
                    "K": rng.uniform(0.15, 0.45, size=n),
                    "LS": rng.uniform(0.4, 2.8, size=n),
                    "C": rng.uniform(0.02, 0.6, size=n),
                    "P": rng.uniform(0.2, 1.0, size=n),
                })
                df["label"] = 0.01 * df["R"] + 4.0 * df["K"] + rng.normal(0, 0.03, size=n)
                state = {"uploads": {}, "models": {}, "best_model": None, "_diagnostics": {}}
                tools.prepare_run_context(state, run_mode="quick", source_mode="uploads", cleanup_history=False)
                ft_path = os.path.join(state["run_context"]["paths"]["features"], "feature_table.parquet")
                df.to_parquet(ft_path, index=False)
                state["feature_table"] = {"path": ft_path, "n_samples": n, "n_features": 5}
                progress = []

                result = tools.optimize_hyperparams(
                    state,
                    algorithms=["knn"],
                    n_folds=3,
                    n_trials=1,
                    progress_callback=lambda message, pct: progress.append((message, pct)),
                )

                self.assertEqual(result["status"], "ok")
                self.assertTrue(any(0.0 < pct < 1.0 for _, pct in progress), progress)
                self.assertEqual(progress[-1][1], 1.0)
            finally:
                tools.RUNS_ROOT = old_runs

    def test_raw_source_replay_prediction_metadata_is_risk_labeled_consistently(self):
        class DummyModel:
            def predict(self, X):
                return np.asarray(X, dtype=float).sum(axis=1)

        old_runs = tools.RUNS_ROOT
        with tempfile.TemporaryDirectory() as td:
            tools.RUNS_ROOT = os.path.join(td, "runs")
            try:
                state = {
                    "uploads": {},
                    "models": {
                        "dummy": {
                            "model": DummyModel(),
                            "feature_names": ["R", "K"],
                            "metrics": {"mae": 1, "rmse": 1, "r2": 0, "nrmse": 1, "pbias": 0, "train_seconds": 0},
                        }
                    },
                    "best_model": "dummy",
                }
                tools.prepare_run_context(state, run_mode="quick", source_mode="rusle_raw", cleanup_history=False)
                df = pd.DataFrame({
                    "grid_id": [0, 1, 2, 3],
                    "year": [2024, 2024, 2024, 2024],
                    "x": [0.5, 1.5, 0.5, 1.5],
                    "y": [1.5, 1.5, 0.5, 0.5],
                    "row": [0, 0, 1, 1],
                    "col": [0, 1, 0, 1],
                    "R": [1.0, 2.0, 3.0, 4.0],
                    "K": [2.0, 3.0, 4.0, 5.0],
                    "label": [0.1, 0.2, 0.3, 0.4],
                })
                ft_path = os.path.join(state["run_context"]["paths"]["features"], "feature_table.parquet")
                df.to_parquet(ft_path, index=False)
                state["feature_table"] = {"path": ft_path, "run_mode": "quick", "n_samples": 4, "n_features": 2}

                result = tools.predict_future(state, scenario="ssp245")

                self.assertEqual(result["status"], "ok")
                self.assertTrue(result["used_fallback_dynamic"])
                self.assertEqual(result["fallback_variables"], [])
                self.assertTrue(state["predictions"]["risk_note"])
                self.assertTrue(state["predictions"]["used_fallback_dynamic"])
                with open(state["predictions"]["pred_meta_path"], "r", encoding="utf-8") as f:
                    meta = json.load(f)
                self.assertTrue(meta["risk_note"])
                self.assertTrue(meta["used_fallback_dynamic"])
                self.assertEqual(meta["fallback_variables"], [])
            finally:
                tools.RUNS_ROOT = old_runs

    def test_upload_prediction_fallback_is_risk_labeled_in_metadata(self):
        class DummyModel:
            def predict(self, X):
                return np.asarray(X, dtype=float).sum(axis=1)

        old_runs = tools.RUNS_ROOT
        with tempfile.TemporaryDirectory() as td:
            tools.RUNS_ROOT = os.path.join(td, "runs")
            try:
                for name, data in {
                    "R_2024.tif": np.ones((2, 2), dtype=np.float32),
                    "K_2024.tif": np.ones((2, 2), dtype=np.float32) * 2,
                }.items():
                    create_sample_tif(os.path.join(td, name), data, (0, 0, 2, 2))
                state = {
                    "uploads": {
                        name: {"filepath": os.path.join(td, name), "size": os.path.getsize(os.path.join(td, name))}
                        for name in ["R_2024.tif", "K_2024.tif"]
                    },
                    "models": {
                        "dummy": {
                            "model": DummyModel(),
                            "feature_names": ["R", "K"],
                            "metrics": {"mae": 1, "rmse": 1, "r2": 0, "nrmse": 1, "pbias": 0, "train_seconds": 0},
                        }
                    },
                    "best_model": "dummy",
                }
                tools.prepare_run_context(state, run_mode="quick", source_mode="uploads", cleanup_history=False)

                result = tools.predict_future(state, scenario="ssp245")

                self.assertEqual(result["status"], "ok")
                self.assertTrue(result["used_fallback_dynamic"])
                self.assertEqual(result["gate_verdict"], tools.PASS_WITH_RISKS)
                with open(state["predictions"]["pred_meta_path"], "r", encoding="utf-8") as f:
                    meta = json.load(f)
                self.assertEqual(meta["prediction_mode"], "historical_dynamic_fallback")
                self.assertTrue(meta["risk_note"])
                self.assertEqual(meta["fallback_variables"], ["K", "R"])
            finally:
                tools.RUNS_ROOT = old_runs

    def test_upload_prediction_aligns_static_factor_to_scenario_grid(self):
        class DummyModel:
            def predict(self, X):
                return np.asarray(X, dtype=float).sum(axis=1)

        old_runs = tools.RUNS_ROOT
        with tempfile.TemporaryDirectory() as td:
            tools.RUNS_ROOT = os.path.join(td, "runs")
            try:
                raster_defs = {
                    "R_2024.tif": (np.ones((2, 2), dtype=np.float32), (0, 0, 2, 2)),
                    "K_2024.tif": (np.ones((2, 2), dtype=np.float32) * 2, (0, 0, 2, 2)),
                    "LS_2024.tif": (np.ones((2, 2), dtype=np.float32) * 3, (0, 0, 2, 2)),
                    "R_2050_ssp245.tif": (np.ones((2, 2), dtype=np.float32) * 10, (0, 0, 2, 2)),
                    "C_2050_ssp245.tif": (np.ones((2, 2), dtype=np.float32) * 4, (0, 0, 2, 2)),
                    "P_static.tif": (np.ones((4, 4), dtype=np.float32) * 5, (-1, -1, 3, 3)),
                }
                for name, (data, bounds) in raster_defs.items():
                    create_sample_tif(os.path.join(td, name), data, bounds)
                state = {
                    "uploads": {
                        name: {"filepath": os.path.join(td, name), "size": os.path.getsize(os.path.join(td, name))}
                        for name in raster_defs
                    },
                    "models": {
                        "dummy": {
                            "model": DummyModel(),
                            "feature_names": ["R", "C", "P", "K", "LS"],
                            "metrics": {"mae": 1, "rmse": 1, "r2": 0, "nrmse": 1, "pbias": 0, "train_seconds": 0},
                        }
                    },
                    "best_model": "dummy",
                }
                tools.prepare_run_context(state, run_mode="quick", source_mode="uploads", cleanup_history=False)

                result = tools.predict_future(state, scenario="ssp245")

                self.assertEqual(result["status"], "ok")
                self.assertEqual(result["fallback_variables"], ["K", "LS"])
                self.assertTrue(result["used_fallback_dynamic"])
                self.assertEqual(result["gate_verdict"], tools.PASS_WITH_RISKS)
                self.assertTrue(os.path.exists(state["predictions"]["pred_path"]))
                with open(state["predictions"]["pred_meta_path"], "r", encoding="utf-8") as f:
                    meta = json.load(f)
                self.assertTrue(meta["used_fallback_dynamic"])
                self.assertEqual(meta["fallback_variables"], ["K", "LS"])
            finally:
                tools.RUNS_ROOT = old_runs

    def test_upload_prediction_aligns_scenario_dynamic_factors_to_one_grid(self):
        class DummyModel:
            def predict(self, X):
                return np.asarray(X, dtype=float).sum(axis=1)

        old_runs = tools.RUNS_ROOT
        with tempfile.TemporaryDirectory() as td:
            tools.RUNS_ROOT = os.path.join(td, "runs")
            try:
                raster_defs = {
                    "R_2050_ssp245.tif": (np.ones((4, 4), dtype=np.float32) * 10, (0, 0, 4, 4)),
                    "C_2050_ssp245.tif": (np.ones((2, 2), dtype=np.float32) * 4, (0, 0, 1, 1)),
                }
                for name, (data, bounds) in raster_defs.items():
                    create_sample_tif(os.path.join(td, name), data, bounds)
                state = {
                    "uploads": {
                        name: {"filepath": os.path.join(td, name), "size": os.path.getsize(os.path.join(td, name))}
                        for name in raster_defs
                    },
                    "models": {
                        "dummy": {
                            "model": DummyModel(),
                            "feature_names": ["R", "C"],
                            "metrics": {"mae": 1, "rmse": 1, "r2": 0, "nrmse": 1, "pbias": 0, "train_seconds": 0},
                        }
                    },
                    "best_model": "dummy",
                }
                tools.prepare_run_context(state, run_mode="quick", source_mode="uploads", cleanup_history=False)

                result = tools.predict_future(state, scenario="ssp245")

                self.assertEqual(result["status"], "ok")
                self.assertEqual(result["prediction_mode"], "scenario_raster_prediction")
                self.assertFalse(result["used_fallback_dynamic"])
                self.assertTrue(os.path.exists(state["predictions"]["pred_path"]))
            finally:
                tools.RUNS_ROOT = old_runs

    def test_upload_prediction_fallback_does_not_downgrade_block_gate(self):
        class DummyModel:
            def predict(self, X):
                return np.asarray(X, dtype=float).sum(axis=1)

        old_runs = tools.RUNS_ROOT
        with tempfile.TemporaryDirectory() as td:
            tools.RUNS_ROOT = os.path.join(td, "runs")
            try:
                for name, data in {
                    "R_2024.tif": np.ones((2, 2), dtype=np.float32),
                    "K_2024.tif": np.ones((2, 2), dtype=np.float32) * 2,
                }.items():
                    create_sample_tif(os.path.join(td, name), data, (0, 0, 2, 2))
                state = {
                    "uploads": {
                        name: {"filepath": os.path.join(td, name), "size": os.path.getsize(os.path.join(td, name))}
                        for name in ["R_2024.tif", "K_2024.tif"]
                    },
                    "models": {
                        "dummy": {
                            "model": DummyModel(),
                            "feature_names": ["R", "K"],
                            "metrics": {"mae": 1, "rmse": 1, "r2": 0, "nrmse": 1, "pbias": 0, "train_seconds": 0},
                        }
                    },
                    "best_model": "dummy",
                }
                tools.prepare_run_context(state, run_mode="quick", source_mode="uploads", cleanup_history=False)
                state["run_context"]["gate_verdict"] = tools.BLOCK

                result = tools.predict_future(state, scenario="ssp245")

                self.assertEqual(result["status"], "ok")
                self.assertTrue(result["used_fallback_dynamic"])
                self.assertEqual(result["gate_verdict"], tools.BLOCK)
                self.assertEqual(state["run_context"]["gate_verdict"], tools.BLOCK)
            finally:
                tools.RUNS_ROOT = old_runs

    def test_visualize_writes_portable_evidence_artifacts(self):
        old_runs = tools.RUNS_ROOT
        with tempfile.TemporaryDirectory() as td:
            tools.RUNS_ROOT = os.path.join(td, "runs")
            try:
                state = {
                    "uploads": {},
                    "models": {
                        "random_forest": {
                            "metrics": {"mae": 1.0, "rmse": 2.0, "r2": 0.5},
                        }
                    },
                    "best_model": "random_forest",
                    "_diagnostics": {
                        "feature_names": ["R", "K"],
                        "importance": [0.7, 0.3],
                        "y_true": np.array([1.0, 2.0, 3.0]),
                        "y_pred": np.array([1.1, 1.9, 3.2]),
                        "residuals": np.array([-0.1, 0.1, -0.2]),
                    },
                    "predictions": {
                        "scenario": "ssp245",
                        "pred_raster": np.array([[1.0, 2.0], [3.0, np.nan]], dtype=np.float32),
                        "uncert_raster": np.array([[0.1, 0.2], [0.3, 0.4]], dtype=np.float32),
                        "transform": from_bounds(0, 0, 2, 2, 2, 2),
                        "crs": "EPSG:4326",
                    },
                }
                tools.prepare_run_context(state, run_mode="quick", source_mode="uploads", cleanup_history=False)

                metrics = tools.visualize(state, "metrics")
                importance = tools.visualize(state, "importance")
                scatter = tools.visualize(state, "scatter")
                map_result = tools.visualize(state, "map")
                uncertainty = tools.visualize(state, "uncertainty")

                for result in [metrics, importance, scatter, map_result, uncertainty]:
                    self.assertEqual(result["status"], "ok")
                    self.assertTrue(result.get("evidence_paths"), result)
                    for path in result["evidence_paths"]:
                        self.assertTrue(os.path.exists(path), path)
                        self.assertIn(path, state["run_context"]["evidence_paths"])
                self.assertTrue(metrics["artifact_path"].endswith(".png"))
                self.assertTrue(map_result["html_path"].endswith(".html"))
                self.assertTrue(uncertainty["html_path"].endswith(".html"))
                self.assertTrue(scatter["residual_artifact_path"].endswith(".png"))
            finally:
                tools.RUNS_ROOT = old_runs

    def test_visualize_error_paths_do_not_create_run_context(self):
        old_runs = tools.RUNS_ROOT
        with tempfile.TemporaryDirectory() as td:
            tools.RUNS_ROOT = os.path.join(td, "runs")
            try:
                empty_state = {}
                no_metrics = tools.visualize(empty_state, "metrics")
                self.assertEqual(no_metrics["status"], "error")
                self.assertNotIn("run_context", empty_state)

                invalid_state = {}
                invalid = tools.visualize(invalid_state, "bad_target")
                self.assertEqual(invalid["status"], "error")
                self.assertNotIn("run_context", invalid_state)
            finally:
                tools.RUNS_ROOT = old_runs

    def test_visualize_repairs_incomplete_run_context_before_success(self):
        old_runs = tools.RUNS_ROOT
        with tempfile.TemporaryDirectory() as td:
            tools.RUNS_ROOT = os.path.join(td, "runs")
            try:
                state = {
                    "run_context": {"run_id": "legacy_partial", "paths": {}},
                    "models": {
                        "random_forest": {
                            "metrics": {"mae": 1.0, "rmse": 2.0, "r2": 0.5},
                        }
                    },
                }

                result = tools.visualize(state, "metrics")

                self.assertEqual(result["status"], "ok")
                self.assertTrue(result["evidence_paths"])
                self.assertTrue(os.path.exists(result["artifact_path"]))
                self.assertIn(result["artifact_path"], state["run_context"]["evidence_paths"])
                self.assertIn("reports", state["run_context"]["paths"])
            finally:
                tools.RUNS_ROOT = old_runs

    def test_generate_explanations_error_paths_do_not_create_run_context(self):
        old_runs = tools.RUNS_ROOT
        with tempfile.TemporaryDirectory() as td:
            tools.RUNS_ROOT = os.path.join(td, "runs")
            try:
                state = {}

                result = tools.generate_explanations(state, output_dpi=80)

                self.assertEqual(result["status"], "error")
                self.assertNotIn("run_context", state)
            finally:
                tools.RUNS_ROOT = old_runs

    def test_generate_explanations_repairs_incomplete_run_context_before_success(self):
        class DummyImportanceModel:
            feature_importances_ = np.array([0.4, 0.2, 0.15, 0.15, 0.1], dtype=float)

        old_runs = tools.RUNS_ROOT
        with tempfile.TemporaryDirectory() as td:
            tools.RUNS_ROOT = os.path.join(td, "runs")
            try:
                n = 16
                df = pd.DataFrame({
                    "grid_id": np.arange(n),
                    "year": np.full(n, 2024),
                    "row": np.repeat(np.arange(4), 4),
                    "col": np.tile(np.arange(4), 4),
                    "R": np.linspace(100, 150, n),
                    "K": np.linspace(0.2, 0.4, n),
                    "LS": np.linspace(0.5, 1.5, n),
                    "C": np.linspace(0.05, 0.4, n),
                    "P": np.linspace(0.3, 0.9, n),
                    "label": np.linspace(1.0, 2.0, n),
                })
                ft_path = os.path.join(td, "features.parquet")
                df.to_parquet(ft_path)
                state = {
                    "run_context": {
                        "run_id": "legacy_partial",
                        "run_mode": "quick",
                        "source_mode": "rusle_raw",
                        "paths": {},
                    },
                    "feature_table": {"path": ft_path},
                    "best_model": "random_forest",
                    "models": {"random_forest": {"model": DummyImportanceModel()}},
                }

                result = tools.generate_explanations(state, output_dpi=80)

                self.assertEqual(result["status"], "ok")
                self.assertEqual(result["explanation_mode"], "proxy")
                self.assertTrue(result["evidence_paths"])
                self.assertIn("explanations", state["run_context"]["paths"])
                self.assertIn("spatial", state["run_context"]["paths"])
                for path in result["evidence_paths"]:
                    self.assertTrue(os.path.exists(path), path)
                    self.assertIn(path, state["run_context"]["evidence_paths"])
            finally:
                tools.RUNS_ROOT = old_runs


if __name__ == "__main__":
    unittest.main()
