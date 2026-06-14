import '../models/feature_vector.dart';
import '../models/model_bundle.dart';
import '../models/prediction_result.dart';

/// 模型推理引擎
/// 负责执行本地线性/Ridge 回归推理
class PredictionService {
  /// 执行模型推理
  /// 输入: 特征向量 + 模型包
  /// 输出: 预测结果（包含状态、置信度、范围判定等）
  Future<PredictionResult> predict({
    required String sessionId,
    required String sampleId,
    required FeatureVector featureVector,
    required ModelBundle modelBundle,
    required String hardwareProfileId,
    required String sourceMode, // "simulated" or "real"
  }) async {
    try {
      // 步骤 1: 验证特征向量有效性
      if (!featureVector.isValid) {
        return _createErrorResult(
          sessionId: sessionId,
          sampleId: sampleId,
          modelId: modelBundle.modelId,
          hardwareProfileId: hardwareProfileId,
          sourceMode: sourceMode,
          validRangeMin: modelBundle.validRange[0],
          validRangeMax: modelBundle.validRange[1],
          errorMessage: '特征向量无效',
        );
      }

      // 步骤 2: 按模型指定的顺序整理特征
      final orderedFeatures =
          featureVector.toOrderedArray(modelBundle.featureOrder);

      // 步骤 3: 验证特征顺序和维度
      if (orderedFeatures.length != modelBundle.coefficients.length) {
        return _createErrorResult(
          sessionId: sessionId,
          sampleId: sampleId,
          modelId: modelBundle.modelId,
          hardwareProfileId: hardwareProfileId,
          sourceMode: sourceMode,
          validRangeMin: modelBundle.validRange[0],
          validRangeMax: modelBundle.validRange[1],
          errorMessage:
              '特征维度不匹配: ${orderedFeatures.length} vs ${modelBundle.coefficients.length}',
        );
      }

      // 步骤 4: 执行线性推理
      // y = intercept + Σ(coefficient_i * feature_i)
      double prediction = modelBundle.intercept;
      for (int i = 0; i < orderedFeatures.length; i++) {
        prediction += modelBundle.coefficients[i] * orderedFeatures[i];
      }

      // 步骤 5: 范围判定和置信度计算
      final isInRange = modelBundle.validRange[0] <= prediction &&
          prediction <= modelBundle.validRange[1];
      final approachingLimit = prediction >= modelBundle.validRange[1] * 0.9 &&
          prediction <= modelBundle.validRange[1];

      String resultStatus = 'valid';
      String confidenceLevel = 'high';
      final warnings = <String>[...modelBundle.warnings];

      if (!isInRange) {
        resultStatus = 'out_of_range';
        confidenceLevel = 'low';
        if (prediction < modelBundle.validRange[0]) {
          warnings.add('结果低于有效范围下限');
        } else {
          warnings.add('结果超过有效范围上限');
        }
      } else if (approachingLimit) {
        resultStatus = 'warning';
        confidenceLevel = 'medium';
        warnings.add('结果接近有效范围上限');
      }

      if (sourceMode == 'simulated') {
        warnings.add('本结果基于模拟数据，仅用于方法验证');
        confidenceLevel = 'medium';
      }

      // 步骤 6: 构建预测结果
      return PredictionResult(
        sessionId: sessionId,
        sampleId: sampleId,
        modelId: modelBundle.modelId,
        predictedValue: prediction.clamp(
          modelBundle.validRange[0] - 1.0,
          modelBundle.validRange[1] + 1.0,
        ),
        unit: 'mg/cm2',
        sourceMode: sourceMode,
        resultStatus: resultStatus,
        confidenceLevel: confidenceLevel,
        validRangeMin: modelBundle.validRange[0],
        validRangeMax: modelBundle.validRange[1],
        featureVector: featureVector.features,
        hardwareProfileId: hardwareProfileId,
        warnings: warnings,
        createdAt: DateTime.now(),
      );
    } catch (e) {
      return _createErrorResult(
        sessionId: sessionId,
        sampleId: sampleId,
        modelId: modelBundle.modelId,
        hardwareProfileId: hardwareProfileId,
        sourceMode: sourceMode,
        validRangeMin: modelBundle.validRange[0],
        validRangeMax: modelBundle.validRange[1],
        errorMessage: '推理失败: $e',
      );
    }
  }

  /// 创建错误结果
  PredictionResult _createErrorResult({
    required String sessionId,
    required String sampleId,
    required String modelId,
    required String hardwareProfileId,
    required String sourceMode,
    required double validRangeMin,
    required double validRangeMax,
    required String errorMessage,
  }) {
    return PredictionResult(
      sessionId: sessionId,
      sampleId: sampleId,
      modelId: modelId,
      predictedValue: 0.0,
      unit: 'mg/cm2',
      sourceMode: sourceMode,
      resultStatus: 'error',
      confidenceLevel: 'low',
      validRangeMin: validRangeMin,
      validRangeMax: validRangeMax,
      featureVector: {},
      hardwareProfileId: hardwareProfileId,
      warnings: [errorMessage],
      createdAt: DateTime.now(),
    );
  }
}
