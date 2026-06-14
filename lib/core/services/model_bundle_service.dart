import 'package:flutter/foundation.dart';
import '../models/model_bundle.dart';

/// 模型包管理服务
/// 负责加载、验证、管理模型包，处理激活和禁用
class ModelBundleService {
  ModelBundle? _activeModelBundle;
  final Map<String, ModelBundle> _modelCache = {};

  /// 获取当前激活的模型包
  ModelBundle? get activeModel => _activeModelBundle;

  /// 加载模型包并验证
  /// 返回验证错误列表，空列表表示验证成功
  Future<List<String>> loadModelBundle(ModelBundle bundle) async {
    try {
      // 验证模型包完整性
      final validationErrors = bundle.validate();
      if (validationErrors.isNotEmpty) {
        return validationErrors;
      }

      // 缓存模型包
      _modelCache[bundle.modelId] = bundle;
      return [];
    } catch (e) {
      return ['模型包加载失败: $e'];
    }
  }

  /// 激活指定的模型包
  Future<List<String>> activateModelBundle(String modelId) async {
    try {
      if (!_modelCache.containsKey(modelId)) {
        return ['模型包不存在: $modelId'];
      }

      _activeModelBundle = _modelCache[modelId];
      return [];
    } catch (e) {
      return ['激活模型包失败: $e'];
    }
  }

  /// 禁用当前激活的模型包
  void deactivateModelBundle() {
    _activeModelBundle = null;
  }

  /// 获取所有缓存的模型包
  List<ModelBundle> getCachedModelBundles() {
    return _modelCache.values.toList();
  }

  /// 检查硬件配置是否与模型匹配
  /// 硬件配置通过 metadata 中的 hardware_profile_id 验证
  bool validateHardwareCompatibility(
    String currentHardwareProfileId,
    ModelBundle bundle,
  ) {
    final requiredProfile =
        bundle.metadata['hardware_profile_id'] as String?;
    if (requiredProfile == null) return true; // 如果模型不要求特定硬件，则兼容
    return currentHardwareProfileId == requiredProfile;
  }

  /// 检查结果是否在模型有效范围内
  bool isResultInValidRange(double value, ModelBundle bundle) {
    return value >= bundle.validRange[0] && value <= bundle.validRange[1];
  }
}
