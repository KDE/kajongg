# -*- coding: utf-8 -*-

"""
Copyright (C) 2010-2012 Wolfgang Rohdewald <wolfgang@rohdewald.de>

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
Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301, USA.
"""

import os, tarfile, subprocess, datetime
from hashlib import md5  # pylint: disable=E0611
if os.name == 'nt':
    import winsound # pylint: disable=F0401

import common
from util import which, logWarning, m18n, appdataDir, logDebug
from common import Debug
from meld import Meld

        # Phonon does not work with short files - it plays them
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
    __hasogg = None
    playProcesses = []


    @staticmethod
    def findOgg():
        """sets __hasogg to True or False"""
        if Sound.__hasogg is None:
            oggName = r'c:\vorbis\oggdec.exe' if os.name == 'nt' else 'ogg123'
            if not which(oggName):
                Sound.enabled = False
                # checks again at next reenable
                logWarning(m18n('No voices will be heard because the program %1 is missing', oggName))
                return
            Sound.__hasogg = True
        return Sound.__hasogg

    @staticmethod
    def speak(what):
        """this is what the user of this module will call."""
        if not Sound.enabled:
            return
        game = common.InternalParameters.field.game
        if os.path.exists(what):
            if Sound.findOgg():
                if os.name == 'nt':
                    name, ext = os.path.splitext(what)
                    assert ext == '.ogg'
                    wavName = name + '.wav'
                    if not os.path.exists(wavName):
                        # TODO: convert all ogg in one run
                        args = [r'c:\vorbis\oggdec', '--quiet', what]
                        process = subprocess.Popen(args)
                        os.waitpid(process.pid, 0)
                    winsound.PlaySound(wavName, winsound.SND_FILENAME)
                else:
                    for process in Sound.playProcesses:
                        diff = datetime.datetime.now() - process.startTime
                        if diff.seconds > 5:
                            process.kill()
                            if common.Debug.sound:
                                game.debug('5 seconds passed. Killing %s' % process.name)
                    Sound.playProcesses = [x for x in Sound.playProcesses if x.returncode is None]
                    args = ['ogg123', '-q', what]
                    if common.Debug.sound:
                        game.debug(' '.join(args))
                    process = subprocess.Popen(args)
                    process.startTime = datetime.datetime.now()
                    process.name = what
                    Sound.playProcesses.append(process)
        elif False:
            text = os.path.basename(what)
            text = os.path.splitext(text)[0]
            # TODO: translate all texts
            # we need package jovie and mbrola voices
            # KSpeech setLanguage de
            # KSpeech.showManagerDialog lets me define voices but
            # how do I use them? it is always the same voice,
            # setDefaultTalker "namefrommanager" does not change anything
            # although defaultTalker returns what we just set even if no talker
            # with that name exists
            # getTalkerCodes returns nothing
            # this all feels immature
            if len(text) == 2 and text[0] in 'sdbcw':
                text = Meld.tileName(text)
            args = ['qdbus', 'org.kde.jovie',
                '/KSpeech', 'say', text, '1']
            subprocess.Popen(args)

class Voice(object):
    """this administers voice sounds"""

    voicesDirectory = None

    def __init__(self, voiceDirectory):
        """give this name a voice"""
        self.voiceDirectory = voiceDirectory
        if not Voice.voicesDirectory:
            Voice.voicesDirectory = os.path.join(appdataDir(), 'voices')
        if Debug.sound:
            logDebug('new Voice(%s)' % voiceDirectory)

    def __str__(self):
        return self.voiceDirectory

    def __repr__(self):
        return "<Voice: %s>" % self

    @staticmethod
    def availableVoices():
        """a list of all voice directories"""
        if not Voice.voicesDirectory:
            Voice.voicesDirectory = os.path.join(appdataDir(), 'voices')
        directories = os.listdir(Voice.voicesDirectory)
        directories = [x for x in directories if os.path.exists(os.path.join(Voice.voicesDirectory, x, 's1.ogg'))]
        return directories

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
        """build the name of the wanted sound file"""
        return os.path.join(self.archiveDirectory(), text.lower().replace(' ', '') + '.ogg')

    def speak(self, text):
        """text must be a sound filename without extension"""
        fileName = self.localTextName(text)
        if not os.path.exists(fileName):
            if not self.voiceDirectory.startswith('MD5') \
                and not self.voiceDirectory.startswith('ROBOT'):
                # we have not been able to convert the player name into a voice archive
                return
            self.__extractArchive()
        Sound.speak(fileName)

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
        else:
            # we have a directory containing the correct fingerprint.
            # now make sure the directory MD5... exists. If not,
            # make it a symlink pointing to the source directory.
            md5Directory = os.path.join(Voice.voicesDirectory, newDir)
            if not os.path.exists(md5Directory):
                os.symlink(os.path.split(sourceDir)[1], md5Directory)


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
