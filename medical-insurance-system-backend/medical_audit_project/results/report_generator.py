from typing import Dict, List, Any

class ReportGenerator:
    @staticmethod
    def generate_json_report(audit_results: List[Dict]) -> List[Dict[str, Any]]:
        """生成JSON格式的违规报告，每项包含：违规项目、违规原因、有关依据（规则）"""
        violations = []
        for result in audit_results:
            if result.get("violation", False):
                item = result.get("item", {})
                problem = result.get("problem", "")
                rule = result.get("ruleDescription", "")
                violations.append({
                    "违规项目": item,
                    "违规原因": problem,
                    "有关依据": rule
                })
        return violations
    @staticmethod
    def generate_report(audit_results: List[Dict]) -> str:
        """生成文本报告"""
        if not audit_results:
            return "未发现违规情况"
        
        report = "医保审核报告\n"
        report += "=" * 50 + "\n"
        
        # 按步骤分组结果
        results_by_step = {}
        for result in audit_results:
            step_id = result.get("step", "unknown")
            if step_id not in results_by_step:
                results_by_step[step_id] = []
            results_by_step[step_id].append(result)
        
        # 输出每个步骤的结果
        for step_id, results in results_by_step.items():
            report += f"\n步骤: {step_id}\n"
            report += "-" * 50 + "\n"
            
            for result in results:
                if "status" in result and result["status"] == "error":
                    report += f"错误: {result.get('message', '未知错误')}\n"
                else:
                    status = "违规" if result.get("violation", False) else "合规"
                    rule_desc = result.get("ruleDescription", "未知规则")
                    item_info = result.get("item", {})
                    
                    if item_info:
                        item_str = ", ".join(f"{k}: {v}" for k, v in item_info.items())
                        report += f"- 项目: {item_str}, 规则: {rule_desc}, 结果: {status}\n"
                    else:
                        report += f"- 规则: {rule_desc}, 结果: {status}\n"
                    if result.get("violation", False) and result.get("problem"):
                        report += f"  违规原因：{result['problem']}\n"
        
        # 统计摘要
        violations = sum(1 for r in audit_results if r.get("violation", False))
        errors = sum(1 for r in audit_results if "status" in r and r["status"] == "error")
        
        report += "\n" + "=" * 50 + "\n"
        report += f"总结: 共发现 {violations} 项违规, {errors} 项错误\n"
        report += "=" * 50 + "\n"
        
        return report