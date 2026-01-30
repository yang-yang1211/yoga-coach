import xgboost as xgb
import numpy as np
import os

class XGBClassifier:
    """
    專門處理 XGBoost (.json) 模型推論
    支援 GPU/CPU 自動切換邏輯，並加入硬體記憶體偵測
    """
    def __init__(self, model_path, labels):
        self.model = xgb.Booster()
        self.model.load_model(model_path)
        self.labels = labels
        self.device = "cpu" # 預設使用 CPU
        self.vram_total = 0 # 單位: GB
        self._setup_device()

    def _setup_device(self):
        """
        硬體最大化邏輯：優先嘗試開啟 CUDA GPU 加速，並抓取記憶體資訊
        """
        # 1. 嘗試偵測實體 GPU 記憶體資訊 (使用 pynvml)
        try:
            import pynvml
            pynvml.nvmlInit()
            handle = pynvml.nvmlDeviceGetHandleByIndex(0) # 取得第一張顯示卡
            info = pynvml.nvmlDeviceGetMemoryInfo(handle)
            self.vram_total = info.total / (1024**3) # 換算為 GB
            print(f"[XGB Engine] 🔍 偵測到硬體：NVIDIA GPU, 專屬顯存容量: {self.vram_total:.2f} GB")
        except ImportError:
            print("[XGB Engine] 💡 提示：若要查看精確顯存資訊，請執行 'pip install nvidia-ml-py'")
        except Exception as e:
            print(f"[XGB Engine] 🔍 無法取得實體顯存詳細資訊: {e}")

        # 2. 嘗試啟動 XGBoost 的 CUDA 加速
        try:
            # 嘗試設定為 GPU 模式 (XGBoost 2.0+ 建議語法)
            self.model.set_param({"device": "cuda"})
            
            # 煙霧測試：確認 CUDA 核心是否能正常預測
            test_names = [f'x{i//2+11}' if i%2==0 else f'y{i//2+11}' for i in range(40)]
            test_data = xgb.DMatrix(np.zeros((1, 40), dtype=np.float32), feature_names=test_names)
            self.model.predict(test_data)
            
            self.device = "gpu"
            print("[XGB Engine] 🚀 成功啟用 CUDA 硬體加速預測")
        except Exception as e:
            # 失敗則降級回 CPU 確保程式可移植性
            try:
                self.model.set_param({"device": "cpu"})
            except:
                pass
            self.device = "cpu"
            print(f"[XGB Engine] 💻 CUDA 加速啟動失敗 (原因: {e})，已切換至 CPU 模式")

    def _extract_features(self, landmarks):
        """
        提取第 11 到 30 號點的 x, y 座標
        """
        features = []
        feature_names = []
        for i in range(11, 31):
            lm = landmarks[i]
            features.extend([lm.x, lm.y])
            feature_names.extend([f'x{i}', f'y{i}'])
        
        return xgb.DMatrix(np.array([features], dtype=np.float32), feature_names=feature_names)

    def predict(self, landmarks):
        """執行模型推論"""
        try:
            dmatrix = self._extract_features(landmarks)
            preds = self.model.predict(dmatrix)
            
            idx = int(np.argmax(preds))
            conf = float(np.max(preds))
            
            label_text = self.labels.get(str(idx), f"動作 {idx}")
            return label_text, conf
        except Exception as e:
            print(f"[XGB Error] 推論失敗: {e}")
            return "分析異常", 0.0