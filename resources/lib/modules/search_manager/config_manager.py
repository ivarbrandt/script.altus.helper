# -*- coding: utf-8 -*-
"""
Data layer for the Altus search-widget manager.

Owns ``search_config.db`` — a single ``search_widget`` table holding the
ordered list of widgets shown in the search results window. No section
concept (search has no sections), no submenus.

Schema:
    search_widget(
        id              INTEGER PK AUTOINCREMENT,
        position        INTEGER NOT NULL,           -- 1-based, gap-free
        label           TEXT    NOT NULL,           -- "[SOURCE] Kind"
        kind            TEXT    NOT NULL,           -- filter / catalog grouping
        source_addon_id TEXT,                       -- NULL = library
        url_template    TEXT    NOT NULL,           -- raw $INFO[...] embedded
        display_type    TEXT    NOT NULL,           -- WidgetListXxx include
        target          TEXT    NOT NULL,           -- "videos" | "music"
        visible         INTEGER NOT NULL DEFAULT 1,
        is_stacked      INTEGER NOT NULL DEFAULT 0,
        stacked_type    TEXT                        -- child include base name
    )

Profiles (deferred until P10) will swap ``_get_db_path()`` for a profile-aware
lookup. All callers go through that function so the swap is one-line.
"""

import sqlite3
import xbmcvfs


_ADDON_DATA = "special://profile/addon_data/script.altus.helper/"
_DEFAULT_DB = _ADDON_DATA + "search_config.db"


def _get_db_path():
    """Returns the resolved path to the active search_config DB.

    P10 will branch on ``Skin.String(altus_active_search_config)`` here. For
    P2-P9, we always use the unnamed default DB.
    """
    if not xbmcvfs.exists(_ADDON_DATA):
        xbmcvfs.mkdir(_ADDON_DATA)
    return xbmcvfs.translatePath(_DEFAULT_DB)


def _connect():
    con = sqlite3.connect(_get_db_path(), timeout=20)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    return con


def _ensure_schema(con):
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS search_widget (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            position        INTEGER NOT NULL,
            label           TEXT    NOT NULL,
            kind            TEXT    NOT NULL,
            source_addon_id TEXT,
            url_template    TEXT    NOT NULL,
            display_type    TEXT    NOT NULL,
            target          TEXT    NOT NULL,
            visible         INTEGER NOT NULL DEFAULT 1,
            is_stacked      INTEGER NOT NULL DEFAULT 0,
            stacked_type    TEXT
        )
        """
    )
    con.commit()


class ConfigManager:
    """CRUD + ordering for search widgets.

    Lifecycle: create on demand, call ``close()`` when done. The manager
    window holds one instance for its session; one-shot routes (XML
    regenerate, catalog add) instantiate, mutate, close.
    """

    def __init__(self):
        self.con = _connect()
        _ensure_schema(self.con)
        self.cur = self.con.cursor()

    def close(self):
        try:
            self.con.close()
        except Exception:
            pass

    # ------------------------------------------------------------------ reads

    def get_all_widgets(self):
        rows = self.cur.execute(
            "SELECT * FROM search_widget ORDER BY position ASC"
        ).fetchall()
        return [dict(r) for r in rows]

    def get_widget(self, widget_id):
        row = self.cur.execute(
            "SELECT * FROM search_widget WHERE id = ?", (widget_id,)
        ).fetchone()
        return dict(row) if row else None

    def get_widget_count(self):
        return self.cur.execute(
            "SELECT COUNT(*) FROM search_widget"
        ).fetchone()[0]

    def is_empty(self):
        return self.get_widget_count() == 0

    # ----------------------------------------------------------------- writes

    def add_widget(self, label, kind, url_template, display_type, target,
                   source_addon_id=None, is_stacked=0, stacked_type=None,
                   visible=1):
        position = self.get_widget_count() + 1
        self.cur.execute(
            """
            INSERT INTO search_widget
                (position, label, kind, source_addon_id, url_template,
                 display_type, target, visible, is_stacked, stacked_type)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (position, label, kind, source_addon_id, url_template,
             display_type, target, visible, is_stacked, stacked_type),
        )
        self.con.commit()
        return self.cur.lastrowid

    def add_widget_from_catalog(self, entry):
        """Convenience: insert a row from a catalog.py CATALOG entry dict."""
        return self.add_widget(
            label=entry["label"],
            kind=entry["kind"],
            url_template=entry["url_template"],
            display_type=entry["display_type"],
            target=entry["target"],
            source_addon_id=entry.get("source_addon_id"),
            is_stacked=entry.get("is_stacked", 0),
            stacked_type=entry.get("stacked_type"),
            visible=1,
        )

    def update_widget(self, widget_id, **fields):
        """Partial update. Only known column names are honored."""
        allowed = {
            "label", "kind", "source_addon_id", "url_template",
            "display_type", "target", "visible", "is_stacked", "stacked_type",
        }
        sets = {k: v for k, v in fields.items() if k in allowed}
        if not sets:
            return
        cols = ", ".join("%s = ?" % k for k in sets)
        params = list(sets.values()) + [widget_id]
        self.cur.execute(
            "UPDATE search_widget SET %s WHERE id = ?" % cols, params,
        )
        self.con.commit()

    def set_visible(self, widget_id, visible):
        self.update_widget(widget_id, visible=1 if visible else 0)

    def toggle_visible(self, widget_id):
        w = self.get_widget(widget_id)
        if w is None:
            return None
        new_val = 0 if w["visible"] else 1
        self.set_visible(widget_id, new_val)
        return new_val

    def delete_widget(self, widget_id):
        w = self.get_widget(widget_id)
        if w is None:
            return
        self.cur.execute("DELETE FROM search_widget WHERE id = ?", (widget_id,))
        self.con.commit()
        self._reorder()

    # ----------------------------------------------------------------- order

    def move_widget(self, widget_id, direction):
        """Move a widget up/down by one slot, wrapping at the ends.

        ``direction`` is "up" or "down". Returns the new position, or None if
        the widget doesn't exist.
        """
        w = self.get_widget(widget_id)
        if w is None:
            return None
        total = self.get_widget_count()
        if total <= 1:
            return w["position"]
        cur_pos = w["position"]
        if direction == "up":
            new_pos = total if cur_pos == 1 else cur_pos - 1
        elif direction == "down":
            new_pos = 1 if cur_pos == total else cur_pos + 1
        else:
            return cur_pos
        self._move_to_position(widget_id, new_pos)
        return new_pos

    def _move_to_position(self, widget_id, new_position):
        w = self.get_widget(widget_id)
        if w is None:
            return
        cur_pos = w["position"]
        if cur_pos == new_position:
            return
        # Park the moving row at 0, shift the band, then drop the row in.
        self.cur.execute(
            "UPDATE search_widget SET position = 0 WHERE id = ?",
            (widget_id,),
        )
        if new_position < cur_pos:
            self.cur.execute(
                """UPDATE search_widget
                   SET position = position + 1
                   WHERE position >= ? AND position < ?""",
                (new_position, cur_pos),
            )
        else:
            self.cur.execute(
                """UPDATE search_widget
                   SET position = position - 1
                   WHERE position > ? AND position <= ?""",
                (cur_pos, new_position),
            )
        self.cur.execute(
            "UPDATE search_widget SET position = ? WHERE id = ?",
            (new_position, widget_id),
        )
        self.con.commit()

    def _reorder(self):
        """Compact positions to be 1..N gap-free, preserving current order."""
        rows = self.cur.execute(
            "SELECT id FROM search_widget ORDER BY position ASC"
        ).fetchall()
        for new_pos, row in enumerate(rows, start=1):
            self.cur.execute(
                "UPDATE search_widget SET position = ? WHERE id = ?",
                (new_pos, row["id"]),
            )
        self.con.commit()
