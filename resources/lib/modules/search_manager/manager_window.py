# -*- coding: utf-8 -*-
"""
Search Manager Window — DialogSearchManager.

Two-panel WindowXMLDialog: widget list on the left, detail editor on the
right. Mirrors the widget-manager architecture:

- Inline icon buttons (Add / Reorder / Delete) live INSIDE the focused list
  item. Left/Right cycle through them, OK fires the action. The active
  button is tracked via Window.Property("search_active_btn"); the XML
  highlights whichever button matches the property.
- In-place list operations (no full repopulate except onInit and reorder
  mode toggling).
- Service monitor thread for selection sync (push-based detail panel
  updates without relying on Kodi's per-list onFocus events in dialogs).
- Long-press (ACTION_CONTEXT_MENU) on a list item toggles its visibility,
  rendered as a dimmed [COLOR 60FFFFFF] label — same vocabulary as widget
  manager.
- On close, fires generate_and_reload() if anything changed; the generator
  internally waits for window 10035 to leave before ReloadSkin so a skin
  settings parent doesn't get torn out from under the user.

Display-type semantics for stacked widgets
------------------------------------------
For a stacked widget, `display_type` is always "WidgetListCategoryStacked"
(the parent list type) and the user-visible "Display Type" field actually
shows / edits `stacked_type` (the child type, e.g. "Landscape"). Toggling
stacked promotes/demotes between the two fields:

    Non-stacked → stacked: stacked_type ← display_type;
                           display_type  ← "WidgetListCategoryStacked"
    Stacked → non-stacked: display_type ← stacked_type;
                           stacked_type  ← NULL

URL template handling
---------------------
DB stores the full URL including the $INFO[...] query placeholder. In the
manager, we strip the placeholder for display and edit, and re-append the
matching variant on save. Two variants supported (encoded vs. trakt) —
detected from the existing URL.

Control IDs (defined in DialogSearchManager.xml):
    3000   widget list (left)
    3500   "Add Search Widget..." button (visible only when list empty)
    5001   detail grouplist (right)
    5100   Edit Label
    5101   Edit Content Type
    5102   Edit URL Template
    5103   Edit Display Type
    5104   Edit Target
    5105   Toggle Stacked
    5106   Test This Path (P7 stub)

Detail panel data flow
----------------------
The detail panel binds through ``SM_Detail*`` XML variables (see
``Includes_SearchManager.xml``). Each variable switches between two
sources based on the ``reorder_widgets`` window property:

- Live (default): ``$INFO[Container(3000).ListItem.Property(<prop>)]``
  reads directly from the focused widget's ListItem properties — no
  Python push needed; the panel updates as selection moves.
- Frozen (during reorder): ``$INFO[Window.Property(reorder_detail_<prop>)]``
  reads a snapshot taken at reorder entry, so detail values stay stable
  while the row physically moves through the list.

ListItem properties the variables read:
    widget_label, kind, url_display, display_type, target, is_stacked

Window properties the dialog sets:
    search_active_btn   ∈ {"add", "reorder", "delete", ""}
    reorder_widgets     "true" while in reorder mode, else clear
    reorder_detail_*    snapshot of the moving widget's display values
"""

import threading

import xbmc
import xbmcaddon
import xbmcgui

from modules.search_manager.config_manager import ConfigManager


SKIN_PATH = xbmcaddon.Addon("skin.altus").getAddonInfo("path")

# Action codes
ACTION_PREVIOUS_MENU = 10
ACTION_NAV_BACK = 92
ACTION_MOVE_LEFT = 1
ACTION_MOVE_RIGHT = 2
ACTION_MOVE_UP = 3
ACTION_MOVE_DOWN = 4
ACTION_CONTEXT_MENU = 117

# Control IDs
LIST_ID = 3000
ADD_EMPTY_BTN = 3500
DETAIL_GROUPLIST = 5001
EDIT_LABEL_BTN = 5100
EDIT_KIND_BTN = 5101
EDIT_URL_BTN = 5102
EDIT_DISPLAY_BTN = 5103
EDIT_TARGET_BTN = 5104
TOGGLE_STACKED_BTN = 5105
TEST_PATH_BTN = 5106

# Inline buttons inside list focusedlayout (matches widget-manager pattern)
WIDGET_BUTTONS = ["add", "reorder", "delete"]
WIDGET_BTN_DEFAULT = 0  # "add" is the default highlight

# $INFO query placeholders — never exposed in the manager UI.
Q_ENCODED = "$INFO[Window(home).Property(altus.search.input.encoded)]"
Q_TRAKT = "$INFO[Window(home).Property(altus.search.input.trakt.encoded)]"

HIDDEN_COLOR = "60FFFFFF"

# Friendly ↔ internal display-type mapping. Search widgets only use the
# subset that makes sense for poster / landscape / square content.
DISPLAY_TYPE_MAP = {
    "WidgetListBigPoster":          "Big Poster",
    "WidgetListPoster":             "Poster",
    "WidgetListSmallPoster":        "Small Poster",
    "WidgetListSmallPosterFlix":    "Small Poster - Flix",
    "WidgetListLandscape":          "Landscape",
    "WidgetListLandscapeFlix":      "Landscape - Flix",
    "WidgetListSmallLandscape":     "Small Landscape",
    "WidgetListSmallLandscapeFlix": "Small Landscape - Flix",
    "WidgetListSquare":             "Square",
    "WidgetListCategoryStacked":    "Category (Stacked)",
}

# Order matters — drives the select dialog.
SEARCH_DISPLAY_TYPES = [
    ("Big Poster",              "WidgetListBigPoster"),
    ("Poster",                  "WidgetListPoster"),
    ("Small Poster",            "WidgetListSmallPoster"),
    ("Small Poster - Flix",     "WidgetListSmallPosterFlix"),
    ("Landscape",               "WidgetListLandscape"),
    ("Landscape - Flix",        "WidgetListLandscapeFlix"),
    ("Small Landscape",         "WidgetListSmallLandscape"),
    ("Small Landscape - Flix",  "WidgetListSmallLandscapeFlix"),
    ("Square",                  "WidgetListSquare"),
]

KINDS = [
    "Movies",
    "Collections",
    "TV Shows",
    "Anime",
    "Seasons",
    "Episodes",
    "Music Videos",
    "Songs",
    "Albums",
    "Artists",
    "People",
    "Keywords (Movies)",
    "Keywords (TV Shows)",
    "Trakt Lists",
]

TARGETS = ["videos", "music"]


# ───────────────────────────────────────────────────────────── helpers

def _friendly(internal_name):
    """Map internal display type name to friendly name (or pass through)."""
    if not internal_name:
        return ""
    name = DISPLAY_TYPE_MAP.get(internal_name)
    if name:
        return name
    if internal_name.endswith("Stacked"):
        return DISPLAY_TYPE_MAP.get(internal_name[:-7], internal_name)
    return internal_name


def _internal(friendly_name):
    """Map friendly name back to internal display type. None if unknown."""
    for f, i in SEARCH_DISPLAY_TYPES:
        if f == friendly_name:
            return i
    return None


def _dim_label(text):
    return "[COLOR %s]%s[/COLOR]" % (HIDDEN_COLOR, text)


def _strip_query_placeholder(url):
    """Return URL with the trailing $INFO query placeholder removed.

    Used for display and edit; the matching placeholder is re-appended on
    save by _restore_query_placeholder.
    """
    if not url:
        return ""
    for placeholder in (Q_TRAKT, Q_ENCODED):
        idx = url.find(placeholder)
        if idx >= 0:
            return url[:idx]
    return url


def _detect_query_variant(url):
    """Return 'trakt' or 'encoded' based on which placeholder the URL uses.

    Defaults to 'encoded' when neither is present (e.g. user-typed URL
    without a placeholder; we add encoded on save).
    """
    if not url:
        return "encoded"
    return "trakt" if Q_TRAKT in url else "encoded"


def _restore_query_placeholder(url_prefix, variant):
    """Re-append the right $INFO placeholder for the chosen variant."""
    placeholder = Q_TRAKT if variant == "trakt" else Q_ENCODED
    if url_prefix.endswith(placeholder):
        return url_prefix
    return url_prefix + placeholder


# ────────────────────────────────────────────────────── service monitor

class _ServiceMonitor(threading.Thread):
    """Polls focus state every 100ms and auto-toggles the inline-button
    highlight based on which control has focus.

    Selection-driven detail refresh is no longer needed — the detail
    panel binds live through SM_Detail* XML variables and updates on its
    own as Container(3000) selection moves.
    """

    def __init__(self, dlg):
        super().__init__(daemon=True)
        self.dlg = dlg
        self._running = True

    def stop(self):
        self._running = False

    def run(self):
        monitor = xbmc.Monitor()
        while self._running and not monitor.abortRequested():
            try:
                self._check()
            except Exception:
                pass
            xbmc.sleep(100)

    def _check(self):
        d = self.dlg
        if d.list is None:
            return
        # Don't manage button highlight during reorder — the column-header
        # reorder indicator is the canonical state cue; an inline button
        # highlight on top would be redundant and visually noisy.
        if d.reorder_mode:
            return
        try:
            focus_id = d.getFocusId()
        except Exception:
            return
        if focus_id == LIST_ID:
            if d.btn_idx < 0 and d.list.size() > 0:
                d._set_btn(d.last_btn_idx)
        else:
            if d.btn_idx >= 0:
                d._clear_btn()


# ─────────────────────────────────────────────────────── dialog class

class SearchManagerDialog(xbmcgui.WindowXMLDialog):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.cm = None
        self.changed = False
        self.list = None
        self.monitor = None
        self.btn_idx = -1
        # Last button the user actively chose. Used by the service monitor
        # to restore button highlight when focus returns to the list (e.g.
        # after exiting reorder mode, after clicking a detail field, etc.).
        # Mirrors widget-manager's widget_btn_default state.
        self.last_btn_idx = WIDGET_BTN_DEFAULT
        self.reorder_mode = False
        self.reorder_widget_id = None

    # ----------------------------------------------------- lifecycle

    def onInit(self):
        self.cm = ConfigManager()
        self.list = self.getControl(LIST_ID)
        self._populate_list()
        self.monitor = _ServiceMonitor(self)
        self.monitor.start()
        if self.cm.get_widget_count() > 0:
            self.list.selectItem(0)
            self.setFocusId(LIST_ID)
            self._set_btn(WIDGET_BTN_DEFAULT)
        else:
            self.setFocusId(ADD_EMPTY_BTN)

    def _on_close(self):
        """Pre-close cleanup. Runs while the dialog is still on screen.

        Skin reload is intentionally NOT done here — it's deferred to
        open_manager() after doModal() returns, so we don't tear the skin
        out from under an in-flight onAction handler.
        """
        if self.monitor is not None:
            self.monitor.stop()
        try:
            if self.cm is not None:
                self.cm.close()
        except Exception:
            pass

    # ---------------------------------------------- list build & query

    def _populate_list(self):
        self.list.reset()
        for w in self.cm.get_all_widgets():
            self.list.addItem(self._make_item(w))

    def _make_item(self, w):
        li = xbmcgui.ListItem()
        self._set_item_props(li, w)
        return li

    def _set_item_props(self, li, w):
        is_stacked = bool(w.get("is_stacked"))
        hidden = not w.get("visible")
        label_raw = w.get("label") or ""
        label_display = _dim_label(label_raw) if hidden else label_raw

        # The "display type" the user sees: friendly stacked_type for
        # stacked widgets, friendly display_type otherwise.
        if is_stacked:
            shown_type = _friendly(w.get("stacked_type") or "")
        else:
            shown_type = _friendly(w.get("display_type") or "")
        line2 = "%s | Stacked" % shown_type if is_stacked and shown_type else (
            "Stacked" if is_stacked else shown_type
        )
        if hidden:
            line2 = _dim_label(line2)

        url_template = w.get("url_template") or ""
        li.setLabel(label_display)
        li.setLabel2(line2)
        li.setProperty("widget_id", str(w["id"]))
        li.setProperty("widget_label", label_raw)
        li.setProperty("kind", w.get("kind") or "")
        li.setProperty("url_template", url_template)
        # url_display is the URL with the $INFO query placeholder stripped;
        # it's what the detail panel shows. The full url_template stays on
        # the row for edit / generator use.
        li.setProperty("url_display", _strip_query_placeholder(url_template))
        li.setProperty("display_type", shown_type)
        li.setProperty("display_type_internal", w.get("display_type") or "")
        li.setProperty("target", w.get("target") or "")
        li.setProperty("is_stacked", "Yes" if is_stacked else "No")
        li.setProperty("stacked_type", w.get("stacked_type") or "")
        li.setProperty("hidden", "true" if hidden else "")

    def _selected_widget_id(self):
        if self.list is None or self.list.size() == 0:
            return None
        idx = self.list.getSelectedPosition()
        if idx < 0:
            return None
        item = self.list.getListItem(idx)
        wid = item.getProperty("widget_id")
        return int(wid) if wid else None

    def _focus_index(self, idx):
        if 0 <= idx < self.list.size():
            self.list.selectItem(idx)
            self.setFocusId(LIST_ID)

    # --------------------------------------------- detail panel binding
    #
    # The detail panel reads ListItem properties live through the
    # SM_Detail* XML variables (see Includes_SearchManager.xml). When
    # focus moves between widgets, the variables resolve against the
    # newly-selected item automatically. No Python push needed for the
    # live case — we only freeze on reorder entry by writing
    # reorder_detail_* window properties; the variables switch source
    # via the reorder_widgets condition.

    def _freeze_detail(self):
        """Snapshot the focused list item's display props for reorder."""
        if self.list is None or self.list.size() == 0:
            return
        idx = self.list.getSelectedPosition()
        if idx < 0:
            return
        try:
            item = self.list.getListItem(idx)
        except Exception:
            return
        for prop in self._REORDER_FREEZE_PROPS:
            self.setProperty(
                "reorder_detail_%s" % prop, item.getProperty(prop)
            )

    def _unfreeze_detail(self):
        for prop in self._REORDER_FREEZE_PROPS:
            self.clearProperty("reorder_detail_%s" % prop)

    # -------------------------------------- inline button highlighting

    def _set_btn(self, idx):
        if 0 <= idx < len(WIDGET_BUTTONS):
            self.btn_idx = idx
            self.last_btn_idx = idx  # remember for restore-on-focus-return
            self.setProperty("search_active_btn", WIDGET_BUTTONS[idx])

    def _clear_btn(self):
        # Note: don't touch last_btn_idx — clearing the highlight is
        # transient; we want to restore the same button when focus
        # returns to the list.
        self.btn_idx = -1
        self.clearProperty("search_active_btn")

    # ----------------------------------------------------- onAction

    def onAction(self, action):
        action_id = action.getId()
        focus_id = self.getFocusId()

        # Long-press → toggle visibility on focused list item.
        if action_id == ACTION_CONTEXT_MENU:
            if focus_id == LIST_ID and not self.reorder_mode:
                self._toggle_visibility()
                return

        # Back / previous menu — exit reorder mode first if active, else close.
        if action_id in (ACTION_PREVIOUS_MENU, ACTION_NAV_BACK):
            if self.reorder_mode:
                self._exit_reorder_mode()
                return
            self._on_close()
            self.close()
            return

        # Reorder mode: intercept up/down to reorder the focused widget.
        if self.reorder_mode and focus_id == LIST_ID:
            if action_id == ACTION_MOVE_UP:
                self._reorder_move("up")
                return
            if action_id == ACTION_MOVE_DOWN:
                self._reorder_move("down")
                return

        # List focus: cycle inline buttons via left/right.
        if focus_id == LIST_ID and not self.reorder_mode:
            if action_id == ACTION_MOVE_RIGHT:
                if self.btn_idx < len(WIDGET_BUTTONS) - 1:
                    self._set_btn(self.btn_idx + 1)
                else:
                    # Past last button → jump to detail panel.
                    self._clear_btn()
                    self.setFocusId(DETAIL_GROUPLIST)
                return
            if action_id == ACTION_MOVE_LEFT:
                if self.btn_idx > 0:
                    self._set_btn(self.btn_idx - 1)
                # At first button or no button selected: stay (leftmost panel).
                return

    # -------------------------------------------------------- onClick

    def onClick(self, control_id):
        # Empty-state Add button (visible only when list is empty).
        if control_id == ADD_EMPTY_BTN:
            self._on_add()
            return

        # List click. In reorder mode, OK/Select exits reorder. Otherwise
        # it fires the active inline button.
        if control_id == LIST_ID:
            if self.reorder_mode:
                self._exit_reorder_mode()
                return
            self._fire_inline_button()
            return

        # Detail panel buttons.
        if control_id == EDIT_LABEL_BTN:
            self._edit_text_field("label", "Label")
        elif control_id == EDIT_KIND_BTN:
            self._edit_kind()
        elif control_id == EDIT_URL_BTN:
            self._edit_url()
        elif control_id == EDIT_DISPLAY_BTN:
            self._edit_display_type()
        elif control_id == EDIT_TARGET_BTN:
            self._edit_target()
        elif control_id == TOGGLE_STACKED_BTN:
            self._toggle_stacked()
        elif control_id == TEST_PATH_BTN:
            xbmcgui.Dialog().notification(
                "Test This Path",
                "Coming in P7",
                xbmcgui.NOTIFICATION_INFO, 1500,
            )

    def _fire_inline_button(self):
        if self.btn_idx < 0:
            return
        btn = WIDGET_BUTTONS[self.btn_idx]
        if btn == "add":
            self._on_add()
        elif btn == "reorder":
            self._enter_reorder_mode()
        elif btn == "delete":
            self._on_delete()

    # ------------------------------------------------------- Add flow

    def _on_add(self):
        # Top-level chooser: where does the new widget come from?
        idx = xbmcgui.Dialog().select(
            "Add Search Widget",
            [
                "Preset paths",
                "Custom widget...",
                "Auto-discover (experimental)",
            ],
        )
        if idx < 0:
            return
        if idx == 0:
            new_id = self._pick_preset_widget()
        elif idx == 1:
            new_id = self._build_custom_widget()
        else:
            xbmcgui.Dialog().notification(
                "Auto-discover", "Coming in P11", xbmcgui.NOTIFICATION_INFO, 2500,
            )
            return
        if new_id is None:
            return
        self._finalize_add(new_id)

    def _pick_preset_widget(self):
        """Catalog dialog: kind → source. Returns new widget id or None."""
        from modules.search_manager.catalog import CATALOG

        # Filter by installed-addon availability. None source (library) is
        # always available.
        avail = []
        seen_addon = {}
        for e in CATALOG:
            aid = e.get("source_addon_id")
            if aid is None:
                avail.append(e)
                continue
            ok = seen_addon.get(aid)
            if ok is None:
                ok = bool(xbmc.getCondVisibility("System.HasAddon(%s)" % aid))
                seen_addon[aid] = ok
            if ok:
                avail.append(e)

        if not avail:
            xbmcgui.Dialog().ok(
                "No presets available",
                "No catalog entries match the addons installed on this system.",
            )
            return None

        # Group by kind, preserve KINDS order so the menu is stable; trailing
        # kinds not in KINDS (catalog drift) get appended in catalog order.
        by_kind = {}
        for e in avail:
            by_kind.setdefault(e["kind"], []).append(e)
        kind_order = [k for k in KINDS if k in by_kind]
        for k in by_kind.keys():
            if k not in kind_order:
                kind_order.append(k)

        kind_idx = xbmcgui.Dialog().select("Content Type", kind_order)
        if kind_idx < 0:
            return None
        kind = kind_order[kind_idx]

        entries = by_kind[kind]
        labels = [e["label"] for e in entries]
        sub_idx = xbmcgui.Dialog().select(kind, labels)
        if sub_idx < 0:
            return None
        return self.cm.add_widget_from_catalog(entries[sub_idx])

    def _build_custom_widget(self):
        """Keyboard prompts: Content Type → URL → Label → Display.

        Order matters: Content Type first decides which $INFO placeholder we
        append (Trakt vs normal) and provides the [TYPE] label prefix. URL is
        entered bare (without the placeholder) — we append it automatically
        after Display. Label is wrapped with "[TYPE] ..." to match catalog.
        """
        kind_idx = xbmcgui.Dialog().select("Content Type", KINDS)
        if kind_idx < 0:
            return None
        kind = KINDS[kind_idx]

        url_hint = "plugin://plugin.video.example/?mode=search&query="
        kb = xbmc.Keyboard(url_hint, "Search URL")
        kb.doModal()
        if not kb.isConfirmed():
            return None
        url_base = kb.getText().strip()
        if not url_base or url_base == url_hint:
            return None

        kb = xbmc.Keyboard("", "Widget label (will be prefixed with [%s])" % kind.upper())
        kb.doModal()
        if not kb.isConfirmed():
            return None
        user_label = kb.getText().strip()
        if not user_label:
            return None

        friendly = [f for f, _ in SEARCH_DISPLAY_TYPES]
        dt_idx = xbmcgui.Dialog().select("Display type", friendly)
        if dt_idx < 0:
            return None
        display_type = SEARCH_DISPLAY_TYPES[dt_idx][1]

        # Append the appropriate $INFO placeholder based on kind. Skip if the
        # user already pasted one in (defensive — keeps a power-user paste from
        # double-appending).
        if "$INFO[" in url_base:
            url_template = url_base
        else:
            placeholder = (
                "$INFO[Window(home).Property(altus.search.input.trakt.encoded)]"
                if kind == "Trakt Lists"
                else "$INFO[Window(home).Property(altus.search.input.encoded)]"
            )
            url_template = url_base + placeholder

        label = "[%s] %s" % (kind.upper(), user_label)
        target = "music" if kind in ("Songs", "Albums", "Artists") else "videos"

        return self.cm.add_widget(
            label=label,
            kind=kind,
            url_template=url_template,
            display_type=display_type,
            target=target,
            source_addon_id=None,
            is_stacked=0,
            stacked_type=None,
            visible=1,
        )

    def _finalize_add(self, new_id):
        """Common post-insert UI: reposition row after current selection,
        bubble-swap into place, focus it, restore default button."""
        self.changed = True

        # Resolve the slot directly after the currently selected widget.
        # Empty-list case: insert_idx = 0; just appended; no swaps needed.
        had_items = self.list.size() > 0
        cur_idx = self.list.getSelectedPosition() if had_items else -1
        insert_idx = (cur_idx + 1) if had_items else 0

        if had_items and cur_idx >= 0:
            cur_item = self.list.getListItem(cur_idx)
            cur_wid = int(cur_item.getProperty("widget_id"))
            cur_widget = self.cm.get_widget(cur_wid)
            if cur_widget:
                self.cm._move_to_position(new_id, cur_widget["position"] + 1)

        new_widget = self.cm.get_widget(new_id)
        if new_widget is None:
            return
        self.list.addItem(self._make_item(new_widget))
        for i in range(self.list.size() - 1, insert_idx, -1):
            self._swap_items(i, i - 1)

        self._focus_index(insert_idx)
        self._set_btn(WIDGET_BTN_DEFAULT)

    # All the properties we set on a ListItem in _set_item_props — used by
    # _swap_items to exchange identities without a list reset.
    _ITEM_PROPS = (
        "widget_id", "widget_label", "kind", "url_template", "url_display",
        "display_type", "display_type_internal", "target",
        "is_stacked", "stacked_type", "hidden",
    )

    # Properties to snapshot on reorder entry. Mirror the detail panel's
    # XML bindings; these keys are read back from Window.Property
    # (with reorder_detail_ prefix) by SM_Detail* variables in
    # Includes_SearchManager.xml.
    _REORDER_FREEZE_PROPS = (
        "widget_label", "kind", "url_display",
        "display_type", "target", "is_stacked",
    )

    def _swap_items(self, idx_a, idx_b):
        """Swap labels and properties of two list items in place."""
        try:
            a = self.list.getListItem(idx_a)
            b = self.list.getListItem(idx_b)
        except Exception:
            return
        la, lb = a.getLabel(), b.getLabel()
        l2a, l2b = a.getLabel2(), b.getLabel2()
        a.setLabel(lb)
        b.setLabel(la)
        a.setLabel2(l2b)
        b.setLabel2(l2a)
        for p in self._ITEM_PROPS:
            va, vb = a.getProperty(p), b.getProperty(p)
            a.setProperty(p, vb)
            b.setProperty(p, va)

    # ----------------------------------------------------- Delete flow

    def _on_delete(self):
        wid = self._selected_widget_id()
        if wid is None:
            return
        idx = self.list.getSelectedPosition()
        self.cm.delete_widget(wid)
        self.changed = True
        self.list.removeItem(idx)
        new_size = self.list.size()
        if new_size > 0:
            self._focus_index(min(idx, new_size - 1))
            # No explicit _set_btn needed: btn_idx was already "delete"
            # (that's how this method got dispatched), focus stays on the
            # list, so the highlight persists naturally — letting the user
            # trash the next neighbour with a single press.
        else:
            self._clear_btn()
            # Container(3000).NumItems isn't updated synchronously after
            # removeItem, so the empty-state button's <visible> clause
            # still evaluates false on this frame and setFocusId silently
            # no-ops. A 50ms breather gives Kodi a frame to refresh.
            # Same dance widget-manager does on its empty-state path.
            xbmc.sleep(50)
            self.setFocusId(ADD_EMPTY_BTN)

    # --------------------------------------------------- Reorder mode

    def _enter_reorder_mode(self):
        wid = self._selected_widget_id()
        if wid is None:
            return
        self.reorder_mode = True
        self.reorder_widget_id = wid
        # Snapshot current item's display props BEFORE setting the
        # reorder_widgets flag, so the SM_Detail* variables don't briefly
        # see empty reorder_detail_* values.
        self._freeze_detail()
        self.setProperty("reorder_widgets", "true")
        # Clear the inline-button highlight while reorder mode is active —
        # the dedicated reorder indicator next to the column header
        # conveys the state, and a highlighted "reorder" button alongside
        # it is visual noise.
        self._clear_btn()

    def _exit_reorder_mode(self):
        self.reorder_mode = False
        self.reorder_widget_id = None
        self.clearProperty("reorder_widgets")
        self._unfreeze_detail()

    def _reorder_move(self, direction):
        wid = self.reorder_widget_id
        if wid is None:
            return
        new_pos = self.cm.move_widget(wid, direction)
        if new_pos is None:
            return
        self.changed = True
        # In-place: refresh each list item's properties from the new DB
        # order. Item count is unchanged, so no add/remove needed.
        widgets = self.cm.get_all_widgets()
        for i, w in enumerate(widgets):
            try:
                item = self.list.getListItem(i)
            except Exception:
                continue
            self._set_item_props(item, w)
        # Move selection to the moved widget's new slot. Detail panel
        # stays frozen via the reorder_widgets flag — SM_Detail* XML
        # variables resolve to reorder_detail_* during reorder, then
        # naturally fall back to live Container(3000).ListItem.Property
        # bindings when reorder exits.
        if 0 <= new_pos - 1 < self.list.size():
            self.list.selectItem(new_pos - 1)

    # ---------------------------------------------------- Visibility

    def _toggle_visibility(self):
        wid = self._selected_widget_id()
        if wid is None:
            return
        new_val = self.cm.toggle_visible(wid)
        if new_val is None:
            return
        self.changed = True
        idx = self.list.getSelectedPosition()
        item = self.list.getListItem(idx)
        widget = self.cm.get_widget(wid)
        self._set_item_props(item, widget)

    # -------------------------------------------------- Edit fields

    def _edit_text_field(self, field, prompt):
        wid = self._selected_widget_id()
        if wid is None:
            return
        widget = self.cm.get_widget(wid)
        if widget is None:
            return
        new_val = xbmcgui.Dialog().input(prompt, widget.get(field) or "")
        if not new_val:
            return
        self._apply_field_update(wid, {field: new_val})

    def _edit_kind(self):
        wid = self._selected_widget_id()
        if wid is None:
            return
        widget = self.cm.get_widget(wid)
        if widget is None:
            return
        cur = widget.get("kind") or ""
        try:
            preselect = KINDS.index(cur)
        except ValueError:
            preselect = -1
        idx = xbmcgui.Dialog().select(
            "Content Type", KINDS, preselect=preselect,
        )
        if idx < 0:
            return
        new_kind = KINDS[idx]
        fields = {"kind": new_kind}
        # Symmetric query-placeholder swap on Kind change:
        #   into  Trakt Lists  →  altus.search.input.trakt.encoded
        #   out of Trakt Lists →  altus.search.input.encoded
        # Only fires when the kind actually changes between Trakt Lists
        # and something else; in-band changes (e.g. Movies → TV Shows)
        # leave the URL untouched.
        target_variant = None
        if new_kind == "Trakt Lists" and cur != "Trakt Lists":
            target_variant = "trakt"
        elif cur == "Trakt Lists" and new_kind != "Trakt Lists":
            target_variant = "encoded"
        if target_variant is not None:
            cur_url = widget.get("url_template") or ""
            if _detect_query_variant(cur_url) != target_variant:
                prefix = _strip_query_placeholder(cur_url)
                fields["url_template"] = _restore_query_placeholder(
                    prefix, target_variant,
                )
        self._apply_field_update(wid, fields)

    def _edit_url(self):
        """Edit URL template without exposing the $INFO[...] placeholder.

        Strip on prompt, restore the matching variant on save.
        """
        wid = self._selected_widget_id()
        if wid is None:
            return
        widget = self.cm.get_widget(wid)
        if widget is None:
            return
        full = widget.get("url_template") or ""
        variant = _detect_query_variant(full)
        prefix = _strip_query_placeholder(full)
        new_prefix = xbmcgui.Dialog().input("URL Template", prefix)
        if not new_prefix:
            return
        new_full = _restore_query_placeholder(new_prefix, variant)
        self._apply_field_update(wid, {"url_template": new_full})

    def _edit_display_type(self):
        """Edit Display Type. For stacked widgets, this updates `stacked_type`
        rather than `display_type` (which stays locked to
        WidgetListCategoryStacked).
        """
        wid = self._selected_widget_id()
        if wid is None:
            return
        widget = self.cm.get_widget(wid)
        if widget is None:
            return
        is_stacked = bool(widget.get("is_stacked"))
        cur_internal = (widget.get("stacked_type") if is_stacked
                        else widget.get("display_type")) or ""
        names = [f for f, _ in SEARCH_DISPLAY_TYPES]
        try:
            preselect = next(
                i for i, (_, internal) in enumerate(SEARCH_DISPLAY_TYPES)
                if internal == cur_internal
            )
        except StopIteration:
            preselect = -1
        idx = xbmcgui.Dialog().select("Display Type", names, preselect=preselect)
        if idx < 0:
            return
        new_internal = SEARCH_DISPLAY_TYPES[idx][1]
        if is_stacked:
            self._apply_field_update(wid, {"stacked_type": new_internal})
        else:
            self._apply_field_update(wid, {"display_type": new_internal})

    def _edit_target(self):
        wid = self._selected_widget_id()
        if wid is None:
            return
        widget = self.cm.get_widget(wid)
        if widget is None:
            return
        try:
            preselect = TARGETS.index(widget.get("target") or "")
        except ValueError:
            preselect = -1
        idx = xbmcgui.Dialog().select("Target", TARGETS, preselect=preselect)
        if idx < 0:
            return
        self._apply_field_update(wid, {"target": TARGETS[idx]})

    def _toggle_stacked(self):
        """Promote/demote between display_type and stacked_type so that the
        DB invariant holds: stacked widgets always have
        display_type='WidgetListCategoryStacked'."""
        wid = self._selected_widget_id()
        if wid is None:
            return
        widget = self.cm.get_widget(wid)
        if widget is None:
            return
        if widget.get("is_stacked"):
            promoted = widget.get("stacked_type") or "WidgetListSmallPoster"
            self._apply_field_update(
                wid,
                {"is_stacked": 0, "display_type": promoted, "stacked_type": None},
            )
        else:
            demoted = widget.get("display_type") or "WidgetListSmallPoster"
            self._apply_field_update(
                wid,
                {"is_stacked": 1,
                 "display_type": "WidgetListCategoryStacked",
                 "stacked_type": demoted},
            )

    def _apply_field_update(self, wid, fields):
        self.cm.update_widget(wid, **fields)
        self.changed = True
        widget = self.cm.get_widget(wid)
        idx = self.list.getSelectedPosition()
        if idx >= 0:
            item = self.list.getListItem(idx)
            self._set_item_props(item, widget)


def open_manager():
    dlg = SearchManagerDialog(
        "DialogSearchManager.xml", SKIN_PATH, "default", "1080i",
    )
    dlg.doModal()
    changed = bool(getattr(dlg, "changed", False))
    del dlg
    # Reload the skin after the dialog is fully gone, never during its
    # own onAction. This avoids tearing the dialog UI down mid-frame and
    # keeps Back/close behaviour deterministic.
    if changed:
        from modules.search_manager.xml_generator import generate_and_reload
        generate_and_reload()
