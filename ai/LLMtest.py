import requests
import time
import json
import psutil
import GPUtil
import threading

# 設定測試參數
MODEL_NAME = "llama3"  # 確保你已執行過 ollama pull llama3
OLLAMA_URL = "http://localhost:11434/api/generate"
TEST_PROMPT = "使用者正在做戰士二式，膝蓋超過腳尖。請給予一句溫柔的鼓勵與修正建議。"

def get_hardware_stats():
    """取得當前的 GPU 和 RAM 狀態"""
    gpus = GPUtil.getGPUs()
    gpu_vram = gpus[0].memoryUsed if gpus else 0
    gpu_load = gpus[0].load * 100 if gpus else 0
    ram_usage = psutil.virtual_memory().percent
    return gpu_vram, gpu_load, ram_usage

def run_benchmark():
    print(f"--- 開始測試模型: {MODEL_NAME} ---")
    
    # 紀錄初始狀態
    init_vram, init_gpu, init_ram = get_hardware_stats()
    
    payload = {
        "model": MODEL_NAME,
        "prompt": TEST_PROMPT,
        "stream": True  # 必須開啟串流才能測試 TTFT
    }

    start_time = time.time()
    ttft = None  # Time To First Token
    total_tokens = 0
    full_response = ""

    # 發送請求
    with requests.post(OLLAMA_URL, json=payload, stream=True) as response:
        for line in response.iter_lines():
            if line:
                chunk = json.loads(line)
                full_response += chunk.get("response", "")
                
                # 紀錄第一個字出現的時間 (TTFT)
                if ttft is None:
                    ttft = time.time() - start_time
                
                if chunk.get("done"):
                    total_duration = time.time() - start_time
                    # Ollama 會在最後一幀回傳統計數據
                    total_tokens = chunk.get("eval_count", 0)
    
    # 紀錄測試結束後的硬體狀態
    end_vram, end_gpu, end_ram = get_hardware_stats()

    # 計算結果
    tps = total_tokens / (total_duration - ttft) if total_tokens > 0 else 0

    print("\n[測試結果報告]")
    print(f"1. 延遲指標:")
    print(f"   - 首字延遲 (TTFT): {ttft:.3f} 秒 (使用者多久會聽到第一聲回饋)")
    print(f"   - 總生成時間: {total_duration:.2f} 秒")
    print(f"   - 生成速度 (TPS): {tps:.2f} tokens/s (建議 > 10 為流暢)")
    
    print(f"\n2. 硬體資源佔用:")
    print(f"   - GPU 顯存 (VRAM): {init_vram}MB -> {end_vram}MB (淨佔用: {end_vram - init_vram}MB)")
    print(f"   - GPU 使用率最高峰: {end_gpu:.1f}%")
    print(f"   - 系統 RAM 使用率: {end_ram}%")
    
    print(f"\n3. 模型回答範例:\n   \"{full_response}\"")

if __name__ == "__main__":
    run_benchmark()