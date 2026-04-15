# -*- coding: utf-8 -*-
import json
import os
import time

import xbmc
import xbmcvfs


REMINDERS_PATH = xbmcvfs.translatePath(
    "special://profile/addon_data/script.altus.helper/reminders.json"
)
LEAD_SECONDS = 120


def _log(msg, level=xbmc.LOGINFO):
    xbmc.log("[script.altus.helper pvr_reminders] %s" % msg, level=level)


def _ensure_dir():
    d = os.path.dirname(REMINDERS_PATH)
    if not os.path.isdir(d):
        os.makedirs(d, exist_ok=True)


def _load():
    if not os.path.isfile(REMINDERS_PATH):
        return []
    try:
        with open(REMINDERS_PATH, "r") as f:
            return json.load(f)
    except (OSError, ValueError) as e:
        _log("load error: %s" % e, xbmc.LOGWARNING)
        return []


def _save(reminders):
    _ensure_dir()
    with open(REMINDERS_PATH, "w") as f:
        json.dump(reminders, f)


def add(reminder):
    reminders = _load()
    bid = reminder.get("broadcastid")
    reminders = [r for r in reminders if r.get("broadcastid") != bid]
    reminders.append(reminder)
    _save(reminders)
    _log("added reminder %r -> %s (total=%d)" % (reminder, REMINDERS_PATH, len(reminders)))


def remove(broadcastid):
    bid = int(broadcastid)
    reminders = [r for r in _load() if r.get("broadcastid") != bid]
    _save(reminders)


def get(broadcastid):
    bid = int(broadcastid)
    for r in _load():
        if r.get("broadcastid") == bid:
            return r
    return None


def ids():
    return {r.get("broadcastid") for r in _load() if r.get("broadcastid") is not None}


def update_lead(broadcastid, lead_seconds):
    bid = int(broadcastid)
    reminders = _load()
    for r in reminders:
        if r.get("broadcastid") == bid:
            r["lead_seconds"] = int(lead_seconds)
            break
    _save(reminders)


def pop_due(now_ts=None):
    """Return and remove reminders whose start_ts is within their lead window."""
    if now_ts is None:
        now_ts = time.time()
    reminders = _load()
    if reminders:
        _log("checking %d reminder(s) at now_ts=%d" % (len(reminders), now_ts))
    due, remaining = [], []
    for r in reminders:
        start_ts = r.get("start_ts", 0)
        lead = r.get("lead_seconds", LEAD_SECONDS)
        if start_ts - now_ts <= lead:
            due.append(r)
        else:
            remaining.append(r)
    if due:
        _log("firing %d reminder(s)" % len(due))
        _save(remaining)
    return due
