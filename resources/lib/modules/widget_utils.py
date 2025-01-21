# -*- coding: utf-8 -*-
import xbmc, xbmcgui

# from modules.logger import logger


def get_skin_variable(variable_name):
    return xbmc.getInfoLabel(f"$VAR[{variable_name}]")


def widget_monitor(list_id):
    if len(list_id) != 5:
        return
    monitor = xbmc.Monitor()
    window = None
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
    stack_id = list_id + "1"
    # poster_toggle, landscape_toggle = True, False
    while not monitor.abortRequested():
        window_id = xbmcgui.getCurrentWindowId()
        if window_id not in [10000, 11121]:
            break
        else:
            window = xbmcgui.Window(window_id)
            home_window = xbmcgui.Window(10000)
            stack_control = window.getControl(int(stack_id))
            stack_label_control = (
                window.getControl(int(stack_id + "666"))
                or window.getControl(int(stack_id + "667"))
                or window.getControl(int(stack_id + "668"))
                or window.getControl(int(stack_id + "669"))
                or window.getControl(int(stack_id + "670"))
                or window.getControl(int(stack_id + "671"))
                or window.getControl(int(stack_id + "672"))
                or window.getControl(int(stack_id + "673"))
                or window.getControl(int(stack_id + "674"))
            )
            try:
                countdown_label = window.getControl(int(list_id + "999"))
            except:
                break
        monitor.waitForAbort(0.25)
        if list_id != str(window.getFocusId()):
            break
        last_path = window.getProperty("altus.%s.path" % list_id)
        cpath_path = xbmc.getInfoLabel("ListItem.FolderPath")
        if last_path == cpath_path or xbmc.getCondVisibility(
            "System.HasActiveModalDialog"
        ):
            continue
        switch_widget = True
        countdown = delay
        while not monitor.abortRequested() and countdown >= 0 and switch_widget:
            monitor.waitForAbort(0.25)
            countdown -= 0.25
            if list_id != str(window.getFocusId()):
                switch_widget = False
            if last_path == cpath_path:
                switch_widget = False
            if xbmc.getInfoLabel("ListItem.FolderPath") != cpath_path:
                switch_widget = False
            if xbmc.getCondVisibility("System.HasActiveModalDialog"):
                switch_widget = False
            if xbmcgui.getCurrentWindowId() not in [10000, 11121]:
                switch_widget = False
            widget_label = xbmc.getInfoLabel("ListItem.Label")
            label_color = get_skin_variable("FocusColorTheme")
            if display_delay:
                home_window.setProperty("altus.countdown_active", "true")
                try:
                    countdown_label.setLabel(
                        "Loading [COLOR {}][B]{{}}[/B][/COLOR] in [B]%0.2f[/B] seconds".format(
                            label_color
                        ).format(
                            widget_label
                        )
                        % (countdown)
                    )
                except:
                    pass
        home_window.clearProperty("altus.countdown_active")
        if switch_widget:
            # position = int(xbmc.getInfoLabel("Container(%s).Position" % list_id))
            cpath_label = xbmc.getInfoLabel("ListItem.Label")
            stack_label_control.setLabel(cpath_label)
            window.setProperty("altus.%s.label" % list_id, cpath_label)
            window.setProperty("altus.%s.path" % list_id, cpath_path)
            monitor.waitForAbort(0.2)
            update_wait_time = 0
            while (
                xbmc.getCondVisibility("Container(%s).IsUpdating" % stack_id)
                and not update_wait_time > 3
            ):
                monitor.waitForAbort(0.10)
                update_wait_time += 0.10
            monitor.waitForAbort(0.50)
            try:
                stack_control.selectItem(0)
            except:
                pass
        else:
            stack_label_control.setLabel(window.getProperty("altus.%s.label" % list_id))
            monitor.waitForAbort(0.25)
    try:
        del monitor
    except:
        pass
    try:
        del window
        del home_window
    except:
        pass


def widget_info_timer(list_id):
    monitor = xbmc.Monitor()
    window = xbmcgui.Window(xbmcgui.getCurrentWindowId())
    try:
        delay = float(xbmc.getInfoLabel("Skin.String(altus_widget_autoinfo_delay)"))
    except (ValueError, TypeError):
        delay = 750
    delay_seconds = delay / 1000
    last_item = xbmc.getInfoLabel(f"Container({list_id}).ListItem.Label")
    countdown = delay_seconds
    while not monitor.abortRequested():
        if monitor.waitForAbort(0.25):
            break
        if not xbmc.getCondVisibility(f"Control.HasFocus({list_id})"):
            break
        current_item = xbmc.getInfoLabel(f"Container({list_id}).ListItem.Label")
        if current_item != last_item:
            last_item = current_item
            countdown = delay_seconds
            continue
        countdown -= 0.25
        if countdown <= 0:
            window.setProperty(f"WidgetInfo.Timer.Complete.{list_id}", "true")


def spotlight_timer(list_id):
    monitor = xbmc.Monitor()
    try:
        delay = float(xbmc.getInfoLabel("Skin.String(altus_spotlight_delay)"))
    except (ValueError, TypeError):
        delay = 10
    last_item = xbmc.getInfoLabel(f"Container({list_id}).ListItem.Label")
    countdown = delay
    while not monitor.abortRequested():
        if monitor.waitForAbort(0.25):
            break
        if not xbmc.getCondVisibility(f"Control.HasFocus({list_id})"):
            break
        current_item = xbmc.getInfoLabel(f"Container({list_id}).ListItem.Label")
        if current_item != last_item:
            last_item = current_item
            countdown = delay
            continue
        countdown -= 0.25
        if countdown <= 0:
            xbmc.executebuiltin('Action(right)')

