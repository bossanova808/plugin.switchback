import sys
from urllib.parse import parse_qs

# noinspection PyUnresolvedReferences
import xbmc
import xbmcgui
import xbmcplugin

from resources.lib.store import Store
from bossanova808.constants import TRANSLATE, ADDON_ICON
from bossanova808.logger import Logger
from bossanova808.notify import Notify


# PVR HACK!
# ListItems and setResolvedUrl does not handle PVR links properly, see https://forum.kodi.tv/showthread.php?tid=381623
# (TODO: remove this hack when setResolvedUrl/ListItems are fixed to properly handle PVR links in listitem.path)
def pvr_hack(path):
    # Kodi is jonesing for one of these, so give it the sugar it needs, see: https://forum.kodi.tv/showthread.php?tid=381623&pid=3232778#pid3232778
    xbmcplugin.setResolvedUrl(int(sys.argv[1]), False, xbmcgui.ListItem())
    xbmc.PlayList(xbmc.PLAYLIST_VIDEO).clear()
    # Get the full details from our stored playback
    # pvr_playback = Store.switchback.find_playback_by_path(path)
    builtin = f'PlayMedia("{path}"'
    if "pvr://recordings" in path:
        builtin += f',resume'
    builtin += ")"
    Logger.debug("Work around PVR links not being handled by ListItem/setResolvedUrl - use PlayMedia:", builtin)
    # No ListItem to set a property on here, so set on the Home Window instead
    Store.update_home_window_switchback_property(path)
    xbmc.executebuiltin(builtin)


# noinspection PyUnusedLocal
def run(args):
    Logger.start("(Plugin)")
    Store()

    plugin_instance = int(sys.argv[1])
    xbmcplugin.setContent(plugin_instance, 'video')

    parsed_arguments = parse_qs(sys.argv[2][1:])
    Logger.debug(parsed_arguments)
    mode = parsed_arguments.get('mode', None)
    if mode:
        Logger.info(f"Switchback mode: {mode}")
    else:
        Logger.info("Switchback mode: default - generate 'folder' of items")

    # Force an update of the Switchback list from disk, in case of changes via the service side of things.
    Store.switchback.load_or_init()

    # Switchback mode - easily swap between switchback.list[0] and switchback.list[1]
    # If there's only one item in the list, then resume playing that item
    if mode and mode[0] == "switchback":
        try:
            if len(Store.switchback.list) == 1:
                switchback_to_play = Store.switchback.list[0]
                Logger.info(f"Playing Switchback[0] - path [{Store.switchback.list[0].path}]")
            else:
                switchback_to_play = Store.switchback.list[1]
                Logger.info(f"Playing Switchback[1] - path [{Store.switchback.list[1].path}]")
            Logger.info(f"{switchback_to_play.pluginlabel}")

            # Notify the user and set properties so we can identify this playback as having been originated from a Switchback
            Notify.kodi_notification(f"{switchback_to_play.pluginlabel}", 3000, ADDON_ICON)
            list_item = switchback_to_play.create_list_item_from_playback(offscreen=True)
            # # (TODO: remove this hack when setResolvedUrl/ListItems are fixed to properly handle PVR links in listitem.path)
            if "pvr://" in switchback_to_play.path:
                pvr_hack(switchback_to_play.path)
                return
            else:
                list_item.setProperty('Switchback', switchback_to_play.path)
                xbmcplugin.setResolvedUrl(plugin_instance, True, list_item)

        except IndexError:
            Notify.error(TRANSLATE(32007))
            Logger.error("No Switchback found to play")

    # Delete an item from the Switchback list - e.g. if it is not playing back properly from Switchback
    if mode and mode[0] == "delete":
        index_to_remove = parsed_arguments.get('index', None)
        if index_to_remove:
            Logger.info(f"Deleting playback {index_to_remove[0]} from Switchback list")
            Store.switchback.list.remove(Store.switchback.list[int(index_to_remove[0])])
            # Save the updated list and then reload it, just to be sure
            Store.switchback.save_to_file()
            Store.switchback.load_or_init()
            Store.update_switchback_context_menu()
            # Force refresh the Kodi list display
            Logger.debug("Force refreshing the container, so Kodi immediately displays the updated Switchback list")
            xbmc.executebuiltin("Container.Refresh")

    # (TODO: remove this hack when setResolvedUrl/ListItems are fixed to properly handle PVR links in listitem.path)
    elif mode and mode[0] == "pvr_hack":
        path_values = parsed_arguments.get('path')
        if not path_values:
            Logger.error("Missing 'path' parameter for pvr_hack")
            return
        path = path_values[0]
        Logger.debug(f"Triggering PVR Playback hack for {path}")
        pvr_hack(path)

    # Default mode - show the whole Switchback List (each of which has a context menu option to delete itself)
    else:
        for index, playback in enumerate(Store.switchback.list[0:Store.maximum_list_length]):
            list_item = playback.create_list_item_from_playback()
            # Add delete option to this item
            list_item.addContextMenuItems([(TRANSLATE(32004), "RunPlugin(plugin://plugin.switchback?mode=delete&index=" + str(index) + ")")])
            # For detecting Switchback playbacks (in player.py)
            list_item.setProperty('Switchback', playback.path)
            # (TODO: remove this hack when setResolvedUrl/ListItems are fixed to properly handle PVR links in listitem.path)
            # Don't use playback.path here, use list_item.getPath(), as the path may now have the plugin proxy url for PVR live playback
            Logger.debug(f"^^^ Adding directory Item: {list_item.getPath()}")
            xbmcplugin.addDirectoryItem(plugin_instance, list_item.getPath(), list_item)

        xbmcplugin.endOfDirectory(plugin_instance, cacheToDisc=False)

    # And we're done...
    Logger.stop("(Plugin)")
