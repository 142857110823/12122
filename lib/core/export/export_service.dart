import '../models/prediction_result.dart';

/// CSV 导出服务
/// 负责生成结构化的 CSV 文本和报告
class ExportService {
  /// CSV 字段列表
  static const List<String> csvHeaders = [
    'session_id',
    'sample_id',
    'model_id',
    'source_mode',
    'hardware_profile_id',
    'baseline_image_path',
    'salted_image_path',
    'roi_area_cm2',
    'dL',
    'da',
    'db',
    'dS',
    'whiteness_index',
    'specular_ratio',
    'glcm_contrast',
    'glcm_energy',
    'dL2',
    'specular_ratio2',
    'predicted_mg_cm2',
    'unit',
    'confidence_level',
    'result_status',
    'valid_range_min',
    'valid_range_max',
    'warnings',
    'created_at',
  ];

  /// 生成单条结果的 CSV 行
  String generateCsvRow({
    required String sessionId,
    required String sampleId,
    required PredictionResult result,
    required double roiAreaCm2,
    required String baselineImagePath,
    required String saltedImagePath,
  }) {
    final warnings = (result.warnings).join('; ');
    final fields = [
      _escape(sessionId),
      _escape(sampleId),
      _escape(result.modelId),
      _escape(result.sourceMode),
      _escape(result.hardwareProfileId),
      _escape(baselineImagePath),
      _escape(saltedImagePath),
      roiAreaCm2.toStringAsFixed(2),
      (result.featureVector['dL'] ?? 0.0).toString(),
      (result.featureVector['da'] ?? 0.0).toString(),
      (result.featureVector['db'] ?? 0.0).toString(),
      (result.featureVector['dS'] ?? 0.0).toString(),
      (result.featureVector['whiteness_index'] ?? 0.0).toString(),
      (result.featureVector['specular_ratio'] ?? 0.0).toString(),
      (result.featureVector['glcm_contrast'] ?? 0.0).toString(),
      (result.featureVector['glcm_energy'] ?? 0.0).toString(),
      (result.featureVector['dL2'] ?? 0.0).toString(),
      (result.featureVector['specular_ratio2'] ?? 0.0).toString(),
      result.predictedValue.toStringAsFixed(4),
      _escape(result.unit),
      _escape(result.confidenceLevel),
      _escape(result.resultStatus),
      result.validRangeMin.toStringAsFixed(4),
      result.validRangeMax.toStringAsFixed(4),
      _escape(warnings),
      _escape(result.createdAt.toIso8601String()),
    ];
    return fields.join(',');
  }

  /// 生成完整 CSV（包含表头）
  String generateCsv({
    required List<Map<String, dynamic>> sessions,
  }) {
    final buffer = StringBuffer();
    buffer.writeln(csvHeaders.map(_escape).join(','));

    for (final session in sessions) {
      try {
        final result = PredictionResult.fromJson(
          Map<String, dynamic>.from(session['result'] ?? {}),
        );
        final roiArea =
            (session['roi_polygon']?['area'] ?? 4.0) as double;
        final baselineImagePath =
            (session['baseline_image_path'] ?? '') as String;
        final saltedImagePath =
            (session['salted_image_path'] ?? '') as String;

        buffer.writeln(
          generateCsvRow(
            sessionId: session['session_id'] as String,
            sampleId: session['sample_id'] as String,
            result: result,
            roiAreaCm2: roiArea,
            baselineImagePath: baselineImagePath,
            saltedImagePath: saltedImagePath,
          ),
        );
      } catch (e) {
        // 跳过无效记录
      }
    }

    return buffer.toString();
  }

  /// 生成报告预览（包含元数据和摘要）
  String generateReportPreview({
    required String sampleId,
    required PredictionResult result,
    required double roiAreaCm2,
    required String baselineImagePath,
    required String saltedImagePath,
  }) {
    final buffer = StringBuffer();
    buffer.writeln('=== FreshSalt Surface 实验结果报告 ===');
    buffer.writeln('生成时间: ${DateTime.now().toIso8601String()}');
    buffer.writeln('');
    buffer.writeln('样品信息:');
    buffer.writeln('  样品 ID: $sampleId');
    buffer.writeln('  ROI 面积: ${roiAreaCm2.toStringAsFixed(2)} cm²');
    buffer.writeln('');
    buffer.writeln('模型信息:');
    buffer.writeln('  模型 ID: ${result.modelId}');
    buffer.writeln('  数据来源: ${result.sourceMode}');
    buffer.writeln('  硬件配置: ${result.hardwareProfileId}');
    buffer.writeln('');
    buffer.writeln('主要结果:');
    buffer.writeln(
      '  表面盐分负载: ${result.predictedValue.toStringAsFixed(4)} ${result.unit}',
    );
    buffer.writeln('  置信等级: ${result.confidenceLevel}');
    buffer.writeln('  结果状态: ${result.resultStatus}');
    buffer.writeln(
      '  有效范围: [${result.validRangeMin}, ${result.validRangeMax}]',
    );
    buffer.writeln('');
    buffer.writeln('提取的特征:');
    for (final entry in result.featureVector.entries) {
      buffer.writeln('  ${entry.key}: ${entry.value}');
    }
    buffer.writeln('');
    if (result.warnings.isNotEmpty) {
      buffer.writeln('警告和提示:');
      for (final warning in result.warnings) {
        buffer.writeln('  - $warning');
      }
      buffer.writeln('');
    }
    buffer.writeln('重要声明:');
    buffer.writeln(
      '本报告仅用于大学物理实验验证和方法研究，',
    );
    buffer.writeln(
      '不作为食品安全判定、商品分级或执法检测依据。',
    );
    buffer.writeln('');
    buffer.writeln('图像路径:');
    buffer.writeln('  基线图 I0: $baselineImagePath');
    buffer.writeln('  待测图 I1: $saltedImagePath');

    return buffer.toString();
  }

  /// 转义 CSV 字段
  static String _escape(String value) {
    if (value.contains(',') || value.contains('"') || value.contains('\n')) {
      return '"${value.replaceAll('"', '""')}"';
    }
    return value;
  }
}
