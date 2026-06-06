from src.core.translation.google_engine import GoogleEngine
from src.core.translation.deepl_engine import DeepLTranslatorEngine

class TranslatorManager:
    def __init__(self):
        self.translators = {
            "Google": GoogleEngine(),
            "DeepL": DeepLTranslatorEngine()
        }
        self.current_translator_name = "Google"
        self._source_lang = "en"
        self._target_lang = "tr"

    def set_translator(self, name: str):
        if name in self.translators:
            self.current_translator_name = name

    def set_api_key(self, engine: str, api_key: str):
        translator = self.translators.get(engine)
        if translator and hasattr(translator, "set_api_key"):
            translator.set_api_key(api_key)

    def set_languages(self, source: str, target: str):
        self._source_lang = source
        self._target_lang = target
        for translator in self.translators.values():
            translator.set_languages(source, target)

    def get_languages(self) -> tuple[str, str]:
        return self._source_lang, self._target_lang

    def translate(self, text: str) -> str:
        translator = self.translators.get(self.current_translator_name)
        if translator:
            return translator.translate(text)
        return text
