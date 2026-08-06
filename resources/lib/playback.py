import os
import json
from dataclasses import dataclass
from typing import List, Optional

import xbmcgui
import xbmcvfs

# noinspection PyPackages
from bossanova808.playback import Playback
# noinspection PyPackages
from bossanova808.utilities import get_resume_point, get_playcount, get_advancedsetting
# noinspection PyPackages
from bossanova808.logger import Logger
# noinspection PyUnresolvedReferences
from infotagger.listitem import ListItemInfoTag


@dataclass
class SwitchbackPlayback(Playback):
    """
    A Playback, plus the Switchback-specific display/ListItem concerns (not needed by other
    consumers of the shared Playback class, and create_list_item_from_playback() needs
    script.module.infotagger, which is a Switchback-only dependency).
    """

    @property
    def pluginlabel(self) -> str:
        """
        Create a more full label, e.g. Showname (2x03) - Episode title

        :return: The Switchback label for display in the plugin list
        """
        label = self.title or self.label or self.channelname or (os.path.basename(self.path) if self.path else None) or "Unknown"
        if self.showtitle:
            if (self.season is not None and self.season >= 0) and (self.episode is not None and self.episode >= 0):
                label = f"{self.showtitle} ({self.season}x{self.episode:02d}) - {self.title or label}"
            elif self.season is not None and self.season >= 0:
                label = f"{self.showtitle} ({self.season}x?) - {self.title or label}"
            else:
                label = f"{self.showtitle} - {self.title or label}"
        elif self.channelname:
            if self.source == "pvr_live":
                label = f"{self.channelname} (PVR Live)"
            else:
                label = f"{label} (PVR Recording {self.channelname})"

        if self.source == "addon":
            label = f"{label} (* Add-on)"
        return label

    @property
    def pluginlabel_short(self) -> str:
        """
        Create a shorter label, e.g. Showname (2x03)
        """
        label = self.title or self.label or self.channelname or (os.path.basename(self.path) if self.path else None) or "Unknown"
        if self.showtitle:
            if (self.season is not None and self.season >= 0) and (self.episode is not None and self.episode >= 0):
                label = f"{self.showtitle} ({self.season}x{self.episode:02d})"
            elif self.season is not None and self.season >= 0:
                label = f"{self.showtitle} ({self.season}x?)"
            else:
                label = f"{self.showtitle}"

        return label

    # noinspection PyMethodMayBeStatic
    def create_list_item_from_playback(self) -> xbmcgui.ListItem:
        """
        Create a Kodi ListItem object from a Playback object

        :return: ListItem: a Kodi ListItem object constructed from the Playback object
        """

        Logger.debug("Creating list item from playback:", self)

        list_item = xbmcgui.ListItem(label=self.pluginlabel, path=self.file if self.source not in ["addon", "pvr_live"] else self.path)
        art = {key:value for key, value in {"thumb":self.thumbnail, "poster":self.poster, "fanart":self.fanart, "icon":self.icon}.items() if value}
        if art:
            list_item.setArt(art)
        list_item.setProperty('IsPlayable', 'true')

        # PVR channels are not really videos! See: https://forum.kodi.tv/showthread.php?tid=381623&pid=3232826#pid3232826
        # So that's all we need to do for PVR playbacks
        if self.source == "pvr_live":
            return list_item

        # Otherwise, it's an episode/movie/file etc...set the InfoVideoTag stuff
        tag = ListItemInfoTag(list_item, "video")
        duration_seconds = None
        if self.duration is not None:
            duration_seconds = self.duration
        elif self.totaltime is not None:
            duration_seconds = self.totaltime

        # Infotagger seems the best way to do this currently as is well tested
        # I found directly setting things on InfoVideoTag to be buggy/inconsistent
        infolabels = {
                'mediatype':self.type,
                'dbid':self.dbid,
                'title':self.title,
                'path':self.path,
                'year':self.year,
                'tvshowtitle':self.showtitle,
                'episode':self.episode,
                'season':self.season,
                'duration':duration_seconds,
        }
        tag.set_info(infolabels)

        # Required, otherwise immediate Switchback mode won't resume properly
        # These keys are correct, even if CodeRabbit says they are not - see https://github.com/jurialmunkey/script.module.infotagger/blob/f138c1dd7201a8aff7541292fbfc61ed7b3a9aa1/resources/modules/infotagger/listitem.py#L204
        tag.set_resume_point({'ResumeTime':float(self.resumetime or 0.0), 'TotalTime':float(self.totaltime or 0.0)})
        if self.tvshowdbid:
            list_item.setProperty('tvshowdbid', str(self.tvshowdbid))

        return list_item


@dataclass
class PlaybackList:
    """
    A list of Playback objects, with some helper methods.  Stored both in memory (accessible via .list) and on disk (filename at .file)
    Is a standard Python list, so can be iterated over, indexed, etc., and of course, all standard list methods are available.

    To create a PlaybackList::
        switchback = PlaybackList([], xbmcvfs.translatePath(os.path.join(PROFILE, "switchback_list.json")))
    """
    list: List[SwitchbackPlayback]
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
                    self.list.append(SwitchbackPlayback(**playback))

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

    def find_playback_by_path(self, path: str) -> Optional[SwitchbackPlayback]:
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
