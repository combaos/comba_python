#!/usr/bin/python
# -*- coding: utf-8 -*-
from modules.controller import *
from comba_lib.reporting.messenger import CombaMessenger
from comba_lib.security.user import CombaUser
from comba_lib.utils.parsexml import *
from comba_lib.base.schedulerconfig import CombaSchedulerConfig
import simplejson
import tempfile
import os
import psutil  
import signal  
import sys
import logging
import urllib2
import random
import string
import base64
import codecs

"""
    CombaController Class
    Die Kommunikation des Controllers mit dem Soundserver
    Benötigt die LiquidsoapClient Klasse
"""
class CombaController(object):
    
    # Constructor
    def __init__(self, sender, lqs_socket, lqs_recsocket):
        """
        Constructor
        @type    sender: object
        @param   sender: Der Communicator Adapter - z-B. zmq
        @type    lqs_socket: string 
        @param   lqs_socket: Liquidsoap Player Socket
        @type    lqs_recsocket: string
        @param   lqs_recsocket: Liquidsoap Recorder Socket 
        """
        # Der Liquidsoap Client
        self.lqc = LiquidsoapClient(lqs_socket)
        self.lqcr = LiquidsoapClient(lqs_recsocket)
        # Felder die Liquidsoap fuer einen Track (rid) zurueckliefert
        self.knownfields = ["status", "album","time","title","artist","comment","filename","on_air","source","rid", "genre"]  
        self.lq_error = ''
        self.sender = sender
        self.is_intern = False
        self.messenger = CombaMessenger()
        self.messenger.setChannel('controller')
        self.messenger.setSection('execjob')
        self.userdb = CombaUser()
        self.job_result = ['', '', '', '','', '']
        errors_file = os.path.dirname(os.path.realpath(__file__)) + '/error/combac_error.js'
        json_data = open(errors_file)
        self.errorData = simplejson.load(json_data)

    #------------------------------------------------------------------------------------------#
    def message(self, message, log=False, warning=False):
        """
        Daten an einen Client senden oder bei einer internen Aktion loggen
        @type     message: string
        @param    message: String, der gesendet wird
        @type     log: boolean
        @param    log: Wenn falsch, wird die message an den Client gesendet
        @type     warning: boolean
        @param    warning: Wenn falsch, ist der logging typ info, andernfalls warning
        @rtype:   string/None
        @return:  Die Message, falls log false ist
        """
        if not self.is_intern:
            self.sender.send(message)
        else:
            return message
        if log: 
            if warning:
                    logging.warning(message) 
            else:     
                logging.info(message) 

    #------------------------------------------------------------------------------------------#
    def allData(self):
        """
        Gibt Metadaten aller Kanäle als JSON-String an den Client zurück 
        @rtype:   string/None
        @return:  Die Antwort des Liquidsoap-Servers

        """        
        channels = self.sendLqcCommand(self.lqc, 'listChannels')
        
        if not isinstance(channels, list):
            self.warning('01')
            self.notifyClient()
            return 
        
        data = {}
        pdata = {}
                      
        try:
            self.is_intern = True  
            playlist_data = simplejson.loads(self.playlist_data(True))
            self.is_intern = False
        except:
            self.warning('01')            
            self.notifyClient()
            return
                    
        # Status des Playlistkanals abfragen
        status = self.sendLqcCommand(self.lqc, 'status', 'mixer', '0')
        
        states = status.split(' ')
        state_data = {}
        
        # Die Stati in python dicts einlesen
        for state in states:
            item = state.split('=')
            try:
                state_data[item[0]] = item[1]
            except:
                self.warning('01')
                self.notifyClient()
                return
        
        remaining = self.sendLqcCommand(self.lqc, 'playlist_remaining')
        state_data['remaining'] = remaining
        # Die Metadaten der Playlist
        pdata['state'] = state_data
        pdata['tracks'] = playlist_data        
        data['playlist'] = pdata
        
        # Servermeldungen abschalten
        self.is_intern = True                
        # die channel queues einlesen
        
        for channel in channels:
            data[channel] = self.channel_queue(channel, True)        
        # Servermeldungen einschalten
        self.is_intern = False
        self.success('00', data)
        self.notifyClient()

    #------------------------------------------------------------------------------------------#
    def ping(self):
        """
        dem Client antworten
        """
        return self.message('OK')

    #------------------------------------------------------------------------------------------#
    def channel_insert(self, channel, uri, pos):
        """
        Track in einen Channel einfuegen 
        @type     channel: string
        @param    channel: Kanal
        @type     uri:     string
        @param    uri:     Uri - z.B. file:///my/audio/mp3 
        @type     pos:     int
        @param    pos:     Die Position an der eingefügt werden soll        
        @rtype:   string/None
        @return:  Die Antwort des Liquidsoap-Servers                
        """
        message = self.sendLqcCommand(self.lqc, 'insert', uri, pos, channel)
        message = message.strip()
        
        try:
            if int(message) > -1:                
                self.success()
                return self.message(message)        
        except:
            self.warning('01')
            self.notifyClient()                    

    #------------------------------------------------------------------------------------------#
    def channel_move(self, channel, fromPos, toPos):        
        """
        Channel-Eintrag von Position fromPos nach Position toPos verschieben 
        @type     channel: string
        @param    channel: Kanal
        @type     fromPos: int
        @param    fromPos: die Position des Eintrags, der verschoben wird 
        @type     toPos:   int
        @param    toPos:   Zielposition             
        @rtype:   string
        @return:  Die Antwort des Liquidsoap-Servers           
        """

        message = self.sendLqcCommand(self.lqc, 'get_queue', channel,'secondary_queue')

        rids = message.strip().split(' ')
        
        try:
            rid = rids[int(fromPos)-1]
        except:
            self.warning('01')
            self.notifyClient()
            return
        try:
            target = rids[int(toPos)-1]
        except:
            self.warning('01') 
            self.notifyClient()  
            return
            
        if rids[int(fromPos)-1] == rids[int(toPos)-1]:
            self.warning('02')
            self.notifyClient()
            return
        
        message = self.sendLqcCommand(self.lqc, 'move', rid, str(int(toPos)-1), channel)        
        message = message.strip()

        if message.strip().find('OK') > -1:
                self.success()                                
                self.notifyClient()
                return        
        else:
            self.warning('03')            
            self.notifyClient()                

    #------------------------------------------------------------------------------------------#
    def channel_off(self, channel):
        """
        Channel deaktivieren 
        @type     channel: string
        @param    channel: Kanal
        @rtype:   string
        @return:  Die Antwort des Liquidsoap-Servers        
        """        
        # internal channel name for playlist is 'common'
        if channel == 'playlist':
            channel = 'common'

        channels = self.sendLqcCommand(self.lqc, 'listChannels', False)

        index = channels.index(channel)            
        message = self.sendLqcCommand(self.lqc, 'deactivate', str(index))        
        if message.find('selected=false'):
            self.success()            
        else:
            self.warning('01')
        
        self.notifyClient()

    #------------------------------------------------------------------------------------------#
    def channel_on(self, channel):
        """
        Channel aktivieren 
        @type     channel: string
        @param    channel: Kanal
        @rtype:   string
        @return:  Die Antwort des Liquidsoap-Servers               
        """                
        # Find channels
        if channel == 'playlist':
            channel = 'common'
        
        channels = self.sendLqcCommand(self.lqc, 'listChannels', False)
        
        index = channels.index(channel)        
        #a activate channel    
        message = self.sendLqcCommand(self.lqc, 'activate', str(index))        
        
        if message.find('selected=true'):
            self.success()
        else:
            self.warning('01')
        
        self.notifyClient()

    #------------------------------------------------------------------------------------------#
    def channel_queue(self, channel, raw=False):
        """
        Channel Queue abrufen 
        @type     channel: string
        @param    channel: Kanal
        @type     raw:     boolean
        @param    raw:     Wenn true, Rückgabe als Python dict Object, andernfalls als JSON-String
        @rtype:   string/dict
        @return:  Der Channel Queue               
        """        
        data = {}
        
        # queue will return request id's (rids)
        
        message = self.sendLqcCommand(self.lqc, 'get_queue', channel)
              
        rids = message.strip().split(' ')
        data['tracks'] = []               
        for rid in rids:
            if rid != '':
                # get each rids metadata
                metadata = self.sendLqcCommand(self.lqc, 'getMetadata', rid)
                track = self._metadata_format(metadata)
                if not track.has_key('title'):
                    if track.has_key('location'):
                        track['title'] = os.path.basename(track['location'])
                    elif track.has_key('filename'):
                        track['title'] = os.path.basename(track['filename'])
                    else:
                        track['title'] = 'unknown' 
                        
                data['tracks'].extend([track])
        channels = self.sendLqcCommand(self.lqc, 'listChannels')   
        
        """
        now get channels state 
        self.lqc.status: ready=false volume=100% single=false selected=false remaining=0.00
        """        
        try:
            index = channels.index(channel)           
            status = self.sendLqcCommand(self.lqc, 'status', 'mixer', str(index + 1))            
            states = status.split(' ')            
            state_data = {}
            for state in states:
                item = state.split('=')
                if len(item) > 1:
                    state_data[item[0]] = item[1]
        except:
            state_data = {}
            self.error('01')
            self.notifyClient()
            return 
            
         
        data['state'] = state_data
        
        if raw:
            # return the list internal
            data['state'] = state_data            
            return data
        else:
            self.success('00', data)
            self.notifyClient()

    #------------------------------------------------------------------------------------------#
    def channel_remove(self, channel, pos):
        """
        Channel-Eintrag löschen 
        @type     channel: string
        @param    channel: Kanal
        @type     pos:     int
        @param    pos:     Position des Eintrags                      
        """               
        # Es kann nur vom Secondary Queue gelöscht werden
        # Falls der Track im Primary Queue gelöscht werden soll, ist ein skip nötg  

        message = self.sendLqcCommand(self.lqc, 'get_queue', channel, 'secondary_queue')        
        rids = message.strip().split(' ')
        try:
            rid = rids[int(pos)-1]
        except:
            self.warning('02')
            self.notifyClient()
            return
        message = self.sendLqcCommand(self.lqc, 'remove', rid, channel)
        if message.find('OK') > -1:
            self.success()
        else:
            self.warning('01')

        self.notifyClient()          

    #------------------------------------------------------------------------------------------#
    def channel_seek(self, channel, duration):
        """
        Im aktuell spielenden Track auf dem Kanal <channel> <duration> Sekunden "vorspulen"
        @type     channel:  string
        @param    channel:  Kanal
        @type     duration: int
        @param    duration: Dauer in Sekunden               
        """                
        # Liquidsoap Kommando        
        data = self.sendLqcCommand(self.lqc, 'seek', duration, channel)
                
        # Resultate prüfen
        if self._check_result(data):        
                self.success('00', self.lq_error['value'])
        else:    
            self.warning('01')
        
        self.notifyClient()                        

    #------------------------------------------------------------------------------------------#
    def channel_skip(self, channel):
        """
        Kanal skippen 
        @type     channel:  string
        @param    channel:  Kanal      
        """                        
        # Liquidsoap Kommando
        channels = self.sendLqcCommand(self.lqc, 'listChannels')

        foundChannel = ''
        if not isinstance(channels, list):
            self.error('02')    
        else:        
            for index, item in enumerate(channels):
                if item == channel:
                    foundChannel = self.sendLqcCommand(self.lqc, 'skip', 'mixer', str(index + 1))
                    break
               
            if foundChannel.strip().find('OK') > -1:
                self.success()
            elif len(channels) < 1:
                self.warning('01')            
            else:
                self.error('03')                                
        
        self.notifyClient()

    #------------------------------------------------------------------------------------------#
    def channel_volume(self, channel, volume):
        """
        Lautstärke auf Kanal <channel> setzen
        @type     channel:  string
        @param    channel:  Kanal
        @type     volume:   int
        @param    volume:  Lautstärke von 1-100               
        """        
                
        if channel == 'playlist':
            channel = 'common'
        # Liquidsoap Kommando
        channels = self.sendLqcCommand(self.lqc, 'listChannels', False)
                
        try: 
            index = channels.index(channel)
            if len(channel) < 1:
                self.warning('02')
        except:
            self.error('03')
            
        else:
            message = self.sendLqcCommand(self.lqc, 'volume', str(index), str(int(volume)))

            if message.find('volume=' + str(volume) + '%'):
                self.success('01', str(volume))
            else:
                self.warning('01')
        
        self.notifyClient()                 

    #------------------------------------------------------------------------------------------#
    def currentData(self):
        """
        Metadaten des gespielten Tracks im JSON-Format
        Beispiel: {"title": "Deserted Cities of the Heart", "filename": "/home/michel/Nas-audio/cream/the_very_best_of/17_Deserted_Cities_of_the_Heart.mp3", "source": "ch2", "on_air": "2014/07/23 23:46:37",  "rid": "2"}               
        """          
        # Liquidsoap Kommando
        message = self.sendLqcCommand(self.lqc, 'currentTrack')      
        
        rid = message.strip()        
        
        metadata = self.sendLqcCommand(self.lqc, 'getMetadata', rid)                    

        data = self._metadata_format(metadata)
        
        if data:
            self.success('00', simplejson.dumps(data))
        elif rid == '':
            self.warning('01')
        else:
            self.warning('02', rid)
        
        self.notifyClient()

    #------------------------------------------------------------------------------------------#
    def get_channel_state(self, channel):        
        if channel == 'playlist':
            channel = 'common'
            
        channels = self.sendLqcCommand(self.lqc, 'listChannels', False)

        index = channels.index(channel)        
        state_data = {}
        try:
            index = channels.index(channel)           
            status = self.sendLqcCommand(self.lqc, 'status', 'mixer', str(index + 1))            
            states = status.split(' ')                        
            for state in states:
                item = state.split('=')
                if len(item) > 1:
                    state_data[item[0]] = item[1]
        except:
            state_data = {}
            self.error('01')
            self.notifyClient()
            return 
        self.success('00', simplejson.dumps(state_data))        
        self.notifyClient()                    

    #------------------------------------------------------------------------------------------#
    def help(self):        
        """
        Gibt die Hilfe aus                 
        """
        errNum = '11'
        try:
            file = open(os.path.dirname(os.path.abspath(__file__)) +  '/doc/comba.hlp', 'r')
            doc = file.read()
            return self.message(doc)
        except:
            self.warning('01')
            self.notifyClient()

    #------------------------------------------------------------------------------------------#
    def listChannels(self):
        """
        Channels auflisten (Simple JSON)                      
        """           
        # Liquidsoap Kommando
        channels = self.sendLqcCommand(self.lqc, 'listChannels')      
        
        if not isinstance(channels, list):
            self.error('02')
        elif len(channels) < 1:            
            self.warning('01')
        else:
            self.success('00', channels)
        
        self.notifyClient()      

    #------------------------------------------------------------------------------------------#
    def playlist_data(self, raw=False):
        """
        Aktuelle Playlist Daten im JSON-Format                  
        """
        
        # Liquidsoap Kommando
        data = self.sendLqcCommand(self.lqc, 'playlistData')
        if not raw:
            self.success('00', simplejson.loads(data))
            self.notifyClient()
        else:
            return data     
           
    #------------------------------------------------------------------------------------------#
    def playlist_flush(self):
        """
        Aktuelle Playlist leeren           
        """ 
        data = self.sendLqcCommand(self.lqc, 'flush')               
        self.success('00') 
        self.notifyClient()        

    #------------------------------------------------------------------------------------------#
    def playlist_insert(self, uri, pos):
        """
        Track in die Playlist einfuegen                        
        """                        
        data = self.sendLqcCommand(self.lqc, 'insert', uri, pos)
        if not self._check_result(data):
            self.warning('01')
        else:
            self.success('00') 
        self.notifyClient()
        
    #------------------------------------------------------------------------------------------#
    def playlist_load(self, uri):
        """
        Playlist laden        
        @type   uri:   string
        @param  uri:   Uri der Playlist          
        """

        try:
            xml = urllib2.urlopen(uri).read().decode('utf8')

        except:
            try:
                xml = open(uri).read().decode('utf8')
            except:
                self.error('01', self.lq_error['message'])
                self.notifyClient()
                return

        (num, filename) = tempfile.mkstemp(suffix=".xspf")

        with codecs.open(filename, "w",encoding='utf8') as text_file:
            text_file.write(xml)

        playlist = parsexml(xml)


        if not isinstance(playlist, dict):
            self.error('02')
            self.notifyClient()
        else:
            self.sendLqcCommand(self.lqc, 'flush')
            data = self.sendLqcCommand(self.lqc, 'loadPlaylist', filename)

            if not self._check_result(data):
                self.error('01', self.lq_error['message'])
                     
            else:
                os.remove(filename)
                self._updateEventQueue(playlist)
                event = {'job':'loadplaylist', 'uri': uri}         
                self.messenger.fireEvent('loadplaylist', event, 'player')
                self.success('00') 
        
            self.notifyClient()

    #------------------------------------------------------------------------------------------#
    def playlist_move(self, fromPos, toPos):
        """
        Playlist-Eintrag von Position fromPos nach Position toPos verschieben
        @type     fromPos: int
        @param    fromPos: die Position des Eintrags, der verschoben wird 
        @type     toPos:   int
        @param    toPos:   Zielposition                                       
        """               
        data = self.sendLqcCommand(self.lqc, 'move', str(int(fromPos)+1), str(int(toPos)+1))
            
        if not self._check_result(data):
            self.warning('01')
        else:
            self.success('00') 
        
        self.notifyClient()    
    
    #------------------------------------------------------------------------------------------#
    def playlist_pause(self):
        """
        Playlist pausieren
        """               

        data = self.sendLqcCommand(self.lqc, 'pause')
        
        if not self._check_result(data):
            self.info('01')
        else:
            self.success('00') 
        
        self.notifyClient()

    #------------------------------------------------------------------------------------------#
    def playlist_stop(self):
        """
        Playlist stoppen - der Kanal wird deaktiviert
        """
        # Kanal 0 (Playlist) deaktivieren
        self.sendLqcCommand(self.lqc, 'deactivate', '0')

        data = self.sendLqcCommand(self.lqc, 'pause')

        if not self._check_result(data):
            self.info('01')
        else:
            self.success('00')

        self.notifyClient()

    #------------------------------------------------------------------------------------------#
    def playlist_play(self, when='now'):
        """
        Playlist starten
        @type   when:   string
        @param  when:   Wenn "now" werden alle anderen Kanäle deaktiviert und geskipped                   
        """                       
        # Playlist Kanal aktivieren
        self.sendLqcCommand(self.lqc, 'activate', '0')
                
        if when == 'now':            
            # immediately skip all playing channels
            # and activate the playlist channel
            channels = self.sendLqcCommand(self.lqc, 'listChannels')
            if not isinstance(channels, list):
                self.error('03')
            elif len(channels) < 1:            
                self.warning('02')
            else:        
                for i in xrange(len(channels)):
                    status = self.sendLqcCommand(self.lqc, 'status', 'mixer', str(i + 1))
                    if "selected=true" in status:
                        status = self.sendLqcCommand(self.lqc, 'deactivate', str(i + 1))
                        status = self.sendLqcCommand(self.lqc, 'skip', 'mixer', str(i + 1))
                        self.sendLqcCommand(self.lqc, 'activate', '0')

        # send the play command
        data = self.sendLqcCommand(self.lqc, 'play')
        if not self._check_result(data):
            self.info('01')
        else:
            self.success('00')
        
        self.notifyClient()

    #------------------------------------------------------------------------------------------#
    def playlist_push(self, uri):
        """
        Eine Uri in die Playlist einfügen
        @type   uri:   str
        @param  uri:   Die Uri
        """                       
        data = self.sendLqcCommand(self.lqc, 'push', uri)
        
        if not self._check_result(data):
            self.info('01')
        else:
            self.success('00') 
        
        self.notifyClient()

    #------------------------------------------------------------------------------------------#
    def playlist_remove(self, pos):
        """
        Playlist-Eintrag löschen 
        @type     pos:     int
        @param    pos:     Position des Eintrags             
        """
        data = self.sendLqcCommand(self.lqc, 'remove', pos)

        if not self._check_result(data):
            self.info('01')
        else:
            self.success('00') 
        
        self.notifyClient()

    #------------------------------------------------------------------------------------------#
    def playlist_seek(self, duration):
        """
        Im aktuell spielenden Track auf dem der Playlist "vorspulen"
        @type     duration: int
        @param    duration: Dauer in Sekunden     
        """                
        data = self.sendLqcCommand(self.lqc, 'seek', duration)
                
        # Resultate prüfen
        if self._check_result(data):        
                self.success('00', self.lq_error['value'])
        else:    
            self.warning('01')
        
        self.notifyClient()                         

    #------------------------------------------------------------------------------------------#
    def playlist_skip(self):
        """
        Playlist skippen 
        """
        data = self.sendLqcCommand(self.lqc, 'skip')                
        
        self.success('00')
        
        self.notifyClient()                         

    #------------------------------------------------------------------------------------------#
    def recorder_start(self):
        """
        Recorder starten
        @rtype:   string
        @return:  Die Antwort des Liquidsoap-Servers               
        """                                
        message = self.sendLqcCommand(self.lqcr, 'start_record')
        if message.strip() == 'OK':
            self.success('00')
        else:    
            self.warning('01')
                
        self.notifyClient()

    #------------------------------------------------------------------------------------------#
    def recorder_stop(self):
        """
        Recorder stoppen  
        """
        message = self.sendLqcCommand(self.lqcr, 'stop_record')
                                 
        if message.strip() == 'OK':
            self.success('00')
        else:    
            self.warning('01')
                
        self.notifyClient()

    #------------------------------------------------------------------------------------------#
    def recorder_stop(self):
        """
        Recorder stoppen  
        """
        message = self.sendLqcCommand(self.lqcr, 'stop_record')
                                 
        if message.strip() == 'OK':
            self.success('00')
        else:    
            self.warning('01')
                
        self.notifyClient()

    #------------------------------------------------------------------------------------------#
    def recorder_data(self):
        """
        Status-Daten des Recorders
        Rückgabe-Beispiel: /var/audio/rec/2014-05-13/2014-05-13-22-00.wav,30 - Aufnahme von 30% der angegebenen Audiodatei     
        """   
        
        message = self.sendLqcCommand(self.lqcr, 'recorder_data')
        l = message.split(',')
        data = {}
        
        if not isinstance(l, list):
            data = {'file':'', 'recorded': ''}
            self.warning('01')
        else:
            data['file'] = l[0]
            if len(l) > 1:
                data['recorded'] = l[1]
            else:
                data['recorded'] = ''
            self.success('00', data) 
        
        self.notifyClient()

    #------------------------------------------------------------------------------------------#
    def scheduler_reload(self):
        """
        Veranlasst den Scheduler zum Reload
        """
        process =  "combas.py"
        pids = psutil.get_pid_list()
        foundProcess = False  
        for pid in pids:
            cmd = psutil.Process(pid).cmdline
            if len(cmd) > 1:
                processName = cmd[1]
            else:
                processName = psutil.Process(pid).name    
    
            if processName.find(process) > 0:
                os.kill(pid,signal.SIGUSR1)                
                foundProcess = True  
                break
        if not foundProcess:
            return False
        else:
            return True

    #------------------------------------------------------------------------------------------#
    def scheduler_data(self):
        """
        Scheduler Config ausliefern
        """
        jobs = []
        
        try:
            # Das scheduler.xml laden            
            schedulerconfig = CombaSchedulerConfig(self.sender.schedule_config)
            jobs = schedulerconfig.getJobs()
        except:
            # Das scheint kein gültiges XML zu sein            
            self.warning('01', False)
                    
        self.success('00', simplejson.dumps(jobs))
        self.notifyClient()

    #------------------------------------------------------------------------------------------#
    def scheduler_store(self, adminuser, adminpassword, json):
        """
        Scheduler Config zurückschreiben
        """   
        if not self.userdb.hasAdminRights(adminuser, adminpassword):        
            self.warning('01', False)
            self.notifyClient()
            return
        try:
            schedulerconfig = CombaSchedulerConfig(self.sender.schedule_config)
        except:
            self.warning('02', False)
            self.notifyClient()
        try:
            schedulerconfig.storeJsonToXml( base64.b64decode(json))
        except:
            self.warning('02', False)
            self.notifyClient()
        else:                    
            if self.scheduler_reload():
                self.success('00', True)
            else:
                self.warning('02', False)            
        self.notifyClient()

    #------------------------------------------------------------------------------------------#
    def setPassword(self, adminuser, adminpassword, username, password):
        """
        Ein Userpasswort setzen
        TODO: Passwörter verschlüsselt übertragen
        """
        if self.userdb.hasAdminRights(adminuser, adminpassword):
            self.userdb.setPassword(username, password)
            self.success('00', password)
        else:
            self.warning('01', False)

        self.notifyClient()
        self.sender.reload()

    #------------------------------------------------------------------------------------------#
    def addUser(self, adminuser, adminpassword, username):
        """
        Einen User hinzufügen
        TODO: Passwort verschlüsselt übertragen
        """
        if self.userdb.hasAdminRights(adminuser, adminpassword):
            password = ''.join(random.sample(string.lowercase+string.uppercase+string.digits,14))
            self.userdb.insertUser(username, password, 'user')
            self.success('00', password)
        # TODO admin rechte checken user und passwort setzen, passwort zurückgeben
        else:
            self.warning('01', False)

        self.notifyClient()
        self.sender.reload()

    #------------------------------------------------------------------------------------------#
    def delUser(self, adminuser, adminpassword, username):
        """
        Einen User löschen
        TODO: Passwort verschlüsselt übertragen
        """
        # TODO admin rechte checken user löschen
        if self.userdb.hasAdminRights(adminuser, adminpassword):
            self.userdb.delete(username)
            self.success('00', True)
        else:
            self.warning('01', False)

        self.notifyClient()
        self.sender.reload()

    #------------------------------------------------------------------------------------------#
    def getUserlist(self, adminuser, adminpassword):
        """
        Einen User löschen
        TODO: Passwort verschlüsselt übertragen
        """
        # TODO admin rechte checken user löschen
        if self.userdb.hasAdminRights(adminuser, adminpassword):
            userlist = self.userdb.getUserlist()
            self.success('00', simplejson.dumps(userlist))
        else:
            self.warning('01', False)

        self.notifyClient()


    #------------------------------------------------------------------------------------------#
    def _metadata_format(self, metadata):
        """
        Private: Vereinheitlicht die Metadaten von Playlist und anderen Kanälen und entfernt Anführungszeichen in den Feldern
        @rtype:   boolean/dict
        @return:  False/Metadaten
        """           
        mdata = {}  
        try:
            for key,val in metadata.items('root'):
                if key in self.knownfields:
                    mdata[key] = val.strip().replace('"', '')
            return mdata
        except:
            return False

    #------------------------------------------------------------------------------------------#
    def _getError(self, errornumber):
        """
        Privat: Ermittelt Fehlermeldung, Job-Name (Klassenmethode) und Fehlercode für den Job aus error/combac_error.js
        @type errornumber:  string
        @param errornumber: Die interne Fehlernummer der aufrufenden Methode  
        """        
        f = sys._getframe(2)
        
        job = f.f_code.co_name
        data = {'message':'', 'job':job, 'code':'unknown'}
        if self.errorData.has_key(job):
            errMsg = self.errorData[job][errornumber]
            errID = self.errorData[job]['id'] + str(errornumber) 
            args = {x:f.f_locals[x] if not x == 'self' else '' for x in f.f_code.co_varnames[:f.f_code.co_argcount]}
            
            for key in args.keys():            
                errMsg = errMsg.replace('::' + key + '::', str(args[key]))
            
            data['message'] = errMsg
            data['job'] = job
            data['code'] = errID
             
        return data

    #------------------------------------------------------------------------------------------#
    def success(self, errnum='00', value='', section='main'):
        """
        Erfolgsmeldung loggen
        @type errnum:    string
        @param errnum:   Errornummer der aufrufenden Funktion
        @type value:     string
        @param value:    Optionaler Wert 
        @type section:   string
        @param section:  Gültigkeitsbereich        
        """
        error = self._getError(errnum)
        self.job_result = {'message':error['message'], 'code':error['code'], 'success':'success', 'job':error['job'], 'value':value, 'section':section}
        self.messenger.send(error['message'], error['code'], 'success', error['job'], value, section)

    #------------------------------------------------------------------------------------------#
    def info(self, errnum='01', value='', section='main'):                        
        """
        Info loggen
        @type errnum:    string
        @param errnum:   Errornummer der aufrufenden Funktion
        @type value:     string
        @param value:    Optionaler Wert 
        @type section:   string
        @param section:  Gültigkeitsbereich                
        """
        error = self._getError(errnum)
        self.job_result = {'message':error['message'], 'code':error['code'], 'success':'info', 'job':error['job'], 'value':value, 'section':section}        
        self.messenger.send(error['message'], error['code'], 'info', error['job'], value, section)

    #------------------------------------------------------------------------------------------#
    def warning(self, errnum='01', value='', section='main'):
        """
        Warnung loggen
        @type errnum:    string
        @param errnum:   Errornummer der aufrufenden Funktion
        @type value:     string
        @param value:    Optionaler Wert 
        @type section:   string
        @param section:  Gültigkeitsbereich                
        """        
        error = self._getError(errnum)
        self.job_result = {'message':error['message'], 'code':error['code'], 'success':'warning', 'job':error['job'], 'value':value, 'section':section}
        self.messenger.send(error['message'], error['code'], 'warning', error['job'], value, section)

    #------------------------------------------------------------------------------------------#
    def error(self, errnum='01', value='', section='main'):
        """
        Error loggen
        @type errnum:    string
        @param errnum:   Errornummer der aufrufenden Funktion
        @type value:     string
        @param value:    Optionaler Wert 
        @type section:   string
        @param section:  Gültigkeitsbereich                
        """        
        error = self._getError(errnum)
        self.job_result = {'message':error['message'], 'code':error['code'], 'success':'error', 'job':error['job'], 'value':value, 'section':section}
        self.messenger.send(error['message'], error['code'], 'error', error['job'], value, section)

    #------------------------------------------------------------------------------------------#
    def fatal(self, errnum='01', value='', section='main'):
        """
        Fatal error loggen
        @type errnum:    string
        @param errnum:   Errornummer der aufrufenden Funktion
        @type value:     string
        @param value:    Optionaler Wert 
        @type section:   string
        @param section:  Gültigkeitsbereich                
        """
        error = self._getError(errnum)
        self.job_result = {'message':error['message'], 'code':error['code'], 'success':'fatal', 'job':error['job'], 'value':value, 'section':section}
        self.messenger.send(error['message'], error['code'], 'fatal', error['job'], value, section)    

    #------------------------------------------------------------------------------------------#
    def notifyClient(self):
        """
        Eine Nachricht als JSON-String an den Client senden
        """
        if not self.is_intern:                        
            self.message(simplejson.dumps(self.job_result))

    #------------------------------------------------------------------------------------------#
    def sendLqcCommand(self, lqs_instance, command, *args):
        """
        Ein Kommando an Liquidsoap senden
        @type  lqs_instance: object
        @param lqs_instance: Instanz eines Liquidsoap-Servers - recorder oder player
        @type  command:      string
        @param command:      Ein Funktionsname aus der Liquidsoap-Klasse
        @type args:          list
        @param args:         Parameterliste
        @rtype:              string
        @return:             Antwort der Liquidsoap-Instanz
        """
        try:
        # Verbindung herstellen
            lqs_instance.connect()
        except:
            # Verbindung gescheitert - Fehler an Client
            if command.find('record') > -1:
                self.fatal('02')
            else:
                self.fatal('01') 
                
            self.notifyClient()
            # Instanz/Thread zerstören - aufrufende Funktion wird nicht weiter abgearbeitet
            del self
        else:
            # Funktion des Liquidsoap Servers zusammenbasteln 
            func = getattr(lqs_instance, command)
            result = func(*args)             
            return result
            
    #------------------------------------------------------------------------------------------#
    def _check_result(self, result):
        """
        Fehlerbehandlung
        @type     result: string
        @param    result: Ein Json-String
        """
        self.lq_error = simplejson.loads(result)
        
        try:
            if self.lq_error['success'] == 'true':
                return True
            else:
                return False
        except:
            return False

    #------------------------------------------------------------------------------------------#
    def _updateEventQueue(self, playlist):
        """
        Playlist Eventqueue updaten
        @type playlist: dict 
        @param playlist: Playlist 
        """
        # eventuell noch bestehende Events im Queue löschen
        self.messenger.queueRemoveEvents('playtrack', 'player')
        # Für jeden Tack einen Event ankündigen
        for track in playlist['playlist']['trackList']['track']:

            if track.has_key('time') and track.has_key('start'):
                starts = str(track['start'] + 'T' + track['time'])
                event = {'job':'play', 'location': track['location'],'length': track['length'], 'date': track['start'], 'time': track['time']}
                self.messenger.queueAddEvent('playtrack', starts, event, 'player')
    