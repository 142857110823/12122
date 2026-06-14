/// 模型包数据结构，用于加载、验证和推理
class ModelBundle {
  final String modelId;
  final String source; // "simulated" or "real"
  final String sampleType; // "cucumber", etc.
  final String target; // "surface_NaCl_load_mg_cm2"
  final String unit; // "mg/cm2"
  final List<double> validRange; // [min, max]
  final List<String> featureOrder; // 特征排序
  final List<double> coefficients; // 模型系数
  final double intercept; // 截距
  final List<String> warnings;
  final Map<String, dynamic> metadata; // 扩展字段

  ModelBundle({
    required this.modelId,
    required this.source,
    required this.sampleType,
    required this.target,
    required this.unit,
    required this.validRange,
    required this.featureOrder,
    required this.coefficients,
    required this.intercept,
    required this.warnings,
    this.metadata = const {},
  });

  /// 验证模型包字段完整性
  List<String> validate() {
    final errors = <String>[];

    if (modelId.isEmpty) errors.add('模型 ID 不能为空');
    if (source.isEmpty) errors.add('模型来源不能为空');
    if (sampleType.isEmpty) errors.add('样品类型不能为空');
    if (validRange.length != 2 || validRange[0] >= validRange[1]) {
      errors.add('有效范围格式错误，需为 [min, max] 且 min < max');
    }
    if (featureOrder.isEmpty) errors.add('特征顺序不能为空');
    if (coefficients.isEmpty) errors.add('模型系数不能为空');
    if (featureOrder.length != coefficients.length) {
      errors.add(
        '特征顺序与系数数量不一致：'
        '${featureOrder.length} vs ${coefficients.length}',
      );
    }

    return errors;
  }

  /// 判断是否为模拟模型
  bool get isSimulated => source == 'simulated';

  /// 从 JSON 加载模型包
  factory ModelBundle.fromJson(Map<String, dynamic> json) {
    return ModelBundle(
      modelId: json['model_id'] ?? '',
      source: json['source'] ?? 'real',
      sampleType: json['sample_type'] ?? '',
      target: json['target'] ?? '',
      unit: json['unit'] ?? 'mg/cm2',
      validRange: List<double>.from(
        (json['valid_range_mg_cm2'] as List?)?.map((x) => (x as num).toDouble()) ??
            [0.0, 1.0],
      ),
      featureOrder: List<String>.from(json['feature_order'] ?? []),
      coefficients: List<double>.from(
        (json['coefficients'] as List?)?.map((x) => (x as num).toDouble()) ??
            [],
      ),
      intercept: (json['intercept'] ?? 0.0).toDouble(),
      warnings: List<String>.from(json['warnings'] ?? []),
      metadata: Map<String, dynamic>.from(json['metadata'] ?? {}),
    );
  }

  /// 转换为 JSON
  Map<String, dynamic> toJson() => {
        'model_id': modelId,
        'source': source,
        'sample_type': sampleType,
        'target': target,
        'unit': unit,
        'valid_range_mg_cm2': validRange,
        'feature_order': featureOrder,
        'coefficients': coefficients,
        'intercept': intercept,
        'warnings': warnings,
        'metadata': metadata,
      };
}
