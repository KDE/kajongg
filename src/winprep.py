#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Copyright (C) 2008-2016 Wolfgang Rohdewald <wolfgang@rohdewald.de>

SPDX-License-Identifier: GPL-2.0


Start this in the installation directory of Kajongg: That
is where this program resides. Below you find a code
block that might have to be adapted.
"""

from subprocess import check_output, call, CalledProcessError
from shutil import copy, move, copytree, rmtree

import os
import zipfile
import tempfile

from qt import QStandardPaths

# pylint:disable=invalid-name


def makeIcon(svgName:str, icoName:str) ->None:
    """generates icoName.ico"""
    tmpDir = tempfile.mkdtemp(prefix='kaj')

    def pngName(resolution:int) ->str:
        """name for this resolution"""
        return '{}/kajongg{}.png'.format(
            tmpDir, resolution)
    resolutions = (16, 24, 32, 40, 48, 64, 96, 128)
    try:
        for resolution in resolutions:
            call(
                'inkscape -z -e {outfile} -w {resolution} '
                '-h {resolution} {infile}'.format(
                    outfile=pngName(resolution),
                    resolution=resolution,
                    infile=svgName).split())
        call('convert {pngFiles} {icoName}.ico'.format(
            pngFiles=' '.join(pngName(x)
                              for x in resolutions), icoName=icoName).split())
    finally:
        for resolution2 in resolutions:
            # if we re-use resolution, pylint sees a problem ...
            if os.path.exists(pngName(resolution2)):
                os.remove(pngName(resolution2))
        os.rmdir(tmpDir)

_ = "kf5-config --expandvars --install icon".split()
iconDir = check_output(_).decode().strip()

oxy48 = iconDir + '/oxygen/base/48x48'
oxy48Cat = oxy48 + '/categories/'
oxy48Act = oxy48 + '/actions/'
oxy48Apps = oxy48 + '/apps/'
oxy48Status = oxy48 + '/status/'

DEST = 'share'
if os.path.exists(DEST):
    rmtree(DEST)

targetDir = DEST + '/kmahjongglib'
kmjLibDir = QStandardPaths.locate(QStandardPaths.AppDataLocation, 'kmahjongglib', QStandardPaths.LocateDirectory)
copytree(kmjLibDir, targetDir)
for tileset in ('alphabet', 'egypt'):
    for extension in ('copyright', 'desktop', 'svgz'):
        os.remove(targetDir + '/tilesets/{}.{}'.format(tileset, extension))

os.makedirs(DEST + '/kajongg')
voiceDir = QStandardPaths.locate(QStandardPaths.AppDataLocation, 'kajongg/voices', QStandardPaths.LocateDirectory)
copytree(voiceDir, DEST + '/kajongg/voices')

for bellSound in ('/usr/share/sounds/KDE-Im-Message-In.ogg', ):
    if os.path.exists(bellSound):
        os.makedirs(DEST + '/sounds')
        copy(bellSound, DEST + '/sounds/bell.ogg')
        break

os.makedirs(DEST + '/icons')
copy(oxy48Cat + 'applications-education.png', DEST + '/icons')
copy(oxy48Status + 'dialog-information.png', DEST + '/icons')
copy(oxy48Status + 'dialog-warning.png', DEST + '/icons')
copy(oxy48Apps + 'preferences-plugin-script.png', DEST + '/icons')
copy(oxy48Apps + 'preferences-desktop-locale.png', DEST + '/icons')


for png in (
        'application-exit', 'games-config-background', 'arrow-right',
        'format-list-ordered', 'object-rotate-left', 'help-contents',
        'dialog-close', 'im-user', 'draw-freehand', 'call-start',
        'configure', 'games-config-tiles', 'arrow-right-double',
        'document-new', 'edit-delete', 'document-open', 'list-add-user',
        'list-remove-user', 'configure-toolbars',
        'go-up', 'go-down', 'go-next', 'go-previous'):
    copy('{}/{}.png'.format(oxy48Act, png), DEST + '/icons')

oggdec = 'oggdecV1.10.1.zip'
try:
    call('wget https://www.rarewares.org/files/ogg/{}'.format(oggdec).split())
    with zipfile.ZipFile(oggdec) as ziparch:
        ziparch.extract('oggdec.exe')
finally:
    os.remove(oggdec)
move('oggdec.exe', DEST + '/kajongg/voices')

copy('backgroundselector.ui', DEST + '/kajongg')
copy('tilesetselector.ui', DEST + '/kajongg')

copy('../icons/sc-apps-kajongg.svgz', DEST + '/icons/kajongg.svgz')

makeIcon('../icons/sc-apps-kajongg.svgz', 'kajongg')
makeIcon(
    iconDir +
    '/hicolor/scalable/actions/games-kajongg-law.svgz',
    'games-kajongg-law')
copy('kajongg.ico', DEST + '/icons')
copy('games-kajongg-law.ico', DEST + '/icons')

# select sufficiently complete languages from
# https://websvn.kde.org/trunk/l10n-kf5
languages = (
    'bs', 'ca', 'da', 'de', 'en_GB', 'es', 'et', 'fr', 'gl', 'it', 'kk',
    'km', 'nl', 'nb', 'nds',
    'pl', 'pt', 'pt_BR', 'ru', 'sl', 'sv', 'uk', 'zh_TW')

# languages = ('de', 'zh_TW')

for lang in languages:
    print('getting language', lang)
    os.makedirs(DEST + '/locale/{}/LC_MESSAGES'.format(lang))
    with open(os.devnull, 'wb') as DEVNULL:
        for filename in (
                'kdegames/kajongg',
                'kdegames/libkmahjongg5',
                'kdegames/desktop_kdegames_libkmahjongg'):
            try:
                mo_data = check_output(
                    'svn cat svn://anonsvn.kde.org/home/kde/'
                    'trunk/l10n-kf5/{}/messages/{}.po'.format(
                        lang, filename).split(), stderr=DEVNULL)
                print('found:', lang, filename)
                with open('x.po', 'wb') as outfile:
                    outfile.write(mo_data)
                call(
                    'msgfmt x.po -o {}/locale/{}/LC_MESSAGES/{}.mo'.format(
                        DEST,
                        lang,
                        filename.split('/')[1]).split())
                os.remove('x.po')
            except CalledProcessError:
                print('not found:', lang, filename)
