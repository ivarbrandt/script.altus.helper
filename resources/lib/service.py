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
        self._initialize()

    def _initialize(self):
        """Initialize service components."""
        if not xbmcvfs.exists(SETTINGS_PATH):
            xbmcvfs.mkdir(SETTINGS_PATH)
        self.home_window = xbmcgui.Window(10000)
        self.get_infolabel = xbmc.getInfoLabel
        self.get_visibility = xbmc.getCondVisibility
        current_config = ImageAnalysisConfig.from_skin_settings()
        self.image_monitor = ImageMonitor(ImageColorAnalyzer, current_config)
        self.ratings_monitor = RatingsMonitor(RatingsDatabase(), self.home_window)

    def run(self):
        """Start the service and monitor."""
        self.image_monitor.start()
        while not self.abortRequested():
            if self._should_pause():
                self.waitForAbort(2)
                continue
            self.ratings_monitor.process_current_item()
            self.monitor_view_properties()
            self.waitForAbort(0.2)

    def monitor_view_properties(self):
        """Monitor visible views and set return properties."""
        if not hasattr(self, '_last_view_states'):
            self._last_view_states = {
                51: False,
                53: False,
                56: False
            }
        current_states = {}
        for view_id in [51, 53, 56]:
            current_states[view_id] = xbmc.getCondVisibility(f"Control.IsVisible({view_id})")
        property_empty = {}
        for view_id in [51, 53, 56]:
            property_empty[view_id] = xbmc.getCondVisibility(f"String.IsEmpty(Window(Home).Property(Returnto{view_id}))")
        for view_id in [51, 53, 56]:
            if current_states[view_id] and not self._last_view_states[view_id] and property_empty[view_id]:
                xbmc.executebuiltin(f"SetProperty(Returnto{view_id},true,Home)")
        self._last_view_states = current_states

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