/// 预测结果模型
class PredictionResult {
  final String sessionId;
  final String sampleId;
  final String modelId;
  final double predictedValue; // mg/cm2 NaCl eq.
  final String unit; // "mg/cm2"
  final String sourceMode; // "simulated" or "real"
  final String resultStatus; // "valid", "warning", "out_of_range", "error"
  final String confidenceLevel; // "high", "medium", "low"
  final double validRangeMin;
  final double validRangeMax;
  final Map<String, dynamic> featureVector;
  final String hardwareProfileId;
  final List<String> warnings;
  final DateTime createdAt;

  PredictionResult({
    required this.sessionId,
    required this.sampleId,
    required this.modelId,
    required this.predictedValue,
    required this.unit,
    required this.sourceMode,
    required this.resultStatus,
    required this.confidenceLevel,
    required this.validRangeMin,
    required this.validRangeMax,
    required this.featureVector,
    required this.hardwareProfileId,
    required this.warnings,
    required this.createdAt,
  });

  /// 判断结果是否为模拟数据
  bool get isSimulated => sourceMode == "simulated";

  /// 判断结果是否超出有效范围
  bool get isOutOfRange =>
      predictedValue < validRangeMin || predictedValue > validRangeMax;

  /// 判断是否接近上限
  bool get approachingUpperLimit {
    final threshold = validRangeMax * 0.9; // 接近上限 90% 处
    return predictedValue >= threshold && predictedValue <= validRangeMax;
  }

  /// 转换为 JSON（用于历史存储）
  Map<String, dynamic> toJson() => {
        'session_id': sessionId,
        'sample_id': sampleId,
        'model_id': modelId,
        'predicted_mg_cm2': predictedValue,
        'unit': unit,
        'source_mode': sourceMode,
        'result_status': resultStatus,
        'confidence_level': confidenceLevel,
        'valid_range_min': validRangeMin,
        'valid_range_max': validRangeMax,
        'feature_vector': featureVector,
        'hardware_profile_id': hardwareProfileId,
        'warnings': warnings,
        'created_at': createdAt.toIso8601String(),
      };

  /// 从 JSON 恢复
  factory PredictionResult.fromJson(Map<String, dynamic> json) {
    return PredictionResult(
      sessionId: json['session_id'] ?? '',
      sampleId: json['sample_id'] ?? '',
      modelId: json['model_id'] ?? '',
      predictedValue: (json['predicted_mg_cm2'] ?? 0.0).toDouble(),
      unit: json['unit'] ?? 'mg/cm2',
      sourceMode: json['source_mode'] ?? 'real',
      resultStatus: json['result_status'] ?? 'valid',
      confidenceLevel: json['confidence_level'] ?? 'high',
      validRangeMin: (json['valid_range_min'] ?? 0.0).toDouble(),
      validRangeMax: (json['valid_range_max'] ?? 1.0).toDouble(),
      featureVector: Map<String, dynamic>.from(json['feature_vector'] ?? {}),
      hardwareProfileId: json['hardware_profile_id'] ?? '',
      warnings: List<String>.from(json['warnings'] ?? []),
      createdAt: DateTime.parse(json['created_at'] ?? DateTime.now().toIso8601String()),
    );
  }
}
