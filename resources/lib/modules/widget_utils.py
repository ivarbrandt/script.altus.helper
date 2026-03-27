# -*- coding: utf-8 -*-
import xbmc, xbmcgui
from .helper import winprop

# from modules.logger import logger


def get_skin_variable(variable_name):
    return xbmc.getInfoLabel(f"$VAR[{variable_name}]")


def widget_monitor(list_id):
    if len(list_id) != 5:
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
    if window_id not in [10000, 11121]:
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
    label_prop = "altus.%s.label" % list_id
    is_updating_cond = "Container(%s).IsUpdating" % stack_id
    while not monitor.abortRequested():
        monitor.waitForAbort(0.1)
        if xbmcgui.getCurrentWindowId() not in [10000, 11121]:
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
            elif xbmcgui.getCurrentWindowId() not in [10000, 11121]:
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
            window.setProperty(label_prop, xbmc.getInfoLabel("ListItem.Label"))
            window.setProperty(path_prop, cpath_path)
            update_wait_time = 0
            while (
                xbmc.getCondVisibility(is_updating_cond)
                and update_wait_time < 3
            ):
                monitor.waitForAbort(0.05)
                update_wait_time += 0.05
            try:
                stack_control.selectItem(0)
            except:
                pass
        else:
            monitor.waitForAbort(0.1)
