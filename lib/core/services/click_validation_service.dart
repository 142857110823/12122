import '../models/click_validation_case.dart';
import '../repositories/click_validation_repository.dart';

/// 点击验证服务
/// 驱动模拟测试用例的执行、断言和日志记录
class ClickValidationService {
  final ClickValidationRepository repository;

  ClickValidationService({required this.repository});

  /// 执行单个点击验证用例
  /// 返回是否通过断言
  Future<ClickValidationLog> executeClickCase({
    required ClickValidationCase testCase,
    required Future<Map<String, dynamic>> Function(Map<String, dynamic>)
        mockServiceCall,
  }) async {
    final startTime = DateTime.now();

    try {
      // 执行模拟服务调用
      final actualOutput = await mockServiceCall(testCase.mockInput);

      // 执行断言
      final passed = _performAssertion(
        expectedOutput: testCase.expectedOutput,
        actualOutput: actualOutput,
      );

      final duration = DateTime.now().difference(startTime).inMilliseconds;

      final log = ClickValidationLog(
        caseId: testCase.caseId,
        module: testCase.module,
        mockInput: testCase.mockInput,
        actualOutput: actualOutput,
        expectedOutput: testCase.expectedOutput,
        result: passed ? 'pass' : 'fail',
        durationMs: duration,
        errorMessage: passed ? null : _generateErrorMessage(
          expected: testCase.expectedOutput,
          actual: actualOutput,
        ),
        createdAt: DateTime.now(),
      );

      // 保存日志
      await repository.saveClickLog(log);

      return log;
    } catch (e) {
      final duration = DateTime.now().difference(startTime).inMilliseconds;

      final log = ClickValidationLog(
        caseId: testCase.caseId,
        module: testCase.module,
        mockInput: testCase.mockInput,
        actualOutput: {},
        expectedOutput: testCase.expectedOutput,
        result: 'fail',
        durationMs: duration,
        errorMessage: '异常: $e',
        createdAt: DateTime.now(),
      );

      await repository.saveClickLog(log);
      return log;
    }
  }

  /// 执行一键全链路验证
  /// 顺序执行多个用例并汇总结果
  Future<Map<String, dynamic>> executeFullChain(
    List<ClickValidationCase> testCases,
    Future<Map<String, dynamic>> Function(String, Map<String, dynamic>)
        moduleServiceCall,
  ) async {
    final logs = <ClickValidationLog>[];
    final startTime = DateTime.now();

    for (final testCase in testCases) {
      try {
        final actualOutput = await moduleServiceCall(
          testCase.module,
          testCase.mockInput,
        );
        final passed = _performAssertion(
          expectedOutput: testCase.expectedOutput,
          actualOutput: actualOutput,
        );

        final log = ClickValidationLog(
          caseId: testCase.caseId,
          module: testCase.module,
          mockInput: testCase.mockInput,
          actualOutput: actualOutput,
          expectedOutput: testCase.expectedOutput,
          result: passed ? 'pass' : 'fail',
          durationMs: 0,
          errorMessage: passed ? null : _generateErrorMessage(
            expected: testCase.expectedOutput,
            actual: actualOutput,
          ),
          createdAt: DateTime.now(),
        );
        logs.add(log);
      } catch (e) {
        logs.add(
          ClickValidationLog(
            caseId: testCase.caseId,
            module: testCase.module,
            mockInput: testCase.mockInput,
            actualOutput: {},
            expectedOutput: testCase.expectedOutput,
            result: 'fail',
            durationMs: 0,
            errorMessage: '异常: $e',
            createdAt: DateTime.now(),
          ),
        );
      }
    }

    // 保存所有日志
    for (final log in logs) {
      await repository.saveClickLog(log);
    }

    final totalDuration = DateTime.now().difference(startTime).inMilliseconds;
    final passedCount = logs.where((log) => log.isPassed).length;
    final failedCount = logs.where((log) => !log.isPassed).length;

    return {
      'total': logs.length,
      'passed': passedCount,
      'failed': failedCount,
      'total_duration_ms': totalDuration,
      'logs': logs.map((log) => {
            'case_id': log.caseId,
            'module': log.module,
            'result': log.result,
            'error_message': log.errorMessage,
          }).toList(),
    };
  }

  /// 执行断言
  bool _performAssertion({
    required Map<String, dynamic> expectedOutput,
    required Map<String, dynamic> actualOutput,
  }) {
    // 简单的等值断言
    for (final key in expectedOutput.keys) {
      if (!actualOutput.containsKey(key)) {
        return false;
      }
      if (actualOutput[key] != expectedOutput[key]) {
        return false;
      }
    }
    return true;
  }

  /// 生成错误消息
  String _generateErrorMessage({
    required Map<String, dynamic> expected,
    required Map<String, dynamic> actual,
  }) {
    final diffs = <String>[];
    for (final key in expected.keys) {
      if (!actual.containsKey(key)) {
        diffs.add('缺失字段: $key');
      } else if (actual[key] != expected[key]) {
        diffs.add('$key: 期望 ${expected[key]}, 实际 ${actual[key]}');
      }
    }
    return diffs.isNotEmpty ? diffs.join('; ') : '未知错误';
  }
}
