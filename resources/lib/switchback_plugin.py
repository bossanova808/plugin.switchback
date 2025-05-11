from urllib.parse import parse_qs

import xbmcplugin
from bossanova808.notify import Notify
from bossanova808.playback import Playback
from bossanova808.utilities import *
# noinspection PyPackages
from .store import Store


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
        Logger.info(f"Mode: {mode}")
    else:
        Logger.info("Mode: default, generate plugin list of items")

    # Switchback mode - easily swap between switchback.list[0] and switchback.list[1]
    # If there's only one item in the list, then resume that
    if mode and mode[0] == "switchback":
        try:
            if len(Store.switchback.list) == 1:
                switchback_to_play = Store.switchback.list[0]
                Logger.info(f"Playing Switchback[0] - path [{Store.switchback.list[0].path}]")
            else:
                switchback_to_play = Store.switchback.list[1]
                Logger.info(f"Playing Switchback[1] - path [{Store.switchback.list[1].path}]")
            Logger.info(f"{switchback_to_play.pluginlabel}")

            # setResolvedUrl does not handle PVR links properly, see https://forum.kodi.tv/showthread.php?tid=381623 ...
            if "pvr://" not in switchback_to_play.path:
                list_item = switchback_to_play.create_list_item(offscreen=True)
                Notify.kodi_notification(f"{switchback_to_play.pluginlabel}", 3000, ADDON_ICON)
                # Set a property indicating this is a Switchback playback, so we can force browse later at the end of this playback
                xbmcplugin.setResolvedUrl(plugin_instance, True, list_item)
            # ...so forced into a direct approach here
            else:
                command = f'PlayMedia("{switchback_to_play.path}",resume)'
                Logger.debug("Working around PVR links not being handled by setResolvedUrl, using PlayMedia instead")
                Logger.debug(command)
                xbmc.executebuiltin(command)

            # Set properties so we can identify this playback as having been originated from a Switchback
            HOME_WINDOW.setProperty('Switchback', 'true')
            HOME_WINDOW.setProperty('Switchback.Path', switchback_to_play.path)

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
            list_item = playback.create_list_item()
            # Add the delete from list option
            list_item.addContextMenuItems([(LANGUAGE(32004), "RunPlugin(plugin://plugin.switchback?mode=delete&index=" + str(index) + ")")])
            xbmcplugin.addDirectoryItem(plugin_instance, playback.path, list_item)

        xbmcplugin.endOfDirectory(plugin_instance, cacheToDisc=False)

    # And we're done...
    Logger.stop("(Plugin)")
