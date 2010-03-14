#!/usr/bin/env python
# -*- coding: utf-8 -*-


"""
Copyright (C) 2010 Wolfgang Rohdewald <wolfgang@rohdewald.de>

kajongg is free software you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation either version 2 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program if not, write to the Free Software
Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.
"""

import os
from PyQt4.QtCore import SIGNAL, QProcess, QString, QStringList

from PyKDE4.kdecore import KGlobal

from util import which, logWarning, m18n

        # Phonon  does not work with short files - it plays them
        # simultaneously or only parts of them. Mar 2010, KDE 4.4. True for mp3
        # and for wav. Also, mpg123 often plays distorted sounds. Kubuntu 9.10.
        # So we use wav - if we get them as mp3, first convert them to wav.
        # self.audio = Phonon.MediaObject(self)
        # self.audioOutput = Phonon.AudioOutput(Phonon.GameCategory, self)
        # Phonon.createPath(self.audio, self.audioOutput)
        # self.audio.enqueue(Phonon.MediaSource(wavName))
        # self.audio.play()

class Sound(object):
    """the sound interface. Use class variables and class methods,
    thusly ensuring no two instances try to speak"""
    enabled = False
    __queue = []
    __playing = None
    __process = None
    __converter = None
    __hasaplay = None
    __hasmpg123 = None

    @staticmethod
    def speak(what):
        """this is what the user of this module will call."""
        if not Sound.enabled:
            return
        if Sound.__hasaplay is None:
            if not which('aplay'):
                Sound.enabled = False
                # checks again at next reenable
                logWarning(m18n('No sound because the program aplay is missing'))
                return
            Sound.__hasaplay = True
        if Sound.__playing:
            Sound.__queue.append(what)
        else:
            Sound.__play(what)

    @staticmethod
    def __play(what):
        """if wavName exists, play it. Else try to convert it from mp3 and then play it"""
        wavName = what + '.wav'
        mp3Name = what + '.mp3'
        if os.path.exists(wavName):
            Sound.__playing = wavName
            Sound.__startProcess()
            return
        if not os.path.exists(mp3Name):
            return
        if Sound.__hasmpg123 is None:
            Sound.__hasmpg123 = which('mpg123') or False
            if not Sound.__hasmpg123:
                logWarning(m18n('No sound because the program mpg123 is missing'))
                return
        if not Sound.__hasmpg123:
            return
        Sound.__playing = wavName
        Sound.__converter = QProcess()
        Sound.__converter.start(QString('mpg123'), QStringList(['-w', Sound.__playing, mp3Name]))
        Sound.__converter.connect(Sound.__converter, SIGNAL('finished(int,QProcess::ExitStatus)'), Sound.__converted)

    @staticmethod
    def __startProcess():
        """start the playing process"""
        Sound.__process = QProcess()
        Sound.__process.connect(Sound.__process, SIGNAL('finished(int,QProcess::ExitStatus)'), Sound.__finished)
        Sound.__process.start(QString('aplay'), QStringList(Sound.__playing))

    @staticmethod
    def __converted(code, status):
        """the mp3 has now been converted to a wav"""
        if os.path.exists(Sound.__playing):
            Sound.__startProcess()
        else:
            Sound.__finished()

    @staticmethod
    def __finished(code=None, status=None):
        """finished playing the sound"""
        Sound.__playing = None
        if Sound.__queue:
            what = Sound.__queue[0]
            Sound.__queue = Sound.__queue[1:]
            Sound.__play(what)

class Voice(object):
    """this administers voice data"""

    def __init__(self, player):
        self.player = player

    def textName(self, text):
        """build the name of the wanted .wav file"""
        fileName = os.path.join('voices', 'local', self.player.name, text.lower().replace(' ', ''))
        fileName = str(KGlobal.dirs().locateLocal("appdata", fileName))
        return fileName

    def speak(self, text):
        Sound.speak(self.textName(text))

