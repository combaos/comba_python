#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# combaarchive.py
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

import os
import os.path
import redis
import sys
import simplejson
import subprocess
import logging
from comba_lib.base.combabase import CombaBase
from comba_lib.utils.audio import CombaAudiotools
from comba_lib.database.broadcasts import *

class CombaArchive(CombaBase):

#------------------------------------------------------------------------------------------#
    def __init__(self):
        pass

#------------------------------------------------------------------------------------------#
    def combine_audiofiles(self,files, subfolder, filename):
        """
        Combines a list of wav files to a single mp3  using sox
        @type     files: list
        @param    files: list of wav files to combine
        @type subfolder: string
        @param subfolder: folder where the files reside
        @type filename: string
        @param filename: the filename for the combined file
        @return:
        """
        if not len(files):
            return

        cur_folder = str(self.archivebase + subfolder + '/').replace('//', '/')

        if not os.path.exists(cur_folder):
            os.mkdir(cur_folder, 0755)
            os.chmod(cur_folder, 0755)

        # Name der Audiodatei, die angelegt werden muss
        out_file = cur_folder +   filename
        command = ["nice","-n","14","sox"]
        for file in files:
            if os.path.exists(file):
                command.append(file)

        command.append("-C")
        command.append("224.01")
        command.append(out_file)
        p = subprocess.Popen(command)
        p.wait()
        os.chmod(out_file, 0644)

    def start(self):
        """
        Watch redis store. If the last track of a recorded programme is dumped,
        combine archive the tracks to a single mp3
        @return:
        """
        self.loadConfig()

        print "Archive is running"
        logging.debug("Archive is running")
        audiotools = CombaAudiotools()
        r = redis.Redis("localhost")
        ps_obj=r.pubsub()
        ps_obj.psubscribe('recordPublish')
        for item in ps_obj.listen():
            logging.debug("listener found item")
            logging.debug(item['data'])
            if type(item['data']) == type(""):
                try:
                    data = simplejson.loads(item['data'])
                except:
                    logging.debug("could not load item")
                    continue

                if not data.has_key('value') or not data.has_key('eventname'):
                    logging.debug("no value, no eventname")
                    continue

                if not data['eventname'] == 'dumpend':
                    logging.debug("eventname ist nicht dumpend")
                    continue

                curtrack = BroadcastEventTrack.objects(location='file://' + data["value"]).first()

                if not curtrack:
                    logging.debug("track nicht gefunden")
                    continue
                logging.debug("track " + str(data["value"]) + ' gefunden')
                if curtrack.isLast():
                    logging.debug("track ist der letzte")

                    tracks = BroadcastEventTrack.objects(broadcast_event=curtrack.broadcast_event)
                    event = curtrack.broadcast_event

                    files = []
                    for track in tracks:
                        files.append(track.location.replace('file://', ''))

                    subfolder = event.start.strftime('%Y-%m-%d')
                    filename = event.start.strftime('%Y-%m-%d-%H-%M-%S.mp3')

                    event.modified = datetime.datetime.now()
                    event.location = 'file://' + str(self.archivebase + subfolder + '/' + filename).replace('//','/')
                    event.state = 'archived'
                    event.modified_by = 'archiver'
                    event.save()
                    cur_folder = str(self.archivebase + subfolder + '/').replace('//', '/')
                    audiotools.combine_audiofiles(files, cur_folder, filename, clean=False, params=["-C", "224.01"])



