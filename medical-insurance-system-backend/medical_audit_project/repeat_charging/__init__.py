"""
重复收费检测模块
Enhanced Duplicate Charging Detection Module

说明：为避免Django在应用注册阶段（apps.populate）导入模型导致的
AppRegistryNotReady错误，本模块的顶层不再导入包含模型的子模块。
请通过 `repeat_charging.integration` 使用对外接口。
"""

__version__ = "1.0.0"
__author__ = "Medical Audit System"

# 顶层不导入任何依赖模型的模块，避免初始化阶段触发模型加载。
# 外部入口请使用：from repeat_charging.integration import detect_enhanced_duplicate_charges

__all__ = []