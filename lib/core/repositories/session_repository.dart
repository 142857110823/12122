import '../models/prediction_result.dart';
import '../models/feature_vector.dart';

/// 会话及结果仓储接口
/// 用于存储采集预测的完整会话记录
abstract class SessionRepository {
  /// 保存会话及其结果
  Future<void> saveSession({
    required String sessionId,
    required String sampleId,
    required PredictionResult result,
    required FeatureVector featureVector,
    required String baselineImagePath,
    required String saltedImagePath,
    required Map<String, dynamic> roiPolygon,
  });

  /// 获取单条会话记录
  Future<Map<String, dynamic>?> getSession(String sessionId);

  /// 获取所有会话记录（支持筛选）
  Future<List<Map<String, dynamic>>> getAllSessions({
    String? sampleId,
    String? modelId,
    bool? isSimulated,
    DateTime? startDate,
    DateTime? endDate,
  });

  /// 删除会话
  Future<void> deleteSession(String sessionId);

  /// 清空所有会话
  Future<void> clearAll();
}

/// 内存实现
class InMemorySessionRepository implements SessionRepository {
  final Map<String, Map<String, dynamic>> _sessionStore = {};

  @override
  Future<void> saveSession({
    required String sessionId,
    required String sampleId,
    required PredictionResult result,
    required FeatureVector featureVector,
    required String baselineImagePath,
    required String saltedImagePath,
    required Map<String, dynamic> roiPolygon,
  }) async {
    _sessionStore[sessionId] = {
      'session_id': sessionId,
      'sample_id': sampleId,
      'result': result.toJson(),
      'feature_vector': featureVector.toJson(),
      'baseline_image_path': baselineImagePath,
      'salted_image_path': saltedImagePath,
      'roi_polygon': roiPolygon,
      'created_at': DateTime.now().toIso8601String(),
      'is_simulated': result.sourceMode == 'simulated',
    };
  }

  @override
  Future<Map<String, dynamic>?> getSession(String sessionId) async {
    return _sessionStore[sessionId];
  }

  @override
  Future<List<Map<String, dynamic>>> getAllSessions({
    String? sampleId,
    String? modelId,
    bool? isSimulated,
    DateTime? startDate,
    DateTime? endDate,
  }) async {
    return _sessionStore.values
        .where((session) {
          if (sampleId != null && session['sample_id'] != sampleId) {
            return false;
          }
          if (modelId != null &&
              session['result']['model_id'] != modelId) {
            return false;
          }
          if (isSimulated != null &&
              session['is_simulated'] != isSimulated) {
            return false;
          }
          if (startDate != null) {
            final createdAt =
                DateTime.parse(session['created_at'] as String);
            if (createdAt.isBefore(startDate)) return false;
          }
          if (endDate != null) {
            final createdAt =
                DateTime.parse(session['created_at'] as String);
            if (createdAt.isAfter(endDate)) return false;
          }
          return true;
        })
        .toList()
        ..sort((a, b) => DateTime.parse(b['created_at'] as String)
            .compareTo(DateTime.parse(a['created_at'] as String)));
  }

  @override
  Future<void> deleteSession(String sessionId) async {
    _sessionStore.remove(sessionId);
  }

  @override
  Future<void> clearAll() async {
    _sessionStore.clear();
  }

  /// 获取所有会话数量
  int getSessionCount() => _sessionStore.length;
}
