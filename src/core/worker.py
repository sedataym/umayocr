import time
import threading
from threading import Lock
from PySide6.QtCore import QThread, Signal, QRect
from src.core.ocr.ocr_manager import OCRManager
from src.core.translation.translator_manager import TranslatorManager
from src.core.exceptions import PortalCanceledError
from src.core.screenshot import ScreenshotFactory, ImageProcessor
from src.core.socket_publisher import TranslationPublisher
from src.config import IMG_PATH, DPI_SCALE_DEFAULT

class OCRWorker(QThread):
    LOOP_SLEEP_SECONDS = 0.2

    new_translation = Signal(str)
    performance_update = Signal(float) # Loop duration in seconds
    translation_status = Signal(bool)  # True: translating (API call active), False: idle
    running_status = Signal(bool)      # True: system started, False: system stopped

    def __init__(self):
        super().__init__()
        self.capture_rect = QRect(560, 750, 800, 140)
        self.dpi_scale = DPI_SCALE_DEFAULT
        self.lock = Lock()
        self.running = False
        self.ocr_manager = OCRManager()
        self.translator_manager = TranslatorManager()
        self.screenshot_engine = ScreenshotFactory.get_engine()
        self.last_text = ""
        self._translation_lock = Lock()
        self._is_translating = False
        self.publisher = TranslationPublisher()

    def set_rect(self, qrect, dpi_scale=None):
        with self.lock:
            self.capture_rect = QRect(qrect)
            if dpi_scale is not None:
                self.dpi_scale = dpi_scale
            self.last_text = ""
            print(f"OCRWorker: New region: {qrect.x()},{qrect.y()} {qrect.width()}x{qrect.height()} DPI: {self.dpi_scale}")

    def set_engine(self, engine_name):
        with self.lock:
            self.ocr_manager.set_engine(engine_name)
            self.last_text = ""
            print(f"OCRWorker: Engine: {engine_name}")

    def set_translator(self, translator_name):
        with self.lock:
            self.translator_manager.set_translator(translator_name)
            self.last_text = ""
            print(f"OCRWorker: Translator: {translator_name}")

    def set_api_key(self, engine: str, api_key: str):
        with self.lock:
            self.translator_manager.set_api_key(engine, api_key)
            self.last_text = ""
            print(f"OCRWorker: API key set for: {engine}")

    def set_screenshot_engine(self, engine_name):
        with self.lock:
            if hasattr(self.screenshot_engine, "close"):
                self.screenshot_engine.close()
            self.screenshot_engine = ScreenshotFactory.get_engine(engine_name)
            self.last_text = ""
            print(f"OCRWorker: Screenshot engine: {engine_name}")

    def set_languages(self, source, target):
        with self.lock:
            self.translator_manager.set_languages(source, target)
            self.ocr_manager.set_language(source)
            self.last_text = ""
            print(f"OCRWorker: Languages: {source} -> {target}")

    def stop(self):
        self.running = False
        if self.isRunning():
            self.wait()
        if hasattr(self.screenshot_engine, "close"):
            self.screenshot_engine.close()
        self.publisher.stop()
        self.running_status.emit(False)

    def _async_translate(self, text):
        with self._translation_lock:
            self._is_translating = True
        self.translation_status.emit(True)
        try:
            translated = self.translator_manager.translate(text)
            self.new_translation.emit(translated)
            source, target = self.translator_manager.get_languages()
            self.publisher.broadcast(
                original=text,
                translated=translated,
                source_lang=source,
                target_lang=target,
                engine=self.translator_manager.current_translator_name,
            )
        except Exception as e:
            print(f"Translation Error: {e}")
        finally:
            with self._translation_lock:
                self._is_translating = False
            self.translation_status.emit(False)

    def run(self):
        self.publisher.start()
        self.running = True
        self.running_status.emit(True)
        print(f"OCRWorker: LOOP STARTED.")
        while self.running:
            try:
                start_total = time.perf_counter()
                with self.lock:
                    rect = QRect(self.capture_rect)
                    current_engine = self.ocr_manager.current_engine_name
                
                with self._translation_lock:
                    translating = self._is_translating

                if rect.width() < 10 or rect.height() < 10:
                    time.sleep(self.LOOP_SLEEP_SECONDS); continue

                # 1. Capture
                if not self.screenshot_engine.capture(rect, IMG_PATH, self.dpi_scale):
                    time.sleep(self.LOOP_SLEEP_SECONDS); continue

                # 2. Prep (Special processing for Tesseract only)
                if current_engine == "Tesseract":
                    ImageProcessor.preprocess_for_tesseract(IMG_PATH, IMG_PATH)

                # 3. OCR
                clean = self.ocr_manager.read_text(IMG_PATH)

                # 4. API (Async Translation)
                if len(clean) > 2 and clean != self.last_text and not translating:
                    self.last_text = clean
                    threading.Thread(target=self._async_translate, args=(clean,), daemon=True).start()
                    print(f"[{current_engine}] Text: {clean} | Duration: {time.perf_counter()-start_total:.2f}s")

                # Emit performance data
                self.performance_update.emit(time.perf_counter() - start_total)

            except PortalCanceledError:
                print("OCRWorker: Portal selection canceled, stopping.")
                self.running = False
                if hasattr(self.screenshot_engine, "close"):
                    self.screenshot_engine.close()
                self.publisher.stop()
                self.running_status.emit(False)
            except Exception as e:
                print(f"Loop Error: {e}")
            time.sleep(self.LOOP_SLEEP_SECONDS)