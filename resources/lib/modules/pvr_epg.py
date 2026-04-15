# -*- coding: utf-8 -*-
import json
import time
from datetime import datetime, timezone
from urllib.parse import quote_plus, unquote_plus

import xbmc
import xbmcgui
import xbmcplugin


def _log(msg, level=xbmc.LOGINFO):
    xbmc.log("[script.altus.helper pvr_epg] %s" % msg, level=level)


def json_rpc(method, **params):
    payload = {"jsonrpc": "2.0", "method": method, "id": 1}
    if params:
        payload["params"] = params
    try:
        raw = xbmc.executeJSONRPC(json.dumps(payload))
        parsed = json.loads(raw)
    except Exception as e:
        _log("json_rpc error (%s): %s" % (method, e), xbmc.LOGERROR)
        return None
    if "error" in parsed:
        _log("json_rpc %s returned error: %s" % (method, parsed["error"]), xbmc.LOGWARNING)
        return None
    return parsed.get("result")


_channel_cache = {}

EPG_CHANNEL_PROP = "altus.pvr.epg_channel"
EPG_READY_PROP = "altus.pvr.epg_ready"
EPG_BUILT_PROP = "altus.pvr.epg_built_channel"


def _set_ready(window, name):
    settled = window.getProperty(EPG_CHANNEL_PROP)
    built = window.getProperty(EPG_BUILT_PROP)
    ready = bool(name) and name == settled and name == built
    window.setProperty(EPG_READY_PROP, "true" if ready else "false")


def channel_focus_debounce(container_id):
    import xbmcgui
    monitor = xbmc.Monitor()
    window_id = xbmcgui.getCurrentWindowId()
    window = xbmcgui.Window(window_id)
    info_label = "Container(%s).ListItem.ChannelName" % container_id
    delay = 0.5
    current_name = window.getProperty(EPG_CHANNEL_PROP)
    initial = current_name == ""

    while not monitor.abortRequested():
        monitor.waitForAbort(0.1)
        if xbmcgui.getCurrentWindowId() != window_id:
            break
        if str(window.getFocusId()) != str(container_id):
            break
        name = xbmc.getInfoLabel(info_label)
        _set_ready(window, name)
        if not name or name == window.getProperty(EPG_CHANNEL_PROP):
            continue
        if xbmc.getCondVisibility("System.HasActiveModalDialog"):
            continue
        if initial:
            window.setProperty(EPG_READY_PROP, "false")
            window.setProperty(EPG_CHANNEL_PROP, name)
            initial = False
            continue
        stable = True
        countdown = delay
        while not monitor.abortRequested() and countdown >= 0 and stable:
            monitor.waitForAbort(0.1)
            countdown -= 0.1
            if str(window.getFocusId()) != str(container_id):
                stable = False
            elif xbmc.getInfoLabel(info_label) != name:
                stable = False
            elif xbmc.getCondVisibility("System.HasActiveModalDialog"):
                stable = False
            elif xbmcgui.getCurrentWindowId() != window_id:
                stable = False
        if stable:
            window.setProperty(EPG_READY_PROP, "false")
            window.setProperty(EPG_CHANNEL_PROP, name)


def _get_channel_map():
    if _channel_cache:
        return _channel_cache
    result = json_rpc("PVR.GetChannels", channelgroupid="alltv")
    if not result:
        _log("PVR.GetChannels returned nothing", xbmc.LOGWARNING)
        return _channel_cache
    channels = result.get("channels", []) or []
    for ch in channels:
        label = ch.get("label")
        cid = ch.get("channelid")
        if label and cid is not None and label not in _channel_cache:
            _channel_cache[label] = cid
    _log("loaded %d channels into map" % len(_channel_cache))
    return _channel_cache


def _get_day_window():
    past = json_rpc("Settings.GetSettingValue", setting="epg.pastdaystodisplay") or {}
    future = json_rpc("Settings.GetSettingValue", setting="epg.futuredaystodisplay") or {}
    try:
        past_days = int(past.get("value", 1))
    except (TypeError, ValueError):
        past_days = 1
    try:
        future_days = int(future.get("value", 7))
    except (TypeError, ValueError):
        future_days = 7
    return past_days, future_days


_time_fmt_cache = None


def _is_12h_clock():
    global _time_fmt_cache
    if _time_fmt_cache is not None:
        return _time_fmt_cache
    region_time = xbmc.getRegion("time") or ""
    region_meridiem = xbmc.getRegion("meridiem") or ""
    is_12h = ("h" in region_time) or bool(region_meridiem.strip())
    _log("region time=%r meridiem=%r is_12h=%s" % (region_time, region_meridiem, is_12h))
    _time_fmt_cache = is_12h
    return is_12h


def _format_time(dt):
    if _is_12h_clock():
        meridiem = "AM" if dt.hour < 12 else "PM"
        h12 = dt.hour % 12 or 12
        return "%d:%02d %s" % (h12, dt.minute, meridiem)
    return "%02d:%02d" % (dt.hour, dt.minute)


def _parse_kodi_datetime(value):
    if not value:
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S"):
        try:
            dt_utc = datetime.strptime(value, fmt).replace(tzinfo=timezone.utc)
            return dt_utc.astimezone().replace(tzinfo=None)
        except ValueError:
            continue
    return None


def _finish_empty(handle, reason=""):
    if reason:
        _log("empty directory: %s" % reason)
    xbmcplugin.endOfDirectory(handle, succeeded=True, cacheToDisc=False)


def build_channel_epg(handle, channelname):
    channelname = unquote_plus(channelname or "").strip()
    _log("build_channel_epg handle=%s channelname=%r" % (handle, channelname))

    if not channelname:
        return _finish_empty(handle, "no channelname param")

    channels = _get_channel_map()
    channelid = channels.get(channelname)
    if channelid is None:
        return _finish_empty(handle, "channel not found: %r" % channelname)

    past_days, future_days = _get_day_window()
    _log("day window: -%d / +%d" % (past_days, future_days))

    now_ts = time.mktime(datetime.now().timetuple())
    min_start = now_ts - past_days * 86400
    max_start = now_ts + future_days * 86400

    result = json_rpc(
        "PVR.GetBroadcasts",
        channelid=channelid,
        properties=[
            "title", "plot", "plotoutline", "starttime", "endtime",
            "runtime", "progress", "progresspercentage", "genre",
            "episodename", "episodenum", "seasonnum", "thumbnail",
            "hastimer", "isactive", "wasactive",
        ],
    ) or {}

    broadcasts = result.get("broadcasts", []) or []
    _log("broadcasts returned: %d for channelid=%s" % (len(broadcasts), channelid))

    from modules import pvr_reminders
    reminded_ids = pvr_reminders.ids()

    items = []
    current_idx = -1
    for idx, b in enumerate(broadcasts):
        start_dt = _parse_kodi_datetime(b.get("starttime"))
        if start_dt is None:
            continue
        start_ts = time.mktime(start_dt.timetuple())
        if start_ts < min_start or start_ts > max_start:
            continue

        title = b.get("title") or ""
        plot = b.get("plot") or b.get("plotoutline") or ""
        runtime = b.get("runtime") or 0
        genre = b.get("genre") or []
        if isinstance(genre, list):
            genre = ", ".join(genre)
        thumbnail = b.get("thumbnail") or ""
        isactive = bool(b.get("isactive"))
        progress_pct = b.get("progresspercentage") or 0
        broadcastid = b.get("broadcastid")
        has_timer = bool(b.get("hastimer"))
        end_dt = _parse_kodi_datetime(b.get("endtime")) or start_dt

        start_str = _format_time(start_dt)
        end_str = _format_time(end_dt)

        li = xbmcgui.ListItem(label=title)
        li.setLabel2(start_str)
        if thumbnail:
            li.setArt({"thumb": thumbnail, "icon": thumbnail})
        li.setProperty("StartTime", start_str)
        li.setProperty("StartDate", start_dt.strftime("%Y-%m-%d"))
        li.setProperty("EndTime", end_str)
        li.setProperty("Duration", str(runtime))
        li.setProperty("Progress", str(int(progress_pct)) if isactive else "0")
        li.setProperty("IsCurrent", "true" if isactive else "false")
        li.setProperty("ChannelName", channelname)
        li.setProperty("Plot", plot)
        li.setProperty("Genre", genre)
        li.setProperty("ChannelId", str(channelid))
        has_reminder = broadcastid is not None and broadcastid in reminded_ids
        if broadcastid is not None:
            li.setProperty("BroadcastId", str(broadcastid))
        if has_reminder:
            li.setProperty("HasReminder", "true")
        if has_timer:
            li.setProperty("HasTimer", "true")

        ctx = [
            ("$LOCALIZE[19000]",
             "RunScript(script.altus.helper,mode=pvr_action&act=switch_channel&channelid=%d)" % channelid),
            ("Jump to now",
             "RunScript(script.altus.helper,mode=pvr_action&act=jump_to_now)"),
            ("$LOCALIZE[19003]",
             "RunScript(script.altus.helper,mode=pvr_action&act=find_similar&broadcastid=%s)" % (broadcastid if broadcastid is not None else "")),
            ("EPG Search",
             "RunScript(script.altus.helper,mode=pvr_action&act=epg_search)"),
        ]
        if broadcastid is not None:
            if has_timer:
                ctx.append((
                    "$LOCALIZE[21450]",
                    "RunScript(script.altus.helper,mode=pvr_action&act=edit_timer&broadcastid=%d)" % broadcastid,
                ))
                ctx.append((
                    "$LOCALIZE[19060]",
                    "RunScript(script.altus.helper,mode=pvr_action&act=delete_timer&broadcastid=%d)" % broadcastid,
                ))
            else:
                ctx.append((
                    "$LOCALIZE[19061]",
                    "RunScript(script.altus.helper,mode=pvr_action&act=add_timer&broadcastid=%d)" % broadcastid,
                ))
                ctx.append((
                    "Record series",
                    "RunScript(script.altus.helper,mode=pvr_action&act=add_series_timer&broadcastid=%d)" % broadcastid,
                ))
        is_future = start_ts > now_ts
        if is_future and broadcastid is not None:
            if has_reminder:
                ctx.append((
                    "Edit reminder",
                    "RunScript(script.altus.helper,mode=pvr_action&act=edit_reminder&broadcastid=%d)" % broadcastid,
                ))
                ctx.append((
                    "Delete reminder",
                    "RunScript(script.altus.helper,mode=pvr_action&act=delete_reminder&broadcastid=%d)" % broadcastid,
                ))
            else:
                ctx.append((
                    "$LOCALIZE[826]",
                    "RunScript(script.altus.helper,mode=pvr_action&act=set_reminder&broadcastid=%d&channelid=%d&start_ts=%d&title=%s)"
                    % (broadcastid, channelid, int(start_ts), quote_plus(title)),
                ))
        li.addContextMenuItems(ctx, replaceItems=True)

        if isactive:
            current_idx = len(items)

        url = "plugin://script.altus.helper/?action=switch_channel&channelid=%d" % channelid
        items.append((url, li, False))

    try:
        win = xbmcgui.Window(xbmcgui.getCurrentWindowId())
        win.setProperty("altus.pvr.epg_current_index", str(current_idx) if current_idx >= 0 else "0")
        win.setProperty(EPG_BUILT_PROP, channelname)
    except Exception as e:
        _log("failed to set current_index: %s" % e, xbmc.LOGWARNING)

    if items:
        xbmcplugin.addDirectoryItems(handle, items, len(items))
    _log("added %d items, current_idx=%d" % (len(items), current_idx))
    xbmcplugin.endOfDirectory(handle, succeeded=True, cacheToDisc=False)
