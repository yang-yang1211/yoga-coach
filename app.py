import sys
import time
import os
import cv2
import json
import mediapipe as mp
import numpy as np
from PyQt6.QtWidgets import QApplication, QMainWindow
from PyQt6.QtCore import QThread, pyqtSignal, Qt, QTimer
from PyQt6.QtGui import QImage

# 匯入專案自定義模組
try:
    from ui.main import MainUI
    from ai.models import PoseEngine, VTuberRenderer
    from core.state import SystemState
    from core.gesture_engine import GestureEngine
    # 從更新後的引擎匯入 Gemini 與 Ollama
    from ai.llm_engine import GeminiCoach, OllamaCoach 
except ImportError as e:
    print(f"[Import Error] 缺少模組: {e}")

def resource_path(relative_path):
    """ 取得資源絕對路徑，兼容開發環境與 PyInstaller 打包環境 """
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.abspath("."), relative_path)

# --- 1. LLM 非同步處理執行緒 (支援座標分析) ---
class LLMWorker(QThread):
    finished = pyqtSignal(str)

    def __init__(self, coach, status, landmarks):
        super().__init__()
        self.coach = coach
        self.status = status
        self.landmarks = landmarks

    def run(self):
        """ 執行 AI 請求 """
        if not self.coach:
            self.finished.emit("教練目前不在線上。")
            return

        # 將座標字典轉為文字描述，讓 AI 更好判斷
        # 例如：L_Knee:(0.50, 0.80), R_Knee:(0.52, 0.82)
        lm_str = ", ".join([f"{k}:({v[0]:.2f}, {v[1]:.2f})" for k, v in self.landmarks.items()])
        
        # 構造精確的 Prompt
        query = (
            f"使用者目前姿勢標籤為: {self.status}。 "
            f"關鍵點座標(歸一化): {lm_str}。 "
            "請判斷使用者動作哪裡不標準，並給出一句 20 字內的具體修正建議。"
        )

        res = self.coach.ask(query)
        self.finished.emit(res)

# --- 2. 影像處理核心執行緒 (負責提取座標與影像) ---
class VideoThread(QThread):
    raw_ready = pyqtSignal(QImage)
    vt_ready = pyqtSignal(QImage)
    # 擴展訊號: (is_active, fps, feedback, hand_x, hand_y, pose_landmarks)
    status_update = pyqtSignal(bool, float, str, float, float, dict)
    gesture_cmd = pyqtSignal(str)

    def __init__(self, state):
        super().__init__()
        self.state = state
        self.pose = PoseEngine(
            model_path=resource_path("yoga_pose_model_RightFoot.json"),
            labels_path=resource_path("rightfoot.json")
        )
        self.vt = VTuberRenderer()
        self.gesture_engine = GestureEngine()
        
        self.mp_hands = mp.solutions.hands
        self.hands = self.mp_hands.Hands(
            static_image_mode=False,
            max_num_hands=1,
            min_detection_confidence=0.7,
            min_tracking_confidence=0.5
        )

    def run(self):
        print("[VideoThread] 正在開啟攝影機...", flush=True)
        cap = cv2.VideoCapture(0)
        if not cap.isOpened():
            print("[VideoThread] ❌ 錯誤：無法開啟攝影機", flush=True)
            return

        last_time = time.time()
        while not self.state.stop_signal:
            ret, frame = cap.read()
            if not ret: continue
            
            frame = cv2.flip(frame, 1)
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            
            anno_frame = frame.copy()
            skeleton = None
            feedback = ""
            is_active = False
            hand_x, hand_y = -1.0, -1.0
            pose_landmarks = {}

            if self.state.mode == "EXERCISE":
                anno_frame, skeleton, feedback = self.pose.process(frame)
                if skeleton:
                    # 1. 提取右食指位置供懸浮控制
                    r_idx = skeleton.landmark[20]
                    if r_idx.visibility > 0.5:
                        hand_x, hand_y = r_idx.x, r_idx.y
                    
                    # 2. 提取關鍵關節座標供 AI 建議使用
                    # 11,12:肩 | 23,24:髖 | 25,26:膝 | 27,28:踝
                    targets = {"L_Shoulder": 11, "R_Shoulder": 12, "L_Knee": 25, "R_Knee": 26, "L_Ankle": 27, "R_Ankle": 28}
                    for name, idx in targets.items():
                        lm = skeleton.landmark[idx]
                        if lm.visibility > 0.5:
                            pose_landmarks[name] = [lm.x, lm.y]
            else:
                results = self.hands.process(rgb_frame)
                feedback = "手部操控模式"
                if results.multi_hand_landmarks:
                    lm = results.multi_hand_landmarks[0]
                    is_fist = self.gesture_engine.is_fist(lm)
                    cmd = self.gesture_engine.get_swipe_command(lm, is_fist, self.state.current_page)
                    hand_x, hand_y = lm.landmark[8].x, lm.landmark[8].y
                    if cmd:
                        self.gesture_cmd.emit(cmd)

            def to_qimg(img):
                h, w, c = img.shape
                return QImage(img.data, w, h, c*w, QImage.Format.Format_BGR888).copy()

            self.raw_ready.emit(to_qimg(anno_frame))
            self.vt_ready.emit(to_qimg(self.vt.render(skeleton)))
            
            curr_time = time.time()
            fps = 1.0 / (curr_time - last_time) if (curr_time - last_time) > 0 else 0
            last_time = curr_time
            
            self.status_update.emit(is_active, fps, feedback, hand_x, hand_y, pose_landmarks)
            
        cap.release()
        self.hands.close()

# --- 3. 主程序入口 ---
def main():
    print("[System] 正在啟動程序...", flush=True)
    app = QApplication(sys.argv)
    
    state = SystemState()
    ui = MainUI(state)

    # 💡 優先初始化 GeminiCoach (雲端版，免安裝 Ollama)
    coach = None
    try:
        # 在開發環境中，apiKey 保持為空，執行環境會自動填入
        coach = GeminiCoach(api_key="AIzaSyDiJH-K5PfEaXlcrqK7HSiTCGz66N3Z1vc") 
        print("[Main] ✅ Gemini AI 教練已就緒", flush=True)
    except Exception as e:
        print(f"[Main] ⚠️ Gemini 初始化失敗: {e}，嘗試回退至 Ollama", flush=True)
        try:
            coach = OllamaCoach()
        except:
            coach = None

    video = VideoThread(state)
    video.raw_ready.connect(ui.update_video)
    video.vt_ready.connect(ui.update_vtuber)
    video.gesture_cmd.connect(ui.handle_command)

    # --- 4. 智慧教練觸發邏輯 ---
    last_coach_time = 0
    last_status = ""

    def handle_coach_trigger(is_active, fps, feedback, x, y, pose_data):
        nonlocal last_coach_time, last_status
        # 更新介面狀態 (原本 ui.update_status 接收 5 個參數)
        ui.update_status(is_active, fps, feedback, x, y)
        
        if state.mode != "EXERCISE" or coach is None: return
        
        current_time = time.time()
        # 觸發條件：15秒冷卻且狀態文字有變且有座標數據
        if current_time - last_coach_time > 15 and pose_data:
            if feedback != last_status and ("正確" in feedback or "偏移" in feedback):
                execute_llm_request(feedback, pose_data)

    def execute_llm_request(status_text, landmarks):
        """ 啟動 LLM Worker """
        nonlocal last_coach_time, last_status
        print(f"[Coach] 正在獲取建議: {status_text}", flush=True)
        
        last_coach_time = time.time()
        last_status = status_text
        
        worker = LLMWorker(coach, status_text, landmarks)
        if hasattr(ui, 'show_coach'):
            worker.finished.connect(ui.show_coach)
        
        ui._current_llm_worker = worker 
        worker.start()

    # --- 5. 手動測試邏輯 (T 鍵) ---
    original_key_press = ui.keyPressEvent
    def manual_test_trigger(event):
        if event.key() == Qt.Key.Key_T:
            print("[Test] 手動測試開始...", flush=True)
            # 測試用假座標
            test_lms = {"R_Knee": [0.5, 0.8], "L_Knee": [0.5, 0.5]}
            execute_llm_request("正確右平衡 (測試)", test_lms)
        elif original_key_press:
            original_key_press(event)

    ui.keyPressEvent = manual_test_trigger
    video.status_update.connect(handle_coach_trigger)

    video.start()
    ui.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()