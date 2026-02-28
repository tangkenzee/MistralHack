import sys
from PyQt6.QtWidgets import QApplication, QMainWindow, QLineEdit, QVBoxLayout, QWidget
from PyQt6.QtCore import Qt, QRect, QPoint, QTimer
from PyQt6.QtGui import QPainter, QColor, QBrush, QPen

class GeneralOverlay(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.showMaximized()

        # UI State
        self.target_rect = None  # This will be the "hole" in the overlay
        self.is_dimmed = True

        # Search Bar Setup
        self.container = QWidget()
        self.setCentralWidget(self.container)
        layout = QVBoxLayout(self.container)
        self.input = QLineEdit()
        self.input.setPlaceholderText("Describe a button on your screen (e.g. 'The red X')")
        self.input.setFixedWidth(500)
        self.input.setStyleSheet("background: white; color: black; padding: 10px; border-radius: 20px;")
        layout.addWidget(self.input, alignment=Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter)
        
        self.input.returnPressed.connect(self.simulate_ai_response)

    def simulate_ai_response(self):
        # 1. Hide briefly and capture (Logic from previous step goes here)
        # 2. For testing, we simulate finding a button at center-screen
        screen_center = self.screen().geometry().center()
        self.target_rect = QRect(screen_center.x() - 50, screen_center.y() - 50, 100, 100)
        self.update() # Trigger redraw

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        if self.is_dimmed:
            # Draw the "Dimmer" layer
            painter.setBrush(QColor(0, 0, 0, 180)) # Dark transparent grey
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRect(self.rect())

        if self.target_rect:
            # THE MAGIC: "Clear" the pixels in the target area to see the real screen
            painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Clear)
            painter.setBrush(QBrush(Qt.GlobalColor.transparent))
            painter.drawRoundedRect(self.target_rect, 10, 10)
            
            # Draw a glowing border around the hole
            painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)
            pen = QPen(QColor(0, 255, 255), 4) # Cyan glow
            painter.setPen(pen)
            painter.drawRoundedRect(self.target_rect, 10, 10)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = GeneralOverlay()
    sys.exit(app.exec())