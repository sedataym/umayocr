import os
from PySide6.QtCore import Qt, QRect, QPoint, Signal, QObject, QEventLoop
from PySide6.QtGui import QPainter, QColor, QPen
from PySide6.QtWidgets import QApplication, QWidget
from src.core.sniper.base_sniper import BaseSniper

class SelectionManager(QObject):
    """Manages the selection state across multiple monitors."""
    selectionChanged = Signal()
    selectionFinished = Signal(QRect)

    def __init__(self):
        super().__init__()
        self.start_pos = QPoint()
        self.end_pos = QPoint()
        self.is_selecting = False

    def startSelection(self, pos):
        self.start_pos = pos
        self.end_pos = pos
        self.is_selecting = True
        self.selectionChanged.emit()

    def updateSelection(self, pos):
        if self.is_selecting:
            self.end_pos = pos
            self.selectionChanged.emit()

    def finishSelection(self):
        if not self.is_selecting:
            return
        self.is_selecting = False
        rect = QRect(self.start_pos, self.end_pos).normalized()
        self.selectionFinished.emit(rect)

class OverlayWindow(QWidget):
    """An overlay window for a single screen."""
    def __init__(self, screen, manager):
        super().__init__()
        self.manager = manager
        self.screen_geometry = screen.geometry()
        
        self.setWindowFlags(
            Qt.FramelessWindowHint |
            Qt.WindowStaysOnTopHint |
            Qt.X11BypassWindowManagerHint |
            Qt.Tool
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        
        self.setGeometry(self.screen_geometry)
        self.setCursor(Qt.CrossCursor)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.StrongFocus)
        
        self.manager.selectionChanged.connect(self.update)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(0, 0, 0, 128))

        if self.manager.is_selecting:
            global_rect = QRect(self.manager.start_pos, self.manager.end_pos).normalized()
            local_intersect = global_rect.intersected(self.screen_geometry)
            
            if not local_intersect.isEmpty():
                local_rect = local_intersect.translated(-self.screen_geometry.topLeft())
                painter.setCompositionMode(QPainter.CompositionMode_Clear)
                painter.fillRect(local_rect, Qt.transparent)
                painter.setCompositionMode(QPainter.CompositionMode_SourceOver)
                painter.setPen(QPen(Qt.red, 2))
                painter.drawRect(local_rect)

    def mousePressEvent(self, event):
        self.setFocus()
        if event.button() == Qt.LeftButton:
            self.manager.startSelection(event.globalPosition().toPoint())

    def mouseMoveEvent(self, event):
        self.manager.updateSelection(event.globalPosition().toPoint())

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.manager.finishSelection()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self.manager.selectionFinished.emit(QRect())

class CoreSniper(BaseSniper):
    def get_region(self) -> QRect | None:
        """Selects a region on the screen using a native multi-monitor overlay."""

        manager = SelectionManager()
        loop = QEventLoop()
        result_rect = [None]

        def on_finished(rect):
            if rect.isValid() and rect.width() > 5 and rect.height() > 5:
                result_rect[0] = rect
            loop.quit()

        manager.selectionFinished.connect(on_finished)

        windows = []
        for screen in QApplication.screens():
            win = OverlayWindow(screen, manager)
            win.show()
            win.activateWindow()
            win.raise_()
            windows.append(win)

        loop.exec()
        
        for win in windows:
            win.close()
            
        return result_rect[0]
