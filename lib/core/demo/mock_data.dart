/// 模拟模型包 - 用于演示和测试
final mockModelBundle = {
  'model_id': 'freshsalt_rgb_cucumber_darkbox_v1',
  'source': 'simulated',
  'sample_type': 'cucumber',
  'target': 'surface_NaCl_load_mg_cm2',
  'unit': 'mg/cm2',
  'valid_range_mg_cm2': [0.0, 0.75],
  'feature_order': [
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
  ],
  'coefficients': [
    0.018,
    -0.003,
    0.002,
    -0.011,
    0.21,
    0.15,
    0.006,
    -0.004,
    -0.0002,
    -0.03,
  ],
  'intercept': 0.01,
  'warnings': ['模拟模型仅用于交互验证，不代表真实检测性能'],
  'metadata': {'hardware_profile_id': 'darkbox_v1'},
};

/// 模拟图像元数据 - 低负载（0.05 mg/cm2）
final mockImageMetadataLow = {
  'saturation_ratio': 0.002,
  'laplacian_variance': 150.0,
  'gray_card_rsd': 0.01,
  'roi_area_cm2': 4.0,
  'roi_within_bounds': true,
  'color_dL': -2.5,
  'color_da': 1.2,
  'color_db': 0.8,
  'color_dS': -0.5,
  'whiteness_index': 0.08,
  'specular_ratio': 0.05,
  'glcm_contrast': 0.12,
  'glcm_energy': 0.85,
  'dL2': 6.25,
  'specular_ratio2': 0.0025,
  'roi_source': 'mock_image_low',
};

/// 模拟图像元数据 - 中等负载（0.35 mg/cm2）
final mockImageMetadataMedium = {
  'saturation_ratio': 0.003,
  'laplacian_variance': 155.0,
  'gray_card_rsd': 0.012,
  'roi_area_cm2': 4.0,
  'roi_within_bounds': true,
  'color_dL': -8.5,
  'color_da': 3.5,
  'color_db': 2.1,
  'color_dS': -1.8,
  'whiteness_index': 0.24,
  'specular_ratio': 0.18,
  'glcm_contrast': 0.28,
  'glcm_energy': 0.78,
  'dL2': 72.25,
  'specular_ratio2': 0.0324,
  'roi_source': 'mock_image_medium',
};

/// 模拟图像元数据 - 高负载（0.70 mg/cm2）
final mockImageMetadataHigh = {
  'saturation_ratio': 0.004,
  'laplacian_variance': 160.0,
  'gray_card_rsd': 0.015,
  'roi_area_cm2': 4.0,
  'roi_within_bounds': true,
  'color_dL': -15.2,
  'color_da': 6.8,
  'color_db': 4.5,
  'color_dS': -3.5,
  'whiteness_index': 0.45,
  'specular_ratio': 0.32,
  'glcm_contrast': 0.48,
  'glcm_energy': 0.68,
  'dL2': 231.04,
  'specular_ratio2': 0.1024,
  'roi_source': 'mock_image_high',
};

/// 模拟图像元数据 - 过曝失败案例
final mockImageMetadataOverexposed = {
  'saturation_ratio': 0.008, // 超过阈值 0.5%
  'laplacian_variance': 150.0,
  'gray_card_rsd': 0.01,
  'roi_area_cm2': 4.0,
  'roi_within_bounds': true,
  'color_dL': -5.0,
  'color_da': 2.0,
  'color_db': 1.5,
  'color_dS': -1.0,
  'whiteness_index': 0.12,
  'specular_ratio': 0.08,
  'glcm_contrast': 0.15,
  'glcm_energy': 0.82,
  'dL2': 25.0,
  'specular_ratio2': 0.0064,
  'roi_source': 'mock_image_overexposed',
};

/// 模拟图像元数据 - 模糊失败案例
final mockImageMetadataBlurry = {
  'saturation_ratio': 0.002,
  'laplacian_variance': 50.0, // 低于阈值 100.0
  'gray_card_rsd': 0.01,
  'roi_area_cm2': 4.0,
  'roi_within_bounds': true,
  'color_dL': -2.5,
  'color_da': 1.2,
  'color_db': 0.8,
  'color_dS': -0.5,
  'whiteness_index': 0.08,
  'specular_ratio': 0.05,
  'glcm_contrast': 0.12,
  'glcm_energy': 0.85,
  'dL2': 6.25,
  'specular_ratio2': 0.0025,
  'roi_source': 'mock_image_blurry',
};

/// 模拟图像元数据 - ROI 越界失败案例
final mockImageMetadataRoiOutOfBounds = {
  'saturation_ratio': 0.002,
  'laplacian_variance': 150.0,
  'gray_card_rsd': 0.01,
  'roi_area_cm2': 4.0,
  'roi_within_bounds': false, // ROI 越界
  'color_dL': -2.5,
  'color_da': 1.2,
  'color_db': 0.8,
  'color_dS': -0.5,
  'whiteness_index': 0.08,
  'specular_ratio': 0.05,
  'glcm_contrast': 0.12,
  'glcm_energy': 0.85,
  'dL2': 6.25,
  'specular_ratio2': 0.0025,
  'roi_source': 'mock_image_roi_out_of_bounds',
};

/// 模拟 ROI 多边形
final mockRoiPolygon = {
  'area': 4.0, // 4 cm2
  'width_cm': 2.0,
  'height_cm': 2.0,
  'center_x': 100.0,
  'center_y': 100.0,
  'within_bounds': true,
};

/// 模拟硬件配置
final mockHardwareProfile = {
  'hardware_profile_id': 'darkbox_v1',
  'camera': 'built_in',
  'light_source': 'led_ring',
  'roi_area_cm2': 4.0,
  'gray_card_type': 'X-Rite_ColorChecker',
};

/// 模拟点击验证用例
final mockClickValidationCases = [
  {
    'case_id': 'M01_HOME',
    'module': '首页',
    'action': '点击"开始采集预测"',
    'mock_input': {'source_mode': 'simulated'},
    'expected_output': {'route': 'capture_page', 'status': 'success'},
    'assertion_rule': '进入采集页面',
  },
  {
    'case_id': 'M02_MODEL',
    'module': '模型包管理',
    'action': '点击"启用模型"',
    'mock_input': {'model_id': 'freshsalt_rgb_cucumber_darkbox_v1'},
    'expected_output': {'status': 'success', 'active_model_id': 'freshsalt_rgb_cucumber_darkbox_v1'},
    'assertion_rule': '模型激活成���',
  },
  {
    'case_id': 'M03_QC_PASS',
    'module': '成像质控',
    'action': '点击"开始质控"',
    'mock_input': {'image_metadata': 'mock_image_medium'},
    'expected_output': {'qc_status': 'passed', 'all_checks': true},
    'assertion_rule': '质控通过',
  },
  {
    'case_id': 'M04_QC_FAIL_EXPOSURE',
    'module': '成像质控',
    'action': '点击"过曝案例"',
    'mock_input': {'image_metadata': 'mock_image_overexposed'},
    'expected_output': {'qc_status': 'failed', 'failed_checks': ['exposure']},
    'assertion_rule': '质控失败：过曝',
  },
  {
    'case_id': 'M05_CAPTURE_I0',
    'module': '基线采集',
    'action': '点击"使用模拟 I0"',
    'mock_input': {'image_type': 'baseline'},
    'expected_output': {'status': 'success', 'image_path_saved': true},
    'assertion_rule': '基线图保存成功',
  },
  {
    'case_id': 'M06_CAPTURE_I1',
    'module': '待测采集',
    'action': '点击"使用模拟 I1"',
    'mock_input': {'image_type': 'salted'},
    'expected_output': {'status': 'success', 'image_path_saved': true},
    'assertion_rule': '待测图保存成功',
  },
  {
    'case_id': 'M07_ROI',
    'module': 'ROI 确认',
    'action': '点击"确认 ROI"',
    'mock_input': {'roi_area': 4.0, 'within_bounds': true},
    'expected_output': {'status': 'success', 'roi_valid': true},
    'assertion_rule': 'ROI 面积有效',
  },
  {
    'case_id': 'M08_FEATURE',
    'module': '特征提取',
    'action': '点击"提取特征"',
    'mock_input': {'session_id': 'session_001'},
    'expected_output': {'status': 'success', 'feature_count': 10},
    'assertion_rule': '特征向量完整',
  },
  {
    'case_id': 'M09_PREDICT',
    'module': '模型推理',
    'action': '点击"计算结果"',
    'mock_input': {'feature_vector': 'mock_features_medium'},
    'expected_output': {'status': 'success', 'predicted_value': 0.35},
    'assertion_rule': '推理输出有效值',
  },
  {
    'case_id': 'M10_RESULT',
    'module': '结果详情',
    'action': '点击"查看结果"',
    'mock_input': {'prediction_result_id': 'result_001'},
    'expected_output': {'status': 'success', 'ui_complete': true},
    'assertion_rule': '结果页图表完整',
  },
  {
    'case_id': 'M11_SAVE',
    'module': '保存历史',
    'action': '点击"保存历史"',
    'mock_input': {'session_id': 'session_001'},
    'expected_output': {'status': 'success', 'saved': true},
    'assertion_rule': '历史记录保存成功',
  },
  {
    'case_id': 'M12_HISTORY',
    'module': '历史记录',
    'action': '点击历史记录',
    'mock_input': {},
    'expected_output': {'status': 'success', 'has_simulated_badge': true},
    'assertion_rule': '列表显示模拟徽标',
  },
  {
    'case_id': 'M13_ANALYSIS',
    'module': '分析总览',
    'action': '点击分析总览',
    'mock_input': {},
    'expected_output': {'status': 'success', 'charts_rendered': true},
    'assertion_rule': '图表显示',
  },
  {
    'case_id': 'M14_EXPORT',
    'module': 'CSV 导出',
    'action': '点击"复制 CSV"',
    'mock_input': {'session_id': 'session_001'},
    'expected_output': {'status': 'success', 'csv_fields_complete': true},
    'assertion_rule': 'CSV 字段完整',
  },
];
