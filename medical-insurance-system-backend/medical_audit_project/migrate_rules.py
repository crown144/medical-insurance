import os
import django
import sys
import re

# 设置 Django 环境
sys.path.append(r"d:\medical vben\medical-insurance-system-project\medical_audit_project")
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'medical_audit_project.settings')
django.setup()

from rules.models import Rule

RULES_FILE_PATH = r"d:\medical vben\medical-insurance-system-project\rules.txt"

def parse_rules_txt(file_path):
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # Split content by sections (一、超标准收费, 二、重复收费)
    # This is a simple parser based on the structure provided
    
    # Extract "超标准收费" section
    over_std_match = re.search(r'一、超标准收费\n(.*?)\n二、重复收费', content, re.DOTALL)
    dup_match = re.search(r'二、重复收费\n(.*)', content, re.DOTALL)
    
    rules_data = []
    
    if over_std_match:
        rules_data.extend(parse_section(over_std_match.group(1), "超标准收费"))
        
    if dup_match:
        rules_data.extend(parse_section(dup_match.group(1), "重复收费"))
        
    return rules_data

def parse_section(section_content, rule_type):
    # Rules are separated by numbers like "1、", "2、" etc.
    # Pattern: ^\d+、(.*?)\n(def execute_rule.*?)(?=\n\d+、|\Z)
    
    # A more robust split: find lines starting with digit + "、"
    # Then everything until next such line is the body
    
    lines = section_content.split('\n')
    parsed_rules = []
    current_rule = None
    
    for line in lines:
        # Check for start of a rule: "1、Title Description"
        match = re.match(r'^(\d+)、(.*?)$', line.strip())
        if match:
            # Save previous rule if exists
            if current_rule:
                parsed_rules.append(current_rule)
            
            # Start new rule
            seq = match.group(1)
            title_desc = match.group(2).strip()
            
            # Try to extract drug name from title (first part before space usually)
            # e.g. "胃肠减压 插胃管加收10元" -> drug="胃肠减压", desc="插胃管加收10元"
            # But sometimes it is just one sentence.
            parts = title_desc.split(' ', 1)
            if len(parts) > 1:
                drug_name = parts[0]
            else:
                drug_name = title_desc
            
            # Generate a rule_id based on type and sequence
            prefix = "OVER_STD" if rule_type == "超标准收费" else "DUP_BILL"
            rule_id = f"{prefix}_{seq.zfill(3)}"
            
            current_rule = {
                "rule_id": rule_id,
                "drug_name": drug_name,
                "description": title_desc,
                "type": rule_type,
                "rule_code_lines": []
            }
        elif current_rule:
            # Append code lines
            # Skip empty lines at the beginning of code block
            if not current_rule["rule_code_lines"] and not line.strip():
                continue
            current_rule["rule_code_lines"].append(line)
            
    # Add the last rule
    if current_rule:
        parsed_rules.append(current_rule)
        
    return parsed_rules

def migrate_rules():
    print("开始解析 rules.txt ...")
    rules_data = parse_rules_txt(RULES_FILE_PATH)
    print(f"解析到 {len(rules_data)} 条规则。")
    
    success_count = 0
    for r_data in rules_data:
        rule_code = '\n'.join(r_data["rule_code_lines"]).strip()
        
        # Create or Update Rule
        # We use rule_id as unique key
        obj, created = Rule.objects.update_or_create(
            rule_id=r_data["rule_id"],
            defaults={
                "drug_name": r_data["drug_name"],
                "description": r_data["description"],
                "type": r_data["type"],
                "rule_code": rule_code,
                "status": True,
                # match_value is redundant now, but we can fill it for backward compat or just leave blank
                "match_value": r_data["drug_name"]
            }
        )
        action = "创建" if created else "更新"
        print(f"[{action}] {r_data['rule_id']} - {r_data['drug_name']}")
        success_count += 1
        
    print(f"迁移完成！共成功处理 {success_count} 条规则。")

if __name__ == '__main__':
    migrate_rules()
