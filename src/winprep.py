#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Start this in the installation directory of kajongg: That
is where this program resides. Below you find a code
block that might have to be adapted.
"""

from subprocess import check_output, call
from shutil import copy, move, copytree, rmtree

import os, zipfile

# pylint:disable=invalid-name

dataDir = check_output("kde4-config --expandvars --install data".format(type).split()).strip()
iconDir = check_output("kde4-config --expandvars --install icon".format(type).split()).strip()
oxy48 = iconDir + '/oxygen/48x48'
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

for png in ('application-exit', 'games-config-background', 'arrow-right', 'format-list-ordered',
            'object-rotate-left', 'help-contents', 'dialog-close', 'im-user', 'draw-freehand',
            'call-start', 'configure', 'games-config-tiles', 'arrow-right-double', 'document-new',
            'edit-delete', 'document-open', 'list-add-user', 'list-remove-user'):
    copy('{}/{}.png'.format(oxy48Act, png), DEST + '/icons')

copy(iconDir + '/hicolor/scalable/actions/games-kajongg-law.svgz', DEST + '/icons')

oggdec = 'oggdecV1.9.9.zip'
call('wget http://www.rarewares.org/files/ogg/{}'.format(oggdec).split())
with zipfile.ZipFile(oggdec) as ziparch:
    ziparch.extract('oggdec.exe')
os.remove(oggdec)
move('oggdec.exe', DEST + '/kde4/apps/kajongg/voices')

copy('backgroundselector.ui', DEST + '/kde4/apps/kajongg')
copy('tilesetselector.ui', DEST + '/kde4/apps/kajongg')

copy('../hisc-apps-kajongg.svgz', DEST + '/icons/kajongg.svgz')
call(('convert.im6 ../hisc-apps-kajongg.svgz kajongg.ico').split())
copy('kajongg.ico', DEST + '/icons')

# select sufficiently complete languages from http://l10n.kde.org/stats/gui/trunk-kde4/po/kajongg.po/
languages = ('de', 'fr', 'pt_BR', 'ca', 'zh_TW', 'da', 'nl', 'it', 'kk', 'km', 'nds',
   'nb', 'pl', 'pt', 'ru', 'sl', 'es', 'sv', 'uk')

#languages = ('de', 'zh_TW')

for lang in languages:
    print 'getting language', lang
    os.makedirs(DEST + '/locale/{}/LC_MESSAGES'.format(lang))
    for directory, filename in (('kdegames', 'kajongg'), ('kdegames', 'libkmahjongg'),
            ('kdelibs', 'kdelibs4'), ('qt', 'kdeqt')):
        mo_data = check_output('svn cat svn://anonsvn.kde.org/home/kde/trunk/l10n-kde4/{}/messages/{}/{}.po'.format(
            lang, directory, filename).split())
        with open('x.po'.format(filename), 'w') as outfile:
            outfile.write(mo_data)
        call('msgfmt x.po -o {}/locale/{}/LC_MESSAGES/{}.mo'.format(DEST, lang, filename).split())
        os.remove('x.po')
