import cv2
import time
import mediapipe as mp
from PyQt6.QtCore import QThread, pyqtSignal
from PyQt6.QtGui import QImage
from ai.models import PoseCorrector, VTuberRenderer
from core.gesture_engine import GestureEngine

class VideoProcessor(QThread):
    """
    背景執行緒：負責影像運算，並回傳手部座標供 UI 懸停判斷
    """
    image_ready = pyqtSignal(QImage)
    vt_image_ready = pyqtSignal(QImage)
    gesture_cmd = pyqtSignal(str)
    # 修改訊號：新增 hand_x (float), hand_y (float) 用於 UI 懸停偵測
    status_update = pyqtSignal(bool, float, str, float, float) 

    def __init__(self, state):
        super().__init__()
        self.state = state
        self.gesture_engine = GestureEngine()
        self.pose_model = PoseCorrector()
        self.vt_renderer = VTuberRenderer()
        
        self.mp_hands = mp.solutions.hands
        self.hands = self.mp_hands.Hands(min_detection_confidence=0.7, max_num_hands=1)

    def run(self):
        cap = cv2.VideoCapture(0)
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        
        prev_time = time.time()
        
        while not self.state.stop_signal:
            ret, frame = cap.read()
            if not ret: continue
            
            curr_time = time.time()
            fps = 1.0 / (curr_time - prev_time) if (curr_time - prev_time) > 0 else 0
            prev_time = curr_time
            
            frame = cv2.flip(frame, 1)
            h, w, ch = frame.shape
            
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            results = self.hands.process(frame_rgb)
            
            is_active = False
            ml_feedback = ""
            hand_x, hand_y = -1.0, -1.0 # 預設座標（-1代表畫面中無手）
            
            if results.multi_hand_landmarks:
                lm = results.multi_hand_landmarks[0]
                is_active = self.gesture_engine.is_fist(lm)
                
                # 取得食指尖 (Index Finger Tip) 作為懸停判斷點
                index_finger = lm.landmark[8]
                hand_x, hand_y = index_finger.x, index_finger.y
                
                # 手勢指令判斷
                cmd = self.gesture_engine.get_swipe_command(lm, is_active, self.state.current_page)
                if cmd:
                    direction_map = {"DataPage": "DataPage", "SettingsPage": "SettingsPage", "CalendarPage": "CalendarPage", "CLOSE": "CLOSE"}
                    if cmd in direction_map:
                        self.gesture_cmd.emit(direction_map[cmd])

            if self.state.mode == "EXERCISE" or self.state.current_page == "HomePage":
                ml_res = self.pose_model.process_frame(frame)
                ml_feedback = ml_res["feedback_message"]
                vt_frame = self.vt_renderer.draw(ml_res["skeleton_data"])
                
                vh, vw, vc = vt_frame.shape
                vt_qimg = QImage(vt_frame.data, vw, vh, vc * vw, QImage.Format.Format_BGR888)
                self.vt_image_ready.emit(vt_qimg)

            # 傳送座標到 UI 進行懸停判斷
            self.status_update.emit(is_active, fps, ml_feedback, hand_x, hand_y)
            
            qimg = QImage(frame.data, w, h, ch * w, QImage.Format.Format_BGR888)
            self.image_ready.emit(qimg)

        cap.release()