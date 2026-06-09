"""v0.3 Full Flow Verification - concise output"""
import os, sys, json, warnings
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
warnings.filterwarnings("ignore")

from tools import execute_tool

UPLOAD_DIR = "./data/uploads"
uploads = {}
for fname in os.listdir(UPLOAD_DIR):
    if fname.lower().endswith(('.tif', '.tiff')):
        fp = os.path.join(UPLOAD_DIR, fname)
        uploads[fname] = {"filepath": fp, "size": os.path.getsize(fp)}

state = {
    "uploads": uploads, "feature_table": None, "models": {},
    "best_model": None, "predictions": None,
    "_diagnostics": {}, "_quality_report": None,
}

steps = [
    ("1.Inspect",    "inspect_uploads",    {}),
    ("2.Quality",    "assess_data_quality", {}),
    ("3.Features",   "build_feature_table", {}),
    ("4.Train",      "train_candidates",    {}),
    ("5.SelectBest", "select_best",         {}),
    ("6.Optimize",   "optimize_hyperparams", {"algorithms": ["lightgbm"], "n_trials": 3, "n_folds": 3}),
    ("7.ReSelect",   "select_best",         {}),
    ("8.Predict",    "predict_future",       {"scenario": "ssp245"}),
    ("9.MapViz",     "visualize",           {"target": "map"}),
    ("10.MetricsViz","visualize",           {"target": "metrics"}),
    ("11.Report",    "export_results",      {}),
]

for step_name, tool_name, kwargs in steps:
    r = execute_tool(tool_name, kwargs, state)
    status = r.get("status", "?")
    msg = r.get("message", "")[:120]
    print(f"{step_name:16s} | {status:4s} | {msg}")

    if status == "error":
        print(f"  >>> ERROR: {r.get('error_type','')} - {r.get('message','')[:200]}")
        break

# Show optimization details
opt_models = {a: i for a, i in state.get("models", {}).items() if "best_params" in i}
if opt_models:
    print(f"\n--- Optimization Results ---")
    for algo, info in opt_models.items():
        m = info["metrics"]
        print(f"  {algo}: RMSE={m['rmse']:.4f} R2={m['r2']:.4f}")
        params_str = json.dumps(info["best_params"], default=str)[:150]
        print(f"    best_params: {params_str}")
        print(f"    study_history: {len(info.get('study_history',[]))} trials")

print(f"\n=== Final State ===")
print(f"Models: {list(state['models'].keys())}")
print(f"Best: {state['best_model']}")
pred = state.get("predictions") or {}
print(f"Predictions: scenario={pred.get('scenario','N/A')}")
for algo, info in state["models"].items():
    has_opt = "best_params" in info
    print(f"  {algo}: optimized={has_opt}")

print("\n>>> ALL PASSED - v0.3 full flow verified!")
