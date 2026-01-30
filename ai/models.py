import cv2
import mediapipe as mp
import numpy as np
import xgboost as xgb
import os
import time

class PoseEngine:
    """
    處理 MediaPipe Pose 偵測與 XGBoost 姿勢辨識
    """
    def __init__(self, model_path="yoga_pose_model_RightFoot.json",labels_path="rightfoot.json"):
        print("[AI Engine] 正在初始化...", flush=True)
        self.mp_pose = mp.solutions.pose
        self.mp_drawing = mp.solutions.drawing_utils
        self.pose = self.mp_pose.Pose(
            min_detection_confidence=0.5,
            min_tracking_confidence=0.5,
            model_complexity=1
        )
        self.user_style = self.mp_drawing.DrawingSpec(color=(0, 255, 0), thickness=3, circle_radius=3)

        # 初始化 XGBoost
        self.classifier = xgb.Booster()
        if os.path.exists(model_path):
            self.classifier.load_model(model_path)
            self.model_loaded = True
            print(f"[AI Engine] 🚀 成功載入模型: {model_path}", flush=True)
        else:
            self.model_loaded = False
            print(f"[AI Engine] ⚠️ 找不到模型，將只顯示骨架", flush=True)

        self.labels = {}
        if os.path.exists(labels_path):
            try:
                with open(labels_path, 'r', encoding='utf-8') as f:
                    # 假設 JSON 格式為 {"0": "動作A", "1": "動作B"}
                    raw_labels = json.load(f)
                    # 確保 key 為整數
                    self.labels = {int(k): v for k, v in raw_labels.items()}
                print(f"[AI Models] 成功載入標籤檔案: {labels_path}")
            except Exception as e:
                print(f"[AI Models] 標籤檔案格式錯誤: {e}")
                self.labels = {0: "姿勢偏移", 1: "正確右平衡"} # 備用標籤
        else:
            print(f"[AI Models] ⚠️ 找不到標籤檔案，使用預設標籤")
            self.labels = {0: "姿勢偏移", 1: "正確右平衡"}

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
                feedback = "偵測中..."
            
        return annotated_frame, skeleton_data, feedback

    def _predict_pose(self, landmarks):
        try:
            features = []
            for i in range(11, 31): # 提取肩膀到腳踝的 20 個點 (40維)
                lm = landmarks.landmark[i]
                features.extend([lm.x, lm.y])
            
            input_data = np.array([features], dtype=np.float32)
            data = xgb.DMatrix(input_data)
            preds = self.classifier.predict(data)
            
            class_idx = np.argmax(preds[0])
            confidence = preds[0][class_idx]
            
            if confidence > 0.7:
                return self.labels.get(class_idx, "未知動作")
            return "正在捕捉動作..."
        except:
            return "分析中..."

class VTuberRenderer:
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