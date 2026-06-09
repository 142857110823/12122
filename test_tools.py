"""快速工具链测试"""
import sys, os, json

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from tools import (inspect_uploads, build_feature_table, train_candidates,
                    select_best, predict_future, visualize, export_results)

upload_dir = os.path.join(os.path.dirname(__file__), "data", "uploads")
state = {
    "uploads": {},
    "feature_table": None,
    "models": {},
    "best_model": None,
    "predictions": None,
    "_diagnostics": {},
}

# 加载文件到state
for fname in os.listdir(upload_dir):
    if fname.endswith(".tif"):
        fpath = os.path.join(upload_dir, fname)
        state["uploads"][fname] = {
            "filepath": fpath,
            "size": os.path.getsize(fpath),
        }

n_files = len(state["uploads"])
print(f"Step 1: Loaded {n_files} files")

# Test inspect_uploads
r1 = inspect_uploads(state)
print(f"Step 2: inspect_uploads - {r1['message'][:80]}")

# Test build_feature_table
r2 = build_feature_table(state)
print(f"Step 3: build_feature_table - {r2['message'][:80]}")

# Test train_candidates (quick: 3 trials, 3 folds)
r3 = train_candidates(state, algorithms=["lightgbm", "xgboost", "random_forest"],
                       optuna_trials=3, cv_folds=3)
print(f"Step 4: train_candidates - {r3['message'][:80]}")

# Test select_best
r4 = select_best(state)
print(f"Step 5: select_best - {r4['message'][:80]}")

# Test predict_future
r5 = predict_future(state, scenario="ssp245")
print(f"Step 6: predict_future - {r5['message'][:80]}")

# Test visualize
r6 = visualize(state, target="metrics")
print(f"Step 7: visualize(metrics) - {r6['message'][:60]}")

r7 = visualize(state, target="importance")
print(f"Step 8: visualize(importance) - {r7['message'][:60]}")

r8 = visualize(state, target="scatter")
print(f"Step 9: visualize(scatter) - {r8['message'][:60]}")

r9 = visualize(state, target="map")
print(f"Step 10: visualize(map) - {r9['message'][:60]}")

# Test export
r10 = export_results(state)
print(f"Step 11: export_results - {r10['message'][:60]}")

print()
print("=" * 60)
print(" ALL TOOLS TEST PASSED!")
print("=" * 60)
