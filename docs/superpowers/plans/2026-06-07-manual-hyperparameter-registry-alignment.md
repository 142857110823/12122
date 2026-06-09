# Manual Hyperparameter Registry Alignment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让平台支持每个机器学习模型的手动超参数设置，并保证默认训练、贝叶斯优化、优化后重训、UI、工具 schema、依赖状态和测试覆盖全部一致。

**Architecture:** 以 `tools.MODEL_REGISTRY` 作为唯一参数源；UI 只负责从注册表渲染和收集参数覆盖；训练/优化/重训统一通过 `_build_estimator_from_registry()` 构建模型，并把实际使用参数写回 state/evidence。CatBoost 默认作为可选依赖处理，不把未安装模型展示成完整可运行能力。

**Tech Stack:** Streamlit, scikit-learn, LightGBM, XGBoost, Optuna, pandas, unittest, joblib.

---

## 开展方向

1. **后端先行**：先让 `train_candidates()` 能接收并真实使用手动参数覆盖，避免出现“UI 可填但训练不用”的空壳交互。
2. **注册表唯一源**：默认参数、参数类型、优化边界、可编辑参数全部从 `MODEL_REGISTRY` 派生。
3. **优化链路闭环**：阶段二优化结果必须能在 `tools.py` 内写回 `state["_optimization_result"]`，阶段三可直接读取并重训，不依赖 Streamlit 外层补桥。
4. **死参数清理**：凡是出现在 `bayes_opt_bounds/default_params` 中的参数，必须被 estimator 构造器消费；不能消费的参数要从注册表移除或转成 UI-only 注释。
5. **依赖状态显式化**：CatBoost 当前未安装，本轮默认不安装新依赖，而是在 UI/schema/后端跳过逻辑中明确标记不可用。
6. **测试兜底**：补参数覆盖、优化结果直连重训、schema 合约、CatBoost 缺依赖跳过、UI 控件存在性测试。

## 划定边界

- 只保留 `app.py` 作为唯一 Streamlit 前端入口；不新增 HTML/Vue/React 前端。
- 不改动 `.env`，不新增在线 API key 流程，不把本地 LLM 改造成在线服务。
- 不手动修改 `data/features`、`data/models`、`data/predictions`、`data/runs` 中既有科学产物；测试生成的新产物按测试行为处理。
- 本轮不默认安装 `catboost`。如果后续明确要求 CatBoost 全量支持，再单独评估 Python 3.13 兼容性和安装验证。
- 本轮不把本地助手升级为自主 tool-calling agent；只修 schema 与后端公开工具契约。若要让助手自动调用工具，另开 `agent.py` 工具调用计划。
- 保持未填写手动参数时的用户流程不变：默认训练、贝叶斯优化、优化后重训仍可按现有按钮顺序执行。

## 子智能体盘查审核

本方案制定阶段已调用 3 个 explorer 子智能体做只读盘查：

- UI/动作子智能体：确认建模页没有手动超参数入口；确认建模页核心按钮不是空壳；指出 `model_focus_selection` 当前是 UI-only 控件。
- 后端模型子智能体：确认 `train_candidates()` 未用 `MODEL_REGISTRY`；指出阶段二结果不在 `tools.py` 内写回 state；指出 SVR `degree`、LightGBM `bagging_freq`、CatBoost `border_count` 等参数存在“注册但未消费”风险。
- schema/测试/依赖子智能体：确认 `agent.py` 加载 schema 但不实际 tool-call；确认 CatBoost 未安装；指出 schema 测试过浅、部分历史测试是脚本式发现测试。

执行阶段还需要再次调用子智能体：

- 实现前：1 个 explorer 复核任务拆分和文件边界。
- 实现后：3 个 explorer 分别复核 UI、后端、schema/tests，要求只读审查并返回文件行号。
- 合并前：运行本计划列出的验证命令，并用子智能体审查结果逐项关单。

## 文件结构

需要修改：

- `tools.py`
  - 参数清洗/覆盖工具函数。
  - `_build_estimator_from_registry()` 参数消费补齐。
  - `_build_optuna_search_space()` 条件参数支持。
  - `train_candidates()` 改为注册表驱动。
  - `run_stage_two_optimization()` 写回 state、跳过不可用模型。
  - `run_stage_three_retrain()` 支持直接传入结果、逐算法隔离失败。
- `app.py`
  - 建模页新增手动超参数控件。
  - `handle_action()` 将手动参数传给训练/优化/重训。
  - `model_focus_selection` 用于展开/高亮对应模型参数区域，避免 UI-only。
- `prompts/tool_descriptions.json`
  - 新增 `run_stage_two_optimization` 和 `run_stage_three_retrain` schema。
  - 为 `algorithms` 增加支持算法枚举。
  - 为 gate stage 增加 `P0/P1/P2/P3` 枚举。
  - 明确 `optimize_hyperparams` 为 legacy，或描述其兼容边界。
- `test_p0_p3_upgrade.py`
  - 后端参数覆盖、重训直连、不可用模型跳过、schema 合约测试。
- `test_ui_design_assets.py`
  - UI 资产/文本/控件 key 覆盖手动超参数区域。

不建议本轮修改：

- `agent.py`
  - 除非只移除误导性 schema 使用或文案。本轮不实现完整 LLM 工具调用。
- `requirements.txt`
  - 不加入 `catboost`，除非任务目标改成 CatBoost 必须可训练。

## Task 1: 后端参数覆盖与注册表统一

**Files:**
- Modify: `D:\空\water_erosion_mvp\tools.py`
- Test: `D:\空\water_erosion_mvp\test_p0_p3_upgrade.py`

- [ ] **Step 1: 写失败测试，证明手动参数必须进入 estimator**

在 `test_p0_p3_upgrade.py` 增加：

```python
def test_train_candidates_uses_manual_param_overrides(self):
    with tempfile.TemporaryDirectory() as td:
        fp = os.path.join(td, "ft.parquet")
        rng = np.random.default_rng(7)
        n = 90
        df = pd.DataFrame({
            "R": rng.normal(size=n),
            "K": rng.normal(size=n),
            "LS": rng.normal(size=n),
            "C": rng.normal(size=n),
            "P": rng.normal(size=n),
            "label": rng.normal(size=n),
        })
        df.to_parquet(fp)
        state = {
            "feature_table": {"path": fp},
            "models": {},
            "best_model": None,
            "uploads": {},
            "_diagnostics": {},
        }

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
```

Run:

```powershell
D:\codex\envs\water_erosion_mvp_py313\Scripts\python.exe -m unittest test_p0_p3_upgrade.TestP0P3Upgrade.test_train_candidates_uses_manual_param_overrides
```

Expected before implementation: `TypeError` because `train_candidates()` does not accept `param_overrides`.

- [ ] **Step 2: 新增参数规范化函数**

在 `tools.py` 的 `MODEL_REGISTRY` 后增加：

```python
def _normalize_param_overrides(param_overrides: Optional[dict], algorithms: list[str]) -> dict:
    if not param_overrides:
        return {}
    allowed_algos = set(algorithms or [])
    normalized = {}
    for algo, values in (param_overrides or {}).items():
        algo = str(algo).lower()
        if algo not in allowed_algos or algo not in MODEL_REGISTRY or not isinstance(values, dict):
            continue
        cfg = MODEL_REGISTRY[algo]
        allowed_params = set(cfg.get("default_params", {})) | set(cfg.get("bayes_opt_bounds", {}))
        ptypes = cfg.get("param_types", {})
        clean = {}
        for name, value in values.items():
            if name not in allowed_params or value is None:
                continue
            ptype = ptypes.get(name)
            if ptype == "int":
                clean[name] = int(value)
            elif ptype == "float":
                clean[name] = float(value)
            elif ptype == "categorical":
                clean[name] = value
            else:
                clean[name] = value
        if clean:
            normalized[algo] = clean
    return normalized
```

- [ ] **Step 3: 修改 `train_candidates()` 签名和构造器**

将签名改为：

```python
def train_candidates(state: dict, algorithms: list = None,
                     optuna_trials: int = 30, cv_folds: int = 5,
                     run_mode: str = "quick",
                     source_mode: str = "uploads",
                     output_dpi: int = DEFAULT_OUTPUT_DPI,
                     run_id: Optional[str] = None,
                     param_overrides: Optional[dict] = None,
                     progress_callback=None) -> dict:
```

删除局部 `_build_estimator()`，在训练前加入：

```python
param_overrides = _normalize_param_overrides(param_overrides, algorithms)
```

在模型循环内使用：

```python
actual_params = dict(MODEL_REGISTRY.get(algo, {}).get("default_params", {}))
actual_params.update(param_overrides.get(algo, {}))
estimator = _build_estimator_from_registry(algo, actual_params)
```

在 `models_dict[algo]` 中新增：

```python
"params": actual_params,
```

- [ ] **Step 4: 运行测试**

Run:

```powershell
D:\codex\envs\water_erosion_mvp_py313\Scripts\python.exe -m unittest test_p0_p3_upgrade.TestP0P3Upgrade.test_train_candidates_uses_manual_param_overrides
```

Expected: PASS.

## Task 2: 补齐注册参数消费与条件搜索空间

**Files:**
- Modify: `D:\空\water_erosion_mvp\tools.py`
- Test: `D:\空\water_erosion_mvp\test_p0_p3_upgrade.py`

- [ ] **Step 1: 写参数消费测试**

新增：

```python
def test_registry_search_params_are_consumed_by_estimators(self):
    checks = {
        "svr": {"kernel": "poly", "degree": 4},
        "lightgbm": {"bagging_freq": 2},
        "catboost": {"border_count": 128},
    }
    for algo, params in checks.items():
        if algo == "catboost":
            try:
                est = tools._build_estimator_from_registry(algo, params)
            except ImportError:
                continue
        else:
            est = tools._build_estimator_from_registry(algo, params)
        est_params = est.get_params()
        for key, value in params.items():
            self.assertEqual(est_params.get(key), value)
```

Expected before implementation: SVR `degree` and LightGBM `bagging_freq` fail; CatBoost may skip if missing.

- [ ] **Step 2: 修改 estimator 参数映射**

在 `_build_estimator_from_registry()` 中：

- LightGBM 增加 `subsample_freq=int(merged.get("bagging_freq", 0))`。
- SVR 增加 `degree=int(merged.get("degree", 3))`。
- CatBoost 增加 `border_count=int(merged.get("border_count", 254))`。

- [ ] **Step 3: 支持条件参数**

在 `_build_optuna_search_space()` 中处理 `conditional_params`。SVR 的 `degree` 只在 `kernel == "poly"` 时搜索；否则使用默认值但不作为 Optuna trial 参数写入。

- [ ] **Step 4: 运行测试**

Run:

```powershell
D:\codex\envs\water_erosion_mvp_py313\Scripts\python.exe -m unittest test_p0_p3_upgrade.TestP0P3Upgrade.test_registry_search_params_are_consumed_by_estimators
```

Expected: PASS.

## Task 3: 优化结果写回与优化后重训直连

**Files:**
- Modify: `D:\空\water_erosion_mvp\tools.py`
- Test: `D:\空\water_erosion_mvp\test_p0_p3_upgrade.py`

- [ ] **Step 1: 写直连重训测试**

新增测试：直接调用 `run_stage_two_optimization(state, algorithms=["random_forest"], n_trials=1)` 后，不经过 `app.py`，直接调用 `run_stage_three_retrain(state)`。

断言：

```python
self.assertEqual(opt["status"], "ok")
self.assertIn("_optimization_result", state)
self.assertIn("random_forest", state["_optimization_result"]["optimization_results"])
self.assertEqual(retrain["status"], "ok")
self.assertTrue(state["models"]["random_forest"]["optimized"])
self.assertIn("params", state["models"]["random_forest"])
```

- [ ] **Step 2: 阶段二写回 state**

`run_stage_two_optimization()` 返回前加入：

```python
result = {
    "status": "ok",
    "optimization_results": opt_results,
    "skipped_algorithms": skipped,
    "message": f"Optimized {len(opt_results)} algorithm(s).",
}
state["_optimization_result"] = {**(state.get("_optimization_result") or {}), **result}
return result
```

- [ ] **Step 3: 阶段二跳过不可用模型**

在每个算法 Optuna 前先尝试 `_build_estimator_from_registry(algo)`；失败时写入：

```python
skipped.append({"algorithm": algo, "reason": str(exc)})
continue
```

不要让不可用模型产生 `best_r2=-1e10` 的伪优化结果。

- [ ] **Step 4: 阶段三支持直接传入结果和逐算法隔离**

将签名扩展为：

```python
def run_stage_three_retrain(state: dict,
                            algorithms: list = None,
                            optimization_results: Optional[dict] = None,
                            base_param_overrides: Optional[dict] = None,
                            progress_callback=None) -> dict:
```

读取顺序：

```python
optimization_results = optimization_results or (state.get("_optimization_result") or {}).get("optimization_results") or {}
```

每个算法独立 `try/except`，失败写入 `skipped_algorithms`，不让单个 CatBoost 缺依赖拖垮全部重训。

## Task 4: 建模页手动超参数控件

**Files:**
- Modify: `D:\空\water_erosion_mvp\app.py`
- Test: `D:\空\water_erosion_mvp\test_ui_design_assets.py`

- [ ] **Step 1: 写 UI 静态测试**

在 `test_ui_design_assets.py` 增加断言：

```python
def test_modeling_lab_exposes_manual_hyperparameter_controls(self):
    with open(os.path.join(os.path.dirname(__file__), "app.py"), "r", encoding="utf-8") as f:
        app_text = f.read()
    self.assertIn("model_param_overrides", app_text)
    self.assertIn("_render_model_hyperparameter_controls", app_text)
    self.assertIn("手动超参数", app_text)
```

- [ ] **Step 2: 新增控件读取函数**

在 `app.py` 中 `_selected_training_algorithms()` 后增加：

```python
def _selected_model_param_overrides() -> dict:
    selected = set(_selected_training_algorithms())
    raw = st.session_state.get("model_param_overrides") or {}
    return {
        algo: params
        for algo, params in raw.items()
        if algo in selected and isinstance(params, dict)
    }
```

- [ ] **Step 3: 渲染参数编辑器**

新增 `_render_model_hyperparameter_controls(registry, selected_algorithms)`：

- 每个模型一个 `st.expander`。
- `int/float` 参数使用 `st.number_input`。
- categorical 参数使用 `st.selectbox` 或 `st.checkbox`。
- 控件 key 使用 `model_param_{algo}_{param}`。
- 保存到 `st.session_state["model_param_overrides"][algo][param]`。

- [ ] **Step 4: 接入建模页**

在 `render_modeling_lab()` 的训练方案控件后调用：

```python
selected_algorithms = _selected_training_algorithms()
_render_model_hyperparameter_controls(registry, selected_algorithms)
```

`model_focus_selection` 用于默认展开或高亮对应模型参数 expander，避免继续成为 UI-only 控件。

- [ ] **Step 5: 传参给工具**

在 `handle_action()` 的 `train_models/optimize_models/retrain_optimized` 分支加入：

```python
manual_params = _selected_model_param_overrides()
if manual_params:
    if action == "train_models":
        kwargs["param_overrides"] = manual_params
    else:
        kwargs["base_param_overrides"] = manual_params
```

## Task 5: 工具 schema 合约与助手边界

**Files:**
- Modify: `D:\空\water_erosion_mvp\prompts\tool_descriptions.json`
- Test: `D:\空\water_erosion_mvp\test_p0_p3_upgrade.py`

- [ ] **Step 1: 新增 schema 合约测试**

新增：

```python
def test_model_tool_schema_contract(self):
    schemas = tools.load_tool_schemas()
    by_name = {item["function"]["name"]: item["function"] for item in schemas}
    for name in ["train_candidates", "run_stage_two_optimization", "run_stage_three_retrain"]:
        self.assertIn(name, by_name)
    alg_enum = by_name["train_candidates"]["parameters"]["properties"]["algorithms"]["items"].get("enum")
    for algo in ["lightgbm", "xgboost", "random_forest", "extratrees", "adaboost", "svr", "knn"]:
        self.assertIn(algo, alg_enum)
```

- [ ] **Step 2: 更新 `tool_descriptions.json`**

为以下工具增加/更新 schema：

- `train_candidates`：增加 `param_overrides`。
- `run_stage_two_optimization`：增加 `algorithms/cv_folds/n_trials/timeout_sec/base_param_overrides`。
- `run_stage_three_retrain`：增加 `algorithms/optimization_results/base_param_overrides`。
- `run_error_corrector` 和 `error_corrector_report` 的 `stage` 增加 enum：`["P0", "P1", "P2", "P3"]`。

- [ ] **Step 3: 明确助手边界**

本轮不实现 `agent.py` 自动工具调用。保留 `load_tool_schemas()` 作为可执行工具目录的静态来源，但 UI 文案不能暗示本地助手能自主调用工具。若要实现工具调用，单独开计划修改 `agent.py` 的 schema 注入、工具选择、参数校验、`tools.execute_tool()` 分发和安全白名单。

## Task 6: CatBoost 可用性处理

**Files:**
- Modify: `D:\空\water_erosion_mvp\tools.py`
- Modify: `D:\空\water_erosion_mvp\app.py`
- Test: `D:\空\water_erosion_mvp\test_p0_p3_upgrade.py`

- [ ] **Step 1: 新增可用性函数**

在 `tools.py` 增加：

```python
def model_dependency_status(algo: str) -> dict:
    algo = str(algo).lower()
    if algo == "catboost":
        try:
            import catboost  # noqa: F401
            return {"available": True, "reason": ""}
        except Exception as exc:
            return {"available": False, "reason": f"catboost unavailable: {exc}"}
    return {"available": True, "reason": ""}
```

- [ ] **Step 2: UI 标记不可用模型**

`render_modeling_lab()` 生成算法选项时，对不可用模型显示 `CatBoost（未安装）` 并禁用或默认不选。手动参数区域对不可用模型只显示说明，不渲染训练参数控件。

- [ ] **Step 3: 后端跳过不可用模型**

`train_candidates()`、`run_stage_two_optimization()`、`run_stage_three_retrain()` 在算法循环前检查 `model_dependency_status(algo)`，不可用则写入 `skipped_algorithms`。

## Task 7: 验证与验收

**Files:**
- All modified files

- [ ] **Step 1: 最小编译检查**

Run:

```powershell
D:\codex\envs\water_erosion_mvp_py313\Scripts\python.exe -m py_compile app.py agent.py tools.py utils\raster_io.py utils\viz.py
```

Expected: exit code 0.

- [ ] **Step 2: 定向测试**

Run:

```powershell
D:\codex\envs\water_erosion_mvp_py313\Scripts\python.exe -m unittest test_p0_p3_upgrade.py
D:\codex\envs\water_erosion_mvp_py313\Scripts\python.exe -m unittest test_ui_design_assets.py
```

Expected: all tests pass, allowed existing `wmic`/Streamlit bare-mode warnings.

- [ ] **Step 3: 全量测试**

Run:

```powershell
D:\codex\envs\water_erosion_mvp_py313\Scripts\python.exe -m unittest discover -p "test_*.py"
```

Expected: all tests pass; no new skipped tests except existing accepted skip.

- [ ] **Step 4: 手动验收点**

通过 Streamlit 页面验证：

- 进入“模型构建”页后，选中的每个模型都有手动超参数区域。
- 修改随机森林 `n_estimators` 后点击“默认训练”，结果中的 `state["models"]["random_forest"]["params"]["n_estimators"]` 与 UI 输入一致。
- 点击“贝叶斯优化”后，`state["_optimization_result"]["optimization_results"]` 存在。
- 不经过 UI 直接运行 `run_stage_two_optimization()` 后再运行 `run_stage_three_retrain()` 也能成功。
- CatBoost 未安装时不会被展示为完整可运行模型；选择或请求 CatBoost 时返回清晰 skip/reason。

## 验收标准

- 手动超参数控件覆盖 `MODEL_REGISTRY` 中所有可用模型的 `default_params`。
- 默认训练实际使用手动参数，并在模型 state、ranking/evidence 中保存实际参数。
- 每个 Optuna 搜索出来的参数都能被对应 estimator 消费；不存在注册但不生效的死参数。
- 阶段二优化结果在 `tools.py` 内写回 state；阶段三不依赖 `app.py` 外层桥接也能重训。
- CatBoost 缺依赖时有 UI/后端/schema 一致提示，不影响其他模型训练、优化、重训。
- 工具 schema 至少覆盖 `train_candidates`、`run_stage_two_optimization`、`run_stage_three_retrain`，并与后端支持算法枚举一致。
- `py_compile`、`test_p0_p3_upgrade.py`、`test_ui_design_assets.py`、全量 `unittest discover` 均通过。
- 实现后完成第二轮子智能体只读审查，并无新增 P1/P2 未处理问题。

