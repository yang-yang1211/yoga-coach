from PyQt6.QtWidgets import (QMainWindow, QWidget, QLabel, QFrame, 
                             QVBoxLayout, QHBoxLayout, QGraphicsBlurEffect)
from PyQt6.QtCore import Qt, QPropertyAnimation, QPoint, QEasingCurve, QTimer, QParallelAnimationGroup
from PyQt6.QtGui import QPixmap, QFont, QPainter, QColor, QPen
import time

class HoverButton(QFrame):
    """
    具有環形進度條的懸浮按鈕
    """
    def __init__(self, parent, text="M"):
        super().__init__(parent)
        self.setFixedSize(100, 100)
        self.text = text
        self.progress = 0  # 0 ~ 100
        self.setStyleSheet("background: transparent;")

    def set_progress(self, val):
        self.progress = val
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # 1. 畫底圓
        painter.setBrush(QColor(30, 30, 30, 180))
        painter.setPen(QPen(QColor(255, 255, 255, 50), 3))
        painter.drawEllipse(10, 10, 80, 80)

        # 2. 畫進度環
        if self.progress > 0:
            pen = QPen(QColor(0, 229, 255), 6)
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            painter.setPen(pen)
            span_angle = -int(self.progress * 3.6 * 16)
            painter.drawArc(10, 10, 80, 80, 90 * 16, span_angle)

        # 3. 畫文字
        painter.setPen(QColor(255, 255, 255))
        painter.setFont(QFont("Consolas", 28, QFont.Weight.Bold))
        painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, self.text)

class GlassBoard(QFrame):
    def __init__(self, parent, title, color_code="#ffffff"):
        super().__init__(parent)
        self.setFixedSize(650, 480)
        self.setObjectName("GlassBoard")
        self.setStyleSheet(f"""
            #GlassBoard {{
                background-color: rgba(30, 30, 30, 220);
                border: 2px solid {color_code}55;
                border-radius: 50px;
            }}
            QLabel {{ background: transparent; color: white; }}
        """)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(50, 50, 50, 50)
        self.title_label = QLabel(title)
        self.title_label.setFont(QFont("Microsoft JhengHei", 28, QFont.Weight.Bold))
        self.title_label.setStyleSheet(f"color: {color_code};")
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.title_label)
        
        self.desc_label = QLabel("空間計算板塊已拉入\n[ 手勢反向揮動可將此板塊推回邊緣 ]")
        self.desc_label.setFont(QFont("Microsoft JhengHei", 14))
        self.desc_label.setStyleSheet("color: rgba(255, 255, 255, 120);")
        self.desc_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.desc_label)
        layout.addStretch()

class MainUI(QMainWindow):
    def __init__(self, state):
        super().__init__()
        self.state = state
        self.setWindowTitle("Spatial UI Framework v15.5")
        self.setMinimumSize(1200, 850)
        self.setStyleSheet("background-color: black;")
        
        self.active_board = None
        self.hover_start_time = None 
        self.trigger_duration = 1.5   
        
        # --- 教練建議狀態管理 ---
        self.coach_advice_active = False # 標記目前是否正在顯示教練建議
        self.coach_advice_text = ""

        # --- 1. 背景與影像 ---
        self.video_bg = QLabel(self)
        self.video_bg.setGeometry(0, 0, 1200, 850)
        self.video_bg.setScaledContents(True)
        self.blur_effect = QGraphicsBlurEffect()
        self.blur_effect.setBlurRadius(0)
        self.video_bg.setGraphicsEffect(self.blur_effect)

        self.vt_view = QLabel(self)
        self.vt_view.setFixedSize(320, 240)
        self.vt_view.setStyleSheet("background-color: rgba(0, 0, 0, 150); border: 2px solid #00e5ff; border-radius: 20px;")
        self.vt_view.move(50, 50)

        # --- 2. M 模式懸停按鈕 ---
        self.m_button = HoverButton(self, "M")
        self.update_m_btn_pos()

        # --- 3. 板塊與提示列 ---
        self.boards = {
            "Data": GlassBoard(self, "📊 數據中心", "#10b981"),
            "Settings": GlassBoard(self, "⚙ 系統設定", "#3b82f6"),
            "Calendar": GlassBoard(self, "📅 訓練計畫", "#a855f7")
        }
        self.reset_board_locations()
        self.setup_hint_bar()
        
        self.video_bg.lower()
        self.m_button.raise_()

    def show_coach(self, text):
        """ 當收到 LLM 建議時，將其顯示在提示窗中 """
        print(f"[UI 顯示] 教練建議已整合至提示窗: {text}")
        
        # 1. 開啟建議模式標記
        self.coach_advice_active = True
        self.coach_advice_text = text
        
        # 2. 立即更新 UI 視覺 (使用顯眼的金色/亮綠色)
        self.status_icon.setText("💡")
        self.status_text.setText(f"教練建議：{text}")
        self.status_text.setStyleSheet("color: #fbbf24; font-weight: bold; font-size: 16px;") # 金色字體
        self.hint_bar.setStyleSheet("""
            background-color: rgba(6, 78, 59, 230); 
            border: 3px solid #fbbf24; 
            border-radius: 45px;
        """)
        
        # 3. 8 秒後自動恢復普通狀態顯示
        QTimer.singleShot(8000, self.reset_coach_status)

    def reset_coach_status(self):
        """ 恢復一般狀態顯示 """
        self.coach_advice_active = False
        self.status_text.setStyleSheet("color: white; font-weight: normal; font-size: 14px;")
        # 顏色會由 update_status 下一次循環時根據模式自動修正

    def setup_hint_bar(self):
        self.hint_bar = QFrame(self)
        self.hint_bar.setFixedSize(800, 90)
        self.hint_bar.setStyleSheet("background-color: rgba(0,0,0,200); border-radius: 45px; border: 1px solid rgba(255,255,255,40);")
        layout = QHBoxLayout(self.hint_bar)
        self.status_icon = QLabel("👤"); self.status_icon.setFont(QFont("Segoe UI Emoji", 20))
        self.status_text = QLabel("初始化系統..."); self.status_text.setFont(QFont("Microsoft JhengHei", 14))
        self.fps_label = QLabel("FPS: 0.0")
        layout.addWidget(self.status_icon); layout.addWidget(self.status_text, 1); layout.addWidget(self.fps_label)
        self.update_hint_pos()

    def update_m_btn_pos(self):
        self.m_button.move(self.width() - 150, 50)

    def toggle_mode_logic(self):
        self.state.toggle_mode()
        if self.state.mode == "EXERCISE" and self.active_board:
            self.animate_back()
        self.status_text.setText(f"已切換至: {'運動模式' if self.state.mode == 'EXERCISE' else '操控模式'}")

    def update_status(self, is_active, fps, feedback, hand_x, hand_y):
        """ 核心偵測邏輯 """
        self.fps_label.setText(f"FPS: {fps:.1f}")
        
        # --- 若正在顯示教練建議，則跳過一般的文字更新，直到時間結束 ---
        if self.coach_advice_active:
            return

        # 處理懸停邏輯 (略)
        if hand_x > 0 and hand_y > 0:
            px = hand_x * self.width(); py = hand_y * self.height()
            btn_rect = self.m_button.geometry()
            if btn_rect.contains(int(px), int(py)):
                if self.hover_start_time is None: self.hover_start_time = time.time()
                elapsed = time.time() - self.hover_start_time
                progress = min(100, int((elapsed / self.trigger_duration) * 100))
                self.m_button.set_progress(progress)
                if elapsed >= self.trigger_duration:
                    self.toggle_mode_logic()
                    self.hover_start_time = None; self.m_button.set_progress(0)
            else:
                self.hover_start_time = None; self.m_button.set_progress(0)
        else:
            self.hover_start_time = None; self.m_button.set_progress(0)

        # 根據模式更新提示列外觀
        if self.state.mode == "EXERCISE":
            self.status_icon.setText("🏃")
            self.status_text.setText(f"運動模式 | {feedback}")
            self.hint_bar.setStyleSheet("background-color: rgba(16, 185, 129, 180); border: 2px solid #10b981; border-radius: 45px;")
        else:
            self.status_icon.setText("✊" if is_active else "🖐")
            prefix = "【感應中】" if is_active else "遠距操控模式"
            self.status_text.setText(f"{prefix} | {feedback if feedback else '手部懸停 M 鍵切換模式'}")
            if is_active:
                self.hint_bar.setStyleSheet("background-color: rgba(59, 130, 246, 180); border: 2px solid #3b82f6; border-radius: 45px;")
            else:
                self.hint_bar.setStyleSheet("background-color: rgba(0, 0, 0, 200); border: 1px solid rgba(255, 255, 255, 40); border-radius: 45px;")

    def reset_board_locations(self):
        w, h = self.width(), self.height()
        self.boards["Data"].move((w - 650) // 2, -440)
        self.boards["Settings"].move((w - 650) // 2, h - 40)
        self.boards["Calendar"].move(-610, (h - 480) // 2)

    def handle_command(self, cmd):
        if self.state.mode == "EXERCISE": return
        mapping = {"TOP": "Data", "DataPage": "Data", "BOTTOM": "Settings", "SettingsPage": "Settings", 
                   "LEFT": "Calendar", "CalendarPage": "Calendar", "CLOSE": "CLOSE", "HomePage": "CLOSE"}
        real_cmd = mapping.get(cmd)
        if not real_cmd: return
        if real_cmd == "CLOSE": self.animate_back()
        else: self.animate_pull_in(real_cmd)

    def animate_pull_in(self, direction):
        if self.active_board == direction: return
        if self.active_board: self.animate_back(silent=True)
        target = self.boards.get(direction)
        if not target: return
        target.raise_(); self.active_board = direction; self.state.current_page = f"{direction}Page"
        self.pull_group = QParallelAnimationGroup()
        move = QPropertyAnimation(target, b"pos")
        move.setDuration(600); move.setStartValue(target.pos())
        move.setEndValue(QPoint((self.width() - 650) // 2, (self.height() - 480) // 2))
        move.setEasingCurve(QEasingCurve.Type.OutCubic); self.pull_group.addAnimation(move)
        blur = QPropertyAnimation(self.blur_effect, b"blurRadius")
        blur.setDuration(600); blur.setEndValue(25.0); self.pull_group.addAnimation(blur)
        self.pull_group.start()

    def animate_back(self, silent=False):
        if not self.active_board: return
        target = self.boards[self.active_board]; direction = self.active_board
        self.active_board = None; self.state.current_page = "HomePage"
        w, h = self.width(), self.height(); end_p = QPoint(0,0)
        if direction == "Data": end_p = QPoint((w - 650) // 2, -440)
        elif direction == "Settings": end_p = QPoint((w - 650) // 2, h - 40)
        elif direction == "Calendar": end_p = QPoint(-610, (h - 480) // 2)
        self.back_group = QParallelAnimationGroup()
        move_back = QPropertyAnimation(target, b"pos")
        move_back.setDuration(500); move_back.setEndValue(end_p)
        move_back.setEasingCurve(QEasingCurve.Type.OutCubic); self.back_group.addAnimation(move_back)
        if not silent:
            clear_blur = QPropertyAnimation(self.blur_effect, b"blurRadius")
            clear_blur.setDuration(500); clear_blur.setEndValue(0.0); self.back_group.addAnimation(clear_blur)
        self.back_group.start()

    def update_video(self, qimg): self.video_bg.setPixmap(QPixmap.fromImage(qimg.copy()))
    def update_vtuber(self, qimg): self.vt_view.setPixmap(QPixmap.fromImage(qimg.copy()))
    def update_hint_pos(self): self.hint_bar.move((self.width() - 800) // 2, self.height() - 120)
    def resizeEvent(self, event):
        self.video_bg.setGeometry(0, 0, self.width(), self.height())
        self.update_m_btn_pos(); self.update_hint_pos()
        if not self.active_board: self.reset_board_locations()
        super().resizeEvent(event)
    def closeEvent(self, event): 
        self.state.stop_signal = True; super().closeEvent(event)