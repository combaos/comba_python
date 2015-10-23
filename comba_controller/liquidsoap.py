#!/usr/bin/python
# -*- coding: utf-8 -*-
import os
import sys
import socket
import time
import ConfigParser
import StringIO
import logging
import urllib

class LQConnectionError(Exception):
     def __init__(self, value):
         self.value = value
     def __str__(self):
         return repr(self.value)


""" LiquidsoapClient Class 
    Kommandos an den Liquidsoap Soundserver oder Recorder senden
    Repräsentiert alle Kommandos, die Soundserver oder Recorder kennen
"""
class LiquidsoapClient():
    
    def __init__(self, socketPath):
        """
        Constructor
        @type    socketPath: string
        @param   socketPath: Der Pfad zum Socket des Liquidsoap-Scripts         
        """        
        self.socketpath = socketPath
        self.connected  = False
        self.can_connect  = True
        self.message    = ''
        if sys.version_info <= (3, 2):    
            self.metareader =  ConfigParser.ConfigParser({'strict':False,'interpolation':None})
        else:     
            self.metareader = ConfigParser.ConfigParser()

    #------------------------------------------------------------------------------------------#
    def connect(self):
        """
        Verbindung herstellen
        """
        try:
            self.client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)            
        except socket.error as msg:
            self.client = None
            self.connected = False
            raise LQConnectionError('Could not Connect')
            return False
        self.client.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)            
        
        try:    
            self.client.connect(self.socketpath)
        except socket.error:
            logging.error('Could not connect to ' + self.socketpath)
            self.connected = False
            raise LQConnectionError('Could not Connect')
            return False
        else:
            self.can_connect = True
            self.connected = True
            return True                

    #------------------------------------------------------------------------------------------#
    def isConnected(self):
        return self.connected

    #------------------------------------------------------------------------------------------#
    def write(self,data):
        """
        Auf den Socket schreiben
        @type    data: string
        @param   data: Der String der gesendet wird
        """
        if self.connected:
            self.client.sendall(data)        

    #------------------------------------------------------------------------------------------#
    def read_all(self, timeout=2):
        """
        Vom Socket lesen, bis dieser "END" sendet
        @type    timeout: int
        @param   timeout: Ein optionales Timeout
        @rtype:  string
        @return: Die Antwort des Liquidsoap-Servers           
        """
        #make socket non blocking
        #self.client.setblocking(0)     
        total_data='';
        data='';     
        begin=time.time()
        while 1:
            #if you got some data, then break after timeout
            if data and time.time()-begin > timeout:
                break
         
            #if you got no data at all, wait a little longer, twice the timeout
            elif time.time()-begin > timeout*2:
                break
            elif data.find('END\r') > 0:
                break
            #recv something
            try:
                data = data + self.client.recv(8192)
                if data:

                    #change the beginning time for measurement
                    begin=time.time()
                else:
                    #sleep for sometime to indicate a gap
                    time.sleep(0.1)
            except:
                pass
                        
        return data

    #------------------------------------------------------------------------------------------#
    def read(self):        
        """
        Vom Socket lesen und anschließend quit senden, um den Server zu veranlassen, die Verbindung schließen
        @rtype:  string
        @return: Die Antwort des Liquidsoap-Servers           
        """
        if self.connected:
            
            ret = self.read_all()
            ret = ret.splitlines()
            try:
                ret.pop()
            except:
                ret = ''
                
            self.message = "\n".join(ret)
            #self.client.sendall('quit\n')
            return self.message

    #------------------------------------------------------------------------------------------#
    def close(self):
        """
        Quit senden und Verbindung schließen
        """
        if self.connected:
            self.client.sendall("quit\r")
            self.client.close()
            self.connected = False

    #------------------------------------------------------------------------------------------#
    def command(self, command, namespace="playlist", param=""):
        """
        Kommando an Liquidosap senden
        @type    command:   string
        @param   command:   Kommando
        @type    namespace: string
        @param   namespace: Namespace/Kanal der angesprochen wird
        @type    param:     mixed            
        @param   param:     ein optionaler Parameter            
        @rtype:  string
        @return: Die Antwort des Liquidsoap-Servers           
        """        
        param = (param.strip()  if param.strip() == "" else " " + urllib.unquote(param.strip()))

        if self.connected:      
            # print namespace + '.' + command + param + "\n"           
            self.client.sendall(str(namespace) + '.' + str(command) + str(param) + "\n")
            self.read()        
            self.client.close()
            return self.message
        else: 
            return False

    #------------------------------------------------------------------------------------------#
    def simplecommand(self, command):
        """
        Parameterloses Kommando ohne Namespace senden
        @type    command:   string
        @param   command:   Kommando
        @rtype:  string
        @return: Die Antwort des Liquidsoap-Servers           
        """                
        
        if self.connected:    
            self.client.sendall(str(command) + "\n")
            self.read()        
            #self.client.close()
            return self.message

    #------------------------------------------------------------------------------------------#
    def getMetadata(self, rid):
        """
        Parameterloses Kommando ohne Namespace senden
        @type    rid:   string/int
        @param   rid:   Die ID eines Requests
        @rtype:  dict
        @return: Die Metadaten als dict           
        """                        
        meta = self.command('metadata '+ str(rid), 'request')
         
        meta = '[root]\n' + meta
        if sys.version_info <= (3, 2):    
            meta = StringIO.StringIO(meta)            
            try:
                self.metareader.readfp(meta)
            except ConfigParser.ParsingError:
                return False      
        else:
            try:
                self.metareader.read_string(meta)
            except ConfigParser.ParsingError:
                return False                              
        return self.metareader

    #------------------------------------------------------------------------------------------#
    def status(self, namespace="mixer", pos=""):
        """
        Status einer Liquidsoap-Source abfragen
        @type    namespace: string
        @param   namespace: Namespace der Source
        @type    pos:       string
        @param   pos:       Die Position - optional - vom Mixer benötigt        
        @rtype:  string
        @return: Die Antwort des Liquidsoap-Servers       
        """                                
        self.command('status',namespace, str(pos))
        return self.message
    
    #------------------------------------------------------------------------------------------#
    def skip(self, namespace="playlist", pos=""):
        """
        Source skippen
        @type    namespace: string
        @param   namespace: Namespace der Source
        @type    pos:       string
        @param   pos:       Die Position - optional - Position des Channels vom Mixer benötigt        
        @rtype:  string
        @return: Die Antwort des Liquidsoap-Servers       
        """                                        
        self.command('skip',namespace, pos)
        return self.message

    #------------------------------------------------------------------------------------------#
    def activate(self, pos, namespace="mixer"):
        """
        Kanal/Source aktivieren
        @type    pos:       string
        @param   pos:       Die Position
        @type    namespace: string
        @param   namespace: Namespace der Source
        @rtype:  string
        @return: Die Antwort des Liquidsoap-Servers       
        """   
        self.command('select',namespace, str(pos) + ' true')
        return self.message

    #------------------------------------------------------------------------------------------#
    def deactivate(self, pos, namespace="mixer"):
        """
        Kanal/Source deaktivieren
        @type    pos:       string
        @param   pos:       Die Position
        @type    namespace: string
        @param   namespace: Namespace der Source
        @rtype:  string
        @return: Die Antwort des Liquidsoap-Servers       
        """
        self.command('select',namespace, str(pos) + ' false')
        return self.message

    #------------------------------------------------------------------------------------------#
    def remove(self, pos, namespace="playlist"):
        """
        Track  aus der secondary_queue oder der Playlist entfernen         
        @type    pos:       string
        @param   pos:       Die Position
        @type    namespace: string
        @param   namespace: Namespace der Source        
        @rtype:  string
        @return: Die Antwort des Liquidsoap-Servers       
        """        
        self.command('remove',namespace, str(pos))
        return self.message

    #------------------------------------------------------------------------------------------#
    def insert(self, uri, pos='0', namespace="playlist"):
        """
        Track  einfügen         
        @type    uri:       string
        @param   uri:       Uri einer Audiodatei        
        @type    pos:       string
        @param   pos:       Die Position                
        @type    namespace: string
        @param   namespace: Namespace der Source
        @rtype:  string
        @return: Die Antwort des Liquidsoap-Servers       
        """        
        self.command('insert', namespace, str(pos) + ' ' + uri)
        return self.message

    #------------------------------------------------------------------------------------------#
    def move(self, fromPos, toPos, namespace="playlist"):
        """
        Track  von Position fromPos nach Position toPos verschieben          
        @type    fromPos:   string/int
        @param   fromPos:   Position des zu verschiebenden Tracks        
        @type    toPos:     string
        @param   toPos:     Die Position zu der verschoben werden soll                
        @type    namespace: string
        @param   namespace: Namespace der Source
        @rtype:  string
        @return: Die Antwort des Liquidsoap-Servers       
        """        
        self.command('move', namespace, str(fromPos) + ' ' + str(toPos))        
        return self.message

    #------------------------------------------------------------------------------------------#
    def play(self, namespace="playlist"):
        """
        Source abspielen - funktioniert nur bei Playlist          
        @type    namespace: string
        @param   namespace: Namespace der Source
        @rtype:  string
        @return: Die Antwort des Liquidsoap-Servers       
        """                  
        self.command('play',namespace)
        return self.message

    #------------------------------------------------------------------------------------------#
    def pause(self, namespace="playlist"):
        """
        Source pausieren/stoppen - funktioniert nur bei Playlist          
        @type    namespace: string
        @param   namespace: Namespace der Source
        @rtype:  string
        @return: Die Antwort des Liquidsoap-Servers       
        """             
        self.command('pause',namespace)
        return self.message

    #------------------------------------------------------------------------------------------#
    def flush(self, namespace="playlist"):
        """
        Playlist leeren          
        @type    namespace: string
        @param   namespace: Namespace der Source
        @rtype:  string
        @return: Die Antwort des Liquidsoap-Servers       
        """                
        self.command('flush',namespace)
        return self.message

    #------------------------------------------------------------------------------------------#
    def push(self, uri, namespace="playlist"):
        """
        Track einfügen und abspielen (wenn source aktiv ist)           
        @type    uri:       string
        @param   uri:       Uri eines Audios                 
        @type    namespace: string
        @param   namespace: Namespace der Source
        @rtype:  string
        @return: Die Antwort des Liquidsoap-Servers       
        """
        self.command('push',namespace, str(uri))
        return self.message

    #------------------------------------------------------------------------------------------#
    def playlistData(self):
        """
        Metadaten der Playlist ausgeben           
        @rtype:  string
        @return: Ein Json-String       
        """        
        self.command('data','playlist')
        return self.message
    
    #------------------------------------------------------------------------------------------#
    def seek(self, duration, namespace="playlist"):
        """
        Aktuell laufenen Track des Kanals vorspulen
        @type    duration:  string/int
        @param   duration:  Dauer in Sekunden                 
        @type    namespace: string
        @param   namespace: Namespace der Source                   
        @rtype:  string
        @return: Die Antwort des Liquidsoap-Servers      
        """                
        self.command('seek',namespace, str(duration))
        return self.message
    
    #------------------------------------------------------------------------------------------#
    def get_queue(self,namespace="ch1",queue='queue'):
        """
        Queue eines Kanals ausgeben
        @type    namespace: string
        @param   namespace: Namespace der Source                   
        @type    queue:     string
        @param   queue:    Name des queues (queue, primary_queue, secondary_queue)                 
        @rtype:  string
        @return: Die Antwort des Liquidsoap-Servers      
        """                                
        self.command(queue,namespace)
        return self.message

    #------------------------------------------------------------------------------------------#
    def loadPlaylist(self, uri, params="", namespace="playlist"):
        """
        Playlist laden         
        @type    uri:       string
        @param   uri:       Uri einer Playlist im XSPF-Format        
        @type    params:    string
        @param   params:    obsolete                
        @type    namespace: string
        @param   namespace: Namespace der Source - hier nur playlist
        @rtype:  string
        @return: Die Antwort des Liquidsoap-Servers       
        """                
        self.command('load',namespace, uri + params)
        return self.message    

    #------------------------------------------------------------------------------------------#
    def listChannels(self, excludeSpecial=True, namespace="mixer"):
        """
        Eine Liste der Kanäle erhalten    
        @type    excludeSpecial: boolean
        @param   excludeSpecial: Playlistkanal ausschließen, wenn True        
        @type    namespace: string
        @param   namespace: Namespace der Source - hier nur mixer
        @rtype:  list
        @return: Die Antwort des Liquidsoap-Servers als Liste       
        """            
        # "Inputs" vom Mixer holen             
        self.command('inputs', namespace)
        # in Liste umwandeln
        inputs = self.message.strip().split(' ')
        # ggf Playlist-Kanal entfernen
        if excludeSpecial:
            tmp = inputs.pop(0)
        return inputs    
              
    #------------------------------------------------------------------------------------------#
    def currentTrack(self, namespace="request"):
        """
        Das oder die ID(s) der gerade abgespielten requests erhalten      
        @type    namespace: string
        @param   namespace: Namespace der Source
        @rtype:  string
        @return: Die Antwort des Liquidsoap-Servers (als String)       
        """                    
        self.command('on_air',namespace)
        return self.message

    #------------------------------------------------------------------------------------------#
    def volume(self, pos, volume, namespace="mixer"):
        """
        Lautstärke eines Kanals setzen
        @type    pos:       int/string
        @param   pos:       Die Position/ Nummer des Kanals (playlist=0)
        @type    volume:    int/string
        @param   volume:    Zahl von 1 -100        
        @type    namespace: string
        @param   namespace: Namespace der Source (immer mixer)
        @rtype:  string
        @return: Die Antwort des Liquidsoap-Servers       
        """        
        self.command('volume',namespace, str(pos) + ' ' + str(volume))
        return self.message        

    #------------------------------------------------------------------------------------------#
    def playlist_remaining(self):
        """
        Wie lange läuft der aktuelle Track der Playlist noch
        @rtype:  string
        @return: Die Antwort des Liquidsoap-Servers 
        """
        self.command('remaining', 'playlist')
        return self.message

    #------------------------------------------------------------------------------------------#
    def recorder_setfilename(self, filename):
        """
        Dateinamen für Aufnahme (Vorproduktion) definieren
        @type    filename: string
        @param   filename: Dateiname - Angabe ohne Verzeichnis und mit Extension 
        @rtype:  string
        @return: Die Antwort des Liquidsoap-Servers 
        """
        self.command('setfilename', 'record', str(filename))
        return self.message        
            
    #------------------------------------------------------------------------------------------#
    def stop_record(self):
        """
        Recorder stoppen
        @rtype:  string
        @return: Die Antwort des Liquidsoap-Servers       
        """        
        message = self.command('stop', 'record')
        return self.message        

    #------------------------------------------------------------------------------------------#
    def start_record(self):
        """
        Recorder starten
        @rtype:  string
        @return: Die Antwort des Liquidsoap-Servers       
        """        
        self.command('start', 'record')
        return self.message        

    #------------------------------------------------------------------------------------------#
    def recorder_data(self):
        """
        Daten des recorders erhalten
        @rtype:  string
        @return: Die Antwort des Liquidsoap-Servers       
        """        
        self.command('curfile','record')        
        return self.message        

    #------------------------------------------------------------------------------------------#
    def getVersion(self):
        """
        Liquidsoap Version ausgeben
        @rtype:  string
        @return: Die Antwort des Liquidsoap-Servers       
        """                

        if self.connected: 
            self.client.sendall('version\n')
            self.read()        
            #self.client.close()
            return self.message    
