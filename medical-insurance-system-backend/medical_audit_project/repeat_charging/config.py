"""
重复收费检测配置模块
Configuration Module for Duplicate Charging Detection
"""

import os
from typing import Dict, Any, Optional


class RepeatChargingConfig:
    """重复收费检测配置管理"""
    
    def __init__(self):
        self.config = self._load_default_config()
        self._load_environment_config()
    
    def _load_default_config(self) -> Dict[str, Any]:
        """加载默认配置"""
        return {
            # 基础检测配置
            'basic_detection': {
                'enabled': True,
                'time_tolerance_hours': 2,  # 时间容差（小时）
                'ignore_codes': ['xxx', 'XXX', '', 'null', 'NULL'],  # 忽略的代码
                'min_amount_threshold': 0.01,  # 最小金额阈值
            },
            
            # 组套检测配置
            'package_detection': {
                'enabled': True,
                'require_multiple_orders': True,  # 需要多个医嘱代码
                'min_package_count': 2,  # 最少组套数量
            },
            
            # AI分析配置
            'ai_analysis': {
                'enabled': False,  # 默认禁用，需要API密钥
                'deepseek_api_key': None,
                'deepseek_base_url': 'https://api.deepseek.com',
                'model_name': 'deepseek-chat',
                'max_tokens': 50,
                'temperature': 0.1,
                'timeout_seconds': 30,
                'retry_count': 3,
            },
            
            # 输出格式配置
            'output_format': {
                'include_highlights': True,
                'include_details': True,
                'severity_levels': ['low', 'medium', 'high'],
                'amount_format': 'yuan',  # yuan, thousand, wan
            },
            
            # 日志配置
            'logging': {
                'level': 'INFO',
                'enable_detailed_logs': False,
                'log_ai_requests': False,
            },
            
            # 性能配置
            'performance': {
                'max_records_per_batch': 1000,
                'enable_parallel_processing': False,
                'cache_ai_results': True,
            }
        }
    
    def _load_environment_config(self):
        """从环境变量加载配置"""
        # DeepSeek API配置
        api_key = os.getenv('DEEPSEEK_API_KEY')
        if api_key:
            self.config['ai_analysis']['deepseek_api_key'] = api_key
            self.config['ai_analysis']['enabled'] = True
            
        base_url = os.getenv('DEEPSEEK_BASE_URL')
        if base_url:
            self.config['ai_analysis']['deepseek_base_url'] = base_url
            
        # 其他环境变量
        log_level = os.getenv('REPEAT_CHARGING_LOG_LEVEL')
        if log_level:
            self.config['logging']['level'] = log_level.upper()
    
    def get(self, key_path: str, default: Any = None) -> Any:
        """
        获取配置值
        
        Args:
            key_path: 配置键路径，如 'ai_analysis.enabled'
            default: 默认值
            
        Returns:
            配置值
        """
        keys = key_path.split('.')
        value = self.config
        
        try:
            for key in keys:
                value = value[key]
            return value
        except (KeyError, TypeError):
            return default
    
    def set(self, key_path: str, value: Any):
        """
        设置配置值
        
        Args:
            key_path: 配置键路径
            value: 配置值
        """
        keys = key_path.split('.')
        config = self.config
        
        for key in keys[:-1]:
            if key not in config:
                config[key] = {}
            config = config[key]
            
        config[keys[-1]] = value
    
    def update_ai_config(self, api_key: str, base_url: Optional[str] = None):
        """
        更新AI配置
        
        Args:
            api_key: API密钥
            base_url: API基础URL
        """
        self.config['ai_analysis']['deepseek_api_key'] = api_key
        self.config['ai_analysis']['enabled'] = True
        
        if base_url:
            self.config['ai_analysis']['deepseek_base_url'] = base_url
    
    def get_ai_config(self) -> Dict[str, Any]:
        """获取AI配置"""
        return self.config['ai_analysis'].copy()
    
    def is_ai_enabled(self) -> bool:
        """检查AI是否启用"""
        return (self.config['ai_analysis']['enabled'] and 
                self.config['ai_analysis']['deepseek_api_key'] is not None)
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return self.config.copy()


def load_config():
    """加载配置"""
    return config.to_dict()


def get_detection_config():
    """获取检测配置"""
    return load_config()


# 全局配置实例
config = RepeatChargingConfig()