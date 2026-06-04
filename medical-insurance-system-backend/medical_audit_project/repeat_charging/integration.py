"""
系统集成接口模块
System Integration Interface Module
"""

import logging
from typing import List, Dict, Any, Optional

from .core import EnhancedDuplicateDetector
from .config import config

logger = logging.getLogger(__name__)


def detect_enhanced_duplicate_charges(patient_data) -> Dict[str, Any]:
    """
    增强重复收费检测主接口
    
    这是与现有系统集成的主要接口函数，支持多种数据格式
    
    Args:
        patient_data: 病历数据，支持以下格式：
                     1. 字典格式：包含"收费报告"字段
                     2. 列表格式：直接的收费记录列表
        
    Returns:
        检测结果字典，包含：
        - violations: list, 违规列表
        - summary: dict, 检测摘要
        - metadata: dict, 元数据信息
    """
    try:
        # 数据格式标准化
        charge_data = None
        
        if isinstance(patient_data, dict):
            if "收费报告" in patient_data:
                charge_data = patient_data["收费报告"]
            else:
                logger.warning("[EnhancedIntegration] 病历JSON中未找到收费报告数据")
                return {"violations": [], "summary": {}, "metadata": {}}
        elif isinstance(patient_data, list):
            # 直接的列表格式，转换为标准格式
            charge_data = patient_data
        else:
            logger.error("[EnhancedIntegration] 不支持的输入数据格式")
            return {"violations": [], "summary": {}, "metadata": {}}
            
        if not charge_data:
            logger.warning("[EnhancedIntegration] 收费数据为空")
            return {"violations": [], "summary": {}, "metadata": {}}
            
        # 创建检测器实例
        detector = EnhancedDuplicateDetector(
            enable_ai=config.is_ai_enabled(),
            deepseek_config=config.get_ai_config() if config.is_ai_enabled() else None
        )
        
        # 构造标准格式的数据
        standard_data = {"收费报告": charge_data}
        
        # 执行检测
        violations = detector.detect_all_violations(standard_data)
        
        # 记录检测摘要
        summary = detector.get_detection_summary(violations)
        logger.info(f"[EnhancedIntegration] 检测完成: {summary}")
        
        # 返回标准格式的结果
        return {
            "violations": violations,
            "summary": summary,
            "metadata": {
                "input_format": "dict" if isinstance(patient_data, dict) else "list",
                "charge_count": len(charge_data),
                "detection_config": config.to_dict()
            }
        }
        
    except Exception as e:
        logger.error(f"[EnhancedIntegration] 检测过程发生错误: {e}")
        return {"violations": [], "summary": {}, "metadata": {"error": str(e)}}


def configure_ai_analysis(api_key: str, base_url: Optional[str] = None) -> bool:
    """
    配置AI分析功能
    
    Args:
        api_key: DeepSeek API密钥
        base_url: API基础URL
        
    Returns:
        配置是否成功
    """
    try:
        config.update_ai_config(api_key, base_url)
        logger.info("[EnhancedIntegration] AI分析配置更新成功")
        return True
    except Exception as e:
        logger.error(f"[EnhancedIntegration] AI分析配置失败: {e}")
        return False


def get_detection_config() -> Dict[str, Any]:
    """
    获取当前检测配置
    
    Returns:
        配置信息
    """
    return {
        'basic_detection_enabled': config.get('basic_detection.enabled'),
        'package_detection_enabled': config.get('package_detection.enabled'),
        'ai_analysis_enabled': config.is_ai_enabled(),
        'time_tolerance_hours': config.get('basic_detection.time_tolerance_hours'),
        'min_package_count': config.get('package_detection.min_package_count'),
        'version': '1.0.0'
    }


def validate_patient_data(patient_json: Dict[str, Any]) -> Dict[str, Any]:
    """
    验证病历数据格式
    
    Args:
        patient_json: 病历数据
        
    Returns:
        验证结果
    """
    validation_result = {
        'valid': True,
        'errors': [],
        'warnings': [],
        'data_summary': {}
    }
    
    try:
        # 检查基本结构
        if not isinstance(patient_json, dict):
            validation_result['valid'] = False
            validation_result['errors'].append('数据不是字典格式')
            return validation_result
            
        # 检查收费报告
        fee_data = patient_json.get("收费报告", [])
        if not fee_data:
            validation_result['warnings'].append('未找到收费报告数据')
        elif not isinstance(fee_data, list):
            validation_result['errors'].append('收费报告数据格式错误，应为列表')
            validation_result['valid'] = False
        else:
            validation_result['data_summary']['fee_records_count'] = len(fee_data)
            
            # 检查收费记录格式
            valid_records = 0
            for i, record in enumerate(fee_data):
                if isinstance(record, dict):
                    if record.get('收费项目代码') and record.get('收费项目名称'):
                        valid_records += 1
                    else:
                        validation_result['warnings'].append(f'第{i+1}条收费记录缺少必要字段')
                else:
                    validation_result['warnings'].append(f'第{i+1}条收费记录格式错误')
                    
            validation_result['data_summary']['valid_records_count'] = valid_records
            
            if valid_records == 0:
                validation_result['warnings'].append('没有有效的收费记录')
                
    except Exception as e:
        validation_result['valid'] = False
        validation_result['errors'].append(f'数据验证过程出错: {str(e)}')
        
    return validation_result


def get_module_status() -> Dict[str, Any]:
    """
    获取模块状态信息
    
    Returns:
        模块状态
    """
    try:
        from .ai_analyzer import AIViolationAnalyzer
        
        # 测试AI分析器
        ai_analyzer = None
        if config.is_ai_enabled():
            ai_analyzer = AIViolationAnalyzer(config.get_ai_config())
            
        return {
            'module_version': '1.0.0',
            'basic_detection_available': True,
            'package_detection_available': True,
            'ai_analysis_available': ai_analyzer is not None and ai_analyzer.enabled,
            'ai_client_status': 'connected' if (ai_analyzer and ai_analyzer.client) else 'disconnected',
            'configuration': get_detection_config(),
            'dependencies': {
                'pandas_available': True,
                'openai_available': True if ai_analyzer else False
            }
        }
        
    except Exception as e:
        logger.error(f"[EnhancedIntegration] 获取模块状态失败: {e}")
        return {
            'module_version': '1.0.0',
            'status': 'error',
            'error': str(e)
        }


# 向后兼容的别名
detect_duplicate_charges_enhanced = detect_enhanced_duplicate_charges