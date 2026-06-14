import '../models/feature_vector.dart';

/// 特征提取服务
/// 负责从图像 ROI 中提取颜色、纹理和散射特征
class FeatureExtractionService {
  /// 执行特征提取
  /// 输入: 图像元数据和 ROI 信息
  /// 输出: FeatureVector，包含所有提取的特征
  Future<FeatureVector> extractFeatures({
    required String sessionId,
    required Map<String, dynamic> imageMetadata,
    required String? differenceImagePath,
  }) async {
    try {
      final features = <String, double>{};

      // 颜色差分特征: dL, da, db, dS
      features['dL'] = (imageMetadata['color_dL'] ?? 0.0) as double;
      features['da'] = (imageMetadata['color_da'] ?? 0.0) as double;
      features['db'] = (imageMetadata['color_db'] ?? 0.0) as double;
      features['dS'] = (imageMetadata['color_dS'] ?? 0.0) as double;

      // 白化指数: 低饱和高亮比例
      features['whiteness_index'] =
          (imageMetadata['whiteness_index'] ?? 0.0) as double;

      // 高光比例: 近饱和像素比例
      features['specular_ratio'] =
          (imageMetadata['specular_ratio'] ?? 0.0) as double;

      // 纹理特征: GLCM contrast 和 energy
      features['glcm_contrast'] =
          (imageMetadata['glcm_contrast'] ?? 0.0) as double;
      features['glcm_energy'] =
          (imageMetadata['glcm_energy'] ?? 0.0) as double;

      // 二阶特征
      features['dL2'] = (imageMetadata['dL2'] ?? 0.0) as double;
      features['specular_ratio2'] =
          (imageMetadata['specular_ratio2'] ?? 0.0) as double;

      // 验证特征向量有效性
      _validateFeatureVector(features);

      return FeatureVector(
        sessionId: sessionId,
        features: features,
        differenceImagePath: differenceImagePath,
        metadata: {
          'extraction_method': 'simulated',
          'roi_from': imageMetadata['roi_source'],
        },
        extractedAt: DateTime.now(),
      );
    } catch (e) {
      throw Exception('特征提取失败: $e');
    }
  }

  /// 验证特征向量有效性（无 NaN，无无穷）
  void _validateFeatureVector(Map<String, double> features) {
    for (final entry in features.entries) {
      if (entry.value.isNaN || entry.value.isInfinite) {
        throw Exception('特征 ${entry.key} 无效: ${entry.value}');
      }
    }
  }

  /// 颜色校正模拟实现
  /// 根据灰卡 RGB 和参考值进行白平衡校正
  Map<String, double> performColorCorrection({
    required List<int> grayCardRgb,
    required List<int> targetGrayRgb,
  }) {
    // 简单的线性校正: 缩放因子 = target / current
    final rScale = targetGrayRgb[0] / (grayCardRgb[0] + 1);
    final gScale = targetGrayRgb[1] / (grayCardRgb[1] + 1);
    final bScale = targetGrayRgb[2] / (grayCardRgb[2] + 1);

    return {
      'r_scale': rScale,
      'g_scale': gScale,
      'b_scale': bScale,
    };
  }

  /// 标准化特征向量
  /// 使用提供的均值和标准差
  List<double> normalizeFeatures(
    List<double> features,
    List<double> means,
    List<double> stds,
  ) {
    if (features.length != means.length || features.length != stds.length) {
      throw Exception('特征维度不一致');
    }

    return List<double>.generate(
      features.length,
      (i) => (features[i] - means[i]) / (stds[i] + 1e-8),
    );
  }
}
