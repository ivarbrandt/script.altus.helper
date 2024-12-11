import xbmc, xbmcgui
from threading import Thread
from modules.MDbList import *
from modules.image import *
import json
import re

logger = xbmc.log
empty_ratings = {
    "metascore": "",
    "metascoreImage": "",
    "traktRating": "",
    "traktImage": "",
    "letterboxdRating": "",
    "letterboxdImage": "",
    "mdblistRating": "",
    "mdblistImage": "",
    "tomatoMeter": "",
    "tomatoImage": "",
    "tomatoUserMeter": "",
    "tomatoUserImage": "",
    "imdbRating": "",
    "imdbImage": "",
    "popularRating": "",
    "popularImage": "",
    "tmdbRating": "",
    "tmdbImage": "",
    "first_in_collection": "",
    "collection_follow_up": "",
    "belongs_to_collection": "",
}

video_id_pattern = re.compile(r"v=([a-zA-Z0-9_-]+)")


class Service(xbmc.Monitor):
    def __init__(self):
        super().__init__()
        self.mdblist_api = MDbListAPI
        self.get_colors = ImageColorAnalyzer
        self.last_set_imdb_id = None
        # self.window = xbmcgui.Window
        self.home_window = xbmcgui.Window(10000)
        # self.get_window_id = xbmcgui.getCurrentWindowId
        self.get_infolabel = xbmc.getInfoLabel
        self.get_visibility = xbmc.getCondVisibility
        self.last_mediatype = ""
        self.last_imdb_id = None

    def run(self):
        image_thread = Thread(target=self.altus_image_monitor)
        image_thread.start()
        # color_monitor_thread = Thread(target=self.color_monitor)
        # color_monitor_thread.start()
        while not self.abortRequested():
            self.altus_ratings_monitor()
            self.waitForAbort(0.2)

    def pause_services(self):
        return self.home_window.getProperty("pause_services") == "true"

    def not_altus(self):
        return xbmc.getSkinDir() != "skin.altus"

    def container_is_scrolling(self):
        return self.get_visibility("Container.Scrolling")

    def onNotification(self, sender, method, data):
        # logger(
        #     "Notification received - Sender: {}, Method: {}, Data: {}".format(
        #         sender, method, data
        #     ),
        #     1,
        # )
        if sender == "xbmc":
            if method in ("GUI.OnScreensaverActivated", "System.OnSleep"):
                self.home_window.setProperty("pause_services", "true")
                logger("###Altus: Device is Asleep, PAUSING All Services", 1)
            elif method in ("GUI.OnScreensaverDeactivated", "System.OnWake"):
                self.home_window.clearProperty("pause_services")
                logger("###Altus: Device is Awake, RESUMING All Services", 1)

    def altus_ratings_monitor(self):
        while not self.abortRequested():
            if self.pause_services():
                self.waitForAbort(2)
                continue
            if self.not_altus():
                self.waitForAbort(15)
                continue
            api_key = self.get_infolabel("Skin.String(mdblist_api_key)")
            if not api_key:
                self.waitForAbort(10)
                continue
            if not self.get_visibility(
                "Window.IsVisible(videos) | Window.IsVisible(home) | Window.IsVisible(11121) | Window.IsActive(movieinformation)"
            ):
                self.waitForAbort(2)
                continue
            if self.container_is_scrolling():
                self.waitForAbort(0.2)
                continue
            imdb_id = self.get_infolabel("ListItem.IMDBNumber") or self.get_infolabel(
                "VideoPlayer.IMDBNumber"
            )
            set_property = self.home_window.setProperty
            get_property = self.home_window.getProperty
            clear_property = self.home_window.clearProperty
            cached_ratings = get_property(f"altus.cachedRatings.{imdb_id}")
            if not imdb_id or not imdb_id.startswith("tt"):
                for k, v in empty_ratings.items():
                    set_property("altus.%s" % k, str(v))
                self.last_set_imdb_id = None
                self.waitForAbort(0.2)
                continue
            if imdb_id == self.last_set_imdb_id:
                trailer_url = xbmc.getInfoLabel(
                    "Window(Home).Property(altus.trailer)"
                )
                if trailer_url:
                    match = video_id_pattern.search(trailer_url)
                    if match:
                        video_id = match.group(1)
                        play_url = (
                            f"plugin://plugin.video.youtube/play/?video_id={video_id}"
                        )
                        xbmc.executebuiltin(
                            f"Skin.SetString(TrailerPlaybackURL,{play_url})"
                        )
                    self.waitForAbort(0.2)
                    continue
            if cached_ratings:
                result = json.loads(cached_ratings)
                for k, v in result.items():
                    set_property("altus.%s" % k, str(v))
                self.last_set_imdb_id = imdb_id
                self.waitForAbort(0.2)
                continue
            Thread(target=self.altus_set_ratings, args=(api_key, imdb_id)).start()
            self.waitForAbort(0.2)

    def altus_set_ratings(self, api_key, imdb_id):
        set_property = self.home_window.setProperty
        result = self.mdblist_api().fetch_info({"imdb_id": imdb_id}, api_key)
        if result:
            set_property(f"altus.cachedRatings.{imdb_id}", json.dumps(result))
            for k, v in result.items():
                set_property("altus.%s" % k, str(v))

    def altus_image_monitor(self):
        while not self.abortRequested():
            if self.pause_services():
                self.waitForAbort(2)
                continue
            if self.not_altus():
                self.waitForAbort(15)
                continue
            radius = "40"
            saturation = "1.5"
            self.get_colors(radius=radius, saturation=saturation)
            self.waitForAbort(0.2)


if __name__ == "__main__":
    service = Service()
    service.run()
