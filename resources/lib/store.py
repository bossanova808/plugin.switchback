import os

from bossanova808.utilities import *
from bossanova808.playback import PlaybackList


class Store:
    """
    Helper class to read in and store the addon settings, and to provide a general centralised store
    Create one with: Store()
    """
    # Static class variables, referred to elsewhere by Store.whatever
    # https://docs.python.org/3/faq/programming.html#how-do-i-create-static-class-data-and-static-class-methods
    kodi_event_monitor = None
    kodi_player = None
    # Holds our playlist of things played back, in first is the latest order
    switchback = PlaybackList([], xbmcvfs.translatePath(os.path.join(PROFILE, "switchback.json")))
    # When something is being played back, store the details
    current_playback = None
    # Playbacks are of these possible types
    kodi_video_types = ["movie", "tvshow", "episode", "musicvideo", "video", "file"]
    kodi_music_types = ["song", "album"]
    # Addon settings
    save_across_sessions = ADDON.getSettingBool('save_across_sessions')
    maximum_list_length = ADDON.getSettingInt('maximum_list_length')
    # GUI Settings - to work out how to force browse to a show after a switchback initiated playback
    flatten_tvshows = None

    def __init__(self):
        """
        Load in the addon settings and do basic initialisation stuff
        :return:
        """
        Store.load_config_from_settings()
        Store.load_config_from_kodi_settings()
        Store.switchback.load_or_init()
        Store.update_home_window_properties()

    @staticmethod
    def load_config_from_settings():
        """
        Load in the addon settings, at start or reload them if they have been changed
        :return:
        """
        Logger.info("Loading configuration")
        Store.maximum_list_length = ADDON.getSettingInt('maximum_list_length')
        Logger.info(f"Maximum Switchback list length is: {Store.maximum_list_length}")
        Store.save_across_sessions = ADDON.getSettingBool('save_across_sessions')
        Logger.info(f"Save across sessions is: {Store.save_across_sessions}")

    @staticmethod
    def load_config_from_kodi_settings():
        Store.flatten_tvshows = int(get_kodi_setting('videolibrary.flattentvshows'))
        Logger.info(f"Flatten TV Shows is: {Store.flatten_tvshows}")

    @staticmethod
    def update_home_window_properties():
        Logger.log(f"Updating Home Window Properties")
        Logger.info("Switchback PlaybackList is:")
        Logger.info(Store.switchback.list)
        set_property(HOME_WINDOW, 'Switchback_List_Length', str(len(Store.switchback.list)))
        if len(Store.switchback.list) > 1:
            set_property(HOME_WINDOW, 'Switchback_Item', Store.switchback.list[1].pluginlabel)
        elif len(Store.switchback.list) == 1:
            set_property(HOME_WINDOW, 'Switchback_Item', Store.switchback.list[0].pluginlabel)
        else:
            clear_property(HOME_WINDOW, 'Switchback_Item')
