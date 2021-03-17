#!/bin/bash
#if you have a mail MTA installed and/or require mail for cron, comment this out or set to appropriate value
MAILTO=""

# you only need this script if you are processing ha-scrobble outside of hass
# you'll need to put this someplace like /usr/local/bin, make it executable by the user running ha-scrobble.py and then
# create a cron job for the user that will run ha-scrobble and add this to that user's crontab
#@reboot /usr/local/bin/scrobble-notifier.sh >/dev/null 2>&1

# edit line below by replaceing user with the name of an actual user on your system
while inotifywait -e modify /home/user/ha-scrobble/mpd-events.txt; do /usr/local/bin/processmpd-events.sh; done
