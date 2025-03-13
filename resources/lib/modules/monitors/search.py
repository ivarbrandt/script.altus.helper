from ..search_utils import *

class SearchMonitor(xbmc.Monitor):
    """Monitor class for handling search history via window properties"""
    def __init__(self, database):
        super().__init__()
        self.database = database
        self.home_window = xbmcgui.Window(10000)
        self.max_history_items = 100
        self.initialize()
    
    def initialize(self):
        self.refresh_search_history()
    
    def refresh_search_history(self):
        history = self.database.fetch_all_spaths()
        for i in range(1, self.max_history_items + 1):
            self.home_window.clearProperty(f"altus.search.history.{i}")
            self.home_window.clearProperty(f"altus.search.history.{i}.id")
        for i, (id, term) in enumerate(history[:self.max_history_items], 1):
            self.home_window.setProperty(f"altus.search.history.{i}", term)
            self.home_window.setProperty(f"altus.search.history.{i}.id", str(id))
        count = min(len(history), self.max_history_items)
        self.home_window.setProperty("altus.search.history.count", str(count))
        if count == 0:
            self.home_window.setProperty("altus.search.history.empty", "Your search history is empty. Click the search icon to perform a new search.")
        else:
            self.home_window.clearProperty("altus.search.history.empty")

    def onNotification(self, sender, method, data):
        """Handle notifications for search operations"""
        if sender != "script.altus.helper":
            return
        elif method == "altus.search.refresh":
            self.refresh_search_history()