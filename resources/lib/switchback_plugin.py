from urllib.parse import parse_qs

import xbmc
import xbmcplugin
import json
from bossanova808.constants import *
from bossanova808.logger import Logger
from bossanova808.notify import Notify
from bossanova808.utilities import *
# noinspection PyPackages
from .store import Store
from infotagger.listitem import ListItemInfoTag


def create_kodi_list_item_from_playback(playback, index=None, offscreen=False):
    Logger.info("Creating list item from playback")
    Logger.info(playback)

    # library item?  If user has asked us to, filter out if watched
    if playback.dbid or playback.tvshowdbid:
        if Store.filter_watched:
            # Get watched status from Kodi DB
            pass
        
    label = playback.title
    if playback.showtitle:
        if playback.season and playback.episode:
            if playback.season >= 0 and playback.episode >= 0:
                label = f"{playback.showtitle} ({playback.season}x{playback.episode:02d}) - {playback.title}"
            elif playback.season >= 0:
                label = f"{playback.showtitle} ({playback.season}x?) - {playback.title}"
        else:
            label = f"{playback.showtitle} - {playback.title}"
    elif playback.channelname:
        if playback.source == "pvr.live":
            label = f"PVR Live - Channel {playback.channelname}"
        else:
            label = f"PVR Recording - Channel {playback.channelname} - {playback.title}"
    elif playback.album:
        label = f"{playback.artist} - {playback.album} - {playback.tracknumber:02d}. {playback.title}"
    elif playback.artist:
        label = f"{playback.artist} - {playback.title}"

    list_item = xbmcgui.ListItem(label=label, path=playback.path, offscreen=offscreen)
    tag = ListItemInfoTag(list_item, 'video')
    infolabels = {
            'mediatype': playback.type,
            'dbid': playback.dbid if playback.type != 'episode' else playback.tvshowdbid,
            'tvshowdbid': playback.tvshowdbid,
            'title': playback.title,
            'year': playback.year,
            'tvshowtitle': playback.showtitle,
            'episode': playback.episode,
            'season': playback.season,
            'album': playback.album,
            'artist': [playback.artist],
            'tracknumber': playback.tracknumber,
            'duration': playback.totaltime,
    }
    # Infotagger seems the best way to do this currently as is well tested
    # I found directly setting things on InfoVideoTag to be buggy/inconsistent
    tag.set_info(infolabels)
    list_item.setPath(path=playback.path)
    list_item.setArt({"thumbnail": playback.thumbnail})
    list_item.setArt({"poster": playback.poster})
    list_item.setArt({"fanart": playback.fanart})
    # Auto resumes just won't work without these, even though they are deprecated...
    list_item.setProperty('TotalTime', str(playback.totaltime))
    list_item.setProperty('ResumeTime', str(playback.resumetime))
    list_item.setProperty('StartOffset', str(playback.resumetime))
    list_item.setProperty('IsPlayable', 'true')

    # index can be zero, so in this case, must explicitly check against None!
    if index is not None:
        list_item.addContextMenuItems([(LANGUAGE(32004), "RunPlugin(plugin://plugin.switchback?mode=delete&index=" + str(index) + ")")])

    return list_item


def run(args):
    plugin_instance = int(sys.argv[1])

    footprints()
    Logger.info("(Plugin)")
    Store()

    xbmcplugin.setContent(plugin_instance, 'mixed')

    parsed_arguments = parse_qs(sys.argv[2][1:])
    Logger.info(parsed_arguments)
    mode = parsed_arguments.get('mode', None)
    Logger.info(f"Mode: {mode}")

    # Switchback mode - easily swap between switchback_list[0] and switchback_list[1]
    if mode and mode[0] == "switchback":
        try:
            switchback = Store.switchback_list[1]
            Logger.info(f"Playing previous path (Store.switchback_list[1]) {switchback.path}")
            list_item = create_kodi_list_item_from_playback(switchback, offscreen=True)
            if list_item:
                Notify.kodi_notification(f"{list_item.getLabel()}", 3000, ADDON_ICON)
                # Set a property so we can potentially force browse later at the end of playback for this type of playback
                HOME_WINDOW.setProperty('Switchback', 'true')
                xbmcplugin.setResolvedUrl(plugin_instance, True, list_item)
            else:
                Notify.error("Could not Switchback, see logs")
                Logger.error("Could not Switchback, see logs")
        except IndexError:
            Notify.error("No previous item found to play")
            Logger.error("No previous item found to play")

    # Delete an item from the Switchback list - e.g. if it is not playing back properly from Switchback
    if mode and mode[0] == "delete":
        index_to_remove = parsed_arguments.get('index', None)
        if index_to_remove:
            Logger.info(f"Deleting playback {index_to_remove[0]} from Switchback List")
            Store.switchback_list.remove(Store.switchback_list[int(index_to_remove[0])])
            Store.save_switchback_list()
            # Force refresh the list
            Logger.debug("Force refresh the container so we see the latest Switchback list")
            xbmc.executebuiltin("Container.Refresh")

    # Default mode - display the Switchback List
    else:
        for index, playback in enumerate(Store.switchback_list[0:Store.maximum_list_length]):
            list_item = create_kodi_list_item_from_playback(playback, index=index)
            xbmcplugin.addDirectoryItem(plugin_instance, playback.file, list_item)

        xbmcplugin.endOfDirectory(plugin_instance)

    # And we're done...
    footprints(startup=False)
