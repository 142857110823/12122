import '../models/click_validation_case.dart';

/// 点击验证日志仓储接口
abstract class ClickValidationRepository {
  /// 保存点击验证日志
  Future<void> saveClickLog(ClickValidationLog log);

  /// 获取所有点击验证日志
  Future<List<ClickValidationLog>> getAllClickLogs();

  /// 获取特定模块的日志
  Future<List<ClickValidationLog>> getClickLogsByModule(String module);

  /// 清空所有日志
  Future<void> clearAll();
}

/// 内存实现
class InMemoryClickValidationRepository implements ClickValidationRepository {
  final List<ClickValidationLog> _logs = [];

  @override
  Future<void> saveClickLog(ClickValidationLog log) async {
    _logs.add(log);
  }

  @override
  Future<List<ClickValidationLog>> getAllClickLogs() async {
    return List.from(_logs);
  }

  @override
  Future<List<ClickValidationLog>> getClickLogsByModule(String module) async {
    return _logs.where((log) => log.module == module).toList();
  }

  @override
  Future<void> clearAll() async {
    _logs.clear();
  }

  /// 获取 pass/fail 统计
  Map<String, int> getPassFailSummary() {
    return {
      'total': _logs.length,
      'passed': _logs.where((log) => log.isPassed).length,
      'failed': _logs.where((log) => !log.isPassed).length,
    };
  }
}
