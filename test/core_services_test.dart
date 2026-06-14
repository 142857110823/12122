import 'package:test/test.dart';

import '../core/models/model_bundle.dart';
import '../core/models/prediction_result.dart';
import '../core/models/feature_vector.dart';
import '../core/models/quality_control_result.dart';
import '../core/services/model_bundle_service.dart';
import '../core/services/quality_control_service.dart';
import '../core/services/feature_extraction_service.dart';
import '../core/services/prediction_service.dart';
import '../core/repositories/session_repository.dart';
import '../core/export/export_service.dart';
import '../core/demo/mock_data.dart';

void main() {
  group('模型包管理服务', () {
    late ModelBundleService service;

    setUp(() {
      service = ModelBundleService();
    });

    test('加载有效的模型包', () async {
      final bundle = ModelBundle.fromJson(mockModelBundle);
      final errors = await service.loadModelBundle(bundle);
      expect(errors, isEmpty);
    });

    test('激活已加载的模型包', () async {
      final bundle = ModelBundle.fromJson(mockModelBundle);
      await service.loadModelBundle(bundle);
      final errors = await service.activateModelBundle(bundle.modelId);
      expect(errors, isEmpty);
      expect(service.activeModel, isNotNull);
      expect(service.activeModel!.modelId, equals(bundle.modelId));
    });

    test('验证硬件兼容性', () {
      final bundle = ModelBundle.fromJson(mockModelBundle);
      final compatible =
          service.validateHardwareCompatibility('darkbox_v1', bundle);
      expect(compatible, isTrue);

      final notCompatible =
          service.validateHardwareCompatibility('darkbox_v2', bundle);
      expect(notCompatible, isFalse);
    });

    test('检查结果是否在有效范围内', () {
      final bundle = ModelBundle.fromJson(mockModelBundle);
      expect(service.isResultInValidRange(0.35, bundle), isTrue);
      expect(service.isResultInValidRange(1.0, bundle), isFalse);
      expect(service.isResultInValidRange(-0.1, bundle), isFalse);
    });
  });

  group('质量控制服务', () {
    late QualityControlService service;

    setUp(() {
      service = QualityControlService();
    });

    test('质控通过 - 中等负荷', () async {
      final result = await service.performQualityControl(
        imageMetadata: mockImageMetadataMedium,
      );
      expect(result.isPassed, isTrue);
      expect(result.checks['exposure'], isTrue);
      expect(result.checks['sharpness'], isTrue);
      expect(result.checks['gray_card_rsd'], isTrue);
      expect(result.checks['roi_integrity'], isTrue);
    });

    test('质控失败 - 过曝', () async {
      final result = await service.performQualityControl(
        imageMetadata: mockImageMetadataOverexposed,
      );
      expect(result.isPassed, isFalse);
      expect(result.checks['exposure'], isFalse);
      expect(result.failureReasons, isNotEmpty);
    });

    test('质控失败 - 模糊', () async {
      final result = await service.performQualityControl(
        imageMetadata: mockImageMetadataBlurry,
      );
      expect(result.isPassed, isFalse);
      expect(result.checks['sharpness'], isFalse);
    });

    test('质控失败 - ROI 越界', () async {
      final result = await service.performQualityControl(
        imageMetadata: mockImageMetadataRoiOutOfBounds,
      );
      expect(result.isPassed, isFalse);
      expect(result.checks['roi_integrity'], isFalse);
    });
  });

  group('特征提取服务', () {
    late FeatureExtractionService service;

    setUp(() {
      service = FeatureExtractionService();
    });

    test('提取有效的特征向量', () async {
      final featureVector = await service.extractFeatures(
        sessionId: 'session_001',
        imageMetadata: mockImageMetadataMedium,
      );

      expect(featureVector.isValid, isTrue);
      expect(featureVector.features.length, equals(10));
      expect(featureVector.features['dL'], isNotNull);
      expect(featureVector.features['whiteness_index'], isNotNull);
    });

    test('标准化特征向量', () {
      final features = [1.0, 2.0, 3.0];
      final means = [0.5, 1.5, 2.5];
      final stds = [0.5, 0.5, 0.5];

      final normalized = service.normalizeFeatures(features, means, stds);
      expect(normalized.length, equals(3));
      expect(normalized[0], equals(1.0)); // (1.0 - 0.5) / 0.5
    });

    test('颜色校正', () {
      final grayCardRgb = [128, 128, 128];
      final targetGrayRgb = [200, 200, 200];

      final scales = service.performColorCorrection(
        grayCardRgb: grayCardRgb,
        targetGrayRgb: targetGrayRgb,
      );

      expect(scales['r_scale'], isNotNull);
      expect(scales['r_scale'], greaterThan(1.0));
    });
  });

  group('模型推理服务', () {
    late PredictionService service;

    setUp(() {
      service = PredictionService();
    });

    test('推理低负荷样品', () async {
      final bundle = ModelBundle.fromJson(mockModelBundle);
      final featureVector = FeatureVector(
        sessionId: 'session_001',
        features: {
          'dL': -2.5,
          'da': 1.2,
          'db': 0.8,
          'dS': -0.5,
          'whiteness_index': 0.08,
          'specular_ratio': 0.05,
          'glcm_contrast': 0.12,
          'glcm_energy': 0.85,
          'dL2': 6.25,
          'specular_ratio2': 0.0025,
        },
        extractedAt: DateTime.now(),
      );

      final result = await service.predict(
        sessionId: 'session_001',
        sampleId: 'sample_001',
        featureVector: featureVector,
        modelBundle: bundle,
        hardwareProfileId: 'darkbox_v1',
        sourceMode: 'simulated',
      );

      expect(result.resultStatus, isNotEmpty);
      expect(result.confidenceLevel, isNotEmpty);
      expect(result.predictedValue, greaterThanOrEqualTo(0.0));
    });

    test('推理高负荷样品 - 接近上限警告', () async {
      final bundle = ModelBundle.fromJson(mockModelBundle);
      final featureVector = FeatureVector(
        sessionId: 'session_002',
        features: {
          'dL': -15.2,
          'da': 6.8,
          'db': 4.5,
          'dS': -3.5,
          'whiteness_index': 0.45,
          'specular_ratio': 0.32,
          'glcm_contrast': 0.48,
          'glcm_energy': 0.68,
          'dL2': 231.04,
          'specular_ratio2': 0.1024,
        },
        extractedAt: DateTime.now(),
      );

      final result = await service.predict(
        sessionId: 'session_002',
        sampleId: 'sample_002',
        featureVector: featureVector,
        modelBundle: bundle,
        hardwareProfileId: 'darkbox_v1',
        sourceMode: 'simulated',
      );

      expect(result.warnings.isNotEmpty, isTrue);
    });
  });

  group('会话仓储', () {
    late InMemorySessionRepository repository;
    late PredictionResult mockResult;
    late FeatureVector mockFeatures;

    setUp(() async {
      repository = InMemorySessionRepository();
      mockResult = PredictionResult(
        sessionId: 'session_001',
        sampleId: 'sample_001',
        modelId: 'model_001',
        predictedValue: 0.35,
        unit: 'mg/cm2',
        sourceMode: 'simulated',
        resultStatus: 'valid',
        confidenceLevel: 'high',
        validRangeMin: 0.0,
        validRangeMax: 0.75,
        featureVector: {'dL': -8.5},
        hardwareProfileId: 'darkbox_v1',
        warnings: [],
        createdAt: DateTime.now(),
      );
      mockFeatures = FeatureVector(
        sessionId: 'session_001',
        features: {'dL': -8.5},
        extractedAt: DateTime.now(),
      );
    });

    test('保存和读取会话', () async {
      await repository.saveSession(
        sessionId: 'session_001',
        sampleId: 'sample_001',
        result: mockResult,
        featureVector: mockFeatures,
        baselineImagePath: '/path/to/baseline.jpg',
        saltedImagePath: '/path/to/salted.jpg',
        roiPolygon: {'area': 4.0},
      );

      final retrieved = await repository.getSession('session_001');
      expect(retrieved, isNotNull);
      expect(retrieved!['sample_id'], equals('sample_001'));
    });

    test('筛选模拟数据会话', () async {
      await repository.saveSession(
        sessionId: 'session_001',
        sampleId: 'sample_001',
        result: mockResult,
        featureVector: mockFeatures,
        baselineImagePath: '/path/to/baseline.jpg',
        saltedImagePath: '/path/to/salted.jpg',
        roiPolygon: {'area': 4.0},
      );

      final simulated = await repository.getAllSessions(isSimulated: true);
      expect(simulated.length, equals(1));
      expect(simulated[0]['is_simulated'], isTrue);
    });
  });

  group('CSV 导出服务', () {
    late ExportService service;
    late PredictionResult mockResult;

    setUp(() {
      service = ExportService();
      mockResult = PredictionResult(
        sessionId: 'session_001',
        sampleId: 'sample_001',
        modelId: 'model_001',
        predictedValue: 0.35,
        unit: 'mg/cm2',
        sourceMode: 'simulated',
        resultStatus: 'valid',
        confidenceLevel: 'high',
        validRangeMin: 0.0,
        validRangeMax: 0.75,
        featureVector: {
          'dL': -8.5,
          'da': 3.5,
          'db': 2.1,
          'dS': -1.8,
          'whiteness_index': 0.24,
          'specular_ratio': 0.18,
          'glcm_contrast': 0.28,
          'glcm_energy': 0.78,
          'dL2': 72.25,
          'specular_ratio2': 0.0324,
        },
        hardwareProfileId: 'darkbox_v1',
        warnings: [],
        createdAt: DateTime.now(),
      );
    });

    test('生成 CSV 行', () {
      final row = service.generateCsvRow(
        sessionId: 'session_001',
        sampleId: 'sample_001',
        result: mockResult,
        roiAreaCm2: 4.0,
        baselineImagePath: '/path/to/baseline.jpg',
        saltedImagePath: '/path/to/salted.jpg',
      );

      expect(row, isNotEmpty);
      expect(row.contains('session_001'), isTrue);
      expect(row.contains('0.3500'), isTrue);
    });

    test('生成报告预览', () {
      final preview = service.generateReportPreview(
        sampleId: 'sample_001',
        result: mockResult,
        roiAreaCm2: 4.0,
        baselineImagePath: '/path/to/baseline.jpg',
        saltedImagePath: '/path/to/salted.jpg',
      );

      expect(preview.contains('FreshSalt Surface'), isTrue);
      expect(preview.contains('0.3500'), isTrue);
      expect(preview.contains('darkbox_v1'), isTrue);
    });
  });
}
