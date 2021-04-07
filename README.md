# README

#### This is a Last.fm scrobbler for Home Assistant media players.  It will scrobble your listens to your Last.fm account.  I wrote it for a number of reasons, but the net of it is that I wanted a single scrobbling solution across the few players that I use and i wanted it to scrobble both listens from my own library as well as streaming content.  Moreover, I was looking for something to practice/learn more python.  The full-readme has more background and details.

#### To install and use, follow these steps.  It can work with yaml based automation or Node-RED flows.  Additionally, these particular installation steps presume that you will run the ha-scrobble.py function in your Home Aassistant machine (be it physical or virtual) - note that it can be a different version of python than used by your Home Assistant instance.  The steps below are for yaml based automation.  If you wisth to use Node-RED or setup ha-scrobble.py outside of your homeasssistant instance, see the full-readme.

### Installation steps - short version 
- obtain a Last.fm account if you don't have one yet and get a Last.fm API and set up a session key - per instructions in full-readme/full-readme.md
- connect into your .homeassistant directory (e.g., ssh or docker exec in if running in a docker container)
- `cd ..`
- clone the repo to ha-scrobble at this level:  `git clone https://github.com/yajrendrag/ha-scrobbler.git ha-scrobble`.  If you're not logged in as the user running hass, chown the ha-scrobble directory to that user.
- `cd ha-scrobble`
- `touch ./ha-scrobble.log`
- `touch ./stackfile.txt`
- move processmpd.sh to your shell_commands directory, e.g., `mv processmpd.sh ../.homeassistant/shell_commands`
- edit ha-scrobble.py and set the Last.fm account constants and other globals - see hascrobblermd/full-readme for details.  Also set the python shebang string (line 1) to the python environment/command you wish to use.
- install requirements.txt to your chosen python environment
- add a yaml automation (see media_automation.yaml in repo) - see full-readme/full-readme.md for details or for Node-RED flow alternative
- add a shell command to your Home Assistant configuration - here's an example based on media_automation.yaml service call:
`process_mpd_data: /home/YOUR-HASS-USER/.homeassistant/shell_commands/processmpd.sh {{ mpd_data }}` - regardless of Node-RED or yaml automation this will pass the media event data to the processmpd.sh shell script to start the scrobbling activity.  Make sure to replace YOUR-HASS-USER with your actual hass user name in above path.
- modify the yaml automation or Node-RED flow as needed to match the media player(s) you use.  Read the full-readme/full-readme.md section on Media Player Events - especially the Event Parsing paragraph if you use players other than forked-daapd, mpd, Jellyfin, Sonos, Spotify, or Plex - these are the players i have tested with so it may take some additional work to make this work for other players.
- set up logrotate per instructions in full-readme/full-readme.md or per your own preferences
- Scrobble away!
