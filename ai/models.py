import cv2
import mediapipe as mp
import numpy as np
import pickle
import json
import os
import time

class PoseCorrector:
    """
    AI 姿勢校正模型核心
    負責：AI 推論與 Mock 邏輯產生
    """
    def __init__(self):
        # 1. 初始化基礎 MediaPipe Pose 引擎
        self.mp_pose = mp.solutions.pose
        self.pose = self.mp_pose.Pose(
            min_detection_confidence=0.5,
            min_tracking_confidence=0.5,
            model_complexity=1
        )
        
        # 2. 狀態變數
        self.model = None
        self.scaler = None
        self.labels = {}
        self.is_mock = True 
        self.status_msg = "初始化"

        # 3. 執行載入程序
        self._bootstrap_model()

    def _bootstrap_model(self):
        """嘗試載入真實模型檔案"""
        model_files = ['svm_model.pkl', 'model.pkl']
        scaler_files = ['scaler.pkl']
        label_files = ['labels.json', 'label.json']

        def find_file(names):
            for n in names:
                if os.path.exists(n): return n
            return None

        m_path, s_path, l_path = find_file(model_files), find_file(scaler_files), find_file(label_files)

        try:
            if l_path:
                with open(l_path, 'r', encoding='utf-8') as f:
                    self.labels = json.load(f)
            
            if s_path:
                with open(s_path, 'rb') as f:
                    self.scaler = pickle.load(f)

            if m_path:
                with open(m_path, 'rb') as f:
                    self.model = pickle.load(f)
                
                if hasattr(self.model, 'predict'):
                    self.is_mock = False
                    self.status_msg = "SVM 模式"
                    return
            
            self.is_mock = True
            self.status_msg = "MOCK 模式"
        except Exception as e:
            self.is_mock = True
            self.status_msg = "MOCK (檔案損壞)"

    def process_frame(self, frame):
        """影像處理窗口"""
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results = self.pose.process(frame_rgb)
        
        feedback = "請進入畫面..."
        skeleton_data = None

        if results.pose_landmarks:
            skeleton_data = results.pose_landmarks
            # 根據模式執行判定
            if self.is_mock:
                feedback = self.mock_analyze(skeleton_data.landmark)
            else:
                feedback = self.predict_real_svm(skeleton_data.landmark)
        
        # 格式化輸出，確保 UI 能清楚顯示
        final_feedback = f"[{self.status_msg}] {feedback}"
        
        return {
            "feedback_message": final_feedback,
            "skeleton_data": skeleton_data
        }

    def predict_real_svm(self, landmarks):
        """SVM 預測邏輯"""
        try:
            expected = getattr(self.model, 'n_features_in_', 132)
            pose_row = []
            if expected == 132:
                for lm in landmarks: pose_row.extend([lm.x, lm.y, lm.z, lm.visibility])
            elif expected == 99:
                for lm in landmarks: pose_row.extend([lm.x, lm.y, lm.z])
            else:
                for lm in landmarks: pose_row.extend([lm.x, lm.y])

            X = self.scaler.transform([pose_row])
            prediction = self.model.predict(X)[0]
            return self.labels.get(str(prediction), f"動作 {prediction}")
        except:
            return "分析中..."

    def mock_analyze(self, landmarks):
        """強化版 Mock 邏輯：檢查鼻子座標 Y 值"""
        nose_y = landmarks[0].y
        # 這裡是原本版本的簡單提示語
        if nose_y > 0.65:
            return "✅ 深度達標！保持核心穩定"
        elif nose_y < 0.45:
            return "💪 準備開始運動，請下蹲"
        return "✨ 偵測中：請注意下蹲深度"

class VTuberRenderer:
    """虛擬角色渲染模型"""
    def __init__(self):
        self.mp_drawing = mp.solutions.drawing_utils
        self.mp_pose = mp.solutions.pose

    def draw(self, skeleton_data):
        """繪製 VTuber 畫像"""
        # 建立 480x640 黑色背景
        canvas = np.zeros((480, 640, 3), dtype="uint8")
        
        try:
            if skeleton_data:
                # 繪製數位感骨架
                self.mp_drawing.draw_landmarks(
                    canvas, 
                    skeleton_data,
                    self.mp_pose.POSE_CONNECTIONS,
                    self.mp_drawing.DrawingSpec(color=(0, 229, 255), thickness=2, circle_radius=2),
                    self.mp_drawing.DrawingSpec(color=(255, 255, 255), thickness=1)
                )
                cv2.putText(canvas, "AI VTuber LIVE", (20, 50), 
                            cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 229, 255), 2)
            else:
                cv2.putText(canvas, "Searching Trainer...", (180, 240), 
                            cv2.FONT_HERSHEY_SIMPLEX, 0.8, (50, 50, 50), 1)
        except:
            pass
            
        return canvas