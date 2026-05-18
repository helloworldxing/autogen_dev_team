# 导入所需包
import requests
import json

# 定义函数
def func(question, model='deepseek-r1:latest',API_URL = "http://localhost:11434/api/generate"):
    headers = {
    "Content-Type": "application/json"
    }
    data = {
    "model": model,
    "prompt": question,
    "stream": True  # 开启流式输出
    }
    response = requests.post(API_URL, headers=headers, json=data, stream=True)
    for line in response.iter_lines():
        if line:
            json_data = json.loads(line.decode("utf-8"))
            print(json_data.get("response", ""), end="", flush=True)

# 调用函数
func('你好', model='deepseek-r1:latest')