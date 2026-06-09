import os
import json
import math
import tempfile
import unittest

import numpy as np
import pandas as pd

import tools
from utils.raster_io import create_sample_tif


class TestP0P3Upgrade(unittest.TestCase):

    def test_raw_filename_mapping(self):
        self.assertEqual(tools._infer_raw_item("SE_Heilongjiang_2018-0000-0001.tif")["variable"], "label")
        self.assertEqual(tools._infer_raw_item("C2018_300.tif")["variable"], "C")
        self.assertEqual(tools._infer_raw_item("K_300.tif")["variable"], "K")
        self.assertEqual(tools._infer_raw_item("R_mean.tif")["variable"], "R")

    def test_manifest_hash_deterministic(self):
        payload = {"a": 1, "b": [3, 2, 1]}
        h1 = tools._manifest_hash(payload)
        h2 = tools._manifest_hash(payload)
        self.assertEqual(h1, h2)

    def test_default_run_ids_are_unique(self):
        self.assertNotEqual(tools._sanitize_run_id(None), tools._sanitize_run_id(None))

    def test_public_tool_schema_and_app_one_click_binding(self):
        schemas = tools.load_tool_schemas()
        by_name = {item["function"]["name"]: item["function"] for item in schemas}
        for name in [
            "prepare_run_context",
            "run_error_corrector",
            "run_one_click_pipeline",
            "generate_explanations",
            "export_evidence_bundle",
        ]:
            self.assertIn(name, by_name)

        run_one_props = by_name["run_one_click_pipeline"]["parameters"]["properties"]
        for param in ["run_mode", "source_mode", "output_dpi", "run_id"]:
            self.assertIn(param, run_one_props)
        self.assertEqual(run_one_props["run_mode"]["enum"], ["quick", "full"])
        self.assertEqual(run_one_props["source_mode"]["enum"], ["rusle_raw", "uploads"])

        with open(os.path.join(os.path.dirname(__file__), "app.py"), "r", encoding="utf-8") as f:
            app_text = f.read()
        self.assertIn('"run_one_click_pipeline": ("run_one_click_pipeline"', app_text)
        self.assertNotIn("run_one_click_pipeline_action", app_text)

    def test_model_tool_schema_contract_covers_optimization_chain(self):
        schemas = tools.load_tool_schemas()
        by_name = {item["function"]["name"]: item["function"] for item in schemas}
        for name in ["train_candidates", "run_stage_two_optimization", "run_stage_three_retrain"]:
            self.assertIn(name, by_name)

        train_props = by_name["train_candidates"]["parameters"]["properties"]
        self.assertIn("param_overrides", train_props)

        stage_two_props = by_name["run_stage_two_optimization"]["parameters"]["properties"]
        for param in ["algorithms", "cv_folds", "n_trials", "timeout_sec", "base_param_overrides"]:
            self.assertIn(param, stage_two_props)

        stage_three_props = by_name["run_stage_three_retrain"]["parameters"]["properties"]
        for param in ["algorithms", "optimization_results", "base_param_overrides"]:
            self.assertIn(param, stage_three_props)

    def test_metric_formulas(self):
        y_true = np.array([10.0, 20.0, 30.0])
        y_pred = np.array([12.0, 18.0, 27.0])
        rmse = float(np.sqrt(np.mean((y_true - y_pred) ** 2)))
        nrmse = tools._calc_nrmse(rmse, y_true)
        pbias = tools._calc_pbias(y_true, y_pred)
        self.assertAlmostEqual(nrmse, rmse / np.mean(y_true) * 100.0, places=6)
        self.assertAlmostEqual(pbias, 100.0 * np.sum(y_pred - y_true) / np.sum(y_true), places=6)

    def test_safe_cleanup_boundary(self):
        old_root = tools.RUNS_ROOT
        with tempfile.TemporaryDirectory() as td:
            tools.RUNS_ROOT = os.path.join(td, "runs")
            os.makedirs(tools.RUNS_ROOT, exist_ok=True)
            for i in range(5):
                p = os.path.join(tools.RUNS_ROOT, f"run_{i}")
                os.makedirs(p, exist_ok=True)
                with open(os.path.join(p, "a.txt"), "w", encoding="utf-8") as f:
                    f.write("x")
            keep_other = os.path.join(tools.RUNS_ROOT, "external_notes")
            os.makedirs(keep_other, exist_ok=True)
            result = tools._safe_cleanup_runs(max_keep=2)
            remain = [d for d in os.listdir(tools.RUNS_ROOT) if os.path.isdir(os.path.join(tools.RUNS_ROOT, d))]
            remain_runs = [d for d in remain if d.startswith("run_")]
            self.assertLessEqual(len(remain_runs), 2)
            self.assertTrue(os.path.isdir(keep_other))
            for rp in result["removed"]:
                self.assertEqual(os.path.commonpath([os.path.realpath(rp), os.path.realpath(tools.RUNS_ROOT)]), os.path.realpath(tools.RUNS_ROOT))
                self.assertTrue(os.path.basename(rp).startswith("run_"))
        tools.RUNS_ROOT = old_root

    def test_prepare_run_context_preserves_history_by_default(self):
        old_root = tools.RUNS_ROOT
        with tempfile.TemporaryDirectory(dir=os.getcwd()) as td:
            tools.RUNS_ROOT = os.path.join(td, "runs")
            try:
                os.makedirs(tools.RUNS_ROOT, exist_ok=True)
                for i in range(14):
                    run_dir = os.path.join(tools.RUNS_ROOT, f"run_old_{i:02d}")
                    os.makedirs(run_dir, exist_ok=True)
                    with open(os.path.join(run_dir, "marker.txt"), "w", encoding="utf-8") as f:
                        f.write("keep")

                state = {"uploads": {}, "models": {}, "_diagnostics": {}}
                tools.prepare_run_context(state, run_mode="quick", source_mode="uploads")
                remaining = [
                    name for name in os.listdir(tools.RUNS_ROOT)
                    if name.startswith("run_old_") and os.path.isdir(os.path.join(tools.RUNS_ROOT, name))
                ]
                self.assertEqual(len(remaining), 14)
            finally:
                tools.RUNS_ROOT = old_root

    def test_upload_sanitizes_filename_and_invalidates_downstream_state(self):
        import app

        class FakeUpload:
            name = r"..\escape.tif"
            size = 4

            def getbuffer(self):
                return b"data"

        old_file = app.__file__
        app.st.session_state.clear()
        app.init_session_state()
        app.st.session_state["feature_table"] = {"path": "old.parquet"}
        app.st.session_state["models"] = {"random_forest": {"metrics": {"r2": 0.9}}}
        app.st.session_state["best_model"] = "random_forest"
        app.st.session_state["predictions"] = {"pred_path": "old.npy"}
        app.st.session_state["_explanation_meta"] = {"explanation_files": ["old.png"]}
        app.st.session_state["_optimization_result"] = {"optimization_results": {"random_forest": {}}}
        app.st.session_state["run_context"] = {"run_id": "old"}

        with tempfile.TemporaryDirectory(dir=os.getcwd()) as td:
            try:
                app.__file__ = os.path.join(td, "app.py")
                count = app.handle_uploaded_files([FakeUpload()])
                upload_root = os.path.realpath(os.path.join(td, "data", "uploads"))
                stored = app.st.session_state["uploads"]["escape.tif"]["filepath"]

                self.assertEqual(count, 1)
                self.assertEqual(
                    os.path.commonpath([os.path.realpath(stored), upload_root]),
                    upload_root,
                )
                self.assertTrue(os.path.exists(stored))
                self.assertFalse(os.path.exists(os.path.join(td, "data", "escape.tif")))
                self.assertIsNone(app.st.session_state["feature_table"])
                self.assertEqual(app.st.session_state["models"], {})
                self.assertIsNone(app.st.session_state["best_model"])
                self.assertIsNone(app.st.session_state["predictions"])
                self.assertEqual(app.st.session_state["_explanation_meta"], {})
                self.assertIsNone(app.st.session_state["_optimization_result"])
                self.assertIsNone(app.st.session_state["run_context"])
            finally:
                app.__file__ = old_file
                app.st.session_state.clear()

    def test_error_corrector_report_alias_is_dispatchable(self):
        old_root = tools.RUNS_ROOT
        with tempfile.TemporaryDirectory() as td:
            tools.RUNS_ROOT = os.path.join(td, "runs")
            try:
                state = {
                    "uploads": {},
                    "feature_table": None,
                    "models": {},
                    "best_model": None,
                    "predictions": None,
                    "_diagnostics": {},
                    "_quality_report": None,
                }
                ctx = tools.prepare_run_context(state, run_mode="quick", source_mode="uploads", cleanup_history=False)
                report = tools.error_corrector_report(state, stage="P0", run_id=ctx["run_id"])
                dispatched = tools.execute_tool(
                    "error_corrector_report",
                    {"stage": "P0", "run_id": ctx["run_id"]},
                    state,
                )
                self.assertIn("error_corrector_report", tools.TOOL_MAP)
                self.assertEqual(report["status"], "ok")
                self.assertEqual(dispatched["status"], "ok")
                self.assertEqual(report["verdict"], dispatched["verdict"])
                self.assertTrue(os.path.exists(report["gate_path"]))
            finally:
                tools.RUNS_ROOT = old_root

    def test_train_candidates_unified_metrics(self):
        with tempfile.TemporaryDirectory() as td:
            fp = os.path.join(td, "ft.parquet")
            rng = np.random.default_rng(42)
            n = 120
            df = pd.DataFrame({
                "grid_id": np.arange(n),
                "year": np.where(np.arange(n) < 60, 2018, 2020),
                "x": rng.normal(size=n),
                "y": rng.normal(size=n),
                "row": np.arange(n) % 12,
                "col": np.arange(n) % 10,
                "tile_id": np.where(np.arange(n) < 60, "tile_a", "tile_b"),
                "R": rng.uniform(100, 200, size=n),
                "K": rng.uniform(0.1, 0.5, size=n),
                "LS": rng.uniform(0.5, 2.5, size=n),
                "C": rng.uniform(0.01, 0.5, size=n),
                "P": rng.uniform(0.1, 1.0, size=n),
            })
            df["label"] = 0.01 * df["R"] + 10 * df["K"] + 2 * df["C"] + rng.normal(0, 0.5, size=n)
            df.to_parquet(fp, index=False)

            state = {
                "uploads": {},
                "feature_table": {"path": fp},
                "models": {},
                "best_model": None,
                "predictions": None,
                "_diagnostics": {},
                "_quality_report": None,
            }
            tools.prepare_run_context(state, run_mode="quick", source_mode="uploads", cleanup_history=False)
            res = tools.train_candidates(state, algorithms=["random_forest", "knn"], cv_folds=3, run_mode="quick", source_mode="uploads")
            self.assertEqual(res["status"], "ok")
            self.assertTrue(res["metrics"])
            required = {"mae", "rmse", "r2", "nrmse", "pbias", "train_seconds"}
            for row in res["metrics"]:
                self.assertTrue(required.issubset(set(row.keys())))
            for info in state["models"].values():
                self.assertNotIn("tile_id", info["feature_names"])

    def test_train_candidates_uses_manual_param_overrides(self):
        with tempfile.TemporaryDirectory() as td:
            fp = os.path.join(td, "ft.parquet")
            rng = np.random.default_rng(77)
            n = 90
            df = pd.DataFrame({
                "grid_id": np.arange(n),
                "year": np.full(n, 2024),
                "row": np.arange(n) // 9,
                "col": np.arange(n) % 9,
                "R": rng.uniform(80, 220, size=n),
                "K": rng.uniform(0.15, 0.45, size=n),
                "LS": rng.uniform(0.4, 2.8, size=n),
                "C": rng.uniform(0.02, 0.6, size=n),
                "P": rng.uniform(0.2, 1.0, size=n),
            })
            df["label"] = (
                0.012 * df["R"]
                + 6.0 * df["K"]
                + 0.8 * df["LS"]
                - 1.5 * df["C"]
                + rng.normal(0, 0.05, size=n)
            )
            df.to_parquet(fp, index=False)
            state = {
                "uploads": {},
                "feature_table": {"path": fp},
                "models": {},
                "best_model": None,
                "predictions": None,
                "_diagnostics": {},
                "_quality_report": None,
            }
            tools.prepare_run_context(state, run_mode="quick", source_mode="uploads", cleanup_history=False)

            res = tools.train_candidates(
                state,
                algorithms=["random_forest"],
                cv_folds=3,
                run_mode="quick",
                source_mode="uploads",
                param_overrides={"random_forest": {"n_estimators": 11, "max_depth": 3}},
            )

            self.assertEqual(res["status"], "ok")
            model_info = state["models"]["random_forest"]
            self.assertEqual(model_info["params"]["n_estimators"], 11)
            self.assertEqual(model_info["params"]["max_depth"], 3)
            self.assertEqual(model_info["model"].get_params()["n_estimators"], 11)
            self.assertEqual(model_info["model"].get_params()["max_depth"], 3)

    def test_train_candidates_accepts_sklearn_max_features_string_overrides(self):
        with tempfile.TemporaryDirectory() as td:
            fp = os.path.join(td, "ft.parquet")
            rng = np.random.default_rng(3307)
            n = 90
            df = pd.DataFrame({
                "grid_id": np.arange(n),
                "year": np.full(n, 2024),
                "row": np.arange(n) // 9,
                "col": np.arange(n) % 9,
                "R": rng.uniform(80, 220, size=n),
                "K": rng.uniform(0.15, 0.45, size=n),
                "LS": rng.uniform(0.4, 2.8, size=n),
                "C": rng.uniform(0.02, 0.6, size=n),
                "P": rng.uniform(0.2, 1.0, size=n),
            })
            df["label"] = 0.012 * df["R"] + 5.0 * df["K"] + 0.3 * df["LS"] + rng.normal(0, 0.05, size=n)
            df.to_parquet(fp, index=False)
            state = {
                "uploads": {},
                "feature_table": {"path": fp},
                "models": {},
                "best_model": None,
                "predictions": None,
                "_diagnostics": {},
                "_quality_report": None,
            }
            tools.prepare_run_context(state, run_mode="quick", source_mode="uploads", cleanup_history=False)

            res = tools.train_candidates(
                state,
                algorithms=["random_forest", "extratrees"],
                cv_folds=3,
                run_mode="quick",
                source_mode="uploads",
                param_overrides={
                    "random_forest": {"n_estimators": 11, "max_depth": 4, "max_features": "sqrt"},
                    "extratrees": {"n_estimators": 11, "max_depth": 4, "max_features": "log2"},
                },
            )

            self.assertEqual(res["status"], "ok")
            self.assertIn("random_forest", state["models"])
            self.assertIn("extratrees", state["models"])
            self.assertEqual(state["models"]["random_forest"]["params"]["max_features"], "sqrt")
            self.assertEqual(state["models"]["extratrees"]["params"]["max_features"], "log2")
            skipped = {item["algorithm"] for item in res.get("skipped_algorithms", [])}
            self.assertNotIn("random_forest", skipped)
            self.assertNotIn("extratrees", skipped)

    def test_modeling_actions_dispatch_manual_params_to_training_optimization_and_retrain(self):
        import app

        app.st.session_state.clear()
        app.init_session_state()
        app.st.session_state["current_layer"] = "modelingLab"
        app.st.session_state["workflow_stage"] = "features_built"
        app.st.session_state["model_algorithm_selection"] = [
            tools.MODEL_REGISTRY["random_forest"]["display_name"]
        ]
        app.st.session_state["model_param_overrides"] = {
            "random_forest": {"n_estimators": 13, "max_depth": 4}
        }

        calls = []
        original_execute = app.execute_tool_and_analyze

        def fake_execute(tool_name, state, tool_kwargs=None, analysis_stage=None):
            calls.append((tool_name, dict(tool_kwargs or {}), analysis_stage))
            return {
                "tool_result": {"status": "error", "message": "stubbed"},
                "analysis": "stubbed",
                "images": [],
                "maps": [],
            }

        try:
            app.execute_tool_and_analyze = fake_execute
            app.handle_action("train_models")
            app.handle_action("optimize_models")
            app.handle_action("retrain_optimized")
        finally:
            app.execute_tool_and_analyze = original_execute
            app.st.session_state.clear()

        self.assertEqual(calls[0][0], "train_candidates")
        self.assertEqual(calls[0][1]["param_overrides"]["random_forest"]["n_estimators"], 13)
        self.assertEqual(calls[0][1]["param_overrides"]["random_forest"]["max_depth"], 4)
        self.assertEqual(calls[1][0], "run_stage_two_optimization")
        self.assertEqual(calls[1][1]["base_param_overrides"]["random_forest"]["n_estimators"], 13)
        self.assertEqual(calls[1][1]["base_param_overrides"]["random_forest"]["max_depth"], 4)
        self.assertEqual(calls[2][0], "run_stage_three_retrain")
        self.assertEqual(calls[2][1]["base_param_overrides"]["random_forest"]["n_estimators"], 13)
        self.assertEqual(calls[2][1]["base_param_overrides"]["random_forest"]["max_depth"], 4)

    def test_build_features_syncs_tool_mutated_feature_table_to_session_state(self):
        import app

        app.st.session_state.clear()
        app.init_session_state()
        app.st.session_state["uploads"] = {
            "R_2022.tif": {"filepath": "R_2022.tif", "size": 1}
        }
        app.st.session_state["current_layer"] = "modelingLab"
        app.st.session_state["workflow_stage"] = "data_loaded"

        original_execute = app.execute_tool_and_analyze
        feature_table = {
            "path": "data/runs/run_test/features/feature_table.parquet",
            "n_samples": 66,
            "n_features": 5,
            "columns": ["P", "R", "K", "LS", "C"],
            "run_id": "run_test",
        }

        def fake_execute(tool_name, state, tool_kwargs=None, analysis_stage=None):
            self.assertEqual(tool_name, "build_feature_table")
            state["feature_table"] = dict(feature_table)
            state["run_context"] = {"run_id": "run_test"}
            return {
                "tool_result": {
                    "status": "ok",
                    "parquet_path": feature_table["path"],
                    "n_samples": feature_table["n_samples"],
                    "n_features": feature_table["n_features"],
                },
                "analysis": "stubbed",
                "images": [],
                "maps": [],
            }

        try:
            app.execute_tool_and_analyze = fake_execute
            app.handle_action("build_features")
        finally:
            app.execute_tool_and_analyze = original_execute
            synced = app.st.session_state.get("feature_table")
            stage = app.st.session_state.get("workflow_stage")
            last_error = app.st.session_state.get("_last_feature_build_error")
            global_state = app.st.session_state.get("global_state") or {}
            global_feature = (global_state.get("shared_artifacts") or {}).get("feature_table")
            global_feature_status = (
                ((global_state.get("layers") or {}).get("modelingLab") or {}).get("input") or {}
            ).get("featureTableStatus")
            app.st.session_state.clear()

        self.assertEqual(synced, feature_table)
        self.assertEqual(stage, "features_built")
        self.assertIsNone(last_error)
        self.assertEqual(global_feature, feature_table)
        self.assertEqual(global_feature_status, "ready")

    def test_core_actions_dispatch_to_real_tools_when_qa_seed_is_disabled(self):
        import app

        expected = {
            "assess_quality": "assess_data_quality",
            "build_features": "build_feature_table",
            "train_models": "train_candidates",
            "optimize_models": "run_stage_two_optimization",
            "retrain_optimized": "run_stage_three_retrain",
            "generate_explanations": "generate_explanations",
            "predict": "predict_future",
            "export_bundle": "export_evidence_bundle",
        }
        old_seed = os.environ.pop("WATER_EROSION_UI_QA_SEED", None)
        original_execute = app.execute_tool_and_analyze
        calls = []

        def fake_execute(tool_name, state, tool_kwargs=None, analysis_stage=None):
            calls.append((tool_name, dict(tool_kwargs or {}), analysis_stage))
            return {
                "tool_result": {"status": "error", "message": f"{tool_name} stubbed"},
                "analysis": f"{tool_name} stubbed",
                "images": [],
                "maps": [],
            }

        try:
            app.execute_tool_and_analyze = fake_execute
            for action, tool_name in expected.items():
                app.st.session_state.clear()
                app.init_session_state()
                app.st.session_state["_qa_seeded"] = True
                app.st.session_state["current_layer"] = "modelingLab"
                app.st.session_state["workflow_stage"] = "models_optimized"
                app.st.session_state["feature_table"] = {"path": "feature_table.parquet"}
                app.st.session_state["models"] = {"random_forest": {"metrics": {}, "params": {}}}
                app.st.session_state["best_model"] = "random_forest"
                app.st.session_state["_optimization_result"] = {"optimization_results": {"random_forest": {"best_params": {}}}}
                app.st.session_state["model_algorithm_selection"] = [
                    tools.MODEL_REGISTRY["random_forest"]["display_name"]
                ]

                before = len(calls)
                app.handle_action(action)

                self.assertEqual(len(calls), before + 1, action)
                self.assertEqual(calls[-1][0], tool_name, action)
        finally:
            app.execute_tool_and_analyze = original_execute
            app.st.session_state.clear()
            if old_seed is not None:
                os.environ["WATER_EROSION_UI_QA_SEED"] = old_seed

    def test_manual_param_normalization_coerces_bool_strings(self):
        normalized = tools._normalize_param_overrides(
            {
                "random_forest": {"bootstrap": "False"},
                "svr": {"shrinking": "0"},
            },
            ["random_forest", "svr"],
        )

        self.assertIs(normalized["random_forest"]["bootstrap"], False)
        self.assertIs(normalized["svr"]["shrinking"], False)

    def test_manual_param_normalization_accepts_sklearn_max_features_strings(self):
        normalized = tools._normalize_param_overrides(
            {
                "random_forest": {"max_features": "sqrt"},
                "extratrees": {"max_features": "log2"},
            },
            ["random_forest", "extratrees"],
        )

        self.assertEqual(normalized["random_forest"]["max_features"], "sqrt")
        self.assertEqual(normalized["extratrees"]["max_features"], "log2")

    def test_manual_param_normalization_rejects_unknown_max_features_strings(self):
        normalized = tools._normalize_param_overrides(
            {
                "random_forest": {"max_features": "bad-value"},
                "extratrees": {"max_features": "auto"},
            },
            ["random_forest", "extratrees"],
        )

        self.assertNotIn("random_forest", normalized)
        self.assertNotIn("extratrees", normalized)

    def test_manual_param_normalization_rejects_out_of_bounds_and_invalid_enums(self):
        normalized = tools._normalize_param_overrides(
            {
                "random_forest": {
                    "n_estimators": 10,
                    "max_depth": 6,
                    "max_features": 2.0,
                },
                "knn": {
                    "n_neighbors": 2,
                    "weights": "bad-weight",
                    "algorithm": "kd_tree",
                },
                "svr": {
                    "kernel": "sigmoid",
                    "C": 1.0,
                },
            },
            ["random_forest", "knn", "svr"],
        )

        self.assertEqual(normalized["random_forest"], {"n_estimators": 10, "max_depth": 6})
        self.assertEqual(normalized["knn"], {"n_neighbors": 2, "algorithm": "kd_tree"})
        self.assertEqual(normalized["svr"], {"C": 1.0})

    def test_invalid_manual_param_skips_only_that_model(self):
        with tempfile.TemporaryDirectory() as td:
            fp = os.path.join(td, "ft.parquet")
            rng = np.random.default_rng(78)
            n = 90
            df = pd.DataFrame({
                "grid_id": np.arange(n),
                "year": np.full(n, 2024),
                "row": np.arange(n) // 9,
                "col": np.arange(n) % 9,
                "R": rng.uniform(80, 220, size=n),
                "K": rng.uniform(0.15, 0.45, size=n),
                "LS": rng.uniform(0.4, 2.8, size=n),
                "C": rng.uniform(0.02, 0.6, size=n),
                "P": rng.uniform(0.2, 1.0, size=n),
            })
            df["label"] = (
                0.012 * df["R"]
                + 6.0 * df["K"]
                + 0.8 * df["LS"]
                - 1.5 * df["C"]
                + rng.normal(0, 0.05, size=n)
            )
            df.to_parquet(fp, index=False)
            state = {
                "uploads": {},
                "feature_table": {"path": fp},
                "models": {},
                "best_model": None,
                "predictions": None,
                "_diagnostics": {},
                "_quality_report": None,
            }
            tools.prepare_run_context(state, run_mode="quick", source_mode="uploads", cleanup_history=False)

            res = tools.train_candidates(
                state,
                algorithms=["random_forest", "knn"],
                cv_folds=3,
                run_mode="quick",
                source_mode="uploads",
                param_overrides={
                    "random_forest": {"n_estimators": 0},
                    "knn": {"n_neighbors": 3},
                },
            )

            self.assertEqual(res["status"], "ok")
            self.assertNotIn("random_forest", state["models"])
            self.assertIn("knn", state["models"])
            self.assertEqual(state["models"]["knn"]["params"]["n_neighbors"], 3)
            self.assertEqual(res["skipped_algorithms"][0]["algorithm"], "random_forest")

    def test_three_stage_training_runs_and_writes_report(self):
        old_runs = tools.RUNS_ROOT
        with tempfile.TemporaryDirectory() as td:
            tools.RUNS_ROOT = os.path.join(td, "runs")
            try:
                rng = np.random.default_rng(2026)
                n = 90
                df = pd.DataFrame({
                    "grid_id": np.arange(n),
                    "year": np.full(n, 2024),
                    "row": np.arange(n) // 9,
                    "col": np.arange(n) % 9,
                    "R": rng.uniform(80, 220, size=n),
                    "K": rng.uniform(0.15, 0.45, size=n),
                    "LS": rng.uniform(0.4, 2.8, size=n),
                    "C": rng.uniform(0.02, 0.6, size=n),
                    "P": rng.uniform(0.2, 1.0, size=n),
                })
                df["label"] = (
                    0.012 * df["R"]
                    + 6.0 * df["K"]
                    + 0.8 * df["LS"]
                    - 1.5 * df["C"]
                    + rng.normal(0, 0.05, size=n)
                )

                state = {
                    "uploads": {"synthetic.csv": {"filepath": "synthetic.csv", "size": 1}},
                    "feature_table": None,
                    "models": {},
                    "best_model": None,
                    "predictions": None,
                    "_diagnostics": {},
                    "_quality_report": None,
                }
                tools.prepare_run_context(state, run_mode="quick", source_mode="uploads", cleanup_history=False)
                ft_path = os.path.join(state["run_context"]["paths"]["features"], "three_stage_feature_table.parquet")
                df.to_parquet(ft_path, index=False)
                state["feature_table"] = {"path": ft_path, "n_samples": n, "n_features": 5}

                progress_events = []
                result = tools.run_three_stage_training(
                    state,
                    algorithms=["knn"],
                    cv_folds=3,
                    n_opt_trials=2,
                    progress_callback=progress_events.append,
                )

                self.assertEqual(result["status"], "ok")
                self.assertEqual(result["best_model"], "knn")
                self.assertEqual(state["best_model"], "knn")
                self.assertIn("KNN", result["stage_one"])
                self.assertIn("knn", result["stage_two"])
                self.assertEqual(result["stage_two"]["knn"]["n_trials"], 2)
                self.assertIn("KNN", result["stage_three"])
                self.assertIn("KNN", result["comparison"])
                self.assertIsInstance(result["comparison"]["KNN"].get("optimized"), dict)
                self.assertTrue(progress_events)

                report_path = result.get("optimization_report_path")
                self.assertTrue(report_path and os.path.exists(report_path))
                with open(report_path, "r", encoding="utf-8") as f:
                    payload = json.load(f)
                self.assertEqual(payload["best_model"], "knn")
                self.assertIn("comparison", payload)
                self.assertIn("KNN", payload["comparison"])
            finally:
                tools.RUNS_ROOT = old_runs

    def test_stage_two_writes_state_and_stage_three_retrains_directly(self):
        old_runs = tools.RUNS_ROOT
        with tempfile.TemporaryDirectory() as td:
            tools.RUNS_ROOT = os.path.join(td, "runs")
            try:
                rng = np.random.default_rng(3301)
                n = 80
                df = pd.DataFrame({
                    "grid_id": np.arange(n),
                    "year": np.full(n, 2024),
                    "x": rng.uniform(120.0, 121.0, size=n),
                    "y": rng.uniform(45.0, 46.0, size=n),
                    "row": np.arange(n) // 8,
                    "col": np.arange(n) % 8,
                    "R": rng.uniform(80, 220, size=n),
                    "K": rng.uniform(0.15, 0.45, size=n),
                    "LS": rng.uniform(0.4, 2.8, size=n),
                    "C": rng.uniform(0.02, 0.6, size=n),
                    "P": rng.uniform(0.2, 1.0, size=n),
                })
                df["label"] = 0.012 * df["R"] + 5.0 * df["K"] + rng.normal(0, 0.05, size=n)
                state = {
                    "uploads": {},
                    "feature_table": None,
                    "models": {},
                    "best_model": None,
                    "predictions": None,
                    "_diagnostics": {},
                    "_quality_report": None,
                }
                tools.prepare_run_context(state, run_mode="quick", source_mode="uploads", cleanup_history=False)
                ft_path = os.path.join(state["run_context"]["paths"]["features"], "feature_table.parquet")
                df.to_parquet(ft_path, index=False)
                state["feature_table"] = {"path": ft_path, "n_samples": n, "n_features": 5}

                opt = tools.run_stage_two_optimization(
                    state,
                    algorithms=["knn"],
                    cv_folds=3,
                    n_trials=1,
                    base_param_overrides={"knn": {"n_neighbors": 3, "weights": "uniform"}},
                )
                self.assertEqual(opt["status"], "ok")
                self.assertIn("_optimization_result", state)
                self.assertIn("knn", state["_optimization_result"]["optimization_results"])
                self.assertEqual(opt["optimization_results"]["knn"]["base_params"]["n_neighbors"], 3)
                self.assertEqual(opt["optimization_results"]["knn"]["base_params"]["weights"], "uniform")

                retrain = tools.run_stage_three_retrain(state, algorithms=["knn"])
                self.assertEqual(retrain["status"], "ok")
                self.assertIn("knn", state["models"])
                self.assertTrue(state["models"]["knn"]["optimized"])
                self.assertIn("model", state["models"]["knn"])
                self.assertIn("feature_names", state["models"]["knn"])
                self.assertEqual(state["models"]["knn"]["feature_names"], ["R", "K", "LS", "C", "P"])
            finally:
                tools.RUNS_ROOT = old_runs

    def test_stage_three_retrain_merges_current_manual_params_with_optimized_trial_params(self):
        old_runs = tools.RUNS_ROOT
        with tempfile.TemporaryDirectory() as td:
            tools.RUNS_ROOT = os.path.join(td, "runs")
            try:
                rng = np.random.default_rng(3308)
                n = 80
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
                df["label"] = 0.012 * df["R"] + 5.0 * df["K"] + rng.normal(0, 0.05, size=n)
                state = {"uploads": {}, "feature_table": None, "models": {}, "best_model": None}
                tools.prepare_run_context(state, run_mode="quick", source_mode="uploads", cleanup_history=False)
                ft_path = os.path.join(state["run_context"]["paths"]["features"], "feature_table.parquet")
                df.to_parquet(ft_path, index=False)
                state["feature_table"] = {"path": ft_path, "n_samples": n, "n_features": 5}
                state["_optimization_result"] = {
                    "optimization_results": {
                        "knn": {
                            "trial_best_params": {"n_neighbors": 5},
                            "best_params": {"n_neighbors": 5, "weights": "uniform"},
                        }
                    }
                }

                retrain = tools.run_stage_three_retrain(
                    state,
                    algorithms=["knn"],
                    base_param_overrides={"knn": {"weights": "distance"}},
                )

                self.assertEqual(retrain["status"], "ok")
                self.assertEqual(state["models"]["knn"]["params"]["n_neighbors"], 5)
                self.assertEqual(state["models"]["knn"]["params"]["weights"], "distance")
                self.assertEqual(state["models"]["knn"]["model"].get_params()["n_neighbors"], 5)
                self.assertEqual(state["models"]["knn"]["model"].get_params()["weights"], "distance")
            finally:
                tools.RUNS_ROOT = old_runs

    def test_stage_two_skips_algorithm_with_invalid_manual_params_only(self):
        old_runs = tools.RUNS_ROOT
        with tempfile.TemporaryDirectory() as td:
            tools.RUNS_ROOT = os.path.join(td, "runs")
            try:
                rng = np.random.default_rng(3305)
                n = 80
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
                df["label"] = 0.012 * df["R"] + 5.0 * df["K"] + rng.normal(0, 0.05, size=n)
                state = {"uploads": {}, "feature_table": None, "models": {}, "best_model": None}
                tools.prepare_run_context(state, run_mode="quick", source_mode="uploads", cleanup_history=False)
                ft_path = os.path.join(state["run_context"]["paths"]["features"], "feature_table.parquet")
                df.to_parquet(ft_path, index=False)
                state["feature_table"] = {"path": ft_path, "n_samples": n, "n_features": 5}

                opt = tools.run_stage_two_optimization(
                    state,
                    algorithms=["random_forest", "knn"],
                    cv_folds=3,
                    n_trials=1,
                    base_param_overrides={
                        "random_forest": {"n_estimators": 0},
                        "knn": {"n_neighbors": 3},
                    },
                )

                self.assertEqual(opt["status"], "ok")
                self.assertNotIn("random_forest", opt["optimization_results"])
                self.assertIn("knn", opt["optimization_results"])
                skipped = {item["algorithm"]: item["reason"] for item in opt["skipped_algorithms"]}
                self.assertIn("random_forest", skipped)
                self.assertIn("invalid manual parameters", skipped["random_forest"])
            finally:
                tools.RUNS_ROOT = old_runs

    def test_stage_three_skips_algorithm_with_invalid_manual_params(self):
        old_runs = tools.RUNS_ROOT
        with tempfile.TemporaryDirectory() as td:
            tools.RUNS_ROOT = os.path.join(td, "runs")
            try:
                rng = np.random.default_rng(3306)
                n = 80
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
                df["label"] = 0.012 * df["R"] + 5.0 * df["K"] + rng.normal(0, 0.05, size=n)
                state = {"uploads": {}, "feature_table": None, "models": {}, "best_model": None}
                tools.prepare_run_context(state, run_mode="quick", source_mode="uploads", cleanup_history=False)
                ft_path = os.path.join(state["run_context"]["paths"]["features"], "feature_table.parquet")
                df.to_parquet(ft_path, index=False)
                state["feature_table"] = {"path": ft_path, "n_samples": n, "n_features": 5}
                state["_optimization_result"] = {
                    "optimization_results": {
                        "knn": {
                            "trial_best_params": {"n_neighbors": 3, "weights": "distance"},
                            "best_params": {"n_neighbors": 3, "weights": "distance"},
                        }
                    }
                }

                retrain = tools.run_stage_three_retrain(
                    state,
                    algorithms=["knn"],
                    base_param_overrides={"knn": {"weights": "bad-weight"}},
                )

                self.assertEqual(retrain["status"], "error")
                self.assertNotIn("knn", state["models"])
                self.assertIn("invalid manual parameters", retrain["skipped_algorithms"][0]["reason"])
            finally:
                tools.RUNS_ROOT = old_runs

    def test_catboost_model_chain_runs_when_available_or_reports_unavailable(self):
        old_runs = tools.RUNS_ROOT
        with tempfile.TemporaryDirectory() as td:
            tools.RUNS_ROOT = os.path.join(td, "runs")
            try:
                rng = np.random.default_rng(3302)
                n = 70
                df = pd.DataFrame({
                    "grid_id": np.arange(n),
                    "year": np.full(n, 2024),
                    "row": np.arange(n) // 7,
                    "col": np.arange(n) % 7,
                    "R": rng.uniform(80, 220, size=n),
                    "K": rng.uniform(0.15, 0.45, size=n),
                    "LS": rng.uniform(0.4, 2.8, size=n),
                    "C": rng.uniform(0.02, 0.6, size=n),
                    "P": rng.uniform(0.2, 1.0, size=n),
                    "label": rng.normal(1.0, 0.1, size=n),
                })
                state = {"uploads": {}, "feature_table": None, "models": {}, "_diagnostics": {}}
                tools.prepare_run_context(state, run_mode="quick", source_mode="uploads", cleanup_history=False)
                ft_path = os.path.join(state["run_context"]["paths"]["features"], "feature_table.parquet")
                df.to_parquet(ft_path, index=False)
                state["feature_table"] = {"path": ft_path, "n_samples": n, "n_features": 5}

                try:
                    import catboost  # noqa: F401
                except Exception:
                    res = tools.run_stage_two_optimization(state, algorithms=["catboost"], cv_folds=3, n_trials=1)
                    self.assertEqual(res["status"], "error")
                    self.assertNotIn("catboost", res.get("optimization_results", {}))
                    self.assertEqual(res["skipped_algorithms"][0]["algorithm"], "catboost")
                    return

                manual_params = {"catboost": {"n_estimators": 20, "depth": 4, "learning_rate": 0.08}}
                train = tools.train_candidates(
                    state,
                    algorithms=["catboost"],
                    cv_folds=3,
                    run_mode="quick",
                    source_mode="uploads",
                    param_overrides=manual_params,
                )
                self.assertEqual(train["status"], "ok")
                self.assertIn("catboost", state["models"])
                self.assertEqual(state["models"]["catboost"]["params"]["n_estimators"], 20)

                opt = tools.run_stage_two_optimization(
                    state,
                    algorithms=["catboost"],
                    cv_folds=3,
                    n_trials=1,
                    base_param_overrides=manual_params,
                )
                self.assertEqual(opt["status"], "ok")
                self.assertIn("catboost", opt["optimization_results"])
                self.assertIn("best_params", opt["optimization_results"]["catboost"])
                self.assertEqual(opt["optimization_results"]["catboost"]["base_params"]["depth"], 4)

                retrain = tools.run_stage_three_retrain(
                    state,
                    algorithms=["catboost"],
                    base_param_overrides=manual_params,
                )
                self.assertEqual(retrain["status"], "ok")
                self.assertIn("catboost", state["models"])
                self.assertTrue(os.path.exists(state["models"]["catboost"]["path"]))
                self.assertIn(state["models"]["catboost"]["path"], state["run_context"]["evidence_paths"])
            finally:
                tools.RUNS_ROOT = old_runs

    def test_three_stage_training_algorithm_matrix_smoke(self):
        old_runs = tools.RUNS_ROOT
        with tempfile.TemporaryDirectory() as td:
            tools.RUNS_ROOT = os.path.join(td, "runs")
            try:
                rng = np.random.default_rng(2027)
                n = 75
                df = pd.DataFrame({
                    "grid_id": np.arange(n),
                    "year": np.full(n, 2025),
                    "row": np.arange(n) // 5,
                    "col": np.arange(n) % 5,
                    "R": rng.uniform(90, 210, size=n),
                    "K": rng.uniform(0.12, 0.5, size=n),
                    "LS": rng.uniform(0.3, 3.0, size=n),
                    "C": rng.uniform(0.01, 0.65, size=n),
                    "P": rng.uniform(0.15, 1.0, size=n),
                })
                df["label"] = (
                    0.01 * df["R"]
                    + 5.5 * df["K"]
                    + 0.6 * df["LS"]
                    - 1.2 * df["C"]
                    + rng.normal(0, 0.08, size=n)
                )

                state = {
                    "uploads": {"matrix.csv": {"filepath": "matrix.csv", "size": 1}},
                    "feature_table": None,
                    "models": {},
                    "best_model": None,
                    "predictions": None,
                    "_diagnostics": {},
                    "_quality_report": None,
                }
                tools.prepare_run_context(state, run_mode="quick", source_mode="uploads", cleanup_history=False)
                ft_path = os.path.join(state["run_context"]["paths"]["features"], "three_stage_matrix.parquet")
                df.to_parquet(ft_path, index=False)
                state["feature_table"] = {"path": ft_path, "n_samples": n, "n_features": 5}

                result = tools.run_three_stage_training(
                    state,
                    algorithms=["random_forest", "svr"],
                    cv_folds=3,
                    n_opt_trials=1,
                )

                self.assertEqual(result["status"], "ok")
                self.assertIn(result["best_model"], {"random_forest", "svr"})
                self.assertIn("random_forest", result["stage_two"])
                self.assertIn("svr", result["stage_two"])
                self.assertNotIn("error", result["stage_two"]["random_forest"])
                self.assertNotIn("error", result["stage_two"]["svr"])
                self.assertIn("随机森林", result["stage_one"])
                self.assertIn("支持向量机", result["stage_one"])
                self.assertIn("随机森林", result["comparison"])
                self.assertIn("支持向量机", result["comparison"])
                self.assertTrue(os.path.exists(result["optimization_report_path"]))
            finally:
                tools.RUNS_ROOT = old_runs

    def test_model_latest_legacy_double_write(self):
        old_runs = tools.RUNS_ROOT
        old_legacy = tools.LEGACY_MODELS_DIR
        with tempfile.TemporaryDirectory() as td:
            tools.RUNS_ROOT = os.path.join(td, "runs")
            tools.LEGACY_MODELS_DIR = os.path.join(td, "legacy_models")
            try:
                rng = np.random.default_rng(7)
                n = 80
                df = pd.DataFrame({
                    "grid_id": np.arange(n),
                    "year": np.full(n, 2020),
                    "x": rng.normal(size=n),
                    "y": rng.normal(size=n),
                    "row": np.arange(n) // 10,
                    "col": np.arange(n) % 10,
                    "R": rng.uniform(100, 200, size=n),
                    "K": rng.uniform(0.1, 0.5, size=n),
                    "LS": rng.uniform(0.5, 2.5, size=n),
                    "C": rng.uniform(0.01, 0.5, size=n),
                    "P": rng.uniform(0.1, 1.0, size=n),
                })
                df["label"] = 0.01 * df["R"] + 4 * df["K"] + rng.normal(0, 0.1, size=n)
                state = {
                    "uploads": {"fixture.tif": {"filepath": "fixture", "size": 1}},
                    "feature_table": None,
                    "models": {},
                    "best_model": None,
                    "predictions": None,
                    "_diagnostics": {},
                    "_quality_report": None,
                }
                tools.prepare_run_context(state, run_mode="quick", source_mode="uploads", cleanup_history=False)
                ft_path = os.path.join(state["run_context"]["paths"]["features"], "feature_table.parquet")
                df.to_parquet(ft_path, index=False)
                state["feature_table"] = {"path": ft_path, "n_samples": n, "n_features": 5}

                train = tools.train_candidates(state, algorithms=["random_forest"], cv_folds=4, run_mode="quick", source_mode="uploads")
                self.assertEqual(train["status"], "ok")
                selected = tools.select_best(state)
                self.assertEqual(selected["status"], "ok")

                for name in [
                    "random_forest_model.joblib",
                    "model_ranking.json",
                    "model_ranking_selected.json",
                    "best_model.joblib",
                    "best_model_meta.json",
                ]:
                    self.assertTrue(os.path.exists(os.path.join(tools.LEGACY_MODELS_DIR, name)), name)
                model_dir = state["run_context"]["paths"]["models"]
                current_best_model = os.path.join(model_dir, "best_model.joblib")
                current_best_meta = os.path.join(model_dir, "best_model_meta.json")
                self.assertTrue(os.path.exists(current_best_model))
                self.assertTrue(os.path.exists(current_best_meta))
                self.assertIn(current_best_model, state["run_context"]["evidence_paths"])
                self.assertIn(current_best_meta, state["run_context"]["evidence_paths"])
                self.assertIn(current_best_model, selected["evidence_paths"])
                self.assertIn(current_best_meta, selected["evidence_paths"])
            finally:
                tools.RUNS_ROOT = old_runs
                tools.LEGACY_MODELS_DIR = old_legacy

    def test_quick_pipeline_with_uploads(self):
        with tempfile.TemporaryDirectory() as td:
            # create tiny rasters
            bounds = (0, 0, 0.02, 0.02)
            shape = (10, 10)
            rng = np.random.default_rng(1)
            def make(name, data):
                p = os.path.join(td, name)
                create_sample_tif(p, data.astype(np.float32), bounds=bounds)
                return p

            uploads = {}
            for year in (2018, 2020):
                r = rng.uniform(100, 150, size=shape)
                k = rng.uniform(0.2, 0.5, size=shape)
                ls = rng.uniform(0.5, 2.0, size=shape)
                c = rng.uniform(0.05, 0.5, size=shape)
                p = rng.uniform(0.3, 1.0, size=shape)
                label = 0.01 * r + 8 * k + 2 * c + rng.normal(0, 0.1, size=shape)
                for var, arr in [("R", r), ("K", k), ("LS", ls), ("C", c), ("P", p), ("label", label)]:
                    fp = make(f"{var}_{year}.tif", arr)
                    uploads[os.path.basename(fp)] = {"filepath": fp, "size": os.path.getsize(fp)}

            state = {
                "uploads": uploads,
                "feature_table": None,
                "models": {},
                "best_model": None,
                "predictions": None,
                "_diagnostics": {},
                "_quality_report": None,
            }
            res = tools.run_one_click_pipeline(state, run_mode="quick", source_mode="uploads", target_resolution_km=5.0, algorithms=["random_forest"])
            self.assertIn(res["status"], {"ok", "error"})
            self.assertTrue(res.get("run_id"))
            rc = state.get("run_context")
            self.assertIsNotNone(rc)
            self.assertTrue(os.path.isdir(rc["paths"]["root"]))
            self.assertTrue(os.path.exists(rc["manifest_path"]))
            if res["status"] == "ok":
                gate_summary_path = os.path.join(rc["paths"]["bundle"], "gate_summary.json")
                self.assertTrue(os.path.exists(gate_summary_path))
                with open(gate_summary_path, "r", encoding="utf-8") as f:
                    gate_summary = json.load(f)
                self.assertIn("P3", gate_summary.get("gate_reports", {}))

    def test_one_click_preserves_run_history_by_default(self):
        captured = {}
        original = tools.prepare_run_context

        def fake_prepare_run_context(**kwargs):
            captured.update(kwargs)
            return {"status": "error", "message": "stop after prepare"}

        try:
            tools.prepare_run_context = fake_prepare_run_context
            res = tools.run_one_click_pipeline({})
            self.assertEqual(res["status"], "error")
            self.assertFalse(captured.get("cleanup_history"))
        finally:
            tools.prepare_run_context = original

    def test_one_click_stops_when_p2_generation_fails(self):
        with tempfile.TemporaryDirectory() as td:
            old_runs = tools.RUNS_ROOT
            tools.RUNS_ROOT = os.path.join(td, "runs")
            originals = {
                "prepare_run_context": tools.prepare_run_context,
                "build_feature_table": tools.build_feature_table,
                "run_error_corrector": tools.run_error_corrector,
                "train_candidates": tools.train_candidates,
                "select_best": tools.select_best,
                "generate_explanations": tools.generate_explanations,
                "predict_future": tools.predict_future,
            }
            called_predict = {"value": False}

            try:
                state = {"uploads": {"dummy.tif": {"filepath": "dummy", "size": 1}}, "models": {}}
                tools.prepare_run_context = lambda **kwargs: originals["prepare_run_context"](**kwargs)
                tools.build_feature_table = lambda **kwargs: {"status": "ok", "message": "features ok"}
                tools.run_error_corrector = lambda state, stage, run_id=None: {"status": "ok", "stage": stage, "verdict": tools.PASS, "block_items": []}
                tools.train_candidates = lambda **kwargs: {"status": "ok", "metrics": [{"algorithm": "dummy", "mae": 1, "rmse": 1, "r2": 0, "nrmse": 1, "pbias": 0, "train_seconds": 0.1}]}
                tools.select_best = lambda state, metric="rmse": {"status": "ok", "best_algorithm": "dummy"}
                tools.generate_explanations = lambda **kwargs: {"status": "error", "message": "p2 failed"}

                def fake_predict(*args, **kwargs):
                    called_predict["value"] = True
                    return {"status": "ok"}

                tools.predict_future = fake_predict
                res = tools.run_one_click_pipeline(state, run_mode="quick", source_mode="uploads")

                self.assertEqual(res["status"], "error")
                self.assertEqual(res["message"], "p2 failed")
                self.assertFalse(called_predict["value"])
            finally:
                for name, fn in originals.items():
                    setattr(tools, name, fn)
                tools.RUNS_ROOT = old_runs

    def test_stage_report_template_is_written_to_run_log(self):
        with tempfile.TemporaryDirectory() as td:
            old_runs = tools.RUNS_ROOT
            tools.RUNS_ROOT = os.path.join(td, "runs")
            try:
                state = {"uploads": {"dummy.tif": {"filepath": "dummy", "size": 1}}}
                ctx = tools.prepare_run_context(state, run_mode="quick", source_mode="uploads", cleanup_history=False)
                tools._record_stage_report(
                    state,
                    "P0",
                    {"verdict": tools.PASS, "block_items": []},
                    "completed",
                    "test stage report",
                )
                log_path = os.path.join(state["run_context"]["paths"]["reports"], tools.RUN_LOG_NAME)
                with open(log_path, "r", encoding="utf-8") as f:
                    rows = [json.loads(line) for line in f if line.strip()]
                reports = [r for r in rows if r.get("event") == "stage_report"]
                self.assertTrue(reports)
                self.assertEqual(reports[-1]["template"], "stage_report_v1")
                self.assertEqual(reports[-1]["stage"], "P0")
                self.assertTrue(reports[-1]["next_allowed"])
                self.assertEqual(ctx["run_id"], reports[-1]["run_id"])
            finally:
                tools.RUNS_ROOT = old_runs

    def test_alignment_keeps_rusle_factors_with_mixed_grids(self):
        with tempfile.TemporaryDirectory() as td:
            rng = np.random.default_rng(7)
            label_bounds = (0.0, 0.0, 0.06, 0.06)
            static_bounds = (-0.01, -0.01, 0.07, 0.07)
            shape_label = (12, 12)
            shape_static = (18, 18)

            def make(name, arr, bounds):
                fp = os.path.join(td, name)
                create_sample_tif(fp, arr.astype(np.float32), bounds=bounds)
                return fp

            uploads = {}
            label = rng.uniform(0.5, 3.0, size=shape_label)
            c = rng.uniform(0.02, 0.6, size=shape_label)
            uploads["label_2018.tif"] = {"filepath": make("label_2018.tif", label, label_bounds), "size": 1}
            uploads["C_2018.tif"] = {"filepath": make("C_2018.tif", c, label_bounds), "size": 1}

            for var in ("R", "K", "LS", "P"):
                arr = rng.uniform(0.1, 1.0, size=shape_static)
                fp = make(f"{var}.tif", arr, static_bounds)
                uploads[os.path.basename(fp)] = {"filepath": fp, "size": os.path.getsize(fp)}

            state = {
                "uploads": uploads,
                "feature_table": None,
                "models": {},
                "best_model": None,
                "predictions": None,
                "_diagnostics": {},
                "_quality_report": None,
            }
            tools.prepare_run_context(state, run_mode="quick", source_mode="uploads", cleanup_history=False)
            res = tools.build_feature_table(
                state=state,
                target_resolution_km=5.0,
                run_mode="quick",
                source_mode="uploads",
            )
            self.assertEqual(res["status"], "ok")
            cols = set(res.get("feature_columns", []))
            self.assertTrue({"R", "K", "LS", "C", "P"}.issubset(cols))
            audit_path = state["feature_table"].get("preprocess_audit_path")
            self.assertTrue(audit_path and os.path.exists(audit_path))
            with open(audit_path, "r", encoding="utf-8") as f:
                audit = json.load(f)
            self.assertTrue(audit.get("required_ok"))
            self.assertEqual(audit.get("missing_factors"), [])

    def test_error_corrector_blocks_incomplete_rusle_factors(self):
        with tempfile.TemporaryDirectory() as td:
            old_runs = tools.RUNS_ROOT
            tools.RUNS_ROOT = os.path.join(td, "runs")
            try:
                state = {
                    "uploads": {"dummy.tif": {"filepath": "dummy", "size": 1}},
                    "feature_table": None,
                    "models": {},
                    "best_model": None,
                    "predictions": None,
                    "_diagnostics": {},
                    "_quality_report": None,
                }
                tools.prepare_run_context(state, run_mode="quick", source_mode="rusle_raw", cleanup_history=False)
                ctx = state["run_context"]

                df = pd.DataFrame({
                    "grid_id": [0, 1, 2],
                    "year": [2018, 2018, 2018],
                    "x": [0.0, 1.0, 2.0],
                    "y": [0.0, 1.0, 2.0],
                    "row": [0, 0, 0],
                    "col": [0, 1, 2],
                    "label": [1.0, 1.2, 0.9],
                    "C": [0.2, 0.3, 0.4],
                })
                ft_path = os.path.join(ctx["paths"]["features"], "feature_table.parquet")
                df.to_parquet(ft_path, index=False)
                audit_path = os.path.join(ctx["paths"]["features"], "preprocess_audit.json")
                with open(audit_path, "w", encoding="utf-8") as f:
                    json.dump({
                        "source_mode": "rusle_raw",
                        "required_rusle_factors": ["R", "K", "LS", "C", "P"],
                        "present_factors": ["C"],
                        "missing_factors": ["R", "K", "LS", "P"],
                        "required_ok": False,
                        "feature_coverage_pct": {"C": 100.0},
                        "used_years": ["2018"],
                        "staging_warnings": [],
                    }, f, ensure_ascii=False)
                with open(os.path.join(ctx["paths"]["features"], "feature_table_meta.json"), "w", encoding="utf-8") as f:
                    json.dump({
                        "n_samples": 3,
                        "n_features": 1,
                        "preprocess_audit_path": audit_path,
                    }, f, ensure_ascii=False)
                state["feature_table"] = {
                    "path": ft_path,
                    "n_samples": 3,
                    "n_features": 1,
                    "preprocess_audit_path": audit_path,
                }
                gate = tools.run_error_corrector(state, stage="P0", run_id=ctx["run_id"])
                self.assertEqual(gate["status"], "ok")
                self.assertEqual(gate["verdict"], tools.BLOCK)
                self.assertIn("preprocess_factor_completeness", gate.get("block_items", []))
            finally:
                tools.RUNS_ROOT = old_runs

    def test_full_resource_preflight_written_for_full_raw_context(self):
        with tempfile.TemporaryDirectory() as td:
            old_runs = tools.RUNS_ROOT
            old_source = tools.DEFAULT_RUSLE_SOURCE_DIR
            tools.RUNS_ROOT = os.path.join(td, "runs")
            try:
                source_dir = os.path.join(td, "raw")
                os.makedirs(source_dir, exist_ok=True)
                bounds = (0, 0, 0.02, 0.02)
                arr = np.ones((8, 8), dtype=np.float32)
                for name in ["R_mean.tif", "K_300.tif", "LS_300.tif", "P_300.tif", "C2018_300.tif", "SE_Heilongjiang_2018-0000-0001.tif"]:
                    create_sample_tif(os.path.join(source_dir, name), arr, bounds=bounds)

                state = {
                    "uploads": {},
                    "feature_table": None,
                    "models": {},
                    "best_model": None,
                    "predictions": None,
                    "_diagnostics": {},
                    "_quality_report": None,
                }
                res = tools.prepare_run_context(state, run_mode="full", source_mode="rusle_raw", source_dir=source_dir, cleanup_history=False)
                self.assertEqual(res["status"], "ok")
                self.assertTrue(res.get("raw_source_index_path"))
                self.assertTrue(os.path.exists(res["raw_source_index_path"]))
                with open(res["raw_source_index_path"], "r", encoding="utf-8") as f:
                    raw_index = json.load(f)
                self.assertTrue(raw_index["source_read_only"])
                self.assertEqual(raw_index["static_factors"], ["K", "LS", "P", "R"])
                self.assertEqual(raw_index["label_tile_counts"]["2018"], 1)
                self.assertTrue(res.get("full_preflight_path"))
                self.assertTrue(os.path.exists(res["full_preflight_path"]))
                self.assertIn(res.get("full_preflight", {}).get("risk_level"), {"low", "medium", "high"})

                pf = tools.prepare_full_resource_preflight(state, source_dir=source_dir, target_resolution_km=5.0, run_id=res["run_id"])
                self.assertEqual(pf["status"], "ok")
                self.assertTrue(os.path.exists(pf["preflight_path"]))
            finally:
                tools.RUNS_ROOT = old_runs
                tools.DEFAULT_RUSLE_SOURCE_DIR = old_source

    def test_plan_full_execution_writes_year_windowed_plan(self):
        with tempfile.TemporaryDirectory() as td:
            old_runs = tools.RUNS_ROOT
            tools.RUNS_ROOT = os.path.join(td, "runs")
            try:
                source_dir = os.path.join(td, "raw")
                os.makedirs(source_dir, exist_ok=True)
                bounds = (0, 0, 0.02, 0.02)
                arr = np.ones((8, 8), dtype=np.float32)
                for name in ["R_mean.tif", "K_300.tif", "LS_300.tif", "P_300.tif"]:
                    create_sample_tif(os.path.join(source_dir, name), arr, bounds=bounds)
                for year in ["2018", "2020", "2022"]:
                    create_sample_tif(os.path.join(source_dir, f"C{year}_300.tif"), arr, bounds=bounds)
                    create_sample_tif(os.path.join(source_dir, f"SE_Heilongjiang_{year}-0000-0000.tif"), arr, bounds=bounds)
                    create_sample_tif(os.path.join(source_dir, f"SE_Heilongjiang_{year}-0000-0001.tif"), arr * 2, bounds=bounds)

                state = {
                    "uploads": {},
                    "feature_table": None,
                    "models": {},
                    "best_model": None,
                    "predictions": None,
                    "_diagnostics": {},
                    "_quality_report": None,
                }
                res = tools.plan_full_execution(
                    state,
                    source_dir=source_dir,
                    target_resolution_km=5.0,
                    year_window_size=2,
                    max_tile_pixels=1_000_000,
                )
                self.assertEqual(res["status"], "ok")
                self.assertEqual(res["batch_count"], 2)
                self.assertEqual(res["year_count"], 3)
                self.assertTrue(res["source_read_only"])
                self.assertIn("plan_full_execution", tools.TOOL_MAP)
                self.assertTrue(os.path.exists(res["plan_path"]))
                with open(res["plan_path"], "r", encoding="utf-8") as f:
                    plan = json.load(f)
                self.assertTrue(plan["source_read_only"])
                self.assertEqual(plan["batches"][0]["years"], ["2018", "2020"])
                self.assertEqual(plan["batches"][1]["years"], ["2022"])
                self.assertEqual(plan["batches"][0]["items"][0]["label_tile_count"], 2)
                self.assertIn("claim_boundary", plan)
            finally:
                tools.RUNS_ROOT = old_runs

    def test_run_full_batch_smoke_blocks_execute_when_over_limits(self):
        with tempfile.TemporaryDirectory() as td:
            old_runs = tools.RUNS_ROOT
            tools.RUNS_ROOT = os.path.join(td, "runs")
            try:
                state = {
                    "uploads": {},
                    "feature_table": None,
                    "models": {},
                    "best_model": None,
                    "predictions": None,
                    "_diagnostics": {},
                    "_quality_report": None,
                }
                ctx = tools.prepare_run_context(state, run_mode="full", source_mode="rusle_raw", cleanup_history=False)
                plan = {
                    "source_read_only": True,
                    "batches": [
                        {
                            "batch_id": "full_batch_001",
                            "years": ["2018"],
                            "estimated_source_size_gb": 3.5,
                            "max_pixels": 300_000_000,
                            "items": [],
                        }
                    ],
                }
                plan_path = os.path.join(state["run_context"]["paths"]["inputs"], "full_execution_plan.json")
                with open(plan_path, "w", encoding="utf-8") as f:
                    json.dump(plan, f)

                dry = tools.run_full_batch_smoke(
                    state,
                    plan_path=plan_path,
                    batch_id="full_batch_001",
                    execute=False,
                    max_source_size_gb=2.0,
                    max_pixels=250_000_000,
                )
                self.assertEqual(dry["status"], "ok")
                self.assertEqual(dry["verdict"], tools.PASS_WITH_RISKS)
                self.assertEqual(dry["execution_mode"], "dry_run")

                blocked = tools.run_full_batch_smoke(
                    state,
                    plan_path=plan_path,
                    batch_id="full_batch_001",
                    execute=True,
                    max_source_size_gb=2.0,
                    max_pixels=250_000_000,
                )
                self.assertEqual(blocked["status"], "ok")
                self.assertEqual(blocked["verdict"], tools.BLOCK)
                self.assertEqual(blocked["execution_mode"], "blocked_execute")
                self.assertTrue(blocked["blockers"])
                self.assertTrue(os.path.exists(blocked["report_path"]))
                self.assertIn("run_full_batch_smoke", tools.TOOL_MAP)
                self.assertEqual(blocked["run_id"], ctx["run_id"])
            finally:
                tools.RUNS_ROOT = old_runs

    def test_plan_full_spatial_tiles_and_tile_smoke(self):
        with tempfile.TemporaryDirectory() as td:
            old_runs = tools.RUNS_ROOT
            tools.RUNS_ROOT = os.path.join(td, "runs")
            try:
                state = {
                    "uploads": {},
                    "feature_table": None,
                    "models": {},
                    "best_model": None,
                    "predictions": None,
                    "_diagnostics": {},
                    "_quality_report": None,
                }
                tools.prepare_run_context(state, run_mode="full", source_mode="rusle_raw", cleanup_history=False)
                plan = {
                    "source_read_only": True,
                    "batches": [
                        {
                            "batch_id": "full_batch_001",
                            "years": ["2018"],
                            "estimated_source_size_gb": 4.0,
                            "max_pixels": 100_000_000,
                            "items": [
                                {
                                    "year": "2018",
                                    "c_factor": {"filename": "C2018.tif", "filepath": "C2018.tif", "width": 10000, "height": 10000, "pixels": 100_000_000},
                                    "label_tiles": [
                                        {"filename": "SE2018.tif", "filepath": "SE2018.tif", "width": 10000, "height": 10000, "pixels": 100_000_000}
                                    ],
                                }
                            ],
                        }
                    ],
                }
                plan_path = os.path.join(state["run_context"]["paths"]["inputs"], "full_execution_plan.json")
                with open(plan_path, "w", encoding="utf-8") as f:
                    json.dump(plan, f)

                tile_plan = tools.plan_full_spatial_tiles(
                    state,
                    plan_path=plan_path,
                    batch_id="full_batch_001",
                    tile_width=2500,
                    tile_height=2500,
                    max_tile_pixels=10_000_000,
                )
                self.assertEqual(tile_plan["status"], "ok")
                self.assertEqual(tile_plan["tile_count"], 16)
                self.assertTrue(os.path.exists(tile_plan["tile_plan_path"]))
                self.assertIn("plan_full_spatial_tiles", tools.TOOL_MAP)

                smoke = tools.run_full_tile_smoke(
                    state,
                    tile_plan_path=tile_plan["tile_plan_path"],
                    execute=False,
                    max_tile_source_size_gb=0.5,
                    max_tile_pixels=10_000_000,
                )
                self.assertEqual(smoke["status"], "ok")
                self.assertEqual(smoke["verdict"], tools.PASS_WITH_RISKS)
                self.assertEqual(smoke["execution_mode"], "dry_run")
                self.assertFalse(smoke["blockers"])
                self.assertTrue(os.path.exists(smoke["report_path"]))
                self.assertIn("run_full_tile_smoke", tools.TOOL_MAP)
            finally:
                tools.RUNS_ROOT = old_runs

    def test_run_full_tile_preprocess_builds_feature_table(self):
        with tempfile.TemporaryDirectory() as td:
            old_runs = tools.RUNS_ROOT
            tools.RUNS_ROOT = os.path.join(td, "runs")
            try:
                source_dir = os.path.join(td, "raw")
                os.makedirs(source_dir, exist_ok=True)
                bounds = (0, 0, 0.02, 0.02)
                arr = np.arange(64, dtype=np.float32).reshape(8, 8) + 1
                paths = {}
                for var in ["R", "K", "LS", "P", "C", "label"]:
                    p = os.path.join(source_dir, f"{var}.tif")
                    create_sample_tif(p, arr if var != "label" else arr * 0.1, bounds=bounds)
                    paths[var] = p
                state = {
                    "uploads": {},
                    "feature_table": None,
                    "models": {},
                    "best_model": None,
                    "predictions": None,
                    "_diagnostics": {},
                    "_quality_report": None,
                }
                tools.prepare_run_context(state, run_mode="full", source_mode="rusle_raw", cleanup_history=False)
                ctx = state["run_context"]
                meta = lambda fp: tools._raw_raster_meta(fp)
                plan = {
                    "source_read_only": True,
                    "preflight": {
                        "risk_level": "low",
                        "missing_static_factors": [],
                        "selected_full_years": ["2018"],
                    },
                    "static_factors": [
                        {"variable": var, "available": True, "meta": meta(paths[var])}
                        for var in ["R", "K", "LS", "P"]
                    ],
                    "batches": [
                        {
                            "batch_id": "full_batch_001",
                            "years": ["2018"],
                            "estimated_source_size_gb": 0.001,
                            "max_pixels": 64,
                            "items": [
                                {
                                    "year": "2018",
                                    "c_factor": meta(paths["C"]),
                                    "label_tile_count": 1,
                                    "label_tiles": [meta(paths["label"])],
                                }
                            ],
                        }
                    ],
                }
                plan_path = os.path.join(ctx["paths"]["inputs"], "full_execution_plan.json")
                with open(plan_path, "w", encoding="utf-8") as f:
                    json.dump(plan, f)
                tile_plan = {
                    "batch_id": "full_batch_001",
                    "reference_raster": meta(paths["C"]),
                    "tiles": [
                        {
                            "tile_id": "full_batch_001_tile_0001",
                            "row_off": 0,
                            "col_off": 0,
                            "height": 8,
                            "width": 8,
                            "estimated_pixels": 64,
                            "estimated_source_size_gb": 0.001,
                        }
                    ],
                }
                tile_plan_path = os.path.join(ctx["paths"]["inputs"], "full_batch_001_spatial_tiles.json")
                with open(tile_plan_path, "w", encoding="utf-8") as f:
                    json.dump(tile_plan, f)

                res = tools.run_full_tile_preprocess(
                    state,
                    plan_path=plan_path,
                    tile_plan_path=tile_plan_path,
                    tile_id="full_batch_001_tile_0001",
                    year="2018",
                    max_tile_pixels=1000,
                    max_records=20,
                )
                self.assertEqual(res["status"], "ok")
                self.assertGreater(res["n_samples"], 0)
                self.assertTrue(os.path.exists(res["feature_table_path"]))
                self.assertTrue(os.path.exists(res["preprocess_audit_path"]))
                self.assertTrue(os.path.exists(res["gate_path"]))
                self.assertTrue(res["gate_path"].endswith("full_batch_001_tile_0001_p0_gate.json"))
                with open(res["gate_path"], "r", encoding="utf-8") as f:
                    tile_gate = json.load(f)
                self.assertEqual(tile_gate["tile_id"], "full_batch_001_tile_0001")
                self.assertIn("stage_gate_path", res)
                self.assertIn(res["gate_verdict"], {tools.PASS, tools.PASS_WITH_RISKS})
                self.assertIn("run_full_tile_preprocess", tools.TOOL_MAP)
            finally:
                tools.RUNS_ROOT = old_runs

    def test_run_full_tile_coverage_probe_records_success_and_failure(self):
        with tempfile.TemporaryDirectory() as td:
            old_runs = tools.RUNS_ROOT
            tools.RUNS_ROOT = os.path.join(td, "runs")
            try:
                source_dir = os.path.join(td, "raw")
                os.makedirs(source_dir, exist_ok=True)
                bounds = (0, 0, 0.02, 0.02)
                arr = np.arange(64, dtype=np.float32).reshape(8, 8) + 1
                paths = {}
                for var in ["R", "K", "LS", "P", "C"]:
                    p = os.path.join(source_dir, f"{var}.tif")
                    create_sample_tif(p, arr, bounds=bounds)
                    paths[var] = p
                label_path = os.path.join(source_dir, "label.tif")
                create_sample_tif(label_path, arr * 0.1, bounds=bounds)
                paths["label"] = label_path

                state = {"uploads": {}, "feature_table": None, "models": {}, "best_model": None, "predictions": None}
                tools.prepare_run_context(state, run_mode="full", source_mode="rusle_raw", cleanup_history=False)
                ctx = state["run_context"]
                meta = lambda fp: tools._raw_raster_meta(fp)
                plan = {
                    "source_read_only": True,
                    "preflight": {"risk_level": "low", "missing_static_factors": [], "selected_full_years": ["2018"]},
                    "static_factors": [{"variable": var, "available": True, "meta": meta(paths[var])} for var in ["R", "K", "LS", "P"]],
                    "batches": [{
                        "batch_id": "full_batch_001",
                        "years": ["2018"],
                        "estimated_source_size_gb": 0.001,
                        "max_pixels": 64,
                        "items": [{
                            "year": "2018",
                            "c_factor": meta(paths["C"]),
                            "label_tile_count": 1,
                            "label_tiles": [meta(paths["label"])],
                        }],
                    }],
                }
                plan_path = os.path.join(ctx["paths"]["inputs"], "full_execution_plan.json")
                with open(plan_path, "w", encoding="utf-8") as f:
                    json.dump(plan, f)
                tile_plan = {
                    "batch_id": "full_batch_001",
                    "reference_raster": meta(paths["C"]),
                    "tile_count": 2,
                    "tiles": [
                        {"tile_id": "full_batch_001_tile_0001", "row_off": 0, "col_off": 0, "height": 8, "width": 8, "estimated_pixels": 64, "estimated_source_size_gb": 0.001},
                        {"tile_id": "full_batch_001_tile_0002", "row_off": 0, "col_off": 8, "height": 8, "width": 8, "estimated_pixels": 64, "estimated_source_size_gb": 0.001},
                    ],
                }
                tile_plan_path = os.path.join(ctx["paths"]["inputs"], "full_batch_001_spatial_tiles.json")
                with open(tile_plan_path, "w", encoding="utf-8") as f:
                    json.dump(tile_plan, f)

                res = tools.run_full_tile_coverage_probe(
                    state,
                    plan_path=plan_path,
                    tile_plan_path=tile_plan_path,
                    tile_ids=["full_batch_001_tile_0001", "full_batch_001_tile_0002"],
                    year="2018",
                    max_tile_pixels=1000,
                    max_records_per_tile=20,
                )
                self.assertEqual(res["status"], "ok")
                self.assertEqual(res["probed_tiles"], 2)
                self.assertEqual(res["successful_tiles"], 1)
                self.assertEqual(res["failed_tiles"], 1)
                self.assertTrue(os.path.exists(res["report_path"]))
                self.assertIn("run_full_tile_coverage_probe", tools.TOOL_MAP)
                with open(res["report_path"], "r", encoding="utf-8") as f:
                    report = json.load(f)
                self.assertEqual(report["results"][0]["status"], "ok")
                self.assertEqual(report["results"][1]["error_type"], "EmptyReferenceWindow")
                self.assertIn("claim_boundary", report)
            finally:
                tools.RUNS_ROOT = old_runs

    def test_quick_raw_source_uses_latest_year_and_skips_label_mosaic(self):
        with tempfile.TemporaryDirectory() as td:
            old_runs = tools.RUNS_ROOT
            tools.RUNS_ROOT = os.path.join(td, "runs")
            try:
                source_dir = os.path.join(td, "raw")
                os.makedirs(source_dir, exist_ok=True)
                bounds = (0, 0, 0.04, 0.04)
                arr = np.ones((8, 8), dtype=np.float32)
                for name in ["R_mean.tif", "K_300.tif", "LS_300.tif", "P_300.tif"]:
                    create_sample_tif(os.path.join(source_dir, name), arr, bounds=bounds)
                for year in ["2018", "2020"]:
                    create_sample_tif(os.path.join(source_dir, f"C{year}_300.tif"), arr, bounds=bounds)
                    create_sample_tif(os.path.join(source_dir, f"SE_Heilongjiang_{year}-0000-0000.tif"), arr, bounds=bounds)
                    create_sample_tif(os.path.join(source_dir, f"SE_Heilongjiang_{year}-0000-0001.tif"), arr * 2, bounds=bounds)

                state = {
                    "uploads": {},
                    "feature_table": None,
                    "models": {},
                    "best_model": None,
                    "predictions": None,
                    "_diagnostics": {},
                    "_quality_report": None,
                }
                ctx = tools.prepare_run_context(
                    state,
                    run_mode="quick",
                    source_mode="rusle_raw",
                    source_dir=source_dir,
                    cleanup_history=False,
                )
                self.assertEqual(ctx["status"], "ok")
                staged = tools._stage_rusle_raw_as_uploads(state, state["run_context"], target_resolution_km=5.0)
                self.assertEqual(staged["selected_years"], ["2020"])
                self.assertTrue(any("quick label subset" in w for w in staged["warnings"]))
                staged_names = set(os.listdir(state["run_context"]["paths"]["inputs"] + os.sep + "staged_uploads"))
                self.assertIn("label_2020.tif", staged_names)
                self.assertFalse(any("__raw_mosaic" in name for name in staged_names))
            finally:
                tools.RUNS_ROOT = old_runs

    def test_raw_source_staging_does_not_modify_source_directory(self):
        with tempfile.TemporaryDirectory() as td:
            old_runs = tools.RUNS_ROOT
            tools.RUNS_ROOT = os.path.join(td, "runs")
            try:
                source_dir = os.path.join(td, "raw")
                os.makedirs(source_dir, exist_ok=True)
                bounds = (0, 0, 0.04, 0.04)
                arr = np.ones((8, 8), dtype=np.float32)
                for name in ["R_mean.tif", "K_300.tif", "LS_300.tif", "P_300.tif", "C2018_300.tif"]:
                    create_sample_tif(os.path.join(source_dir, name), arr, bounds=bounds)
                create_sample_tif(os.path.join(source_dir, "SE_Heilongjiang_2018-0000-0000.tif"), arr, bounds=bounds)
                create_sample_tif(os.path.join(source_dir, "SE_Heilongjiang_2018-0000-0001.tif"), arr * 2, bounds=bounds)

                def snapshot_source():
                    out = {}
                    for name in sorted(os.listdir(source_dir)):
                        fp = os.path.join(source_dir, name)
                        st = os.stat(fp)
                        out[name] = (int(st.st_size), int(st.st_mtime_ns))
                    return out

                before = snapshot_source()
                state = {
                    "uploads": {},
                    "feature_table": None,
                    "models": {},
                    "best_model": None,
                    "predictions": None,
                    "_diagnostics": {},
                    "_quality_report": None,
                }
                ctx = tools.prepare_run_context(
                    state,
                    run_mode="full",
                    source_mode="rusle_raw",
                    source_dir=source_dir,
                    cleanup_history=False,
                )
                self.assertEqual(ctx["status"], "ok")
                staged = tools._stage_rusle_raw_as_uploads(state, state["run_context"], target_resolution_km=5.0)
                self.assertEqual(staged["selected_years"], ["2018"])
                self.assertEqual(before, snapshot_source())
                self.assertFalse(any("__raw_mosaic" in name for name in os.listdir(source_dir)))
                staged_names = os.listdir(os.path.join(state["run_context"]["paths"]["inputs"], "staged_uploads"))
                self.assertIn("label_2018.tif", staged_names)
                self.assertFalse(any("__raw_mosaic" in name for name in staged_names))
            finally:
                tools.RUNS_ROOT = old_runs

    def test_large_explanations_use_proxy_filenames(self):
        class DummyImportanceModel:
            feature_importances_ = np.array([0.4, 0.2, 0.15, 0.15, 0.1], dtype=float)

        with tempfile.TemporaryDirectory() as td:
            old_runs = tools.RUNS_ROOT
            tools.RUNS_ROOT = os.path.join(td, "runs")
            try:
                rng = np.random.default_rng(11)
                n = 5200
                df = pd.DataFrame({
                    "grid_id": np.arange(n),
                    "year": np.full(n, 2018),
                    "x": rng.normal(size=n),
                    "y": rng.normal(size=n),
                    "row": np.arange(n) // 100,
                    "col": np.arange(n) % 100,
                    "R": rng.uniform(100, 200, size=n),
                    "K": rng.uniform(0.1, 0.5, size=n),
                    "LS": rng.uniform(0.5, 2.5, size=n),
                    "C": rng.uniform(0.01, 0.5, size=n),
                    "P": rng.uniform(0.1, 1.0, size=n),
                    "label": rng.uniform(0.0, 10.0, size=n),
                })
                state = {
                    "uploads": {"dummy.tif": {"filepath": "dummy", "size": 1}},
                    "feature_table": None,
                    "models": {
                        "dummy": {
                            "model": DummyImportanceModel(),
                            "metrics": {
                                "mae": 1.0,
                                "rmse": 1.0,
                                "r2": 0.1,
                                "nrmse": 10.0,
                                "pbias": 0.0,
                                "train_seconds": 0.1,
                            },
                        }
                    },
                    "best_model": "dummy",
                    "predictions": None,
                    "_diagnostics": {},
                    "_quality_report": None,
                }
                tools.prepare_run_context(state, run_mode="quick", source_mode="uploads", cleanup_history=False)
                ft_path = os.path.join(state["run_context"]["paths"]["features"], "feature_table.parquet")
                df.to_parquet(ft_path, index=False)
                audit_path = os.path.join(state["run_context"]["paths"]["features"], "preprocess_audit.json")
                with open(audit_path, "w", encoding="utf-8") as f:
                    json.dump({
                        "source_mode": "uploads",
                        "required_rusle_factors": ["R", "K", "LS", "C", "P"],
                        "present_factors": ["R", "K", "LS", "C", "P"],
                        "missing_factors": [],
                        "required_ok": True,
                        "feature_coverage_pct": {"R": 100, "K": 100, "LS": 100, "C": 100, "P": 100},
                        "used_years": ["2018"],
                        "staging_warnings": [],
                    }, f, ensure_ascii=False)
                with open(os.path.join(state["run_context"]["paths"]["features"], "feature_table_meta.json"), "w", encoding="utf-8") as f:
                    json.dump({"n_samples": n, "n_features": 5, "preprocess_audit_path": audit_path}, f, ensure_ascii=False)
                state["feature_table"] = {"path": ft_path, "n_samples": n, "n_features": 5, "preprocess_audit_path": audit_path}

                res = tools.generate_explanations(state, output_dpi=80, run_id=state["run_context"]["run_id"])
                self.assertEqual(res["status"], "ok")
                self.assertFalse(res["shap_ready"])
                self.assertEqual(res["explanation_mode"], "proxy")
                self.assertTrue(all(os.path.basename(p).startswith("proxy_") for p in res["explanation_files"]))

                gate = tools.run_error_corrector(state, stage="P2", run_id=state["run_context"]["run_id"])
                self.assertEqual(gate["verdict"], tools.PASS_WITH_RISKS)
            finally:
                tools.RUNS_ROOT = old_runs

    def test_raw_quick_explanations_use_safe_proxy_even_for_small_runs(self):
        class DummyImportanceModel:
            feature_importances_ = np.array([0.4, 0.2, 0.15, 0.15, 0.1], dtype=float)

        with tempfile.TemporaryDirectory() as td:
            old_runs = tools.RUNS_ROOT
            tools.RUNS_ROOT = os.path.join(td, "runs")
            try:
                rng = np.random.default_rng(17)
                n = 80
                df = pd.DataFrame({
                    "grid_id": np.arange(n),
                    "year": np.full(n, 2020),
                    "x": rng.normal(size=n),
                    "y": rng.normal(size=n),
                    "row": np.arange(n) // 10,
                    "col": np.arange(n) % 10,
                    "R": rng.uniform(100, 200, size=n),
                    "K": rng.uniform(0.1, 0.5, size=n),
                    "LS": rng.uniform(0.5, 2.5, size=n),
                    "C": rng.uniform(0.01, 0.5, size=n),
                    "P": rng.uniform(0.1, 1.0, size=n),
                    "label": rng.uniform(0.0, 10.0, size=n),
                })
                state = {
                    "uploads": {"raw_source_index.json": {"filepath": "dummy", "size": 1}},
                    "feature_table": None,
                    "models": {
                        "dummy": {
                            "model": DummyImportanceModel(),
                            "metrics": {
                                "mae": 1.0,
                                "rmse": 1.0,
                                "r2": 0.1,
                                "nrmse": 10.0,
                                "pbias": 0.0,
                                "train_seconds": 0.1,
                            },
                        }
                    },
                    "best_model": "dummy",
                    "predictions": None,
                    "_diagnostics": {},
                    "_quality_report": None,
                }
                tools.prepare_run_context(state, run_mode="quick", source_mode="rusle_raw", cleanup_history=False)
                raw_index_path = os.path.join(state["run_context"]["paths"]["inputs"], "raw_source_index.json")
                with open(raw_index_path, "w", encoding="utf-8") as f:
                    json.dump({"source_mode": "rusle_raw"}, f, ensure_ascii=False)
                ft_path = os.path.join(state["run_context"]["paths"]["features"], "feature_table.parquet")
                df.to_parquet(ft_path, index=False)
                audit_path = os.path.join(state["run_context"]["paths"]["features"], "preprocess_audit.json")
                with open(audit_path, "w", encoding="utf-8") as f:
                    json.dump({
                        "source_mode": "rusle_raw",
                        "required_rusle_factors": ["R", "K", "LS", "C", "P"],
                        "present_factors": ["R", "K", "LS", "C", "P"],
                        "missing_factors": [],
                        "required_ok": True,
                        "feature_coverage_pct": {"R": 100, "K": 100, "LS": 100, "C": 100, "P": 100},
                        "used_years": ["2020"],
                        "staging_warnings": [],
                    }, f, ensure_ascii=False)
                with open(os.path.join(state["run_context"]["paths"]["features"], "feature_table_meta.json"), "w", encoding="utf-8") as f:
                    json.dump({"n_samples": n, "n_features": 5, "preprocess_audit_path": audit_path}, f, ensure_ascii=False)
                state["feature_table"] = {"path": ft_path, "n_samples": n, "n_features": 5, "preprocess_audit_path": audit_path}

                res = tools.generate_explanations(state, output_dpi=80, run_id=state["run_context"]["run_id"])
                self.assertEqual(res["status"], "ok")
                self.assertFalse(res["shap_ready"])
                self.assertEqual(res["explanation_mode"], "proxy")
                self.assertIn("quick raw-source", res["shap_risk_note"].lower())
                self.assertTrue(all(os.path.basename(p).startswith("proxy_") for p in res["explanation_files"]))

                gate = tools.run_error_corrector(state, stage="P2", run_id=state["run_context"]["run_id"])
                self.assertEqual(gate["verdict"], tools.PASS_WITH_RISKS)
            finally:
                tools.RUNS_ROOT = old_runs

    def test_small_explanations_use_real_shap_filenames_when_available(self):
        try:
            import shap  # noqa: F401
        except Exception:
            self.skipTest("shap is not installed")

        with tempfile.TemporaryDirectory() as td:
            old_runs = tools.RUNS_ROOT
            tools.RUNS_ROOT = os.path.join(td, "runs")
            try:
                rng = np.random.default_rng(13)
                n = 80
                df = pd.DataFrame({
                    "grid_id": np.arange(n),
                    "year": np.full(n, 2018),
                    "x": rng.normal(size=n),
                    "y": rng.normal(size=n),
                    "row": np.arange(n) // 10,
                    "col": np.arange(n) % 10,
                    "R": rng.uniform(100, 200, size=n),
                    "K": rng.uniform(0.1, 0.5, size=n),
                    "LS": rng.uniform(0.5, 2.5, size=n),
                    "C": rng.uniform(0.01, 0.5, size=n),
                    "P": rng.uniform(0.1, 1.0, size=n),
                })
                df["label"] = 0.01 * df["R"] + 5 * df["K"] + 0.4 * df["LS"] + rng.normal(0, 0.05, size=n)
                state = {
                    "uploads": {},
                    "feature_table": None,
                    "models": {},
                    "best_model": None,
                    "predictions": None,
                    "_diagnostics": {},
                    "_quality_report": None,
                }
                tools.prepare_run_context(state, run_mode="quick", source_mode="uploads", cleanup_history=False)
                ft_path = os.path.join(state["run_context"]["paths"]["features"], "feature_table.parquet")
                df.to_parquet(ft_path, index=False)
                state["feature_table"] = {"path": ft_path, "n_samples": n, "n_features": 5}

                train = tools.train_candidates(state, algorithms=["random_forest"], cv_folds=3, run_mode="quick", source_mode="uploads")
                self.assertEqual(train["status"], "ok")
                sel = tools.select_best(state)
                self.assertEqual(sel["status"], "ok")

                res = tools.generate_explanations(state, output_dpi=80, run_id=state["run_context"]["run_id"])
                self.assertEqual(res["status"], "ok")
                self.assertTrue(res["shap_ready"])
                self.assertEqual(res["explanation_mode"], "shap")
                self.assertTrue(any(os.path.basename(p).startswith("shap_") for p in res["explanation_files"]))
                self.assertFalse(any(os.path.basename(p).startswith("proxy_") for p in res["explanation_files"]))
            finally:
                tools.RUNS_ROOT = old_runs

    def test_quick_raw_prediction_replays_feature_grid(self):
        class DummyModel:
            def predict(self, X):
                return np.asarray(X, dtype=float).sum(axis=1)

        with tempfile.TemporaryDirectory() as td:
            old_runs = tools.RUNS_ROOT
            tools.RUNS_ROOT = os.path.join(td, "runs")
            try:
                state = {
                    "uploads": {},
                    "feature_table": None,
                    "models": {
                        "dummy": {
                            "model": DummyModel(),
                            "feature_names": ["R", "K"],
                            "metrics": {"mae": 1.0, "rmse": 1.0, "r2": 0.1, "nrmse": 10.0, "pbias": 0.0, "train_seconds": 0.1},
                        }
                    },
                    "best_model": "dummy",
                    "predictions": None,
                    "_diagnostics": {"ok": True},
                    "_quality_report": None,
                }
                tools.prepare_run_context(state, run_mode="quick", source_mode="rusle_raw", cleanup_history=False)
                ctx = state["run_context"]
                df = pd.DataFrame({
                    "grid_id": [0, 1, 2, 3],
                    "year": [2018, 2018, 2020, 2020],
                    "x": [0.0, 1.0, 0.0, 1.0],
                    "y": [0.0, 0.0, 1.0, 1.0],
                    "row": [0, 0, 0, 0],
                    "col": [0, 1, 0, 1],
                    "R": [1.0, 2.0, 3.0, 4.0],
                    "K": [10.0, 20.0, 30.0, 40.0],
                    "label": [1.0, 2.0, 3.0, 4.0],
                })
                ft_path = os.path.join(ctx["paths"]["features"], "feature_table.parquet")
                df.to_parquet(ft_path, index=False)
                state["feature_table"] = {"path": ft_path, "n_samples": 4, "n_features": 2}

                res = tools.predict_future(state, scenario="ssp245")
                self.assertEqual(res["status"], "ok")
                self.assertEqual(res["prediction_mode"], "historical_feature_replay")
                self.assertEqual(res["gate_verdict"], tools.PASS_WITH_RISKS)
                pred_path = os.path.join(ctx["paths"]["predictions"], "pred_ssp245.npy")
                uncert_path = os.path.join(ctx["paths"]["predictions"], "uncert_ssp245.npy")
                meta_path = os.path.join(ctx["paths"]["predictions"], "pred_ssp245_meta.json")
                self.assertEqual(state["predictions"]["pred_path"], pred_path)
                self.assertEqual(state["predictions"]["uncertainty_path"], uncert_path)
                self.assertEqual(state["predictions"]["pred_meta_path"], meta_path)
                self.assertTrue(os.path.exists(meta_path))
            finally:
                tools.RUNS_ROOT = old_runs

    def test_full_tile_prediction_replay_is_risk_labeled(self):
        class DummyModel:
            def predict(self, X):
                return np.asarray(X, dtype=float).sum(axis=1)

        with tempfile.TemporaryDirectory() as td:
            old_runs = tools.RUNS_ROOT
            tools.RUNS_ROOT = os.path.join(td, "runs")
            try:
                state = {
                    "uploads": {"tile_sample": {"filepath": os.path.join(td, "ft.parquet"), "source": "rusle_raw_bounded_tile_sample"}},
                    "feature_table": None,
                    "models": {
                        "dummy": {
                            "model": DummyModel(),
                            "feature_names": ["R", "K"],
                            "metrics": {"mae": 1.0, "rmse": 1.0, "r2": 0.1, "nrmse": 10.0, "pbias": 0.0, "train_seconds": 0.1},
                        }
                    },
                    "best_model": "dummy",
                    "predictions": None,
                    "_diagnostics": {"ok": True},
                    "_quality_report": None,
                }
                tools.prepare_run_context(state, run_mode="full", source_mode="rusle_raw", cleanup_history=False)
                ctx = state["run_context"]
                df = pd.DataFrame({
                    "grid_id": [0, 1, 2, 3],
                    "year": [1992, 1992, 1992, 1992],
                    "x": [0.0, 1.0, 0.0, 1.0],
                    "y": [0.0, 0.0, 1.0, 1.0],
                    "row": [0, 0, 1, 1],
                    "col": [0, 1, 0, 1],
                    "R": [1.0, 2.0, 3.0, 4.0],
                    "K": [10.0, 20.0, 30.0, 40.0],
                    "label": [1.0, 2.0, 3.0, 4.0],
                })
                ft_path = os.path.join(ctx["paths"]["features"], "feature_table_full_tile.parquet")
                df.to_parquet(ft_path, index=False)
                audit_path = os.path.join(ctx["paths"]["features"], "preprocess_audit.json")
                with open(audit_path, "w", encoding="utf-8") as f:
                    json.dump({
                        "source_mode": "rusle_raw",
                        "required_rusle_factors": ["R", "K"],
                        "present_factors": ["R", "K"],
                        "missing_factors": [],
                        "feature_coverage_pct": {"R": 100.0, "K": 100.0},
                        "used_years": ["1992"],
                        "staging_warnings": ["test full tile replay fixture"],
                        "required_ok": True,
                    }, f)
                state["feature_table"] = {
                    "path": ft_path,
                    "n_samples": 4,
                    "n_features": 2,
                    "run_mode": "full_tile_p1_sample",
                    "preprocess_audit_path": audit_path,
                }

                res = tools.predict_future(state, scenario="bounded")
                self.assertEqual(res["status"], "ok")
                self.assertEqual(res["prediction_mode"], "bounded_tile_feature_replay")
                self.assertEqual(res["gate_verdict"], tools.PASS_WITH_RISKS)
                self.assertTrue(os.path.exists(os.path.join(ctx["paths"]["predictions"], "pred_bounded_meta.json")))

                bundle = tools.export_evidence_bundle(state, run_id=ctx["run_id"])
                self.assertEqual(bundle["status"], "ok")
                self.assertEqual(state["run_context"].get("bundle_zip"), bundle["bundle_zip"])
                self.assertTrue(os.path.exists(state["run_context"]["bundle_zip"]))
                gate = tools.run_error_corrector(state, stage="P3", run_id=ctx["run_id"])
                self.assertEqual(gate["status"], "ok")
                self.assertIn(gate["verdict"], {tools.PASS, tools.PASS_WITH_RISKS})
                self.assertFalse(gate["block_items"])
                with open(gate["gate_path"], "r", encoding="utf-8") as f:
                    payload = json.load(f)
                check_names = [c["name"] for c in payload["checks"]]
                self.assertIn("bounded_tile_prediction_replay_mode", check_names)
            finally:
                tools.RUNS_ROOT = old_runs

    def test_export_results_writes_report_paths_to_run_context(self):
        old_runs = tools.RUNS_ROOT
        with tempfile.TemporaryDirectory() as td:
            tools.RUNS_ROOT = os.path.join(td, "runs")
            try:
                state = {
                    "uploads": {},
                    "feature_table": {"path": os.path.join(td, "missing.parquet"), "n_samples": 2, "n_features": 2},
                    "models": {
                        "dummy": {
                            "metrics": {"mae": 1.0, "rmse": 2.0, "r2": 0.5, "nrmse": 10.0, "pbias": 0.0, "train_seconds": 0.1}
                        }
                    },
                    "best_model": "dummy",
                    "predictions": {"scenario": "ssp245", "mean_erosion": 1.2, "max_erosion": 2.4, "high_risk_ratio": 0.0},
                    "_diagnostics": {},
                }
                tools.prepare_run_context(state, run_mode="quick", source_mode="uploads", cleanup_history=False)
                res = tools.export_results(state)
                self.assertEqual(res["status"], "ok")
                self.assertEqual(state["run_context"].get("report_path"), res["run_report_path"])
                self.assertTrue(os.path.exists(state["run_context"]["report_path"]))
            finally:
                tools.RUNS_ROOT = old_runs

    def test_export_evidence_bundle_index_redacts_absolute_paths(self):
        old_runs = tools.RUNS_ROOT
        with tempfile.TemporaryDirectory(dir=os.getcwd()) as td:
            tools.RUNS_ROOT = os.path.join(td, "runs")
            try:
                state = {"uploads": {}, "models": {}, "_diagnostics": {}}
                tools.prepare_run_context(state, run_mode="quick", source_mode="uploads", cleanup_history=False)
                ctx = state["run_context"]
                outside_path = os.path.join(td, "outside_secret", "raw.tif")
                os.makedirs(os.path.dirname(outside_path), exist_ok=True)
                with open(outside_path, "w", encoding="utf-8") as f:
                    f.write("secret")
                state["run_context"]["evidence_paths"].append(outside_path)

                bundle = tools.export_evidence_bundle(state, run_id=ctx["run_id"])

                self.assertEqual(bundle["status"], "ok")
                with open(bundle["bundle_index"], "r", encoding="utf-8") as f:
                    index_payload = json.load(f)
                serialized = json.dumps(index_payload, ensure_ascii=False)
                self.assertNotIn(td, serialized)
                self.assertNotIn(outside_path, serialized)
                self.assertIn("bundle/bundle_index.json", index_payload["evidence_paths"])
                self.assertIn("[outside-data-root-redacted]", index_payload["evidence_paths"])
                self.assertEqual(index_payload["classification"], "research_sensitive")
            finally:
                tools.RUNS_ROOT = old_runs

    def test_full_multi_tile_prediction_replay_mode(self):
        class DummyModel:
            def predict(self, X):
                return np.asarray(X, dtype=float).sum(axis=1)

        with tempfile.TemporaryDirectory() as td:
            old_runs = tools.RUNS_ROOT
            tools.RUNS_ROOT = os.path.join(td, "runs")
            try:
                state = {
                    "uploads": {},
                    "feature_table": None,
                    "models": {
                        "dummy": {
                            "model": DummyModel(),
                            "feature_names": ["R", "K"],
                            "metrics": {"mae": 1.0, "rmse": 1.0, "r2": 0.1, "nrmse": 10.0, "pbias": 0.0, "train_seconds": 0.1},
                        }
                    },
                    "best_model": "dummy",
                }
                tools.prepare_run_context(state, run_mode="full", source_mode="rusle_raw", cleanup_history=False)
                ctx = state["run_context"]
                df = pd.DataFrame({
                    "grid_id": [0, 1, 2, 3],
                    "year": [1992, 1992, 1992, 1992],
                    "tile_id": ["a", "a", "b", "b"],
                    "row": [0, 0, 1, 1],
                    "col": [0, 1, 0, 1],
                    "R": [1.0, 2.0, 3.0, 4.0],
                    "K": [10.0, 20.0, 30.0, 40.0],
                    "label": [1.0, 2.0, 3.0, 4.0],
                })
                ft_path = os.path.join(ctx["paths"]["features"], "feature_table_multi_tile.parquet")
                df.to_parquet(ft_path, index=False)
                state["feature_table"] = {
                    "path": ft_path,
                    "n_samples": 4,
                    "n_features": 2,
                    "run_mode": "full_multi_tile_p1_sample",
                }
                res = tools.predict_future(state, scenario="bounded_multi")
                self.assertEqual(res["status"], "ok")
                self.assertEqual(res["prediction_mode"], "bounded_multi_tile_feature_replay")
                self.assertEqual(res["gate_verdict"], tools.PASS_WITH_RISKS)
            finally:
                tools.RUNS_ROOT = old_runs

    def test_platform_heartbeat_throttles_to_12h(self):
        import app

        log_path = os.path.join(os.path.dirname(app.__file__), "Workflow-Logs", "platform_open_heartbeat.jsonl")
        if os.path.exists(log_path):
            os.remove(log_path)

        app.init_session_state()
        app.record_platform_open_heartbeat(interval_hours=12)
        self.assertTrue(os.path.exists(log_path))
        first_size = os.path.getsize(log_path)
        app.record_platform_open_heartbeat(interval_hours=12)
        second_size = os.path.getsize(log_path)
        self.assertEqual(first_size, second_size)


if __name__ == "__main__":
    unittest.main()
