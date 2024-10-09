#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Copyright (C) 2008-2017 Wolfgang Rohdewald <wolfgang@rohdewald.de>

SPDX-License-Identifier: GPL-2.0

Start this in the installation directory of Kajongg: That
is where this program resides. Below you find a code
block that might have to be adapted.
"""

from distutils.core import setup
from distutils.command.build import build
from subprocess import call

import re
import os

# Adapt this range: =======================================================
FULLAUTHOR = "Wolfgang Rohdewald <wolfgang@rohdewald.de>"
LICENSE = 'GNU General Public License v2'
URL = "https://apps.kde.org/kajongg"
try:
    from appversion import VERSION
except ImportError:
    VERSION = "Unknown"

# =======================================================

# This most certainly does not run on Windows. We do not care for now.
# at least all / in paths would have to be changed

(AUTHOR, EMAIL) = re.match('^(.*?)\s*<(.*)>$', FULLAUTHOR).groups()

os.umask(0o0022) # files should be readable and executable by everybody

kdeDirs = {}
for type in 'exe', 'data', 'xdgdata-apps', 'icon', 'html':
    kdeDirs[type] = os.popen("kf5-config --expandvars --install %s" % type).read().strip()
kdeDirs['iconApps'] = os.path.join(kdeDirs['icon'], 'hicolor', 'scalable', 'apps')
kdeDirs['iconActions'] = os.path.join(kdeDirs['icon'], 'hicolor', 'scalable', 'actions')

app_files = [os.path.join('src', x) for x in os.listdir('src') if x.endswith('.py')]
app_files.append('src/kajonggui.rc')
app_files.append('COPYING')
app_files.append('COPYING.DOC')

doc_files = [os.path.join('doc', x) for x in os.listdir('doc') if x.endswith('.png')]

for ignFile in os.listdir('src'):
    if ignFile.endswith('.pyc'):
        os.remove(os.path.join('src', ignFile))

data_files = [ \
    (kdeDirs['exe'], ['kajongg', 'kajonggserver']),
    (os.path.join(kdeDirs['data'], 'kajongg'), app_files),
    (os.path.join(kdeDirs['html'], 'en', 'kajongg'), doc_files),
    (kdeDirs['xdgdata-apps'], ['org.kde.kajongg.desktop']),
    ('/usr/share/doc/kajongg/', ['COPYING.DOC']),
    (kdeDirs['iconApps'], ['kajongg.svgz']),
    (kdeDirs['iconActions'], ['games-kajongg-law.svgz'])]

voice_directories = [x for x in os.listdir('voices') if x.startswith('male') or x.startswith('female')]
for directory in voice_directories:
    data_files.append((os.path.join(kdeDirs['data'], 'kajongg', 'voices', directory), [os.path.join('voices', directory, x) for x in os.listdir(os.path.join('voices', directory))]))

extra = {}
# extra['requires'] = ('pyQt4', 'sdf') does not do anything

class KmjBuild(build):

    def run(self):
        for binary in ['kajongg', 'kajonggserver']:
            open(binary, 'w').write('#!/bin/sh\nexec %skajongg/%s.py $*\n' % (kdeDirs['data'], binary))
            os.chmod(binary, 0o0755)
        call(['cp sc-apps-kajongg.svgz kajongg.svgz'], shell=True)
        call(['cp sc-action-games-kajongg-law.svgz games-kajongg-law.svgz'], shell=True)
        build.run(self)


setup(name='kajongg',
    version=VERSION,
    description='The classical game of Mah Jongg',
    long_description="This is the classical Mah Jongg for four players. "
            "If you are looking for the Mah Jongg solitaire please use the "
            "application kmahjongg.",
    author=AUTHOR,
    author_email=EMAIL,
    url=URL,
    download_url='https://www.linux-apps.com/p/1109453/',
    data_files=data_files,
    cmdclass = { 'build' : KmjBuild },  # define custom build class
    license=LICENSE,
    classifiers=['Development Status :: 4 - Beta',
        'License :: OSI Approved :: GNU General Public License (GPL)',
        'Operating System :: OS Independent',
        'Environment :: X11 Applications :: KDE',
        'Topic :: Desktop Environment :: K Desktop Environment (KDE)',
        'Topic :: Games:: Board Games',
        'Intended Audience :: End Users/Desktop',
        'Programming Language :: Python',],
    **extra)
