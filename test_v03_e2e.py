"""
v0.3 End-to-End Test: train → optimize → predict → report
Uses existing mock data in data/uploads/
"""
import os
import sys
import json
import warnings

# Ensure project root in path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
warnings.filterwarnings("ignore")

from tools import (
    inspect_uploads, assess_data_quality, build_feature_table,
    train_candidates, optimize_hyperparams, select_best,
    predict_future, visualize, export_results, execute_tool,
)

UPLOAD_DIR = os.path.join(os.path.dirname(__file__), "data", "uploads")


def build_mock_state():
    """Build a state dict from the mock data files."""
    uploads = {}
    if os.path.exists(UPLOAD_DIR):
        for fname in os.listdir(UPLOAD_DIR):
            if fname.lower().endswith(('.tif', '.tiff')):
                filepath = os.path.join(UPLOAD_DIR, fname)
                uploads[fname] = {
                    "filepath": filepath,
                    "size": os.path.getsize(filepath),
                }
    return {
        "uploads": uploads,
        "feature_table": None,
        "models": {},
        "best_model": None,
        "predictions": None,
        "_diagnostics": {},
        "_quality_report": None,
    }


def test_step(step_name, tool_name, state, tool_kwargs=None):
    """Execute a tool step and check the result."""
    kwargs = tool_kwargs or {}
    print(f"\n{'='*60}")
    print(f"Step: {step_name} ({tool_name})")
    print(f"{'='*60}")
    result = execute_tool(tool_name, kwargs, state)
    status = result.get("status", "unknown")
    msg = result.get("message", "")
    print(f"  Status: {status}")
    print(f"  Message: {msg[:200]}")
    if status == "error":
        print(f"  ERROR: {result.get('error_type', '')}: {result.get('message', '')}")
    return result


def main():
    state = build_mock_state()
    print(f"Mock data: {len(state['uploads'])} files in {UPLOAD_DIR}")

    # Step 1: Inspect uploads
    r1 = test_step("1. Inspect Uploads", "inspect_uploads", state)
    assert r1["status"] == "ok", f"inspect failed: {r1.get('message')}"
    print(f"  Files: {r1['total_files']}, Can train: {r1['can_train']}")

    # Step 2: Assess quality
    r2 = test_step("2. Assess Quality", "assess_data_quality", state)
    assert r2["status"] == "ok", f"quality failed: {r2.get('message')}"
    print(f"  Quality: {r2.get('quality_label', '?')}")

    # Step 3: Build feature table
    r3 = test_step("3. Build Feature Table", "build_feature_table", state)
    assert r3["status"] == "ok", f"feature table failed: {r3.get('message')}"
    print(f"  Samples: {r3['n_samples']}, Features: {r3['n_features']}")

    # Step 4: Train candidates (Stage A - fixed default params)
    r4 = test_step("4. Train Candidates", "train_candidates", state)
    assert r4["status"] == "ok", f"train failed: {r4.get('message')}"
    print(f"  Best: {r4['best_algorithm']}, RMSE: {r4['best_rmse']}, R2: {r4['best_r2']}")
    for m in r4.get("metrics", []):
        print(f"    {m['algorithm']}: MAE={m['mae']:.4f}, RMSE={m['rmse']:.4f}, R2={m['r2']:.4f}")

    # Step 5: Select best
    r5 = test_step("5. Select Best", "select_best", state)
    assert r5["status"] == "ok", f"select best failed: {r5.get('message')}"
    print(f"  Best: {r5['best_algorithm']}")

    # Step 6: Optimize hyperparams (Stage B - new tool!)
    print("\n" + "="*60)
    print("Step 6: Optimize Hyperparams (v0.3 NEW)")
    print("="*60)
    # Use small n_trials for quick test
    r6 = optimize_hyperparams(
        state,
        algorithms=["lightgbm", "xgboost"],
        n_trials=5,
        n_folds=3,
        progress_callback=lambda msg, pct: print(f"  [Optimize] {msg}"),
    )
    print(f"  Status: {r6['status']}")
    print(f"  Message: {r6.get('message', '')[:200]}")
    assert r6["status"] == "ok", f"optimize failed: {r6.get('message')}"
    print(f"  Best: {r6['best_algorithm']}, RMSE: {r6['best_rmse']}, R2: {r6['best_r2']}")
    for m in r6.get("metrics", []):
        print(f"    {m['algorithm']}: MAE={m['mae']:.4f}, RMSE={m['rmse']:.4f}, R2={m['r2']:.4f}")
    for algo, params in r6.get("best_params", {}).items():
        print(f"    {algo} best_params: {json.dumps(params, default=str)[:120]}")
    for algo, hist in r6.get("study_history", {}).items():
        print(f"    {algo} study_history length: {len(hist)}")

    # Step 7: Re-select best after optimization
    r7 = test_step("7. Select Best (post-optimization)", "select_best", state)
    assert r7["status"] == "ok", f"select best post-opt failed: {r7.get('message')}"
    print(f"  Best after optimization: {r7['best_algorithm']}")

    # Step 8: Predict future
    r8 = test_step("8. Predict Future", "predict_future", state,
                    tool_kwargs={"scenario": "ssp245"})
    assert r8["status"] == "ok", f"predict failed: {r8.get('message')}"
    print(f"  Mean erosion: {r8['mean_erosion']}, Max: {r8['max_erosion']}")

    # Step 9: Visualize map
    r9 = test_step("9. Visualize Map", "visualize", state,
                    tool_kwargs={"target": "map"})
    assert r9["status"] == "ok", f"map viz failed: {r9.get('message')}"

    # Step 10: Visualize metrics
    r10 = test_step("10. Visualize Metrics", "visualize", state,
                     tool_kwargs={"target": "metrics"})
    assert r10["status"] == "ok", f"metrics viz failed: {r10.get('message')}"

    # Step 11: Export report
    r11 = test_step("11. Export Report", "export_results", state)
    assert r11["status"] == "ok", f"report failed: {r11.get('message')}"
    print(f"  Report path: {r11.get('report_path', 'N/A')}")

    # Summary
    print("\n" + "="*60)
    print("ALL TESTS PASSED! v0.3 E2E flow verified.")
    print(f"  Models: {list(state.get('models', {}).keys())}")
    print(f"  Best model: {state.get('best_model')}")
    print(f"  Predictions: scenario={state.get('predictions', {}).get('scenario')}")
    print("="*60)


if __name__ == "__main__":
    main()
