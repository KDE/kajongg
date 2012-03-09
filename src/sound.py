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

import os, tarfile, subprocess, datetime, cStringIO
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
    """this administers voice sounds.

    When transporting voices between players, a compressed tarfile
    is generated at source and transferred to destination. At
    destination, no tarfile is written, only the content. It makes
    only sense to cache the voice in a tarfile at source."""

    voicesDirectory = None

    def __init__(self, voiceDirectory):
        """give this name a voice"""
        self.voiceDirectory = voiceDirectory
        self.__builtArchive = False
        self.__md5sum = None
        if not Voice.voicesDirectory:
            Voice.voicesDirectory = os.path.join(appdataDir(), 'voices')

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

    @staticmethod
    def locate(name):
        """returns Voice or None if no voice matches"""
        if name in Voice.availableVoices():
            if Debug.sound:
                logDebug('locate found %s' % name)
            return Voice(name)

    def localTextName(self, text):
        """build the name of the wanted sound file"""
        return os.path.join(self.voicesDirectory, self.voiceDirectory, text.lower().replace(' ', '') + '.ogg')

    def speak(self, text):
        """text must be a sound filename without extension"""
        fileName = self.localTextName(text)
        if not os.path.exists(fileName):
            if Debug.sound:
                logDebug('Voice.speak: fileName %s not found' % fileName)
        Sound.speak(fileName)

    def oggFiles(self):
        """a list of all found ogg files"""
        directory = os.path.join(Voice.voicesDirectory, self.voiceDirectory)
        if os.path.exists(directory):
            return sorted(x for x in os.listdir(directory) if x.endswith('.ogg'))

    def __buildArchive(self):
        """write the archive file and set self.__md5sum"""
        if self.__md5sum:
            return
        directory = os.path.join(Voice.voicesDirectory, self.voiceDirectory)
        md5FileName = os.path.join(directory, 'md5sum')
        ogg = self.oggFiles()
        if not ogg:
            if os.path.exists(self.archiveName()):
                os.remove(self.archiveName())
            if os.path.exists(md5FileName):
                os.remove(md5FileName)
            self.__md5sum = None
            return
        md5sum = md5()
        for oggFile in ogg:
            md5sum.update(open(os.path.join(directory, oggFile)).read())
        # the md5 stamp goes into the old archive directory 'username'
        self.__md5sum = md5sum.hexdigest()
        if os.path.exists(md5FileName):
            existingMd5sum = open(md5FileName, 'r').readlines()[0]
        else:
            existingMd5sum = None
        if self.__md5sum != existingMd5sum:
            if Debug.sound:
                if not os.path.exists(md5FileName):
                    logDebug('creating new %s' % md5FileName)
                else:
                    logDebug('md5sum %s changed, rewriting %s with %s' % (existingMd5sum, md5FileName, self.__md5sum))
            open(md5FileName, 'w').write('%s\n' % self.__md5sum)
            tarFile = tarfile.open(self.archiveName(), mode='w:bz2')
            for oggFile in ogg:
                tarFile.add(os.path.join(directory, oggFile), arcname=oggFile)
            tarFile.close()

    def archiveName(self):
        """ the full path of the archive file"""
        return os.path.join(Voice.voicesDirectory, self.voiceDirectory, 'content.tbz')

    @apply
    def md5sum():
        """the name of the tarfile"""
        def fget(self):
            # pylint: disable=W0212
            self.__buildArchive()
            return self.__md5sum
        return property(**locals())

    @apply
    def archiveContent():
        """the content of the tarfile"""
        def fget(self):
            # pylint: disable=W0212
            self.__buildArchive()
            if self.__md5sum:
                return open(self.archiveName()).read()
        def fset(self, archiveContent):
            if not archiveContent:
                return
            directory = os.path.join(Voice.voicesDirectory, self.voiceDirectory)
            if not os.path.exists(directory):
                os.makedirs(directory)
            filelike = cStringIO.StringIO(archiveContent)
            tarFile = tarfile.open(mode='r|bz2', fileobj=filelike)
            tarFile.extractall(path=directory)
            if Debug.sound:
                logDebug('extracted archive into %s' % directory)
            tarFile.close()
            filelike.close()

        return property(**locals())
