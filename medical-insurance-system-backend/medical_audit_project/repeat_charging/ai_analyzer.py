"""
AI分析模块 - 假性违规过滤
AI Analyzer Module for False Positive Filtering
"""

import logging
from typing import List, Dict, Any, Optional
import json

logger = logging.getLogger(__name__)

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None
    logger.warning("[AIAnalyzer] OpenAI库未安装，AI分析功能将被禁用")


class AIViolationAnalyzer:
    """AI违规分析器"""
    
    def __init__(self, deepseek_config: Optional[Dict] = None):
        """
        初始化AI分析器
        
        Args:
            deepseek_config: DeepSeek API配置
        """
        self.client = None
        self.enabled = False
        
        if deepseek_config and OpenAI is not None:
            try:
                api_key = deepseek_config.get('api_key')
                base_url = deepseek_config.get('base_url', 'https://api.deepseek.com')
                
                if api_key:
                    self.client = OpenAI(api_key=api_key, base_url=base_url)
                    self.enabled = True
                    logger.info("[AIAnalyzer] DeepSeek客户端初始化成功")
                else:
                    logger.warning("[AIAnalyzer] 未提供API密钥，AI分析功能禁用")
            except Exception as e:
                logger.error(f"[AIAnalyzer] 初始化DeepSeek客户端失败: {e}")
                self.client = None
                self.enabled = False
        else:
            logger.info("[AIAnalyzer] AI分析功能未启用")
    
    def filter_false_positives(
        self, 
        violations: List[Dict[str, Any]], 
        patient_json: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        过滤假性违规
        
        Args:
            violations: 原始违规列表
            patient_json: 病历数据
            
        Returns:
            过滤后的违规列表
        """
        if not self.enabled or not violations:
            logger.info("[AIAnalyzer] AI分析未启用或无违规数据，跳过过滤")
            return violations
            
        filtered_violations = []
        
        for violation in violations:
            # 只对组套重复收费进行AI分析
            if violation.get('violation_type') == 'package_duplicate':
                if self._should_keep_violation(violation):
                    filtered_violations.append(violation)
                else:
                    logger.info(f"[AIAnalyzer] 过滤假性违规: {violation.get('reason', '')}")
            else:
                # 基础重复收费直接保留
                filtered_violations.append(violation)
        
        logger.info(f"[AIAnalyzer] 过滤前: {len(violations)} 项，过滤后: {len(filtered_violations)} 项")
        return filtered_violations
    
    def _should_keep_violation(self, violation: Dict[str, Any]) -> bool:
        """
        判断是否应该保留违规记录
        
        Args:
            violation: 违规记录
            
        Returns:
            是否保留
        """
        package_analysis = violation.get('package_analysis', {})
        if not package_analysis.get('requires_ai_verification', False):
            return True
            
        charge_item_name = package_analysis.get('charge_item', '')
        package_names = package_analysis.get('package_names', [])
        
        if not charge_item_name or len(package_names) < 2:
            return True
            
        # 调用AI分析
        ai_result = self._ask_deepseek_about_body_parts(charge_item_name, package_names)
        
        # 如果AI判断为"不同"，则为假性违规，应该过滤掉
        if ai_result == "不同":
            return False
        else:
            return True
    
    def _ask_deepseek_about_body_parts(self, charge_item_name: str, package_names: List[str]) -> str:
        """
        询问DeepSeek关于收费项目在不同组套中的功能差异
        
        Args:
            charge_item_name: 收费项目名称
            package_names: 组套名称列表
            
        Returns:
            AI分析结果 ("相同" 或 "不同")
        """
        if not self.client:
            logger.warning("[AIAnalyzer] DeepSeek客户端未初始化，默认返回'相同'")
            return "相同"
            
        prompt = self._build_analysis_prompt(charge_item_name, package_names)
        
        try:
            response = self.client.chat.completions.create(
                model="deepseek-chat",
                messages=[
                    {"role": "system", "content": "你是一个医学专家，专门分析医疗收费项目的功能差异。"},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=50,
                temperature=0.1
            )
            
            result = response.choices[0].message.content.strip()
            logger.info(f"[AIAnalyzer] DeepSeek分析结果: {charge_item_name} -> {result}")
            
            # 确保返回值为预期格式
            if "不同" in result:
                return "不同"
            else:
                return "相同"
                
        except Exception as e:
            logger.error(f"[AIAnalyzer] DeepSeek API调用失败: {e}")
            # 出错时保守处理，认为是真实违规
            return "相同"
    
    def _build_analysis_prompt(self, charge_item_name: str, package_names: List[str]) -> str:
        """
        构建AI分析提示词
        
        Args:
            charge_item_name: 收费项目名称
            package_names: 组套名称列表
            
        Returns:
            分析提示词
        """
        prompt = f"""
你是一个医学专家，熟悉各种医疗服务项目的内涵，现在要筛选组套重复收费的检测结果，去除假性违规。

组套重复收费的定义是：不同检验组套项目中包含同一检测项目，同时开展并收费多个组套项目，重复收取重叠收费项目费用。

如果重叠的收费项目功能或应用的部位不同，即没有重复收费，为假性违规。

收费项目：{charge_item_name}

该收费项目在以下组套中出现：
{chr(10).join([f"{i+1}. {name}" for i, name in enumerate(package_names)])}

请仔细分析这个收费项目在不同组套中的具体应用，判断它是否具有不同的功能或检查不同的位置。

判断标准：
1. 如果同一个收费项目在不同组套中检查不同的器官或部位，则回答"不同"
2. 如果同一个收费项目在不同组套中检查相同的部位且具有相同的功能，则回答"相同"
3. 如果不确定，请基于医学常识进行合理判断

例如：
1、"肝功能9项"和"心肌酶5项"组套项目，均包含"血清天门冬氨酸氨基转移酶测定"收费项目，该收费项目在两个组套项目中具有相同功能，因此收费项目相同，则回答"相同"。
2、"血糖测定(组套)"和"血气分析(组套)"，均包含"葡萄糖测定"收费项目，该收费项目在两个组套项目中具有相同功能，因此收费项目相同，则回答"相同"。
3、"一般细菌、真菌培养及鉴定(粪便)(组套)(检验科)"和"一般细菌、真菌培养及鉴定(痰液)(组套)(检验科)"组套项目，均包含"真菌培养及鉴定"收费项目，但由于该收费项目应用部位不同，分别是粪便和痰液，因此收费项目不同，则回答"不同"。
4、"腹部(彩超)"和"泌尿系(彩超)"，均包含"超声计算机图文报告(B超)"收费项目，但由于该收费项目应用部位不同，分别是腹部和泌尿系，因此收费项目不同，则回答"不同"。

请只回答"不同"或"相同"，不要添加其他解释。如果无法明确判断，则回答"相同"。
"""
        return prompt
    
    def get_analysis_stats(self) -> Dict[str, Any]:
        """
        获取AI分析统计信息
        
        Returns:
            统计信息
        """
        return {
            'ai_enabled': self.enabled,
            'client_available': self.client is not None,
            'analysis_count': getattr(self, '_analysis_count', 0),
            'filter_count': getattr(self, '_filter_count', 0)
        }