# mock_server.py (最终修正版)

from flask import Flask, jsonify, request
from flask_cors import CORS
import json
import os

app = Flask(__name__)
CORS(app) # 确保 CORS 存在

# --- 加载你的所有真实病历 JSON 文件 ---
mock_data_dir = "mock_patient_data"
patient_cases = {} # key 是住院号, value 是 JSON 内容
if os.path.exists(mock_data_dir):
    for filename in os.listdir(mock_data_dir):
        if filename.endswith(".json"):
            filepath = os.path.join(mock_data_dir, filename)
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    case_id = filename.replace(".json", "") # 用文件名（不含.json）作为 key
                    patient_cases[case_id] = json.load(f)
                    print(f"Mock Server: 成功加载了模拟数据: {case_id}")
            except Exception as e:
                print(f"Mock Server: 加载文件 {filename} 失败: {e}")

if not patient_cases:
    print("警告：在 mock_patient_data 目录下未找到任何 .json 文件！")


@app.route('/get_patient_data', methods=['GET'])
def get_patient_data():
    hospitalization_id = request.args.get('hospitalization_id')
    
    if not hospitalization_id:
        return jsonify({"error": "缺少 hospitalization_id 参数"}), 400

    # --- 核心改造点：根据 hospitalization_id 精确查找 ---
    case_data = patient_cases.get(hospitalization_id)
    
    if case_data:
        print(f"Mock Server: 收到对 {hospitalization_id} 的请求，成功找到并返回对应数据。")
        return jsonify(case_data)
    else:
        # 如果找不到精确匹配的，可以返回一个错误，或者返回一个默认/随机的数据
        print(f"Mock Server: 收到对 {hospitalization_id} 的请求，但未找到匹配数据！将返回第一个可用数据作为备用。")
        if patient_cases:
            first_key = list(patient_cases.keys())[0]
            return jsonify(patient_cases[first_key])
        else:
            return jsonify({"error": f"未找到住院号为 {hospitalization_id} 的病历"}), 404

if __name__ == '__main__':
    print("Mock Server 正在启动，监听 http://127.0.0.1:8001 ...")
    app.run(port=8001)