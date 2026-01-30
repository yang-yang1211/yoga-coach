import sys
import time
import os
import cv2
import mediapipe as mp
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QThread, pyqtSignal, QTimer, Qt
from PyQt6.QtGui import QImage

# 匯入專案模組
from ui.main import MainUI
from ai.models import PoseEngine, VTuberRenderer
from core.state import SystemState
from core.gesture_engine import GestureEngine
from ai.llm_engine import OllamaCoach  # 確保導入 Ollama 引擎
import json
def resource_path(relative_path):
    """ 取得資源絕對路徑，兼容開發環境與打包後的環境 """
    if hasattr(sys, '_MEIPASS'):
        # PyInstaller 運行時的臨時路徑
        return os.path.join(sys._MEIPASS, relative_path)
    # 開發環境下的當前路徑
    return os.path.join(os.path.abspath("."), relative_path)
# 1. 讀取 Llama 配置
config_path = resource_path("llama_config.json")
with open(config_path, "r", encoding="utf-8") as f:
    config = json.load(f)

# 2. 載入 XGBoost 模型
model_path = resource_path("yoga_pose_model_RightFoot.json")
# 假設您使用 xgboost 的 load_model 或自定義載入邏輯
# bst.load_model(model_path) 

# 3. 讀取標籤檔
labels_path = resource_path("rightfoot.json")
with open(labels_path, "r", encoding="utf-8") as f:
    labels = json.load(f)

# 強制輸出啟動訊號
print("[System] 正在啟動程序...", flush=True)

# --- 1. LLM 非同步處理執行緒 ---
class LLMWorker(QThread):
    finished = pyqtSignal(str)
    def __init__(self, coach, status):
        super().__init__()
        self.coach = coach
        self.status = status
        print(f"[LLM Worker] 準備請求 AI 建議: {self.status}", flush=True)

    def run(self):
        # 執行耗時的 Ollama 請求
        res = self.coach.ask(self.status)
        self.finished.emit(res)

# --- 2. 影像處理核心執行緒 ---
class VideoThread(QThread):
    raw_ready = pyqtSignal(QImage)
    vt_ready = pyqtSignal(QImage)
    # 狀態訊號對應 V14 UI: (is_active, fps, feedback, hand_x, hand_y)
    status_update = pyqtSignal(bool, float, str, float, float)
    gesture_cmd = pyqtSignal(str)

    def __init__(self, state):
        super().__init__()
        self.state = state
        print("[VideoThread] 正在初始化 AI 視覺引擎...", flush=True)
        self.pose = PoseEngine()
        self.vt = VTuberRenderer()
        self.gesture_engine = GestureEngine()
        
        # 初始化 MediaPipe Hands (僅操控模式使用)
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

            # --- 切換邏輯：運動用 Pose / 操控用 Hands ---
            if self.state.mode == "EXERCISE":
                # 在運動模式下呼叫 PoseEngine 的 process
                anno_frame, skeleton, feedback = self.pose.process(frame)
                if skeleton:
                    # 運動模式下使用 Pose 右食指 (20) 作為觸發點
                    r_idx = skeleton.landmark[20]
                    if r_idx.visibility > 0.5:
                        hand_x, hand_y = r_idx.x, r_idx.y
            else:
                # --- 修正處：正確處理手勢偵測邏輯 ---
                # 操控模式下使用 MediaPipe Hands 並對接 GestureEngine 方法
                results = self.hands.process(rgb_frame)
                feedback = "手部操控模式"
                
                if results.multi_hand_landmarks:
                    lm = results.multi_hand_landmarks[0]
                    # 呼叫 GestureEngine 定義的方法
                    is_active = self.gesture_engine.is_fist(lm)
                    cmd = self.gesture_engine.get_swipe_command(
                        lm, is_active, self.state.current_page
                    )
                    
                    # 取得食指指尖位置 (8 號點) 用於 M 鍵懸停
                    hand_x, hand_y = lm.landmark[8].x, lm.landmark[8].y
                    
                    if cmd:
                        self.gesture_cmd.emit(cmd)

            # 轉換 QImage
            def to_qimg(img):
                h, w, c = img.shape
                return QImage(img.data, w, h, c*w, QImage.Format.Format_BGR888).copy()

            self.raw_ready.emit(to_qimg(anno_frame))
            self.vt_ready.emit(to_qimg(self.vt.render(skeleton)))
            
            curr_time = time.time()
            fps = 1.0 / (curr_time - last_time) if (curr_time - last_time) > 0 else 0
            last_time = curr_time
            
            self.status_update.emit(is_active, fps, feedback, hand_x, hand_y)
            
        cap.release()
        self.hands.close()

# --- 3. 主程序入口 ---
def main():
    print("[Main] 進入主函式", flush=True)
    app = QApplication(sys.argv)
    
    state = SystemState()
    ui = MainUI(state)
    
    # 💡 關鍵點：在這裡強制初始化 OllamaCoach
    print("[Main] 正在強制初始化 Ollama 教練...", flush=True)
    try:
        coach = OllamaCoach(model="llama3")
        print("[Main] ✅ OllamaCoach 物件建立完成", flush=True)
    except Exception as e:
        print(f"[Main] ❌ OllamaCoach 初始化失敗: {e}", flush=True)
        coach = None

    video = VideoThread(state)
    video.raw_ready.connect(ui.update_video)
    video.vt_ready.connect(ui.update_vtuber)
    video.status_update.connect(ui.update_status)
    video.gesture_cmd.connect(ui.handle_command)

    # --- 4. 智慧教練觸發邏輯 ---
    last_coach_time = 0
    last_status = ""

    def handle_coach_trigger(is_active, fps, feedback, x, y):
        nonlocal last_coach_time, last_status
        if state.mode != "EXERCISE" or coach is None: return
        
        current_time = time.time()
        # 觸發條件：15秒冷卻且狀態文字有變 (例如: 偏移 -> 正確)
        if current_time - last_coach_time > 15 and feedback != last_status:
            if "正確" in feedback or "偏移" in feedback:
                execute_llm_request(feedback)

    def execute_llm_request(status_text):
        """執行 LLM 請求的共用函式"""
        nonlocal last_coach_time, last_status
        print(f"[Coach] 觸發 AI 建議請求: {status_text}", flush=True)
        last_coach_time = time.time()
        last_status = status_text
        
        worker = LLMWorker(coach, status_text)
        if hasattr(ui, 'show_coach'):
            worker.finished.connect(ui.show_coach)
        worker.start()
        ui._llm_worker = worker

    # --- 5. 手動測試邏輯 (按下鍵盤 T 鍵觸發) ---
    def manual_test_trigger(event):
        if event.key() == Qt.Key.Key_T:
            print("[Test] 檢測到按下 T 鍵，正在手動觸發 LLM 測試...", flush=True)
            execute_llm_request("正確右平衡 (手動測試)")
        # 呼叫原本的 keyPressEvent (如果有)
        MainUI.keyPressEvent(ui, event)

    # 將測試函式注入 UI 實例
    ui.keyPressEvent = manual_test_trigger

    video.status_update.connect(handle_coach_trigger)

    video.start()
    print("[Main] 正在顯示主視窗...", flush=True)
    print("[Main] 💡 提示：您可以在視窗啟動後按下鍵盤『T』鍵來手動測試 LLM 輸出。", flush=True)
    ui.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()