import time
import pickle
import os
from PySide6.QtCore import Qt, QRect, QPoint, QTimer, Slot
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QComboBox, QPushButton, QApplication, QFontComboBox, QSpinBox, QDoubleSpinBox, QHBoxLayout, QColorDialog, QProgressBar, QTabWidget, QListWidget, QLineEdit, QMessageBox
from src.core.worker import OCRWorker
from src.ui.result_popup import TransparentOverlay
from src.core.sniper import SniperFactory
from src.config import OCR_ENGINES, TRANSLATION_ENGINES, LANGUAGES, SETTINGS_FILE, PRESETS_FILE, DPI_SCALE_DEFAULT, SCREENSHOT_ENGINES
from src.i18n import _

class ControlPanel(QWidget):
    def __init__(self):
        super().__init__()
        self.worker = OCRWorker()
        self.overlay = TransparentOverlay()
        self.setWindowTitle("UmayOCR General Instant Translator")
        
        # Set window icon
        icon_path = os.path.join(os.path.dirname(__file__), "assets", "UmayOCR.png")
        self.setWindowIcon(QIcon(icon_path))
        
        # Disable maximization
        self.setWindowFlags(self.windowFlags() | Qt.MSWindowsFixedSizeDialogHint)
        self.setWindowFlag(Qt.WindowMaximizeButtonHint, False)
        self._normal_window_flags = self.windowFlags()
        
        layout = QVBoxLayout(self)
        layout.setSizeConstraint(QVBoxLayout.SetFixedSize) # Fixed size according to content
        
        # --- Tabs for Settings ---
        self.tabs = QTabWidget()
        
        # --- Status Tab (first) ---
        tab_status = QWidget()
        tab_status_layout = QVBoxLayout(tab_status)
        tab_status_layout.setSpacing(6)
        tab_status_layout.setContentsMargins(8, 8, 8, 8)
        
        # -- System Status --
        h_system = QHBoxLayout()
        h_system.setSpacing(6)
        self.system_indicator = QLabel()
        self.system_indicator.setFixedSize(16, 16)
        self.system_indicator.setStyleSheet(
            "background-color: #C62828; border-radius: 8px;"
        )
        h_system.addWidget(self.system_indicator)
        self.system_status_label = QLabel("Stopped")
        h_system.addWidget(self.system_status_label)
        h_system.addStretch()
        tab_status_layout.addLayout(h_system)
        
        tab_status_layout.addStretch()
        
        # -- Region (bottom of status tab) --
        self.rect_label_status = QLabel(_("Region: —"))
        self.rect_label_status.setStyleSheet("font-family: monospace;")
        tab_status_layout.addWidget(self.rect_label_status)
        
        self.tabs.addTab(tab_status, _("Status"))
        
        # --- OCR Tab ---
        tab_ocr = QWidget()
        tab_ocr_layout = QVBoxLayout(tab_ocr)
        tab_ocr_layout.addWidget(QLabel(_("OCR Engine:")))
        self.combo_ocr = QComboBox()
        self.combo_ocr.addItems(OCR_ENGINES)
        self.combo_ocr.currentTextChanged.connect(self.worker.set_engine)
        self.combo_ocr.currentTextChanged.connect(self.save_settings)
        tab_ocr_layout.addWidget(self.combo_ocr)

        tab_ocr_layout.addWidget(QLabel(_("Screen Engine:")))
        self.combo_screenshot = QComboBox()
        self.combo_screenshot.addItems(SCREENSHOT_ENGINES)
        self.combo_screenshot.setCurrentText("Portal")
        self.combo_screenshot.currentTextChanged.connect(self.worker.set_screenshot_engine)
        self.combo_screenshot.currentTextChanged.connect(self.save_settings)
        tab_ocr_layout.addWidget(self.combo_screenshot)

        # DPI Scale control
        self.dpi_locked = False
        h_dpi = QHBoxLayout()
        h_dpi.addWidget(QLabel(_("DPI Scale:")))
        self.dpi_lock_label = QLabel("🔓")
        self.dpi_lock_label.setToolTip(_("DPI unlocked (click to lock)"))
        self.dpi_lock_label.setCursor(Qt.PointingHandCursor)
        self.dpi_lock_label.mousePressEvent = self._toggle_dpi_lock
        self.dpi_lock_label.setStyleSheet("font-size: 16px; padding: 0px;")
        self.dpi_lock_label.setFixedWidth(24)
        h_dpi.addWidget(self.dpi_lock_label)
        self.dpi_scale_spin = QDoubleSpinBox()
        self.dpi_scale_spin.setRange(50, 300)
        self.dpi_scale_spin.setSingleStep(25)
        self.dpi_scale_spin.setDecimals(0)
        self.dpi_scale_spin.setSuffix(" %")
        self.dpi_scale_spin.setValue(DPI_SCALE_DEFAULT * 100)
        self.dpi_scale_spin.setToolTip(_("Scale factor for high-DPI monitors.\nAuto-detected when selecting a region."))
        self.dpi_scale_spin.valueChanged.connect(self.on_dpi_scale_changed)
        h_dpi.addWidget(self.dpi_scale_spin)
        tab_ocr_layout.addLayout(h_dpi)

        tab_ocr_layout.addStretch()
        self.tabs.addTab(tab_ocr, _("OCR"))
        
        # --- Translation Tab ---
        tab_translation = QWidget()
        tab_translation_layout = QVBoxLayout(tab_translation)
        tab_translation_layout.addWidget(QLabel(_("Translation Engine:")))
        self.combo_translator = QComboBox()
        self.combo_translator.addItems(TRANSLATION_ENGINES)
        self.combo_translator.currentTextChanged.connect(self.worker.set_translator)
        self.combo_translator.currentTextChanged.connect(self.save_settings)
        self.combo_translator.currentTextChanged.connect(self.on_translator_changed)
        tab_translation_layout.addWidget(self.combo_translator)
        
        h_lang = QHBoxLayout()
        v_source = QVBoxLayout()
        v_source.addWidget(QLabel(_("Source Language:")))
        self.combo_source = QComboBox()
        self.combo_source.addItems(list(LANGUAGES.keys()))
        self.combo_source.setCurrentText("English")
        self.combo_source.currentTextChanged.connect(self.update_languages)
        v_source.addWidget(self.combo_source)
        h_lang.addLayout(v_source)

        v_target = QVBoxLayout()
        v_target.addWidget(QLabel(_("Target Language:")))
        self.combo_target = QComboBox()
        self.combo_target.addItems(list(LANGUAGES.keys()))
        self.combo_target.setCurrentText("Turkish")
        self.combo_target.currentTextChanged.connect(self.update_languages)
        v_target.addWidget(self.combo_target)
        h_lang.addLayout(v_target)
        tab_translation_layout.addLayout(h_lang)
        
        # --- API Key field (shown for engines that need one, e.g. DeepL) ---
        self.api_key_label = QLabel(_("API Key"))
        tab_translation_layout.addWidget(self.api_key_label)
        self.api_key_input = QLineEdit()
        self.api_key_input.setEchoMode(QLineEdit.Password)
        self.api_key_input.setPlaceholderText(_("Enter API key..."))
        self.api_key_input.textChanged.connect(self.on_api_key_changed)
        tab_translation_layout.addWidget(self.api_key_input)
        # Store api keys persistently, keyed by engine name
        self.api_keys = {}
        # Always visible to keep window size fixed; state toggled per engine
        
        tab_translation_layout.addStretch()
        self.tabs.addTab(tab_translation, _("Translation"))
        
        # --- Appearance Tab ---
        tab_appearance = QWidget()
        tab_appearance_layout = QVBoxLayout(tab_appearance)
        
        h_font = QHBoxLayout()
        v_font_family = QVBoxLayout()
        v_font_family.addWidget(QLabel(_("Font Family:")))
        self.font_picker = QFontComboBox()
        self.font_picker.currentFontChanged.connect(self.on_font_changed)
        v_font_family.addWidget(self.font_picker)
        h_font.addLayout(v_font_family)

        v_font_size = QVBoxLayout()
        v_font_size.addWidget(QLabel(_("Size:")))
        self.font_size_spin = QSpinBox()
        self.font_size_spin.setRange(8, 72)
        self.font_size_spin.setValue(self.overlay.font_size)
        self.font_size_spin.valueChanged.connect(self.on_font_size_changed)
        v_font_size.addWidget(self.font_size_spin)
        h_font.addLayout(v_font_size)
        tab_appearance_layout.addLayout(h_font)

        h_colors = QHBoxLayout()
        self.btn_color = QPushButton(_("🎨 Text Color"))
        self.btn_color.clicked.connect(self.choose_color)
        h_colors.addWidget(self.btn_color)

        self.color_sample = QLabel()
        self.color_sample.setFixedSize(24, 24)
        self.color_sample.setStyleSheet(f"background-color: {self.overlay.font_color}; border: 1px solid gray; border-radius: 4px;")
        h_colors.addWidget(self.color_sample)

        self.btn_bg_color = QPushButton(_("🎨 Background"))
        self.btn_bg_color.clicked.connect(self.choose_bg_color)
        h_colors.addWidget(self.btn_bg_color)

        self.bg_color_sample = QLabel()
        self.bg_color_sample.setFixedSize(24, 24)
        self.bg_color_sample.setStyleSheet(f"background-color: {self.overlay.bg_color}; border: 1px solid gray; border-radius: 4px;")
        h_colors.addWidget(self.bg_color_sample)
        tab_appearance_layout.addLayout(h_colors)

        h_bg_opacity = QHBoxLayout()
        h_bg_opacity.addWidget(QLabel(_("Background Opacity:")))
        self.bg_opacity_spin = QSpinBox()
        self.bg_opacity_spin.setRange(0, 255)
        self.bg_opacity_spin.setValue(self.overlay.bg_opacity)
        self.bg_opacity_spin.valueChanged.connect(self.on_bg_opacity_changed)
        h_bg_opacity.addWidget(self.bg_opacity_spin)
        tab_appearance_layout.addLayout(h_bg_opacity)
        tab_appearance_layout.addStretch()
        self.tabs.addTab(tab_appearance, _("Appearance"))
        
        # --- Save Tab (Presets) ---
        tab_save = QWidget()
        tab_save_layout = QVBoxLayout(tab_save)
        
        h_name = QHBoxLayout()
        h_name.addWidget(QLabel(_("Preset Name:")))
        self.preset_name_input = QLineEdit()
        self.preset_name_input.setPlaceholderText(_("Enter preset name..."))
        h_name.addWidget(self.preset_name_input)
        tab_save_layout.addLayout(h_name)
        
        h_buttons = QHBoxLayout()
        self.btn_save_preset = QPushButton(_("💾 Save"))
        self.btn_save_preset.clicked.connect(self.save_preset)
        h_buttons.addWidget(self.btn_save_preset)
        
        self.btn_load_preset = QPushButton(_("📂 Load"))
        self.btn_load_preset.clicked.connect(self.load_preset)
        h_buttons.addWidget(self.btn_load_preset)
        
        self.btn_delete_preset = QPushButton(_("🗑 Delete"))
        self.btn_delete_preset.clicked.connect(self.delete_preset)
        h_buttons.addWidget(self.btn_delete_preset)
        tab_save_layout.addLayout(h_buttons)
        
        tab_save_layout.addWidget(QLabel(_("Saved Presets:")))
        self.preset_combo = QComboBox()
        tab_save_layout.addWidget(self.preset_combo)
        tab_save_layout.addStretch()
        
        self.tabs.addTab(tab_save, _("Save"))
        
        # --- About Tab (last) ---
        tab_about = QWidget()
        tab_about_layout = QVBoxLayout(tab_about)
        about_title = QLabel(_("<b>UmayOCR General Instant Translator</b>"))
        about_title.setStyleSheet("font-size: 14px;")
        tab_about_layout.addWidget(about_title)
        tab_about_layout.addWidget(QLabel(_("Version: 0.1.0")))
        tab_about_layout.addWidget(QLabel(""))
        tab_about_layout.addWidget(QLabel(_("A real-time OCR-based translation tool.")))
        tab_about_layout.addWidget(QLabel(_("Select a screen region, capture text via OCR,")))
        tab_about_layout.addWidget(QLabel(_("and translate instantly with Google or DeepL.")))
        tab_about_layout.addStretch()
        self.tabs.addTab(tab_about, _("About"))

        
        layout.addWidget(self.tabs)

        # --- Performance Indicator (outside tabs) ---
        layout.addWidget(QLabel(_("<br><b>Performance</b>")))
        self.perf_bar = QProgressBar()
        self.perf_bar.setRange(0, 100)
        self.perf_bar.setValue(0)
        self.perf_bar.setTextVisible(False)
        self.perf_bar.setFixedHeight(10)
        layout.addWidget(self.perf_bar)
        
        # --- Controls (outside tabs) ---
        layout.addWidget(QLabel(_("<b>Controls</b>")))
        self.btn_reg = QPushButton(_("🖼 Select Region"))
        self.btn_reg.setStyleSheet("background-color: #1565C0; color: white; font-weight: bold; padding: 10px;")
        self.btn_reg.clicked.connect(self.select_region)
        layout.addWidget(self.btn_reg)
        
        self.btn_start = QPushButton(_("▶ Start"))
        self.btn_start.setStyleSheet("background-color: #2E7D32; color: white; font-weight: bold; padding: 10px;")
        self.btn_start.clicked.connect(self.start)
        layout.addWidget(self.btn_start)
        
        self.btn_stop = QPushButton(_("■ Stop"))
        self.btn_stop.setStyleSheet("background-color: #C62828; color: white; font-weight: bold; padding: 10px;")
        self.btn_stop.clicked.connect(self.stop)
        layout.addWidget(self.btn_stop)
        
        self.worker.new_translation.connect(self.overlay.update_text)
        self.worker.performance_update.connect(self.update_performance_bar)
        self.worker.running_status.connect(self.update_system_status)
        self.overlay.main_window_topmost_requested.connect(self.set_settings_always_on_top)
        self._settings_always_on_top = False
        
        # Load settings or set defaults
        self.load_settings()

        # Initialize status tab with current rect
        self.update_rect_label()
        self.refresh_preset_list()
        self.show()
        
        # Align overlay to the right of the control panel with a slight delay
        # to ensure the window manager has placed the main window.
        QTimer.singleShot(100, self.align_overlay)

    def align_overlay(self):
        """Positions the overlay window next to the main window."""
        # Force a refresh of the window's geometry information
        QApplication.processEvents()
        
        # Get the global position of the main window's frame
        rect = self.frameGeometry()
        target_x = rect.right() + 10
        target_y = rect.top()
        
        # Move and then show the overlay
        self.overlay.move(target_x, target_y)
        self.overlay.show()
        
        # For windows bypassing the WM, move after show is often more reliable
        self.overlay.move(target_x, target_y)

    @Slot(bool)
    def set_settings_always_on_top(self, enabled):
        """Toggle the control panel's game-friendly topmost state from the overlay."""
        self._settings_always_on_top = enabled

        if enabled:
            # Keep the control panel decorated by the window manager.
            # Qt.Tool / Qt.X11BypassWindowManagerHint can remove borders on some WMs,
            # so the settings window uses normal flags plus always-on-top here.
            self.setWindowFlags(self._normal_window_flags | Qt.WindowStaysOnTopHint)
            self.setWindowFlag(Qt.WindowMaximizeButtonHint, False)
            self.setAttribute(Qt.WA_ShowWithoutActivating, True)
            self.show()
            self.raise_()
            self.activateWindow()
        else:
            self.setAttribute(Qt.WA_ShowWithoutActivating, False)
            self.setWindowFlags(self._normal_window_flags)
            self.setWindowFlag(Qt.WindowMaximizeButtonHint, False)
            self.show()
            self.lower()

    def on_font_changed(self, font):
        self.overlay.set_font_family(font.family())
        self.save_settings()

    def on_font_size_changed(self, size):
        self.overlay.set_font_size(size)
        self.save_settings()

    def on_dpi_scale_changed(self, percent_value):
        self.worker.dpi_scale = percent_value / 100.0
        self.dpi_locked = True
        self.dpi_lock_label.setText("🔒")
        self.dpi_lock_label.setToolTip(_("DPI locked (click to unlock)"))
        self.save_settings()

    def _toggle_dpi_lock(self, event):
        self.dpi_locked = not self.dpi_locked
        if self.dpi_locked:
            self.dpi_lock_label.setText("🔒")
            self.dpi_lock_label.setToolTip(_("DPI locked (click to unlock)"))
        else:
            self.dpi_lock_label.setText("🔓")
            self.dpi_lock_label.setToolTip(_("DPI unlocked (click to lock)"))
        return True

    def on_bg_opacity_changed(self, opacity):
        self.overlay.set_bg_opacity(opacity)
        self.save_settings()

    def save_settings(self):
        settings = {
            "ocr_engine": self.combo_ocr.currentText(),
            "translator_engine": self.combo_translator.currentText(),
            "source_lang": self.combo_source.currentText(),
            "target_lang": self.combo_target.currentText(),
            "font_family": self.font_picker.currentFont().family(),
            "font_size": self.font_size_spin.value(),
            "font_color": self.overlay.font_color,
            "bg_color": self.overlay.bg_color,
            "bg_opacity": self.overlay.bg_opacity,
            "translator_api_keys": self.api_keys,
            "capture_rect": (self.worker.capture_rect.x(), self.worker.capture_rect.y(), 
                            self.worker.capture_rect.width(), self.worker.capture_rect.height()),
            "dpi_scale": self.worker.dpi_scale,
            "screenshot_engine": self.combo_screenshot.currentText()
        }
        try:
            with open(SETTINGS_FILE, "wb") as f:
                pickle.dump(settings, f)
            print("Settings saved.")
        except Exception as e:
            print(f"Settings save error: {e}")

    def load_settings(self):
        if os.path.exists(SETTINGS_FILE):
            try:
                with open(SETTINGS_FILE, "rb") as f:
                    s = pickle.load(f)
                
                # Update UI elements (triggers signals without blocking)
                self.combo_ocr.setCurrentText(s.get("ocr_engine", "Tesseract"))
                self.combo_translator.setCurrentText(s.get("translator_engine", "Google"))
                self.combo_source.setCurrentText(s.get("source_lang", "English"))
                self.combo_target.setCurrentText(s.get("target_lang", "Turkish"))
                
                font_family = s.get("font_family", "Arial")
                self.font_picker.setCurrentFont(font_family)
                self.overlay.set_font_family(font_family)
                
                font_size = s.get("font_size", 20)
                self.font_size_spin.setValue(font_size)
                self.overlay.set_font_size(font_size)
                
                font_color = s.get("font_color", "white")
                self.overlay.set_font_color(font_color)
                self.color_sample.setStyleSheet(f"background-color: {font_color}; border: 1px solid gray; border-radius: 4px;")
                
                bg_color = s.get("bg_color", "#000000")
                self.overlay.set_bg_color(bg_color)
                self.bg_color_sample.setStyleSheet(f"background-color: {bg_color}; border: 1px solid gray; border-radius: 4px;")
                
                bg_opacity = s.get("bg_opacity", 180)
                self.bg_opacity_spin.setValue(bg_opacity)
                self.overlay.set_bg_opacity(bg_opacity)
                
                # Load DPI scale
                dpi_scale = s.get("dpi_scale", DPI_SCALE_DEFAULT)
                self.dpi_scale_spin.blockSignals(True)
                self.dpi_scale_spin.setValue(dpi_scale * 100)
                self.dpi_scale_spin.blockSignals(False)
                self.worker.dpi_scale = dpi_scale

                rect = s.get("capture_rect")
                if rect:
                    self.worker.set_rect(QRect(rect[0], rect[1], rect[2], rect[3]))
                    self.update_rect_label()
                
                # Load screenshot engine
                screenshot_engine = s.get("screenshot_engine", "Portal")
                self.combo_screenshot.setCurrentText(screenshot_engine)
                self.worker.set_screenshot_engine(screenshot_engine)

                # Load API keys
                self.api_keys = s.get("translator_api_keys", {})
                self._apply_api_key_for_current_engine()

                self.update_languages()
                print("Settings loaded.")
                return
            except Exception as e:
                print(f"Settings load error: {e}")
        
        # If file not exists or error occurs, set defaults
        self.update_languages()

    def update_system_status(self, is_running):
        if is_running:
            self.system_indicator.setStyleSheet(
                "background-color: #2E7D32; border-radius: 8px;"
            )
            self.system_status_label.setText("Running")
        else:
            self.system_indicator.setStyleSheet(
                "background-color: #C62828; border-radius: 8px;"
            )
            self.system_status_label.setText("Stopped")
            self.overlay.set_mode(False)
            self.perf_bar.setValue(0)
            self.perf_bar.setStyleSheet("")

    def update_rect_label(self):
        r = self.worker.capture_rect
        self.rect_label_status.setText(
            _("Region: X:{x} Y:{y}  {w}×{h}").format(x=r.x(), y=r.y(), w=r.width(), h=r.height())
        )

    def update_performance_bar(self, duration):
        # Inverse logic: 0.5s -> %100 (Best), 3.0s -> %0 (Worst)
        percent = int(100 - (((duration - 0.5) / 2.5) * 100))
        percent = max(0, min(100, percent))
        
        self.perf_bar.setValue(percent)
        
        # Color determination based on percentage (Health bar logic)
        if percent >= 75:
            color = "#2E7D32" # Green (Great)
        elif percent >= 35:
            color = "#F9A825" # Yellow/Orange (Normal)
        else:
            color = "#C62828" # Red (Poor)
            
        self.perf_bar.setStyleSheet(f"""
            QProgressBar::chunk {{
                background-color: {color};
                border-radius: 2px;
            }}
            QProgressBar {{
                border: 1px solid gray;
                border-radius: 3px;
                background: #E0E0E0;
            }}
        """)

    def update_languages(self):
        source_code = LANGUAGES.get(self.combo_source.currentText(), "en")
        target_code = LANGUAGES.get(self.combo_target.currentText(), "tr")
        self.worker.set_languages(source_code, target_code)
        self.save_settings()

    def choose_color(self):
        color = QColorDialog.getColor()
        if color.isValid():
            color_name = color.name()
            self.overlay.set_font_color(color_name)
            self.color_sample.setStyleSheet(f"background-color: {color_name}; border: 1px solid gray; border-radius: 4px;")
            self.save_settings()

    def choose_bg_color(self):
        color = QColorDialog.getColor()
        if color.isValid():
            color_name = color.name()
            self.overlay.set_bg_color(color_name)
            self.bg_color_sample.setStyleSheet(f"background-color: {color_name}; border: 1px solid gray; border-radius: 4px;")
            self.save_settings()

    def select_region(self):
        #self.hide()
        QApplication.processEvents()
        time.sleep(0.2)

        sniper = SniperFactory.get_engine()
        rect = sniper.get_region()
        if rect:
            # Auto-detect DPI scale from the selected screen (only if not manually locked)
            if not self.dpi_locked and hasattr(sniper, 'detected_dpi'):
                self.dpi_scale_spin.blockSignals(True)
                self.dpi_scale_spin.setValue(sniper.detected_dpi * 100)
                self.dpi_scale_spin.blockSignals(False)
                self.worker.dpi_scale = sniper.detected_dpi

            self.worker.set_rect(rect)
            self.overlay.label.setText(f"Region: {rect.x()},{rect.y()} {rect.width()}x{rect.height()}")
            self.update_rect_label()
            self.save_settings()
        
        #self.show()

    def start(self): 
        self.overlay.set_mode(True)
        if not self.worker.isRunning():
            self.worker.start()

    def stop(self):
        self.worker.stop()
        self.overlay.set_mode(False)
        self.perf_bar.setValue(0)
        self.perf_bar.setStyleSheet("")

    def closeEvent(self, event):
        self.worker.stop()
        self.overlay.close()
        super().closeEvent(event)
 
    # ---------- API Key Helpers ----------
    def _apply_api_key_for_current_engine(self):
        """Update the API key textbox state and value for the current engine."""
        engine = self.combo_translator.currentText()
        key = self.api_keys.get(engine, "")
        # Block signals to avoid triggering on_api_key_changed during load
        self.api_key_input.blockSignals(True)
        self.api_key_input.setText(key)
        self.api_key_input.blockSignals(False)
        # Push to worker so the engine uses the saved key
        if key:
            self.worker.set_api_key(engine, key)
        # Toggle editable state based on engine (always visible, fixed window size)
        self._update_api_key_state(engine)

    def _update_api_key_state(self, engine: str):
        """Enable/disable the API key field based on engine, keep it always visible."""
        engines_needing_key = {"DeepL"}
        if engine in engines_needing_key:
            self.api_key_input.setReadOnly(False)
            self.api_key_input.setEnabled(True)
            self.api_key_input.setToolTip("")
        else:
            self.api_key_input.setReadOnly(True)
            self.api_key_input.setEnabled(False)
            self.api_key_input.setToolTip(_("This engine does not require an API key"))

    def on_translator_changed(self, engine: str):
        """Called when the translation engine combo box changes."""
        self._apply_api_key_for_current_engine()

    def on_api_key_changed(self, text: str):
        """Called when the user types in the API key text box."""
        engine = self.combo_translator.currentText()
        self.api_keys[engine] = text
        self.worker.set_api_key(engine, text)
        self.save_settings()

    # ---------- Preset Management ----------
    def _load_presets_dict(self):
        """Load all presets from pickle file, returns dict."""
        if os.path.exists(PRESETS_FILE):
            try:
                with open(PRESETS_FILE, "rb") as f:
                    return pickle.load(f)
            except Exception as e:
                print(f"Presets load error: {e}")
        return {}

    def _save_presets_dict(self, presets):
        """Save presets dict to pickle file."""
        try:
            with open(PRESETS_FILE, "wb") as f:
                pickle.dump(presets, f)
        except Exception as e:
            print(f"Presets save error: {e}")

    def refresh_preset_list(self):
        """Refresh the combo box with preset names."""
        self.preset_combo.clear()
        presets = self._load_presets_dict()
        for name in sorted(presets.keys()):
            self.preset_combo.addItem(name)

    def save_preset(self):
        """Save current overlay position/size + capture rect + appearance to a named preset."""
        name = self.preset_name_input.text().strip()
        if not name:
            QMessageBox.warning(self, "No Name", "Please enter a preset name.")
            return
        
        preset = {
            "capture_rect": (
                self.worker.capture_rect.x(),
                self.worker.capture_rect.y(),
                self.worker.capture_rect.width(),
                self.worker.capture_rect.height(),
            ),
            "overlay_x": self.overlay.pos().x(),
            "overlay_y": self.overlay.pos().y(),
            "overlay_w": self.overlay.width(),
            "overlay_h": self.overlay.height(),
            "font_family": self.overlay.font_family,
            "font_size": self.overlay.font_size,
            "font_color": self.overlay.font_color,
            "bg_color": self.overlay.bg_color,
            "bg_opacity": self.overlay.bg_opacity,
        }
        
        presets = self._load_presets_dict()
        presets[name] = preset
        self._save_presets_dict(presets)
        self.refresh_preset_list()
        self.preset_name_input.clear()
        print(f"Preset '{name}' saved.")

    def load_preset(self):
        """Load the selected preset from the combo box and apply it."""
        name = self.preset_combo.currentText()
        if not name:
            QMessageBox.information(self, _("No Selection"), _("Please select a preset to load."))
            return
        presets = self._load_presets_dict()
        preset = presets.get(name)
        if preset is None:
            QMessageBox.warning(self, "Not Found", f"Preset '{name}' not found.")
            return
        
        # Apply capture rect
        rect_data = preset.get("capture_rect")
        if rect_data:
            self.worker.set_rect(QRect(rect_data[0], rect_data[1], rect_data[2], rect_data[3]))
            self.update_rect_label()
        
        # Apply overlay position and size
        ox = preset.get("overlay_x")
        oy = preset.get("overlay_y")
        ow = preset.get("overlay_w")
        oh = preset.get("overlay_h")
        if ox is not None and oy is not None:
            self.overlay.move(ox, oy)
        if ow is not None and oh is not None:
            self.overlay.resize(ow, oh)
        
        # Apply appearance
        ff = preset.get("font_family")
        if ff:
            self.overlay.set_font_family(ff)
            self.font_picker.setCurrentFont(ff)
        
        fs = preset.get("font_size")
        if fs:
            self.overlay.set_font_size(fs)
            self.font_size_spin.setValue(fs)
        
        fc = preset.get("font_color")
        if fc:
            self.overlay.set_font_color(fc)
            self.color_sample.setStyleSheet(
                f"background-color: {fc}; border: 1px solid gray; border-radius: 4px;"
            )
        
        bgc = preset.get("bg_color")
        if bgc:
            self.overlay.set_bg_color(bgc)
            self.bg_color_sample.setStyleSheet(
                f"background-color: {bgc}; border: 1px solid gray; border-radius: 4px;"
            )
        
        bgo = preset.get("bg_opacity")
        if bgo is not None:
            self.overlay.set_bg_opacity(bgo)
            self.bg_opacity_spin.setValue(bgo)
        
        print(f"Preset '{name}' loaded.")

    def delete_preset(self):
        """Delete the selected preset."""
        name = self.preset_combo.currentText()
        if not name:
            QMessageBox.information(self, "No Selection", "Please select a preset to delete.")
            return
        presets = self._load_presets_dict()
        if name in presets:
            del presets[name]
            self._save_presets_dict(presets)
            self.refresh_preset_list()
            print(f"Preset '{name}' deleted.")
        else:
            QMessageBox.warning(self, "Not Found", f"Preset '{name}' not found.")
