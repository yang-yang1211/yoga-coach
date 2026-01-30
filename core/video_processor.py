import cv2
import time
from PyQt6.QtCore import QThread, pyqtSignal
from PyQt6.QtGui import QImage
from ai.models import PoseEngine, VTuberRenderer
from core.gesture_engine import GestureEngine

class VideoProcessor(QThread):
    image_ready = pyqtSignal(QImage)
    vt_image_ready = pyqtSignal(QImage)
    status_update = pyqtSignal(bool, float, str, float, float)
    gesture_cmd = pyqtSignal(str)

    def __init__(self, state):
        super().__init__()
        self.state = state
        # 確保在 V14 結構下正確初始化
        self.pose_model = PoseEngine()
        self.vt_renderer = VTuberRenderer()
        self.gesture_engine = GestureEngine()

    def run(self):
        print("[VideoProcessor] 啟動攝影機串流...", flush=True)
        cap = cv2.VideoCapture(0)
        last_time = time.time()
        
        while not self.state.stop_signal:
            ret, frame = cap.read()
            if not ret: continue
            
            frame = cv2.flip(frame, 1)
            
            # --- 關鍵修正處：現在接收 3 個參數 ---
            anno_frame, skeleton, feedback = self.pose_model.process(frame)
            
            # 渲染畫布
            vt_frame = self.vt_renderer.render(skeleton)
            
            # 手勢處理
            is_active = False
            hand_x, hand_y = -1, -1
            if self.state.mode == "CONTROL":
                is_active, cmd, (hand_x, hand_y) = self.gesture_engine.detect(frame)
                if cmd: self.gesture_cmd.emit(cmd)

            # 計算 FPS
            curr_time = time.time()
            fps = 1.0 / (curr_time - last_time) if (curr_time - last_time) > 0 else 0
            last_time = curr_time

            # 發送訊號
            self.image_ready.emit(self._to_qimage(anno_frame))
            self.vt_image_ready.emit(self._to_qimage(vt_frame))
            self.status_update.emit(is_active, fps, feedback, hand_x, hand_y)

        cap.release()

    def _to_qimage(self, cv_img):
        h, w, ch = cv_img.shape
        return QImage(cv_img.data, w, h, ch * w, QImage.Format.Format_BGR888).copy()