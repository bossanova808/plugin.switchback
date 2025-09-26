import sys
from urllib.parse import parse_qs

# noinspection PyUnresolvedReferences
import xbmc
import xbmcplugin

from resources.lib.store import Store
from bossanova808.constants import TRANSLATE, HOME_WINDOW
from bossanova808.logger import Logger
from bossanova808.notify import Notify


def run():
    Logger.start("(Plugin)")
    # This also forces an update of the Switchback list from disk, in case of changes via the service side of things.
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

    # Switchback mode - easily swap between switchback.list[0] and switchback.list[1]
    # If there's only one item in the list, then resume playing that item
    if mode and mode[0] == "switchback":
        try:
            if len(Store.switchback.list) == 1:
                switchback_to_play = Store.switchback.list[0]
                Logger.info(f"Playing Switchback[0] - path [{Store.switchback.list[0].path}]")
                Logger.info(f"Playing Switchback[0] - file [{Store.switchback.list[0].file}]")
            else:
                switchback_to_play = Store.switchback.list[1]
                Logger.info(f"Playing Switchback[1] - path [{Store.switchback.list[1].path}]")
                Logger.info(f"Playing Switchback[1] - file [{Store.switchback.list[1].file}]")

            Logger.info(f"Switching back to: {switchback_to_play.pluginlabel} - path [{switchback_to_play.path}] file [{switchback_to_play.file}]")

        except IndexError:
            Notify.error(TRANSLATE(32007))
            Logger.error("No Switchback found to play")
            return

        # Notify the user and set properties so we can identify this playback as having been originated from a Switchback
        Notify.kodi_notification(f"{switchback_to_play.pluginlabel}", 3000, switchback_to_play.poster)
        list_item = switchback_to_play.create_list_item_from_playback(offscreen=True)
        list_item.setProperty('Switchback', switchback_to_play.path)
        HOME_WINDOW.setProperty('Switchback', switchback_to_play.path)
        xbmcplugin.setResolvedUrl(plugin_instance, True, list_item)
        return

    # Delete an item from the Switchback list - e.g. if it is not playing back properly from Switchback
    if mode and mode[0] == "delete":
        index_values = parsed_arguments.get('index')
        if index_values:
            try:
                idx = int(index_values[0])
            except (ValueError, TypeError):
                Logger.error("Invalid 'index' parameter for delete:", index_values)
                return
            if 0 <= idx < len(Store.switchback.list):
                Logger.info(f"Deleting playback {idx} from Switchback list")
                Store.switchback.list.pop(idx)
            else:
                Logger.error("Index out of range for delete:", idx)
                return
            # Save the updated list and then reload it, just to be sure
            Store.switchback.save_to_file()
            Store.switchback.load_or_init()
            Store.update_switchback_context_menu()
            # Force refresh the Kodi list display
            Logger.debug("Force refreshing the container, so Kodi immediately displays the updated Switchback list")
            xbmc.executebuiltin("Container.Refresh")

    # Default mode - show the whole Switchback List (each of which has a context menu option to delete itself)
    else:
        for index, playback in enumerate(Store.switchback.list[0:Store.maximum_list_length]):
            list_item = playback.create_list_item_from_playback()
            # Add delete option to this item
            list_item.addContextMenuItems([(TRANSLATE(32004), "RunPlugin(plugin://plugin.switchback?mode=delete&index=" + str(index) + ")")])
            # For detecting Switchback playbacks (in player.py)
            list_item.setProperty('Switchback', playback.path)
            xbmcplugin.addDirectoryItem(plugin_instance, playback.file if playback.source != "addon" else playback.path, list_item)

        xbmcplugin.endOfDirectory(plugin_instance, cacheToDisc=False)

    # And we're done...
    Logger.stop("(Plugin)")
