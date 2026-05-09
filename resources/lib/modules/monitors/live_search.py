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

# $INFO markers that may appear inside a widget's url_template. Replaced
# with the URL-encoded query value before the resolved URL is written to
# the widget's path property.
_ENCODED_MARKER = "$INFO[Window(home).Property(altus.search.input.encoded)]"
_TRAKT_MARKER = "$INFO[Window(home).Property(altus.search.input.trakt.encoded)]"

# Cross-process sentinel for "this term was already committed to history".
# Both LiveSearchMonitor (post-widget-focus) and search_utils.search_input
# (post-add_spath_to_database) write this on commit; both check it before
# firing a fresh commit. Cleared when input goes empty.
COMMITTED_TERM_PROPERTY = "altus.search.last_committed.lower"


def write_resolved_widget_paths(encoded_term):
    """Resolve every visible search widget's url_template against the given
    URL-encoded query and publish to each widget's path property. Used by
    both the keystroke-debounced refresh path (LiveSearchMonitor) and the
    keyboard-confirmed search path (search_utils.search_input) — the latter
    needs to bypass the debounce so widgets are loadable when re_search's
    SetFocus(2000) lands."""
    from modules.search_manager.xml_generator import (
        iter_visible_widgets_with_ids,
    )
    import xbmcgui as _xbmcgui

    home = _xbmcgui.Window(10000)
    for list_id, w in iter_visible_widgets_with_ids():
        template = w["url_template"]
        resolved = template.replace(_ENCODED_MARKER, encoded_term).replace(
            _TRAKT_MARKER, encoded_term
        )
        home.setProperty("altus.search.widget.%s.path" % list_id, resolved)


class LiveSearchMonitor(threading.Thread):
    """Debounces live-search widget refreshes.

    Watches Window(home).Property(altus.search.input). When the value stays
    unchanged for DEBOUNCE_MS, fires starting_search_widgets() once in a
    sub-thread so the poll loop keeps draining keystrokes.

    Also owns the per-widget content_path properties:
    ``altus.search.widget.<list_id>.path``. Generator-emitted parent widgets
    read these via $INFO. We write the noop URL at startup and on input
    clear (resting state → NumItems=0), and the resolved plugin URL on each
    debounced fire (active query). This drives container state directly
    instead of relying on plugin empty-query behavior.
    """

    def __init__(self):
        super().__init__()
        self.daemon = True
        self.home_window = xbmcgui.Window(10000)
        # Stacked child path/label properties live on the search window's
        # namespace (Window(1121) in InfoLabels resolves to the runtime-
        # shifted id 11121). The parent's path lives on Window(home).
        self.search_window = xbmcgui.Window(SEARCH_WINDOW_ID)
        self._monitor = xbmc.Monitor()
        self._last_seen = self.home_window.getProperty("altus.search.input")
        self._last_focus_id = 0
        self._last_change = 0.0
        self._pending = False
        self._refresh_lock = threading.Lock()
        self._refreshing = False
        self._widget_cache = self._load_widget_cache()
        from modules.search_manager.xml_generator import INITIAL_PATH
        self._write_resting_paths(INITIAL_PATH)
        # Last term committed to history this session — guards against the
        # tick loop firing repeated commits while focus lingers in the widget
        # range. add_spath_to_database is idempotent (COLLATE NOCASE) but
        # refresh_search_history rewrites ~100 properties, so dedup pays off.
        self._last_committed_term = None

    def _load_widget_cache(self):
        """Snapshot of (list_id, url_template) for every visible search
        widget, in the same order/id-allocation that xml_generator uses.
        Cached at service start; ReloadSkin() after a manager save restarts
        this service, so the cache stays in sync without per-fire DB reads.

        Also populates ``self._widget_focus_ids`` — the exact set of control
        ids that count as "user accepted this query" for P8e history commit.
        Using a numeric range here would catch unrelated widget list_ids in
        the search window (e.g. 27100/27300 for recent add-ons) and fire
        the commit prematurely on initial focus."""
        try:
            from modules.search_manager.xml_generator import (
                iter_visible_widgets_with_ids,
            )
            cache = []
            focus_ids = set()
            for list_id, w in iter_visible_widgets_with_ids():
                cache.append((list_id, w["url_template"], bool(w.get("is_stacked"))))
                focus_ids.add(list_id)
                # Stacked child id matches xml_generator's "{parent}1" rule.
                # Adding it unconditionally is harmless — non-stacked widgets
                # never produce a control with that id, so it can't fire.
                focus_ids.add(int("%s1" % list_id))
            self._widget_focus_ids = focus_ids
            return cache
        except Exception:
            self._widget_focus_ids = set()
            return []

    def _path_property(self, list_id):
        return "altus.search.widget.%s.path" % list_id

    def _write_resting_paths(self, value):
        # Parent path lives on Window(home); stacked children read their
        # own path/label from Window(SEARCH_WINDOW_ID). Both must move in
        # lockstep — flushing only the parent leaves a stacked child
        # rendering the prior session's artwork/label until the user
        # navigates the parent again. NOOP_URL forces an empty refetch on
        # the child container; the label is cleared so it doesn't show
        # the stale category text alongside an empty list.
        for list_id, _url, is_stacked in self._widget_cache:
            self.home_window.setProperty(self._path_property(list_id), value)
            if is_stacked:
                self.search_window.setProperty(
                    "altus.%s.path" % list_id, value
                )
                self.search_window.clearProperty("altus.%s.label" % list_id)

    def _write_resolved_paths(self, encoded):
        write_resolved_widget_paths(encoded)

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
            # Input going empty fires the clear path immediately — debouncing
            # this would let the user scroll around with stale widgets visible
            # until they stopped interacting. The clear is cheap (a few
            # property writes), no plugin fetch fans out from the main thread.
            if not cur:
                from modules.search_manager.xml_generator import NOOP_URL
                self.home_window.clearProperty("altus.search.input.encoded")
                self.home_window.clearProperty("altus.search.input.trakt.encoded")
                self.home_window.clearProperty("altus.search.refreshing")
                self._write_resting_paths(NOOP_URL)
                self._pending = False
                # Same query later should bump count again, not be deduped
                # against this session's prior commit.
                self._last_committed_term = None
                self.home_window.clearProperty(COMMITTED_TERM_PROPERTY)
                return
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
            # Focus entering one of our generated search-widget controls =
            # user accepted the query. Commit current input to history
            # (P8e). Dedup against the last committed term so re-entering
            # the widgets with the same query is a no-op. Empty/whitespace
            # input is filtered inside commit_live_search_history.
            elif focus_id in self._widget_focus_ids:
                term = (cur or "").strip()
                if term:
                    folded = term.casefold()
                    # Dedup against both the in-process tracker (covers
                    # repeated focus within this Kodi session) and the
                    # cross-process sentinel (covers commits made by
                    # search_input from a separate RunScript process).
                    already = self.home_window.getProperty(COMMITTED_TERM_PROPERTY)
                    if folded != (self._last_committed_term or "").casefold() and folded != already:
                        self._last_committed_term = term
                        self.home_window.setProperty(COMMITTED_TERM_PROPERTY, folded)
                        threading.Thread(target=self._commit_history, daemon=True).start()
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
            self._refreshing = True
            settled_value = cur
        threading.Thread(
            target=self._do_refresh, args=(settled_value,), daemon=True
        ).start()

    def _commit_history(self):
        """Off the polling thread so ~100 setProperty calls from
        refresh_search_history don't stall the tick loop."""
        try:
            from modules.search_utils import SPaths
            SPaths().commit_live_search_history()
        except Exception:
            pass

    def _do_refresh(self, search_term):
        """Publish the encoded properties and the per-widget resolved URLs.
        Containers bound to ``altus.search.widget.<id>.path`` via $INFO
        refetch automatically when the property changes. Then kick the
        legacy stacked-Trakt widgets and clear the in-progress flag."""
        from modules.cpath_maker import starting_search_widgets

        try:
            encoded = quote(search_term)
            self.home_window.setProperty("altus.search.refreshing", "true")
            self.home_window.setProperty("altus.search.input.encoded", encoded)
            self.home_window.setProperty("altus.search.input.trakt.encoded", encoded)
            self._write_resolved_paths(encoded)
            starting_search_widgets()
            xbmc.sleep(COOLDOWN_MS)
            self.home_window.clearProperty("altus.search.refreshing")
        finally:
            with self._refresh_lock:
                self._refreshing = False
