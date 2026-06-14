import 'package:test/test.dart';
import '../core/orchestrator/freshsalt_orchestrator.dart';
import '../core/models/model_bundle.dart';
import '../core/models/click_validation_case.dart';
import '../core/services/model_bundle_service.dart';
import '../core/services/quality_control_service.dart';
import '../core/services/feature_extraction_service.dart';
import '../core/services/prediction_service.dart';
import '../core/services/click_validation_service.dart';
import '../core/repositories/session_repository.dart';
import '../core/repositories/click_validation_repository.dart';
import '../core/export/export_service.dart';
import '../core/demo/mock_data.dart';

void main() {
  group('FreshSalt APP 核心编绎', () {
    late FreshSaltAppOrchestrator orchestrator;
    late ModelBundleService modelBundleService;

    setUp(() {
      modelBundleService = ModelBundleService();
      final qualityControlService = QualityControlService();
      final featureExtractionService = FeatureExtractionService();
      final predictionService = PredictionService();
      final clickValidationRepo = InMemoryClickValidationRepository();
      final clickValidationService =
          ClickValidationService(repository: clickValidationRepo);
      final sessionRepository = InMemorySessionRepository();
      final exportService = ExportService();

      orchestrator = FreshSaltAppOrchestrator(
        modelBundleService: modelBundleService,
        qualityControlService: qualityControlService,
        featureExtractionService: featureExtractionService,
        predictionService: predictionService,
        clickValidationService: clickValidationService,
        sessionRepository: sessionRepository,
        exportService: exportService,
      );
    });

    test('完整采集预测流程 - 此刚项目不使用 UI 层', () async {
      // 加载模型包
      final bundle = ModelBundle.fromJson(mockModelBundle);
      await modelBundleService.loadModelBundle(bundle);
      await modelBundleService.activateModelBundle(bundle.modelId);

      // 设置处理配置
      orchestrator.setHardwareProfile('darkbox_v1');
      orchestrator.setSourceMode('simulated');

      // 执行编绎流程
      final result = await orchestrator.executeFullCaptureWorkflow(
        sessionId: 'session_001',
        sampleId: 'sample_001',
        imageMetadata: mockImageMetadataMedium,
        baselineImagePath: '/mock/baseline.jpg',
        saltedImagePath: '/mock/salted.jpg',
        roiPolygon: mockRoiPolygon,
      );

      expect(result['status'], isNotNull);
      expect(result['results'], isNotNull);
    });

    test('编绎处理质控失败的情况', () async {
      final bundle = ModelBundle.fromJson(mockModelBundle);
      await modelBundleService.loadModelBundle(bundle);
      await modelBundleService.activateModelBundle(bundle.modelId);

      orchestrator.setHardwareProfile('darkbox_v1');
      orchestrator.setSourceMode('simulated');

      // 使用过曝图像数据
      final result = await orchestrator.executeFullCaptureWorkflow(
        sessionId: 'session_002',
        sampleId: 'sample_002',
        imageMetadata: mockImageMetadataOverexposed,
        baselineImagePath: '/mock/baseline.jpg',
        saltedImagePath: '/mock/salted.jpg',
        roiPolygon: mockRoiPolygon,
      );

      expect(result['status'], equals('qc_failed'));
      expect(result['failure_reasons'], isNotEmpty);
    });

    test('编绎检查模型不可用', () async {
      // 不加载模型，直接执行
      orchestrator.setHardwareProfile('darkbox_v1');
      orchestrator.setSourceMode('simulated');

      final result = await orchestrator.executeFullCaptureWorkflow(
        sessionId: 'session_003',
        sampleId: 'sample_003',
        imageMetadata: mockImageMetadataMedium,
        baselineImagePath: '/mock/baseline.jpg',
        saltedImagePath: '/mock/salted.jpg',
        roiPolygon: mockRoiPolygon,
      );

      expect(result['status'], equals('error'));
      expect(result['error'], contains('模型包'));
    });
  });

  group('点击验证整合流程', () {
    late FreshSaltAppOrchestrator orchestrator;
    late ModelBundleService modelBundleService;

    setUp(() async {
      modelBundleService = ModelBundleService();
      final qualityControlService = QualityControlService();
      final featureExtractionService = FeatureExtractionService();
      final predictionService = PredictionService();
      final clickValidationRepo = InMemoryClickValidationRepository();
      final clickValidationService =
          ClickValidationService(repository: clickValidationRepo);
      final sessionRepository = InMemorySessionRepository();
      final exportService = ExportService();

      orchestrator = FreshSaltAppOrchestrator(
        modelBundleService: modelBundleService,
        qualityControlService: qualityControlService,
        featureExtractionService: featureExtractionService,
        predictionService: predictionService,
        clickValidationService: clickValidationService,
        sessionRepository: sessionRepository,
        exportService: exportService,
      );

      // 预载模型
      final bundle = ModelBundle.fromJson(mockModelBundle);
      await modelBundleService.loadModelBundle(bundle);
      await modelBundleService.activateModelBundle(bundle.modelId);
    });

    test('执行一键点击验证全链路', () async {
      final testCases = (mockClickValidationCases as List)
          .map((c) => ClickValidationCase.fromJson(
              Map<String, dynamic>.from(c as Map)))
          .toList();

      final result = await orchestrator.executeFullClickValidation(testCases);

      expect(result['total'], isNotNull);
      expect(result['passed'], isNotNull);
      expect(result['failed'], isNotNull);
      expect(result['logs'], isList);
    });
  });
}
