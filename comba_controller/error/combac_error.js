{
	"allData":        {
		  	    "id": "01",
		  	    "00": "Global Metadata delivered",
			     "01": "Could not get Data from Sound Engine"
		          },
	"channel_insert": {
		   	    "id": "02",
		   	    "00": "On Channel ::channel:: insert ::uri:: at position ::pos::",
			     "02": "On Channel ::channel:: could not insert ::uri:: at position ::pos::"
		          },
	"channel_move":   {
			     "id": "03",
			     "00": "On Channel ::channel:: moved Item from ::fromPos:: to position ::toPos::",
			     "01": "Warning: Position ::fromPos:: out of range",
			     "02": "Warning: Cannot move to same position",
			     "03": "On Channel ::channel:: could not move from position ::fromPos:: to  position ::toPos::"
		          },
	"channel_off":    {
			     "id": "04",
			     "00": "Channel ::channel:: off",
			     "01": "Could not activate Channel ::channel::"
		          },
	"channel_on":     {
                             "id": "05",
			     "00": "Channel ::channel:: on",
			     "01": "Could not deactivate Channel ::channel::"
		          },
	"channel_queue":  {
			     "id": "06",
			     "00": "Channel Queue for ::channel:: delivered",
			     "01": "Could not get channel queue from channel ::channel::",
			     "02": "Could not get channel queue from channel ::channel::",
			     "03": "Could not get channel queue from channel ::channel::"
		          },
	"channel_remove": {
			     "id": "07",
			     "00": "Removed item on position ::pos:: from channel ::channel::",
			     "01": "Could not remove item on position ::pos:: from channel ::channel::",
			     "02": "Warning: position ::pos:: out of range'"
		          },
	"channel_seek":   {
			     "id": "08",
			     "00": "Seeked channel ::channel:: ::duration:: seconds",
			     "01": "Could not seek channel ::channel:: ::duration:: seconds"
		          },
	"channel_skip":   {
			     "id": "09",
			     "00": "Skipped channel ::channel::",
			     "01": "0 Channels listed",
			     "02": "Could not get channels from sound engine",
			     "03": "Could not skip ::channel::"
		          },
	"channel_volume": {
			     "id": "10",
			     "00": "Volume ::volume::% set on channel ::channel::",
			     "01": "Could not set volume to ::volume::% on channel ::channel::",
			     "02": "0 Channels listed",
			     "03": "Could not get channels from sound engine"
		          },
	"currentData":    {
			     "id": "11",
			     "00": "Current track metadata delivered",
			     "01": "Nothing seems to be on air",
			     "02": "Could not detect metadata"
		          },
	"help":  {
			     "id": "12",
			     "00": "none",
			     "01": "Could not open help file"
		          },
	"listChannels":   {
			     "id": "13",
			     "00": "Listed Channels",
			     "01": "0 Channels listed",
			     "02": "Could not get channels from sound engine"
		          },
	"message":        {
			     "id": "14",
			     "00": "none"
		          },
	"playlist_data":  {
			     "id": "15",
			     "00": "Playlist data delivered"

		          },
	"playlist_flush": {
			     "id": "16",
			     "00": "Flushed playlist",
			     "01": "Could not flush playlist"
		          },
	"playlist_insert":{
			     "id": "17",
			     "00": "Insert track ::uri:: on position ::pos::"
		          },
	"playlist_load":  {
			     "id": "18",
			     "00": "Load Playlist ::uri::",
			     "01": "Could not load Playlist ::uri::",
                 "02": "Playlist is not well formed XML"
		          },
	"playlist_move":  {
			     "id": "19",
			     "00": "Moved playlist track from position ::fromPos:: to ::toPos::"
		          },
	"playlist_pause": {
			     "id": "20",
			     "00": "Playlist paused",
			     "01": "Playlist already paused"
		          },
	"playlist_stop": {
			     "id": "21",
			     "00": "Playlist stopped",
			     "01": "Playlist already stopped"
		          },
	"playlist_play":  {
			     "id": "22",
			     "00": "Playlist started",
			     "01": "Playlist already playing",
			     "02": "0 Channels listed",
			     "03": "Could not get channels from sound engine"
		          },
	"playlist_push":  {
			     "id": "23",
			     "00": "Playlist: pushed ::uri::",
			     "01": "Could not push ::uri::"
		          },
	"playlist_remove":{
			     "id": "24",
			     "00": "Removed track on position ::pos:: from playlist",
			     "01": "Could not remove track on position ::pos:: from playlist"
		          },
	"playlist_seek":  {
			     "id": "25",
			     "00": "Seeked playlist ::duration:: seconds",
			     "01": "Could not seek playlist ::duration:: seconds"
		          },
	"playlist_skip":  {
			     "id": "26",
			     "00": "Skipped playlist",
			     "00": "Could not skip playlist"
		          },
	"recorder_data":  {
			     "id": "27",
			     "00": "Delivered recorder data",
			     "01": "Could not deliver recorder data"
		          },
	"recorder_start": {
			     "id": "28",
			     "00": "Recorder started",
			     "01": "Could not start recorder"
		          },
	"recorder_stop":  {
			     "id": "29",
			     "00": "Recorder stopped",
			     "01": "Could not stop recorder"
		          },
	"scheduler_reload":  {
			     "id": "30",
			     "00": "Reload signal was sent to scheduler",
			     "01": "Could not find the scheduler process"
		          },
	"sendLqcCommand":  {
			     "id": "31",
			     "01": "Soundengine not running",
			     "02": "Recorder not running"
		          },
	"get_channel_state" : {
				 "id": "32",
			     "00": "Channels ::channel:: state",
			     "01": "Could not get channel state from channel ::channel::"
				  },
	"setPassword":  {
			     "id": "33",
			     "00": "Successfull set password",
			     "01": "Not enough access rights for this operation"
		          },
	"addUser":  {
			     "id": "34",
			     "00": "Successfull add user ::username::",
			     "01": "Not enough access rights for this operation"
		          },
	"delUser":  {
			     "id": "35",
			     "00": "Successfull removed user ::username::",
			     "01": "Not enough access rights for this operation"
		          },
	"scheduler_data":  {
			     "id": "36",
			     "00": "Successfull delivered scheduler config",
			     "01": "Scheduler config seems to be broken"
		          },
	"scheduler_store":  {
			     "id": "37",
			     "00": "Successfull stored scheduler config",
			     "01": "Not enough access rights for this operation",
			     "02": "Could not store a valid scheduler XML"
		          },
	"getUserlist":  {
			     "id": "38",
			     "00": "Userlist was successfully delivered",
			     "01": "Not enough access rights for this operation"
		          }
}