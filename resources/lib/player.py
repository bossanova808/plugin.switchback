from bossanova808.utilities import *
from resources.lib.store import Store
from bossanova808.playback import Playback


class KodiPlayer(xbmc.Player):
    """
    This class represents/monitors the Kodi video player
    """

    # noinspection PyUnusedLocal
    def __init__(self, *args):
        xbmc.Player.__init__(self)
        Logger.debug('Player __init__')

    # Use on AVStarted (vs Playback started) we want to record a playback only if the user actually _saw_ a video...
    def onAVStarted(self):
        Logger.info('onAVStarted')

        # KISS - only support video...
        if xbmc.getCondVisibility('Player.HasVideo'):

            # (If only we could just serialise a Kodi ListItem...)
            item = self.getPlayingItem()
            file = self.getPlayingFile()

            # If the current playback was Switchback-triggered from a Kodi ListItem (i.e. not PVR, see hack in switchback_plugin.py),
            # retrieve the previously recorded Playback details from the list. Set the Home Window properties that have not yet been set.
            if item.getProperty('Switchback') or HOME_WINDOW.getProperty('Switchback'):
                Logger.debug("Switchback triggered playback, so finding and re-using existing Playback object")
                Logger.debug("Home Window property is:", HOME_WINDOW.getProperty('Switchback'))
                Logger.debug("ListItem property is:", item.getProperty('Switchback'))
                path_to_find = HOME_WINDOW.getProperty('Switchback') or item.getProperty('Switchback') or item.getPath()
                Store.current_playback = Store.switchback.find_playback_by_path(path_to_find)
                if Store.current_playback:
                    Logger.debug("Re-using previously stored Playback object:", Store.current_playback)
                    # We won't have access to the listitem once playback is finishes, so set a property now so it can be used/cleared in onPlaybackFinished below
                    Store.update_home_window_switchback_property(Store.current_playback.path)
                    return
                else:
                    Logger.error(f"Switchback triggered playback, but no playback found in the list for this path - this shouldn't happen?!", path_to_find)

            # If we got to here, this was not a Switchback-triggered playback, or for some reason we've been unable to find the Playback
            # Create a new Playback object and record the details/
            Logger.debug("Not a Switchback playback, or error retrieving previous Playback, so creating a new Playback object to record details")
            Store.current_playback = Playback()
            Store.current_playback.file = file
            Store.current_playback.update_playback_details_from_listitem(item)

    def onPlayBackEnded(self):
        self.onPlaybackFinished()

    # User stopped playback
    def onPlayBackStopped(self):
        self.onPlaybackFinished()

    @staticmethod
    def onPlaybackFinished():
        """
        Playback has finished - we need to update the PlaybackList and save it to file, and, if the user desires, force Kodi to browse to the appropriate show/season

        :return:
        """
        if not Store.current_playback or not Store.current_playback.path:
            Logger.error("onPlaybackFinished with no current playback details available?! ...not recording this playback")
            return

        Logger.debug("onPlaybackFinished with Store.current_playback:", Store.current_playback)
        Logger.debug("onPlaybackFinished with Store.switchback.list: ", Store.switchback.list)

        # Was this a Switchback-initiated playback?
        # (This property was set above in onAVStarted if the ListItem property was set, or explicitly in the PVR HACK! section in switchback_plugin.py)
        switchback_playback = HOME_WINDOW.getProperty('Switchback')
        # Clear the property if set, now playback has finished
        HOME_WINDOW.clearProperty('Switchback')

        # If we Switchbacked to an episode, force Kodi to browse to the Show/Season
        if switchback_playback == 'true':
            if Store.current_playback.type == "episode":
                Logger.info(f"Force browsing to tvshow/season of just finished playback")
                Logger.debug(f'flatten tvshows {Store.flatten_tvshows} totalseasons {Store.current_playback.totalseasons} dbid {Store.current_playback.dbid} tvshowdbid {Store.current_playback.tvshowdbid}')
                # Default: Browse to the show
                window = f'videodb://tvshows/titles/{Store.current_playback.tvshowdbid}'
                # If the user has Flatten TV shows set to 'never' (=0), browse to the actual season
                if Store.flatten_tvshows == 0:
                    window += f'/{Store.current_playback.season}'
                # Else if the user has Flatten TV shows set to 'If Only One Season' and there is indeed more than one season, browse to the actual season
                elif Store.flatten_tvshows == 1 and Store.current_playback.totalseasons > 1:
                    window += f'/{Store.current_playback.season}'

                xbmc.executebuiltin(f'ActivateWindow(Videos,{window},return)')
            else:
                # TODO - is is possible to force Kodi to go to movies and focus a specific movie?
                pass

        # This rather long-windeed approach is used to keep ALL the details recorded from the original playback
        # (in case they don't make it through when the playback is Switchback initiated - as sometimes seems to be the case)

        # for previous_playback in Store.switchback.list:
        #     if previous_playback.path == Store.current_playback.path:
        #         playback_to_remove = previous_playback
        #         break

        playback_to_remove = Store.switchback.find_playback_by_path(Store.current_playback.path)
        if playback_to_remove:
            Logger.debug("Shuffling list order")
            # Remove it from its current position
            Store.switchback.list.remove(playback_to_remove)
            # Update with the current playback times
            if Store.current_playback.source != "pvr_live":
                playback_to_remove.update({'resumetime': Store.current_playback.resumetime, 'totaltime': Store.current_playback.totaltime})
            # Re-insert at the top of the list
            Store.switchback.list.insert(0, playback_to_remove)
        else:
            Store.switchback.list.insert(0, Store.current_playback)

        # Trim the list to the max length
        Store.switchback.list = Store.switchback.list[0:Store.maximum_list_length]

        # Finally, save the updated PlaybackList
        Logger.debug("Saving updated Store.switchback.list:", Store.switchback.list)
        Store.switchback.save_to_file()
        # & make sure the context menu items are updated
        Store.update_switchback_context_menu()
