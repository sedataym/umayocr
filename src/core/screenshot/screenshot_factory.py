from src.core.screenshot.base_screenshot import BaseScreenshot
from src.core.screenshot.spectacle_screenshot import SpectacleScreenshot

try:
    from src.core.screenshot.portal_screenshot import PortalScreenshot
except Exception as exc:
    PortalScreenshot = None
    _PORTAL_IMPORT_ERROR = exc
else:
    _PORTAL_IMPORT_ERROR = None
 
class ScreenshotFactory:
    @staticmethod
    def get_engine(engine_name: str = "Portal") -> BaseScreenshot:
        if engine_name == "Portal":
            if PortalScreenshot is not None and PortalScreenshot.is_available():
                return PortalScreenshot()

            if _PORTAL_IMPORT_ERROR is not None:
                print(f"Portal screenshot engine unavailable: {_PORTAL_IMPORT_ERROR}")
            print("Falling back to Spectacle screenshot engine.")
            return SpectacleScreenshot()

        # Spectacle
        return SpectacleScreenshot()
