from src.core.ocr.base_ocr import BaseOCREngine
from src.config import OCR_LANG_MAPPING

class EasyOCREngine(BaseOCREngine):
    def __init__(self):
        self.reader = None
        self.current_langs = ['en']

    def set_language(self, lang_code: str):
        mapping = OCR_LANG_MAPPING.get(lang_code, OCR_LANG_MAPPING["en"])
        new_lang = mapping["easy"]
        
        # Always include 'en' as base, but add the target language if different
        target_langs = list({'en', new_lang})
        
        if target_langs != self.current_langs:
            self.current_langs = target_langs
            self.reader = None # Trigger re-initialization on next read
            print(f"EasyOCREngine: Languages scheduled for update: {self.current_langs}")

    def read_text(self, image_path: str) -> str:
        if self.reader is None:
            import easyocr
            print(f"EasyOCREngine: Initializing reader with {self.current_langs}")
            self.reader = easyocr.Reader(self.current_langs, gpu=True)
        
        try:
            res = self.reader.readtext(image_path)
            clean = " ".join([r[1] for r in res])
            return " ".join(clean.split()).strip().strip("_").rstrip(":")
        except Exception as e:
            print(f"EasyOCR Error: {e}")
            return ""
