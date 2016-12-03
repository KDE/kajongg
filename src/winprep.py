#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Copyright (C) 2008-2016 Wolfgang Rohdewald <wolfgang@rohdewald.de>

Kajongg is free software you can redistribute it and/or modify
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

Start this in the installation directory of Kajongg: That
is where this program resides. Below you find a code
block that might have to be adapted.
"""

from __future__ import print_function

from subprocess import check_output, call, CalledProcessError
from shutil import copy, move, copytree, rmtree

import os
import zipfile
import tempfile

# pylint:disable=invalid-name


def makeIcon(svgName, icoName):
    """generates icoName.ico"""
    tmpDir = tempfile.mkdtemp(prefix='kaj')

    def pngName(resolution):
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

dataDir = check_output(
    "kde4-config --expandvars --install data".split()).strip()
iconDir = check_output(
    "kde4-config --expandvars --install icon".split()).strip()
oxy48 = iconDir + '/oxygen/base/48x48'
oxy48Cat = oxy48 + '/categories/'
oxy48Act = oxy48 + '/actions/'
oxy48Apps = oxy48 + '/apps/'
oxy48Status = oxy48 + '/status/'

DEST = 'share'
if os.path.exists(DEST):
    rmtree(DEST)

targetDir = DEST + '/kde4/apps/kmahjongglib'
os.makedirs(DEST + '/kde4/apps')
copytree(dataDir + '/kmahjongglib', targetDir)
for tileset in ('alphabet', 'egypt'):
    for extension in ('copyright', 'desktop', 'svgz'):
        os.remove(targetDir + '/tilesets/{}.{}'.format(tileset, extension))

os.makedirs(DEST + '/kde4/apps/kajongg')
copytree(dataDir + '/kajongg/voices', DEST + '/kde4/apps/kajongg/voices')

os.makedirs(DEST + '/icons')
copy(oxy48Cat + 'applications-education.png', DEST + '/icons')
copy(oxy48Status + 'dialog-information.png', DEST + '/icons')
copy(oxy48Status + 'dialog-warning.png', DEST + '/icons')
copy(oxy48Apps + 'preferences-plugin-script.png', DEST + '/icons')

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
    call('wget http://www.rarewares.org/files/ogg/{}'.format(oggdec).split())
    with zipfile.ZipFile(oggdec) as ziparch:
        ziparch.extract('oggdec.exe')
finally:
    os.remove(oggdec)
move('oggdec.exe', DEST + '/kde4/apps/kajongg/voices')

copy('backgroundselector.ui', DEST + '/kde4/apps/kajongg')
copy('tilesetselector.ui', DEST + '/kde4/apps/kajongg')

copy('../hisc-apps-kajongg.svgz', DEST + '/icons/kajongg.svgz')

makeIcon('../hisc-apps-kajongg.svgz', 'kajongg')
makeIcon(
    iconDir +
    '/hicolor/scalable/actions/games-kajongg-law.svgz',
    'games-kajongg-law')
copy('kajongg.ico', DEST + '/icons')
copy('games-kajongg-law.ico', DEST + '/icons')

# select sufficiently complete languages from
# http://l10n.kde.org/stats/gui/trunk-kde4/po/kajongg.po/
languages = (
    'bs', 'ca', 'da', 'de', 'en_GB', 'es', 'et', 'fr', 'gl', 'it', 'kk',
    'km', 'nl', 'nb', 'nds',
    'pl', 'pt', 'pt_BR', 'ru', 'sl', 'sv', 'uk', 'zh_TW')

# languages = ('de', 'zh_TW')

for lang in languages:
    print('getting language', lang)
    os.makedirs(DEST + '/locale/{}/LC_MESSAGES'.format(lang))
    DEVNULL = open(os.devnull, 'wb')
    for kde45 in ('l10n-kde4', 'l10n-kf5'):
        for filename in (
                'kdegames/kajongg', 'kdegames/libkmahjongg',
                'kdegames/libkmahjongg5',
                'kdegames/desktop_kdegames_libkmahjongg',
                'kdelibs/kdelibs4', 'qt/kdeqt'):
            try:
                mo_data = check_output(
                    'svn cat svn://anonsvn.kde.org/home/kde/'
                    'trunk/{}/{}/messages/{}.po'.format(
                        kde45, lang, filename).split(), stderr=DEVNULL)
                print('found:', lang, kde45, filename)
                with open('x.po', 'wb') as outfile:
                    outfile.write(mo_data)
                call(
                    'msgfmt x.po -o {}/locale/{}/LC_MESSAGES/{}.mo'.format(
                        DEST,
                        lang,
                        filename.split('/')[1]).split())
                os.remove('x.po')
            except CalledProcessError:
                pass
