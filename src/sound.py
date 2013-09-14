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
from hashlib import md5
if os.name == 'nt':
    import winsound # pylint: disable=F0401

from common import Debug, Internal
from util import which, logWarning, m18n, cacheDir, logDebug, \
    removeIfExists, logException, uniqueList

if Internal.haveKDE:
    from kde import KGlobal, KConfigGroup

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
    lastCleaned = None

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
    def cleanProcesses():
        """terminate ogg123 children"""
        now = datetime.datetime.now()
        if Sound.lastCleaned and (now - Sound.lastCleaned).seconds < 2:
            return
        Sound.lastCleaned = now
        remaining = []
        for process in Sound.playProcesses:
            if process.poll() is not None:
                # ogg123 self-finished
                continue
            diff = now - process.startTime
            if diff.seconds > 10:
                try:
                    process.kill()
                except OSError:
                    pass
                try:
                    os.waitpid(process.pid, 0)
                except OSError:
                    pass
                if Debug.sound:
                    game = Internal.field.game
                    game.debug('10 seconds passed. Killing %s' % process.name)
            else:
                remaining.append(process)
        Sound.playProcesses = remaining

    @staticmethod
    def speak(what):
        """this is what the user of this module will call."""
        if not Sound.enabled:
            return
        game = Internal.field.game
        reactor = Internal.reactor
        if game and not game.autoPlay and Sound.playProcesses:
            # in normal play, wait a moment between two speaks. Otherwise
            # sometimes too many simultaneous speaks make them ununderstandable
            lastSpeakStart = max(x.startTime for x in Sound.playProcesses)
            if datetime.datetime.now() - lastSpeakStart < datetime.timedelta(seconds=0.3):
                reactor.callLater(1, Sound.speak, what)
                return
        if os.path.exists(what):
            if Sound.findOgg():
                if os.name == 'nt':
                    name, ext = os.path.splitext(what)
                    assert ext == '.ogg'
                    wavName = name + '.wav'
                    if not os.path.exists(wavName):
                        args = [r'c:\vorbis\oggdec', '--quiet', what]
                        process = subprocess.Popen(args)
                        os.waitpid(process.pid, 0)
                    winsound.PlaySound(wavName, winsound.SND_FILENAME)
                else:
                    args = ['ogg123', '-q', what]
                    if Debug.sound:
                        game.debug(' '.join(args))
                    process = subprocess.Popen(args)
                    process.startTime = datetime.datetime.now()
                    process.name = what
                    Sound.playProcesses.append(process)
                    reactor.callLater(3, Sound.cleanProcesses)
                    reactor.callLater(6, Sound.cleanProcesses)
        elif False:
            text = os.path.basename(what)
            text = os.path.splitext(text)[0]
            # If this ever works, we need to translate all texts
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

    __availableVoices = None

    def __init__(self, directory, content=None):
        """give this name a voice"""
        self.__md5sum = None
        if not os.path.split(directory)[0]:
            if Debug.sound:
                logDebug('place voice %s in %s' % (directory, cacheDir()))
            directory = os.path.join(cacheDir(), directory)
        self.directory = directory
        self.__setArchiveContent(content)

    def __str__(self):
        return self.directory

    def __repr__(self):
        return "<Voice: %s>" % self

    def language(self):
        """the language code of this voice. Locally defined voices
        have no language code and return 'local'.
        remote voices received from other clients return 'remote',
        they always get predecence."""
        if len(self.directory) == 32:
            if os.path.split(self.directory)[1] == self.md5sum:
                return 'remote'
        home = os.environ['HOME'].decode('utf-8')
        if self.directory.startswith(home):
            return 'local'
        result = os.path.split(self.directory)[0]
        result = os.path.split(result)[1]
        if result == 'voices':
            result = 'en_US'
        return result


    @staticmethod
    def availableVoices():
        """a list of all voice directories"""
        if not Voice.__availableVoices and Internal.haveKDE:
            result = []
            for parentDirectory in KGlobal.dirs().findDirs("appdata", "voices"):
                parentDirectory = unicode(parentDirectory)
                for (dirpath, _, _) in os.walk(parentDirectory, followlinks=True):
                    if os.path.exists(os.path.join(dirpath, 's1.ogg')):
                        result.append(Voice(dirpath))
            config = KGlobal.config()
            group = KConfigGroup(config, 'Locale')
            prefLanguages = uniqueList(':'.join(['local', str(group.readEntry('Language')), 'en_uS']).split(':'))
            prefLanguages = dict((x[1], x[0]) for x in enumerate(prefLanguages))
            result = sorted(result, key=lambda x: prefLanguages.get(x.language(), 9999))
            if Debug.sound:
                logDebug('found voices:%s' % [str(x) for x in result])
            Voice.__availableVoices = result
        return Voice.__availableVoices

    @staticmethod
    def locate(name):
        """returns Voice or None if no foreign or local voice matches.
        In other words never return a predefined voice"""
        for voice in Voice.availableVoices():
            dirname = os.path.split(voice.directory)[-1]
            if name == voice.md5sum:
                if Debug.sound:
                    logDebug('locate found %s by md5sum in %s' % (name, voice.directory))
                return voice
            elif name == dirname and voice.language() == 'local':
                if Debug.sound:
                    logDebug('locate found %s by name in %s' % (name, voice.directory))
                return voice
        if Debug.sound:
            logDebug('%s not found' % (name))

    def buildSubvoice(self, oggName, side):
        """side is 'left' or 'right'."""
        angleDirectory = os.path.join(cacheDir(), 'angleVoices', self.md5sum, side)
        stdName = os.path.join(self.directory, oggName)
        angleName = os.path.join(angleDirectory, oggName)
        if os.path.exists(stdName) and not os.path.exists(angleName):
            sox = which('sox')
            if not sox:
                return stdName
            if not os.path.exists(angleDirectory):
                os.makedirs(angleDirectory)
            args = [sox, stdName, angleName, 'remix']
            if side == 'left':
                args.extend(['1,2', '0'])
            elif side == 'right':
                args.extend(['0', '1,2'])
            callResult = subprocess.call(args)
            if callResult:
                if Debug.sound:
                    logDebug('failed to build subvoice %s: return code=%s' % (angleName, callResult))
                return stdName
            if Debug.sound:
                logDebug('built subvoice %s' % angleName)
        return angleName

    def localTextName(self, text, angle):
        """build the name of the wanted sound file"""
        oggName = text.lower().replace(' ', '') + '.ogg'
        if angle == 90:
            return self.buildSubvoice(oggName, 'left')
        if angle == 270:
            return self.buildSubvoice(oggName, 'right')
        return os.path.join(self.directory, oggName)

    def speak(self, text, angle):
        """text must be a sound filename without extension"""
        fileName = self.localTextName(text, angle)
        if not os.path.exists(fileName):
            if Debug.sound:
                logDebug('Voice.speak: fileName %s not found' % fileName)
        Sound.speak(fileName)

    def oggFiles(self):
        """a list of all found ogg files"""
        if os.path.exists(self.directory):
            return sorted(x for x in os.listdir(self.directory) if x.endswith('.ogg'))

    def __computeMd5sum(self):
        """update md5sum file. If it changed, return True.
        If unchanged or no ogg files exist, remove archive and md5sum and return False.
        If ogg files exist but no archive, return True."""
        if self.__md5sum:
            # we already checked
            return
        md5FileName = os.path.join(self.directory, 'md5sum')
        archiveExists = os.path.exists(self.archiveName())
        ogg = self.oggFiles()
        if not ogg:
            removeIfExists(self.archiveName())
            removeIfExists(md5FileName)
            self.__md5sum = None
            logDebug('no ogg files in %s' % self)
            return
        md5sum = md5()
        for oggFile in ogg:
            md5sum.update(open(os.path.join(self.directory, oggFile)).read())
        # the md5 stamp goes into the old archive directory 'username'
        self.__md5sum = md5sum.hexdigest()
        existingMd5sum = self.savedmd5Sum()
        md5Name = self.md5FileName()
        if self.__md5sum != existingMd5sum:
            if Debug.sound:
                if not os.path.exists(md5Name):
                    logDebug('creating new %s' % md5Name)
                else:
                    logDebug('md5sum %s changed, rewriting %s with %s' % (existingMd5sum, md5Name, self.__md5sum))
            try:
                open(md5Name, 'w').write('%s\n' % self.__md5sum)
            except BaseException as exception:
                logException(m18n('cannot write <filename>%1</filename>: %2', md5Name, str(exception)))
        if archiveExists:
            archiveIsOlder = os.path.getmtime(md5Name) > os.path.getmtime(self.archiveName())
            if self.__md5sum != existingMd5sum or archiveIsOlder:
                os.remove(self.archiveName())

    def __buildArchive(self):
        """write the archive file and set self.__md5sum"""
        self.__computeMd5sum()
        if not os.path.exists(self.archiveName()):
            tarFile = tarfile.open(self.archiveName(), mode='w:bz2')
            for oggFile in self.oggFiles():
                tarFile.add(os.path.join(self.directory, oggFile), arcname=oggFile)
            tarFile.close()

    def archiveName(self):
        """ the full path of the archive file"""
        return os.path.join(self.directory, 'content.tbz')

    def md5FileName(self):
        """the name of the md5sum file"""
        return os.path.join(self.directory, 'md5sum')

    def savedmd5Sum(self):
        """returns the current value of the md5sum file"""
        if os.path.exists(self.md5FileName()):
            return open(self.md5FileName(), 'r').readlines()[0].strip()

    @property
    def md5sum(self):
        """the current checksum over all ogg files"""
        self.__computeMd5sum()
        return self.__md5sum

    def __setArchiveContent(self, content):
        """fill the Voice with ogg files"""
        if not content:
            return
        if not os.path.exists(self.directory):
            os.makedirs(self.directory)
        filelike = cStringIO.StringIO(content)
        tarFile = tarfile.open(mode='r|bz2', fileobj=filelike)
        tarFile.extractall(path=self.directory)
        if Debug.sound:
            logDebug('extracted archive into %s' % self.directory)
        tarFile.close()
        filelike.close()

    @property
    def archiveContent(self):
        """the content of the tarfile"""
        self.__buildArchive()
        if os.path.exists(self.archiveName()):
            return open(self.archiveName()).read()

    @archiveContent.setter
    def archiveContent(self, content):
        """new archive content"""
        self.__setArchiveContent(content)
