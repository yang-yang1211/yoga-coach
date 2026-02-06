import cv2
import mediapipe as mp
import numpy as np
import xgboost as xgb
import os
import json # 必須導入此庫以處理標籤檔案
import sys

def resource_path(relative_path):
    """ 取得資源絕對路徑，相容於開發與 PyInstaller 打包環境 """
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.abspath("."), relative_path)

class PoseEngine:
    """
    處理 MediaPipe Pose 偵測與 XGBoost 姿勢辨識
    """
    def __init__(self, model_path="yoga_pose_model_RightFoot.json", labels_path="rightfoot.json"):
        print("[AI Engine] 正在初始化...", flush=True)
        
        # 轉換為資源路徑
        self.actual_model_path = resource_path(model_path)
        self.actual_labels_path = resource_path(labels_path)
        
        self.mp_pose = mp.solutions.pose
        self.mp_drawing = mp.solutions.drawing_utils
        self.pose = self.mp_pose.Pose(
            min_detection_confidence=0.5,
            min_tracking_confidence=0.5,
            model_complexity=1
        )
        self.user_style = self.mp_drawing.DrawingSpec(color=(0, 255, 0), thickness=3, circle_radius=3)

        # 1. 初始化 XGBoost
        self.classifier = xgb.Booster()
        if os.path.exists(self.actual_model_path):
            self.classifier.load_model(self.actual_model_path)
            self.model_loaded = True
            print(f"[AI Engine] 🚀 成功載入模型: {self.actual_model_path}", flush=True)
        else:
            self.model_loaded = False
            print(f"[AI Engine] ⚠️ 找不到模型檔案: {self.actual_model_path}，將只顯示骨架", flush=True)

        # 2. 初始化標籤
        self.labels = {}
        self._load_labels()

    def _load_labels(self):
        """ 載入標籤 JSON 檔案 """
        if os.path.exists(self.actual_labels_path):
            try:
                with open(self.actual_labels_path, 'r', encoding='utf-8') as f:
                    raw_labels = json.load(f)
                    # 確保 key 轉換為整數，因為 XGB 預測結果是數值索引
                    self.labels = {int(k): v for k, v in raw_labels.items()}
                print(f"[AI Engine] ✅ 成功載入標籤: {self.labels}")
            except Exception as e:
                print(f"[AI Engine] ❌ 標籤檔案解析失敗: {e}")
                self.labels = {0: "姿勢偏移 (預設)", 1: "正確動作 (預設)"}
        else:
            print(f"[AI Engine] ⚠️ 找不到標籤檔案於: {self.actual_labels_path}")
            self.labels = {0: "姿勢偏移 (預設)", 1: "正確動作 (預設)"}

    def process(self, frame):
        """
        處理影格
        回傳: (標記影像, 骨骼數據, 辨識回饋文字)
        """
        if frame is None: return None, None, "No Signal"
        
        annotated_frame = frame.copy()
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results = self.pose.process(frame_rgb)
        
        feedback = "請進入畫面"
        skeleton_data = None

        if results.pose_landmarks:
            skeleton_data = results.pose_landmarks
            self.mp_drawing.draw_landmarks(
                annotated_frame, 
                skeleton_data, 
                self.mp_pose.POSE_CONNECTIONS,
                landmark_drawing_spec=self.user_style
            )
            
            # 執行辨識
            if self.model_loaded:
                feedback = self._predict_pose(skeleton_data)
            else:
                feedback = "骨架偵測中..."
            
        return annotated_frame, skeleton_data, feedback

    def _predict_pose(self, landmarks):
        """ 根據 20 個關鍵點 (40維特徵) 進行預測 """
        try:
            features = []
            # 提取肩膀 (11) 到腳踝 (30) 的點
            for i in range(11, 31):
                lm = landmarks.landmark[i]
                features.extend([lm.x, lm.y])
            
            input_data = np.array([features], dtype=np.float32)
            data = xgb.DMatrix(input_data)
            preds = self.classifier.predict(data)
            
            # 取得信心度最高的類別
            class_idx = np.argmax(preds[0])
            confidence = preds[0][class_idx]
            
            if confidence > 0.7:
                # 這裡會從讀取的 self.labels 中抓取對應文字
                return self.labels.get(class_idx, f"未知動作 (ID:{class_idx})")
            
            return "動作匹配中..."
        except Exception as e:
            # 印出具體錯誤以便調試
            # print(f"預測錯誤: {e}")
            return "分析中..."

class VTuberRenderer:
    """ 渲染純黑背景的骨架圖 (用於 GUI 顯示) """
    def __init__(self):
        self.mp_drawing = mp.solutions.drawing_utils
        self.mp_pose = mp.solutions.pose
        self.style = self.mp_drawing.DrawingSpec(color=(0, 255, 255), thickness=2, circle_radius=4)

    def render(self, skeleton_data):
        canvas = np.zeros((480, 640, 3), dtype="uint8")
        if skeleton_data:
            self.mp_drawing.draw_landmarks(
                canvas, 
                skeleton_data, 
                self.mp_pose.POSE_CONNECTIONS,
                landmark_drawing_spec=self.style
            )
        return canvas