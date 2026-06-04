import json

drug_limit = "限有明确的溃疡、间歇性跛行及严重疼痛体征的患者"

# 从JSON文件中提取患者症状
def extract_patient_symptoms(json_file_path):
    """
    从JSON文件中提取患者症状信息
    抽取路径：入院记录.主诉, 入院记录.现病史, 入院记录.体格检查, 入院记录.专科情况, 入院记录.辅助检查
    """
    try:
        with open(json_file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        symptoms = []
        
        # 提取入院记录信息
        admission_record = data.get('入院记录', {})
        
        # 提取主诉
        chief_complaint = admission_record.get('主诉', '')
        if chief_complaint and chief_complaint != '文本中未提及该内容':
            symptoms.append(chief_complaint)
        
        # 提取现病史
        present_illness = admission_record.get('现病史', '')
        if present_illness and present_illness != '文本中未提及该内容':
            symptoms.append(present_illness)
        
        # 提取体格检查
        physical_exam = admission_record.get('体格检查', '')
        if physical_exam and physical_exam != '文本中未提及该内容':
            symptoms.append(physical_exam)
        
        # 提取专科情况
        specialist_condition = admission_record.get('专科情况', '')
        if specialist_condition and specialist_condition != '文本中未提及该内容':
            symptoms.append(specialist_condition)
        
        # 提取辅助检查
        auxiliary_exam = admission_record.get('辅助检查', '')
        if auxiliary_exam and auxiliary_exam != '文本中未提及该内容':
            symptoms.append(auxiliary_exam)
        
        return symptoms
    
    except Exception as e:
        print(f"读取JSON文件时出错: {e}")
        return []

# 指定JSON文件路径
json_file_path = r"c:\Users\王\Desktop\病人数据\patient_ZY020000504259_20250720_203640.json"

# 从JSON文件中提取患者症状
patient_symptoms = extract_patient_symptoms(json_file_path)

prompt = f"""你是一名医学审核专家，请判断患者的症状是否满足药品的限制条件。

【药品限制】
{drug_limit}

【患者症状】
{', '.join(patient_symptoms)}

请直接回答“是否满足限制条件”，并简要说明理由。输出格式如下：
满足/不满足
理由：xxx
"""

# 调用大模型
from llm_api import LLMApiClient
client = LLMApiClient()
result = client.chat(prompt)
print(result)
