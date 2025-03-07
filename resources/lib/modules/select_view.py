import xbmc, xbmcgui, xbmcvfs

# Define your views - adjust view IDs and localization strings as needed for your skin
# Base view templates
BASE_VIEWS = {
    'List': {'viewid': '50', 'localized': '535'},
    'PosterFlow': {'viewid': '51', 'localized': '310981'},
    'IconWall': {'viewid': '52', 'localized': '31099'},
    'Slide': {'viewid': '53', 'localized': '31100'},
    'PosterInfo': {'viewid': '54', 'localized': '31101'},
    'LandscapeInfo': {'viewid': '55', 'localized': '311012'},
    'FlixInfo': {'viewid': '56', 'localized': '31107'},
    'Season': {'viewid': '57', 'localized': '311024'},
    'Wall': {'viewid': '500', 'localized': '311022'},
    'LandscapeWall': {'viewid': '501', 'localized': '311023'},
}

def make_view(label, content_type):
    base = BASE_VIEWS[label].copy()
    base['label'] = label
    base['preview'] = f"{label.lower()}_{content_type}_preview.jpg"
    return base

# Define which views are available for each content type
MOVIE_VIEWS = ['List', 'PosterFlow', 'Slide', 'PosterInfo', 'LandscapeInfo', 'FlixInfo', 'Wall', 'LandscapeWall']
TVSHOW_VIEWS = ['List', 'PosterFlow', 'Slide', 'PosterInfo', 'LandscapeInfo', 'FlixInfo', 'Wall', 'LandscapeWall']
SEASON_VIEWS = ['List', 'PosterFlow', 'Slide', 'PosterInfo', 'LandscapeInfo', 'FlixInfo', 'Season', 'Wall', 'LandscapeWall']
EPISODE_LIST_VIEWS = ['List', 'PosterFlow', 'Slide', 'LandscapeInfo', 'FlixInfo', 'LandscapeWall']
EPISODE_VIEWS = ['List', 'LandscapeInfo', 'LandscapeWall']
ADDON_VIEWS = ['List']
FAVOURITES_VIEWS = ['List', 'IconWall']
FILES_VIEWS = ['List', 'IconWall']
MENU_VIEWS = ['List', 'IconWall']

# Build the complete VIEWS dictionary
VIEWS = {
    'movies': [make_view(view, 'movies') for view in MOVIE_VIEWS],
    'tvshows': [make_view(view, 'tvshows') for view in TVSHOW_VIEWS],
    'seasons': [make_view(view, 'seasons') for view in SEASON_VIEWS],
    'episodes.outside': [make_view(view, 'episodes') for view in EPISODE_LIST_VIEWS],
    'episodes.inside': [make_view(view, 'episodes') for view in EPISODE_VIEWS],
    'addons': [make_view(view, 'addons') for view in ADDON_VIEWS],
    'favourites': [make_view(view, 'favourites') for view in FAVOURITES_VIEWS],
    'files': [make_view(view, 'files') for view in FILES_VIEWS],
    '': [make_view(view, 'menu') for view in MENU_VIEWS],  # Empty content type for menus
}

def get_content_type():
    if xbmc.getCondVisibility('Container.Content(episodes)'):
        if xbmc.getCondVisibility('String.StartsWith(Container.PluginCategory,Season)'):
            return 'episodes.inside'
        return 'episodes.outside'
    content = xbmc.getInfoLabel('Container.Content')
    return '' if not content else content

class ViewSelectorDialog(xbmcgui.WindowXMLDialog):
    def __init__(self, *args, **kwargs):
        self.content_type = kwargs.get('content_type', '')
        self.current_view = kwargs.get('current_view', '')
        self.views = VIEWS.get(self.content_type, [])
        super(ViewSelectorDialog, self).__init__(*args)

    def onInit(self):
        self.viewlist = self.getControl(3000)
        for view in self.views:
            list_item = xbmcgui.ListItem(view['label'])
            self.viewlist.addItem(list_item)
        
        if self.views:
            self.viewlist.selectItem(0)
            self.setFocusId(3000)

    def onAction(self, action):
        action_id = action.getId()
        if action_id in [xbmcgui.ACTION_PREVIOUS_MENU, xbmcgui.ACTION_NAV_BACK]:
            xbmc.executebuiltin(f'Skin.SetString(Skin.ForcedView.{self.content_type},{self.current_view})')
            xbmc.executebuiltin('ClearProperty(ViewTransitioning,home)')
            self.close()

    def onClick(self, controlId):
        if controlId == 3000:
            selected_index = self.viewlist.getSelectedPosition()
            view = self.views[selected_index]
            xbmc.executebuiltin(f'Skin.Reset(Skin.ForcedView.{self.content_type})')
            xbmc.sleep(200)
            xbmc.executebuiltin(f'SetProperty(ViewSwitchLabel,{view["label"]},home)')
            for _ in range(3):
                xbmc.executebuiltin(f'Container.SetViewMode({view["viewid"]})')
                xbmc.sleep(500)
                localized_value = xbmc.getLocalizedString(int(view["localized"]))
                xbmc.executebuiltin(f'Skin.SetString(Skin.ForcedView.{self.content_type},{localized_value})')
            xbmc.executebuiltin('ClearProperty(ViewTransitioning,home)')
            xbmc.executebuiltin('ClearProperty(ViewSwitchLabel,home)')
            self.close()

def select_view():
    xbmc.executebuiltin('Action(right)')
    xbmc.sleep(500)
    xbmc.executebuiltin('SetProperty(ViewTransitioning,true,home)')
    
    content_type = get_content_type()
    current_view = xbmc.getInfoLabel('Container.Viewmode')
    
    if not VIEWS.get(content_type, []):
        xbmc.executebuiltin(f'Skin.SetString(Skin.ForcedView.{content_type},{current_view})')
        xbmc.executebuiltin('ClearProperty(ViewTransitioning,home)')
        return

    dialog = ViewSelectorDialog('Custom_1122_ViewSelector.xml', xbmcvfs.translatePath('special://skin/'), 'Default', content_type=content_type, current_view=current_view)
    dialog.doModal()
    del dialog