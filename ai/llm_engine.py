import requests
import time
import json

class GeminiCoach:
    def __init__(self, api_key=""):
        # API Key 由執行環境提供，此處設為空字串
        self.api_key = api_key
        self.url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-preview-09-2025:generateContent?key={self.api_key}"
        self.system_prompt = (
            "你是一位專業的瑜珈與健身教練。我會給你使用者的姿勢狀態與關鍵關節座標。"
            "座標為歸一化 0-1 (Y軸 0為頂部, 1為底部)。"
            "請根據數據精確判斷哪裡不對，並給出具體、鼓勵性且不超過 25 字的修正建議。"
        )

    def ask(self, user_query):
        payload = {
            "contents": [{
                "parts": [{"text": user_query}]
            }],
            "systemInstruction": {
                "parts": [{"text": self.system_prompt}]
            }
        }
        
        # 指數退避重試機制 (Exponential Backoff)
        for i in range(5):
            try:
                response = requests.post(self.url, json=payload, timeout=10)
                if response.status_code == 200:
                    result = response.json()
                    text = result.get('candidates', [{}])[0].get('content', {}).get('parts', [{}])[0].get('text', "")
                    return text.strip()
            except Exception as e:
                print(f"[Gemini] 第 {i+1} 次請求失敗: {e}")
            
            time.sleep(2 ** i) # 1s, 2s, 4s...
            
        return "教練目前連線不穩定，請保持姿勢並稍後再試。"

# 保留原本的 OllamaCoach 作為備援
class OllamaCoach:
    def __init__(self, model="llama3"):
        self.model = model
        self.url = "http://localhost:11434/api/generate"

    def ask(self, prompt):
        try:
            res = requests.post(self.url, json={
                "model": self.model,
                "prompt": prompt,
                "stream": False
            }, timeout=5)
            return res.json().get('response', "")
        except:
            return None