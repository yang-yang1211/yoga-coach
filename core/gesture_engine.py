class GestureEngine:
    """
    純邏輯模組：優化累積位移演算法，支援偵錯輸出，並修正頁面字串匹配問題。
    """
    def __init__(self):
        # --- 1. 系統參數優化 ---
        self.SWIPE_THRESHOLD = 0.07          # 極靈敏門檻 (相對於螢幕寬高的位移比例)
        self.GESTURE_COOLDOWN_FRAMES = 15    # 觸發後的冷卻幀數
        self.GESTURE_PURITY = 1.1            # 進入板塊時的方向純粹度要求
        
        # --- 2. 狀態變數 ---
        self.ref_x = 0.0                     # 參考起點 X
        self.ref_y = 0.0                     # 參考起點 Y
        self.gesture_cooldown = 0            # 冷卻計時器
        self.was_activated = False           # 記錄前一幀是否處於握拳狀態

    def is_fist(self, lm):
        """
        握拳判定：檢查 4 根手指尖是否低於第二指節 (Y 軸向下為正)
        """
        tips = [8, 12, 16, 20]
        pips = [6, 10, 14, 18]
        count = 0
        for i in range(4):
            if lm.landmark[tips[i]].y > lm.landmark[pips[i]].y:
                count += 1
        
        fist_detected = count >= 3
        return fist_detected

    def get_swipe_command(self, lm, is_activated, current_page):
        """
        手勢指令判定：支援物理空間拉動，並修正指令與 PyQt UI 鍵值的對應關係。
        指令對應：
        - TOP: 數據中心 (從上拉下)
        - BOTTOM: 系統設定 (從下往上)
        - LEFT: 訓練日曆 (從左往右)
        - CLOSE: 返回主頁
        """
        # 處理冷卻
        if self.gesture_cooldown > 0:
            self.gesture_cooldown -= 1
            self.was_activated = is_activated
            return None

        # 取得當前位置 (手腕)
        wrist = lm.landmark[0]
        curr_x, curr_y = wrist.x, wrist.y
        command = None

        # --- 偵錯區：顯示基本狀態 ---
        status_str = "✊ 握拳" if is_activated else "🖐 放開"
        print(f"\r[狀態] {status_str} | 頁面: {current_page:<12} | 坐標: ({curr_x:.3f}, {curr_y:.3f})", end="")

        if is_activated:
            # 剛握拳或失去參考點：初始化參考起點
            if not self.was_activated or self.ref_x == 0.0:
                self.ref_x = curr_x
                self.ref_y = curr_y
                self.was_activated = True
                print(f"\n[DEBUG] 設定參考點: ({self.ref_x:.3f}, {self.ref_y:.3f})")
                return None
            
            # 計算相對於起點的總累積位移
            dx = curr_x - self.ref_x
            dy = curr_y - self.ref_y
            abs_dx = abs(dx)
            abs_dy = abs(dy)

            # --- 偵錯區：顯示位移量 ---
            print(f" | 累積位移 dX: {dx:+.3f}, dY: {dy:+.3f} (門檻: {self.SWIPE_THRESHOLD})", end="")

            # --- 反向重置機制 (修正為與 UI 傳入字串一致) ---
            reset_dist = 0.02
            if current_page == "DataPage" and dy > reset_dist: 
                self.ref_y = curr_y
                print(f"\n[DEBUG] 反向修正: 重置 Y 軸起點至最低點")
            elif current_page == "SettingsPage" and dy < -reset_dist: 
                self.ref_y = curr_y
                print(f"\n[DEBUG] 反向修正: 重置 Y 軸起點至最高點")
            elif current_page == "CalendarPage" and dx > reset_dist: 
                self.ref_x = curr_x
                print(f"\n[DEBUG] 反向修正: 重置 X 軸起點至最右點")

            # --- 判斷邏輯 A：主頁 (負責「拉入」板塊) ---
            # 這裡的指令字串已修正為與 UI 的 boards 鍵值一致 (TOP, BOTTOM, LEFT)
            if current_page == "HomePage":
                if abs_dy > abs_dx * self.GESTURE_PURITY:
                    if dy > self.SWIPE_THRESHOLD:
                        command = "DataPage"      # 數據中心 (向下揮，由上拉出)
                    elif dy < -self.SWIPE_THRESHOLD:
                        command = "SettingsPage"   # 系統設定 (向上揮，由下拉出)
                elif abs_dx > abs_dy * self.GESTURE_PURITY:
                    if dx > self.SWIPE_THRESHOLD:
                        command = "CalendarPage"     # 訓練日曆 (向右揮，由左拉出)
            
            # --- 判斷邏輯 B：子頁面 (負責「推回」主頁) ---
            else:
                if current_page == "DataPage" and dy < -self.SWIPE_THRESHOLD:
                    command = "CLOSE"      # 向上推回
                elif current_page == "SettingsPage" and dy > self.SWIPE_THRESHOLD:
                    command = "CLOSE"      # 向下推回
                elif current_page == "CalendarPage" and dx < -self.SWIPE_THRESHOLD:
                    command = "CLOSE"      # 向左推回
        else:
            # 手掌張開時，清空參考點
            if self.was_activated:
                print(f"\n[DEBUG] 手掌張開，清除參考點")
            self.reset_gesture_state()
            self.was_activated = False

        # 指令觸發後的清理與冷卻
        if command:
            print(f"\n[!!!] 觸發指令: {command} (冷卻開始)")
            self.gesture_cooldown = self.GESTURE_COOLDOWN_FRAMES
            self.reset_gesture_state()
            return command

        return None

    def reset_gesture_state(self):
        """重置參考起點與狀態"""
        self.ref_x = 0.0
        self.ref_y = 0.0