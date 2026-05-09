import time
import threading
from urllib.parse import quote
import xbmc
import xbmcgui

DEBOUNCE_MS = 1000
POLL_MS = 50
COOLDOWN_MS = 1200

# QWERTY key control IDs in Custom_1121_SearchResults.xml — focus changes
# within this range are treated as "still navigating between keys" and
# reset the debounce timer so the fire only happens once the user has
# truly stopped interacting with the keyboard.
KEY_FOCUS_MIN = 9200
KEY_FOCUS_MAX = 9605
SEARCH_WINDOW_ID = 11121  # 1121 declared, runtime-shifted (see custom-window-id memory)


class LiveSearchMonitor(threading.Thread):
    """Debounces live-search widget refreshes.

    Watches Window(home).Property(altus.search.input). When the value stays
    unchanged for DEBOUNCE_MS, fires starting_search_widgets() once in a
    sub-thread so the poll loop keeps draining keystrokes.

    Per-keystroke writers (live_input, search_input) only set properties;
    this monitor is the single dispatcher for the actual widget reload.
    """

    def __init__(self):
        super().__init__()
        self.daemon = True
        self.home_window = xbmcgui.Window(10000)
        self._monitor = xbmc.Monitor()
        self._last_seen = self.home_window.getProperty("altus.search.input")
        self._last_focus_id = 0
        self._last_change = 0.0
        self._pending = False
        self._refresh_lock = threading.Lock()
        self._refreshing = False

    def _focus_id(self):
        # Use the InfoLabel rather than xbmcgui.Window(...).getFocusId() —
        # the latter is unreliable when called from a daemon thread (mirrors
        # the getControl().getText() thread-safety issue documented in the
        # kodi-getcontrol-thread-unsafe memory). InfoLabels go through the
        # standard infomanager and are safe off the main thread.
        if not xbmc.getCondVisibility("Window.IsVisible(1121)"):
            return 0
        raw = xbmc.getInfoLabel("System.CurrentControlID")
        try:
            return int(raw) if raw else 0
        except ValueError:
            return 0

    def run(self):
        while not self._monitor.abortRequested():
            self._tick()
            if self._monitor.waitForAbort(POLL_MS / 1000.0):
                break

    def _tick(self):
        activity = False
        cur = self.home_window.getProperty("altus.search.input")
        if cur != self._last_seen:
            self._last_seen = cur
            self._pending = True
            activity = True
        focus_id = self._focus_id()
        if focus_id != self._last_focus_id:
            self._last_focus_id = focus_id
            # Only navigation between QWERTY keys defers the fire.
            # Leaving the keyboard area (e.g. focusing the results list)
            # should let any pending refresh run.
            if self._pending and KEY_FOCUS_MIN <= focus_id <= KEY_FOCUS_MAX:
                activity = True
        if activity:
            self._last_change = time.monotonic()
            return
        if not self._pending:
            return
        with self._refresh_lock:
            if self._refreshing:
                return
            if (time.monotonic() - self._last_change) * 1000 < DEBOUNCE_MS:
                return
            self._pending = False
            if not cur:
                self.home_window.clearProperty("altus.search.input.encoded")
                self.home_window.clearProperty("altus.search.input.trakt.encoded")
                self.home_window.clearProperty("altus.search.refreshing")
                return
            self._refreshing = True
            settled_value = cur
        threading.Thread(
            target=self._do_refresh, args=(settled_value,), daemon=True
        ).start()

    def _do_refresh(self, search_term):
        """Publish the encoded properties (which trigger Kodi's auto-refetch
        of widgets whose <content> embeds $INFO[...input.encoded]) and kick
        the legacy stacked-Trakt widgets, then clear the in-progress flag."""
        from modules.cpath_maker import starting_search_widgets

        try:
            encoded = quote(search_term)
            self.home_window.setProperty("altus.search.refreshing", "true")
            self.home_window.setProperty("altus.search.input.encoded", encoded)
            self.home_window.setProperty("altus.search.input.trakt.encoded", encoded)
            starting_search_widgets()
            xbmc.sleep(COOLDOWN_MS)
            self.home_window.clearProperty("altus.search.refreshing")
        finally:
            with self._refresh_lock:
                self._refreshing = False
