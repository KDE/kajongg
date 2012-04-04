#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Start this in the installation directory of kajongg: That
is where this program resides. Below you find a code
block that might have to be adapted.
"""

from distutils.core import setup
from distutils.command.build import build
from distutils.spawn import find_executable, spawn
from distutils.debug import DEBUG

from subprocess import call
from shutil import copytree, rmtree



import re
import os, sys

if not hasattr(sys, 'version_info') or sys.version_info < (2, 6, 0, 'final'):
    raise SystemExit, "Kajongg requires python 2.6 or later."

# Adapt this range: =======================================================
FULLAUTHOR = "Wolfgang Rohdewald <wolfgang@rohdewald.de>"
LICENSE = 'GNU General Public License v2'
URL = "http://www.kde-apps.org/content/show.php/kajongg?content=103206"
VERSION = "4.9.0"
# where do we have the doc?
docDir = None
tryingDirs = ['doc', os.path.join('..', 'doc')]
for tryDir in tryingDirs:
    if os.path.exists(tryDir):
        docDir = tryDir
        break
if not docDir:
    print 'I cannot find the doc directory, tried %s' % ', '.join(tryingDirs)
    print 'I will not process the handbook'
# =======================================================

# This most certainly does not run on Windows. We do not care for now.
# at least all / in paths would have to be changeds

(AUTHOR, EMAIL) = re.match('^(.*?)\s*<(.*)>$', FULLAUTHOR).groups()

os.umask(0022) # files should be readable and executable by everybody

kdeDirs = {}
for type in 'exe', 'data', 'xdgdata-apps', 'icon', 'html':
    kdeDirs[type] = os.popen("kde4-config --expandvars --install %s" % type).read().strip()
kdeDirs['iconApps'] = os.path.join(kdeDirs['icon'], 'hicolor', 'scalable', 'apps')
kdeDirs['iconActions'] = os.path.join(kdeDirs['icon'], 'hicolor', 'scalable', 'actions')

app_files = [os.path.join('src', x) for x in os.listdir('src') if x.endswith('.py') or x.endswith('.ui')]
app_files.append('src/kajonggui.rc')
app_files.append('src/COPYING')

if not os.path.exists('doc'):
    # in the svn tree, the kajongg doc is outside of our tree, move it in:
    copytree(os.path.join('..', 'doc', 'kajongg'), 'doc')

doc_files = []
if docDir:
    doc_files = [os.path.join('doc', x) for x in os.listdir(docDir) if x.endswith('.png')]

for ignFile in os.listdir('src'):
    if ignFile.endswith('.pyc'):
        os.remove(os.path.join('src', ignFile))

data_files = [ \
    (kdeDirs['exe'], ['kajongg','kajonggserver']),
    (os.path.join(kdeDirs['data'], 'kajongg'), app_files),
    (os.path.join(kdeDirs['html'], 'en','kajongg'), doc_files),
    (kdeDirs['xdgdata-apps'], ['kajongg.desktop']),
    ('/usr/share/doc/kajongg/', ['src/COPYING']),
    (kdeDirs['iconApps'], ['kajongg.svgz']),
    (kdeDirs['iconActions'], ['games-kajongg-law.svgz'])]

voice_directories = [x for x in os.listdir('voices') if x.startswith('male') or x.startswith('female')]
for directory in voice_directories:
    data_files.append((os.path.join(kdeDirs['data'], 'kajongg', 'voices', directory), [os.path.join('voices', directory, x) for x in os.listdir(os.path.join('voices', directory))]))

extra = {}
# extra['requires'] = ('pyQt4', 'sdf') does not do anything

class KmjBuild(build):

    def run(self):
        for binary in ['kajongg','kajonggserver']:
            open(binary, 'w').write('#!/bin/sh\nexec %skajongg/%s.py $*\n' % (kdeDirs['data'], binary))
            os.chmod(binary, 0755 )
        call(['cp hisc-apps-kajongg.svgz kajongg.svgz'], shell=True)
        call(['cp hisc-action-games-kajongg-law.svgz games-kajongg-law.svgz'], shell=True)
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

