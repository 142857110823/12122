import '../models/quality_control_result.dart'
    show QualityControlResult;

/// 质量控制服务
/// 负责曝光、清晰度、灰卡 RSD、ROI 完整性检查
class QualityControlService {
  /// 曝光检查的过饱和阈值
  static const double _exposureThreshold = 0.005; // 0.5%

  /// 清晰度检查的最小 Laplacian 方差
  static const double _sharpnessThreshold = 100.0;

  /// 灰卡 RSD 检查的最大允许值
  static const double _grayCardRsdThreshold = 0.02; // 2%

  /// 执行完整的质量控制检查
  /// 模拟实现：检查所有指标
  Future<QualityControlResult> performQualityControl({
    required Map<String, dynamic> imageMetadata,
  }) async {
    final checks = <String, bool>{};
    final metrics = <String, dynamic>{};
    final failureReasons = <String>[];

    // 曝光检查
    final exposurePass = _checkExposure(imageMetadata);
    checks['exposure'] = exposurePass;
    metrics['exposure_saturation_ratio'] =
        imageMetadata['saturation_ratio'] ?? 0.0;
    if (!exposurePass) {
      failureReasons.add(
        '过曝: 饱和像素比例 '
        '${((imageMetadata['saturation_ratio'] ?? 0.0) * 100).toStringAsFixed(2)}% '
        '超过阈值 ${(_exposureThreshold * 100).toStringAsFixed(2)}%',
      );
    }

    // 清晰度检查
    final sharpnessPass = _checkSharpness(imageMetadata);
    checks['sharpness'] = sharpnessPass;
    metrics['laplacian_variance'] = imageMetadata['laplacian_variance'] ?? 0.0;
    if (!sharpnessPass) {
      failureReasons.add(
        '图像模糊: Laplacian 方差 '
        '${(imageMetadata['laplacian_variance'] ?? 0.0).toStringAsFixed(2)} '
        '低于阈值 ${_sharpnessThreshold.toStringAsFixed(2)}',
      );
    }

    // 灰卡 RSD 检查
    final grayCardPass = _checkGrayCardRsd(imageMetadata);
    checks['gray_card_rsd'] = grayCardPass;
    metrics['gray_card_rsd'] = imageMetadata['gray_card_rsd'] ?? 0.0;
    if (!grayCardPass) {
      failureReasons.add(
        '灰卡不稳定: RSD '
        '${((imageMetadata['gray_card_rsd'] ?? 0.0) * 100).toStringAsFixed(2)}% '
        '超过阈值 ${(_grayCardRsdThreshold * 100).toStringAsFixed(2)}%',
      );
    }

    // ROI 完整性检查
    final roiPass = _checkRoiIntegrity(imageMetadata);
    checks['roi_integrity'] = roiPass;
    metrics['roi_area_cm2'] = imageMetadata['roi_area_cm2'] ?? 0.0;
    metrics['roi_within_bounds'] = imageMetadata['roi_within_bounds'] ?? false;
    if (!roiPass) {
      if ((imageMetadata['roi_area_cm2'] ?? 0.0) <= 0) {
        failureReasons.add('ROI 面积无效或为 0');
      }
      if (!(imageMetadata['roi_within_bounds'] ?? false)) {
        failureReasons.add('ROI 越界');
      }
    }

    final allPassed = checks.values.every((v) => v);
    final status = allPassed ? 'passed' : 'failed';

    return QualityControlResult(
      status: status,
      checks: checks,
      metrics: metrics,
      failureReasons: failureReasons,
      checkedAt: DateTime.now(),
    );
  }

  /// 曝光检查
  bool _checkExposure(Map<String, dynamic> metadata) {
    final saturationRatio = (metadata['saturation_ratio'] ?? 0.0) as num;
    return saturationRatio < _exposureThreshold;
  }

  /// 清晰度检查
  bool _checkSharpness(Map<String, dynamic> metadata) {
    final laplacianVariance = (metadata['laplacian_variance'] ?? 0.0) as num;
    return laplacianVariance >= _sharpnessThreshold;
  }

  /// 灰卡 RSD 检查
  bool _checkGrayCardRsd(Map<String, dynamic> metadata) {
    final rsd = (metadata['gray_card_rsd'] ?? 0.0) as num;
    return rsd <= _grayCardRsdThreshold;
  }

  /// ROI 完整性检查
  bool _checkRoiIntegrity(Map<String, dynamic> metadata) {
    final roiArea = (metadata['roi_area_cm2'] ?? 0.0) as num;
    final withinBounds = (metadata['roi_within_bounds'] ?? false) as bool;
    return roiArea > 0 && withinBounds;
  }
}
