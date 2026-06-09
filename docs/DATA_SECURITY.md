# 科研数据安全说明

本平台默认按本地/内网科研使用场景设计。该说明用于帮助科研人员理解数据保存位置、外部传输边界和清理方式，不替代单位法务或网安合规审查。

## 数据保存位置

- 上传副本：`data/uploads`
- 特征表：`data/features` 与 `data/runs/<run_id>/features`
- 模型文件：`data/models` 与 `data/runs/<run_id>/models`
- 预测结果：`data/predictions` 与 `data/runs/<run_id>/predictions`
- 解释图和空间产物：`data/runs/<run_id>/explanations`、`data/runs/<run_id>/spatial`
- 报告、审计和证据包：`data/report.md` 与 `data/runs/<run_id>/reports`、`data/runs/<run_id>/bundle`

## 外部传输边界

- 默认 `allow_external_llm = false`，智能小助手不会向外部模型 API 发送用户问题、平台状态、文件路径、报告内容或证据包内容。
- 当外部模型被明确允许时，助手提示词会先脱敏，移除 API Key、`sk-` 明文、本机绝对路径和用户目录片段。
- API Key 只能来自 `.env` 或系统环境变量，不能写入源码、前端状态、日志、测试、截图、报告或复盘文件。

## 导出保护

- 证据包索引使用相对路径或脱敏占位符，不写入本机绝对路径。
- 导出时会记录 `security_audit.jsonl`，包含导出事件、数据分类、保留期和外部模型许可状态。
- 报告和索引不应包含 API Key、原始密钥字段或本机用户目录。

## 清理建议

- 使用平台生成目录时，只清理 `data/uploads`、`data/features`、`data/models`、`data/predictions`、`data/runs` 中的副本和运行产物。
- 不要自动删除用户原始数据源目录。
- 本地/内网部署建议启用磁盘加密、受控系统账号和目录访问权限。
- 不建议把项目目录放在公开网盘、自动同步目录或多人共享的无权限隔离目录中。

## 升级边界

如果平台未来改为单位服务器或公网服务，需要先补充账号认证、角色权限、HTTPS、审计查询、备份恢复、访问频率控制、渗透测试和合规评估。
