from bossanova808.utilities import *
# noinspection PyPackages
from .store import Store
# noinspection PyPackages
from bossanova808.playback import Playback
import xbmc
import json


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

            # (If only we could just serialise this...)
            item = self.getPlayingItem()

            # If the current playback was Switchback-triggered from a Kodi ListItem (i.e. not PVR, see hack in switchback_plugin.py),
            # retrieve the previously recorded Playback details from the list. Set the Home Window properties that have not yet been set.
            if item.getProperty('Switchback'):
                Logger.debug("Switchback triggered playback, so finding and re-using existing Playback object")
                Store.current_playback = Store.switchback.find_playback_by_path(item.getProperty('Switchback.Path') or item.getPath())
                if Store.current_playback:
                    Logger.debug("Re-using previously stored Playback object (ListItem):", Store.current_playback)
                    # Set these here so they can be used/cleared in onPlaybackFinished below
                    Store.update_home_window_properties_for_playback(Store.current_playback.path)
                    return
                else:
                    Logger.error(f"Switchback triggered playback (ListItem), but no playback found in the list for this path - this shouldn't happen?!", Store.current_playback.path)

            # If the current playback was Switchback-triggered (PVR),
            # retrieve the previously recorded Playback details from the list. The Home Window properties are already set.
            elif HOME_WINDOW.getProperty('Switchback'):
                Store.current_playback = Store.switchback.find_playback_by_path(HOME_WINDOW.getProperty('Switchback.Path'))
                if Store.current_playback:
                    Logger.debug("Re-using previously stored Playback object (PVR):", Store.current_playback)
                    return
                else:
                    Logger.error(f"Switchback triggered playback (PVR PlayMedia), but no playback found in the list for this path - this shouldn't happen?!", Store.current_playback.path)

            # If we got to here, this was not a Switchback-triggered playback, or for some reason we've been unable to find the Playback
            # Create a new Playback object and record the details/
            Logger.debug("Not a Switchback playback, or error retrieving previous Playback, so creating a new Playback object to record details")
            Store.current_playback = Playback()
            Store.current_playback.file = self.getPlayingFile()
            Store.current_playback.label = item.getLabel()
            Store.current_playback.label = item.getLabel2()
            Store.current_playback.path = item.getPath()

            # SOURCE - Kodi Library (...get DBID), PVR, or Non-Library Media?
            Store.current_playback.dbid = int(xbmc.getInfoLabel(f'VideoPlayer.DBID')) if xbmc.getInfoLabel(f'VideoPlayer.DBID') else None
            if Store.current_playback.dbid:
                Store.current_playback.source = "kodi_library"
            elif 'channels' in Store.current_playback.file:
                Store.current_playback.source = "pvr_live"
            elif 'recordings' in Store.current_playback.file:
                Store.current_playback.source = "pvr_recording"
            elif 'http' in Store.current_playback.file:
                Store.current_playback.source = "addon"

            else:
                Logger.info("Not from Kodi library, not PVR, not an http source - must be a non-library media file")
                Store.current_playback.source = "file"

            # TITLE
            if Store.current_playback.source != "pvr_live":
                Store.current_playback.title = xbmc.getInfoLabel(f'VideoPlayer.Title')
            else:
                Store.current_playback.title = xbmc.getInfoLabel('VideoPlayer.ChannelName')

            # DETERMINE THE MEDIA TYPE - not 100% on the logic here...
            if xbmc.getInfoLabel('VideoPlayer.TVShowTitle'):
                Store.current_playback.type = "episode"
                Store.current_playback.tvshowdbid = int(xbmc.getInfoLabel('VideoPlayer.TvShowDBID')) if xbmc.getInfoLabel('VideoPlayer.TvShowDBID') else None
            elif Store.current_playback.dbid:
                Store.current_playback.type = "movie"
            elif xbmc.getInfoLabel('VideoPlayer.ChannelName'):
                Store.current_playback.type = "pvr"
            else:
                Store.current_playback.type = "file"

            # Initialise PLAYBACK TIME and DURATION
            if Store.current_playback.source != "pvr_live":
                Store.current_playback.totaltime = Store.kodi_player.getTotalTime()
                # Times in form 1:35:23 don't seem to work properly, seeing inaccurate durations, so use float from getTotalTime() below instead
                Store.current_playback.duration = Store.kodi_player.getTotalTime()
                # This will get updated as playback progresses, by the monitot but initialise here...
                Store.current_playback.resumetime = Store.kodi_player.getTime()

            # ARTWORK - POSTER, FANART and THUMBNAIL
            Store.current_playback.poster = clean_art_url(xbmc.getInfoLabel('Player.Art(tvshow.poster)') or xbmc.getInfoLabel('Player.Art(poster)') or xbmc.getInfoLabel('Player.Art(thumb)'))
            Store.current_playback.fanart = clean_art_url(xbmc.getInfoLabel('Player.Art(fanart)'))
            Store.current_playback.thumbnail = clean_art_url(xbmc.getInfoLabel('Player.Art(thumb)') or item.getArt('thumb'))

            # OTHER DETAILS
            # Episodes & Movies
            Store.current_playback.year = int(xbmc.getInfoLabel(f'VideoPlayer.Year')) if xbmc.getInfoLabel(f'VideoPlayer.Year') else None
            # Episodes
            Store.current_playback.showtitle = xbmc.getInfoLabel('VideoPlayer.TVShowTitle')
            Store.current_playback.season = int(xbmc.getInfoLabel('VideoPlayer.Season')) if xbmc.getInfoLabel('VideoPlayer.Season') else None
            Store.current_playback.episode = int(xbmc.getInfoLabel('VideoPlayer.Episode')) if xbmc.getInfoLabel('VideoPlayer.Episode') else None
            # PVR Live/Recordings
            Store.current_playback.channelname = xbmc.getInfoLabel('VideoPlayer.ChannelName')
            Store.current_playback.channelnumberlabel = xbmc.getInfoLabel('VideoPlayer.ChannelNumberLabel')
            Store.current_playback.channelgroup = xbmc.getInfoLabel('VideoPlayer.ChannelGroup')

            # NUMBER OF SEASONS
            # If it's a TV Episode, we want the number of seasons so we can force-browse to the appropriate spot after a Swtichback initiated playback
            if Store.current_playback.tvshowdbid:
                json_dict = {
                        "jsonrpc":"2.0",
                        "id":"VideoLibrary.GetSeasons",
                        "method":"VideoLibrary.GetSeasons",
                        "params":{
                                "tvshowid":Store.current_playback.tvshowdbid,
                        },
                }
                query = json.dumps(json_dict)
                properties_json = send_kodi_json(f'Get seasons details for tv show {Store.current_playback.showtitle}', query)
                properties = properties_json['result']
                # {'limits': {'end': 2, 'start': 0, 'total': 2}, 'seasons': [{'label': 'Season 1', 'seasonid': 131094}, {'label': 'Season 2', 'seasonid': 131095}]}
                Store.current_playback.totalseasons = properties['limits']['total']
                # Playback ended by simply running out (i.e. user didn't stop it)

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
        if not Store.current_playback or not Store.current_playback.file:
            Logger.error("onPlaybackFinished with no current playback details available?! ...not recording this playback")
            return

        Logger.debug("onPlaybackFinished with Store.current_playback:", Store.current_playback)
        Logger.debug("onPlaybackFinished with Store.switchback.list: ", Store.switchback.list)

        # Was this a Switchback-initiated playback?
        switchback_playback = HOME_WINDOW.getProperty('Switchback')
        # Clear the property if set, now playback has finished
        HOME_WINDOW.clearProperty('Switchback')
        HOME_WINDOW.clearProperty('Switchback.Path')

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
        playback_to_remove = None
        for previous_playback in Store.switchback.list:
            if previous_playback.path == Store.current_playback.path:
                playback_to_remove = previous_playback
                break
        if playback_to_remove:
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
        Store.update_home_window_properties_for_context_menu()
