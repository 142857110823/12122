## v0.3 (2026-04-28)

### Added
- 新增 tools.optimize_hyperparams，基于Optuna TPE+空间分块CV做超参搜索
- 状态机新增 models_optimized 阶段与对应选项卡
- models_trained 阶段新增"开始超参优化"选项
- models_optimized 阶段支持：用调优后模型预测 / 对比调优前后 / 再跑20轮搜索 / 退回原始训练

### Changed
- CANDIDATES从 {RandomForest, GradientBoosting, Ridge} 切换为 {LightGBM, XGBoost, RandomForest}
- 三个训练函数统一为固定默认参数（n_estimators=300, n_jobs=1），移除旧网格搜索逻辑
- LightGBM: verbose=-1 + fit(verbose=False) + catch "No further splits" warning
- XGBoost: verbosity=0
- RandomForest: n_jobs=1
- requirements.txt 新增 lightgbm>=4.2, xgboost>=2.0, optuna>=3.5
