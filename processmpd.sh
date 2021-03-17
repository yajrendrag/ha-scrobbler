#!/bin/bash

MAILTO=""
# if running outside of hass, you may wish to uncomment the /bin/echo line
# below and edit the path to mpd-events.txt replacing YOUR_HASS_USER with your
# actual hass user name
# /bin/echo "$@" >> /home/YOUR_HASS_USER/ha-scrobble/mpd-events.txt

# edit the line below by replacing YOUR_HASS_USER with your actual hass user name
/home/YOUR_HASS_USER/ha-scrobble/ha-scrobble.py "$@" 
# if running outside of hass, comment above line out
