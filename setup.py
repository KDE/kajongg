#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Start this in the installation directory of kajongg: That
is where this program resides. Below you find a code 
block that might have to be adapted.

This script adds translations for all languages appearing 
in kajongg.desktop."""

from distutils.core import setup
from distutils.command.build import build
from distutils.spawn import find_executable, spawn
from distutils.debug import DEBUG

from subprocess import call
from shutil import copytree, rmtree



import re
import os, sys

if not hasattr(sys, 'version_info') or sys.version_info < (2, 5, 0, 'final'):
    raise SystemExit, "Qct requires python 2.5 or later."

# Adapt this range: =======================================================
FULLAUTHOR = "Wolfgang Rohdewald <wolfgang@rohdewald.de>"
LICENSE = 'GNU General Public License v2'
URL = "http://www.kde-apps.org/content/show.php/kajongg?content=103206"
VERSION = "0.4.0"
# where do we have the source?
kdeDir = os.path.join(os.getenv('HOME'),'src', 'kde')
# =======================================================

# This most certainly does not run on Windows. We do not care for now.
# at least all / in paths would have to be changeds

(AUTHOR, EMAIL) = re.match('^(.*?)\s*<(.*)>$', FULLAUTHOR).groups()

os.umask(0022) # files should be readable and executable by everybody

def compress_icons():
    for icon in ['games-kajongg-law','kajongg']:
    	call(['gzip -c %(icon)s.svg >%(icon)s.svgz' % locals()], shell=True, cwd='src')

locales = []
for desktopLine in open('kajongg.desktop', 'r').readlines():
    if desktopLine.startswith('Comment['):
        part1 = desktopLine.split('=')[0][8:-1]
	if part1 != 'x-test':
        	locales.append(part1)

for locale in locales:
    localeDir = os.path.join('locale', locale)
    if not os.path.exists(localeDir):
        os.makedirs(localeDir)
    poFileName = os.path.join(localeDir, 'kajongg.po')
    moFileName = os.path.join(localeDir, 'kajongg.mo')
    poFile = open(poFileName, 'w')
    nullFile = open('/dev/null', 'w')
    call(['svn', 'cat', 'svn://anonsvn.kde.org/home/kde/trunk/l10n-kde4/%s/messages/playground-games/kajongg.po' % locale, poFileName], stdout=poFile, stderr=nullFile)
    call(['msgfmt', '-o', moFileName, poFileName])

kdeDirs = {}
for type in 'exe', 'data', 'xdgdata-apps', 'icon', 'locale', 'html':
    kdeDirs[type] = os.popen("kde4-config --expandvars --install %s" % type).read().strip()
kdeDirs['iconApps'] = os.path.join(kdeDirs['icon'], 'hicolor', 'scalable', 'apps')
kdeDirs['iconActions'] = os.path.join(kdeDirs['icon'], 'hicolor', 'scalable', 'actions')

app_files = [os.path.join('src', x) for x in os.listdir('src') if x.endswith('.py')]
app_files.append('src/kajonggui.rc')
app_files.append('src/COPYING')

if not os.path.exists('doc'):
    # in the svn tree, the kajongg doc is outside of our tree, move it in:
    copytree(os.path.join('..', 'doc', 'kajongg'), 'doc')

docDir = os.path.join(kdeDir, 'playground', 'games', 'doc', 'kajongg')
doc_files = [os.path.join('doc', x) for x in os.listdir(docDir) if x.endswith('.png')]

compress_icons()

for ignFile in os.listdir('src'):
    if ignFile.endswith('.pyc'):
      	os.remove(os.path.join('src', ignFile))

data_files = [ \
    (kdeDirs['exe'], ['kajongg','kajonggserver']),
    (os.path.join(kdeDirs['data'], 'kajongg'), app_files),
    (os.path.join(kdeDirs['html'], 'en','kajongg'), doc_files),
    (kdeDirs['xdgdata-apps'], ['kajongg.desktop']),
    ('/usr/share/doc/kajongg/', ['src/COPYING']),
    (kdeDirs['iconApps'], ['src/kajongg.svgz']),
    (kdeDirs['iconActions'], ['src/games-kajongg-law.svgz'])]

for locale in locales:
    data_files.append((os.path.join(kdeDirs['locale'], locale, 'LC_MESSAGES'), [os.path.join('locale', locale, 'kajongg.mo')]))
    trdocDir = os.path.join(kdeDir, 'l10n-kde4', locale, 'docs', 'playground-games', 'kajongg')
    if os.path.exists(trdocDir):
    	print 'found:',trdocDir
    	trdoc_files = [os.path.join(trdocDir, x) for x in os.listdir(trdocDir) \
		if x.endswith('.png') or x.endswith('.docbook')]
    	data_files.append((os.path.join(kdeDirs['html'], locale, 'kajongg'), trdoc_files))

extra = {}
# extra['requires'] = ('pyQt4', 'sdf') does not do anything

class KmjBuild(build):
    def compile_ui(self, ui_file, py_file):
     # Search for pyuic4 in python bin dir, then in the $Path.
        try:
            from PyQt4 import pyqtconfig
        except ImportError:
            pyuic_exe = None
        else:
            pyqt_configuration = pyqtconfig.Configuration()
            pyuic_exe = find_executable('pyuic4', pyqt_configuration.default_bin_dir)
        if not pyuic_exe: pyuic_exe = find_executable('pyuic4')
        if not pyuic_exe: pyuic_exe = find_executable('pyuic4.bat')
        if not pyuic_exe: print "Unable to find pyuic4 executable"; return
        cmd = [pyuic_exe, ui_file, '-o', py_file]
        try:
            spawn(cmd)
        except:
            print pyuic_exe + " is a shell script"
            cmd = ['/bin/sh', '-e', pyuic_exe, ui_file, '-o', py_file]
            spawn(cmd)

    def run(self):
        for binary in ['kajongg','kajonggserver']:
            open(binary, 'w').write('#!/bin/sh\nexec %skajongg/%s.py $*\n' % (kdeDirs['data'], binary))
            os.chmod(binary, 0755 )
        uiFiles = [os.path.join('src', x) for x in os.listdir('src') if x.endswith('.ui')]
        for uiFile in uiFiles:
            pyFile = uiFile.replace('.ui', '_ui.py')
            if not os.path.exists('src/'+pyFile):
                self.compile_ui(uiFile, pyFile)
        build.run(self)

setup(name='kajongg',
    version=VERSION,
    description='computes payments among the 4 players',
    long_description="This is the classical Mah Jongg for four players. "
            "If you are looking for the Mah Jongg solitaire please use the "
            "application kmahjongg. Right now this program only allows to "
            "enter the scores, it will then compute the payments and show "
            "the ranking of the players.",
    author=AUTHOR,
    author_email=EMAIL,
    url=URL,
    download_url='http://www.kde-apps.org/content/download.php?content=103206&id=1',
    data_files=data_files,
    cmdclass = { 'build' : KmjBuild },  # define custom build class
    license=LICENSE,
    classifiers=['Development Status :: 1 - Alpha',
        'License :: OSI Approved :: GNU General Public License (GPL)',
        'Operating System :: OS Independent',
        'Environment :: X11 Applications :: KDE',
        'Topic :: Desktop Environment :: K Desktop Environment (KDE)',
        'Topic :: Games:: Board Games',
        'Intended Audience :: End Users/Desktop',
        'Programming Language :: Python',],
    **extra)

for cleanFile in os.listdir('src'):
    if cleanFile.endswith('.svgz'):
      	os.remove(os.path.join('src', cleanFile))

