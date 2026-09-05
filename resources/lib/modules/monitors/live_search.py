import time
import threading
from urllib.parse import quote
import xbmc
import xbmcgui

DEBOUNCE_MS = 1000
POLL_MS = 50
# Tail buffer after the containers finish, not the throttle itself — the wait
# for IsUpdating to clear is what actually spaces rounds apart.
COOLDOWN_MS = 300
# Containers report IsUpdating ~250ms after the paths land; wait past that
# before testing, or the round looks finished before it has started.
SETTLE_GRACE_MS = 500
# Ceiling on the wait for a round to finish, so a hung fetch can't wedge search.
ROUND_MAX_MS = 20000
# Gap between successive widget path writes. Writing them in a burst makes Kodi
# start every plugin fetch at once; crashes were traced to Kodi's own fetch
# handling (the monitor thread is asleep at that point — see _do_refresh step
# markers), so the only lever left is lowering how many run concurrently.
# Mitigation, not a fix: it reduces the odds, it cannot remove them.
STAGGER_MS = 300
# Ceiling on how long the fire will wait for widgets to finish loading. A dead
# addon or a hung network call can leave a container updating indefinitely;
# without this, search would wedge permanently rather than degrade.
MAX_DEFER_MS = 15000

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


def set_gui_property(name, value):
    """Set a home-window property from the GUI thread.

    Any property bound to a container's content_path via $INFO MUST go through
    here rather than Window.setProperty. Writing one from a daemon thread while
    the GUI is rendering that container races the GUI thread and hard-crashes
    Kodi — no Python traceback, the log's tail is lost to the buffer. The same
    race is documented in search_manager/xml_generator for Window(1121); moving
    these keys to Window(home) made it rarer, not safe. Reproducible by typing
    while search results are still loading.

    xbmc.executebuiltin() runs on the app thread, which removes the race.

    Caveat: the builtin splits its arguments on commas, so a value containing a
    literal comma would be truncated. No widget URL in the catalog contains one
    and hand-entered custom widgets are URLs too, so this is accepted rather
    than guarded — but a value with a comma will corrupt the path silently, so
    check here first if a widget ever loads a mangled URL.
    """
    xbmc.executebuiltin("SetProperty(%s,%s,home)" % (name, value))


def clear_gui_property(name):
    """Clear a content_path-bound property from the GUI thread. See
    set_gui_property for why these can't use Window.clearProperty."""
    xbmc.executebuiltin("ClearProperty(%s,home)" % name)


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

    first = True
    for list_id, w in iter_visible_widgets_with_ids():
        template = w["url_template"]
        resolved = template.replace(_ENCODED_MARKER, encoded_term).replace(
            _TRAKT_MARKER, encoded_term
        )
        # Stagger so Kodi doesn't start every plugin fetch at once. No sleep
        # before the first write, so a single-widget config is unaffected and
        # the first results appear as promptly as before.
        if not first:
            xbmc.sleep(STAGGER_MS)
        first = False
        set_gui_property("altus.search.widget.%s.path" % list_id, resolved)


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
        self._monitor = xbmc.Monitor()
        self._last_seen = self.home_window.getProperty("altus.search.input")
        # Last edit-control text we mirrored to altus.search.input. Guard
        # against re-mirroring on every tick (and clobbering python-driven
        # writes that don't go through the edit control).
        self._last_edit = ""
        self._last_focus_id = 0
        self._last_change = 0.0
        self._pending = False
        self._refresh_lock = threading.Lock()
        self._refreshing = False
        # When the fire first started waiting on still-loading widgets, so the
        # MAX_DEFER_MS ceiling can be measured. None while not deferring.
        self._defer_since = None
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

    def _widgets_still_loading(self):
        """True while any search container is still fetching.

        Starting a round on top of one still in flight re-paths containers
        mid-fetch: widgets half-populate, some never come back, and enough
        overlap takes Kodi down. DEBOUNCE_MS only made that collision less
        likely — typing while results are loading still reproduced it at 3000ms.

        _widget_focus_ids already holds exactly the ids to check: every parent
        list_id plus its stacked child. Ids with no matching control just read
        false.
        """
        updating = [
            list_id
            for list_id in self._widget_focus_ids
            if xbmc.getCondVisibility("Container(%s).IsUpdating" % list_id)
        ]
        return bool(updating)

    def _path_property(self, list_id):
        return "altus.search.widget.%s.path" % list_id

    def _write_resting_paths(self, value):
        # All search-related properties live on Window(home). Parent path
        # at altus.search.widget.<id>.path; stacked-child path/label at
        # altus.search.child.<id>.path / .label (distinct prefix from
        # home stacked widgets' altus.<id>.* — the numeric list_id
        # ranges overlap, see search_manager/xml_generator comment).
        # Both must move in lockstep so flushing one without the other
        # can't leave a child rendering the prior session's artwork.
        # Order matters: write children before parents. Flushing the parent
        # first tears down the stacked group while the child container still
        # holds resolved items, leaving them stuck on the prior session's
        # artwork until the next focus/refresh.
        # Content_path-bound keys — GUI thread only, see set_gui_property.
        for list_id, _url, is_stacked in self._widget_cache:
            if is_stacked:
                set_gui_property("altus.search.child.%s.path" % list_id, value)
                clear_gui_property("altus.search.child.%s.label" % list_id)
        for list_id, _url, _is_stacked in self._widget_cache:
            set_gui_property(self._path_property(list_id), value)

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

    def _mirror_edit_control(self):
        """Mirror the native edit control into altus.search.input.

        Read via InfoLabel — getControl().getText() is not safe from this
        daemon thread (feedback_kodi_getcontrol_thread_unsafe.md). Writes only
        when the text actually changed, so python-driven property writes (e.g.
        history replay via search_input) aren't clobbered by the next tick.

        Callers must confirm control 9100 is addressable first. That check and
        the InfoLabel read here are separate calls, though, so a dialog opening
        between them still yields a spurious "" — which would wipe a live query,
        unmount every widget, and (by also resetting _last_edit) write the stale
        edit text back when the dialog closes. Losing text is the only
        unrecoverable direction, so re-verify before accepting an empty read. A
        genuine clear still passes, because 9100 stays addressable.
        """
        edit_text = xbmc.getInfoLabel("Control.GetLabel(9100).index(1)")
        if edit_text == self._last_edit:
            return
        if not edit_text and self._last_edit:
            if not xbmc.getCondVisibility(
                "Window.IsActive(1121) + Control.IsVisible(9100)"
            ):
                xbmc.log(
                    "[altus.livesearch] discarded spurious empty read "
                    "(prev=%r) — dialog opened mid-tick" % self._last_edit,
                    xbmc.LOGINFO,
                )
                return
        self._last_edit = edit_text
        self.home_window.setProperty("altus.search.input", edit_text)

    def _tick(self):
        activity = False
        # Gate ONLY the mirror on 9100 being addressable. Everything below —
        # input bookkeeping, the clear path, focus handling — must keep running
        # when it isn't. Skipping the whole tick lets altus.search.input drift
        # away from _last_seen while 9100 is hidden (history mode), so when it
        # reappears the monitor treats the stale value as new input and re-fires
        # the debounce, reloading widgets that were meant to stay cleared.
        # Control.GetLabel and Control.IsVisible both resolve against the ACTIVE
        # window, so IsVisible(9100) is false in exactly the cases where the
        # read is meaningless — whatever is on top, modal or not. Enumerating
        # dialog types does not work: Window.IsActive(1121) stays true beneath
        # an open dialog, and redlight's custom dialogs are non-modal.
        if xbmc.getCondVisibility("Window.IsActive(1121) + Control.IsVisible(9100)"):
            self._mirror_edit_control()
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
        # Don't fan out plugin fetches while the search window isn't front.
        # Control.IsVisible(9100) is false whenever something is on top (see
        # the mirror gate above), and a fetch the user can't see only competes
        # for worker threads. _pending survives, so the refresh runs as soon as
        # they come back — and _last_change is already stale by then, so it
        # fires immediately rather than waiting out another debounce.
        if not xbmc.getCondVisibility(
            "Window.IsActive(1121) + Control.IsVisible(9100)"
        ):
            return
        with self._refresh_lock:
            if self._refreshing:
                return
            if (time.monotonic() - self._last_change) * 1000 < DEBOUNCE_MS:
                return
            # Never start a round while the previous one is still loading.
            # _pending stays set, so this retries every tick and fires as soon
            # as the containers settle — instant for library widgets, patient
            # only when plugins are slow. _last_change isn't touched, so no
            # further debounce is served after the wait.
            if self._widgets_still_loading():
                now = time.monotonic()
                if self._defer_since is None:
                    self._defer_since = now
                if (now - self._defer_since) * 1000 < MAX_DEFER_MS:
                    return
            self._defer_since = None
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
        legacy stacked-Trakt widgets and clear the in-progress flag.

        The COOLDOWN_MS sleep is load-bearing: it holds _refreshing so the next
        refresh cannot start until the containers have had time to settle. An
        earlier attempt to abandon superseded refreshes released it early, which
        removed that spacing during typing and left widgets half-loaded."""
        from modules.cpath_maker import starting_search_widgets

        try:
            encoded = quote(search_term)
            self.home_window.setProperty("altus.search.refreshing", "true")
            self.home_window.setProperty("altus.search.input.encoded", encoded)
            self.home_window.setProperty("altus.search.input.trakt.encoded", encoded)
            self._write_resolved_paths(encoded)
            starting_search_widgets()
            # Hold _refreshing for the round's real duration, not a guess.
            # Measured: containers report IsUpdating within ~250ms of the paths
            # landing and finish around 3s — but COOLDOWN_MS used to release the
            # throttle at 1.2s, so any fire between 1.2s and 3s started a second
            # round on top of one still fetching. That re-paths containers
            # mid-fetch, which is why widgets sometimes never came back as the
            # term changed. Slow or erroring plugins stretch the round well past
            # 3s, which no fixed constant can cover.
            xbmc.sleep(SETTLE_GRACE_MS)
            deadline = time.monotonic() + (ROUND_MAX_MS / 1000.0)
            while time.monotonic() < deadline and self._widgets_still_loading():
                xbmc.sleep(100)
            xbmc.sleep(COOLDOWN_MS)
            self.home_window.clearProperty("altus.search.refreshing")
        finally:
            with self._refresh_lock:
                self._refreshing = False
