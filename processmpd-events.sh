#!/bin/bash

# you only need this script if you are running ha-scrobble.py outside of hass
# edit the paths below by replacing "user" with an actual user name
# this script will need to be triggered with something like inotifywait (see full-readme.md)
x=$(tail -1 /home/user/ha-scrobble/mpd-events.txt)
/home/user/ha-scrobble/ha-scrobble.py "$x"
