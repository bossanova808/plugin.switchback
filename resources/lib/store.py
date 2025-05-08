import os

from bossanova808.utilities import *
from bossanova808.playback import PlaybackList


class Store:
    """
    Helper class to read in and store the addon settings, and to provide a centralised store
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
    # Advanced settings - for manually working out if we have reached the 'will be marked as watched' point in the playback
    ignore_seconds_at_start = None
    ignore_percent_at_end = None

    def __init__(self):
        """
        Load in the addon settings and do basic initialisation stuff
        :return:
        """
        Store.load_config_from_settings()
        Store.load_config_from_kodi_settings()
        Store.load_config_from_advancedsettings()
        if Store.save_across_sessions:
            Store.switchback.load_from_file()
        else:
            Store.switchback.init()
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
    def load_config_from_advancedsettings():
        """
        Load anything we need from Kodi's advancedSettings.xml file
        :return:
        """
        Logger.info("Query for advancedsettings.xml settings: ignoresecondsatstart (default 180), ignorepercentatend (default 8)")
        Store.ignore_seconds_at_start = int(get_advancedsetting('./video/ignoresecondsatstart')) or 180
        Store.ignore_percent_at_end = int(get_advancedsetting('./video/ignorepercentatend')) or 8
        Logger.info(f"Using ignore seconds at start: {Store.ignore_seconds_at_start}")
        Logger.info(f"Using ignore percent at end: {Store.ignore_percent_at_end}")

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
