/// 点击验证用例模板
final clickValidationCaseTemplate = '''
点击验证用例规范：

格式：
{
  case_id: "M01_模块",
  module: "模块名",
  action: "点击动作描述",
  mock_input: {...},
  expected_output: {...},
  assertion_rule: "断言说明",
}

字段说明：
- case_id: 用例唯一编号，格式 M{number}_{module}
- module: 页面或服务模块名称
- action: 用户操作或点击的具体描述
- mock_input: 模拟输入数据
- expected_output: 预期输出结果
- assertion_rule: 断言验证规则（文字描述）

执行流程：
1. 接收 mock_input
2. 调用对应服务模块
3. 获取 actual_output
4. 比对 expected_output
5. 记录 pass/fail 和耗时
6. 保存到 click_log

点击验收矩阵 (M01-M14):
- M01_HOME: 首页进入
- M02_MODEL: 模型包管理
- M03_QC_PASS: 质控通过
- M04_QC_FAIL: 质控失败
- M05_CAPTURE_I0: 基线采集
- M06_CAPTURE_I1: 待测采集
- M07_ROI: ROI 确认
- M08_FEATURE: 特征提取
- M09_PREDICT: 模型推理
- M10_RESULT: 结果详情
- M11_SAVE: 保存历史
- M12_HISTORY: 历史记录
- M13_ANALYSIS: 分析总览
- M14_EXPORT: CSV 导出
''';
