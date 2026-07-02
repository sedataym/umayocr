import os
import tempfile

OCR_ENGINES = ["Tesseract", "EasyOCR"]  # "PaddleOCR" (uncomment when paddlepaddle is available)
TRANSLATION_ENGINES = ["Google", "DeepL"]
SCREENSHOT_ENGINES = ["Portal", "Spectacle"]
LANGUAGES = {
    "Auto": "auto",
    "English": "en",
    "Turkish": "tr",
    "German": "de",
    "French": "fr",
    "Japanese": "ja",
    "Korean": "ko",
    "Chinese": "zh",
    "Russian": "ru",
    "Arabic": "ar",
    "Hebrew": "he",
    "Vietnamese": "vi",
    "Thai": "th",
    "Spanish": "es"
}

# Map UI language codes to Tesseract/EasyOCR language codes
OCR_LANG_MAPPING = {
    "en": {"tess": "eng", "easy": "en", "paddle": "en"},
    "tr": {"tess": "tur", "easy": "tr", "paddle": "tr"},
    "ru": {"tess": "rus", "easy": "ru", "paddle": "ru"},
    "ar": {"tess": "ara", "easy": "ar", "paddle": "ar"},
    "he": {"tess": "heb", "easy": "he", "paddle": "he"},
    "de": {"tess": "deu", "easy": "de", "paddle": "de"},
    "fr": {"tess": "fra", "easy": "fr", "paddle": "fr"},
    "ja": {"tess": "jpn", "easy": "ja", "paddle": "ja"},
    "ko": {"tess": "kor", "easy": "ko", "paddle": "ko"},
    "zh": {"tess": "chi_sim", "easy": "ch_sim", "paddle": "ch"},
    "vi": {"tess": "vie", "easy": "vi", "paddle": "vi"},
    "th": {"tess": "tha", "easy": "th", "paddle": "th"},
    "es": {"tess": "spa", "easy": "es", "paddle": "es"}
}

DPI_SCALE_DEFAULT = 1.0  # Auto-detected from QScreen.devicePixelRatio, user can override

CONFIG_DIR = os.path.expanduser("~/.config/umayocr")
if not os.path.exists(CONFIG_DIR):
    os.makedirs(CONFIG_DIR, exist_ok=True)

SETTINGS_FILE = os.path.join(CONFIG_DIR, "settings.pkl")
PRESETS_FILE = os.path.join(CONFIG_DIR, "presets.pkl")

# Temp Files
TEMP_DIR = tempfile.gettempdir()
DEV_SHM ="/dev/shm"
IMG_PATH = os.path.join(DEV_SHM, "umayocr_snapshot.jpeg")
FULL_SCREEN_TEMP_PATH = os.path.join(DEV_SHM, "umayocr_full_snap.jpeg")
SOCKET_PATH = os.path.join(TEMP_DIR, "umayocr.sock")
SLURP_TEMP_PATH = os.path.join(TEMP_DIR, "slurp_final.txt")
