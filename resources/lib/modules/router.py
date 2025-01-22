# -*- coding: utf-8 -*-
import sys
from urllib.parse import parse_qsl

# from modules.logger import logger


def routing():
    params = dict(parse_qsl(sys.argv[1], keep_blank_values=True))
    _get = params.get
    mode = _get("mode", "check_for_update")

    if mode == "widget_monitor":
        from modules.widget_utils import widget_monitor

        return widget_monitor(_get("list_id"))

    if mode == "widget_info_timer":
        from modules.widget_utils import widget_info_timer

        return widget_info_timer(_get("list_id"))

    if mode == "spotlight_timer":
        from modules.widget_utils import spotlight_timer

        return spotlight_timer(_get("list_id"))

    if "actions" in mode:
        from modules import actions

        return exec("actions.%s(params)" % mode.split(".")[1])

    if mode == "check_for_update":
        from modules.version_monitor import check_for_update

        return check_for_update(_get("skin_id"))

    if mode == "check_for_profile_change":
        from modules.version_monitor import check_for_profile_change

        return check_for_profile_change(_get("skin_id"))

    if mode == "starting_widgets":
        from modules.cpath_maker import starting_widgets

        return starting_widgets()

    if mode == "manage_widgets":
        from modules.cpath_maker import CPaths

        return CPaths(_get("cpath_setting")).manage_widgets()

    if mode == "manage_main_menu_path":
        from modules.cpath_maker import CPaths

        return CPaths(_get("cpath_setting")).manage_main_menu_path()

    if mode == "remake_all_cpaths":
        from modules.cpath_maker import remake_all_cpaths

        return remake_all_cpaths()

    if mode == "search_input":
        from modules.search_utils import SPaths

        return SPaths().search_input()

    if mode == "remove_all_spaths":
        from modules.search_utils import SPaths

        return SPaths().remove_all_spaths()

    if mode == "re_search":
        from modules.search_utils import SPaths

        return SPaths().re_search()

    if mode == "open_search_window":
        from modules.search_utils import SPaths

        return SPaths().open_search_window()

    if mode == "set_api_key":
        from modules.custom_actions import set_api_key

        return set_api_key()

    if mode == "select_view":
        from modules.select_view import select_view

        return select_view()

    if mode == "delete_all_ratings":
        from modules.databases.ratings import RatingsDatabase

        return RatingsDatabase().delete_all_ratings()

    if mode == "set_image":
        from modules.custom_actions import set_image

        return set_image()

    if mode == "play_trailer":
        from modules.custom_actions import play_trailer

        return play_trailer()

    if mode == "clear_cache":
        from modules.helper import clear_cache

        return clear_cache()

    if mode == "calculate_cache_size":
        from modules.helper import calculate_cache_size

        return calculate_cache_size()

    if mode == "show_changelog":
        from modules.custom_actions import show_changelog

        return show_changelog()

    if mode == "check_api_key_on_load":
        from modules.custom_actions import check_api_key_on_load

        return check_api_key_on_load()

    # if mode == "set_widget_boundaries":
    #     from modules.custom_actions import set_widget_boundaries

    #     return set_widget_boundaries()
