from PySide6.QtCore import Qt, QTimer, Slot
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel

class TransparentOverlay(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("UMAYOCR_TRANSLATION_OVERLAY")
        self.setWindowFlags(Qt.WindowStaysOnTopHint |
                            Qt.FramelessWindowHint |
                            Qt.WindowDoesNotAcceptFocus |
                            Qt.Tool |
                            Qt.X11BypassWindowManagerHint)

        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setMouseTracking(True)
        self.resize(800, 200)
        
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        
        # Style variables
        self.font_family = "Arial"
        self.font_size = 20
        self.font_color = "white"
        self.bg_color = "#000000"
        self.bg_opacity = 180
        
        self.label = QLabel("Translation will appear here.")
        self.label.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.label.setWordWrap(True)
        self.label.setAlignment(Qt.AlignCenter)
        self.update_style()
        self.layout.addWidget(self.label)
        
        self.hide_timer = QTimer(self)
        self.hide_timer.setSingleShot(True)
        self.hide_timer.timeout.connect(lambda: self.label.setText(""))

        self.set_mode(False)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.raise_)
        self.timer.start(2000)

        # Manual drag state (X11BypassWindowManagerHint bypasses WM)
        self._drag_mode = None  # "move" or "resize"
        self._drag_start_pos = None
        self._drag_start_geometry = None

    def update_style(self):
        r = int(self.bg_color[1:3], 16)
        g = int(self.bg_color[3:5], 16)
        b = int(self.bg_color[5:7], 16)
        style = (
            f"color: {self.font_color}; "
            f"font-family: '{self.font_family}'; "
            f"font-size: {self.font_size}px; "
            f"font-weight: bold; "
            f"background: rgba({r},{g},{b},{self.bg_opacity}); border-radius: 6px; padding: 10px;"
        )
        self.label.setStyleSheet(style)

    @Slot(str)
    def set_font_family(self, family):
        self.font_family = family
        self.update_style()

    @Slot(int)
    def set_font_size(self, size):
        self.font_size = size
        self.update_style()

    @Slot(str)
    def set_font_color(self, color):
        self.font_color = color
        self.update_style()

    @Slot(str)
    def set_bg_color(self, color):
        self.bg_color = color
        self.update_style()

    @Slot(int)
    def set_bg_opacity(self, opacity):
        self.bg_opacity = opacity
        self.update_style()

    @Slot(str)
    def update_text(self, text):
        self.label.setText(text)
        self.raise_()
        self.hide_timer.start(10000)

    def set_mode(self, scan):
        self.setAttribute(Qt.WA_TransparentForMouseEvents, scan)
        self.setCursor(Qt.ArrowCursor if scan else Qt.SizeAllCursor)
        if scan:
            self.hide_timer.start(10000)
        else:
            self.hide_timer.stop()
            self.label.setText(_("Translation will appear here."))

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._drag_start_pos = event.globalPosition().toPoint()
            self._drag_start_geometry = self.geometry()
            if event.position().x() > self.width() - 20 and event.position().y() > self.height() - 20:
                self._drag_mode = "resize"
                self.setCursor(Qt.SizeFDiagCursor)
            else:
                self._drag_mode = "move"
                self.setCursor(Qt.SizeAllCursor)
            event.accept()

    def mouseMoveEvent(self, event):
        if self._drag_mode is None:
            if event.position().x() > self.width() - 20 and event.position().y() > self.height() - 20:
                self.setCursor(Qt.SizeFDiagCursor)
            else:
                self.setCursor(Qt.SizeAllCursor)
            return

        if self._drag_start_pos is None:
            return

        delta = event.globalPosition().toPoint() - self._drag_start_pos
        if self._drag_mode == "move":
            self.move(self._drag_start_geometry.x() + delta.x(),
                      self._drag_start_geometry.y() + delta.y())
        elif self._drag_mode == "resize":
            new_w = max(200, self._drag_start_geometry.width() + delta.x())
            new_h = max(100, self._drag_start_geometry.height() + delta.y())
            self.resize(new_w, new_h)
        event.accept()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._drag_mode = None
            self._drag_start_pos = None
            self._drag_start_geometry = None
            if event.position().x() > self.width() - 20 and event.position().y() > self.height() - 20:
                self.setCursor(Qt.SizeFDiagCursor)
            else:
                self.setCursor(Qt.SizeAllCursor)
            event.accept()
