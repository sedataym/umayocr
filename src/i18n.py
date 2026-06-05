import gettext
import os
import locale

# Global translator object
_translator = None

def init_i18n(locale_dir=None, domain="messages"):
    """
    Initialize internationalization.
    If locale_dir is not provided, it defaults to 'src/translations'.
    """
    global _translator
    
    if locale_dir is None:
        # Default translation directory: src/translations
        base_dir = os.path.dirname(os.path.abspath(__file__))
        locale_dir = os.path.join(base_dir, "translations")

    # Detect system language
    try:
        current_locale, encoding = locale.getlocale()
        if current_locale is None:
            # On some systems, getlocale() returns None
            current_locale = locale.getdefaultlocale()[0]
    except Exception:
        current_locale = "en_US"

    if not current_locale:
        current_locale = "en_US"

    # Load translation
    try:
        _translator = gettext.translation(domain, locale_dir, languages=[current_locale], fallback=True)
        _translator.install() # This installs _() into builtins
    except Exception as e:
        print(f"Warning: Could not load translation for {current_locale}: {e}")
        # Fallback to null translation
        _translator = gettext.NullTranslations()
        _translator.install()

def _(message):
    """
    Helper function to translate a message.
    """
    if _translator is None:
        return message
    return _translator.gettext(message)
