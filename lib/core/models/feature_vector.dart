/// 特征向量模型，包含所有提取的图像特征
class FeatureVector {
  final String sessionId;
  final Map<String, double> features; // 特征名 -> 值
  final String? differenceImagePath; // 差分图路径
  final Map<String, dynamic> metadata; // 元数据
  final DateTime extractedAt;

  FeatureVector({
    required this.sessionId,
    required this.features,
    this.differenceImagePath,
    this.metadata = const {},
    required this.extractedAt,
  });

  /// 检查特征向量有效性（无 NaN，维度一致）
  bool get isValid {
    return features.values.every((v) => !v.isNaN && !v.isInfinite);
  }

  /// 按指定顺序获取特征值数组
  List<double> toOrderedArray(List<String> featureOrder) {
    return featureOrder
        .map((name) => features[name] ?? 0.0)
        .toList();
  }

  factory FeatureVector.fromJson(Map<String, dynamic> json) {
    return FeatureVector(
      sessionId: json['session_id'] ?? '',
      features: Map<String, double>.from(
        (json['features'] as Map?)?.cast<String, dynamic>() ?? {},
      ).map((k, v) => MapEntry(k, (v as num).toDouble())),
      differenceImagePath: json['difference_image_path'],
      metadata: Map<String, dynamic>.from(json['metadata'] ?? {}),
      extractedAt: DateTime.parse(
        json['extracted_at'] ?? DateTime.now().toIso8601String(),
      ),
    );
  }

  Map<String, dynamic> toJson() => {
        'session_id': sessionId,
        'features': features,
        'difference_image_path': differenceImagePath,
        'metadata': metadata,
        'extracted_at': extractedAt.toIso8601String(),
      };
}
