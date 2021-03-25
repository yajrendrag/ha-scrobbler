#!/usr/local/bin/python3.9

import json
import time
import pylast
import sys
import re
import datetime
import shutil
from types import SimpleNamespace
import httpx
from bs4 import BeautifulSoup
import logging

# set up account constants
API_KEY = "YOUR_LASTFM_API_KEY_HERE"
API_SECRET = "YOUR_LASTFM_API_SECRET_HERE"
SESSION_KEY = "YOUR_LAST_FM_SESSION_KEY_HERE"
USER_NAME = "YOUR_LASTFM_USERNAME_HERE"

# program globals
LOGFILE = '/full/path/to/ha-scrobble.log_here'
STACKFILE = '/full/path/to/a/stackfile.txt_here'
SUFFIX_LIST = ('.flac', '.mp3') #list of music file suffixes - edit as needed
EMPTYFILE = '/dev/null' # should be ok as is
LFM_URL = 'http://ws.audioscrobbler.com/2.0/' # should be ok as is

logging.basicConfig(filename=LOGFILE, filemode='a', level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')

try:
    stack = open(STACKFILE, 'r+')
except:
    logging.error(f"error opening {STACKFILE}\n")
    sys.exit(1)

def main():
    # get media metadata
    args = sys.argv[1:]
    media = args[0]
    try:
        media_json = BeautifulSoup(media, features="html.parser").get_text()
    except:
        logging.error(f"improperly formatted media data, exiting\n{media}\n")
        sys.exit(1)

    network = pylast.LastFMNetwork(
        api_key=API_KEY, api_secret=API_SECRET, session_key=SESSION_KEY)

    # parse event data from both old and new events captured
    # event data may not have all of the details which will
    # be resolved in next outside_temp
    new = event(media_json,'new', network)
    new_data, new_state, new_time = new.get_event_info()
    old = event(media_json,'old', network)
    old_data, old_state, old_time = old.get_event_info()

    if new_state.state != "playing" and old_state.state != "playing":
        logging.error(f"error - neither new or old states are playing\n")
        sys.exit(1)
    if new_data.content_type != "music" and new_state.state == "playing":
        logging.error(f"exiting - media being played is not music\n")
        sys.exit(1)

    # parse track details from old and new events - provides
    # any missing details from lastFM that simple event
    # parsing failed to capture
    if new_state.state == "playing" or new_state.player.find("Plex") == -1 :
        new_track = new.get_missing_track_info()

    # pop track from stack..
    try:
        ptrack=json.load(stack, object_hook=lambda d: SimpleNamespace(**d))
        ar = network.search_for_artist(
            ptrack.data.artist).get_next_page()[1] #lfm updatenowplaying better?
        stack.close()
    except (json.decoder.JSONDecodeError, IndexError):
        #stack empty or non-existent artist - push new_track on stack
        ptrack = new_track
        push_stack(new_track)

    if old_state.state == "playing" or old_state.player.find("Plex") == -1:
        old_track = old.get_missing_track_info()
    else:
        old_track = ptrack

    logging.info(f"\n  New track: {new_track}\n\n  Old track: {old_track}\n\n"
                 + f"Popped track: {ptrack}\n")

    # compare new_track, old_track with popped track...
    if ptrack.data == old_track.data:
        if (not_scrobbled_already(old_track.data.artist, old_track.data.title,
                old_track.time.time_stamp, old_track.data.duration, network) and
                long_enough_to_scrobble(old_track.data.duration,
                new_track.time.time_stamp, ptrack.time.time_stamp) and
                track_not_stale(ptrack, new_track)):
            scrobble_track(old_track, network)

    if ptrack.data != new_track.data: push_stack(new_track)

    logging.info(f"---")
    stack.close()

def scrobble_track(track, network):

    '''Scrobble track based on source - stream or local file.

       Use pylast to scrobble easily with network.scrobble unless it's
       a radio station in which case chosenByUser is set to 0 to indicate
       the track was chosen, for example, by the radio station.
    '''

    if track.data.artist == None or '[unknown]' in track.data.artist:
        logging.info(f"No scrobbling performed - unknown artist string\n")
        return

    if ((next((True for s in SUFFIX_LIST
               if track.data.content_id[-len(s):] == s), False) and
         track.data.title[0:4] != 'http') or int(track.state.media_track) > 0):

        # scrobble with pylast
        network.scrobble(artist=track.data.artist, title=track.data.title,
            timestamp=track.time.time_stamp)
        scrobble_result = "scrobble implicit"
    else:

        # crobble with lfm direct api in order to set chosenByUser to 0
        params=[('api_key', API_KEY), ('artist', track.data.artist),
                ('track', track.data.title), ('method', 'track.scrobble'),
                ('sk', SESSION_KEY), ('timestamp', str(track.time.time_stamp)),
                ('chosenByUser', '0')]
        sorted_params = sorted(params, key=lambda x: x[0])
        api_sig=''.join('%s' % ''.join(p) for p in sorted_params) + API_SECRET
        api_sig = pylast.md5(api_sig)
        xparams={k:v for (k, v) in sorted_params}
        xparams['api_sig']=api_sig
        xparams['format']='json'
        response = httpx.post(LFM_URL, params=xparams)
        if response.json()['scrobbles']['@attr']['accepted'] == 1:
            scrobble_result = "scrobble accepted"
        else:
            scrobble_result = "scrobble not accepted"

    logging.info(f"Popped track == old_track & duration longer than 30 seconds"
         + f"and played ≥ half its duration or its longer than 4 minutes - "
         + f"scrobbling old_track: {track}\n{scrobble_result}\n")
    return

def not_scrobbled_already(artist, title, timestamp, duration, network):

    '''check to o avoid duplicate scrobbles.

    Check for any scrobbles in the last x minutes where
    x is the minimum of twice the duration or 15 minutes...
    '''

    user=network.get_user(username=USER_NAME)
    t=user.get_recent_tracks(limit=3)
    for item in iter(t):
        track, album, date, time = item # track is a pylast named tuple

        # sometimes the srobbled tracks don't keep corrections made
        track.artist.name = track.artist.get_correction()
        track.title = track.get_correction()
        diff = timestamp - float(time) # only needed with below logging
        logging.info(f"track.artist.name = {track.artist.name}, "
                 + f"Popped artist = {artist},"
                 + f" track.title = {track.title}, Popped title = {title}, "
                 + f"time = {time}, timestamp = {timestamp}, "
                 + f"timestamp - time = {diff}\n")
        if (track.artist.name == artist and track.title == title and
                (abs(int(timestamp) - int(time))
                    < min(duration*2 if duration > 0 else 900, 900))):
            logging.info(f"Already scrobbled - artist: {artist}, "
                     + f"title: {title}, timestamp: {timestamp}\n")
            return False
    return True

def long_enough_to_scrobble(old_duration, new_timestamp, p_timestamp):

    '''Check to ensure track has played long enough before scrobbling.

    Ensure track is at least 30 seconds long or has played at least half
    of it's duration or 240 seconds in order to scrobble it.
    '''

    if ((int(old_duration) > 30 and (int(new_timestamp) - int(p_timestamp)) >
            (int(old_duration)/2)) or
            (int(new_timestamp) - int(p_timestamp)) > 240):
        return True
    return False

def track_not_stale(ptrack, new_track):

    '''Check if popped track is stale and needs to be replaced.'''

    if (new_track.time.time_stamp >
            (ptrack.time.time_stamp + ptrack.data.duration*2)):

        # popped track is stale
        push_stack(new_track)
        return False
    return True

def push_stack(trackToPush):

    '''Push track on stack file.'''

    shutil.copy2(EMPTYFILE, STACKFILE)
    stack = open(STACKFILE,'r+')
    json.dump({"data": trackToPush.data.__dict__,
               "time": trackToPush.time.__dict__,
               "state": trackToPush.state.__dict__}, stack)
    stack.close()

class event:

    '''Homeassistant Media Event Class.

    A class to parse media player event data originating
    from homeassistant media_player events.
    '''

    def __init__(self, media, state, network):
        self.media = media
        self.state = state
        self.network = network
        try:
            self.event = self.__media_player_event(self.media, self.state)
            self.track_data = self.event['data']
            self.track_time = self.event['time']
            self.playing_state = self.event['state']
        except:
            logging.error(f"bad event data supplied, terminating\n{media}\n")
            sys.exit(1)

    def __media_player_event(self, media, state):

        '''Parse media player event data to dictionary.'''

        e = {}
        d = {}
        try:
            media_title = json.loads(media)[state+'_state']['media_title']
        except:
            media_title = ""
        try:
            media_artist = json.loads(media)[state+'_state']['media_artist']
        except KeyError:
            media_artist = ""
        except:
            media_artist = ""
        try:
            media_content_type = (json.loads(media)
                [state+'_state']['media_content_type'])
        except:
            media_content_type = ""
        try:
            media_duration = json.loads(media)[state+'_state']['media_duration']
        except:
            media_duration = 0
        try:
            time_stamp = (datetime.datetime.strptime(json.loads(
                media)['time_'+state], '%Y-%m-%dT%H:%M:%S.%f%z').timestamp())
        except:
            time_stamp = 0
        try:
            media_content_id = str(json.loads(media)
                [state+'_state']['media_content_id'])
        except:
            media_content_id = ""
        try:
            media_track = str(json.loads(media)[state+'_state']['media_track'])
            if media_track == "": media_track = 0
        except:
            media_track = -1
        try:
            playing_state = str(json.loads(media)['state_'+state])
        except:
            playing_state = ""
        try:
            player = json.loads(media)[state+'_state']['friendly_name']
        except:
            player = ""
        try:
            sonos = json.loads(media)[state+'_state']['sonos_group']
            if sonos: player="sonos"
        except:
            sonos = ""
        d = {"artist": media_artist,
             "title": media_title,
             "duration": media_duration,
             "content_id": media_content_id,
             "content_type": media_content_type}
        e_time = {"time_stamp":time_stamp}
        e_state = {"state": playing_state, "media_track": media_track,
                  "player": player}
        e = {"data": d, "time": e_time, "state": e_state}
        return e

    def get_event_info(self):

        '''Return class media player event data.'''

        return (SimpleNamespace(**self.track_data),
                SimpleNamespace(**self.playing_state),
                SimpleNamespace(**self.track_time))

    def get_missing_track_info(self):

        '''Identify artist, track title, and track duration from lastFM.'''

        ev = SimpleNamespace(**self.track_data)
        time = SimpleNamespace(**self.track_time)
        state = SimpleNamespace(**self.playing_state)
        tck = {}
        track = SimpleNamespace()

        # parse artist, title from event data
        track.artist, track.title = self.__parse_event(ev, track, state)

        # get lastFM track data & correct it (normalized artist and title)
        lfmTrack = self.network.get_track(track.artist, track.title)
        track.artist = lfmTrack.artist.name = lfmTrack.artist.get_correction()
        lfmTrack.title = self.__get_local_correction(lfmTrack.title,
                         track.artist)
        track.title = lfmTrack.title = lfmTrack.get_correction()
        track.duration = self.__local_get_duration(track, lfmTrack,
                         self.network)

        # a local attempt of lfm's track.getSimilar - removes string enclosed
        # with [] or () preceeded by space from end of title. track.getSimilar
        # doesn't seem to id these as similar, e.g., ' (Album Version)'
        if track.duration == 0:
            track.title = lfmTrack.title = re.sub(r' [\(\[][ \w]+[\]\)]$',
                          '', track.title)
            track.duration = self.__local_get_duration(track,
                             lfmTrack, self.network)

        tck['data'] = SimpleNamespace(artist=track.artist, title=track.title,
            duration=int(track.duration), content_id=ev.content_id,
            content_type=ev.content_type)
        tck['time'] = SimpleNamespace(time_stamp=time.time_stamp)
        tck['state'] = SimpleNamespace(state=state.state,
            media_track=state.media_track, player=state.player)
        return SimpleNamespace(**tck)

    def __parse_event(self, ev, track, state):

        '''Parse or obtain track and title from event data.

        Some streams combine artist and title into title field - other streams
        and local files cleanly place artist and title into their distinct
        fields.
        '''

        if ev.artist == "" and ev.content_id[0:4] == 'http':
            # its a radio station played from mpd -
            # parse title and artist from title string
            if ev.title.find(": ") == -1:
                track.artist, track.title = self.__parse_title(ev.title)
            elif ev.title.find(": ") > 0:
                stream_name_end = ev.title.find(": ")
                track.artist, track.title = self.__parse_title(
                    ev.title[stream_name_end+2:])
        elif (int(state.media_track) >= 0 or
                next((True for s in SUFFIX_LIST
                      if ev.content_id[-len(s):] == s), False) or
                int(state.media_track) == -1 and state.player == "sonos"):
            # it's a radio station from forked_daapd_server and they identify
            # artist & title or its a file from library - in either case no
            # parsing required, both are directly available from event
            track.artist = ev.artist
            track.title = ev.title
        return track.artist, track.title

    def __parse_title(self, title):

        '''Parse title from combined artist title string separated by "-".'''

        artist_end = title.find(" - ")
        artist = title[0:artist_end]
        title = title[artist_end+3:]
        return artist, title

    def __get_local_correction(self, title, artist):

        '''apply local title corrections that lfm may not process.

        if title is of form "artist - title", then this strips off "artist - "
        and then also finds any station appended strings at the  end of title
        like "[2iQi]"
        '''

        artist_end = title.find(" - ")
        title = (title[artist_end+3:]
                 if artist_end > 0 and title[0:artist_end] == artist else title)
        title = re.sub(' $', '', title)
        suffix = re.search(r' \[\w+\]$', title)
        try:
            if len(suffix.group()) < 8:
                return title[0:title.find(suffix.group())]
        except (TypeError, AttributeError):
            return title

    def __local_get_duration(self, track, lfmTrack, network):

        '''get duration from lastfm.

        if get_duration returns 0, search through all combinations
        of lfm title/artist tracks for non-zero durations - pick largest.
        '''

        try:
            track.duration = lfmTrack.get_duration()/1000
        except pylast.WSError:
            track.duration = 0
        else:
            if track.duration == 0:
                # search through all releases of track.title by
                # track.artist for non-zero durations pick the longest..
                # otherwise duration = zero
                found_tracks = network.search_for_track(track.artist,
                    track.title).get_next_page()
                try:
                    _tracks = (tk for tk in found_tracks
                               if tk.get_duration() > 0)
                    _longest = max(_tracks, key=lambda x: x.get_duration())
                except:
                    track.duration = 0
                else:
                    track.duration = _longest.get_duration()/1000
        return track.duration

if __name__ == '__main__':
    main()
