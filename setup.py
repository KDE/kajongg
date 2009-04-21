#!/usr/bin/env python
# -*- coding: utf-8 -*-

from distutils.core import setup
from distutils.command.build import build
from distutils.spawn import find_executable, spawn
from distutils.debug import DEBUG

DEBUG = 1

import re
import os, sys

if not hasattr(sys, 'version_info') or sys.version_info < (2, 5, 0, 'final'):
    raise SystemExit, "Qct requires python 2.5 or later."

FULLAUTHOR = "Wolfgang Rohdewald <wolfgang@rohdewald.de>"
LICENSE = 'GNU General Public License v2'
#URL = "http://code.google.com/p/id3encodingconverter"
VERSION = "0.1"

(AUTHOR, EMAIL) = re.match('^(.*?)\s*<(.*)>$', FULLAUTHOR).groups()

for ignFile in os.listdir('src'):
    if ignFile.endswith('.pyc'):
        os.remove(os.path.join('src', ignFile))

kdeDirs = {}
for type in 'exe', 'data', 'xdgdata-apps', 'icon', 'locale':
    kdeDirs[type] = os.popen("kde4-config --expandvars --install %s" % type).read().strip()

def createMOPathList(targetDir, sourceDir):
    import os, stat
    names = os.listdir(sourceDir)
    fileList = []
    for name in names:
        try:
            st = os.lstat(os.path.join(sourceDir, name))
        except os.error:
            continue
        if stat.S_ISDIR(st.st_mode):
            for fileName in os.listdir(os.path.join(sourceDir, name)):
                target = os.path.join(targetDir, name, 'LC_MESSAGES')
                source = os.path.join(sourceDir, name, fileName)
                fileList.append((target, [source]))
    return fileList

app_files = [os.path.join('src', x) for x in os.listdir('src') if x.endswith('.py')]
app_files.append('src/kmjui.rc')
app_files.append('src/COPYING')

data_files = [ \
    (kdeDirs['exe'], ['kmj']),
    (os.path.join(kdeDirs['data'], 'kmj'), app_files),
    (kdeDirs['xdgdata-apps'], ['kmj.desktop']),
    ('/usr/share/doc/kmj/', ['src/COPYING']),
    (kdeDirs['icon'], ['src/kmj.svg'])]
#data_files.extend(createMOPathList(kde4LocaleTarget, 'mo/'))
print 'data_files:', data_files
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
        kde4DataTarget = os.popen("kde4-config --expandvars --install data").read().strip()
        kde4ExeTarget = os.popen("kde4-config --expandvars --install exe").read().strip()
        open('kmj', 'w').write('#!/bin/sh\nexec %skmj/kmj.py\n' % kde4DataTarget)
        os.chmod('kmj',0755 )
        uiFiles = [os.path.join('src', x) for x in os.listdir('src') if x.endswith('.ui')]
        for uiFile in uiFiles:
            pyFile = uiFile.replace('.ui', '_ui.py')
            if not os.path.exists('src/'+pyFile):
                self.compile_ui(uiFile, pyFile)
        build.run(self)

# TODO: locales

setup(name='kmj',
    version=VERSION,
    description='computes payments among the 4 players',
    long_description="This is the classical Mah Jongg for four players. "
            "If you are looking for the Mah Jongg solitaire please use the "
            "application kmahjongg. Right now this programm only allows to "
            "enter the scores, it will then compute the payments and show "
            "the ranking of the players.",
    author=AUTHOR,
    author_email=EMAIL,
#    url=URL,
 #   download_url='http://code.google.com/p/id3encodingconverter/downloads/list',
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

