"""
    Copyright (C) 2010 Wolfgang Rohdewald <wolfgang@rohdewald.de>

    partially based on C++ code from:
    Copyright (C) 2006 Mauricio Piacentini  <mauricio@tabuleiro.com>

    Libkmahjongg is free software; you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation; either version 2 of the License, or
    (at your option) any later version.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with this program; if not, write to the Free Software
    Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.
"""

from os import path

from PyKDE4.kdecore import KStandardDirs
from PyQt4 import uic

def loadUi(base):
    """load the ui file for class base, deriving the file name from the class name"""
    name = base.__class__.__name__.lower() + '.ui'
    if path.exists(name):
        directory = path.cwd()
    else:
        directory = path.dirname(str(KStandardDirs.locate("appdata", name)))
    uic.loadUi(path.join(directory,name), base)
