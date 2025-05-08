from urllib.parse import parse_qs

import xbmcplugin
from bossanova808.notify import Notify
from bossanova808.playback import Playback
from bossanova808.utilities import *
# noinspection PyPackages
from .store import Store
from infotagger.listitem import ListItemInfoTag


def create_kodi_list_item_from_playback(playback: Playback, index=None, offscreen=False):
    Logger.info(f"Creating list item from playback of {playback.pluginlabel}")
    Logger.info(playback)
    url = playback.path
    # url = playback.file
    # if playback.source == 'addon':
    #     Logger.debug(f"Playback is an addon, so using the path instead of the file for the url: {playback.path}")
    #     url = playback.path
    list_item = xbmcgui.ListItem(label=playback.pluginlabel, path=url, offscreen=offscreen)
    tag = ListItemInfoTag(list_item, "video")
    # Infotagger seems the best way to do this currently as is well tested
    # I found directly setting things on InfoVideoTag to be buggy/inconsistent
    infolabels = {
            'mediatype': playback.type,
            'dbid': playback.dbid if playback.type != 'episode' else playback.tvshowdbid,
            # InfoTagger throws a Key Error on this?
            # 'tvshowdbid': playback.tvshowdbid or None,
            'title': playback.title,
            'path': playback.path,
            'year': playback.year,
            'tvshowtitle': playback.showtitle,
            'episode': playback.episode,
            'season': playback.season,
            'duration': playback.totaltime,
    }
    tag.set_info(infolabels)
    if "pvr" not in playback.source:
        tag.set_resume_point({'ResumeTime':playback.resumetime, 'TotalTime':playback.totaltime})
    list_item.setArt({"thumb": playback.thumbnail})
    list_item.setArt({"poster": playback.poster})
    list_item.setArt({"fanart": playback.fanart})
    list_item.setProperty('IsPlayable', 'true')

    # index can be zero, so in this case, must explicitly check against None!
    if index is not None:
        list_item.addContextMenuItems([(LANGUAGE(32004), "RunPlugin(plugin://plugin.switchback?mode=delete&index=" + str(index) + ")")])

    return list_item


# noinspection PyUnusedLocal
def run(args):
    plugin_instance = int(sys.argv[1])

    Logger.start("(Plugin)")
    Store()
    xbmcplugin.setContent(plugin_instance, 'video')
    parsed_arguments = parse_qs(sys.argv[2][1:])
    Logger.debug(parsed_arguments)
    mode = parsed_arguments.get('mode', None)
    Logger.info(f"Mode: {mode}")

    # Switchback mode - easily swap between switchback.list[0] and switchback.list[1]
    # If there's only one item in the list, then resume that
    if mode and mode[0] == "switchback":
        try:
            if len(Store.switchback.list) == 1:
                switchback_to_play = Store.switchback.list[0]
                Logger.info(f"Playing Switchback[0] - file (Store.switchback.list[0])")
            else:
                switchback_to_play = Store.switchback.list[1]
                Logger.info(f"Playing Switchback[1] - file (Store.switchback.list[1])")
            Logger.info(f"{switchback_to_play.pluginlabel}")
            list_item = create_kodi_list_item_from_playback(switchback_to_play, offscreen=True)
            Notify.kodi_notification(f"{switchback_to_play.pluginlabel}", 3000, ADDON_ICON)
            # Set a property indicating this is a Switchback playback, so we can force browse later at the end of this playback
            HOME_WINDOW.setProperty('Switchback', 'true')
            HOME_WINDOW.setProperty('Switchback.Path', switchback_to_play.path)
            xbmcplugin.setResolvedUrl(plugin_instance, True, list_item)
        except IndexError:
            Notify.error(LANGUAGE(32007))
            Logger.error("No Switchback found to play")

    # Delete an item from the Switchback list - e.g. if it is not playing back properly from Switchback
    if mode and mode[0] == "delete":
        index_to_remove = parsed_arguments.get('index', None)
        if index_to_remove:
            Logger.info(f"Deleting playback {index_to_remove[0]} from Switchback list")
            Store.switchback.list.remove(Store.switchback.list[int(index_to_remove[0])])
            Store.switchback.save_to_file()
            Store.update_home_window_properties()
            # Force refresh the list
            Logger.debug("Force refresh the container, so Kodi displays the latest Switchback list")
            xbmc.executebuiltin("Container.Refresh")

    # Default mode - show the whole Switchback List
    else:
        for index, playback in enumerate(Store.switchback.list[0:Store.maximum_list_length]):
            url = playback.path
            # url = playback.file
            # if playback.source == 'addon':
            #     url = playback.path
            list_item = create_kodi_list_item_from_playback(playback, index=index)
            xbmcplugin.addDirectoryItem(plugin_instance, url, list_item)

        xbmcplugin.endOfDirectory(plugin_instance, cacheToDisc=False)

    # And we're done...
    Logger.stop("(Plugin)")
