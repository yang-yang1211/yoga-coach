class SystemState:
    """
    管理全域共享狀態，確保背景運算與介面顯示同步
    """
    def __init__(self):
        self.mode = "CONTROL"        # 當前模式: CONTROL (操控) 或 EXERCISE (運動)
        self.current_page = "HomePage" # 當前顯示的板塊頁面
        self.stop_signal = False      # 程式關閉信號

    def toggle_mode(self):
        """切換模式"""
        self.mode = "CONTROL" if self.mode == "EXERCISE" else "EXERCISE"