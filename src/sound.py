# -*- coding: utf-8 -*-

"""
Copyright (C) 2010-2016 Wolfgang Rohdewald <wolfgang@rohdewald.de>

SPDX-License-Identifier: GPL-2.0

"""

import os
import sys
import tarfile
import subprocess
import datetime
from io import BytesIO
from hashlib import md5

from common import Debug, Internal, ReprMixin, cacheDir
from util import which, removeIfExists, uniqueList, elapsedSince
from log import logWarning, i18n, logDebug, logException

from qt import QStandardPaths

from tile import Tile

        # Phonon does not work with short files - it plays them
        # simultaneously or only parts of them. Mar 2010, KDE 4.4. True for mp3
        # and for wav. Also, mpg123 often plays distorted sounds. Kubuntu 9.10.
        # So we use ogg123 and ogg sound files.
        # self.audio = Phonon.MediaObject(self)
        # self.audioOutput = Phonon.AudioOutput(Phonon.GameCategory, self)
        # Phonon.createPath(self.audio, self.audioOutput)
        # self.audio.enqueue(Phonon.MediaSource(wavName))
        # self.audio.play()

if sys.platform == 'win32':
    import winsound  # pylint: disable=import-error

class SoundPopen(subprocess.Popen):

    """with additional attributes"""

    def __init__(self, what, args):
        super().__init__(args)
        self.name = what
        self.startTime = datetime.datetime.now()


class Sound:

    """the sound interface. Use class variables and class methods,
    thusly ensuring no two instances try to speak"""
    __oggBinary = None
    __bonusOgg = None
    playProcesses = []
    lastCleaned = None

    @staticmethod
    def findOggBinary():
        """set __oggBinary to exe name or an empty string"""
        if Sound.__oggBinary is None:
            if sys.platform == 'win32':
                Sound.__oggBinary = os.path.join('share', 'kajongg', 'voices', 'oggdec.exe')
                msg = ''  # we bundle oggdec.exe with the kajongg installer, it must be there
            else:
                oggBinary = 'ogg123'
                msg = i18n(
                    'No voices will be heard because the program %1 is missing',
                    oggBinary)
                if which(oggBinary):
                    Sound.__oggBinary = oggBinary
                else:
                    Sound.__oggBinary = ''
                    assert Internal.Preferences
                    Internal.Preferences.useSounds = False
                    # checks again at next reenable
                    if msg:
                        logWarning(msg)
            if Debug.sound:
                logDebug('ogg123 found:' + Sound.__oggBinary)
        return Sound.__oggBinary

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
                    assert Internal.scene
                    game = Internal.scene.game
                    assert game
                    game.debug('10 seconds passed. Killing %s' % process.name)
            else:
                remaining.append(process)
        Sound.playProcesses = remaining

    @staticmethod
    def speak(what):
        """this is what the user of this module will call."""
        # pylint: disable=too-many-branches
        if not Internal.scene:
            return
        assert Internal.Preferences
        if not Internal.Preferences.useSounds:
            return
        game = Internal.scene.game
        if not game:
            return
        reactor = Internal.reactor
        assert reactor
        if game and not game.autoPlay and len(Sound.playProcesses) > 0:
            # in normal play, wait a moment between two speaks. Otherwise
            # sometimes too many simultaneous speaks make them ununderstandable
            lastSpeakStart = max(x.startTime for x in Sound.playProcesses)
            if elapsedSince(lastSpeakStart) < 0.3:
                assert reactor
                reactor.callLater(1, Sound.speak, what)
                return
        if os.path.exists(what):
            oggBinary = Sound.findOggBinary()
            if oggBinary:
                if sys.platform == 'win32':
                    # convert to .wav, store .wav in cacheDir
                    name, ext = os.path.splitext(what)
                    assert ext == '.ogg', 'what: {} name: {} ext: {}'.format(what, name, ext)
                    if 'bell' in name:
                        nameParts = ['bell']
                    else:
                        nameParts = os.path.normpath(name).split(os.sep)
                        nameParts = nameParts[nameParts.index('voices') + 1:]
                    wavName = os.path.normpath(
                        '{}/{}.wav'.format(cacheDir(),
                                           '_'.join(nameParts)))
                    if not os.path.exists(wavName):
                        args = [oggBinary, '-a', '-w', wavName, os.path.normpath(what)]
                        startupinfo = subprocess.STARTUPINFO()
                        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                        subprocess.call(args, startupinfo=startupinfo)
                        if Debug.sound:
                            logDebug('converted {} to wav {}'.format(what, wavName))
                    try:
                        winsound.PlaySound(
                            wavName,
                            winsound.SND_FILENAME | winsound.SND_NODEFAULT)
                    except RuntimeError:
                        pass
                else:
                    args = [oggBinary, '-q', what]
                    if Debug.sound:
                        game.debug(' '.join(args))
                    process = SoundPopen(what, args)
                    Sound.playProcesses.append(process)
                    reactor.callLater(3, Sound.cleanProcesses)
                    reactor.callLater(6, Sound.cleanProcesses)

    @staticmethod
    def bonus():
        """ring some sort of bell, if we find such a file"""
        if Sound.__bonusOgg is None:
            Sound.__bonusOgg = ''
            for oggName in (
                    '/usr/share/sounds/KDE-Im-Message-In.ogg',
                    'share/sounds/bell.ogg'):
                if os.path.exists(oggName):
                    Sound.__bonusOgg = oggName
                    if Debug.sound:
                        logDebug('Bonus sound found:{}'.format(oggName))
                    break
            if Debug.sound and not Sound.__bonusOgg:
                logDebug('No bonus sound found')
        if Sound.__bonusOgg:
            Sound.speak(Sound.__bonusOgg)

class Voice(ReprMixin):

    """this administers voice sounds.

    When transporting voices between players, a compressed tarfile
    is generated at source and transferred to destination. At
    destination, no tarfile is written, only the content. It makes
    only sense to cache the voice in a tarfile at source."""

    __availableVoices = []
    md5sumLength = 32 # magical constant

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

    def language(self):
        """the language code of this voice. Locally defined voices
        have no language code and return 'local'.
        remote voices received from other clients return 'remote',
        they always get predecence."""
        if len(self.directory) == self.md5sumLength:
            if os.path.split(self.directory)[1] == self.md5sum:
                return 'remote'
        if 'HOME' in os.environ:
            home = os.environ['HOME']
        elif 'HOMEPATH' in os.environ:
            home = os.environ['HOMEPATH']
        else:
            logException('have neither HOME nor HOMEPATH')
        if home:
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
        if not Voice.__availableVoices:
            result = []
            directories = QStandardPaths.locateAll(
                QStandardPaths.AppDataLocation, 'voices', QStandardPaths.LocateDirectory)
            directories.insert(0, os.path.join('share', 'kajongg', 'voices'))
            for parentDirectory in directories:
                for (dirpath, _, _) in os.walk(parentDirectory, followlinks=True):
                    if os.path.exists(os.path.join(dirpath, 's1.ogg')):
                        result.append(Voice(dirpath))
            group = Internal.kajonggrc.group('Locale')
            _ = uniqueList(
                ':'.join(['local', str(group.readEntry('Language')), 'en_US']).split(':'))
            prefLanguages = dict((x[1], x[0]) for x in enumerate(_))
            result = sorted(
                result, key=lambda x: prefLanguages.get(x.language(), 9999))
            if Debug.sound:
                logDebug('found voices:%s' % [str(x) for x in result])
            Voice.__availableVoices = result
        return Voice.__availableVoices

    @staticmethod
    def locate(name):
        """return Voice or None if no foreign or local voice matches.
        In other words never return a predefined voice"""
        for voice in Voice.availableVoices():
            dirname = os.path.split(voice.directory)[-1]
            if name == voice.md5sum:
                if Debug.sound:
                    logDebug(
                        'locate found %s by md5sum in %s' %
                        (name, voice.directory))
                return voice
            if name == dirname and voice.language() == 'local':
                if Debug.sound:
                    logDebug(
                        'locate found %s by name in %s' %
                        (name, voice.directory))
                return voice
        if Debug.sound:
            logDebug('Personal sound for %s not found' % (name))
        return None

    def buildSubvoice(self, oggName, side):
        """side is 'left' or 'right'."""
        angleDirectory = os.path.join(
            cacheDir(),
            'angleVoices',
            self.md5sum,
            side)
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
                    logDebug(
                        'failed to build subvoice %s: return code=%s' %
                        (angleName, callResult))
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
        if isinstance(text, Tile):
            text = str(text.exposed)
        fileName = self.localTextName(text, angle)
        if not os.path.exists(fileName):
            if Debug.sound:
                logDebug('Voice.speak: fileName %s not found' % fileName)
        Sound.speak(fileName)

    def oggFiles(self):
        """a list of all found ogg files"""
        if os.path.exists(self.directory):
            return sorted(x for x in os.listdir(self.directory) if x.endswith('.ogg'))
        return []

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
            with open(os.path.join(self.directory, oggFile), 'rb') as _:
                md5sum.update(_.read())
        # the md5 stamp goes into the old archive directory 'username'
        self.__md5sum = md5sum.hexdigest()
        existingMd5sum = self.savedmd5Sum()
        md5Name = self.md5FileName()
        if self.__md5sum != existingMd5sum:
            if Debug.sound:
                if not os.path.exists(md5Name):
                    logDebug('creating new %s' % md5Name)
                else:
                    logDebug(
                        'md5sum %s changed, rewriting %s with %s' %
                        (existingMd5sum, md5Name, self.__md5sum))
            try:
                with open(md5Name, 'w', encoding='ascii') as _:
                    _.write('%s\n' % self.__md5sum)
            except OSError as exception:
                logException(
                    '\n'.join([i18n('cannot write <filename>%1</filename>: %2',
                                    md5Name,
                                    str(exception)),
                               i18n('The voice files have changed, their checksum has changed.'),
                               i18n('Please reinstall kajongg or do, with sufficient permissions:'),
                               'cd {} ; cat *.ogg | md5sum > md5sum'.format(self.directory)]))
        if archiveExists:
            archiveIsOlder = os.path.getmtime(
                md5Name) > os.path.getmtime(self.archiveName())
            if self.__md5sum != existingMd5sum or archiveIsOlder:
                os.remove(self.archiveName())

    def __buildArchive(self):
        """write the archive file and set self.__md5sum"""
        self.__computeMd5sum()
        if not os.path.exists(self.archiveName()):
            with tarfile.open(self.archiveName(), mode='w:bz2') as tarFile:
                for oggFile in self.oggFiles():
                    tarFile.add(
                        os.path.join(
                            self.directory,
                            oggFile),
                        arcname=oggFile)

    def archiveName(self):
        """ the full path of the archive file"""
        return os.path.join(self.directory, 'content.tbz')

    def md5FileName(self):
        """the name of the md5sum file"""
        return os.path.join(self.directory, 'md5sum')

    def savedmd5Sum(self):
        """return the current value of the md5sum file"""
        if os.path.exists(self.md5FileName()):
            try:
                with open(self.md5FileName(), 'r', encoding='ascii') as _:
                    line = _.readlines()[0].replace(' -', '').strip()
                if len(line) == self.md5sumLength:
                    return line
                logWarning('{} has wrong content: {}'.format(self.md5FileName(), line))
            except OSError as exc:
                logWarning('{} has wrong content: {}'.format(self.md5FileName(), exc))
        return None

    @property
    def md5sum(self):
        """the current checksum over all ogg files"""
        self.__computeMd5sum()
        assert self.__md5sum
        return self.__md5sum

    def __setArchiveContent(self, content):
        """fill the Voice with ogg files"""
        if not content:
            return
        if not os.path.exists(self.directory):
            os.makedirs(self.directory)
        filelike = BytesIO(content)
        with tarfile.open(mode='r|bz2', fileobj=filelike) as tarFile:
            tarFile.extractall(path=self.directory)
            if Debug.sound:
                logDebug('extracted archive into %s' % self.directory)
        filelike.close()

    @property
    def archiveContent(self):
        """the content of the tarfile"""
        self.__buildArchive()
        if os.path.exists(self.archiveName()):
            return open(self.archiveName(), 'rb').read()
        return None

    @archiveContent.setter
    def archiveContent(self, content):
        """new archive content"""
        self.__setArchiveContent(content)
