import json
import requests

class LLMApiClient:
    def __init__(self, 
                 base_url="http://localhost:16666/v1/chat/completions", 
                 model_name="Qwen2.5-7B-Instruct", 
                 temperature=0.01, 
                 max_tokens=4000):
        self.base_url = base_url
        self.model_name = model_name
        self.temperature = temperature
        self.max_tokens = max_tokens

    def send_chat_completion_request(self, message_content, model_name=None, temperature=None):
        url = self.base_url
        headers = {"Content-Type": "application/json"}
        data = {
            "model": model_name or self.model_name,
            "messages": [{"role": "user", "content": message_content}],
            "temperature": temperature if temperature is not None else self.temperature,
            "max_tokens": self.max_tokens
        }
        json_data = json.dumps(data)
        # print(data)
        try:
            response = requests.post(url, headers=headers, data=json_data)
            if response.status_code == 200:
                return response.json()["choices"][0]["message"]["content"]
            else:
                raise Exception(f"Request failed with status {response.status_code}: {response.text}")
        except Exception as e:
            return f"An error occurred: {type(e).__name__} - {e}"

    def chat(self, content, **kwargs):
        return self.send_chat_completion_request(content, **kwargs)

# 示例用法
if __name__ == "__main__":
    client = LLMApiClient()
    print(client.chat("我最近一直发烧怎么办"))


# print(chat_method('''
# 任务描述：
# 你需要评估给定的医学问题是否属于 “合理问题”。合理问题应满足非特异性和可泛化性标准，且能够通过医学图像或报告提供支持性判断依据。
# “问题文本”：患者是否经历了后玻璃体脱离？
# 【合理问题的判断标准】
# 非特异性：
#     问题不涉及特定个体的操作细节（如“该病人是否已完成XX操作”）。
#     问题不涉及人员信息（如“由哪位医生执行”）。
#     问题不涉及病程前后比较（如“与上次检查相比是否有好转”）。
# 可泛化性
#     问题可通过其他类似病例的报告或医学知识解答。
#     医学图像或报告能提供键支持信息（如病灶特征、术后改变、典型影像学表现等）。
# 【不合理问题的处理】
# 若问题符合以下任一类，则视为不合理，并需标注对应的 unreasonable_type：
#     不合理问题分类
#     "涉及患者个人病程"：包含 具体患者的识别信息 或 个体化操作记录（如“患者张三的术后恢复情况如何？”）。
#     "涉及诊疗计划是否被执行"：询问 诊疗行为是否完成（如“是否已进行化疗？”、“是否按时复查？”）。
#     "人工操作信息"：涉及 医疗人员或操作细节（如“手术由哪位主刀医生完成？”、“是否使用了XX器械？”）。
#     "其他类型"：图像或报告 完全无法提供辅助判断，且不属于上述类别（如“患者的医保类型是什么？”）。
# 输出格式
# 请严格按以下 JSON 格式 输出，确保可被 json.loads() 解析：

#     请按照以下 JSON 格式输出，务必正确闭合引号，确保能被 `json.loads()` 正确解析：
#     ```json
#      {{
#         "question": "[问题原文]",
#         "is_reasonable": [false/true],
#         "unreasonable_type": [不合理问题类型/null],
#         "reason": "[不合理问理由/null]。
#     }}
#     ```
#     '''))

# print(chat_method("""
#     发烧了应该怎么办
#     请按照以下 JSON 格式输出，务必正确闭合引号，确保能被 `json.loads()` 正确解析：
#     ```json
#      {{
#         "answer": "XXXX",
#     }}
#     ```"""))