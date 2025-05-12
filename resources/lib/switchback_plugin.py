from urllib.parse import parse_qs

import xbmcplugin

# noinspection PyPackages
from .store import Store
from bossanova808.utilities import *
from bossanova808.notify import Notify


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
        Logger.info("Mode: default - generate 'folder' of items")

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
            HOME_WINDOW.setProperty('Switchback', 'true')
            HOME_WINDOW.setProperty('Switchback.Path', switchback_to_play.path)

            # setResolvedUrl does not handle PVR links properly, see https://forum.kodi.tv/showthread.php?tid=381623
            # (TODO: remove this hack when setResolvedUrl is fixed to handle PVR links)
            if "pvr://" in switchback_to_play.path:
                # Kodi is jonesing for one of these, so give it the sugar it needs, see: https://forum.kodi.tv/showthread.php?tid=381623&pid=3232778#pid3232778
                xbmcplugin.setResolvedUrl(int(sys.argv[1]), False, xbmcgui.ListItem())
                # ...but then directly play the PVR channel/recording
                built_in = f'PlayMedia("{switchback_to_play.path}",resume)'
                Logger.debug("Working around PVR links not being handled by setResolvedUrl, using PlayMedia instead:", built_in)
                # Can't use a property on the ListItem here, so set them on the Home Window instead
                Store.update_home_window_properties_for_playback(switchback_to_play.path)
                xbmc.executebuiltin(built_in)
            # For all things setResolvedUrl can handle...
            else:
                list_item = switchback_to_play.create_list_item(offscreen=True)
                list_item.setProperty('Switchback', 'true')
                list_item.setProperty('Switchback.Path', switchback_to_play.path)
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
            Store.switchback.save_to_file()
            Store.update_home_window_properties_for_context_menu()
            # Force refresh the list
            Logger.debug("Force refresh the container, so Kodi immediately displays the updated Switchback list")
            xbmc.executebuiltin("Container.Refresh")

    # Default mode - show the whole Switchback List (each of which has context menu option to delete itself)
    else:
        for index, playback in enumerate(Store.switchback.list[0:Store.maximum_list_length]):
            list_item = playback.create_list_item()
            list_item.addContextMenuItems([(LANGUAGE(32004), "RunPlugin(plugin://plugin.switchback?mode=delete&index=" + str(index) + ")")])
            list_item.setProperty('Switchback', 'true')
            list_item.setProperty('Switchback.Path', playback.path)
            xbmcplugin.addDirectoryItem(plugin_instance, playback.path, list_item)

        xbmcplugin.endOfDirectory(plugin_instance, cacheToDisc=False)

    # And we're done...
    Logger.stop("(Plugin)")
