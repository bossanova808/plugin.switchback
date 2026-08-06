import os
import json
from dataclasses import dataclass
from typing import List, Optional

import xbmcvfs

# noinspection PyPackages
from bossanova808.playback import Playback
# noinspection PyPackages
from bossanova808.utilities import get_resume_point, get_playcount, get_advancedsetting
# noinspection PyPackages
from bossanova808.logger import Logger


@dataclass
class PlaybackList:
    """
    A list of Playback objects, with some helper methods.  Stored both in memory (accessible via .list) and on disk (filename at .file)
    Is a standard Python list, so can be iterated over, indexed, etc., and of course, all standard list methods are available.

    To create a PlaybackList::
        switchback = PlaybackList([], xbmcvfs.translatePath(os.path.join(PROFILE, "switchback_list.json")))
    """
    list: List[Playback]
    file: str
    remove_watched_playbacks: bool = False

    def toJson(self) -> str:
        """
        Return the list of Playback objects as JSON

        :return: the list of Playback objects as JSON
        """
        return json.dumps([p.__dict__ for p in self.list], ensure_ascii=False, indent=2)

    def init(self) -> None:
        """
        Initialise/reset in memory PlaybackList, and delete/re-create the empty PlaybackList file
        """
        self.list = []
        xbmcvfs.mkdirs(os.path.dirname(self.file))
        with open(self.file, 'w', encoding='utf-8') as switchback_list_file:
            switchback_list_file.write('[]')

    def load_or_init(self) -> None:
        """
        Load a JSON-formatted PlaybackList from the PlaybackList file
        """
        Logger.info("Try to load PlaybackList from file:", self.file)
        # Ensure we start from a clean slate before loading from disk
        self.list = []
        try:
            with open(self.file, 'r', encoding='utf-8') as switchback_list_file:
                switchback_list_json = json.load(switchback_list_file)
                if not isinstance(switchback_list_json, list):
                    Logger.error(f"PlaybackList file [{self.file}] did not contain a JSON array — reinitialising")
                    self.init()
                    return
                for playback in switchback_list_json:
                    self.list.append(Playback.from_dict(playback))

        except FileNotFoundError:
            Logger.warning(f"Could not find: [{self.file}] - creating empty PlaybackList & file")
            self.init()
        except json.JSONDecodeError:
            Logger.error(f"JSONDecodeError - Unable to parse PlaybackList file [{self.file}] -  creating empty PlaybackList & file")
            self.init()

        list_needs_save = False

        # If the user wants to filter out watched items from the list
        if self.remove_watched_playbacks:
            paths_to_remove = []
            for item in list(self.list):
                # DB item?  Is it marked as watched in the DB?
                if item.dbid:
                    playcount = get_playcount(item.type, item.dbid)
                    if playcount is None:
                        Logger.warning(f"dbid {item.dbid} no longer valid in Kodi library for [{item.pluginlabel}] - removing from Switchback list")
                        paths_to_remove.append(item.path)
                        list_needs_save = True
                    elif playcount > 0:
                        list_needs_save = True
                        Logger.warning(f"Filtering watched playback from the list (as playcount > 0 in Kodi DB): [{item.pluginlabel}]")
                        paths_to_remove.append(item.path)

                # Not a DB item, use a calculation instead and compare to the playcount_minium_percent
                elif item.resumetime and item.totaltime:
                    percent_played = (item.resumetime / item.totaltime) * 100
                    # Use the user set playcount_minium_percent if there is one, or fallback to Kodi default 90 percent
                    setting = get_advancedsetting('video/playcountminimumpercent')
                    playcount_minium_percent = float(setting) if setting and setting != 0 else 90.0
                    if percent_played >= playcount_minium_percent:
                        list_needs_save = True
                        Logger.debug(f"Filtering watched playback from the list (as {percent_played:.1f}% played over playcount_minium_percent {playcount_minium_percent}%): [{item.pluginlabel}]")
                        paths_to_remove.append(item.path)

            if paths_to_remove:
                list_needs_save = True
                for path in paths_to_remove:
                    self.remove_playbacks_of_path(path)

        # Update resume points with current data from the Kodi library (consider e.g. shared library scenarios)
        for item in self.list:
            if item.dbid:
                library_resume_point = get_resume_point(item.type, item.dbid)
                if library_resume_point != item.resumetime:
                    Logger.debug(f"Retrieved library resume point: {library_resume_point} != existing list resume point {item.resumetime} - updating playback list")
                    list_needs_save = True
                    item.resumetime = library_resume_point

        if list_needs_save:
            self.save_to_file()

    def save_to_file(self) -> None:
        """
        Save the PlaybackList to the PlaybackList file (as JSON)
        """
        Logger.info(f"Saving PlaybackList to file: {self.file}")
        import tempfile
        import time
        directory_name = os.path.dirname(self.file)
        temp_dir = None
        if directory_name:
            xbmcvfs.mkdirs(directory_name)
            temp_dir = directory_name
        with tempfile.NamedTemporaryFile('w', delete=False, encoding='utf-8', dir=temp_dir) as temp_file:
            temp_file.write(self.toJson())
            temporary_name = temp_file.name

        # On Windows, os.replace() can transiently fail with PermissionError if another
        # Switchback process (the service, or an overlapping plugin invocation) has the
        # destination file briefly open - retry a few times rather than letting a routine
        # save crash the caller.
        last_error = None
        for attempt in range(5):
            try:
                os.replace(temporary_name, self.file)
                return
            except PermissionError as e:
                last_error = e
                time.sleep(0.1)
        Logger.error(f"Could not save PlaybackList to file [{self.file}] after retries: {last_error}")
        try:
            os.remove(temporary_name)
        except OSError:
            pass

    def delete_file(self) -> None:
        """
        Deletes the PlaybackList file
        """
        if os.path.exists(self.file):
            Logger.info(f"Deleting PlaybackList file [{self.file}]")
            os.remove(self.file)

    def remove_playbacks_of_path(self, path: str) -> None:
        """
        Remove any playbacks of a given path from the PlaybackList
        """
        self.list = [x for x in self.list if x.path != path]

    def find_playback_by_path(self, path: str) -> Optional[Playback]:
        """
        Return a playback with the matching path if found, otherwise None

        :param path: str The path to search for
        :return: Playback or None: The Playback object if found, otherwise None
        """
        Logger.debug(f"find_playback_by_path: {path}")
        for playback in self.list:
            if playback.path == path:
                Logger.debug(f"Matched playback to [{playback.path}]")
                return playback
        Logger.debug(f"No matching playback for [{path}]")
        return None
