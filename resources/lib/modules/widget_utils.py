# -*- coding: utf-8 -*-
import xbmc, xbmcgui
from .helper import winprop

# from modules.logger import logger


ADDONBROWSER_WINDOW_ID = 10040


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


def addonbrowser_menu_monitor(menu_id):
    """Load the highlighted root once the selection has settled.

    Runs while the add-on browser's roots menu holds focus: each move restarts
    the countdown, and a selection that stays put swaps the window's listing to
    that root. The root the window is already inside is left alone, so stepping
    out to the menu and back keeps the place you were at.

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
    path_info = f"Container({menu_id}).ListItem.Property(path)"
    root_info = f"Window({ADDONBROWSER_WINDOW_ID}).Property(root_path)"
    last_path = xbmc.getInfoLabel(path_info)
    countdown = delay_seconds
    while not monitor.abortRequested():
        if monitor.waitForAbort(0.25):
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
        countdown -= 0.25
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
