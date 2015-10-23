#!/usr/bin/python
# -*- coding: utf-8 -*-

import os
import time
import math
import logging
import pyev
import datetime
import simplejson
import contextlib
import signal
from thread import start_new_thread
import glob
import wave
from comba_lib.base.schedulerconfig import CombaSchedulerConfig
from comba_lib.base.combabase import CombaBase
from comba_lib.reporting.messenger import CombaMessenger
from comba_lib.service.calendar import CombaCalendarService
from comba_lib.utils.audio import CombaAudiotools


"""
    CombaMonitor Class
    Überwacht Vorgänge und greift notfalls ein 
"""
class CombaMonitor(CombaBase):
    # Constructor
    def __init__(self, CombaClient_instance):
        """
        Constructor
        @type    CombaClient_instance: object
        @param   CombaClient_instance: Der Client für Liquidsoap
        """        
        self.client = CombaClient_instance
        
        # Messenger für Systemzustände initieren
        self.messenger = CombaMessenger()
        self.messenger.setChannel('monitor')
        self.messenger.setSection('execjob')
        
        self.playlistwatchers = []
        self.watchers = []
        
        # das pyev Loop-Object
        self.loop = pyev.default_loop()
        self.playlistwatcher_loop = pyev.Loop()
        # Die Signale, die Abbruch signalisieren
        self.stopsignals = (signal.SIGTERM, signal.SIGINT)
        
        # Das ist kein Reload
        self.initial = True
        self.config = object
        self.config_path = ""
        self.stop_time = ''
        self.start_time = ''
        self.duration = ""

        # Der Monitor wartet noch auf den Start Befehl
        self.ready = False

        self.block_combine = False
        
        errors_file = os.path.dirname(os.path.realpath(__file__)) + '/error/combam_error.js'
        json_data = open(errors_file)
        self.errorData = simplejson.load(json_data)
        self.livetime = False

        self.messenger.send('Monitor started', '0000', 'success', 'initApp' , None, 'appinternal')
        
    #------------------------------------------------------------------------------------------#
    def _loadConfig(self):
        """
        Scheduler-Config importieren
        @rtype:   boolean
        @return:  True/False
        """        
        # Wenn das Scheduling bereits läuft, muss der Scheduler nicht unbedingt angehalten werden         
        error_type = 'fatal' if self.initial else 'error'
        try:
            # Das scheduler.xml laden
            watcher_jobs = self.config.getJobs()
        except:

            # Das scheint kein gültiges XML zu sein
            self.messenger.send('Config is broken', '0301', error_type, 'loadConfig' , None, 'config')
            # Wenn das beim Start passiert können wir nix tun
            if self.initial: 
                self.ready = False                                
            return False

        # Fehlermeldung senden, wenn keine Jobs gefunden worden sind
        if len(watcher_jobs) == 0:
            self.messenger.send('No Jobs found in Config', '0302', error_type, 'loadConfig' , None, 'config')
                 
        # Anhand der Jobs weitere Daten ermitteln, die für interne Zwecke benötigt werden
        self._get_jobs_infos(watcher_jobs)
        # Es kann losgehen        
        self.ready = True
        return True

    #------------------------------------------------------------------------------------------#
    def _get_jobs_infos(self, jobs):
        """
        Ermittelt aus der Start- und Stopzeit der Playlist Dauer der Automatisierung und die Startzeit
        @type    jobs: list
        @param   jobs: Liste mit den Jobs
        """

        self.livetime = True
        now = datetime.datetime.now()
        # Jobs nach Start und Stop-Zeit der Playlist durchsuchen

        for job in jobs:

            if job['job'] ==  'play_playlist':
                if self.config.in_timeperiod(now,job):
                    self.livetime   = False
                    self.start_time = job['time']
                    self.stop_time  = job['until']
                    self.duration   = int(job['duration'])

            elif job['job'] ==  'start_recording' and self.config.in_timeperiod(now,job):
                self.start_time = job['time']
                self.stop_time  =  job['until']
                self.duration = int(job['duration'])

    #------------------------------------------------------------------------------------------#
    def set(self, key, value):
        """
        Eine property setzen
        @type    key: string
        @param   key: Der Key
        @type    value: mixed
        @param   value: Beliebiger Wert
        """
        self.__dict__[key] = value        

    #------------------------------------------------------------------------------------------#
    def start(self):      
        """
        Monitor Loop starten
        """
        self.config = CombaSchedulerConfig(self.config_path)
        #TODO: Unterscheide bei den Funktionsnamen zwischen scheduler.xml und comba.ini
        ## die comba.ini laden
        self.loadConfig()
        self.messenger.setMailAddresses(self.get('frommail'), self.get('adminmail'))
        ## die scheduler.xml laden
        self._loadConfig()

        # Der erste Watcher ist ein Signal-Watcher, der den sauberen Abbruch ermöglicht
        self.watchers = [pyev.Signal(sig, self.loop, self.signal_cb)
                         for sig in self.stopsignals]
        
        self.watchers.append(self.loop.timer(0, 20, self.checkComponents))
        
        self.watchers.append(self.loop.timer(0, 60, self.checkPlaylistEvent))        
        
        # Der dritte Watcher sendet alle 20 Sekunden ein Lebenszeichen
        say_alive = self.loop.timer(0, 20, self.sayAlive) 

        #self.audiowatcher = self.loop.timer(0, 0,self.combine_audiofiles, self.audiowatcher_data)
        self.watchers.append(say_alive)
        
        # Alle watcher starten
        for watcher in self.watchers:
            watcher.start()        
        
        logging.debug("{0}: started".format(self))             
        try:
            self.loop.start()
        except:
            self.messenger.send("Loop did'nt start", '0101', 'fatal', 'appstart' , None, 'appinternal')
        else:
            self.messenger.send("Monitor started", '0100', 'success', 'appstart' , None, 'appinternal')    
    
    #------------------------------------------------------------------------------------------#
    def stop(self):
        """
        Event Loop stoppen
        """
        self.loop.stop(pyev.EVBREAK_ALL)
        # alle watchers stoppen und entfernen
        while self.watchers:
            self.watchers.pop().stop()
        self.messenger.send("Loop stopped", '0400', 'success', 'appstart' , None, 'appinternal')        

    #------------------------------------------------------------------------------------------#
    def sayAlive(self, watcher, revents):
        """
        Alle 20 Sekunden ein Lebenssignal senden
        @type  watcher:  object
        @param watcher:  Das watcher Objekt
        @type  revents: object
        @param revents: Event Callbacks    
        """
        self.messenger.sayAlive()

    #------------------------------------------------------------------------------------------#
    def signal_cb(self, loop, revents):
        """
        Signalverarbeitung bei Abbruch
        @type  loop: object
        @param loop: Das py_ev loop Objekt
        @type  revents: object
        @param revents: Event Callbacks
        """
        self.messenger.send("Received stop signal", '1100', 'success', 'appstop' , None, 'appinternal')           
        self.stop()

    #------------------------------------------------------------------------------------------#
    def checkComponents(self, watcher, revents):
        """
        Alle 20 Sekunden Checken, ob Komponenten noch laufen
        @type  watcher:  object
        @param watcher:  Das watcher Objekt
        @type  revents: object
        @param revents: Event Callbacks    
        """

        if not self.messenger.getAliveState('scheduler'):            
            self.messenger.send("Scheduler is down... try to start scheduler", '0201', 'error', 'checkComponents' , None, 'appinternal')
            self._restartScheduler()

        if not self.messenger.getAliveState('controller'):            
            self.messenger.send("Controller is down... try to start controller", '0202', 'error', 'checkComponents' , None, 'appinternal')
            self._restartController()
        
        if not self.messenger.getAliveState('record') or not self.messenger.getAliveState('altrecord') or not self.messenger.getAliveState('playd'):
            self.messenger.send("Liquidsoap components are down... try to start soundengine components", '0202', 'error', 'checkComponents' , None, 'appinternal')
            self._restartLiquidsoap()
            time.sleep(10);

            jobs = self.config.getJobs()
            self._get_jobs_infos(jobs)
            if self.livetime:
                for i in '123':                    
                    if self.messenger.getAliveState('record'):
                        self.messenger.send("Start recorder", '0204', 'info', 'checkComponents' , None, 'appinternal')
                        start_new_thread(self._restartRecord,())                                                                    
                        break;
                    time.sleep(20);
            else:
                for i in '123':                    
                    if self.messenger.getAliveState('playd'):

                        self.messenger.send("Start playlist", '0205', 'info', 'checkComponents' , None, 'appinternal')
                        start_new_thread(self._reloadPlaylist,())                        
                        break;
                    time.sleep(20);

        if not self.messenger.getAliveState('archive'):
            self.messenger.send("Archive is down... try to start archive", '0201', 'error', 'checkComponents' , None, 'appinternal')
            self._restartArchive()


    #------------------------------------------------------------------------------------------#
    def checktrack(self, watcher, revents):
        """
        Einen Track checken und ggf. den Player anhalten oder skippen
        @type  watcher:  object
        @param watcher:  Das watcher Objekt
        @type  revents: object
        @param revents: Event Callbacks
        """
        
        def playlist_stop(wait):
            """
            Interne Routine - stoppt den Player
            @type wait: string
            @param wait: Anz. Sekunden nach der der Player wieder gestartet wird
            """
            self.client.playlist_stop()
            time.sleep(int(wait))
            self.client.playlist_play()
        
        def playlist_skip(wait):
            """
            Interne Routine - skippt den Player
            @type wait: string
            @param wait: Anz. Sekunden nach der der Player geskippt wird
            """            
            time.sleep(int(wait))
            self.client.playlist_skip()            
        # Watcher stoppen
        watcher.stop()
        stopforDuration = 0
        skipafterDuration = 0         
        
        if not watcher.data.has_key('location'):
            return False    
        
        # Dauer des Tracks lt. Playlist
        duration = int(watcher.data['length'])  
        
        # Dateipfad
        fname = watcher.data['location'].replace('file://', '')
        
        # Wenn die Datei nicht existiert, muss der Player für die Dauer des Tracks angehalten werden
        if not os.path.isfile(fname):
            stopforDuration = str(duration)        
            start_new_thread(playlist_stop,(stopforDuration,))

        else:
            # Dauer der WAV-Datei ermitteln
            with contextlib.closing(wave.open(fname,'r')) as f:
                frames = f.getnframes()
                rate = f.getframerate()
                fduration = int(math.ceil(frames / float(rate)))
                
                # Ist die Dauer der WAV-Datei kleiner als die angegebene Dauer des Tracks,
                # muss  die Playlist um die Differenz angehalten werden  
                if fduration < duration:
                    stopforDuration = str(duration - fduration)
                    start_new_thread(playlist_stop,(stopforDuration,))

                # Ist die Dauer der WAV-Datei größer als die angegebene Dauer des Tracks,
                # muss der laufende Track nach der Diffenz geskippt
                elif fduration > duration:
                    skipafterDuration = str(fduration - duration)
                    start_new_thread(playlist_skip,(skipafterDuration,))

    #------------------------------------------------------------------------------------------#
    def checkPlaylistEvent(self, watcher, revents):
        """
        Prüft ob der LoaPlaylist event gefeurt wurde und reagiert ggf.
        """            
        eventFired = self.messenger.getEvent('loadplaylist','player')
        if eventFired:
            eventQueue = self.messenger.getEventQueue('playtrack', 'player')
            
               
            if not eventQueue or not isinstance(eventQueue, list):
                self.messenger.send('No event queue present', '1301', 'warning', 'checkPlaylistEvent' , None, 'events')

            else:
                
                # stop all playlist watchers
                for watcher in self.playlistwatchers:
                    watcher.stop()
                    self.playlistwatchers = []
                cnt = 0
                self.playlistwatcher_loop.stop()
                self.playlistwatcher_loop = pyev.Loop()
    
                for index, item in enumerate(eventQueue):
                    cnt = cnt + 10
                    if not item.has_key('date') or not item.has_key('time'):
                        # funny
                        continue
                    
                    # Sekunden berechnen nach der Timer gestartet wird
                    track_time = int(datetime.datetime.strptime(item['date'][0:10] + 'T' + item['time'],"%Y-%m-%dT%H:%M").strftime("%s")) - 1
                    self.playlistwatchers.append(self.playlistwatcher_loop.periodic(track_time, 0.0, self.checktrack, item))

                for watcher in self.playlistwatchers:
                    watcher.start()    
                       
    #------------------------------------------------------------------------------------------#
    def combine_audiofiles(self, watcher, revents):
        """
        Kombiniert Dateien, die in einem best. Zeitintervall entstanden sind
        @type watcher:  object
        @param watcher: der watcher
        @type revents:    object
        @param revents:  revents - nicht verwendet
        """
        self.block_combine = False
        self.messenger.send('Stop watcher', '0501', 'info', 'combine_audiofiles' , None, 'appinternal')
        
        from_time = int(watcher.data['from_time'])
        to_time = int(watcher.data['to_time'])
        
        watcher.stop()
        watcher.loop.stop()
        # Den Ordner  bestimmen, in dem die Dateien liegen
        cur_folder = self.record_dir + '/' + datetime.datetime.fromtimestamp(from_time).strftime("%Y-%m-%d") + "/"
        
        uid = os.stat(cur_folder).st_uid
        gid = os.stat(cur_folder).st_gid
        # Name der Audiodatei, die angelegt werden muss
        out_file = datetime.datetime.fromtimestamp(from_time).strftime("%Y-%m-%d-%H-%M") + ".wav"

        # Alle WAV-Dateien im Ordner
        files = glob.glob(cur_folder + "*.wav")
        
        combine = []
        if len(files) > 0:
            for file in files:            
                t = int(os.path.getmtime(file))            
                # Liegt die Mtime im definierten Intervall?
                if t > from_time and t <= to_time:
                    combine.append(file)

            if len(combine) > 0:

                audiotools = CombaAudiotools()
                audiotools.combine_audiofiles(combine, cur_folder, out_file, nice=19)
                os.chown(out_file, uid, gid);
                self.messenger.send("Combined  to file " + out_file, '0502', 'info', 'combine_audiofiles' , None, 'appinternal')

    #------------------------------------------------------------------------------------------#
    def _load_playlist(self):
        """
        Playlist laden und von dem Track und Zeitpunkt an starten, der aktuell laufen sollte
        """

        self.messenger.send("Try to load playlist", '0501', 'info', 'loadPlaylist' , None, 'appinternal')

        # Die Playlist holen
        store = CombaCalendarService()

        # start_date ist das Datum, an dem die Playlist beginnen soll - abrunden auf den Beginn der denierten Länge für einen Track
        start_date  = datetime.datetime.now() - datetime.timedelta(seconds=int(datetime.datetime.now().strftime('%s')) % int(self.secondspertrack))

        store.setDateFrom(start_date.strftime("%Y-%m-%dT%H:%M"))
        store.setUntilTime(self.stop_time)

        store.start()
        uri = store.getUri()

        # wait until childs thread returns
        store.join()

        result = self.client.playlist_load(uri)
            
        if not self._get_data(result):
            self.messenger.send('Could not get Data from controller', '0504', 'fatal', 'loadPlaylist' , None, 'appinternal')
        else:
            result = self.client.playlist_play()
            if not self._get_data(result):
                self.messenger.send('Could not get Data from controller', '0505', 'fatal', 'loadPlaylist' , None, 'appinternal')

            else:

                time.sleep(0.2)
                unix_time_now = int(datetime.datetime.now().strftime('%s'))
                # berechnen die Sekunden die wir noch weiterspulen müssen
                seek_time = unix_time_now - int(start_date.strftime('%s'))
                # ... und seek
                self.client.playlist_seek(str(seek_time))
                       
    #------------------------------------------------------------------------------------------#
    def _restartScheduler(self):
        """
        Scheduler neu starten
        """
        os.system("service combascheduler restart")

    #------------------------------------------------------------------------------------------#
    def _restartArchive(self):
        """
        Restart archive controller
        """
        os.system("service combaarchive restart")

    #------------------------------------------------------------------------------------------#
    def _restartController(self):
        """
        Controller neu starten
        """
        os.system("service comba restart")

    #------------------------------------------------------------------------------------------#
    def _restartLiquidsoap(self):
        """
        Player und recorder neu starten
        """
        os.system("service comba_liq restart")

    #------------------------------------------------------------------------------------------#
    def _restartRecord(self):
        """
        Recorder neu starten
        Da die Aufnahme vermutlich unterbrochen wurde, werden Audiodateien aus dem vorgesehenen Zeitraum zusammengefügt
        """
        result = self.client.recorder_start()
        if self.block_combine:
            return
        
        self.block_combine = True
        now = int(datetime.datetime.now().strftime("%s"))

        mod = now % int(self.secondspertrack)
        from_time = (now - mod)
        to_time = from_time + int(self.secondspertrack)
        # combine_audiofiles wird 1 Sekunde nach Ende der Aufnahme ausgeführt 
        time_start = float((to_time - now) +1) 
        
        data = {}
        data['from_time'] = from_time
        data['to_time'] = to_time 
        loop = pyev.Loop()
        #self.audiowatcher.set(0.0, time_start)
        
        watcher = loop.timer(time_start, 0, self.combine_audiofiles, data)
        #self.audiowatcher.set(10, 0.0)
        self.messenger.send("Audiofiles may be combined in " + str(watcher.remaining) + " seconds", '0601', 'info', 'restartRecord' , None, 'appinternal')
        
        watcher.start()
        loop.start()
        
    #------------------------------------------------------------------------------------------#
    def _reloadPlaylist(self):
        """
        Playliste neu laden und starten
        """
        self._load_playlist()

    #------------------------------------------------------------------------------------------#
    def _adminMessage(self,message):
        pass

    #------------------------------------------------------------------------------------------#
    def _get_data(self, result):
        """                
        @type     result: dict
        @param    result: Ein dict objekt
        """        
        if type(result) == type(str()):
            try:
                result = simplejson.loads(result)
            except:
                return False
        try:
            if result['success'] == 'success':
                if result.has_key('value') and result['value']:
                    return result['value']
                else:

                    return True
            else:
                return False
        except:

            return False   

    