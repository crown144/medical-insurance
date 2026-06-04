# engine/template_executor.py (完整修正版)

import logging
import json
import functools
from typing import Dict, List, Any
from .predefined_functions import eval_logic_expression # 导入新的辅助函数
from rules.models import Rule, MedicalCode
from .predefined_functions import PREDEFINED_FUNCTIONS_MAP

class TemplateExecutor:
    def __init__(self):
        self.logger = logging.getLogger("TemplateExecutor")
        self.logger.setLevel(logging.DEBUG)
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            handler.setFormatter(formatter)
            handler.setLevel(logging.DEBUG)
            self.logger.addHandler(handler)
        # 移除实例变量，避免状态污染
    
    def execute_template(self, template: Dict, patient_data: Dict, selected_rules: List = None) -> List[Dict]:
        results = []
        # 每次执行都创建全新的variables字典，避免状态污染
        context = {"data": patient_data, "variables": {}, "selected_rules": selected_rules}
        template_id = template.get('templateId')
        steps = template.get("steps", [])
        self.logger.info(f"开始执行模板: {template_id}")
        self.logger.debug(f"模板包含 {len(steps)} 个步骤，初始上下文字段: {list(context['variables'].keys())}")
        for index, step in enumerate(steps):
            self.logger.debug(f"开始执行第 {index + 1}/{len(steps)} 个步骤: {step.get('stepId', 'unknown')} - 类型 {step.get('type')}")
            self._execute_step(step, context, results)
        self.logger.info(f"模板执行完成，共生成 {len(results)} 条结果")
        self.logger.debug(f"模板执行结果明细: {json.dumps(results, ensure_ascii=False, default=str)[:2000]}")
        return results

    def _execute_step(self, step: Dict, context: Dict, results: List):
        step_type = step.get("type")
        step_id = step.get("stepId", "unknown")
        self.logger.debug(f"执行步骤: {step_id} (类型: {step_type})，当前变量: {list(context['variables'].keys())}")
        if step_type == "field_extraction":
            self._execute_extraction(step, context, results)
        elif step_type == "loop":
            self._execute_loop(step, context, results)
        elif step_type == "rule_lookup":
            self._execute_rule_lookup(step, context, results)
        else:
            msg = f"不支持的步骤类型: {step_type}"
            results.append({"step": step_id, "status": "error", "message": msg})
            self.logger.error(msg)

    def _execute_extraction(self, step: Dict, context: Dict, results: List):
        path = step.get("path", "")
        output_var = step.get("outputVariable", "")
        step_id = step.get("stepId", "unknown")
        if not path or not output_var:
            msg = "字段提取步骤缺少path或outputVariable参数"
            results.append({"step": step_id, "status": "error", "message": msg})
            self.logger.error(msg)
            return
        try:
            value = self._get_value_from_path(context["data"], path)
            context["variables"][output_var] = value
            preview = str(value)
            if preview and len(preview) > 200:
                preview = preview[:200] + "..."
            self.logger.debug(f"提取字段成功: {path} -> {output_var} = {preview}")
            if value is None:
                self.logger.warning(f"提取字段结果为 None, 路径: {path}, 输出变量: {output_var}")
        except Exception as e:
            msg = f"字段提取失败: {e}"
            results.append({"step": step_id, "status": "error", "message": msg})
            self.logger.error(msg, exc_info=True)
    
    def _execute_loop(self, step: Dict, context: Dict, results: List):
        collection_var = step.get("collection", "")
        item_var = step.get("itemVariable", "")
        substeps = step.get("steps", [])
        
        if not collection_var or not item_var:
            self.logger.error("循环步骤缺少 collection 或 itemVariable 配置")
            return
            
        collection = context["variables"].get(collection_var, [])
        if collection is None:
            self.logger.warning(f"循环集合变量 '{collection_var}' 为空，跳过循环")
            return
        if not isinstance(collection, list):
            if isinstance(collection, dict):
                self.logger.warning(f"循环集合变量 '{collection_var}' 类型为 dict，尝试拉平成列表，原始键: {list(collection.keys())}")
                flattened_items = []
                for key, value in collection.items():
                    if isinstance(value, list):
                        for child in value:
                            if isinstance(child, dict):
                                item_copy = child.copy()
                                item_copy.setdefault("__group__", key)
                                item_copy = self._normalize_item_fields(item_copy)
                                flattened_items.append(item_copy)
                            else:
                                flattened_items.append({"__group__": key, "value": child})
                    elif isinstance(value, dict):
                        item_copy = value.copy()
                        item_copy.setdefault("__group__", key)
                        item_copy = self._normalize_item_fields(item_copy)
                        flattened_items.append(item_copy)
                    elif value is not None:
                        flattened_items.append({"__group__": key, "value": value})
                collection = flattened_items
                context["variables"][collection_var] = collection
                self.logger.debug(f"循环集合变量 '{collection_var}' 已转换为 {len(collection)} 个元素的列表")
            else:
                self.logger.warning(f"循环集合变量 '{collection_var}' 类型为 {type(collection)}, 无法遍历，跳过循环")
                return

        if isinstance(collection, list):
            normalized_collection = []
            for element in collection:
                if isinstance(element, dict):
                    normalized_collection.append(self._normalize_item_fields(element))
                else:
                    normalized_collection.append(element)
            collection = normalized_collection
            context["variables"][collection_var] = collection

        self.logger.debug(f"循环将遍历 {len(collection)} 个元素，集合变量: {collection_var}")
        
        for idx, item in enumerate(collection):
            preview = str(item)
            if preview and len(preview) > 200:
                preview = preview[:200] + "..."
            self.logger.debug(f"循环第 {idx + 1}/{len(collection)} 次迭代，itemVariable: {item_var}，元素预览: {preview}")
            loop_context_variables = context["variables"].copy()
            loop_context_variables[item_var] = item
            loop_context_variables["current_item"] = item
            
            sub_context = {
                "data": context["data"],
                "variables": loop_context_variables,
                "selected_rules": context.get("selected_rules")
            }
            for substep in substeps:
                self._execute_step(substep, sub_context, results)
        self.logger.debug(f"循环步骤执行完成: collection={collection_var}, itemVariable={item_var}")
   
    def _execute_rule_lookup(self, step: Dict, context: Dict, results: List):
        step_id = step.get("stepId", "unknown")
        rule_lookup = step.get("ruleLookup", {})
        lookup_key = rule_lookup.get("key") 

        if not lookup_key:
            msg = f"步骤 {step_id}: ruleLookup缺少key参数"
            results.append({"step": step_id, "status": "error", "message": msg})
            self.logger.error(msg)
            return
            
        medical_code = self._get_value_from_context(context, lookup_key)
        if not medical_code:
            self.logger.warning(f"在路径 '{lookup_key}' 未找到药品代码，上下文变量: {list(context['variables'].keys())}")
            return

        self.logger.debug(f"步骤 {step_id}: 解析到药品代码 {medical_code}")

        # --- 变量作用域修正 ---
        drug_name = None
        relevant_rules = Rule.objects.none() # 初始化为空的查询集
        
        try:
            medical_item = MedicalCode.objects.get(code=medical_code)
            drug_name = medical_item.name
            self.logger.debug(f"步骤 {step_id}: 药品名称 {drug_name}")
            
            # 获取基础规则查询集
            base_rules = Rule.objects.filter(drug_name__iexact=drug_name, status=True)
            self.logger.debug(f"步骤 {step_id}: 命中基础规则 {base_rules.count()} 条")
            
            # 如果有选定的规则，则进一步过滤
            selected_rules = context.get("selected_rules")
            if selected_rules is not None:
                # 提取规则ID列表
                selected_rule_ids = [rule.rule_id for rule in selected_rules]
                relevant_rules = base_rules.filter(rule_id__in=selected_rule_ids)
                self.logger.debug(f"步骤 {step_id}: 过滤选中规则后剩余 {relevant_rules.count()} 条 (选中ID: {selected_rule_ids})")
            else:
                relevant_rules = base_rules
                self.logger.debug(f"步骤 {step_id}: 使用全部基础规则 {relevant_rules.count()} 条")
        except MedicalCode.DoesNotExist:
            self.logger.error(f"数据库中未找到代码为 '{medical_code}' 的药品。")
            return
        except Exception as e:
            self.logger.error(f"数据库查询规则时出错: {e}")
            return

        if not relevant_rules.exists():
            self.logger.info(f"步骤 {step_id}: 针对药品 {drug_name} 未命中可用规则")
            return

        for rule_obj in relevant_rules:
            try:
                rule_context = {
                    "data": context["data"],
                    "variables": context["variables"],
                    **PREDEFINED_FUNCTIONS_MAP,
                    "getMedication": lambda: drug_name,
                }
                logic_preview = (rule_obj.logic_expression or "").strip()
                if logic_preview and len(logic_preview) > 500:
                    logic_preview = logic_preview[:500] + "..."
                self.logger.debug(f"步骤 {step_id}: 执行规则 {rule_obj.rule_id}, 逻辑表达式预览: {logic_preview}")
                # --- 使用新的 eval 辅助函数 ---
                eval_result = eval_logic_expression(rule_obj.logic_expression, rule_context)
                self.logger.debug(f"步骤 {step_id}: 规则 {rule_obj.rule_id} 计算结果: {eval_result}")
                is_pass = eval_result["pass"]
                evidence = eval_result.get("evidence", [])
                reference_values = eval_result.get("reference_values", [])
                
                # 构造 problem 字段

                if not is_pass and evidence:
                    import re
                    first_path = evidence[0].get('field_path', '')
                    # 去除开头的$., 所有[数字]，以及多余的点
                    path_str = re.sub(r'^\$\.', '', first_path)  # 去掉开头$.
                    path_str = re.sub(r'\[\d+\]', '', path_str) # 去掉所有[数字]
                    path_str = re.sub(r'\.+', '.', path_str) if path_str.startswith('.') else path_str # 防止多余点
                    path_str = path_str.lstrip('.') # 去掉前导点
                    values = [item.get('highlighted_text', '') for item in evidence]
                    values_str = '、'.join(values)
                    ref_str = '、'.join([str(v) for v in reference_values]) if reference_values else ''
                    problem = f"提取路径：{path_str} 内容：{{{values_str}}} 不匹配参考值：{{{ref_str}}}"
                else:
                    problem = None

                result = {
                    "step": step_id,
                    "ruleId": rule_obj.rule_id,
                    "ruleDescription": rule_obj.description,
                    "violation": not bool(is_pass),
                    "item": context["variables"].get("current_item", {}),
                    "problem": None if is_pass else problem,
                    "highlights": [] if is_pass else evidence
                }
                results.append(result)
                if is_pass:
                    self.logger.debug(f"步骤 {step_id}: 规则 {rule_obj.rule_id} 校验通过")
                else:
                    self.logger.info(f"步骤 {step_id}: 规则 {rule_obj.rule_id} 触发违规，证据数量: {len(evidence)}")
            except Exception as e:
                error_msg = f"执行规则 '{rule_obj.rule_id}' 失败: {e}"
                self.logger.error(error_msg, exc_info=True)
                results.append({"step": step_id, "ruleId": rule_obj.rule_id, "status": "error", "message": error_msg})
    
    # --- 确保下面这两个方法有正确的缩进 ---
    def _get_value_from_context(self, context: Dict, path: str) -> Any:
        if not path: return None
        parts = path.split('.')
        if parts[0] in context["variables"]:
            current = context["variables"][parts[0]]
            remaining_path = '.'.join(parts[1:])
            if not remaining_path:
                return current
            return self._get_value_from_path(current, remaining_path)
        return self._get_value_from_path(context["data"], path)
        
    def _get_value_from_path(self, data: Any, path: str) -> Any:
        if not path: return data
        keys = path.split('.')
        current = data
        for key in keys:
            if current is None: return None
            if isinstance(current, dict):
                current = current.get(key)
            elif isinstance(current, list) and key.isdigit():
                idx = int(key)
                current = current[idx] if 0 <= idx < len(current) else None
            else:
                return None
        return current

    def _normalize_item_fields(self, item: Any) -> Any:
        if not isinstance(item, dict):
            return item
        normalized = dict(item)
        alias_map = {
            "药品国家编码": [
                "医保药品代码-国家",
                "药物国家编码",
                "药品国家编码_国家库",
            ]
        }
        for target_key, aliases in alias_map.items():
            if normalized.get(target_key):
                continue
            for alias_key in aliases:
                alias_value = normalized.get(alias_key)
                if alias_value:
                    normalized[target_key] = alias_value
                    break
        return normalized