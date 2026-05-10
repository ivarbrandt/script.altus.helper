# -*- coding: utf-8 -*-

import time
import xbmc, xbmcgui, xbmcvfs
import sqlite3 as database
from modules import xmls
from urllib.parse import quote

# from modules.logger import logger

SETTINGS_PATH = xbmcvfs.translatePath(
    "special://profile/addon_data/script.altus.helper/"
)

SEARCH_DATABASE_PATH = xbmcvfs.translatePath(
    "special://profile/addon_data/script.altus.helper/spath_cache.db"
)

search_history_xml = "script-altus-search_history"

default_xmls = {
    "search_history": (search_history_xml, xmls.default_history, "SearchHistory")
}

default_path = "addons://sources/video"


def _humanize_timestamp(ts):
    """Render a unix timestamp as a relative phrase ('3 days ago')."""
    if not ts:
        return ""
    diff = int(time.time()) - int(ts)
    if diff < 1:
        return "just now"
    if diff < 60:
        return "%d second%s ago" % (diff, "" if diff == 1 else "s")
    if diff < 3600:
        n = diff // 60
        return "%d minute%s ago" % (n, "" if n == 1 else "s")
    if diff < 86400:
        n = diff // 3600
        return "%d hour%s ago" % (n, "" if n == 1 else "s")
    if diff < 86400 * 7:
        n = diff // 86400
        return "%d day%s ago" % (n, "" if n == 1 else "s")
    if diff < 86400 * 30:
        n = diff // (86400 * 7)
        return "%d week%s ago" % (n, "" if n == 1 else "s")
    if diff < 86400 * 365:
        n = diff // (86400 * 30)
        return "%d month%s ago" % (n, "" if n == 1 else "s")
    n = diff // (86400 * 365)
    return "%d year%s ago" % (n, "" if n == 1 else "s")


class SPaths:
    def __init__(self, spaths=None):
        self.connect_database()
        if spaths is None:
            self.spaths = []
        else:
            self.spaths = spaths
        self.refresh_spaths = False
        self.home_window = xbmcgui.Window(10000)
        self.max_history_items = 100

    def connect_database(self):
        if not xbmcvfs.exists(SETTINGS_PATH):
            xbmcvfs.mkdir(SETTINGS_PATH)
        self.dbcon = database.connect(SEARCH_DATABASE_PATH, timeout=20)
        self.dbcon.execute(
            "CREATE TABLE IF NOT EXISTS spath (spath_id INTEGER PRIMARY KEY AUTOINCREMENT, spath text)"
        )
        # Schema migration: existing installs may be missing the new columns.
        cols = [r[1] for r in self.dbcon.execute("PRAGMA table_info(spath)").fetchall()]
        if "last_searched" not in cols:
            self.dbcon.execute("ALTER TABLE spath ADD COLUMN last_searched INTEGER")
        if "search_count" not in cols:
            self.dbcon.execute(
                "ALTER TABLE spath ADD COLUMN search_count INTEGER NOT NULL DEFAULT 0"
            )
        self.dbcon.commit()
        self.dbcur = self.dbcon.cursor()

    def add_spath_to_database(self, spath):
        """Insert-or-update a search term.

        On first sight: insert with search_count=1 and last_searched=now.
        On repeat: bump search_count and stamp last_searched=now in place.
        Returns the spath_id for the stored row.

        Dedup is case-insensitive (COLLATE NOCASE) so 'Harry Potter' and
        'harry potter' merge into one row. The originally stored capitalization
        wins — repeats only bump count/last_searched, they don't rewrite spath.
        """
        self.refresh_spaths = True
        now = int(time.time())
        existing = self.dbcur.execute(
            "SELECT spath_id, search_count FROM spath WHERE spath = ? COLLATE NOCASE",
            (spath,),
        ).fetchone()
        if existing:
            spath_id, count = existing
            self.dbcur.execute(
                "UPDATE spath SET search_count = ?, last_searched = ? WHERE spath_id = ?",
                ((count or 0) + 1, now, spath_id),
            )
        else:
            self.dbcur.execute(
                "INSERT INTO spath (spath, search_count, last_searched) VALUES (?, 1, ?)",
                (spath, now),
            )
            spath_id = self.dbcur.lastrowid
        self.dbcon.commit()
        return spath_id

    def remove_spath_from_database(self, spath_id):
        self.refresh_spaths = True
        self.dbcur.execute("DELETE FROM spath WHERE spath_id = ?", (spath_id,))
        self.dbcon.commit()

    def is_database_empty(self):
        self.dbcur.execute("SELECT COUNT(*) FROM spath")
        rows = self.dbcur.fetchone()[0]
        return rows == 0

    def remove_all_spaths(self, skip_dialog=False):
        count_str = self.home_window.getProperty("altus.search.history.count")
        count = int(count_str) if count_str else 0
        if count == 0:
            return
        if not skip_dialog:
            dialog = xbmcgui.Dialog()
            title = "Altus"
            prompt = f"You are about to delete [COLOR red][B]{count}[/B][/COLOR] items from your search history.[CR][CR]This action cannot be undone. Proceed?"
            if not dialog.yesno(title, prompt):
                return False
        self.refresh_spaths = True
        self.dbcur.execute("DELETE FROM spath")
        self.dbcur.execute("DELETE FROM sqlite_sequence WHERE name='spath'")
        self.dbcon.commit()
        for i in range(1, 101):
            self.home_window.clearProperty(f"altus.search.history.{i}")
            self.home_window.clearProperty(f"altus.search.history.{i}.id")
            self.home_window.clearProperty(f"altus.search.history.{i}.count")
            self.home_window.clearProperty(f"altus.search.history.{i}.last")
        self.home_window.setProperty("altus.search.history.count", "0")
        # Reset the live-timestamps cadence signal — without this, the
        # service tick keeps reading the prior most-recent timestamp and
        # may stay on the 1s fast-poll cadence with nothing to update.
        self.home_window.setProperty("altus.search.history.most_recent_ts", "0")
        # Drop the cross-process dedup sentinel so the user can re-search
        # the same term immediately after clearing — otherwise the live-
        # search commit path silently skips the next add.
        self.home_window.clearProperty("altus.search.last_committed.lower")
        self.home_window.clearProperty("altus.search.input")
        self.home_window.clearProperty("altus.search.input.encoded")
        self.home_window.clearProperty("altus.search.input.trakt.encoded")
        self.home_window.setProperty(
            "altus.search.history.empty",
            "Your search history is empty. Click the search icon above to perform a new search.",
        )
        return True

    def fetch_all_spaths(self):
        """Return all rows ordered by most-recent-search first.

        Falls back to spath_id DESC for any rows that pre-date the
        last_searched column (NULL timestamps sort last).
        """
        results = self.dbcur.execute(
            "SELECT spath_id, spath, search_count, last_searched FROM spath "
            "ORDER BY COALESCE(last_searched, 0) DESC, spath_id DESC"
        ).fetchall()
        return results

    def check_spath_exists(self, spath):
        result = self.dbcur.execute(
            "SELECT spath_id FROM spath WHERE spath = ?", (spath,)
        ).fetchone()
        return result[0] if result else None

    def refresh_search_history(self):
        """Rewrite all per-history-item window properties from the DB.

        Sets, per index i ∈ 1..max_history_items:
            altus.search.history.{i}        the search term
            altus.search.history.{i}.id     spath_id
            altus.search.history.{i}.count  cumulative search_count
            altus.search.history.{i}.last   "3 days ago" relative phrase
        Plus the aggregate altus.search.history.count and the empty-state
        message.
        """
        history = self.fetch_all_spaths()
        for i in range(1, self.max_history_items + 1):
            self.home_window.clearProperty(f"altus.search.history.{i}")
            self.home_window.clearProperty(f"altus.search.history.{i}.id")
            self.home_window.clearProperty(f"altus.search.history.{i}.count")
            self.home_window.clearProperty(f"altus.search.history.{i}.last")
        most_recent_ts = 0
        for i, row in enumerate(history[: self.max_history_items], 1):
            spath_id, term, search_count, last_searched = row
            self.home_window.setProperty(f"altus.search.history.{i}", term)
            self.home_window.setProperty(f"altus.search.history.{i}.id", str(spath_id))
            self.home_window.setProperty(
                f"altus.search.history.{i}.count", str(search_count or 0)
            )
            self.home_window.setProperty(
                f"altus.search.history.{i}.last",
                _humanize_timestamp(last_searched),
            )
            if last_searched and int(last_searched) > most_recent_ts:
                most_recent_ts = int(last_searched)
        self.home_window.setProperty(
            "altus.search.history.most_recent_ts", str(most_recent_ts)
        )
        count = min(len(history), self.max_history_items)
        self.home_window.setProperty("altus.search.history.count", str(count))
        if count == 0:
            self.home_window.setProperty(
                "altus.search.history.empty",
                "Your search history is empty. Click the search icon to perform a new search.",
            )
        else:
            self.home_window.clearProperty("altus.search.history.empty")

    def refresh_history_timestamps(self):
        """Update only the .last (humanized timestamp) properties.

        The full refresh_search_history() clears every history.{i} property
        before re-setting them. List 9000's items use
        ``<visible>!String.IsEmpty(...history.{i})</visible>``, so during the
        clear pass every item briefly becomes invisible — Kodi can't hold
        focus on an invisible item, so a 60s tick fired while the user is
        on 9000 yanks focus and the only recovery is reopening the window.

        This method only writes ``.last`` for the rows that already exist,
        never touching the term/id/count properties or the visible-keyed
        history.{i}, so focus on 9000 is preserved.
        """
        history = self.fetch_all_spaths()
        most_recent_ts = 0
        for i, row in enumerate(history[: self.max_history_items], 1):
            _spath_id, _term, _search_count, last_searched = row
            self.home_window.setProperty(
                f"altus.search.history.{i}.last",
                _humanize_timestamp(last_searched),
            )
            if last_searched and int(last_searched) > most_recent_ts:
                most_recent_ts = int(last_searched)
        self.home_window.setProperty(
            "altus.search.history.most_recent_ts", str(most_recent_ts)
        )

    # update_search_history_properties was an in-place property shifter that
    # mirrored the old delete+re-add flow. With the upsert + sort-by-timestamp
    # model, refresh_search_history() rewrites all properties from the DB
    # canonically — simpler, and it picks up count/last bookkeeping for free.

    def open_search_window(self):
        """Open search window and focus appropriate control based on history state"""
        if xbmcgui.getCurrentWindowId() == 10000:
            xbmc.executebuiltin("ActivateWindow(1121)")
        self.home_window.clearProperty("altus.search.input")
        self.home_window.clearProperty("altus.search.input.encoded")
        self.home_window.clearProperty("altus.search.input.trakt.encoded")
        xbmc.sleep(200)
        count_str = self.home_window.getProperty("altus.search.history.count")
        count = int(count_str) if count_str else 0
        if count == 0:
            self.home_window.setProperty(
                "altus.search.history.empty",
                "Your search history is empty. Click the search icon to perform a new search.",
            )
            xbmc.executebuiltin("SetFocus(801)")
        else:
            self.home_window.clearProperty("altus.search.history.empty")
            xbmc.executebuiltin("SetFocus(801)")

    def search_input(self, search_term=None, from_history=False):
        if search_term is None or not search_term.strip():
            prompt = "Search" if xbmcgui.getCurrentWindowId() == 10000 else "New Search"
            keyboard = xbmc.Keyboard("", prompt, False)
            keyboard.doModal()
            if keyboard.isConfirmed():
                search_term = keyboard.getText()
                if not search_term or not search_term.strip():
                    return
            else:
                return
        self.home_window.setProperty("altus.search.refreshing", "true")
        encoded_search_term = quote(search_term)
        # Upsert: increments search_count if the term already exists, else
        # inserts with count=1. Either way, last_searched is bumped to now.
        self.add_spath_to_database(search_term)
        # Rewrite all history properties from the DB. Cheap (≤100 setProperty
        # calls) and keeps count/last in lockstep with the DB.
        self.refresh_search_history()
        self.home_window.setProperty("altus.search.input", search_term)
        self.home_window.setProperty("altus.search.input.encoded", encoded_search_term)
        self.home_window.setProperty(
            "altus.search.input.trakt.encoded", encoded_search_term
        )
        # Confirmed-search path: skip the keystroke debounce. Resolve and
        # publish widget paths now so SetFocus(2000) downstream (re_search)
        # has loadable widget containers to land on.
        from modules.monitors.live_search import (
            COMMITTED_TERM_PROPERTY,
            write_resolved_widget_paths,
        )

        write_resolved_widget_paths(encoded_search_term)
        # Stamp the cross-process commit sentinel so LiveSearchMonitor's
        # P8e widget-focus path doesn't double-bump search_count for this
        # term. Cleared by the monitor when input goes empty.
        self.home_window.setProperty(COMMITTED_TERM_PROPERTY, search_term.casefold())
        if not from_history:
            xbmc.executebuiltin("SetFocus(2000)")

    def commit_live_search_history(self):
        """Commit the current live-search input to history (P8e).

        Called from the search results window when the user focuses the
        widget grouplist (control 2000) — the heuristic that the user has
        accepted the query enough to interact with results. Empty/whitespace
        input is a no-op (e.g. user clears, then idly focuses widgets).

        Dedup is handled by add_spath_to_database (COLLATE NOCASE), so
        repeated focus on the same query just bumps search_count and
        last_searched without spamming new history rows.
        """
        search_term = self.home_window.getProperty("altus.search.input") or ""
        if not search_term.strip():
            return
        self.add_spath_to_database(search_term)
        self.refresh_search_history()

    def re_search(self):
        search_term = xbmc.getInfoLabel("ListItem.Label")
        # Mark this session as "results came from a history click" so 803's
        # onleft path (via 802's conditional onfocus) knows to flush the
        # widgets when the user navigates back. Cleared by 801/802 onfocus
        # and by the search window's onload.
        self.home_window.setProperty("altus.search.from", "history")
        self.search_input(search_term, True)
        xbmc.sleep(100)
        xbmc.executebuiltin("SetFocus(9000,0,absolute)")
        xbmc.sleep(300)
        xbmc.executebuiltin("SetFocus(2000)")

    def toggle_search_filter(self, kind):
        """Toggle a kind in the live-mode filter pill panel (P8c).

        Property format: ``all`` (or empty) means no filter; otherwise a
        concatenation of ``@Kind1@@Kind2@`` tokens. ``@`` delimiter is used
        (not ``[]``) because brackets inside ``String.Contains`` second-arg
        get parsed by Kodi as grouping expressions, not literal characters,
        and the contains check then never matches.

        - First toggle from ``all``/empty: replace with ``@kind@``.
        - Toggling an already-present kind: remove it; if nothing remains,
          fall back to ``all`` so widgets become visible again.
        - Toggling a new kind: append ``@kind@``.
        """
        if not kind:
            return
        cur = self.home_window.getProperty("altus.search.filter.kind") or ""
        token = "@" + kind + "@"
        if cur in ("all", ""):
            new = token
        elif token in cur:
            new = cur.replace(token, "")
            if not new:
                new = "all"
        else:
            new = cur + token
        self.home_window.setProperty("altus.search.filter.kind", new)


# class SPaths:
#     def __init__(self, spaths=None):
#         self.connect_database()
#         if spaths is None:
#             self.spaths = []
#         else:
#             self.spaths = spaths
#         self.refresh_spaths = False

#     def connect_database(self):
#         if not xbmcvfs.exists(SETTINGS_PATH):
#             xbmcvfs.mkdir(SETTINGS_PATH)
#         self.dbcon = database.connect(SEARCH_DATABASE_PATH, timeout=20)
#         self.dbcon.execute(
#             "CREATE TABLE IF NOT EXISTS spath (spath_id INTEGER PRIMARY KEY AUTOINCREMENT, spath text)"
#         )
#         self.dbcur = self.dbcon.cursor()

#     def add_spath_to_database(self, spath):
#         self.refresh_spaths = True
#         self.dbcur.execute(
#             "INSERT INTO spath (spath) VALUES (?)",
#             (spath,),
#         )
#         self.dbcon.commit()

#     def remove_spath_from_database(self, spath_id):
#         self.refresh_spaths = True
#         self.dbcur.execute("DELETE FROM spath WHERE spath_id = ?", (spath_id,))
#         self.dbcon.commit()

#     def is_database_empty(self):
#         self.dbcur.execute("SELECT COUNT(*) FROM spath")
#         rows = self.dbcur.fetchone()[0]
#         return rows == 0

#     def remove_all_spaths(self):
#         dialog = xbmcgui.Dialog()
#         title = "Altus"
#         prompt = "Are you sure you want to clear all search history? Once cleared, these items cannot be recovered. Proceed?"
#         self.fetch_all_spaths()
#         if dialog.yesno(title, prompt):
#             self.refresh_spaths = True
#             self.dbcur.execute("DELETE FROM spath")
#             self.dbcur.execute("DELETE FROM sqlite_sequence WHERE name='spath'")
#             self.dbcon.commit()
#             self.make_default_xml()
#             Thread(target=self.update_settings_and_reload_skin).start()

#     def fetch_all_spaths(self):
#         results = self.dbcur.execute(
#             "SELECT * FROM spath ORDER BY spath_id DESC"
#         ).fetchall()
#         return results

#     def update_settings_and_reload_skin(self):
#         xbmc.executebuiltin("Skin.SetString(SearchInput,)")
#         xbmc.executebuiltin("Skin.SetString(SearchInputEncoded,)")
#         xbmc.executebuiltin("Skin.SetString(SearchInputTraktEncoded, 'none')")
#         xbmc.executebuiltin("Skin.SetString(DatabaseStatus, 'Empty')")
#         xbmc.sleep(300)
#         xbmc.executebuiltin("ReloadSkin()")
#         xbmc.sleep(200)
#         xbmc.executebuiltin("SetFocus(27400)")

#     def make_search_history_xml(self, active_spaths, event=None):
#         if not self.refresh_spaths:
#             return
#         if not active_spaths:
#             self.make_default_xml()
#         xml_file = "special://skin/xml/%s.xml" % (search_history_xml)
#         final_format = xmls.media_xml_start.format(main_include="SearchHistory")
#         for _, spath in active_spaths:
#             body = xmls.history_xml_body
#             body = body.format(spath=spath)
#             final_format += body
#         final_format += xmls.media_xml_end
#         self.write_xml(xml_file, final_format)
#         xbmc.executebuiltin("ReloadSkin()")
#         if event is not None:
#             event.set()

#     def write_xml(self, xml_file, final_format):
#         with xbmcvfs.File(xml_file, "w") as f:
#             f.write(final_format)

#     def make_default_xml(self):
#         item = default_xmls["search_history"]
#         final_format = item[1].format(includes_type=item[2])
#         xml_file = "special://skin/xml/%s.xml" % item[0]
#         with xbmcvfs.File(xml_file, "w") as f:
#             f.write(final_format)

#     def check_spath_exists(self, spath):
#         result = self.dbcur.execute(
#             "SELECT spath_id FROM spath WHERE spath = ?", (spath,)
#         ).fetchone()
#         return result[0] if result else None

#     def open_search_window(self):
#         if xbmcgui.getCurrentWindowId() == 10000:
#             xbmc.executebuiltin("ActivateWindow(1121)")
#         if self.is_database_empty():
#             xbmc.executebuiltin("Skin.SetString(DatabaseStatus, 'Empty')")
#             xbmc.executebuiltin("Skin.SetString(SearchInputTraktEncoded, 'none')")
#             xbmc.executebuiltin("ReloadSkin()")
#             xbmc.sleep(200)
#             xbmc.executebuiltin("SetFocus(27400)")
#         else:
#             self.remake_search_history()
#             xbmc.executebuiltin("Skin.Reset(DatabaseStatus)")
#             xbmc.executebuiltin("Skin.SetString(SearchInput,)")
#             xbmc.executebuiltin("Skin.SetString(SearchInputEncoded,)")
#             xbmc.executebuiltin("Skin.SetString(SearchInputTraktEncoded, 'none')")
#             xbmc.executebuiltin("ReloadSkin()")
#             xbmc.sleep(200)
#             xbmc.executebuiltin("SetFocus(9000)")

#     def search_input(self, search_term=None):
#         if search_term is None or not search_term.strip():
#             prompt = "Search" if xbmcgui.getCurrentWindowId() == 10000 else "New Search"
#             keyboard = xbmc.Keyboard("", prompt, False)
#             keyboard.doModal()
#             if keyboard.isConfirmed():
#                 xbmc.executebuiltin("Skin.Reset(DatabaseStatus)")
#                 search_term = keyboard.getText()
#                 if not search_term or not search_term.strip():
#                     return
#             else:
#                 return
#         encoded_search_term = quote(search_term)
#         if xbmcgui.getCurrentWindowId() == 10000:
#             xbmc.executebuiltin("ActivateWindow(1121)")
#         existing_spath = self.check_spath_exists(search_term)
#         if existing_spath:
#             self.remove_spath_from_database(existing_spath)
#         self.add_spath_to_database(search_term)
#         if xbmcgui.getCurrentWindowId() == 10000:
#             self.make_search_history_xml(self.fetch_all_spaths())
#         else:
#             event = Event()
#             Thread(
#                 target=self.make_search_history_xml,
#                 args=(self.fetch_all_spaths(), event),
#             ).start()
#             event.wait()
#         xbmc.executebuiltin(f"Skin.SetString(SearchInputEncoded,{encoded_search_term})")
#         xbmc.executebuiltin(
#             f"Skin.SetString(SearchInputTraktEncoded,{encoded_search_term})"
#         )
#         xbmc.executebuiltin(f"Skin.SetString(SearchInput,{search_term})")
#         xbmc.executebuiltin("SetFocus(2000)")
#         starting_widgets()

#     def re_search(self):
#         search_term = xbmc.getInfoLabel("ListItem.Label")
#         self.search_input(search_term)

#     def remake_search_history(self):
#         self.refresh_spaths = True
#         active_spaths = self.fetch_all_spaths()
#         if active_spaths:
#             self.make_search_history_xml(active_spaths)
#         else:
#             self.make_default_xml()


# def remake_all_spaths(silent=False):
#     for item in "search_history":
#         SPaths(item).remake_search_history()
#     if not silent:
#         xbmcgui.Dialog().ok("Altus", "Search history remade")
