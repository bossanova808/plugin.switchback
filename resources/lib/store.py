import json
from json import JSONDecodeError

from bossanova808.constants import *
from bossanova808.logger import Logger
from bossanova808.notify import Notify
import os
from types import SimpleNamespace

from resources.lib.playback import Playback


class Store:
    """
    Helper class to read in and store the addon settings, and to provide a centralised store
    """
    # Static class variables, referred to elsewhere by Store.whatever
    # https://docs.python.org/3/faq/programming.html#how-do-i-create-static-class-data-and-static-class-methods
    kodi_event_monitor = None
    kodi_player = None
    # Holds our playlist of things played back, in first is the latest order
    switchback_list = []
    switchback_list_file = xbmcvfs.translatePath(os.path.join(PROFILE, "switchback_list.json"))
    # When something is being played back, store the details
    current_playback = None
    # Addon settings
    maximum_list_length = ADDON.getSettingInt('maximum_list_length')
    include_music = ADDON.getSettingBool('include_music')
    filter_watched = ADDON.getSettingBool('filter_watched')
    # Playbacks are of these possible types
    kodi_video_types = ["movie", "tvshow", "episode", "musicvideo", "video"]
    kodi_music_types = ["song","album"]

    def __init__(self):
        """
        Load in the addon settings and do basic initialisation stuff
        :return:
        """
        Store.load_config_from_settings()

    @staticmethod
    def load_config_from_settings():
        """
        Load in the addon settings, at start or reload them if they have been changed
        :return:
        """
        Logger.info("Loading configuration")
        Store.maximum_list_length = ADDON.getSettingInt('maximum_list_length')
        Store.include_music = ADDON.getSettingBool('include_music')
        Store.filter_watched = ADDON.getSettingBool('filter_watched')
        Logger.info(f"Maximum Switchback list length is: {Store.maximum_list_length}")
        Logger.info(f"Include Music is: {Store.include_music}")

        Store.switchback_list = []
        Logger.info(f"Loading Switchback playlist from file: {Store.switchback_list_file}")
        try:
            with open(Store.switchback_list_file, 'r') as switchback_list_file:
                switchback_list_json = json.load(switchback_list_file)
                for playback in switchback_list_json:
                    Store.switchback_list.append(Playback(**playback))
        except FileNotFoundError:
            Logger.error("Switchback list file not found, creating empty Switchback list file")
            # Creates an empty Switchback list file if it doesn't yet exist
            os.makedirs(os.path.dirname(Store.switchback_list_file), exist_ok=True)
            with open(Store.switchback_list_file, 'w'):
                pass
            Store.switchback_list = []
        except JSONDecodeError:
            Logger.error("Unable to parse switchback list, JSONDecodeError...corrupt or empty, starting a new empty list")
            Store.switchback_list = []
        except:
            raise

        # Filter out any music playbacks if the setting is currently not to record them
        for playback_to_maybe_remove in Store.switchback_list:
            if not Store.include_music and playback_to_maybe_remove.type in Store.kodi_music_types:
                Logger.warning("Include music is false, removing music playback from Switchback list")
                Store.switchback_list.remove(playback_to_maybe_remove)

        Logger.info("Switchback List is:")
        Logger.info(Store.switchback_list)

    @staticmethod
    def save_switchback_list():
        """
        Save the Switchback list to file in JSON format
        :return:
        """
        Logger.debug(Store.switchback_list)

        # This approach keeps all the details from the original playback
        # (in case they don't make it through when the repeat playback from the Switchback list occurs - as sometimes seems to be the case)
        playback_to_remove = None
        for previous_playback in Store.switchback_list:
            if previous_playback.path == Store.current_playback.path:
                playback_to_remove = previous_playback
                break

        if playback_to_remove:
            Store.switchback_list.remove(playback_to_remove)
            # Update with the current playback times
            playback_to_remove.resumetime = Store.current_playback.resumetime
            playback_to_remove.totaltime = Store.current_playback.totaltime
            Store.switchback_list.insert(0, playback_to_remove)
        else:
            Store.switchback_list.insert(0, Store.current_playback)

        Logger.debug(Store.switchback_list)

        # Trim the list to the max length
        Store.switchback_list = Store.switchback_list[0:Store.maximum_list_length]

        # And finally write out the updated list to disk
        with open(Store.switchback_list_file, 'w', encoding='utf-8') as f:
            json_string = json.dumps([vars(playback) for playback in Store.switchback_list], indent=4)
            f.write(json_string)




