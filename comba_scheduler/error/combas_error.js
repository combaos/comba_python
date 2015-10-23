{
	"exec_job":        {
		  	    "id": "01",
		  	     "00": "Execute job ::job::",
			     "01": "Fatal: Could not execute job ::job::. Command ::exec:: results in Exception ::Exception::. Stopped watcher"

		          },
	"schedule_job":        {
		  	    "id": "02",
		  	     "00": "Scheduled job ::job:: for ::scheduled_for:: at ::scheduled_at::",
			     "01": "Could not execute job"

		          },
	"load_playlist": {
		   	    "id": "03",
		   	    "00": "Load playlist ::uri::",
			    "01": "Could not load playlist ::uri::. File does not exist!",
			    "02": "Controller failed to load playlist ::uri::. Message was '::message::'"
		          },
	"play_playlist":   {
			     "id": "04",
			     "00": "Started playlist",
			     "01": "Controller failed to start playlist. Message was '::message::'"
		          },
	"stop_playlist":    {
			     "id": "05",
			     "00": "Started playlist",
			     "01": "Controller failed to start playlist. Message was '::message::'"
			  },
	"start_recording":     {
                             "id": "06",
   			     "00": "Started recording",
			     "01": "Controller failed to start recording. Message was '::message::'"
		          },
	"stop_recording":  {
			     "id": "07",
   			     "00": "Stopped recording",
			     "01": "Controller failed to stop recording. Message was '::message::'"		          },
	"precache": {
			     "id": "08",
   			     "00": "Precached playlists",
			     "01": "Could not precache playlist."
		          },
	"clean_cached":   {
			     "id": "09",
   			     "00": "Cleaned cache",
			     "01": "Could not clean cache"
		          },
	"on_start":   {
			     "id": "10",
   			     "00": "Do initial jobs",
			     "01": "Could not do initial jobs"
		          },
    "lookup_prearranged":   {
			     "id": "11",
   			     "00": "Lookup for prearranged tracks",
			     "01": "No system channel available"
		          },
    "start_prearranged":   {
			     "id": "12",
   			     "00": "Started preaarranged tracks"
		          },
    "end_prearranged":   {
			     "id": "13",
   			     "00": "Stopped preaarranged tracks"
		          }
}

