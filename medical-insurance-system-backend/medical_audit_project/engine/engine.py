# engine/engine.py

"""
规则引擎核心（重构版）
- 移除 Template 机制
- 直接遍历收费报告中的收费项目
- 根据收费项目匹配规则并执行
"""

import logging
from typing import Dict, List, Any, Optional
from .rule_executor import RuleExecutor
from rules.models import Rule

logger = logging.getLogger(__name__)


class RuleEngine:
    """规则引擎核心（重构版）"""
    
    def __init__(self, log_level=logging.INFO):
        """
        规则引擎核心（重构版）
        """
        self.logger = logging.getLogger("RuleEngine")
        self.logger.setLevel(log_level)
        self.executor = RuleExecutor()
    
    def audit_patient(
        self, 
        patient_data: Dict, 
        selected_rules: Optional[List[Rule]] = None,
        charge_section_path: str = "收费报告"
    ) -> List[Dict]:
        """
        审核病人数据
        
        :param patient_data: 病人病历数据（字典格式）
        :param selected_rules: 选定的规则列表，如果为None则使用所有启用的规则
        :param charge_section_path: 收费报告在病历数据中的路径，默认为 "收费报告"
        :return: 审查结果列表，每个结果格式为 {"passed": bool, "reason": str, "step": str, "ruleId": str, ...}
        """
        results = []
        
        try:
            # 1. 定位收费报告模块
            charge_items = self._get_charge_items(patient_data, charge_section_path)
            if not charge_items:
                self.logger.warning(f"未找到收费报告数据，路径: {charge_section_path}")
                return [{
                    "passed": True,
                    "reason": "未找到收费报告数据",
                    "step": "charge_extraction"
                }]
            
            self.logger.info(f"找到 {len(charge_items)} 条收费项目")
            
            # 2. 获取规则列表
            if selected_rules is None:
                rules = list(Rule.objects.filter(status=True))
            else:
                rules = list(selected_rules)
            
            if not rules:
                self.logger.warning("未找到可用的规则")
                return [{
                    "passed": True,
                    "reason": "未找到可用规则",
                    "step": "rule_lookup"
                }]
            
            self.logger.info(f"加载了 {len(rules)} 条规则")
            
            # 3. 遍历每条收费项目
            for idx, charge_item in enumerate(charge_items):
                self.logger.debug(f"处理收费项目 {idx + 1}/{len(charge_items)}: {charge_item.get('收费项目名称', 'N/A')}")
                
                # 4. 根据收费项目匹配规则
                matched_rules = self._match_rules(charge_item, rules)
                
                if not matched_rules:
                    continue
                
                self.logger.debug(f"收费项目匹配到 {len(matched_rules)} 条规则")
                
                # 5. 执行每条匹配的规则
                for rule in matched_rules:
                    if not rule.rule_code:
                        self.logger.warning(f"规则 {rule.rule_id} 没有规则代码，跳过")
                        continue
                    
                    try:
                        result = self.executor.execute_rule(
                            rule_code=rule.rule_code,
                            medical_record=patient_data,
                            current_item=charge_item,
                            rule_id=rule.rule_id
                        )
                        
                        # 添加规则信息到结果
                        result["ruleId"] = rule.rule_id
                        result["ruleDescription"] = rule.description
                        result["violation"] = not result.get("passed", False)
                        result["item"] = charge_item
                        
                        # 如果未通过，添加高亮信息
                        if not result.get("passed", False):
                            result["highlights"] = [{
                                "field_path": "收费报告",
                                "highlighted_text": str(charge_item)
                            }]
                        
                        results.append(result)
                        
                        if result.get("passed", False):
                            self.logger.debug(f"规则 {rule.rule_id} 校验通过")
                        else:
                            self.logger.info(f"规则 {rule.rule_id} 触发违规: {result.get('reason', 'N/A')}")
                            
                    except Exception as e:
                        error_msg = f"执行规则 {rule.rule_id} 时出错: {str(e)}"
                        self.logger.error(error_msg, exc_info=True)
                        results.append({
                            "passed": False,
                            "reason": error_msg,
                            "step": rule.rule_id,
                            "ruleId": rule.rule_id,
                            "status": "error"
                        })
            
            self.logger.info(f"审核完成，共生成 {len(results)} 条结果")
            return results
            
        except Exception as e:
            error_msg = f"审核过程中发生错误: {str(e)}"
            self.logger.error(error_msg, exc_info=True)
            return [{
                "passed": False,
                "reason": error_msg,
                "step": "engine_error",
                "status": "error"
            }]
    
    def _get_charge_items(self, patient_data: Dict, charge_section_path: str) -> List[Dict]:
        """
        从病历数据中提取收费项目列表
        
        :param patient_data: 病历数据
        :param charge_section_path: 收费报告路径，支持点分隔路径
        :return: 收费项目列表
        """
        if not patient_data:
            return []
        
        # 支持点分隔路径，如 "收费报告" 或 "费用明细.收费项目"
        keys = charge_section_path.split('.')
        current = patient_data
        
        for key in keys:
            if isinstance(current, dict):
                current = current.get(key)
            elif isinstance(current, list):
                # 如果遇到列表，返回列表本身（可能是嵌套结构）
                return current if isinstance(current[0], dict) else []
            else:
                return []
            
            if current is None:
                return []
        
        # 确保返回的是列表
        if isinstance(current, list):
            return [item for item in current if isinstance(item, dict)]
        elif isinstance(current, dict):
            # 如果是字典，尝试提取其中的列表字段
            for key in ['items', 'charges', '收费项目', '费用明细']:
                if key in current and isinstance(current[key], list):
                    return current[key]
            # 如果没有找到列表字段，返回空列表
            return []
        else:
            return []
    
    def _match_rules(self, charge_item: Dict, rules: List[Rule]) -> List[Rule]:
        """
        根据收费项目匹配规则
        
        匹配逻辑：
        1. 如果规则有 match_field 和 match_value，使用这些字段匹配
        2. 否则，使用 drug_name 字段匹配收费项目名称或代码
        
        :param charge_item: 收费项目字典
        :param rules: 规则列表
        :return: 匹配的规则列表
        """
        matched_rules = []
        
        for rule in rules:
            if not rule.status:
                continue
            
            # 优先使用 match_field 和 match_value
            if rule.match_field and rule.match_value:
                field_value = charge_item.get(rule.match_field, "")
                if str(field_value) == str(rule.match_value):
                    matched_rules.append(rule)
                    continue
            
            # 回退到使用 drug_name 匹配
            if rule.drug_name:
                item_name = charge_item.get("收费项目名称", "")
                item_code = charge_item.get("收费项目代码", "")
                
                # 匹配名称或代码
                if rule.drug_name in item_name or item_name == rule.drug_name:
                    matched_rules.append(rule)
                elif rule.drug_name in item_code or item_code == rule.drug_name:
                    matched_rules.append(rule)
        
        return matched_rules
