# apps/engine/function_registry.py

"""
函数注册器：
1. 从 atomic.py、business.py、utils.py 加载本地写死的原子函数。
2. 从数据库 BusinessFunction 表加载动态生成的业务函数。
"""

import logging
from typing import Dict, Any
from django.apps import apps  # 核心新增：用于动态获取模型，防止循环导入

logger = logging.getLogger(__name__)


class FunctionRegistry:
    """函数注册器，管理规则执行时可用的函数"""
    
    def __init__(self):
        self._functions: Dict[str, Any] = {}
        # 初始化时立即加载函数
        self._load_functions()
    
    def _load_functions(self):
        """加载本地原子函数 + 数据库业务函数"""
        self._functions = {} # 重置，防止重复加载
        
        try:
            # -------------------------------------------------------
            # 1. 加载本地写死的原子函数 (atomic.py, business.py, utils.py)
            # -------------------------------------------------------
            from . import atomic, business, utils
            
            for module in [atomic, business, utils]:
                for name in dir(module):
                    obj = getattr(module, name)
                    # 只注册可调用的函数，且不注册私有函数(_开头)
                    if callable(obj) and not name.startswith('_'):
                        self._functions[name] = obj
                        logger.debug(f"注册本地函数: {name}")

            # -------------------------------------------------------
            # 2. 【核心新增】加载数据库里的动态业务函数
            # -------------------------------------------------------
            try:
                # 使用 apps.get_model 动态获取，防止循环引用
                # 因为 function_registry 被 engine 引用，engine 被 tasks 引用，tasks 被 models 引用...
                BusinessFunction = apps.get_model('rules', 'BusinessFunction')
                
                # 查询所有启用的动态函数
                # 注意：如果是第一次 migrate 数据库还没表，这步会报错，所以需要捕获异常
                db_funcs = BusinessFunction.objects.filter(is_active=True)
                
                for db_f in db_funcs:
                    self._register_dynamic_function(db_f.func_name, db_f.function_body)
                    
                if db_funcs.exists():
                    logger.info(f"成功加载 {db_funcs.count()} 个数据库业务函数")
                
            except LookupError:
                # 数据库迁移未完成时可能找不到 model
                logger.warning("跳过加载数据库函数：BusinessFunction 模型尚未就绪")
            except Exception as db_e:
                # 其他数据库错误（如表不存在）
                logger.warning(f"加载数据库业务函数失败 (可能是首次迁移或表不存在): {db_e}")

            logger.info(f"函数注册完成，共注册 {len(self._functions)} 个函数")
            
        except Exception as e:
            logger.error(f"加载函数注册器出错: {e}", exc_info=True)
            raise

    def _register_dynamic_function(self, name, code_str):
        """
        将字符串形式的代码转换为可执行函数并注册
        """
        try:
            # 准备执行环境
            # 允许动态函数调用已有的原子函数（如 get_value, check_limit）
            # 所以我们将 self._functions 作为全局变量传入
            exec_globals = self._functions.copy()
            exec_locals = {}
            
            # 执行代码字符串，这会在 exec_locals 中定义函数
            # 例如 code_str 是 "def is_acute_stroke(record): ..."
            exec(code_str, exec_globals, exec_locals)
            
            # 从作用域中取出函数对象
            if name in exec_locals:
                func_obj = exec_locals[name]
                self._functions[name] = func_obj
                logger.debug(f"动态注册数据库函数: {name}")
            else:
                logger.error(f"数据库函数定义错误: 代码中未找到名为 {name} 的函数")
                
        except Exception as e:
            logger.error(f"解析动态函数 {name} 失败: {e}")

    def get_safe_globals(self, medical_record: Dict, current_item: Dict) -> Dict[str, Any]:
        """
        获取安全的全局命名空间，用于 RuleExecutor 的 exec() 执行
        这里不需要改动逻辑，因为 _load_functions 已经把数据库里的函数放进 self._functions 了
        """
        safe_globals = {
            # 1. 内置函数白名单（限制危险函数，如 open, import 等）
            '__builtins__': {
                'len': len,
                'str': str,
                'int': int,
                'float': float,
                'bool': bool,
                'list': list,
                'dict': dict,
                'tuple': tuple,
                'set': set,
                'max': max,
                'min': min,
                'sum': sum,
                'abs': abs,
                'round': round,
                'range': range,
                'enumerate': enumerate,
                'zip': zip,
                'isinstance': isinstance,
                'type': type,
                'hasattr': hasattr,
                'getattr': getattr,
                'print': print, # 允许打印日志用于调试
            },
            
            # 2. 注册的所有函数 (包括本地原子函数 + 数据库业务函数)
            **self._functions,
            
            # 3. 数据上下文
            'medical_record': medical_record,
            'current_item': current_item,
            'record': medical_record,  # 别名，兼容旧代码习惯
        }
        
        return safe_globals
    
    def get_function(self, name: str):
        """获取指定名称的函数"""
        return self._functions.get(name)
    
    def list_functions(self) -> list:
        """列出所有已注册的函数名"""
        return list(self._functions.keys())


# 全局单例
_registry_instance = None

def get_registry() -> FunctionRegistry:
    """获取函数注册器单例"""
    global _registry_instance
    if _registry_instance is None:
        _registry_instance = FunctionRegistry()
    return _registry_instance

def reload_registry():
    """
    强制重载注册器（当数据库新增函数后调用）
    """
    global _registry_instance
    _registry_instance = FunctionRegistry()
    return _registry_instance