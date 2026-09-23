# -*- coding: utf-8 -*-
import time
import xbmc, xbmcaddon, xbmcgui
from .helper import winprop

# from modules.logger import logger


ADDONBROWSER_WINDOW_ID = 10040
ADDONBROWSER_CRUMBS = 3
ADDONBROWSER_MAX_ITEMS = 200
ADDONBROWSER_TICK = 0.3
ADDONBROWSER_MENU_TICK = 0.2

_addonbrowser_names = {}
_addonbrowser_children = {}


def get_skin_variable(variable_name):
    return xbmc.getInfoLabel(f"$VAR[{variable_name}]")


def widget_monitor(list_id):
    if len(list_id) != 4:
        return
    monitor = xbmc.Monitor()
    try:
        delay = (
            float(xbmc.getInfoLabel("Skin.String(altus_category_widget_delay)")) / 1000
        )
    except:
        delay = 0.75
    display_delay = (
        xbmc.getInfoLabel("Skin.HasSetting(altus_category_widget_display_delay)")
        == "True"
    )
    label_color = get_skin_variable("FocusColorTheme")
    stack_id = list_id + "1"
    window_id = xbmcgui.getCurrentWindowId()
    if window_id != 11121:
        return
    window = xbmcgui.Window(window_id)
    home_window = xbmcgui.Window(10000)
    try:
        stack_control = window.getControl(int(stack_id))
    except:
        return
    try:
        countdown_label = window.getControl(int(list_id + "999"))
    except:
        return
    path_prop = "altus.%s.path" % list_id
    is_updating_cond = "Container(%s).IsUpdating" % stack_id
    while not monitor.abortRequested():
        monitor.waitForAbort(0.1)
        if xbmcgui.getCurrentWindowId() != 11121:
            break
        if list_id != str(window.getFocusId()):
            break
        last_path = window.getProperty(path_prop)
        cpath_path = xbmc.getInfoLabel("ListItem.FolderPath")
        if last_path == cpath_path or xbmc.getCondVisibility(
            "System.HasActiveModalDialog"
        ):
            continue
        switch_widget = True
        countdown = delay
        while not monitor.abortRequested() and countdown >= 0 and switch_widget:
            monitor.waitForAbort(0.1)
            countdown -= 0.1
            if list_id != str(window.getFocusId()):
                switch_widget = False
            elif xbmc.getInfoLabel("ListItem.FolderPath") != cpath_path:
                switch_widget = False
            elif xbmc.getCondVisibility("System.HasActiveModalDialog"):
                switch_widget = False
            elif xbmcgui.getCurrentWindowId() != 11121:
                switch_widget = False
            if switch_widget and display_delay:
                home_window.setProperty("altus.countdown_active", "true")
                try:
                    countdown_label.setLabel(
                        "Loading [COLOR {}][B]{{}}[/B][/COLOR] in [B]%0.2f[/B] seconds".format(
                            label_color
                        ).format(
                            xbmc.getInfoLabel("ListItem.Label")
                        )
                        % max(countdown, 0)
                    )
                except:
                    pass
        home_window.clearProperty("altus.countdown_active")
        if switch_widget:
            new_label = xbmc.getInfoLabel("ListItem.Label")
            # Route stacked-child path/label to Window(home) under a distinct
            # prefix (altus.search.child.<id>.*) to avoid the Window(11121)
            # cross-thread crash and to keep clear of home wall IDs that share
            # the same numeric range.
            home_window.setProperty(
                "altus.search.child.%s.label" % list_id, new_label
            )
            home_window.setProperty(
                "altus.search.child.%s.path" % list_id, cpath_path
            )
            start_wait = 0
            while not xbmc.getCondVisibility(is_updating_cond) and start_wait < 1:
                monitor.waitForAbort(0.05)
                start_wait += 0.05
            update_wait_time = 0
            while xbmc.getCondVisibility(is_updating_cond) and update_wait_time < 3:
                monitor.waitForAbort(0.05)
                update_wait_time += 0.05
            try:
                stack_control.selectItem(0)
            except:
                pass
        else:
            monitor.waitForAbort(0.1)


def _addonbrowser_folder(path):
    return path if path.endswith("/") else path + "/"


def _addonbrowser_cache_listing(folder):
    """Remember the name and the whereabouts of every folder on screen.

    Nothing in an addons:// path is a name - the segments are add-on ids and
    content-type ids - and Files.GetDirectory refuses these paths outright, so
    the names are taken while we stand in the listing: the folder you are about
    to enter is named by the item you enter it from, in the user's language and
    with no id map for this skin to maintain.

    Which items were here is kept too, because Kodi's child paths don't nest
    under their parent - entering Look and feel then Skin gives two siblings,
    addons://user/category.lookandfeel and addons://user/xbmc.gui.skin - so
    belonging to the listing we just left is the only sign of a step inwards.
    """
    try:
        count = int(xbmc.getInfoLabel("Container.NumItems") or 0)
    except ValueError:
        return
    children = set()
    for index in range(min(count, ADDONBROWSER_MAX_ITEMS)):
        path = xbmc.getInfoLabel(f"Container.ListItemAbsolute({index}).FolderPath")
        label = xbmc.getInfoLabel(f"Container.ListItemAbsolute({index}).Label")
        if not path or label == "..":
            continue
        child = _addonbrowser_folder(path)
        children.add(child)
        if label:
            _addonbrowser_names.setdefault(child, label)
    _addonbrowser_children[_addonbrowser_folder(folder)] = children


def _addonbrowser_trail(trail, folder):
    """Follow the walk: a step in, a step back, or somewhere else entirely."""
    if folder in trail:
        return trail[: trail.index(folder) + 1]
    if trail and folder in _addonbrowser_children.get(trail[-1], ()):
        return trail + [folder]
    return [folder]


def _addonbrowser_is_root(folder, root):
    """The header says "root" for the root itself, and the menu names which one.

    Only the root the window was sent to is spoken for: drilling into My add-ons
    from the addons:// listing leaves the menu sitting on Add-ons, so that step
    has to be named by the header.
    """
    return folder == root or not folder[len("addons://") :].strip("/")


def _addonbrowser_name(folder, segment):
    name = _addonbrowser_names.get(folder)
    if name:
        return name
    try:
        name = xbmcaddon.Addon(segment).getAddonInfo("name")
    except Exception:
        name = segment
    _addonbrowser_names[folder] = name
    return name


def _addonbrowser_crumbs(trail, root):
    """Name every step of the walk below the root, the header says that part."""
    names = []
    for folder in trail:
        if not folder.startswith("addons://") or _addonbrowser_is_root(folder, root):
            continue
        names.append(_addonbrowser_name(folder, folder.strip("/").split("/")[-1]))
    return names[-ADDONBROWSER_CRUMBS:]


def _addonbrowser_write_crumbs(window, trail):
    """Name the walk in one go.

    The header holds whatever was written last, so nothing here may describe a
    path we are only part-way into: the crumbs change once, when the new walk
    is known, the way the launcher's panels hold the parent until the child is
    ready.
    """
    root = xbmc.getInfoLabel(f"Window({ADDONBROWSER_WINDOW_ID}).Property(root_path)")
    names = _addonbrowser_crumbs(trail, _addonbrowser_folder(root) if root else "")
    for index in range(ADDONBROWSER_CRUMBS):
        window.setProperty(
            "crumb%d" % (index + 1), names[index] if index < len(names) else ""
        )


def _addonbrowser_claim(window, key):
    """Claim the window for this run, and hand back how to tell it was taken.

    A skin reload re-opens this window instantly, so a run that waits for the
    window to go away stays alive beside the run that replaces it, both writing
    the same properties. Newest claim wins.
    """
    token = str(time.time())
    window.setProperty(key, token)
    return token, f"Window({ADDONBROWSER_WINDOW_ID}).Property({key})"


def addonbrowser_crumb_monitor():
    """Name the walk for the path header, for as long as the window is open.

    Nothing in an addons:// path is a name, and Kodi drops the category from a
    child path, so the walk is followed rather than parsed: each listing is read
    while we stand in it, and what was in it tells a step inwards from a step
    back. Anything unrecognised starts the trail over, so a bad guess can only
    shorten the header, never misdirect it.

    Kodi answers for the *active* window, so a dialog on top pauses the work
    instead of ending it.
    """
    monitor = xbmc.Monitor()
    window = xbmcgui.Window(ADDONBROWSER_WINDOW_ID)
    token, token_info = _addonbrowser_claim(window, "crumb_monitor")
    last_folder = ""
    last_listing = ()
    trail = []
    _addonbrowser_write_crumbs(window, trail)
    while not monitor.abortRequested():
        if monitor.waitForAbort(ADDONBROWSER_TICK):
            break
        if xbmc.getInfoLabel(token_info) != token:
            break
        if not xbmc.getCondVisibility("Window.IsActive(addonbrowser)"):
            break
        if xbmcgui.getCurrentWindowId() != ADDONBROWSER_WINDOW_ID:
            continue
        path = xbmc.getInfoLabel("Container.FolderPath")
        folder = _addonbrowser_folder(path) if path else ""
        if not folder:
            continue
        listing = (folder, xbmc.getInfoLabel("Container.NumItems"))
        if folder != last_folder:
            last_folder = folder
            trail = _addonbrowser_trail(trail, folder)
        if listing != last_listing:
            last_listing = listing
            _addonbrowser_cache_listing(folder)
            _addonbrowser_write_crumbs(window, trail)


def addonbrowser_menu_monitor(menu_id):
    """Load the highlighted root once the selection has settled.

    Runs while the roots menu holds focus: each move restarts the countdown, and
    a selection that stays put swaps the window's listing to that root. The root
    the window is already inside is left alone, so stepping out to the menu and
    back keeps the place you were at.

    A load leaves no control focused for a moment, so the run ends only when
    another control takes focus or the window changes; treating "nothing is
    focused" as an exit killed the monitor after the first few loads.
    """
    monitor = xbmc.Monitor()
    try:
        delay = float(xbmc.getInfoLabel("Skin.String(altus_addonbrowser_menu_delay)"))
    except (ValueError, TypeError):
        delay = 400
    delay_seconds = delay / 1000
    window = xbmcgui.Window(ADDONBROWSER_WINDOW_ID)
    token, token_info = _addonbrowser_claim(window, "menu_monitor")
    path_info = f"Container({menu_id}).ListItem.Property(path)"
    root_info = f"Window({ADDONBROWSER_WINDOW_ID}).Property(root_path)"
    last_path = xbmc.getInfoLabel(path_info)
    countdown = delay_seconds
    while not monitor.abortRequested():
        if monitor.waitForAbort(ADDONBROWSER_MENU_TICK):
            break
        if xbmc.getInfoLabel(token_info) != token:
            break
        focus_id = xbmc.getInfoLabel("System.CurrentControlID")
        if xbmcgui.getCurrentWindowId() != ADDONBROWSER_WINDOW_ID or (
            focus_id and focus_id != menu_id
        ):
            break
        if not focus_id:
            continue
        current_path = xbmc.getInfoLabel(path_info)
        if current_path != last_path:
            last_path = current_path
            countdown = delay_seconds
            continue
        if not current_path or current_path in (
            xbmc.getInfoLabel("Container.FolderPath"),
            xbmc.getInfoLabel(root_info),
        ):
            continue
        countdown -= ADDONBROWSER_MENU_TICK
        if countdown > 0:
            continue
        countdown = delay_seconds
        xbmc.executebuiltin(f"SetProperty(root_path,{current_path},AddonBrowser)")
        xbmc.executebuiltin(f"Container.Update({current_path},replace)")


def season_monitor(container_id):
    monitor = xbmc.Monitor()
    window_id = xbmcgui.getCurrentWindowId()
    if window_id != 10025:
        return
    window = xbmcgui.Window(window_id)
    path_prop = "altus.season.path"
    path_info = "Container(%s).ListItem.FolderPath" % container_id
    delay = 0.5
    current_path = window.getProperty(path_prop)
    initial = current_path == ""
    while not monitor.abortRequested():
        monitor.waitForAbort(0.1)
        if xbmcgui.getCurrentWindowId() != window_id:
            break
        if str(window.getFocusId()) != container_id:
            break
        cpath = xbmc.getInfoLabel(path_info)
        if not cpath or cpath == window.getProperty(path_prop):
            continue
        if xbmc.getCondVisibility("System.HasActiveModalDialog"):
            continue
        if initial:
            window.setProperty(path_prop, cpath)
            _cache_unwatched_index(window, container_id)
            initial = False
            continue
        switch = True
        countdown = delay
        while not monitor.abortRequested() and countdown >= 0 and switch:
            monitor.waitForAbort(0.1)
            countdown -= 0.1
            if str(window.getFocusId()) != container_id:
                switch = False
            elif xbmc.getInfoLabel(path_info) != cpath:
                switch = False
            elif xbmc.getCondVisibility("System.HasActiveModalDialog"):
                switch = False
            elif xbmcgui.getCurrentWindowId() != window_id:
                switch = False
        if switch:
            window.setProperty(path_prop, cpath)
            _cache_unwatched_index(window, container_id)


def _cache_unwatched_index(window, container_id):
    prop = "altus.season.unwatched_index"
    if not xbmc.getCondVisibility("Skin.HasSetting(Enable.57FocusUnwatched)"):
        window.setProperty(prop, "0")
        return
    watched = xbmc.getInfoLabel(
        "Container(%s).ListItem.Property(WatchedEpisodes)" % container_id
    )
    unwatched = xbmc.getInfoLabel(
        "Container(%s).ListItem.Property(UnwatchedEpisodes)" % container_id
    )
    is_partial = watched and watched != "0" and unwatched and unwatched != "0"
    if not is_partial:
        window.setProperty(prop, "0")
        return
    window.setProperty(prop, watched)
