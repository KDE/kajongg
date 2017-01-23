# pylint: disable=too-many-lines
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


Here we define replacement classes for the case that we have no
python interface to KDE.

"""


import os
from locale import _parse_localename, getdefaultlocale, setlocale, LC_ALL


# pylint: disable=wrong-import-order

# here come the replacements:

# pylint: disable=wildcard-import,unused-wildcard-import
from qt import *

from common import Internal, Debug
from util import uniqueList

import gettext


try:
    from kdepaths import LOCALEPATH
except ImportError:
    LOCALEPATH = None

__all__ = ['i18n', 'i18nc', 'qi18nc', 'i18nE', 'i18ncE', 'KDETranslator', 'MLocale']


ENGLISHDICT = {}

def __insertArgs(translatedTemplate, *args):
    """
    put format arguments into the translated template.
    KDE semantics markup is removed.

    @param translatedTemplate: The translated string template.
    @type translatedTemplate: C{str}
    @param args: The format arguments
    @type args: A list or tuple of C{str}

    @return: The formatted translated text.
    @rtype: C{str}
    """

    if '\004' in translatedTemplate:
        translatedTemplate = translatedTemplate.split('\004')[1]
    result = translatedTemplate
    if '%' in result:
        for idx in range(len(args)):
            result = result.replace('%%%d' % (idx + 1), '{%d}' % idx)
        result = result.format(*args)
    for ignore in ['numid', 'filename', 'interface']:
        result = result.replace('<%s>' % ignore, '')
        result = result.replace('</%s>' % ignore, '')
    return result


def i18n(englishIn, *args):
    """
    Translate. Since this is a 1:1 replacement for the
    corresponding KDE function, it accepts only C{str}.

    @param englishIn: The english template.
    @type englishIn: C{str}
    @return: The translated text, args included.
    @rtype: C{str}
    """
    if MLocale.translation and englishIn:
        _ = MLocale.translation.gettext(englishIn)
    else:
        _ = englishIn
    if not args:
        ENGLISHDICT[_] = englishIn
    result = __insertArgs(_, *args)
    return result


def i18nc(context, englishIn, *args):
    """
    Translate. Since this is a 1:1 replacement for the
    corresponding KDE function, it accepts only C{str}.

    @param context: The context of this string.
    @type context: C{str}
    @param englishIn: The english template.
    @type englishIn: C{str}
    @return: The translated text, args included.
    @rtype: C{str}
    """
    # The \004 trick is taken from kdecore/localization/gettext.h,
    # definition of pgettext_aux"""
    if not MLocale.translation:
        return __insertArgs(englishIn, *args)
    withContext = '\004'.join([context, englishIn])
    _ = MLocale.translation.gettext(withContext)
    if _ == withContext:
        # try again without context
        _ = MLocale.translation.gettext(englishIn)
    if not args:
        ENGLISHDICT[_] = englishIn
    return __insertArgs(_, *args)

def qi18nc(context, englishIn, *args):
    """This uses the Qt translation files"""
    if Internal.app is None:
        _ = englishIn
    else:
        _ = Internal.app.translate(context, englishIn)
    return __insertArgs(_, *args)

def i18nE(englishText):
    """use this if you want to get the english text right now but still have the string translated"""
    return englishText


def i18ncE(dummyContext, englishText):
    """use this if you want to get the english text right now but still have the string translated"""
    return englishText

def english(i18nstring):
    """translate back from local language"""
    return ENGLISHDICT.get(i18nstring, i18nstring)


class KDETranslator(QTranslator):

    """we also want Qt-only strings translated. Make Qt call this
    translator for its own strings. Use this with qi18nc()"""

    def __init__(self, parent):
        QTranslator.__init__(self, parent)

    def translate(self, context, text, disambiguation, numerus=-1):
        """context should be the class name defined by qt5 or kf5"""
        if Debug.neutral:
            return text
        result = QTranslator.translate(self, context, text, disambiguation, numerus)
        if not result:
            # for kwidgetsaddons5_qt locale de, KStandardGuiItem '&OK' returns an empty string.
            # but this works for other languages like uk, catalan, ptbr and zh_TW.
            # What is different with German? The .po source seems OK, just like the others.
            result = i18n(text)
        return result


class MLocale:
    """xxxx"""

    @classmethod
    def initStatic(cls):
        """init class attributes"""
        if hasattr(cls, 'translation'):
            return

        if os.name == 'nt':
            # on Linux, QCoreApplication initializes locale but not on Windows.
            # This is actually documented for QCoreApplication
            setlocale(LC_ALL, '')

    @classmethod
    def installTranslations(cls, languages):
        """install translations for languages"""  # TODO: auch Qt
        cls.translation = gettext.NullTranslations()
        for language in languages:
            for context in ('kajongg', 'libkmahjongg5', 'kxmlgui5', 'kconfigwidgets5', 'libc'):
                directories = cls.localeDirectories()
                for resourceDir in directories:
                    try:
                        cls.translation.add_fallback(gettext.translation(
                            context, resourceDir, languages=[language]))
                        break
                    except IOError:
                        pass
        cls.translation.install()

    @staticmethod
    def localeDirectories():
        """hard coded paths to i18n directories, all are searched"""
        result = list(x for x in ('share/locale', '/usr/local/share/locale', '/usr/share/locale') if os.path.exists(x))
        if LOCALEPATH and os.path.exists(LOCALEPATH):
            result.insert(0, LOCALEPATH)
        return result


    @staticmethod
    def extendRegionLanguages(languages):
        """for de_DE, return de_DE, de"""
        for lang in languages:
            if lang is not None:
                yield lang
                if '_' in lang:
                    yield lang.split('_')[0]

    @classmethod
    def availableLanguages(cls):
        """see python lib, getdefaultlocale (which only returns the first one)"""
        localenames = [getdefaultlocale()[0]]
        for variable in ('LANGUAGE', 'LC_ALL', 'LC_MESSAGES', 'LANG'):
            try:
                localename = os.environ[variable]
            except KeyError:
                continue
            else:
                if variable == 'LANGUAGE':
                    localenames.extend(localename.split(':'))
                else:
                    localenames.append(localename)
        languages = list(_parse_localename(x)[0]
                         for x in localenames if len(x))
        for resourceDir in cls.localeDirectories():
            for sysLanguage in sorted(os.listdir(resourceDir)):
                if cls.__isLanguageInstalledForKajongg(sysLanguage):
                    languages.append(sysLanguage)
        if languages:
            languages = uniqueList(cls.extendRegionLanguages(languages))
            languages = list(
                x for x in languages if cls.isLanguageInstalled(x))
        if 'en_US' not in languages:
            languages.extend(['en_US', 'en'])
        return ':'.join(languages)

    @classmethod
    def availableLanguages_(cls):
        """like availableLanguages but if xx_yy exists, exclude xx"""
        languages = set(cls.availableLanguages().split(':'))
        for _ in list(languages):
            if '_' in _ and _[:2] in languages:
                languages.remove(_[:2])
        return ':'.join(sorted(languages))

    @classmethod
    def isLanguageInstalled(cls, lang):  # TODO: should be is Available
        """is any translation available for lang?"""
        for directory in cls.localeDirectories():
            if os.path.exists(os.path.join(directory, lang)):
                return True
        return False

    @classmethod
    def __isLanguageInstalledForKajongg(cls, lang):
        """see kdelibs, KCatalog::catalogLocaleDir"""
        for directory in cls.localeDirectories():
            if os.path.exists(os.path.join(directory, lang, 'LC_MESSAGES', 'kajongg.mo')):
                return True
        return False

MLocale.initStatic()
