/// 质量控制检查结果
class QualityControlResult {
  final String status; // "passed", "failed"
  final Map<String, bool> checks; // 各检查项结果
  final Map<String, dynamic> metrics; // 质量指标
  final List<String> failureReasons; // 失败原因
  final DateTime checkedAt;

  QualityControlResult({
    required this.status,
    required this.checks,
    required this.metrics,
    required this.failureReasons,
    required this.checkedAt,
  });

  bool get isPassed => status == 'passed';

  factory QualityControlResult.fromJson(Map<String, dynamic> json) {
    return QualityControlResult(
      status: json['status'] ?? 'failed',
      checks: Map<String, bool>.from(json['checks'] ?? {}),
      metrics: Map<String, dynamic>.from(json['metrics'] ?? {}),
      failureReasons: List<String>.from(json['failure_reasons'] ?? []),
      checkedAt: DateTime.parse(
        json['checked_at'] ?? DateTime.now().toIso8601String(),
      ),
    );
  }

  Map<String, dynamic> toJson() => {
        'status': status,
        'checks': checks,
        'metrics': metrics,
        'failure_reasons': failureReasons,
        'checked_at': checkedAt.toIso8601String(),
      };
}
