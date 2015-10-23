__author__ = 'michel'
# -*- coding: utf-8 -*-
import datetime
from datetime import timedelta
from comba_lib.database.broadcasts import *
"""
Model - handles events
"""

class ModelBroadcastEventOverrides(object):

    #------------------------------------------------------------------------------------------#
    @staticmethod
    def upcoming(datefrom, freq):
        dateto = (datefrom + timedelta(seconds=freq))
        datefromquery = Q(start__gt=datefrom)
        datetoquery = Q(start__lte=dateto)
        tracks = BroadcastEventOverride.objects(datefromquery & datetoquery)
        return tracks


