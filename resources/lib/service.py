import xbmc, xbmcgui, xbmcvfs
from threading import Thread
from modules.logger import logger

from modules.monitors.ratings import RatingsMonitor
from modules.monitors.image import ImageMonitor, ImageColorAnalyzer, ImageAnalysisConfig
from modules.databases.ratings import RatingsDatabase
from modules.config import SETTINGS_PATH


class Service(xbmc.Monitor):
    """Main service class that coordinates monitor and rating lookups."""

    def __init__(self):
        super().__init__()
        self.section_states = {
            "movie": False,
            "tvshow": False,
            "custom1": False,
            "custom2": False,
            "custom3": False,
        }
        self.section_settings = {
            "movie": "HomeMenuNoMoviesButton",
            "tvshow": "HomeMenuNoTVShowsButton",
            "custom1": "HomeMenuNoCustom1Button",
            "custom2": "HomeMenuNoCustom2Button",
            "custom3": "HomeMenuNoCustom3Button",
        }
        self._initialize()

    def _initialize(self):
        """Initialize service components."""
        if not xbmcvfs.exists(SETTINGS_PATH):
            xbmcvfs.mkdir(SETTINGS_PATH)
        self.home_window = xbmcgui.Window(10000)
        self.get_infolabel = xbmc.getInfoLabel
        self.get_visibility = xbmc.getCondVisibility
        self.image_monitor = ImageMonitor(ImageColorAnalyzer, ImageAnalysisConfig())
        self.ratings_monitor = RatingsMonitor(RatingsDatabase(), self.home_window)
        self._update_section_states()

    def _update_section_states(self):
        """Update the current state of all sections."""
        for section, setting in self.section_settings.items():
            self.section_states[section] = not self.get_visibility(
                f"Skin.HasSetting({setting})"
            )

    def _check_section_changes(self):
        """Check for changes in section visibility and trigger widget loading if needed."""
        for section, setting in self.section_settings.items():
            current_state = not self.get_visibility(f"Skin.HasSetting({setting})")
            if not self.section_states[section] and current_state:
                xbmc.executebuiltin(
                    f"RunScript(script.altus.helper,mode=starting_widgets,section={section})"
                )
            self.section_states[section] = current_state

    def run(self):
        """Start the service and monitor."""
        self.image_monitor.start()
        while not self.abortRequested():
            if self._should_pause():
                self.waitForAbort(2)
                continue
            self.ratings_monitor.process_current_item()
            if self.get_visibility("Window.IsVisible(Home)"):
                self._check_section_changes()
            self.waitForAbort(0.2)

    def _should_pause(self):
        if self.home_window.getProperty("pause_services") == "true":
            return True
        if xbmc.getSkinDir() != "skin.altus":
            return True
        if not self.get_infolabel("Skin.String(mdblist_api_key)"):
            return True
        if not self.get_visibility(
            "Window.IsVisible(videos) | "
            "Window.IsVisible(home) | "
            "Window.IsVisible(11121) | "
            "Window.IsActive(movieinformation)"
        ):
            return True
        return False

    def onNotification(self, sender, method, data):
        """Handle Kodi notifications."""
        # logger(
        #     "Notification received - Sender: {}, Method: {}, Data: {}".format(
        #         sender, method, data
        #     ),
        #     1,
        # )
        if sender == "xbmc":
            if method in ("GUI.OnScreensaverActivated", "System.OnSleep"):
                self.home_window.setProperty("pause_services", "true")
            elif method in ("GUI.OnScreensaverDeactivated", "System.OnWake"):
                self.home_window.clearProperty("pause_services")
            elif method == "GUI.OnScreensaverDeactivated":
                self._update_section_states()


if __name__ == "__main__":
    service = Service()
    service.run()
