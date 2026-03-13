import xbmc, xbmcgui, xbmcvfs
import json
import os
from threading import Thread
from modules.logger import logger
from modules.monitors.ratings import RatingsMonitor
from modules.monitors.image import ImageMonitor, ImageColorAnalyzer, ImageAnalysisConfig
from modules.databases.ratings import RatingsDatabase
from modules.config import SETTINGS_PATH
from modules.select_view import VIEW_PREFERENCES_PATH


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
        self._last_addon_key = None
        self._last_content_type = None
        self._view_prefs_cache = {}
        self._view_prefs_mtime = 0

    def run(self):
        """Start the service and monitor."""
        self.image_monitor.start()
        while not self.abortRequested():
            if self._should_pause():
                self.waitForAbort(2)
                continue
            self.ratings_monitor.process_current_item()
            self.monitor_addon_views()
            self.waitForAbort(0.2)

    def _load_view_preferences(self):
        """Load view preferences from JSON, using mtime-based cache."""
        try:
            mtime = os.path.getmtime(VIEW_PREFERENCES_PATH)
            if mtime != self._view_prefs_mtime:
                with open(VIEW_PREFERENCES_PATH, "r") as f:
                    self._view_prefs_cache = json.load(f)
                self._view_prefs_mtime = mtime
        except (FileNotFoundError, json.JSONDecodeError, IOError):
            self._view_prefs_cache = {}
        return self._view_prefs_cache

    def _apply_all_addon_views(self, addon_key, prefs):
        """Set all stored skin strings for an addon at once."""
        addon_prefs = prefs.get(addon_key, {})
        # Set skin strings for all saved content types
        for ct, saved_view in addon_prefs.items():
            if isinstance(saved_view, dict):
                xbmc.executebuiltin(
                    f'Skin.SetString(Skin.ForcedView.{ct},{saved_view["label"]})'
                )
        # Reset any content types this addon doesn't have saved
        all_content_types = set()
        for ap in prefs.values():
            if isinstance(ap, dict):
                all_content_types.update(ap.keys())
        for ct in all_content_types - set(addon_prefs.keys()):
            xbmc.executebuiltin(f"Skin.Reset(Skin.ForcedView.{ct})")

    def monitor_addon_views(self):
        """Apply saved per-addon view preferences when addon/content changes."""
        plugin_name = self.get_infolabel("Container.PluginName")
        content = self.get_infolabel("Container.Content")
        if content == "episodes":
            if self.get_visibility(
                "String.StartsWith(Container.PluginCategory,Season)"
            ):
                content_type = "episodes.inside"
            else:
                content_type = "episodes.outside"
        else:
            content_type = content

        addon_key = plugin_name if plugin_name else "__library__"
        prefs = self._load_view_preferences()

        # When addon changes, preload all skin strings for the new addon
        if addon_key != self._last_addon_key:
            self._last_addon_key = addon_key
            self._apply_all_addon_views(addon_key, prefs)

        # When content type changes, apply SetViewMode for the current view
        if content_type != self._last_content_type:
            self._last_content_type = content_type
            saved_view = prefs.get(addon_key, {}).get(content_type)
            if saved_view and isinstance(saved_view, dict):
                xbmc.executebuiltin(f'Container.SetViewMode({saved_view["viewid"]})')

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
