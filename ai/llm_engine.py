import requests
import json
import os
import sys

def resource_path(relative_path):
    """ 取得資源絕對路徑，確保打包後能找到所有資源 """
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.abspath("."), relative_path)

class OllamaCoach:
    def __init__(self, config_name="llama_config.json", model=None):
        # 1. 取得配置檔的正確路徑
        config_path = resource_path(config_name)
        
        # 2. 讀取配置檔
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                config = json.load(f)
            
            self.url = config.get("api_url", "http://localhost:11434/api/generate")
            self.model = config.get("model", "llama3")
            self.system_prompt = config.get("system_prompt", "你是一位專業健身教練。")
            # 如果你有不同的教練人格，也可以存入 JSON
            self.personas = config.get("personas", {})
            
            print(f"[LLM Engine] 從配置檔載入成功 (模型: {self.model})", flush=True)
        except Exception as e:
            print(f"[LLM Engine] ⚠️ 無法讀取配置檔，使用預設值。錯誤: {e}", flush=True)
            self.url = "http://localhost:11434/api/generate"
            self.model = "llama3"
            self.system_prompt = "你是一位專業健身教練。"
            self.personas = {}

    def ask(self, feedback_text, persona_type=None):
        """傳送動作狀態給 Ollama，並取得一句話建議"""
        print(f"[LLM Engine] 正在為狀態 '{feedback_text}' 請求 AI 建議...", flush=True)
        
        # 根據選擇的人格調整 System Prompt
        current_system = self.personas.get(persona_type, self.system_prompt)
        
        prompt = f"{current_system}\n使用者正在做動作，目前的狀態是：{feedback_text}。請給出一句專業、簡短的建議或鼓勵，繁體中文，不超過 20 字。"
        
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": 0.8,
                "top_p": 0.9
            }
        }
        try:
            response = requests.post(self.url, json=payload, timeout=10)
            if response.status_code == 200:
                answer = response.json().get("response", "").strip()
                print(f"[LLM Engine] ✅ Ollama 回應成功: {answer}", flush=True)
                return answer
            
            return "加油！保持呼吸。"
            
        except Exception as e:
            print(f"[LLM Engine] ❌ 無法連線至 Ollama: {e}", flush=True)
            return "教練連線中..."