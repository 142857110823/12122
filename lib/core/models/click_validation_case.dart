/// 点击验证用例
class ClickValidationCase {
  final String caseId; // e.g., "QC_PASS_001"
  final String module; // e.g., "成像质控"
  final String action; // e.g., "点击开始质控"
  final Map<String, dynamic> mockInput; // 模拟输入
  final Map<String, dynamic> expectedOutput; // 预期输出
  final String? assertionRule; // 断言规则说明

  ClickValidationCase({
    required this.caseId,
    required this.module,
    required this.action,
    required this.mockInput,
    required this.expectedOutput,
    this.assertionRule,
  });

  factory ClickValidationCase.fromJson(Map<String, dynamic> json) {
    return ClickValidationCase(
      caseId: json['case_id'] ?? '',
      module: json['module'] ?? '',
      action: json['action'] ?? '',
      mockInput: Map<String, dynamic>.from(json['mock_input'] ?? {}),
      expectedOutput: Map<String, dynamic>.from(json['expected_output'] ?? {}),
      assertionRule: json['assertion_rule'],
    );
  }

  Map<String, dynamic> toJson() => {
        'case_id': caseId,
        'module': module,
        'action': action,
        'mock_input': mockInput,
        'expected_output': expectedOutput,
        'assertion_rule': assertionRule,
      };
}

/// 点击验证日志记录
class ClickValidationLog {
  final String caseId;
  final String module;
  final Map<String, dynamic> mockInput;
  final Map<String, dynamic> actualOutput;
  final Map<String, dynamic> expectedOutput;
  final String result; // "pass" or "fail"
  final int durationMs;
  final String? errorMessage;
  final String? screenshotPath;
  final DateTime createdAt;

  ClickValidationLog({
    required this.caseId,
    required this.module,
    required this.mockInput,
    required this.actualOutput,
    required this.expectedOutput,
    required this.result,
    required this.durationMs,
    this.errorMessage,
    this.screenshotPath,
    required this.createdAt,
  });

  bool get isPassed => result == 'pass';

  factory ClickValidationLog.fromJson(Map<String, dynamic> json) {
    return ClickValidationLog(
      caseId: json['case_id'] ?? '',
      module: json['module'] ?? '',
      mockInput: Map<String, dynamic>.from(json['mock_input'] ?? {}),
      actualOutput: Map<String, dynamic>.from(json['actual_output'] ?? {}),
      expectedOutput: Map<String, dynamic>.from(json['expected_output'] ?? {}),
      result: json['result'] ?? 'fail',
      durationMs: json['duration_ms'] ?? 0,
      errorMessage: json['error_message'],
      screenshotPath: json['screenshot_path'],
      createdAt: DateTime.parse(
        json['created_at'] ?? DateTime.now().toIso8601String(),
      ),
    );
  }

  Map<String, dynamic> toJson() => {
        'case_id': caseId,
        'module': module,
        'mock_input': mockInput,
        'actual_output': actualOutput,
        'expected_output': expectedOutput,
        'result': result,
        'duration_ms': durationMs,
        'error_message': errorMessage,
        'screenshot_path': screenshotPath,
        'created_at': createdAt.toIso8601String(),
      };
}
