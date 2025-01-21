import xbmc, xbmcgui
from threading import Thread
from modules.MDbList import *
from modules.image import *
import json
import re

logger = xbmc.log
empty_ratings = {
    "digital_release_flag":"",
    "digital_release_date":"",
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
        self.last_set_id = None
        # self.window = xbmcgui.Window
        self.home_window = xbmcgui.Window(10000)
        # self.get_window_id = xbmcgui.getCurrentWindowId
        self.get_infolabel = xbmc.getInfoLabel
        self.get_visibility = xbmc.getCondVisibility
        self.last_mediatype = ""
        self.last_imdb_id = None
        self.current_ratings_thread = None
        self.pending_id = None 

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
            dbtype = self.get_infolabel("ListItem.DBTYPE").lower()
            if not dbtype in ["movie", "tvshow", "episode", "season"]:
                self._clear_ratings_properties()
                self.last_set_id = None
                self.pending_id = None
                self.waitForAbort(0.2)
                continue
            current_imdb_id = (self.get_infolabel("ListItem.IMDBNumber") or 
                               self.get_infolabel("ListItem.Property(imdb)"))
            current_tmdb_id = (self.get_infolabel("ListItem.Property(TMDb_ID)") or 
                               self.get_infolabel("ListItem.Property(tmdb)"))
            if current_imdb_id and current_imdb_id.startswith('tt'):
                meta = {'imdb_id': current_imdb_id}
            elif current_tmdb_id:
                meta = {
                    'tmdb_id': current_tmdb_id,
                    'media_type': self._get_media_type()
                }
            else:
                title = self.get_infolabel("ListItem.Label")
                if not title:
                    self._clear_ratings_properties()
                    self.last_set_id = None
                    self.pending_id = None
                    self.waitForAbort(0.2)
                    continue
                meta = {
                    'title': title,
                    'premiered': self.get_infolabel("ListItem.Premiered"),
                    'media_type': self._get_media_type()
                }
                found_imdb_id = self.mdblist_api().lookup_imdb_id(meta)
                if not found_imdb_id:
                    self._clear_ratings_properties()
                    self.last_set_id = None
                    self.pending_id = None
                    self.waitForAbort(0.2)
                    continue
                current_imdb_id = found_imdb_id
                meta = {'imdb_id': current_imdb_id}
            
            if current_imdb_id and current_imdb_id.startswith('tt'):
                media_id = current_imdb_id
            elif current_tmdb_id:
                media_id = current_tmdb_id
                meta = {
                    'tmdb_id': current_tmdb_id,
                    'media_type': self._get_media_type()
                }
            if media_id == self.last_set_id:
                trailer_url = xbmc.getInfoLabel("Window(Home).Property(altus.trailer)")
                if trailer_url:
                    match = video_id_pattern.search(trailer_url)
                    if match:
                        video_id = match.group(1)
                        play_url = f"plugin://plugin.video.youtube/play/?video_id={video_id}"
                        xbmc.executebuiltin(f"Skin.SetString(TrailerPlaybackURL,{play_url})")
                    self.waitForAbort(0.2)
                    continue
            if media_id != self.last_set_id or media_id != self.pending_id:
                cached_ratings = self.home_window.getProperty(f"altus.cachedRatings.{media_id}")
                if cached_ratings:
                    self._set_ratings_from_cache(media_id, cached_ratings)
                else:
                    self._start_new_ratings_thread(api_key, media_id)
            self.waitForAbort(0.2)

    def _clear_ratings_properties(self):
        for k, v in empty_ratings.items():
            self.home_window.setProperty("altus.%s" % k, str(v))

    def _get_media_type(self):
        dbtype = self.get_infolabel("ListItem.DBTYPE").lower()
        if dbtype == "movie":
            return "movie"
        elif dbtype in ["tvshow", "episode", "season"]:
            return "tv"
        return "movie"

    def _set_ratings_from_cache(self, imdb_id, cached_ratings):
        try:
            result = json.loads(cached_ratings)
            for k, v in result.items():
                self.home_window.setProperty("altus.%s" % k, str(v))
            self.last_set_id = imdb_id
        except json.JSONDecodeError:
            self._clear_ratings_properties()

    def _start_new_ratings_thread(self, api_key, imdb_id):
        if self.current_ratings_thread and self.current_ratings_thread.is_alive():
            if self.pending_id != imdb_id:
                self.pending_id = None
        if self.pending_id != imdb_id:
            self.pending_id = imdb_id
            self.current_ratings_thread = Thread(
                target=self._fetch_ratings_thread,
                args=(api_key, imdb_id)
            )
            self.current_ratings_thread.start()

    def _fetch_ratings_thread(self, api_key, media_id):
        if media_id != self.pending_id:
            return
        meta = {}
        if media_id.startswith('tt'):
            meta['imdb_id'] = media_id
        elif media_id.isdigit():
            meta['tmdb_id'] = media_id
            meta['media_type'] = self._get_media_type()
        else:
            meta.update({
                'title': self.get_infolabel("ListItem.Label"),
                'premiered': self.get_infolabel("ListItem.Premiered"),
                'media_type': self._get_media_type()
            })
        result = self.mdblist_api().fetch_info(meta, api_key)
        if media_id != self.pending_id:
            return
        if result:
            imdb_id = result.get('imdbid')
            tmdb_id = result.get('tmdbid')
            if imdb_id:
                self.home_window.setProperty(f"altus.cachedRatings.{imdb_id}", json.dumps(result))
            if tmdb_id:
                self.home_window.setProperty(f"altus.cachedRatings.{tmdb_id}", json.dumps(result))
            for k, v in result.items():
                self.home_window.setProperty("altus.%s" % k, str(v))
            self.last_set_id = imdb_id if imdb_id else media_id

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

