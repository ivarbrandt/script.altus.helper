# -*- coding: utf-8 -*-
import json
import time
from datetime import datetime, timezone

import xbmc
import xbmcgui


def _log(msg, level=xbmc.LOGINFO):
    xbmc.log("[script.altus.helper pvr_actions] %s" % msg, level=level)


def _json_rpc(method, **params):
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
        _log("json_rpc %s error: %s" % (method, parsed["error"]), xbmc.LOGWARNING)
        return None
    return parsed.get("result")


def _parse_utc(value):
    if not value:
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S"):
        try:
            dt = datetime.strptime(value, fmt).replace(tzinfo=timezone.utc)
            return dt.astimezone().replace(tzinfo=None)
        except ValueError:
            continue
    return None


def _refresh_epg_container():
    xbmc.executebuiltin("Container(52).Refresh")


def _get_broadcast(broadcastid):
    res = _json_rpc(
        "PVR.GetBroadcastDetails",
        broadcastid=int(broadcastid),
        properties=[
            "title", "plot", "plotoutline", "starttime", "endtime",
            "runtime", "genre", "episodename", "episodenum", "seasonnum",
            "thumbnail", "hastimer", "isactive",
        ],
    )
    if not res:
        return None
    return res.get("broadcastdetails")


def switch_channel(params):
    channelid = params.get("channelid")
    if not channelid:
        return
    res = _json_rpc("Player.Open", item={"channelid": int(channelid)})
    if res is None:
        xbmcgui.Dialog().notification("Altus", "Failed to switch channel", xbmcgui.NOTIFICATION_ERROR, 2500)


def jump_to_now(params):
    win = xbmcgui.Window(xbmcgui.getCurrentWindowId())
    idx = win.getProperty("altus.pvr.epg_current_index") or "0"
    xbmc.executebuiltin("SetFocus(52,%s,absolute)" % idx)


def find_similar(params):
    xbmcgui.Dialog().notification("Altus", "Searching EPG for similar entries...", xbmcgui.NOTIFICATION_INFO, 2000)
    broadcastid = params.get("broadcastid")
    if not broadcastid:
        return
    b = _get_broadcast(broadcastid)
    if not b:
        return
    title = (b.get("title") or "").strip()
    if not title:
        xbmcgui.Dialog().notification("Altus", "No title to search", xbmcgui.NOTIFICATION_WARNING, 2000)
        return

    group_label = xbmc.getInfoLabel("Container(49).ListItem.Label") or ""
    group_id = "alltv"
    if group_label:
        groups_res = _json_rpc("PVR.GetChannelGroups", channeltype="tv") or {}
        for g in groups_res.get("channelgroups", []) or []:
            if (g.get("label") or "") == group_label:
                gid = g.get("channelgroupid")
                if isinstance(gid, int):
                    group_id = gid
                break
    _log("find_similar using group_id=%r (label=%r)" % (group_id, group_label))
    channels = _json_rpc("PVR.GetChannels", channelgroupid=group_id) or {}
    if not (channels.get("channels") or []):
        _log("group %r returned no channels, falling back to alltv" % group_id, xbmc.LOGWARNING)
        channels = _json_rpc("PVR.GetChannels", channelgroupid="alltv") or {}
    matches = []
    now_ts = time.time()
    title_l = title.lower()
    for ch in channels.get("channels", []) or []:
        cid = ch.get("channelid")
        cname = ch.get("label") or ""
        if cid is None:
            continue
        res = _json_rpc(
            "PVR.GetBroadcasts",
            channelid=cid,
            properties=["title", "starttime", "endtime", "runtime"],
        ) or {}
        for bc in res.get("broadcasts", []) or []:
            t = (bc.get("title") or "").strip()
            if not t or t.lower() != title_l:
                continue
            sdt = _parse_utc(bc.get("starttime"))
            if not sdt:
                continue
            sts = time.mktime(sdt.timetuple())
            if sts < now_ts - 3600:
                continue
            hour12 = sdt.hour % 12 or 12
            ampm = "AM" if sdt.hour < 12 else "PM"
            date_str = "%s %s %d, %d:%02d %s" % (
                sdt.strftime("%a"), sdt.strftime("%b"), sdt.day, hour12, sdt.minute, ampm,
            )
            matches.append({
                "label": "%s  —  %s" % (cname, date_str),
                "channelid": cid,
                "broadcastid": bc.get("broadcastid"),
                "start_ts": sts,
            })

    if not matches:
        xbmcgui.Dialog().notification("Altus", 'No upcoming airings of "%s"' % title, xbmcgui.NOTIFICATION_INFO, 3000)
        return

    matches.sort(key=lambda m: m["start_ts"])
    labels = [m["label"] for m in matches]
    idx = xbmcgui.Dialog().select('Find similar: %s' % title, labels)
    if idx < 0:
        return
    chosen = matches[idx]

    actions = [("Switch to channel", "switch"), ("Add timer", "timer")]
    if chosen["start_ts"] > time.time():
        actions.append(("Set reminder", "reminder"))
    header = "%s  —  %s" % (title, chosen["label"])
    action_idx = xbmcgui.Dialog().select(header, [a[0] for a in actions])
    if action_idx < 0:
        return
    choice = actions[action_idx][1]
    if choice == "switch":
        switch_channel({"channelid": chosen["channelid"]})
    elif choice == "timer" and chosen["broadcastid"] is not None:
        add_timer({"broadcastid": chosen["broadcastid"]})
    elif choice == "reminder" and chosen["broadcastid"] is not None:
        set_reminder({
            "broadcastid": chosen["broadcastid"],
            "channelid": chosen["channelid"],
            "start_ts": chosen["start_ts"],
            "title": title,
        })


def set_reminder(params):
    from urllib.parse import unquote_plus
    broadcastid = params.get("broadcastid")
    channelid = params.get("channelid")
    start_ts = params.get("start_ts")
    title = unquote_plus(params.get("title") or "")
    if not broadcastid or not channelid or not start_ts:
        xbmcgui.Dialog().notification("Altus", "Missing reminder data", xbmcgui.NOTIFICATION_WARNING, 2000)
        return
    start_ts = int(start_ts)
    if start_ts <= time.time():
        xbmcgui.Dialog().notification("Altus", "Programme already started", xbmcgui.NOTIFICATION_WARNING, 2000)
        return

    from modules import pvr_reminders
    pvr_reminders.add({
        "broadcastid": int(broadcastid),
        "channelid": int(channelid),
        "title": title,
        "start_ts": start_ts,
    })
    _refresh_epg_container()


_LEAD_CHOICES_MIN = [1, 2, 5, 10, 15, 30, 60]


def edit_reminder(params):
    from modules import pvr_reminders
    broadcastid = params.get("broadcastid")
    if not broadcastid:
        return
    r = pvr_reminders.get(broadcastid)
    if not r:
        xbmcgui.Dialog().notification("Altus", "Reminder not found", xbmcgui.NOTIFICATION_WARNING, 2000)
        return
    current_lead = int(r.get("lead_seconds", pvr_reminders.LEAD_SECONDS))
    labels = ["%d min before" % m for m in _LEAD_CHOICES_MIN]
    preselect = 2
    for i, m in enumerate(_LEAD_CHOICES_MIN):
        if m * 60 == current_lead:
            preselect = i
            break
    idx = xbmcgui.Dialog().select(
        'Lead time for "%s"' % (r.get("title") or "reminder"),
        labels, preselect=preselect,
    )
    if idx < 0:
        return
    pvr_reminders.update_lead(broadcastid, _LEAD_CHOICES_MIN[idx] * 60)
    xbmcgui.Dialog().notification("Altus", "Reminder updated", xbmcgui.NOTIFICATION_INFO, 2000)
    _refresh_epg_container()


def delete_reminder(params):
    from modules import pvr_reminders
    broadcastid = params.get("broadcastid")
    if not broadcastid:
        return
    r = pvr_reminders.get(broadcastid)
    title = (r.get("title") if r else "") or "this reminder"
    if not xbmcgui.Dialog().yesno("Delete reminder", "Delete reminder for [B]%s[/B]?" % title):
        return
    pvr_reminders.remove(broadcastid)
    _refresh_epg_container()


def add_timer(params):
    broadcastid = params.get("broadcastid")
    if not broadcastid:
        xbmcgui.Dialog().notification("Altus", "No broadcast id", xbmcgui.NOTIFICATION_WARNING, 2000)
        return
    res = _json_rpc("PVR.AddTimer", broadcastid=int(broadcastid))
    if res is None:
        xbmcgui.Dialog().notification("Altus", "Failed to add timer", xbmcgui.NOTIFICATION_ERROR, 2500)
    else:
        _refresh_epg_container()


def add_series_timer(params):
    broadcastid = params.get("broadcastid")
    if not broadcastid:
        xbmcgui.Dialog().notification("Altus", "No broadcast id", xbmcgui.NOTIFICATION_WARNING, 2000)
        return
    res = _json_rpc("PVR.AddTimer", broadcastid=int(broadcastid), timerrule=True)
    if res is None:
        xbmcgui.Dialog().notification("Altus", "Failed to add series timer", xbmcgui.NOTIFICATION_ERROR, 2500)
    else:
        _refresh_epg_container()


def epg_search(params):
    xbmc.executebuiltin("ActivateWindow(TVSearch)")


def open_channel_guide(params):
    target = (xbmc.getLocalizedString(19686) or "").strip()
    if not target:
        return
    home = xbmcgui.Window(10000)
    home.setProperty("altus.pvr.hiding_ctx", "true")
    try:
        monitor = xbmc.Monitor()
        xbmc.executebuiltin("Action(ContextMenu)")
        for _ in range(40):
            if xbmc.getCondVisibility("Window.IsVisible(contextmenu)"):
                break
            if monitor.waitForAbort(0.02):
                return
        else:
            return
        prev = None
        for _ in range(60):
            label = (xbmc.getInfoLabel("System.CurrentControl") or "").strip()
            if label and label == target:
                xbmc.executebuiltin("Action(Select)")
                return
            if label and label == prev:
                break
            prev = label
            xbmc.executebuiltin("Action(Down)")
            if monitor.waitForAbort(0.030):
                return
        xbmc.executebuiltin("Action(Close)")
    finally:
        xbmc.sleep(300)
        home.clearProperty("altus.pvr.hiding_ctx")


def _find_timerid_for_broadcast(broadcastid):
    bid = int(broadcastid)
    res = _json_rpc("PVR.GetTimers", properties=["broadcastid"]) or {}
    for t in res.get("timers", []) or []:
        if t.get("broadcastid") == bid:
            return t.get("timerid")
    return None


def edit_timer(params):
    broadcastid = params.get("broadcastid")
    timerid = _find_timerid_for_broadcast(broadcastid) if broadcastid else None
    target_title = None
    if timerid is not None:
        details = _json_rpc(
            "PVR.GetTimerDetails",
            timerid=int(timerid),
            properties=["title"],
        )
        if details:
            t = details.get("timerdetails") or {}
            target_title = (t.get("title") or "").strip() or None

    xbmc.executebuiltin("ActivateWindow(TVTimers)")
    monitor = xbmc.Monitor()

    def _wait_for_close_and_refresh():
        while xbmc.getCondVisibility("Window.IsVisible(TVTimers)"):
            if monitor.waitForAbort(0.25):
                return
        _refresh_epg_container()

    if not target_title:
        _wait_for_close_and_refresh()
        return

    for _ in range(50):
        if xbmc.getCondVisibility("Window.IsVisible(TVTimers)"):
            break
        if monitor.waitForAbort(0.1):
            return
    else:
        _refresh_epg_container()
        return
    for _ in range(50):
        if not xbmc.getCondVisibility("Window.IsVisible(TVTimers)"):
            _refresh_epg_container()
            return
        try:
            if int(xbmc.getInfoLabel("Container(50).NumItems") or 0) > 0:
                break
        except ValueError:
            pass
        if monitor.waitForAbort(0.1):
            return

    if xbmc.getCondVisibility("Window.IsVisible(TVTimers)"):
        try:
            total = int(xbmc.getInfoLabel("Container(50).NumItems") or 0)
        except ValueError:
            total = 0
        for i in range(total):
            if not xbmc.getCondVisibility("Window.IsVisible(TVTimers)"):
                break
            xbmc.executebuiltin("SetFocus(50,%d,absolute)" % i)
            if monitor.waitForAbort(0.08):
                return
            if not xbmc.getCondVisibility("Window.IsVisible(TVTimers)"):
                break
            label = xbmc.getInfoLabel("Container(50).ListItem.Label")
            if label and label.strip() == target_title:
                break

    _wait_for_close_and_refresh()


def delete_timer(params):
    broadcastid = params.get("broadcastid")
    if not broadcastid:
        return
    timerid = _find_timerid_for_broadcast(broadcastid)
    if timerid is None:
        xbmcgui.Dialog().notification("Altus", "Timer not found", xbmcgui.NOTIFICATION_WARNING, 2000)
        _refresh_epg_container()
        return

    all_timers = (_json_rpc("PVR.GetTimers", properties=["title", "istimerrule"]) or {}).get("timers", []) or []
    this_timer = next((t for t in all_timers if t.get("timerid") == int(timerid)), None) or {}
    this_title = (this_timer.get("title") or "").strip()
    this_is_rule = bool(this_timer.get("istimerrule"))
    rule_id = 0
    if this_is_rule:
        rule_id = int(timerid)
    elif this_title:
        for t in all_timers:
            if t.get("istimerrule") and (t.get("title") or "").strip() == this_title:
                rule_id = int(t.get("timerid") or 0)
                break
    _log("delete_timer timerid=%s title=%r rule_id=%d this_is_rule=%s" % (timerid, this_title, rule_id, this_is_rule))

    is_series_member = rule_id > 0
    if is_series_member:
        choice = xbmcgui.Dialog().yesnocustom(
            "Delete timer",
            "Delete the timer for this episode, or the whole series?",
            nolabel="This episode",
            yeslabel="Series",
            customlabel="Cancel",
        )
        if choice in (-1, 2):
            return
        if choice == 1:
            target_id = rule_id
        else:
            target_id = int(timerid)
    else:
        if not xbmcgui.Dialog().yesno("Delete timer", "Delete this timer?"):
            return
        target_id = int(timerid)

    res = _json_rpc("PVR.DeleteTimer", timerid=target_id)
    if res is None:
        xbmcgui.Dialog().notification("Altus", "Failed to delete timer", xbmcgui.NOTIFICATION_ERROR, 2500)
    else:
        _refresh_epg_container()


_ACTIONS = {
    "switch_channel": switch_channel,
    "jump_to_now": jump_to_now,
    "find_similar": find_similar,
    "add_timer": add_timer,
    "add_series_timer": add_series_timer,
    "edit_timer": edit_timer,
    "delete_timer": delete_timer,
    "epg_search": epg_search,
    "open_channel_guide": open_channel_guide,
    "set_reminder": set_reminder,
    "edit_reminder": edit_reminder,
    "delete_reminder": delete_reminder,
}


def dispatch(params):
    act = params.get("act")
    fn = _ACTIONS.get(act)
    if not fn:
        _log("unknown action: %r" % act, xbmc.LOGWARNING)
        return
    try:
        fn(params)
    except Exception as e:
        _log("action %r failed: %s" % (act, e), xbmc.LOGERROR)
        xbmcgui.Dialog().notification("Altus", "Action failed", xbmcgui.NOTIFICATION_ERROR, 2500)
