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

import os, tarfile
from hashlib import md5

from PyQt4.QtCore import SIGNAL, QProcess, QString, QStringList

import common
from util import which, logWarning, m18n, appdataDir


        # Phonon  does not work with short files - it plays them
        # simultaneously or only parts of them. Mar 2010, KDE 4.4. True for mp3
        # and for wav. Also, mpg123 often plays distorted sounds. Kubuntu 9.10.
        # So we use ogg123 and ogg sound files.
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
    __process = None
    __hasogg123 = None

    @staticmethod
    def speak(what):
        """this is what the user of this module will call."""
        print 'speak:', what
        if not Sound.enabled:
            print 'no sound enabled'
            return
        if Sound.__hasogg123 is None:
            if not which('ogg123'):
                print 'no ogg123'
                Sound.enabled = False
                # checks again at next reenable
                logWarning(m18n('No voices will be heard because the program ogg123 is missing'))
                return
            Sound.__hasogg123 = True
        if Sound.__process:
            Sound.__queue.append(what)
        else:
            Sound.__play(what)

    @staticmethod
    def __play(what):
        """play what if it exists"""
        if os.path.exists(what):
            Sound.__process = QProcess()
            Sound.__process.connect(Sound.__process, SIGNAL('finished(int,QProcess::ExitStatus)'), Sound.__finished)
            args = QStringList('-q')
            args.append(what)
            Sound.__process.start(QString('ogg123'), args)

    @staticmethod
    def __finished(dummyCode=None, dummyStatus=None):
        """finished playing the sound"""
        Sound.__process = None
        if Sound.__queue:
            what = Sound.__queue[0]
            Sound.__queue = Sound.__queue[1:]
            Sound.__play(what)

class Voice(object):
    """this administers voice sounds"""

    voicesDirectory = None

    def __init__(self, voiceDirectory):
        """give this name a voice"""
        self.voiceDirectory = voiceDirectory
        if not Voice.voicesDirectory:
            Voice.voicesDirectory = os.path.join(appdataDir(), 'voices')

    def __str__(self):
        return self.voiceDirectory

    def __repr__(self):
        return "<Voice: %s>" % self

    def __extractArchive(self):
        """if we have an unextracted archive, extract it"""
        if self.voiceDirectory.startswith('MD5'):
            archiveDirectory = self.archiveDirectory()
            archiveName = self.archiveName()
            if not os.path.exists(archiveDirectory) and os.path.exists(archiveName):
                tarFile = tarfile.open(archiveName)
                os.mkdir(archiveDirectory)
                tarFile.extractall(path=archiveDirectory)

    def localTextName(self, text):
        """build the name of the wanted sound  file"""
        return os.path.join(self.archiveDirectory(), text.lower().replace(' ', '') + '.ogg')

    def speak(self, text):
        """text must be a sound filename without extension"""
        if not self.voiceDirectory.startswith('MD5') \
            and not self.voiceDirectory.startswith('ROBOT'):
            # we have not been able to convert the player name into a voice archive
            return
        self.__extractArchive()
        Sound.speak(self.localTextName(text))

    def buildArchive(self):
        """returns None or the name of an archive with this voice. That
        name contains the md5sum of the tar content. The tar file is
        recreated if an ogg has changed. The ogg content is checked,
        not the timestamp."""
        if self.voiceDirectory.startswith('MD5'):
            return
        uploadVoice = common.PREF.uploadVoice if common.PREF else False
        # common.PREF is not available on the server
        if self.voiceDirectory.startswith('ROBOT') or not uploadVoice:
            # the voice of robot players is never transferred to others
            return
        sourceDir = self.archiveDirectory()
        if not os.path.exists(sourceDir):
            return
        oggFiles = sorted(x for x in os.listdir(sourceDir) if x.endswith('.ogg'))
        if not oggFiles:
            return
        md5sum = md5()
        for oggFile in oggFiles:
            md5sum.update(open(os.path.join(sourceDir, oggFile)).read())
        # the md5 stamp goes into the old archive directory 'username'
        newDir = 'MD5' + md5sum .hexdigest()
        md5FileName = os.path.join(self.archiveDirectory(), newDir)
        self.voiceDirectory = newDir
        if not os.path.exists(md5FileName):
            # if the checksum over all voice files has changed:
            # remove old md5 stamps and old archives (there should be just one)
            for name in (x for x in os.listdir(sourceDir) if x.startswith('MD5')):
                os.remove(os.path.join(sourceDir, name))
                os.remove(self.archiveName(name))
            open(md5FileName, 'w').write('')
            if not os.path.exists(self.archiveName()):
                tarFile = tarfile.open(self.archiveName(), mode='w:bz2')
                for oggFile in oggFiles:
                    tarFile.add(os.path.join(sourceDir, oggFile), arcname=oggFile)
                tarFile.close()
            os.symlink(sourceDir, self.archiveDirectory())

    def archiveDirectory(self, name=None):
        """the full path of the archive directory"""
        if name is None:
            name = self.voiceDirectory
        return os.path.join(Voice.voicesDirectory, name)

    def archiveName(self, name=None):
        """ the full path of the archive file"""
        directory = self.archiveDirectory(name)
        if directory:
            return directory + '.tbz'

    def hasData(self):
        """if we have the voice tar file, return its filename"""
        self.buildArchive()
        if self.voiceDirectory.startswith('MD5'):
            if os.path.exists(self.archiveName()):
                return self.archiveName()

    @apply
    def archiveContent():
        """the content of the tarfile"""
        def fget(self):
            dataFile = self.hasData()
            if dataFile:
                return open(dataFile).read()
        def fset(self, archiveContent):
            if not archiveContent:
                return
            if not os.path.exists(Voice.voicesDirectory):
                os.makedirs(Voice.voicesDirectory)
            open(self.archiveName(), 'w').write(archiveContent)
        return property(**locals())
