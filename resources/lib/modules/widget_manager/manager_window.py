# -*- coding: utf-8 -*-
import xbmc
import xbmcgui
import xbmcaddon
import threading

from modules.widget_manager.config_manager import ConfigManager
from modules.widget_manager.xml_generator import generate_and_reload
from modules.widget_manager import path_browser

SKIN_PATH = xbmcaddon.Addon("skin.altus").getAddonInfo("path")

# Display type mapping: internal name → friendly name
DISPLAY_TYPE_MAP = {
    "WidgetListBigPoster": "Big Poster",
    "WidgetListPoster": "Poster",
    "WidgetListSmallPoster": "Small Poster",
    "WidgetListSmallPosterFlix": "Small Poster - Flix",
    "WidgetListLandscape": "Landscape",
    "WidgetListLandscapeFlix": "Landscape - Flix",
    "WidgetListSmallLandscape": "Small Landscape",
    "WidgetListSmallLandscapeFlix": "Small Landscape - Flix",
    "WidgetListCategory": "Category",
    "WidgetListCategoryStacked": "Category (Stacked)",
    "WidgetListSquare": "Square",
    "WidgetListFavourites": "SquareWall",
    "WidgetListPVR": "PVR",
}

# Selectable display types (tuples of friendly, internal)
WIDGET_DISPLAY_TYPES = [
    ("Big Poster", "WidgetListBigPoster"),
    ("Poster", "WidgetListPoster"),
    ("Small Poster", "WidgetListSmallPoster"),
    ("Small Poster - Flix", "WidgetListSmallPosterFlix"),
    ("Landscape", "WidgetListLandscape"),
    ("Landscape - Flix", "WidgetListLandscapeFlix"),
    ("Small Landscape", "WidgetListSmallLandscape"),
    ("Small Landscape - Flix", "WidgetListSmallLandscapeFlix"),
    ("Category", "WidgetListCategory"),
]

STACKED_DISPLAY_TYPES = [
    ("Big Poster", "WidgetListBigPoster"),
    ("Poster", "WidgetListPoster"),
    ("Small Poster", "WidgetListSmallPoster"),
    ("Small Poster - Flix", "WidgetListSmallPosterFlix"),
    ("Landscape", "WidgetListLandscape"),
    ("Landscape - Flix", "WidgetListLandscapeFlix"),
    ("Small Landscape", "WidgetListSmallLandscape"),
    ("Small Landscape - Flix", "WidgetListSmallLandscapeFlix"),
]

PVR_DISPLAY_TYPES = [
    ("PVR", "WidgetListPVR"),
    ("Square", "WidgetListSquare"),
    ("Category", "WidgetListCategory"),
]

MUSIC_DISPLAY_TYPES = [
    ("Square", "WidgetListSquare"),
    ("Category", "WidgetListCategory"),
]

ADDON_DISPLAY_TYPES = [
    ("Square", "WidgetListSquare"),
]

FAVOURITES_DISPLAY_TYPES = [
    ("SquareWall", "WidgetListFavourites"),
    ("Square", "WidgetListSquare"),
]

CATEGORY_ONLY_DISPLAY_TYPES = [
    ("Category", "WidgetListCategory"),
]

PICTURE_DISPLAY_TYPES = [
    ("Category", "WidgetListCategory"),
]

GAME_DISPLAY_TYPES = [
    ("Square", "WidgetListSquare"),
]

PROGRAM_DISPLAY_TYPES = [
    ("Square", "WidgetListSquare"),
]

TARGET_TYPES = [
    "videos",
    "music",
    "programs",
    "addonbrowser",
    "pictures",
    "games",
    "tvchannels",
    "tvguide",
    "tvrecordings",
    "tvtimers",
    "tvsearch",
    "radiochannels",
    "radioguide",
    "radiorecordings",
    "radiotimers",
    "radiosearch",
    "files",
]


def _get_display_types_for_widget(widget):
    """Return the appropriate (name, internal) display type list for a widget."""
    path = widget.get("path", "")
    target = widget.get("target", "")
    if path.startswith("pvr://"):
        return PVR_DISPLAY_TYPES
    if path == "addons://":
        return CATEGORY_ONLY_DISPLAY_TYPES
    if path.startswith("addons://") or path.startswith("androidapp://"):
        return ADDON_DISPLAY_TYPES
    if path.startswith("favourites://"):
        return FAVOURITES_DISPLAY_TYPES
    if path.startswith("musicdb://") or path.startswith("library://music/"):
        return MUSIC_DISPLAY_TYPES
    if target == "music":
        return MUSIC_DISPLAY_TYPES
    if path.startswith("sources://pictures/") or target == "pictures":
        return PICTURE_DISPLAY_TYPES
    if target == "games":
        return GAME_DISPLAY_TYPES
    if target == "programs":
        return PROGRAM_DISPLAY_TYPES
    # Video content — all types available
    return WIDGET_DISPLAY_TYPES


SORT_BY_TYPES = [
    "none",
    "label",
    "title",
    "date",
    "year",
    "rating",
    "genre",
    "artist",
    "album",
    "track",
    "duration",
    "lastplayed",
    "lastused",
    "dateadded",
    "episode",
    "season",
    "totalepisodes",
    "playcount",
    "random",
]

SORT_ORDER_TYPES = ["ascending", "descending"]

# Control IDs matching DialogWidgetManager.xml
SECTION_LIST = 3000
WIDGET_LIST = 4000
DETAIL_GROUPLIST = 5001
DETAIL_LABEL = 5100
DETAIL_DISPLAY_TYPE = 5101
DETAIL_PATH = 5102
DETAIL_STACKED = 5103
DETAIL_TARGET = 5104
DETAIL_STACKED_TYPE = 5105
DETAIL_LIMIT = 5106
DETAIL_SORTBY = 5107
DETAIL_SORTORDER = 5108
ADD_SECTION_BTN = 3500
ADD_WIDGET_BTN = 4500
DETAIL_CONTROLS = frozenset(
    (
        DETAIL_GROUPLIST,
        DETAIL_LABEL,
        DETAIL_DISPLAY_TYPE,
        DETAIL_PATH,
        DETAIL_STACKED,
        DETAIL_TARGET,
        DETAIL_LIMIT,
        DETAIL_SORTBY,
        DETAIL_SORTORDER,
    )
)

# Kodi action IDs
ACTION_MOVE_LEFT = 1
ACTION_MOVE_RIGHT = 2
ACTION_MOVE_UP = 3
ACTION_MOVE_DOWN = 4
ACTION_SELECT = 7
ACTION_PREVIOUS_MENU = 10
ACTION_NAV_BACK = 92
ACTION_CONTEXT_MENU = 117

# Inline button definitions
SECTION_BUTTONS = ["add", "rename", "edit", "reorder", "delete"]
WIDGET_BUTTONS = ["add", "reorder", "delete"]


HIDDEN_COLOR = "60FFFFFF"


def _friendly(internal_name):
    if not internal_name:
        return internal_name
    name = DISPLAY_TYPE_MAP.get(internal_name)
    if name:
        return name
    # Fallback: strip "Stacked" suffix and retry (handles old DB values)
    if internal_name.endswith("Stacked"):
        return DISPLAY_TYPE_MAP.get(internal_name[:-7], internal_name)
    return internal_name


def _dim_label(text):
    """Wrap text in a dim color tag for hidden items."""
    return "[COLOR %s]%s[/COLOR]" % (HIDDEN_COLOR, text)


class _ServiceMonitor(threading.Thread):
    """Background thread that polls list state while the window is open."""

    def __init__(self, window):
        super().__init__(daemon=True)
        self.window = window
        self.running = True

    def run(self):
        monitor = xbmc.Monitor()
        while self.running and not monitor.abortRequested():
            try:
                self._check_state()
            except Exception:
                pass
            xbmc.sleep(100)

    def _check_state(self):
        w = self.window
        # Don't interfere during reorder
        if w.reorder_mode:
            return
        # Detect section selection change → refresh widget list
        section_list = w.getControl(SECTION_LIST)
        idx = section_list.getSelectedPosition()
        if 0 <= idx < len(w.section_ids):
            sid = w.section_ids[idx]
            if sid != w.current_section_id:
                w.current_section_id = sid
                w._update_widgets_inline()

        # Auto-highlight inline button based on which list has focus
        try:
            focus_id = w.getFocusId()
        except Exception:
            return

        if focus_id == SECTION_LIST:
            if w.section_btn_idx < 0 and len(w.section_ids) > 0:
                w._set_btn("section", w.section_btn_default)
            if w.widget_btn_idx >= 0:
                w._clear_btn("widget")
        elif focus_id == WIDGET_LIST:
            if w.widget_btn_idx < 0 and len(w.widget_ids) > 0:
                w._set_btn("widget", w.widget_btn_default)
            if w.section_btn_idx >= 0:
                w._clear_btn("section")
        else:
            # Detail panel or other control
            if w.section_btn_idx >= 0:
                w._clear_btn("section")
            if w.widget_btn_idx >= 0:
                w._clear_btn("widget")

    def stop(self):
        self.running = False


class WidgetManagerWindow(xbmcgui.WindowXMLDialog):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.cm = None
        self.config = {}
        self.section_ids = []
        self.widget_ids = []
        self.current_section_id = None
        self.reorder_mode = False
        self.reorder_target = None
        self.reorder_item_id = None
        self.changed = False
        self.monitor_thread = None
        # Inline button tracking: -1 = no button selected
        self.section_btn_idx = -1
        self.widget_btn_idx = -1
        # Remember last button position for each list (persists across up/down)
        self.section_btn_default = 0
        self.widget_btn_default = 0
        # Track previous focus for detail→section redirect
        self.prev_focus_id = 0

    def onInit(self):
        self.cm = ConfigManager()
        self._load_config()
        self._populate_sections()
        # Start service monitor
        self.monitor_thread = _ServiceMonitor(self)
        self.monitor_thread.start()
        # Focus first section and set initial button
        if self.section_ids:
            self.getControl(SECTION_LIST).selectItem(0)
            self.setFocusId(SECTION_LIST)
            self._set_btn("section", 0)
        else:
            self.setFocusId(ADD_SECTION_BTN)

    def _load_config(self):
        self.config = self.cm.get_full_config()

    def _populate_sections(self):
        section_list = self.getControl(SECTION_LIST)
        section_list.reset()
        self.section_ids = []
        sorted_ids = sorted(
            self.config, key=lambda sid: self.config[sid]["section"]["position"]
        )
        for sid in sorted_ids:
            section = self.config[sid]["section"]
            name = section["name"]
            hidden = section.get("visible") == "false"
            li = xbmcgui.ListItem(_dim_label(name) if hidden else name)
            li.setProperty("section_id", str(sid))
            li.setProperty("hidden", "true" if hidden else "")
            section_list.addItem(li)
            self.section_ids.append(sid)
        if self.section_ids:
            if self.current_section_id not in self.section_ids:
                self.current_section_id = self.section_ids[0]
            # Select immediately to avoid flicker on item 0
            idx = self.section_ids.index(self.current_section_id)
            section_list.selectItem(idx)
            self._populate_widgets()

    def _populate_widgets(self):
        """Full populate — only called from onInit."""
        widget_list = self.getControl(WIDGET_LIST)
        widget_list.reset()
        self.widget_ids = []
        self.widget_btn_idx = -1
        if self.current_section_id is None:
            return
        section_data = self.config.get(self.current_section_id)
        if not section_data:
            return
        for widget in section_data["widgets"]:
            li = self._make_widget_item(widget)
            widget_list.addItem(li)
            self.widget_ids.append(widget["id"])

    def _update_widgets_inline(self):
        """Update widget list in-place without reset — no flicker."""
        widget_list = self.getControl(WIDGET_LIST)
        self.widget_btn_idx = -1
        new_widgets = []
        is_weather = False
        if self.current_section_id and self.current_section_id in self.config:
            section_data = self.config.get(self.current_section_id)
            if section_data:
                new_widgets = section_data["widgets"]
                is_weather = section_data["section"]["name"] == "Weather"
        if is_weather:
            self.setProperty("weather_section", "true")
        else:
            self.clearProperty("weather_section")
        old_count = len(self.widget_ids)
        new_count = len(new_widgets)
        # Update existing items in-place
        for i in range(min(old_count, new_count)):
            widget = new_widgets[i]
            li = widget_list.getListItem(i)
            self._set_widget_item_props(li, widget)
        # Remove excess items from end
        for i in range(old_count - 1, new_count - 1, -1):
            widget_list.removeItem(i)
        # Add new items if new section has more widgets
        for i in range(old_count, new_count):
            li = self._make_widget_item(new_widgets[i])
            widget_list.addItem(li)
        self.widget_ids = [w["id"] for w in new_widgets]

    def _make_widget_item(self, widget):
        """Create a ListItem from a widget dict."""
        is_stacked = widget["is_stacked"]
        stacked_type = widget.get("stacked_type", "")
        hidden = widget.get("visible") == "false"
        if is_stacked:
            friendly_type = _friendly(stacked_type)
            line2 = "%s | Stacked" % friendly_type if friendly_type else "Stacked"
        else:
            friendly_type = _friendly(widget["display_type"])
            line2 = friendly_type
        label = _dim_label(widget["label"]) if hidden else widget["label"]
        line2 = _dim_label(line2) if hidden else line2
        li = xbmcgui.ListItem(label, line2)
        self._set_widget_item_props(li, widget)
        return li

    def _set_widget_item_props(self, li, widget):
        """Set all properties on a widget ListItem."""
        is_stacked = widget["is_stacked"]
        stacked_type = widget.get("stacked_type", "")
        hidden = widget.get("visible") == "false"
        if is_stacked:
            friendly_type = _friendly(stacked_type)
            line2 = "%s | Stacked" % friendly_type if friendly_type else "Stacked"
        else:
            friendly_type = _friendly(widget["display_type"])
            line2 = friendly_type
        label = _dim_label(widget["label"]) if hidden else widget["label"]
        line2 = _dim_label(line2) if hidden else line2
        li.setLabel(label)
        li.setLabel2(line2)
        li.setProperty("widget_id", str(widget["id"]))
        li.setProperty("widget_label", widget["label"])
        if is_stacked:
            li.setProperty("display_type", _friendly(stacked_type))
        else:
            li.setProperty("display_type", _friendly(widget["display_type"]))
        li.setProperty("widget_path", widget["path"])
        li.setProperty("target", widget["target"])
        li.setProperty("is_stacked", "Yes" if is_stacked else "No")
        li.setProperty("stacked_type", _friendly(stacked_type))
        li.setProperty("limit_num", str(widget.get("limit_num", 0)))
        li.setProperty("sortby", widget.get("sortby", ""))
        li.setProperty("sortorder", widget.get("sortorder", ""))
        li.setProperty("hidden", "true" if hidden else "")

    def _get_selected_section_id(self):
        section_list = self.getControl(SECTION_LIST)
        idx = section_list.getSelectedPosition()
        if 0 <= idx < len(self.section_ids):
            return self.section_ids[idx]
        return None

    def _get_selected_widget_id(self):
        widget_list = self.getControl(WIDGET_LIST)
        idx = widget_list.getSelectedPosition()
        if 0 <= idx < len(self.widget_ids):
            return self.widget_ids[idx]
        return None

    # ── Inline Button Management ──

    def _set_btn(self, target, idx):
        """Set the active button via window property."""
        if target == "section":
            self.section_btn_idx = idx
            if idx >= 0:
                self.section_btn_default = idx
            btn_name = SECTION_BUTTONS[idx] if idx >= 0 else ""
            self.setProperty("section_active_btn", btn_name)
        else:
            self.widget_btn_idx = idx
            if idx >= 0:
                self.widget_btn_default = idx
            btn_name = WIDGET_BUTTONS[idx] if idx >= 0 else ""
            self.setProperty("widget_active_btn", btn_name)

    def _clear_btn(self, target):
        """Clear button highlight."""
        if target == "section":
            self.section_btn_idx = -1
            self.clearProperty("section_active_btn")
        else:
            self.widget_btn_idx = -1
            self.clearProperty("widget_active_btn")

    def _activate_btn(self, target):
        """Execute the currently highlighted button's action."""
        if target == "section":
            idx = self.section_btn_idx
            if idx < 0:
                return
            btn = SECTION_BUTTONS[idx]
            item_id = self._get_selected_section_id()
            self._clear_btn("section")
            if btn == "add":
                self._add_section()
            elif btn == "rename":
                self._rename_section()
            elif btn == "edit":
                self._edit_section_onclick()
            elif btn == "reorder":
                self._toggle_reorder("section", item_id)
            elif btn == "delete":
                self._delete_section()
            # Re-set button immediately so user doesn't need extra click
            if self.section_ids and not self.reorder_mode:
                self._set_btn("section", self.section_btn_default)
        else:
            idx = self.widget_btn_idx
            if idx < 0:
                return
            btn = WIDGET_BUTTONS[idx]
            item_id = self._get_selected_widget_id()
            self._clear_btn("widget")
            if btn == "add":
                self._add_widget()
            elif btn == "reorder":
                self._toggle_reorder("widget", item_id)
            elif btn == "delete":
                self._delete_widget()
            # Re-set button immediately so user doesn't need extra click
            if self.widget_ids and not self.reorder_mode:
                self._set_btn("widget", self.widget_btn_default)

    # ── Section Actions ──

    def _add_section(self):
        result = path_browser.browse()
        if not result:
            return
        default_name = result.get("label", "")
        # Weather is a special section — hardcoded onclick and widgets in skin XML
        is_weather = default_name == "Weather" and not result.get("path")
        if is_weather:
            name = "Weather"
        else:
            name = self._input("Section Name", default_name)
            if not name:
                return
        onclick = (
            "ActivateWindow(Weather)"
            if is_weather
            else path_browser.build_onclick(
                result["path"], result.get("target", "videos")
            )
        )
        # Determine insert position (after current selection)
        current = self._get_selected_section_id()
        current_idx = (
            self.section_ids.index(current)
            if current and current in self.section_ids
            else len(self.section_ids) - 1
        )
        pos_after = None
        if current and current in self.config:
            pos_after = self.config[current]["section"]["position"]
        section_id = self.cm.add_section(name=name, onclick=onclick)
        if pos_after is not None:
            self.cm.reorder_section(section_id, pos_after + 1)
        self.changed = True
        # Insert in-place (no list reset = no flicker)
        insert_idx = current_idx + 1
        li = xbmcgui.ListItem(name)
        li.setProperty("section_id", str(section_id))
        section_list = self.getControl(SECTION_LIST)
        section_list.addItem(li)
        # Move from end to correct position by swapping
        for i in range(len(self.section_ids), insert_idx, -1):
            self._swap_section_items(section_list, i, i - 1)
        self.section_ids.insert(insert_idx, section_id)
        self.current_section_id = section_id
        self._load_config()
        self._update_widgets_inline()
        # Select AFTER update to prevent focus side effects
        section_list.selectItem(insert_idx)

    def _delete_section(self):
        sid = self._get_selected_section_id()
        if sid is None:
            return
        name = self.config[sid]["section"]["name"]
        if not self._confirm("Delete section '%s' and all its widgets?" % name):
            return
        del_idx = self.section_ids.index(sid) if sid in self.section_ids else 0
        self.cm.remove_section(sid)
        self.changed = True
        # Remove in-place (no list reset = no focus flicker)
        section_list = self.getControl(SECTION_LIST)
        section_list.removeItem(del_idx)
        self.section_ids.pop(del_idx)
        if self.section_ids:
            focus_idx = min(del_idx, len(self.section_ids) - 1)
            self.current_section_id = self.section_ids[focus_idx]
            section_list.selectItem(focus_idx)
        else:
            self.current_section_id = None
        self._load_config()
        self._update_widgets_inline()

    def _rename_section(self):
        sid = self._get_selected_section_id()
        if sid is None:
            return
        current_name = self.config[sid]["section"]["name"]
        new_name = self._input("Rename Section", current_name)
        if not new_name or new_name == current_name:
            return
        self.cm.update_section(sid, name=new_name)
        self.changed = True
        # Update label in-place
        idx = self.section_ids.index(sid) if sid in self.section_ids else -1
        if idx >= 0:
            self.getControl(SECTION_LIST).getListItem(idx).setLabel(new_name)
        self._load_config()

    def _edit_section_onclick(self):
        sid = self._get_selected_section_id()
        if sid is None:
            return
        result = path_browser.browse()
        if not result:
            return
        onclick = path_browser.build_onclick(
            result["path"], result.get("target", "videos")
        )
        self.cm.update_section(sid, onclick=onclick)
        self.changed = True
        self._load_config()

    # ── Widget Actions ──

    def _add_widget(self):
        if self.current_section_id is None:
            xbmcgui.Dialog().notification("Widget Manager", "Select a section first")
            return
        section_data = self.config.get(self.current_section_id)
        if section_data and section_data["section"]["name"] == "Weather":
            return
        result = path_browser.browse()
        if not result:
            return
        path = result["path"]
        target = result.get("target", "videos")
        default_label = result.get("label", "")
        label = self._input("Widget Label", default_label)
        if not label:
            return
        internal_type = result.get("display_type")
        if internal_type is None:
            # Auto-assign didn't resolve — prompt with filtered types
            types = _get_display_types_for_widget({"path": path, "target": target})
            names = [t[0] for t in types]
            idx = self._select("Display Type", names)
            if idx is None or idx < 0:
                return
            internal_type = types[idx][1]
        # Determine insert position (after current widget)
        current_wid = self._get_selected_widget_id()
        current_idx = (
            self.widget_ids.index(current_wid)
            if current_wid and current_wid in self.widget_ids
            else len(self.widget_ids) - 1
        )
        pos_after = None
        if current_wid:
            widget = self.cm.get_widget(current_wid)
            if widget:
                pos_after = widget["position"]
        widget_id = self.cm.add_widget(
            section_id=self.current_section_id,
            path=path,
            label=label,
            display_type=internal_type,
            target=target,
            stacked_type=internal_type,
        )
        if pos_after is not None:
            self.cm.reorder_widget(widget_id, pos_after + 1)
        self.changed = True
        # Insert in-place (no list reset = no flicker)
        friendly_type = _friendly(internal_type)
        li = xbmcgui.ListItem(label, friendly_type)
        li.setProperty("widget_id", str(widget_id))
        li.setProperty("widget_label", label)
        li.setProperty("display_type", friendly_type)
        li.setProperty("widget_path", path)
        li.setProperty("target", target)
        li.setProperty("is_stacked", "No")
        li.setProperty("stacked_type", "")
        li.setProperty("limit_num", "0")
        li.setProperty("sortby", "")
        li.setProperty("sortorder", "")
        insert_idx = current_idx + 1
        widget_list = self.getControl(WIDGET_LIST)
        widget_list.addItem(li)
        for i in range(len(self.widget_ids), insert_idx, -1):
            self._swap_widget_items(widget_list, i, i - 1)
        self.widget_ids.insert(insert_idx, widget_id)
        widget_list.selectItem(insert_idx)
        self._load_config()
        self.setFocusId(WIDGET_LIST)

    def _delete_widget(self):
        wid = self._get_selected_widget_id()
        if wid is None:
            return
        del_idx = self.widget_ids.index(wid) if wid in self.widget_ids else -1
        if del_idx < 0:
            return
        self.cm.remove_widget(wid)
        self.changed = True
        # Remove in-place (no list reset = no focus jump to sections)
        widget_list = self.getControl(WIDGET_LIST)
        widget_list.removeItem(del_idx)
        self.widget_ids.pop(del_idx)
        if self.widget_ids:
            focus_idx = min(del_idx, len(self.widget_ids) - 1)
            widget_list.selectItem(focus_idx)
        self._load_config()

    def _edit_widget_field(self, field, control_id):
        wid = self._get_selected_widget_id()
        if wid is None:
            return
        row = self.cm.get_widget(wid)
        if not row:
            return
        widget = dict(row)
        if field == "display_type":
            if widget["is_stacked"]:
                # Stacked widget: display_type is locked to CategoryStacked,
                # so change the child type (stacked_type) instead
                types = STACKED_DISPLAY_TYPES
                names = [t[0] for t in types]
                idx = self._select("Display Type", names)
                if idx is None or idx < 0:
                    return
                new_val = types[idx][1]
                self.cm.update_widget(wid, stacked_type=new_val)
                self.changed = True
                self._update_widget_item_in_place(wid)
                return
            types = _get_display_types_for_widget(widget)
            names = [t[0] for t in types]
            idx = self._select("Display Type", names)
            if idx is None or idx < 0:
                return
            new_val = types[idx][1]
            # Sync stacked_type so it's ready if user toggles stacked on later
            self.cm.update_widget(wid, stacked_type=new_val)
        elif field == "target":
            idx = self._select("Target", TARGET_TYPES)
            if idx is None or idx < 0:
                return
            new_val = TARGET_TYPES[idx]
        elif field == "is_stacked":
            current = widget["is_stacked"]
            new_val = 0 if current else 1
            if new_val:
                # Turning ON stacked
                stacked_type = widget["stacked_type"]
                if not stacked_type:
                    names = [t[0] for t in STACKED_DISPLAY_TYPES]
                    idx = self._select("Stacked Child Display Type", names)
                    if idx is None or idx < 0:
                        return
                    stacked_type = STACKED_DISPLAY_TYPES[idx][1]
                self.cm.update_widget(
                    wid,
                    is_stacked=1,
                    stacked_type=stacked_type,
                    display_type="WidgetListCategoryStacked",
                )
            else:
                # Turning OFF stacked — revert display_type to child type
                self.cm.update_widget(
                    wid,
                    is_stacked=0,
                    display_type=widget["stacked_type"] or widget["display_type"],
                )
            self.changed = True
            self._update_widget_item_in_place(wid)
            return
        elif field == "stacked_type":
            names = [t[0] for t in STACKED_DISPLAY_TYPES]
            idx = self._select("Stacked Child Display Type", names)
            if idx is None or idx < 0:
                return
            new_val = STACKED_DISPLAY_TYPES[idx][1]
        elif field == "limit_num":
            current = widget.get("limit_num", 0)
            new_val = xbmcgui.Dialog().numeric(0, "Limit (0 = no limit)", str(current))
            if new_val == "" or new_val is None:
                return
            try:
                new_val = int(new_val)
            except ValueError:
                return
        elif field == "sortby":
            idx = self._select("Sort By", SORT_BY_TYPES)
            if idx is None or idx < 0:
                return
            new_val = SORT_BY_TYPES[idx]
        elif field == "sortorder":
            idx = self._select("Sort Order", SORT_ORDER_TYPES)
            if idx is None or idx < 0:
                return
            new_val = SORT_ORDER_TYPES[idx]
        elif field == "path":
            result = path_browser.browse()
            if not result:
                return
            new_path = result["path"]
            new_target = result.get("target", widget.get("target", "videos"))
            default_label = result.get("label", widget.get("label", ""))
            new_label = self._input("Widget Label", default_label)
            if not new_label:
                new_label = default_label or widget.get("label", "")
            self.cm.update_widget(
                wid, path=new_path, label=new_label, target=new_target
            )
            self.changed = True
            self._update_widget_item_in_place(wid)
            return
        else:
            current = str(widget.get(field, ""))
            new_val = self._input(field.replace("_", " ").title(), current)
            if not new_val:
                return
        self.cm.update_widget(wid, **{field: new_val})
        self.changed = True
        self._update_widget_item_in_place(wid)

    def _update_widget_item_in_place(self, wid):
        """Update the ListItem properties in-place from DB without resetting the list."""
        row = self.cm.get_widget(wid)
        if not row:
            return
        widget = dict(row)
        if wid not in self.widget_ids:
            return
        idx = self.widget_ids.index(wid)
        widget_list = self.getControl(WIDGET_LIST)
        try:
            li = widget_list.getListItem(idx)
        except Exception:
            return
        self._set_widget_item_props(li, widget)
        # Reload config so subsequent edits see updated data
        self._load_config()

    # ── Reorder Mode ──

    _DETAIL_PROPS = (
        "widget_label",
        "display_type",
        "widget_path",
        "is_stacked",
        "target",
        "limit_num",
        "sortby",
        "sortorder",
    )

    def _freeze_detail_props(self):
        """Snapshot current widget's detail properties as window properties."""
        wid = self._get_selected_widget_id()
        if wid is None:
            return
        idx = self.widget_ids.index(wid)
        widget_list = self.getControl(WIDGET_LIST)
        li = widget_list.getListItem(idx)
        for prop in self._DETAIL_PROPS:
            self.setProperty("reorder_detail_%s" % prop, li.getProperty(prop))

    def _clear_detail_props(self):
        """Clear frozen detail properties."""
        for prop in self._DETAIL_PROPS:
            self.clearProperty("reorder_detail_%s" % prop)

    def _toggle_reorder(self, target, item_id=None):
        if self.reorder_mode and self.reorder_target == target:
            self.reorder_mode = False
            self.reorder_target = None
            self.reorder_item_id = None
            self.clearProperty("reorder_sections")
            self.clearProperty("reorder_widgets")
            self._clear_detail_props()
        else:
            self.reorder_mode = True
            self.reorder_target = target
            self.reorder_item_id = item_id
            if target == "section":
                self.setProperty("reorder_sections", "true")
                self.clearProperty("reorder_widgets")
                self.setFocusId(SECTION_LIST)
            elif target == "widget":
                self._freeze_detail_props()
                self.setProperty("reorder_widgets", "true")
                self.clearProperty("reorder_sections")
                self.setFocusId(WIDGET_LIST)

    def _handle_reorder_move(self, direction):
        item_id = self.reorder_item_id
        if item_id is None:
            return
        if self.reorder_target == "section":
            if item_id not in self.section_ids:
                return
            count = len(self.section_ids)
            if count < 2:
                return
            current_idx = self.section_ids.index(item_id)
            new_idx = (current_idx + direction) % count
            # Update DB — wrapping needs explicit target position
            if new_idx == count - 1 and current_idx == 0:
                self.cm.reorder_section(item_id, count)
            elif new_idx == 0 and current_idx == count - 1:
                self.cm.reorder_section(item_id, 1)
            else:
                current_pos = self.config[item_id]["section"]["position"]
                self.cm.reorder_section(item_id, current_pos + direction)
            self.changed = True
            self._load_config()
            # Refresh all section items from config
            section_list = self.getControl(SECTION_LIST)
            sorted_ids = sorted(
                self.config, key=lambda sid: self.config[sid]["section"]["position"]
            )
            for i, sid in enumerate(sorted_ids):
                section = self.config[sid]["section"]
                name = section["name"]
                hidden = section.get("visible") == "false"
                li = section_list.getListItem(i)
                li.setLabel(_dim_label(name) if hidden else name)
                li.setProperty("section_id", str(sid))
                li.setProperty("hidden", "true" if hidden else "")
            self.section_ids = sorted_ids
            section_list.selectItem(new_idx)
        elif self.reorder_target == "widget":
            if item_id not in self.widget_ids:
                return
            count = len(self.widget_ids)
            if count < 2:
                return
            current_idx = self.widget_ids.index(item_id)
            new_idx = (current_idx + direction) % count
            # Update DB — wrapping needs explicit target position
            widget = self.cm.get_widget(item_id)
            if not widget:
                return
            if new_idx == count - 1 and current_idx == 0:
                self.cm.reorder_widget(item_id, count)
            elif new_idx == 0 and current_idx == count - 1:
                self.cm.reorder_widget(item_id, 1)
            else:
                self.cm.reorder_widget(item_id, widget["position"] + direction)
            self.changed = True
            self._load_config()
            # Refresh all widget items from config
            section_data = self.config.get(self.current_section_id)
            widgets = section_data["widgets"] if section_data else []
            widget_list = self.getControl(WIDGET_LIST)
            for i, w in enumerate(widgets):
                self._set_widget_item_props(widget_list.getListItem(i), w)
            self.widget_ids = [w["id"] for w in widgets]
            widget_list.selectItem(new_idx)

    # ── Visibility Toggle ──

    def _toggle_section_visibility(self):
        sid = self._get_selected_section_id()
        if sid is None:
            return
        section = self.config[sid]["section"]
        currently_hidden = section.get("visible") == "false"
        new_visible = "" if currently_hidden else "false"
        if new_visible == "false":
            visible_count = sum(
                1 for s in self.config.values()
                if s["section"].get("visible") != "false"
            )
            if visible_count <= 1:
                xbmcgui.Dialog().notification(
                    "Altus", "At least one section must remain visible",
                    xbmcgui.NOTIFICATION_WARNING, 3000,
                )
                return
        self.cm.update_section(sid, visible=new_visible)
        self.changed = True
        self._load_config()
        # Update label in-place
        idx = self.section_ids.index(sid) if sid in self.section_ids else -1
        if idx >= 0:
            name = self.config[sid]["section"]["name"]
            li = self.getControl(SECTION_LIST).getListItem(idx)
            li.setLabel(_dim_label(name) if new_visible == "false" else name)
            li.setProperty("hidden", "true" if new_visible == "false" else "")

    def _toggle_widget_visibility(self):
        wid = self._get_selected_widget_id()
        if wid is None:
            return
        row = self.cm.get_widget(wid)
        if not row:
            return
        widget = dict(row)
        currently_hidden = widget.get("visible") == "false"
        new_visible = "" if currently_hidden else "false"
        self.cm.update_widget(wid, visible=new_visible)
        self.changed = True
        self._update_widget_item_in_place(wid)

    # ── Event Handlers ──

    def onFocus(self, control_id):
        # Redirect: detail panel left should go to widgets, not sections
        if control_id == SECTION_LIST and self.prev_focus_id in DETAIL_CONTROLS:
            self.setFocusId(WIDGET_LIST)
            self.prev_focus_id = WIDGET_LIST
            return
        self.prev_focus_id = control_id

    def onClick(self, control_id):
        if control_id == ADD_SECTION_BTN:
            self._add_section()
            if self.section_ids:
                self.setFocusId(SECTION_LIST)
                self._set_btn("section", 0)
            return

        if control_id == SECTION_LIST:
            if self.reorder_mode and self.reorder_target == "section":
                self.reorder_mode = False
                self.reorder_target = None
                self.reorder_item_id = None
                self.clearProperty("reorder_sections")
                return
            if self.section_btn_idx >= 0:
                self._activate_btn("section")

        elif control_id == ADD_WIDGET_BTN:
            self._add_widget()

        elif control_id == WIDGET_LIST:
            if self.reorder_mode and self.reorder_target == "widget":
                self.reorder_mode = False
                self.reorder_target = None
                self.reorder_item_id = None
                self.clearProperty("reorder_widgets")
                self._clear_detail_props()
                return
            if self.widget_btn_idx >= 0:
                self._activate_btn("widget")

        # Detail fields
        elif control_id == DETAIL_LABEL:
            self._edit_widget_field("label", control_id)
        elif control_id == DETAIL_DISPLAY_TYPE:
            self._edit_widget_field("display_type", control_id)
        elif control_id == DETAIL_PATH:
            self._edit_widget_field("path", control_id)
        elif control_id == DETAIL_STACKED:
            self._edit_widget_field("is_stacked", control_id)
        elif control_id == DETAIL_TARGET:
            self._edit_widget_field("target", control_id)
        elif control_id == DETAIL_LIMIT:
            self._edit_widget_field("limit_num", control_id)
        elif control_id == DETAIL_SORTBY:
            self._edit_widget_field("sortby", control_id)
        elif control_id == DETAIL_SORTORDER:
            self._edit_widget_field("sortorder", control_id)

    def onAction(self, action):
        action_id = action.getId()

        # Long press: toggle visibility
        if action_id == ACTION_CONTEXT_MENU:
            focus_id = self.getFocusId()
            if focus_id == SECTION_LIST:
                self._toggle_section_visibility()
                return
            elif focus_id == WIDGET_LIST:
                self._toggle_widget_visibility()
                return

        # Close dialog
        if action_id in (ACTION_PREVIOUS_MENU, ACTION_NAV_BACK):
            if self.reorder_mode:
                self.reorder_mode = False
                self.reorder_target = None
                self.reorder_item_id = None
                self.clearProperty("reorder_sections")
                self.clearProperty("reorder_widgets")
                self._clear_detail_props()
                return
            self._on_close()
            self.close()
            return

        focus_id = self.getFocusId()

        # Reorder mode: intercept up/down
        if self.reorder_mode:
            if action_id == ACTION_MOVE_UP:
                self._handle_reorder_move(-1)
                return
            elif action_id == ACTION_MOVE_DOWN:
                self._handle_reorder_move(1)
                return

        # Section list: inline button navigation
        if focus_id == SECTION_LIST and not self.reorder_mode:
            if action_id == ACTION_MOVE_RIGHT:
                if self.section_btn_idx < len(SECTION_BUTTONS) - 1:
                    self._set_btn("section", self.section_btn_idx + 1)
                    return
                else:
                    # Past last button → move to widget list
                    self._clear_btn("section")
                    if self.widget_ids:
                        self.setFocusId(WIDGET_LIST)
                    else:
                        self.setFocusId(ADD_WIDGET_BTN)
                    return
            elif action_id == ACTION_MOVE_LEFT:
                if self.section_btn_idx > 0:
                    self._set_btn("section", self.section_btn_idx - 1)
                    return
                else:
                    # At first button, leftmost panel → do nothing
                    return

        # Widget list: inline button navigation
        if focus_id == WIDGET_LIST and not self.reorder_mode:
            if action_id == ACTION_MOVE_RIGHT:
                if self.widget_btn_idx < len(WIDGET_BUTTONS) - 1:
                    self._set_btn("widget", self.widget_btn_idx + 1)
                    return
                else:
                    # Past last button → move to detail panel
                    self._clear_btn("widget")
                    self.setFocusId(DETAIL_GROUPLIST)
                    return
            elif action_id == ACTION_MOVE_LEFT:
                if self.widget_btn_idx > 0:
                    self._set_btn("widget", self.widget_btn_idx - 1)
                    return
                else:
                    # At first button → move to section list
                    self._clear_btn("widget")
                    self.setFocusId(SECTION_LIST)
                    return

    def _on_close(self):
        if self.monitor_thread:
            self.monitor_thread.stop()
        if self.cm:
            self.cm.close()
        if self.changed:
            generate_and_reload()

    # ── Helpers ──

    def _swap_section_items(self, section_list, idx_a, idx_b):
        """Swap labels and properties of two section list items."""
        a = section_list.getListItem(idx_a)
        b = section_list.getListItem(idx_b)
        label_a, label_b = a.getLabel(), b.getLabel()
        a.setLabel(label_b)
        b.setLabel(label_a)
        for prop in ("section_id", "hidden"):
            va, vb = a.getProperty(prop), b.getProperty(prop)
            a.setProperty(prop, vb)
            b.setProperty(prop, va)

    def _swap_widget_items(self, widget_list, idx_a, idx_b):
        """Swap labels and properties of two widget list items."""
        a = widget_list.getListItem(idx_a)
        b = widget_list.getListItem(idx_b)
        la, lb = a.getLabel(), b.getLabel()
        a.setLabel(lb)
        b.setLabel(la)
        l2a, l2b = a.getLabel2(), b.getLabel2()
        a.setLabel2(l2b)
        b.setLabel2(l2a)
        for prop in (
            "widget_id",
            "widget_label",
            "display_type",
            "widget_path",
            "target",
            "is_stacked",
            "stacked_type",
            "limit_num",
            "sortby",
            "sortorder",
            "hidden",
        ):
            va, vb = a.getProperty(prop), b.getProperty(prop)
            a.setProperty(prop, vb)
            b.setProperty(prop, va)

    def _input(self, heading, default=""):
        return xbmcgui.Dialog().input(heading, defaultt=default)

    def _confirm(self, message):
        return xbmcgui.Dialog().yesno("Widget Manager", message)

    def _select(self, heading, options):
        return xbmcgui.Dialog().select(heading, options)


def _ensure_config_exists():
    """Ensure widget config DB has sections — migrate or create defaults.

    Returns True if new config was created (XML generation needed on close).
    """
    from modules.widget_manager.config_manager import ConfigManager
    cm = ConfigManager()
    count = cm.dbcur.execute("SELECT COUNT(*) FROM sections").fetchone()[0]
    cm.close()
    if count > 0:
        return False
    from modules.widget_manager.migration import migrate
    if not migrate():
        from modules.widget_manager.default_config import create_default_sections
        create_default_sections()
    return True


def open_manager():
    config_created = _ensure_config_exists()
    window = WidgetManagerWindow(
        "DialogWidgetManager.xml",
        SKIN_PATH,
        "default",
        "1080i",
    )
    if config_created:
        window.changed = True
    window.doModal()
    del window
