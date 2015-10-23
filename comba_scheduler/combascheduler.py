#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# combacscheduler.py
#
#       Copyright 2014 BFR <info@freie-radios.de>
#
#       This program is free software; you can redistribute it and/or modify
#       it under the terms of the GNU General Public License as published by
#       the Free Software Foundation; Version 3 of the License
#
#       This program is distributed in the hope that it will be useful,
#       but WITHOUT ANY WARRANTY; without even the implied warranty of
#       MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#       GNU General Public License for more details.
#
#       You should have received a copy of the GNU General Public License
#       along with this program; if not, the license can be downloaded here:
#
#       http://www.gnu.org/licenses/gpl.html

# Meta
__version__ = '0.1.1'
__license__ = "GNU General Public License (GPL) Version 3"
__version_info__ = (0, 1, 1)
__author__ = 'Michael Liebler <michael-liebler@radio-z.net>'

"""
Comba Scheduler Klasse 
"""
import signal
import pyev
import os
import os.path
import time
import simplejson
import datetime
from datetime import timedelta
from dateutil.relativedelta import *
import logging
from glob import glob
import threading

# Die eigenen Bibliotheken
from comba_lib.base.combabase import CombaBase
from comba_lib.base.schedulerconfig import CombaSchedulerConfig
from comba_lib.reporting.messenger import CombaMessenger
from comba_lib.service.calendar import CombaCalendarService
from comba_lib.database.broadcasts import *
from modules.scheduler.models import *

"""
Comba Scheduler Class 
Liefert Start und Stop Jobs an den Comba Controller, lädt XML-Playlisten und räumt auf 
"""


class CombaScheduler(CombaBase):

    def __init__(self, CombaClient_instance, config):
        """
        Constructor
        @type    CombaClient_instance: object
        @param   CombaClient_instance: Der Client für Liquidsoap
        @type    config:               string
        @param   config:               Pfad zum scheduler.xml
        """
        self.client = CombaClient_instance
        self.loadConfig()
        # Messenger für Systemzustände initieren
        self.messenger = CombaMessenger()
        self.messenger.setChannel('scheduler')
        self.messenger.setSection('execjob')
        self.messenger.setMailAddresses(self.get('frommail'), self.get('adminmail'))
        self.config_path = config
        self.config = object

        # Die Signale, die Abbruch signalisieren
        self.stopsignals = (signal.SIGTERM, signal.SIGINT)

        # das pyev Loop-Object
        self.loop = pyev.default_loop()

        # Das ist kein Reload
        self.initial = True

        # Der Scheduler wartet noch auf den Start Befehl
        self.ready = False

        # DIe Config laden
        self._loadConfig()

        self.scriptdir = os.path.dirname(os.path.abspath(__file__)) + '/..'

        errors_file = os.path.dirname(os.path.realpath(__file__)) + '/error/combas_error.js'
        json_data = open(errors_file)
        self.errorData = simplejson.load(json_data)

        self.messenger.send('Scheduler started', '0000', 'success', 'initApp', None, 'appinternal')

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
    def reload(self):
        """
        Reload Scheduler - Config neu einlesen
        """
        self.stop()
        # Scheduler Config neu laden
        if self._loadConfig():
            self.messenger.send('Scheduler reloaded by user', '0500', 'success', 'reload', None, 'appinternal')
        self.start()

    #------------------------------------------------------------------------------------------#
    def _loadConfig(self):
        """
        Scheduler-Config importieren
        @rtype:   boolean
        @return:  True/False
        """
        # Wenn das Scheduling bereits läuft, muss der Scheduler nicht unbedingt angehalten werden         
        error_type = 'fatal' if self.initial else 'error'
        watcher_jobs = self.getJobs()
        try:
            # Die Jobs aus der Config ...
            watcher_jobs = self.getJobs()
        except:
            self.messenger.send('Config is broken', '0301', error_type, 'loadConfig', None, 'config')
            if self.initial:
                self.ready = False
            return False

            # Fehlermeldung senden, wenn keine Jobs gefunden worden sind
        if len(watcher_jobs) == 0:
            self.messenger.send('No Jobs found in Config', '0302', error_type, 'loadConfig', None, 'config')

        # Der erste Watcher ist ein Signal-Watcher, der den sauberen Abbruch ermöglicht
        self.watchers = [pyev.Signal(sig, self.loop, self.signal_cb)
                         for sig in self.stopsignals]

        # Der zweite Watcher soll das Signal zum Reload der Config ermöglicen
        sig_reload = self.loop.signal(signal.SIGUSR1, self.signal_reload)

        self.watchers.append(sig_reload)

        # Der dritte Watcher sendet alle 20 Sekunden ein Lebenszeichen
        say_alive = self.loop.timer(0, 20, self.sayAlive)

        self.watchers.append(say_alive)

        # Der vierte Watcher schaut alle 20 Sekunden nach, ob eine Vorproduktion eingespielt werden soll
        lookup_prearranged = self.loop.timer(0, 20, self.lookup_prearranged)

        self.watchers.append(lookup_prearranged)

        # Der fünfte Watcher führt initiale Jobs durch
        on_start = self.loop.timer(0, 30, self.on_start)

        self.watchers.append(on_start)

        # Nun Watcher für alle Jobs aus der Config erstellen 
        for watcher_job in watcher_jobs:
            watcher = pyev.Scheduler(self.schedule_job, self.loop, self.exec_job, watcher_job)
            # Jeder watcher wird von der Scheduler Funktion schedule_job schedult und vom Callback exec_job ausgeführt
            # watcher_job wird an watcher.data übergeben 
            # schedule_job meldet an den Loop den nächsten Zeitpunkt von watcher_job['time']
            # exec_job führt die Funktion dieser Klasse aus, die von watcher_job['job'] bezeichnet wird
            self.watchers.append(watcher)

        # Es kann losgehen        
        self.ready = True
        return True

    def getJobs(self):
        error_type = 'fatal' if self.initial else 'error'
        try:
            # Das scheduler.xml laden
            self.config = CombaSchedulerConfig(self.config_path)
        except:
            # Das scheint kein gültiges XML zu sein
            self.messenger.send('Config is broken', '0301', error_type, 'loadConfig', None, 'config')
            # Wenn das beim Start passiert können wir nix tun
            if self.initial:
                self.ready = False
            return False
        jobs = self.config.getJobs()
        
        for job in jobs:
            if job['job'] == 'start_recording' or job['job'] == 'play_playlist':
                stopjob = self._getStopJob(job)
                jobs.append(stopjob)
                
        return jobs   
            
    # -----------------------------------------------------------------------#
    def _getStopJob(self, startjob):
         job = {}
         job['job'] = 'stop_playlist' if startjob['job'] == 'play_playlist' else 'stop_recording'
         if startjob['day'] == 'all':
             job['day'] = startjob['day']
         else:
             
             if startjob['time'] < startjob['until']:
                 job['day'] = startjob['day']
             else:
                try:
                     day = int(startjob['day'])
                     stopday = 0 if  day > 5 else day+1
                     job['day'] = str(stopday)
                except:
                    job['day'] = 'all'
                
         job['time'] = startjob['until']  
         return job

    #------------------------------------------------------------------------------------------#
    def start(self):
        """
        Event Loop starten
        """
        # Alle watcher starten
        for watcher in self.watchers:
            watcher.start()

        logging.debug("{0}: started".format(self))
        try:
            self.loop.start()
        except:
            self.messenger.send("Loop did'nt start", '0302', 'fatal', 'appstart', None, 'appinternal')
        else:
            self.messenger.send("Scheduler started", '0100', 'success', 'appstart', None, 'appinternal')

    #------------------------------------------------------------------------------------------#
    def stop(self):
        """
        Event Loop stoppen
        """
        self.loop.stop(pyev.EVBREAK_ALL)
        # alle watchers stoppen und entfernen
        while self.watchers:
            self.watchers.pop().stop()
        self.messenger.send("Loop stopped", '0400', 'success', 'appstart', None, 'appinternal')

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
        self.messenger.send("Received stop signal", '1100', 'success', 'appstop', None, 'appinternal')
        self.stop()

    #------------------------------------------------------------------------------------------#
    def signal_reload(self, loop, revents):
        """
        Lädt Scheduling-Konfiguration neu bei Signal SIGUSR1
        @type  loop: object
        @param loop: Das py_ev loop Objekt
        @type  revents: object
        @param revents: Event Callbacks        
        """
        self.messenger.send("Comba Scheduler gracefull restarted", '1200', 'success', 'appreload', None, 'appinternal')
        self.reload()

    #------------------------------------------------------------------------------------------#
    def schedule_job(self, watcher, now):
        """
        Callback zum Scheduling eines Jobs
        @type  watcher:  object
        @param watcher:  Das watcher Objekt
        @type  now:      float 
        @param now:      Aktuelle Zeit in Sekunden        
        @rtype:          float
        @return:         Die Zeit zu der der Job ausgeführt werden soll in Sekunden
        """
        # nächstes Ereignis dieses Watchers aus den watcher data
        data = watcher.data.copy()
        next_schedule = data['time']

        # Minuten und Stunden
        (next_hour, next_minute) = next_schedule.split(':')

        # Zum Vergleich die aktuelle und die auszuführende Unhrzeit in Integer wandeln
        today_time = int(datetime.datetime.now().strftime('%H%M'))
        next_time = int(next_hour + next_minute)

        # Wenn der Job erst morgen ausgeführt werden soll ist day_offset 1 
        day_offset = 1 if (today_time >= next_time) else 0

        # Ist ein Tag angegeben
        if data.has_key('day'):
            try:
                #Montag ist 0 
                dayofweek = int(data['day'])
                delta = relativedelta(hour=int(next_hour), minute=int(next_minute), second=0, microsecond=0,
                                      weekday=dayofweek)
            except:
                #Fallback -  day ist vermutlich ein String
                delta = relativedelta(hour=int(next_hour), minute=int(next_minute), second=0, microsecond=0)
        else:
            delta = relativedelta(hour=int(next_hour), minute=int(next_minute), second=0, microsecond=0)

        # Ermittle das Datumsobjekt 
        schedule_result = datetime.datetime.now() + timedelta(day_offset) + delta

        # In Sekunden umrechnen
        result = time.mktime(schedule_result.timetuple())

        schedule_time_human = datetime.datetime.fromtimestamp(int(result)).strftime('%Y-%m-%d %H:%M:%S')
        time_now = datetime.datetime.fromtimestamp(time.time()).strftime('%Y-%m-%d %H:%M:%S')
        date_human = datetime.datetime.fromtimestamp(int(result)).strftime('%Y-%m-%d')
        time_human = datetime.datetime.fromtimestamp(int(result)).strftime('%H:%M')
        # Events feuern, zum stoppen und starten einer Playlist
        # TODO: Diese events müssen bei einem Reset gelöscht werden       
        # Es sollte sicher sein, einfach alle keys mit  playerevent_*_playliststart unc playerevent_*_playliststop zu löschen
        if data.has_key('job'):
            if data['job'] == 'play_playlist':
                event = {'job': 'play_playlist', 'date': date_human, 'time': time_human}
                self.messenger.queueAddEvent('playliststart', str(schedule_time_human).replace(' ', 'T'), event,
                                             'player')
            if data['job'] == 'stop_playlist':
                event = {'job': 'stop_playlist', 'date': date_human, 'time': time_human}
                self.messenger.queueAddEvent('playliststop', str(schedule_time_human).replace(' ', 'T'), event,
                                             'player')

        data['scheduled_at'] = time_now
        data['scheduled_for'] = schedule_time_human

        self.info('schedule_job', data, '00', simplejson.dumps(data), 'schedulejob')

        # das nächste mal starten wir diesen Job in result Sekunden 
        return result

    #------------------------------------------------------------------------------------------#
    def exec_job(self, watcher, revents):
        """
        Callback, um einen Job auszuführen
        @type  watcher:  object
        @param watcher:  Das watcher Objekt
        @type  revents:  object
        @param revents:  Event Callbacks     
        """
        data = watcher.data.copy()

        # Welcher Job ausgeführt werden soll wird in watcher.data vermerkt
        job = data['job']

        # Job ausführen
        try:
            exec "a=self." + job + "(data)"
        except Exception, e:
            data['exec'] = 'exec"a=self.' + job + '(' + simplejson.dumps(data) + ')"'
            data['Exception'] = str(e)
            self.fatal('exec_job', data, '01', simplejson.dumps(data))
            watcher.stop()  #stop the watcher
        else:
            self.success('exec_job', data, '00', simplejson.dumps(data))

    #------------------------------------------------------------------------------------------#
    def clearChannel(self, channel):
        """
        Schaltet auto-Channel aus und common-Channel ein
        Skippt anschließend ggf. verbleibende Tracks vom auto-Channel
        @type channel: str
        @param channel:  Kanal
        """
        def _get_data(result):
            """
            Untermethode: prüft ob noch tracks im Channel Queue sind
            """
            try:
                if result['success'] == 'success':
                    if 'value' in result:
                        return  result['value']
                    else:
                        return True
                else:
                    return False
            except:
                return False

        # Common Channel laut
        self.client.channel_set_volume('common', 100)
        # Auto-Channel leise
        self.client.channel_set_volume(channel, 0)
        # Channel Queue holen
        data = self.client.get_channelqueue(channel)
        # Channel initial skippen...
        self.client.channel_skip(channel)
        queue = _get_data(data)

        # ...für jeden track erneut skippen
        if queue and 'tracks' in queue:
            tracks = queue['tracks']
            for track in tracks:
                time.sleep(1.0)
                self.client.channel_skip(channel)

        # Auto Channel für erneute Verwendung ausschalten und laut stellen
        self.client.channel_off(channel)
        self.client.channel_set_volume(channel, 100)

    #------------------------------------------------------------------------------------------#
    def runChannel(self, channel):
        self.client.channel_set_volume('common', 0)
        self.client.channel_set_volume(channel, 100)
        self.client.channel_on(channel)

    #------------------------------------------------------------------------------------------#
    def lookup_prearranged(self, watcher, revents):
        """
        Job-Methode. Spielt ggf. Vorproduktionen aus
        Diese wird als Trackliste auf einen von zwei Extra-Channels (auto1 und 2) gelegt

        @type  watcher:  object
        @param watcher:  Das watcher Objekt
        @type  revents:  object
        @param revents:  Event Callbacks
        """

        # Vorproduktion in den nächsten 20 Sekunden vorgemerkt?
        tracks = ModelBroadcastEventOverrides.upcoming(datetime.datetime.now(),20)

        if tracks and len(tracks) > 0:
            # alle tracks enthalten die Information über den zugehörigen broadcast event
            event = tracks[0].broadcast_event

            # freien preprod channel checken,
            channel = 'auto1'
            if not self.client.channel_is_active('auto1'):
                channel = 'auto1'
            elif not self.client.channel_is_active('auto2'):
                channel = 'auto2'
            else:
                self.error('lookup_prearranged', "false", '01')
                return

            # tracks in preprod channel laden
            pos = 0
            for track in tracks:

                self.client.channel_track_insert(channel, track.location, pos)
                pos = pos + 1

            now = datetime.datetime.now()

            # zeitgesteuert einschalten
            on = (event.start - now).total_seconds()
            threading.Timer(on, self.runChannel,[channel]).start()

            # zeitgesteuert skippen
            off = (event.end - now).total_seconds()
            threading.Timer(off, self.clearChannel,[channel]).start()

    #------------------------------------------------------------------------------------------#
    def on_start(self, watcher, revents):

        if self.get('has_input_device'):

            self.client.playlist_play()
            self.client.playlist_pause()
        watcher.stop()


    #------------------------------------------------------------------------------------------#
    def load_playlist(self, data):
        """
        Playlist laden
        """

        store = CombaCalendarService()
        self._preparePlaylistStore(store, datetime.datetime.now(), data)
        uri = store.getUri()
        store.start()

        # wait until childs thread returns
        store.join()

        data = {}
        data['uri'] = uri

        result = self.client.playlist_load(uri)
        if self._check_result(result):
            self.success('load_playlist', data, '00')
        else:
            self.error('load_playlist', data, '02')

    #------------------------------------------------------------------------------------------#
    def _preparePlaylistStore(self, store, dateBegin, data):

        """
        Playlist speichern
        """

        try:
            fromtime = data['from']
            until = data['until']
        except:
            return


        # Das aktuelle Datum
        today_time = dateBegin.strftime('%H:%M')

        # Wir müssen ermitteln, ob die eigentliche Abspielzeit vielleicht erst morgen ist

        day_offset = 1 if (today_time > fromtime) else 0
        start_date = dateBegin + timedelta(day_offset)

        # datefrom ist Datum, an dem die Playlist beginnen soll
        datefrom =  str(start_date.strftime('%F')) + ' ' + fromtime


        # Die Playlist holen

        store.setDateFrom(datefrom)
        store.setUntilTime(until)

    #------------------------------------------------------------------------------------------#
    def play_playlist(self, data):
        """
        Playlist starten
        """
        #TODO: Fehler auswerten
        result = self.client.playlist_play()
        if self._check_result(result):
            self.success('play_playlist', result, '00')
        else:
            self.error('play_playlist', result, '01')

    #------------------------------------------------------------------------------------------#
    def stop_playlist(self, data):
        """
        Playlist anhalten
        """
        #TODO: Fehler auswerten
        if self.get('has_input_device'):
            result = self.client.playlist_pause()
        else:
            result = self.client.playlist_stop()

        if self._check_result(result):
            self.success('stop_playlist', result, '00')
        else:
            self.error('stop_playlist', result, '01')

    #------------------------------------------------------------------------------------------#
    def start_recording(self, data):
        """
        Aufnahme starten
        """
        result = self.client.recorder_start()
        store = CombaCalendarService()
        self._preparePlaylistStore(store, datetime.datetime.now(), data)
        uri = store.getUri()
        store.start()
        if self._check_result(result):
            self.success('start_recording', result, '00')
        else:
            self.error('start_recording', result, '01')

    #------------------------------------------------------------------------------------------#
    def stop_recording(self, data):
        """
        Aufnahme anhalten
        """
        result = self.client.recorder_stop()
        if self._check_result(result):
            self.success('stop_recording', result, '00')
        else:
            self.error('stop_recording', result, '01')

    #------------------------------------------------------------------------------------------#
    def precache(self, data):
        """
        Playlisten 7 Tage im Voraus abholen
        """
        periods = self.config.getPlayPeriods() +  self.config.getRecordPeriods()
        timeBegin = datetime.datetime.now()
        for i in range(0, int(self.get('calendar_precache_days'))):
            for period in periods:

                store = CombaCalendarService()
                self._preparePlaylistStore(store, timeBegin, period)
                store.start()
                counter = 40
                while  counter > 0  and store.is_alive():
                    counter = counter - 1
                    time.sleep(0.1)

            timeBegin =  timeBegin + datetime.timedelta(1)


        self.success('precache')

    #------------------------------------------------------------------------------------------#
    def clean_cached(self, data):
        """
        Nicht mehr benötigte Audios und Playlisten löschen
        @type  data:  dict
        @param data:  das job dict
        """
        # Zeitdauer, die  Dateien aufgehoben werden sollen
        try: 
            savetime = int(data['daysolder']) * 86400
        except:
            savetime = 3*86400 
        # Jetzt ist Jetzt
        now = time.time()
        files = []
        # Alle Audiodateien finden
        for dir, _, _ in os.walk(self.audiobase):
            # Leere Verzeichnisse löschen
            if len(os.listdir(dir)) == 0:
                try:
                    os.rmdir(dir)
                except:
                    #TODO: Fehlemeldung
                    pass
            else:
                files.extend(glob(os.path.join(dir, '*.wav')))

        # Alle Dateien löschen, die älter als savetime sind
        for file in files:
            if os.path.isfile(file) and os.stat(file).st_mtime < now - savetime:
                try:
                    os.remove(file)
                except:
                    #TODO: Fehlemeldung
                    pass
        self.success('clean_cached')

    #------------------------------------------------------------------------------------------#
    def _getError(self, job, errornumber, data):
        """
        Privat: Ermittelt Fehlermeldung, Job-Name (Klassenmethode) und Fehlercode für den Job aus error/combac_error.js
        @type errornumber:  string
        @param errornumber: Die interne Fehlernummer der aufrufenden Methode  
        """
        ### weil es eine "bound method" ist, kommmt data als string an!???
        if data == None:
            data = {}
        if type(data) == type(str()):
            data = simplejson.loads(data)

        hasData = isinstance(data, (dict)) and len(data) > 0

        if self.errorData.has_key(job):
            errMsg = self.errorData[job][errornumber]
            errID = self.errorData[job]['id'] + str(errornumber)
            if hasData:
                for key in data.keys():
                    errMsg = errMsg.replace('::' + key + '::', str(data[key]))
            data['message'] = errMsg
            data['job'] = job
            data['code'] = errID
        return data

    #------------------------------------------------------------------------------------------#
    def success(self, job, data=None, errnum='00', value='', section='execjob'):
        """
        Erfolgsmeldung loggen
        @type errnum:    string
        @param errnum:   Errornummer der aufrufenden Funktion
        @type value:     string
        @param value:    Optionaler Wert 
        @type section:   string
        @param section:  Gültigkeitsbereich        
        """
        error = self._getError(job, errnum, data)
        self.job_result = {'message': error['message'], 'code': error['code'], 'success': 'success',
                           'job': error['job'], 'value': value, 'section': section}
        self.messenger.send(error['message'], error['code'], 'success', error['job'], value, section)

    #------------------------------------------------------------------------------------------#
    def info(self, job, data=None, errnum='01', value='', section='execjob'):
        """
        Info loggen
        @type errnum:    string
        @param errnum:   Errornummer der aufrufenden Funktion
        @type value:     string
        @param value:    Optionaler Wert 
        @type section:   string
        @param section:  Gültigkeitsbereich                
        """
        error = self._getError(job, errnum, data)
        self.job_result = {'message': error['message'], 'code': error['code'], 'success': 'info', 'job': error['job'],
                           'value': value, 'section': section}
        self.messenger.send(error['message'], error['code'], 'info', error['job'], value, section)

    #------------------------------------------------------------------------------------------#
    def warning(self, job, data=None, errnum='01', value='', section='execjob'):
        """
        Warnung loggen
        @type errnum:    string
        @param errnum:   Errornummer der aufrufenden Funktion
        @type value:     string
        @param value:    Optionaler Wert 
        @type section:   string
        @param section:  Gültigkeitsbereich                
        """
        error = self._getError(job, errnum, data)
        self.job_result = {'message': error['message'], 'code': error['code'], 'success': 'warning',
                           'job': error['job'], 'value': value, 'section': section}
        self.messenger.send(error['message'], error['code'], 'warning', error['job'], value, section)

    #------------------------------------------------------------------------------------------#
    def error(self, job, data=None, errnum='01', value='', section='execjob'):
        """
        Error loggen
        @type errnum:    string
        @param errnum:   Errornummer der aufrufenden Funktion
        @type value:     string
        @param value:    Optionaler Wert 
        @type section:   string
        @param section:  Gültigkeitsbereich                
        """
        error = self._getError(job, errnum, data)
        self.job_result = {'message': error['message'], 'code': error['code'], 'success': 'error', 'job': error['job'],
                           'value': value, 'section': section}
        self.messenger.send(error['message'], error['code'], 'error', error['job'], value, section)

    #------------------------------------------------------------------------------------------#
    def fatal(self, job, data=None, errnum='01', value='', section='execjob'):
        """
        Fatal error loggen
        @type errnum:    string
        @param errnum:   Errornummer der aufrufenden Funktion
        @type value:     string
        @param value:    Optionaler Wert 
        @type section:   string
        @param section:  Gültigkeitsbereich                
        """
        error = self._getError(job, errnum, data)
        self.job_result = {'message': error['message'], 'code': error['code'], 'success': 'fatal', 'job': error['job'],
                           'value': value, 'section': section}
        self.messenger.send(error['message'], error['code'], 'fatal', error['job'], value, section)

    #------------------------------------------------------------------------------------------#
    def _check_result(self, result):
        """
        Fehlerbehandlung
        @type     result: string
        @param    result: Ein Json-String
        """
        try:
            self.lq_error = simplejson.loads(result)
        except:
            return False

        try:
            if self.lq_error['success'] == 'success':
                return True
            else:
                return False
        except:
            return False