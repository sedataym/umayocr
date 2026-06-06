import os
import deepl
from src.core.translation.base_translator import BaseTranslator


class DeepLTranslatorEngine(BaseTranslator):
    def __init__(self, api_key=None, source='en', target='tr'):
        self.api_key = api_key or os.getenv(
            "DEEPL_API_KEY",
            ""
        )
        self.source = source
        self.target = target
        self._translator = None

    @property
    def translator(self):
        if self._translator is None:
            try:
                self._translator = deepl.Translator(self.api_key)
            except Exception as e:
                print(f"DeepL Initialization Error: {e}")
        return self._translator

    def set_languages(self, source: str, target: str):
        self.source = source
        self.target = target

    def translate(self, text: str) -> str:
        if not self.api_key or self.api_key == "YOUR_DEEPL_API_KEY":
            return "Error: DeepL API key is missing. Please define DEEPL_API_KEY."

        try:
            if self.translator:
                result = self.translator.translate_text(
                    text,
                    source_lang=self.source,
                    target_lang=self.target,
                )
                return result.text
            return "Error: DeepL could not be initialized."
        except Exception as e:
            print(f"DeepL Translation Error: {e}")
            return f"Error: {e}"