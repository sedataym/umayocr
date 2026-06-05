import sys
import os

# Add project root (parent of src) to sys.path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication
from src.ui.main_window import ControlPanel
from src.i18n import init_i18n

def main():
    # Initialize internationalization
    init_i18n()
    
    os.environ["QT_QPA_PLATFORM"] = "xcb"
    
    app = QApplication(sys.argv)
    
    # Set application icon
    icon_path = os.path.join(os.path.dirname(__file__), "ui", "assets", "UmayOCR.png")
    app.setWindowIcon(QIcon(icon_path))
    
    panel = ControlPanel()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
