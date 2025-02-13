# -*- coding: utf-8 -*-

"""
Copyright (C) 2008-2016 Wolfgang Rohdewald <wolfgang@rohdewald.de>

SPDX-License-Identifier: GPL-2.0-only



Here we define replacement classes for the case that we have no
python interface to KDE.

"""


import os
import sys
from locale import setlocale, LC_ALL
from locale import _parse_localename  # type: ignore
from typing import Any, List, Generator, Optional

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

def __insertArgs(translatedTemplate:str, *args:Any) ->str:
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
            result = result.replace(f'%{int(idx + 1)}', '{%d}' % idx)
        result = result.format(*args)
    for ignore in ['numid', 'filename', 'interface']:
        result = result.replace(f'<{ignore}>', '')
        result = result.replace(f'</{ignore}>', '')
    return result


def i18n(englishIn:str, *args:Any) ->str:
    """
    Translate. Since this is a 1:1 replacement for the
    corresponding KDE function, it accepts only C{str}.

    @param englishIn: The english template.
    @type englishIn: C{str}
    @return: The translated text, args included.
    @rtype: C{str}
    """
    if not Debug.neutral and englishIn:
        _ = MLocale.gettext(englishIn)
    else:
        _ = englishIn
    if not args:
        ENGLISHDICT[_] = englishIn
    result = __insertArgs(_, *args)
    return result


def i18nc(context:str, englishIn:str, *args:Any) ->str:
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
    if Debug.neutral:
        return __insertArgs(englishIn, *args)
    withContext = '\004'.join([context, englishIn])
    _ = MLocale.gettext(withContext)
    if _ == withContext:
        # try again without context
        _ = MLocale.gettext(englishIn)
    if not args:
        ENGLISHDICT[_] = englishIn
    return __insertArgs(_, *args)

def qi18nc(context:str, englishIn:str, *args:Any) ->str:
    """This uses the Qt translation files"""
    if Internal.app is None:
        _ = englishIn
    else:
        _ = Internal.app.translate(context.encode(), englishIn.encode())
    return __insertArgs(_, *args)

def i18nE(englishText:str) ->str:
    """use this if you want to get the english text right now but still have the string translated"""
    return englishText


def i18ncE(unusedContext:str, englishText:str) ->str:
    """use this if you want to get the english text right now but still have the string translated"""
    return englishText

def english(i18nstring:str) ->str:
    """translate back from local language"""
    return ENGLISHDICT.get(i18nstring, i18nstring)


class KDETranslator(QTranslator):

    """we also want Qt-only strings translated. Make Qt call this
    translator for its own strings. Use this with qi18nc()"""

    def __init__(self, parent:QObject) ->None:
        super().__init__(parent)

    def translate(self, context:str, text:str,  # type:ignore[override]
        disambiguation:Optional[bytes]=None, numerus:int=-1) ->str:
        """context should be the class name defined by Qt.
        PyQt uses str, Pyside uses bytes - so just ignore typing warnings"""
        # Qt doc says str but on Debian Bookworm, .pyi says bytes
        if Debug.neutral:
            return text  # type:ignore[return-value]
        result = super().translate(context, text, disambiguation, numerus)  # type:ignore[arg-type]
        if result:
            return result  # type:ignore[return-value]
        if not MLocale.currentLanguages():
            # when starting kajongg.py, Qt loads translators for the system default
            # language. I do not know how to avoid that. And I cannot delete
            # translators I do not own. So if we want no translation, just return text.
            # But we still need to install our own QTranslator overriding the ones
            # mentioned above. It will never find a translation, so we come here.
            assert Internal.app.translators == [self]
        return text  # type:ignore[return-value]



class MLocale:
    """xxxx"""

    __cached_availableLanguages = None

    translation:Optional[gettext.NullTranslations]  = None  # pylint:disable=used-before-assignment

    @classmethod
    def gettext(cls, txt:str) ->str:
        """with lazy installation of languages"""
        if cls.translation is None and Internal.kajonggrc:
            cls.installTranslations()
        if cls.translation is None:
            return txt
        return cls.translation.gettext(txt)

    @classmethod
    def installTranslations(cls) ->None:
        """install translations"""
        if sys.platform == 'win32':
            # on Linux, QCoreApplication initializes locale but not on Windows.
            # This is actually documented for QCoreApplication
            setlocale(LC_ALL, '')
        languages = cls.currentLanguages()
        cls.translation = gettext.NullTranslations()
        if Debug.i18n:
            Internal.logger.debug('Trying to install translations for %s', ','.join(languages))
        for language in languages:
            for context in ('kajongg', 'libkmahjongg5', 'kxmlgui5', 'kconfigwidgets5', 'libc'):
                directories = cls.localeDirectories()
                for resourceDir in directories:
                    try:
                        cls.translation.add_fallback(gettext.translation(
                            context, resourceDir, languages=[language]))
                        if Debug.i18n:
                            Internal.logger.debug(
                                'Found %s translation for %s in %s', language, context, resourceDir)
                        break
                    except IOError as _:
                        if Debug.i18n:
                            Internal.logger.debug(str(_))
        cls.translation.install()

    @staticmethod
    def localeDirectories() ->List[str]:
        """hard coded paths to i18n directories, all are searched"""
        candidates = (
            'share/locale', '/usr/local/share/locale', '/usr/share/locale',
            os.path.join(os.path.dirname(sys.argv[0]), 'share/locale'))
        result = [x for x in candidates if os.path.exists(x)]
        if not result and Debug.i18n:
            Internal.logger.debug('no locale path found. We have:%s', os.listdir('.'))

        if LOCALEPATH and os.path.exists(LOCALEPATH):
            result.insert(0, LOCALEPATH)
        return result

    @classmethod
    def currentLanguages(cls) ->List[str]:
        """the currently used languages, primary first"""
        try:
            languages = Internal.kajonggrc.group('Locale').readEntry('Language')
        except AttributeError:
            return []
        if not languages:
            return []
        languages = languages.split(':')
        if 'en_US' in languages:
            languages.remove('en_US')
        return languages

    @staticmethod
    def extendRegionLanguages(languages:List[str]) ->Generator[str, None, None]:
        """for de_DE, return de_DE, de"""
        for lang in languages:
            if lang is not None:
                yield lang
                if '_' in lang:
                    yield lang.split('_')[0]

    @staticmethod
    def get_localenames() ->List[str]:
        """parse environment variables"""
        result = []
        for variable in ('LANGUAGE', 'LC_ALL', 'LC_MESSAGES', 'LANG'):
            try:
                localename = os.environ[variable]
                if localename is None:
                    raise ValueError(f'{variable} is None')
            except KeyError:
                continue
            else:
                if variable == 'LANGUAGE':
                    result.extend(localename.split(':'))
                else:
                    result.append(localename)
        if Debug.i18n:
            Internal.logger.debug('get_localenames: %s', format(','.join(result)))
        return result

    @classmethod
    def availableLanguages(cls) ->str:
        """see python lib, getdefaultlocale (which only returns the first one)"""
        if cls.__cached_availableLanguages:
            return cls.__cached_availableLanguages
        localenames = cls.get_localenames()
        languages = []
        for _ in localenames:
            if _ is None:
                continue
            _ = _parse_localename(_)
            if _[0]:
                languages.append(_[0])
        if Debug.i18n:
            Internal.logger.debug('languages from locale: %s', ','.join(languages) if languages else None)
            Internal.logger.debug('looking for translations in %s', ','.join(cls.localeDirectories()))
        installed_languages = set()
        for resourceDir in cls.localeDirectories():
            installed_languages |= set(os.listdir(resourceDir))
        for sysLanguage in sorted(installed_languages):
            if cls.__isLanguageInstalledForKajongg(sysLanguage):
                languages.append(sysLanguage)

        if languages:
            languages = uniqueList(cls.extendRegionLanguages(languages))
            languages = [x for x in languages if cls.isLanguageInstalled(x)]
        if 'en_US' not in languages:
            languages.extend(['en_US', 'en'])
        if Debug.i18n:
            Internal.logger.debug('languages available: %s', ':'.join(languages) if languages else None)
        cls.__cached_availableLanguages = ':'.join(languages)
        return cls.__cached_availableLanguages

    @classmethod
    def availableLanguages_(cls) ->str:
        """like availableLanguages but if xx_yy exists, exclude xx"""
        languages = set(cls.availableLanguages().split(':'))
        for _ in list(languages):
            if '_' in _ and _[:2] in languages:
                languages.remove(_[:2])
        return ':'.join(sorted(languages))

    @classmethod
    def isLanguageInstalled(cls, lang:str) ->bool:  # TODO: should be is Available
        """is any translation available for lang?"""
        if lang == 'en_US':
            return True
        for directory in cls.localeDirectories():
            if os.path.exists(os.path.join(directory, lang)):
                return True
        return False

    @classmethod
    def __isLanguageInstalledForKajongg(cls, lang:str) ->bool:
        """see kdelibs, KCatalog::catalogLocaleDir"""
        for directory in cls.localeDirectories():
            _ = os.path.join(directory, lang, 'LC_MESSAGES', 'kajongg.mo')
            if os.path.exists(_):
                if Debug.i18n:
                    Internal.logger.debug('language %s installed in %s', lang, _)
                return True
        return False
