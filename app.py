import sys
from PyQt6.QtWidgets import QApplication
from ui.main import MainUI
from core.state import SystemState
from core.video_processor import VideoProcessor

def main():
    # 1. 建立 Qt 應用程式
    app = QApplication(sys.argv)
    
    # 2. 初始化全域狀態
    state = SystemState()
    
    # 3. 初始化 UI 視窗與背景處理器
    # 注意: VideoProcessor 需要你之前寫好的 core/video_processor.py
    window = MainUI(state)
    processor = VideoProcessor(state)
    
    # 4. 連接訊號 (Signals) 與 槽 (Slots)
    processor.image_ready.connect(window.update_video)
    processor.status_update.connect(window.update_status)
    processor.gesture_cmd.connect(window.handle_command)
    
    # 5. 啟動背景執行緒
    processor.start()
    
    # 6. 顯示視窗並啟動主迴圈
    window.show()
    
    # 7. 關閉處理
    status = app.exec()
    state.stop_signal = True
    processor.wait()
    sys.exit(status)

if __name__ == "__main__":
    main()