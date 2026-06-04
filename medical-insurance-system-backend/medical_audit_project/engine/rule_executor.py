# engine/rule_executor.py

"""
规则执行器：动态执行规则代码
"""

import logging
from typing import Dict, Any, Optional
from .function_registry import get_registry

logger = logging.getLogger(__name__)


class RuleExecutor:
    """规则执行器，使用 exec() 动态执行规则代码"""
    
    def __init__(self):
        self.registry = get_registry()
        self.logger = logging.getLogger(self.__class__.__name__)
    
    def execute_rule(
        self, 
        rule_code: str, 
        medical_record: Dict, 
        current_item: Dict,
        rule_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        执行规则代码
        
        :param rule_code: 规则代码字符串（完整的函数定义）
        :param medical_record: 完整病历数据
        :param current_item: 当前收费项
        :param rule_id: 规则ID（用于日志）
        :return: 执行结果 {"passed": bool, "reason": str, "step": str}
        """
        if not rule_code or not rule_code.strip():
            return {
                "passed": True,
                "reason": "规则代码为空",
                "step": rule_id or "unknown"
            }
        
        try:
            # 准备执行环境
            safe_globals = self.registry.get_safe_globals(medical_record, current_item)
            safe_locals = {}
            
            # 执行规则代码（定义函数）
            self.logger.debug(f"执行规则代码 (rule_id={rule_id}):\n{rule_code[:200]}...")
            exec(rule_code, safe_globals, safe_locals)
            
            # 查找 execute_rule 函数
            if 'execute_rule' not in safe_locals:
                # 如果不在 locals，可能在 globals
                execute_func = safe_globals.get('execute_rule')
            else:
                execute_func = safe_locals['execute_rule']
            
            if not execute_func or not callable(execute_func):
                return {
                    "passed": False,
                    "reason": "规则代码中未找到 execute_rule 函数",
                    "step": rule_id or "unknown"
                }
            
            # 调用 execute_rule 函数
            result = execute_func(medical_record, current_item)
            
            # 标准化返回结果
            if isinstance(result, bool):
                return {
                    "passed": result,
                    "reason": "通过" if result else "未通过",
                    "step": rule_id or "unknown"
                }
            elif isinstance(result, dict):
                # 确保包含必要字段
                return {
                    "passed": result.get("passed", result.get("pass", False)),
                    "reason": result.get("reason", result.get("message", "")),
                    "step": result.get("step", rule_id or "unknown"),
                    **{k: v for k, v in result.items() if k not in ["passed", "pass", "reason", "message", "step"]}
                }
            else:
                return {
                    "passed": False,
                    "reason": f"规则返回了意外的类型: {type(result)}",
                    "step": rule_id or "unknown"
                }
                
        except Exception as e:
            error_msg = f"执行规则时出错: {str(e)}"
            self.logger.error(f"规则执行失败 (rule_id={rule_id}): {error_msg}", exc_info=True)
            return {
                "passed": False,
                "reason": error_msg,
                "step": rule_id or "unknown"
            }

