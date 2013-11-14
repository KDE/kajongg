# -*- coding: utf-8 -*-

"""
Copyright (C) 2008-2012 Wolfgang Rohdewald <wolfgang@rohdewald.de>

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


Here we define replacement classes for the case that we have no 
python interface to KDE.

"""

# pylint: disable=unused-import

__all__ = ['KAboutData', 'KApplication', 'KCmdLineArgs', 'KConfig',
            'KCmdLineOptions', 'i18n', 'i18nc', 'ki18n',
            'KMessageBox', 'KConfigSkeleton', 'KDialogButtonBox',
            'KConfigDialog', 'KDialog', 'KLineEdit',
            'KUser', 'KToggleFullScreenAction', 'KStandardAction',
            'KXmlGuiWindow', 'KStandardDirs', 'KGlobal', 'KIcon', 'KAction']

# no replacement yet available for those classes:

from PyKDE4.kdecore import KUser, KGlobal, KStandardDirs, \
    KAboutData, KCmdLineArgs, KConfig, KCmdLineOptions
from PyKDE4.kdecore import ki18n
from PyKDE4.kdeui import KMessageBox, KIcon, KLineEdit, \
    KConfigSkeleton, KDialogButtonBox, KAction, KStandardAction, \
    KApplication, KToggleFullScreenAction, KXmlGuiWindow, \
    KConfigDialog, KDialog

from util import xToUtf8

def i18n(englishIn, *args):
    """dummy for server TODO: should really translate and be usable for client too"""
    result = englishIn
    if '%' in result:
        for idx, arg in enumerate(args):
            arg = xToUtf8(arg)
            result = result.replace('%' + str(idx+1), unicode(arg))
    if '%' in result:
        for ignore in ['numid', 'filename']:
            result = result.replace('<%s>' % ignore, '')
            result = result.replace('</%s>' % ignore, '')
    return result

def i18nc(dummyContext, englishIn, *args):
    """dummy for server TODO: should really translate and be usable for client too"""
    return i18n(englishIn, *args)
