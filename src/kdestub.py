# -*- coding: utf-8 -*-

"""
Copyright (C) 2008-2014 Wolfgang Rohdewald <wolfgang@rohdewald.de>

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

__all__ = ['KAboutData', 'KApplication', 'KCmdLineArgs', 'KConfig',
            'KCmdLineOptions', 'i18n', 'i18nc', 'ki18n',
            'KMessageBox', 'KConfigSkeleton', 'KDialogButtonBox',
            'KConfigDialog', 'KDialog', 'KLineEdit',
            'KUser', 'KToggleFullScreenAction', 'KStandardAction',
            'KXmlGuiWindow', 'KStandardDirs', 'KGlobal', 'KIcon', 'KAction']

import sys, os, subprocess, getpass, pwd, webbrowser
import weakref
from collections import defaultdict

try:
    from ConfigParser import SafeConfigParser, NoSectionError, NoOptionError
except ImportError:
    # gone with python3.4
    # pylint: disable=import-error
    from configparser import SafeConfigParser, NoSectionError, NoOptionError

from locale import _parse_localename, getdefaultlocale

# here come the replacements:

# pylint: disable=wildcard-import,unused-wildcard-import
from qt import *

from common import Internal, Debug
from util import xToUtf8, uniqueList

import gettext

def insertArgs(englishIn, *args):
    """format the string"""
    if '@' in englishIn:
        print('insertargs:', englishIn)

    if '\004' in englishIn:
        englishIn = englishIn.split('\004')[1]
    result = englishIn
    if '%' in result:
        for idx in range(len(args)):
            result = result.replace('%%%d' % (idx+1), '{%d}' % idx)
        args = list(x.decode('utf-8') for x in args)
        result = result.format(*args)
    for ignore in ['numid', 'filename']:
        result = result.replace('<%s>' % ignore, '')
        result = result.replace('</%s>' % ignore, '')
    return result

def i18n(englishIn, *args):
    """stub"""
    englishIn, args = xToUtf8(englishIn, args)
    if KGlobal.translation:
        _ = KGlobal.translation.gettext(englishIn).decode('utf-8')
    else:
        _ = englishIn
    return insertArgs(_, *args)

ki18n = i18n # pylint: disable=invalid-name

def i18nc(context, englishIn, *args):
    """The \004 trick is taken from kdecore/localization/gettext.h,
    definition of pgettext_aux"""
    withContext = '\004'.join([context, englishIn])
    if KGlobal.translation:
        _ = KGlobal.translation.gettext(withContext).decode('utf-8')
    else:
        _ = withContext
    if '\004' in _:
        # found no translation with context
        result = i18n(englishIn, *args)
    else:
        result = i18n(withContext, *args)
    return result

class OptionHelper(object):
    """stub"""
    def __init__(self, options):
        self.options = options

    def isSet(self, option):
        """did the user specify this option?"""
        if any(x[0].startswith('no%s' % option) for x in self.options):
            return not any(x.startswith('--no%s' % option) for x in sys.argv)
        else:
            return any(x.startswith('--%s' % option) for x in sys.argv)

    @staticmethod
    def getOption(option):
        """try to mimic KDE logic as far as we need it"""
        for arg in sys.argv:
            if arg.startswith('--%s' % option):
                parts = arg.split('=')
                if len(parts) > 1:
                    return parts[1]
                else:
                    return True
            if arg.startswith('--no%s' % option):
                parts = arg.split('=')
                if len(parts) > 1:
                    return parts[1]
                else:
                    return False
        return ''

class KCmdLineArgs(object):
    """stub"""
    options = None
    argv = None
    about = None

    @classmethod
    def parsedArgs(cls):
        """stub"""
        return cls.options

    @classmethod
    def init(cls, argv, about):
        """stub"""
        cls.argv = argv
        cls.about = about

    @classmethod
    def addCmdLineOptions(cls, options):
        """stub"""
        cls.options = OptionHelper(options)

class KCmdLineOptions(list):
    """stub"""
    def __init__(self):
        list.__init__(self)

    def add(self, definition, helptext, default=None):
        """stub"""
        self.append((definition, helptext, default))

class KAboutData(object):
    """stub"""
    License_GPL = 1

    def __init__(self, appname, catalog, programName, version, description,
        kajLicense, kajCopyright, aboutText, homePage):
        # pylint: disable=too-many-arguments
        KGlobal.aboutData = self
        self.appname = appname
        self.catalog = catalog
        self.programName = programName
        self.version = version
        self.description = description
        self.kajLicense = kajLicense
        self.kajCopyright = kajCopyright
        self.aboutText = aboutText
        self.homePage = homePage
        self._authors = []

    def addAuthor(self, name, description, mailAdress):
        """authors to be shown on about page"""
        self._authors.append((name, description, mailAdress))

    def authors(self):
        """stub"""
        return self._authors

    @staticmethod
    def licenseFile():
        """which may currently only be 1: GPL_V2"""
        for path in ('COPYING', '../COPYING',
            '%s/share/kde4/apps/LICENSES/GPL_V2' % KStandardDirs.prefix()):
            path = os.path.abspath(path)
            if os.path.exists(path):
                return path

class KApplication(QApplication):
    """stub"""
    def __init__(self):
        QApplication.__init__(self, sys.argv)
        KLocale.initQtTranslator(self)

    @staticmethod
    def kApplication():
        """the global app instance"""
        return QApplication.instance()

class CaptionMixin(object):
    """used by KDialog and KXmlGuiWindow"""
    def setCaption(self, caption):
        """append app name"""
        if caption:
            if not caption.endswith(i18n('Kajongg')):
                caption += u' – {}'.format(i18n('Kajongg'))
        else:
            caption = i18n('Kajongg')
        self.setWindowTitle(caption)

def getDocUrl(languages):
    """returns the best match for the online user manual"""
    from twisted.web import client
    def processResult(dummyResult, fallbacks):
        """if status 404, try the next fallback language"""
        return getDocUrl(fallbacks) if factory.status == '404' else url
    host = 'docs.kde.org'
    path = '/stable/{}/kdegames/kajongg/index.html'.format(languages[0])
    url = 'http://' + host + path
    factory = client.HTTPClientFactory(url)
    factory.protocol = client.HTTPPageGetter
    factory.protocol.handleEndHeaders = lambda x: x
    Internal.reactor.connectTCP(host, 80, factory)
    factory.deferred.addCallback(processResult, languages[1:])
    return factory.deferred

def startHelp():
    """start the KDE help center for kajongg or go to docs.kde.org"""
    try:
        subprocess.Popen(['khelpcenter', 'help:/kajongg/index.html'])
    except OSError:
        def gotUrl(url):
            """now we know where the manual is"""
            webbrowser.open(url)
        languages = KGlobal.config().group('Locale').readEntry('Language').split(':')
        getDocUrl(languages).addCallback(gotUrl)

class IconLabel(QLabel):
    """for use in messages and about dialog"""
    def __init__(self, iconName, dialog):
        QLabel.__init__(self)
        icon = KIcon(iconName)
        option = QStyleOption()
        option.initFrom(dialog)
        self.setPixmap(icon.pixmap(dialog.style().pixelMetric(
            QStyle.PM_MessageBoxIconSize, option, dialog)))

class KMessageBox(object):
    """again only what we need"""
    NoExec = 1
    @staticmethod
    def createKMessageBox(dialog, icon, text, dummyStrlist, dummyAsk, dummyCheckboxReturn, dummyOptions):
        """translated as far as needed from kmessagegox.cpp"""
        # pylint: disable=too-many-locals
        mainLayout = QVBoxLayout()

        hLayout = QHBoxLayout()
        hLayout.setContentsMargins(0, 0, 0, 0)
        hLayout.setSpacing(-1)
        mainLayout.addLayout(hLayout, 5)

        iconName = {
            QMessageBox.Information: 'dialog-information',
            QMessageBox.Warning: 'dialog-warning',
            QMessageBox.Question: 'dialog-information'}[icon]
        icon = KIcon(iconName)
        iconLayout = QVBoxLayout()
        iconLayout.addStretch(1)
        iconLayout.addWidget(IconLabel(iconName, dialog))
        iconLayout.addStretch(5)
        hLayout.addLayout(iconLayout, 0)

        messageLabel = QLabel(text)
        messageLabel.setTextInteractionFlags(
            Qt.TextSelectableByMouse | Qt.TextSelectableByKeyboard)

        desktop = KApplication.kApplication().desktop().availableGeometry()
        if messageLabel.sizeHint().width() > desktop.width() * 0.5:
            messageLabel.setWordWrap(True)

        usingScrollArea = desktop.height() // 3 < messageLabel.sizeHint().height()
        if usingScrollArea:
            scrollArea = QScrollArea(dialog)
            scrollArea.setWidget(messageLabel)
            scrollArea.setWidgetResizable(True)
            scrollArea.setFocusPolicy(Qt.NoFocus)
            scrollPal = QPalette(scrollArea.palette())
            scrollArea.viewport().setPalette(scrollPal)
            hLayout.addWidget(scrollArea, 5)
        else:
            hLayout.addWidget(messageLabel, 5)

        mainLayout.addWidget(dialog.buttonBox)
        dialog.setLayout(mainLayout)

KDialogButtonBox = QDialogButtonBox # pylint: disable=invalid-name

class KDialog(CaptionMixin, QDialog):
    """QDialog should be enough for kajongg"""
    Ok = QDialogButtonBox.Ok
    Cancel = QDialogButtonBox.Cancel
    Yes = QDialogButtonBox.Yes
    No = QDialogButtonBox.No
    Help = QDialogButtonBox.Help
    Apply = QDialogButtonBox.Apply
    RestoreDefaults = QDialogButtonBox.RestoreDefaults
    Close = QDialogButtonBox.Close

    def __init__(self, parent=None, flags=None):
        if flags is None:
            flags = Qt.WindowFlags(0)
        QDialog.__init__(self, parent, flags)
        self.buttonBox = QDialogButtonBox()
        self.buttonBox.accepted.connect(self.accept)
        self.buttonBox.rejected.connect(self.reject)
        self.__mainWidget = None

    def setButtons(self, buttonMask):
        """(re)create the buttonbox and put all wanted buttons into it"""
        self.buttonBox.setStandardButtons(buttonMask)
        if KDialog.Apply & buttonMask:
            self.buttonBox.button(KDialog.Apply).setText(i18n('&Apply'))
        if KDialog.Cancel & buttonMask:
            self.buttonBox.button(KDialog.Cancel).setText(i18n('&Cancel'))
        if KDialog.RestoreDefaults & buttonMask:
            self.buttonBox.button(KDialog.RestoreDefaults).setText(i18n('&Defaults'))
        if KDialog.Help & buttonMask:
            self.buttonBox.button(KDialog.Help).clicked.connect(startHelp)

    def setMainWidget(self, widget):
        """see KDialog.setMainWidget"""
        if self.layout() is None:
            QVBoxLayout(self)
            self.layout().addWidget(self.buttonBox)
        if self.__mainWidget:
            self.layout().removeWidget(self.__mainWidget)
            self.layout().removeWidget(self.buttonBox)
        self.__mainWidget = widget
        self.layout().addWidget(widget)
        self.layout().addWidget(self.buttonBox)

    def button(self, buttonCode):
        """returns the matching button"""
        return self.buttonBox.button(buttonCode)

    @staticmethod
    def ButtonCode(value): # pylint: disable=invalid-name
        """not needed in Python"""
        return value

    @staticmethod
    def spacingHint():
        """stub"""
        return QApplication.style().pixelMetric(QStyle.PM_DefaultLayoutSpacing)

    @staticmethod
    def marginHint():
        """stub"""
        return QApplication.style().pixelMetric(QStyle.PM_DefaultChildMargin)

class KUser(object):
    """only the things kajongg needs"""
    def __init__(self, uid):
        self.__uid = uid
    def fullName(self):
        """stub"""
        if os.name == 'nt':
            return self.loginName()
        else:
            return pwd.getpwnam(self.loginName()).pw_gecos.replace(',', '')
        return None
    @staticmethod
    def loginName():
        """stub"""
        return getpass.getuser()

class KToggleFullScreenAction(QAction):
    """stub"""
    def __init__(self, *dummyArgs):
        QAction.__init__(self, Internal.mainWindow)

    def setWindow(self, window):
        """stub"""

class KStandardAction(object):
    """stub"""
    @classmethod
    def preferences(cls, slot, actionCollection):
        """should add config dialog menu entry"""
        action = KAction(Internal.mainWindow)
        action.triggered.connect(slot)
        action.setText(i18n('Configure Kajongg'))
        action.setIcon(KIcon('configure'))
        action.setIconText(i18n('Configure'))
        separator = QAction(Internal.mainWindow)
        separator.setSeparator(True)
        actionCollection.addAction('options_configure', separator)
        actionCollection.addAction('options_configure', action)

class ActionCollection(object):
    """stub"""
    def __init__(self, mainWindow):
        self._collections = {}
        self.mainWindow = mainWindow

    def addAction(self, name, action):
        """stub"""
        self._collections[name] = action
        for content in self.mainWindow.menus.values():
            if name in content[1]:
                content[0].addAction(action)

class MyStatusBar(object):
    """/dev/null. KStatusBar has those things, QStatusBar does not.
    So for now just live without status bar"""
    def hasItem(self, *dummyArgs): # pylint:disable=no-self-use
        """stub"""
        return False
    def changeItem(self, *args):
        """stub"""
    def insertItem(self, *args):
        """stub"""
    def removeItem(self, *args):
        """stub"""
    def setItemAlignment(self, *args):
        """stub"""

class KXmlGuiWindow(CaptionMixin, QMainWindow):
    """stub"""
    def __init__(self):
        QMainWindow.__init__(self)
        self._actions = ActionCollection(self)
        self._toolBar = QToolBar(self)
        self._statusBar = MyStatusBar()
        self.menus = {}
        for menu in (
            (i18n('&Game'), ('scoreGame', 'play', 'abort', 'quit')),
            (i18n('&View'), ('scoreTable', 'explain')),
            (i18n('&Settings'), ('players', 'rulesets', 'demoMode', '', 'options_configure')),
            (i18n('&Help'), ('help', 'aboutkajongg', 'aboutkde'))):
            self.menus[menu[0]] = (QMenu(menu[0]), menu[1])
            self.menuBar().addMenu(self.menus[menu[0]][0])
        self.setCaption('')
        self.actionHelp = self._kajonggAction("help", "help-contents", startHelp)
        self.actionHelp.setText(i18nc('@action:inmenu', 'Help'))
        self.actionAboutKajongg = self._kajonggAction('aboutkajongg', 'kajongg', self.aboutKajongg)
        self.actionAboutKajongg.setText(i18nc('@action:inmenu', 'About Kajongg'))
        self.setWindowIcon(KIcon('kajongg'))

    def actionCollection(self):
        """stub"""
        return self._actions
    def setupGUI(self):
        """stub"""
        self.applySettings()

    def toolBar(self):
        """stub"""
        return self._toolBar

    def statusBar(self):
        """stub"""
        return self._statusBar

    def _kajonggAction(self, name, icon, slot=None, shortcut=None, actionData=None):
        """this is defined in MainWindow(KXmlGuiWindow)"""

    @staticmethod
    def aboutKajongg():
        """show an about dialog"""
        AboutKajonggDialog(Internal.mainWindow).exec_()

class KStandardDirs(object):
    """as far as we need it. """
    _localBaseDirs = None
    _baseDirs = None
    _prefix = None
    Recursive = 1

    def __init__(self):
        if KStandardDirs._baseDirs is None:
            KStandardDirs._localBaseDirs = defaultdict(str)
            KStandardDirs._localBaseDirs.update({
                'cache': '/var/tmp/kdecache-wr',
                'data': 'share/apps',
                'config': 'share/config',
                'appdata': 'share/apps/kajongg',
                })
            home = os.environ.get('KDEHOME', '~/.kde')
            for key, value in KStandardDirs._localBaseDirs.items():
                KStandardDirs._localBaseDirs[key] = os.path.expanduser(home + '/' + value)
            KStandardDirs._baseDirs = defaultdict(list)
            KStandardDirs._baseDirs.update({
                'data': ['share/kde4/apps'],
                'locale': ['share/locale'],
                'appdata': ['share/kde4/apps/kajongg'],
                'icon': ['share/icons'],
                })
            KStandardDirs._prefix = subprocess.Popen(['which', 'kde4-config'],
                stdout=subprocess.PIPE).communicate()[0].split('/')[1]
            KStandardDirs._prefix = '/%s/' % KStandardDirs._prefix

    @classmethod
    def kde_default(cls, type_):
        """the default relative paths for standard resource types"""

    @classmethod
    def __tryPath(cls, *args):
        """try this path. Returns result and full actual path"""
        if args[0] == '':
            # happens because we use a defaultdict(str) for localBaseDirs
            return False, None
        tryThis = os.path.join(*args)
        exists = os.path.exists(tryThis)
        if Debug.locate:
            if exists:
                print('found: %s' % tryThis)
            else:
                print('not found: %s' % tryThis)
        return exists, tryThis

    @classmethod
    def locate(cls, type_, filename):
        """see KStandardDirs doc"""
        type_ = str(type_)
        filename = str(filename)
        found, path = cls.__tryPath(cls._localBaseDirs[type_], filename)
        if found:
            return path
        for baseDir in cls._baseDirs[type_]:
            found, path = cls.__tryPath(cls._prefix, baseDir, filename)
            if found:
                return path

    @classmethod
    def locateLocal(cls, type_, filename):
        """see KStandardDirs doc"""
        type_ = str(type_)
        filename = str(filename)
        fullPath = os.path.join(cls._localBaseDirs[type_], filename)
        if not os.path.exists(os.path.dirname(fullPath)):
            if Debug.locate:
                print('locateLocal creates missing dir %s', fullPath)
            os.makedirs(os.path.dirname(fullPath))
        if Debug.locate:
            print('locateLocal(%s, %s) returns %s' % (
                type_, filename, fullPath))
        return fullPath

    @classmethod
    def addResourceType(cls, type_, basetype, relativename):
        """see KStandardDirs doc"""
        type_ = str(type_)
        basetype = str(basetype)
        relativename = str(relativename)
        for baseDir in cls._baseDirs[basetype]:
            cls._baseDirs[str(type_)].append(os.path.join(baseDir, relativename))

    @classmethod
    def prefix(cls):
        """returns the big prefix like usr or usr/local
            KDEDIRS KDEHOME KDEROOTHOME"""
        return cls._prefix

    @classmethod
    def resourceDirs(cls, type_):
        """see KStandardDirs doc"""
        type_ = str(type_)
        result = [cls._localBaseDirs[type_]]
        result.extend(cls._baseDirs[type_])
        return list(x for x in result if x is not None)

    @classmethod
    def findDirs(cls, type_, reldir):
        """Tries to find all directories whose names consist of the specified type and a relative path"""
        result = []
        type_ = str(type_)
        reldir = str(reldir)
        found, path = cls.__tryPath(cls._localBaseDirs[type_], reldir)
        if found:
            result.append(path)
        for baseDir in cls._baseDirs[type_]:
            found, path = cls.__tryPath(cls._prefix, baseDir, reldir)
            if found:
                result.append(path)
        return result

    @classmethod
    def findAllResources(cls, type_, filter_, dummyRecursive):
        """Return all resources with the specified type. Recursion is not implemented."""
        dirs = cls.findDirs(type_, '')
        type_ = str(type_)
        filter_ = str(filter_)
        assert filter_ == '*.desktop' # nothing else we need
        result = []
        for directory in dirs:
            result.extend(x for x in os.listdir(directory) if x.endswith('.desktop'))
        return result

    @classmethod
    def findResourceDir(cls, type_, filename):
        """tries to find the directory the file is in"""
        result = cls.findDirs(type_, filename)
        if Debug.locate:
            print('findResourceDir(%s,%s) finds %s' % (type_, filename, result))
        return result

class KDETranslator(QTranslator):
    """we also want Qt-only strings translated. Make Qt call this
    translator for its own strings"""
    def __init__(self, parent):
        QTranslator.__init__(self, parent)

    @staticmethod
    def translate(dummyContext, sourceText, dummyMessage, dummyNumber=-1):
        """for now this seems to translate all we need, otherwise
        search for translateQt in kdelibs/kdecore/localization"""
        return i18n(sourceText)

    @staticmethod
    def isEmpty():
        """stub"""
        return False

class KLocale(object):
    """as far as we need it"""
    @staticmethod
    def insertCatalog(dummy):
        """to be done for translation, I suppose"""

    @staticmethod
    def initQtTranslator(app):
        """stub"""
        QCoreApplication.installTranslator(KDETranslator(app))

class KConfigGroup(object):
    """mimic KConfigGroup as far as we need it"""
    def __init__(self, config, groupName):
        self.config = weakref.ref(config)
        self.groupName = groupName

    def __default(self, name):
        """defer computation of Languages until really needed"""
        if self.groupName == 'Locale' and name == 'Language':
            return QString(self.__availableLanguages())

    def readEntry(self, name, default=None):
        """get an entry from this group.
        If default is passed, the original returns QVariant, else QString.
        To make things easier, we never accept a default and
        always return QString"""
        assert default is None
        try:
            items = self.config().items(self.groupName)
        except NoSectionError:
            return self.__default(name)
        items = dict((x for x in items if x[0].startswith(name)))
        i18nItems = dict(((x[0], x[1].decode('utf-8')) for x in items.items() if x[0].startswith(name + '[')))
        if i18nItems:
            for language in KGlobal.config().group('Locale').readEntry('Language').split(':'):
                key = '%s[%s]' % (name, language)
                if key in i18nItems:
                    return QString(i18nItems[key])
        if name in items:
            if self.groupName == 'Locale' and name == 'Language':
                languages = list(x for x in items[name].split(':') if self.__isLanguageInstalled(x))
                if languages:
                    return QString(':'.join(languages))
                else:
                    return QString(self.__availableLanguages())
            return QString(items[name])
        return self.__default(name)

    @classmethod
    def __extendRegionLanguages(cls, languages):
        """for de_DE, return de_DE, de"""
        for lang in languages:
            if lang is not None:
                yield lang
                if '_' in lang:
                    yield lang.split('_')[0]

    @classmethod
    def __availableLanguages(cls):
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
        languages = list(_parse_localename(x)[0] for x in localenames if len(x))
        if languages:
            languages = uniqueList(cls.__extendRegionLanguages(languages))
            languages = list(x for x in languages if cls.__isLanguageInstalled(x))
        if 'en_US' not in languages:
            languages.extend(['en_US', 'en'])
        return ':'.join(languages)

    @classmethod
    def __isLanguageInstalled(cls, lang):
        """is any translation available for lang?"""
        return bool(KGlobal.dirs().findDirs('locale', lang))

    @classmethod
    def __isLanguageInstalledForKajongg(cls, lang):
        """see kdelibs, KCatalog::catalogLocaleDir"""
        relpath = '{lang}/LC_MESSAGES/kajongg.mo'.format(lang=lang)
        return bool(KGlobal.dirs().findResourceDir("locale", relpath))

class KGlobal(object):
    """stub"""

    @classmethod
    def initStatic(cls):
        """init class members"""
        cls.dirInstance = KStandardDirs()
        cls.localeInstance = KLocale()
        cls.configInstance = KConfig()
        languages = str(cls.configInstance.group('Locale').readEntry('Language'))
        if languages:
            languages = languages.split(':')
        else:
            languages = None
        resourceDirs = KGlobal.dirs().findResourceDir('locale', '')
        cls.translation = gettext.NullTranslations()
        if languages:
            for resourceDir in resourceDirs:
                for context in ('kajongg', 'libkmahjongg', 'kdelibs4', 'libphonon', 'kio4', 'kdeqt', 'libc'):
                    try:
                        cls.translation.add_fallback(gettext.translation(context, resourceDir, languages=languages))
                    except IOError:
                        # no translation for language/domain available
                        pass
        cls.translation.install()

    @classmethod
    def dirs(cls):
        """stub"""
        return cls.dirInstance

    @classmethod
    def locale(cls):
        """stub"""
        return cls.localeInstance

    @classmethod
    def config(cls):
        """stub"""
        return cls.configInstance

class KConfig(SafeConfigParser):
    """Parse KDE config files.
    This mimics KDE KConfig but can also be used like any SafeConfigParser but
    without support for a default section.
    We Override write() with a variant which does not put spaces
    around the '=' delimiter. This is configurable in Python3.3,
    so after kajongg is ported to Python3, this can be removed"""

    SimpleConfig = 1

    def __init__(self, path=None, dummyVariant=None):
        SafeConfigParser.__init__(self)
        if path is None:
            path = KGlobal.dirs().locateLocal("config", "kajonggrc")
        self.path = str(path)
        self.read(self.path)

    def as_dict(self):
        """a dict of dicts"""
        result = dict(self._sections)
        for key in result:
            result[key] = dict(self._defaults, **result[key])
            result[key].pop('__name__', None)
        return result

    def optionxform(self, value):
        """KDE needs upper/lowercase distinction"""
        return value

    def setValue(self, section, option, value):
        """like set but add missing section"""
        if section not in self._sections:
            self.add_section(section)
        self.set(section, option, str(value))

    def writeToFile(self, fileName=None):
        """Write an .ini-format representation of the configuration state."""
        if fileName is None:
            fileName = self.path
        with open(fileName, 'wb') as filePointer:
            for section in self._sections:
                filePointer.write("[%s]\n" % section)
                for (key, value) in self._sections[section].items():
                    key = str(key)
                    value = str(value)
                    if key == "__name__":
                        continue
                    if value is not None:
                        key = "=".join((key, value.replace('\n', '\n\t')))
                    filePointer.write('%s\n' % (key))
                filePointer.write('\n')

    def group(self, groupName):
        """just like KConfig"""
        return KConfigGroup(self, groupName)

class KIcon(QIcon):
    """stub"""
    initDone = False
    def __init__(self, name=None):
        if name is None:
            QIcon.__init__(self)
            return
        dirs = KGlobal.dirs()
        if not KIcon.initDone:
            KIcon.initDone = True
            dirs.addResourceType('appicon', 'data', 'kajongg/pics/')
            dirs.addResourceType('appicon', 'icon', 'oxygen/48x48/actions/')
            dirs.addResourceType('appicon', 'icon', 'oxygen/48x48/categories/')
            dirs.addResourceType('appicon', 'icon', 'oxygen/48x48/status/')
            dirs.addResourceType('appicon', 'icon', 'hicolor/scalable/apps/')
            dirs.addResourceType('appicon', 'icon', 'hicolor/scalable/actions/')
        for suffix in ('png', 'svgz', 'svg', 'xpm'):
            result = dirs.locate('appicon', '.'.join([name, suffix]))
            if result:
                name = result
                break
        QIcon.__init__(self, name)

class KAction(QAction):
    """stub"""
    def __init__(self, *args, **kwargs):
        QAction.__init__(self, *args, **kwargs)
        self.__helpText = None

    def setHelpText(self, text):
        """stub"""
        self.__helpText = text

class KConfigSkeletonItem(object):
    """one preferences setting used by KOnfigSkeleton"""
    def __init__(self, skeleton, key, value, default=None):
        assert skeleton
        self.skeleton = skeleton
        self.group = skeleton.currentGroup
        self.key = key
        self._value = value
        if value is None:
            self._value = default
        self.default = default

    def value(self):
        """default getter"""
        return self._value

    def pythonValue(self):
        """default getter"""
        return self._value

    def setValue(self, value):
        """default setter"""
        self._value = value

    def setPythonValue(self, value):
        """default setter"""
        self._value = value

    def getFromConfig(self):
        """if not there, use default"""
        try:
            self._value = self.skeleton.config.get(self.group, self.key)
        except (NoSectionError, NoOptionError):
            self._value = self.default

class ItemBool(KConfigSkeletonItem):
    """boolean preferences setting used by KOnfigSkeleton"""
    def __init__(self, skeleton, key, value, default=None):
        KConfigSkeletonItem.__init__(self, skeleton, key, value, default)

    def getFromConfig(self):
        """if not there, use default"""
        try:
            self._value = self.skeleton.config.getboolean(self.group, self.key)
        except (NoSectionError, NoOptionError):
            self._value = self.default

class ItemString(KConfigSkeletonItem):
    """string preferences setting used by KOnfigSkeleton"""
    def __init__(self, skeleton, key, value, default=None):
        if value == '':
            value = default
        KConfigSkeletonItem.__init__(self, skeleton, key, value, default)

    def pythonValue(self):
        return str(self._value)

    def setPythonValue(self, value):
        self._value = QString(value)

class ItemInt(KConfigSkeletonItem):
    """integer preferences setting used by KOnfigSkeleton"""
    def __init__(self, skeleton, key, value, default=0):
        KConfigSkeletonItem.__init__(self, skeleton, key, value, default)
        self.minValue = -99999
        self.maxValue = 99999999

    def getFromConfig(self):
        """if not there, use default"""
        try:
            self._value = self.skeleton.config.getint(self.group, self.key)
        except (NoSectionError, NoOptionError):
            self._value = self.default

    def setMinValue(self, value):
        """minimum value for this setting"""
        self.minValue = value

    def setMaxValue(self, value):
        """maximum value for this setting"""
        self.maxValue = value

class KConfigSkeleton(object):
    """handles preferences settings"""
    def __init__(self):
        self.currentGroup = None
        self.items = []
        self.config = KConfig()

    def readConfig(self):
        """init already read config"""
        for item in self.items:
            item.getFromConfig()

    def writeConfig(self):
        """to the same file name"""
        for item in self.items:
            self.config.setValue(item.group, item.key, item.pythonValue())
        self.config.writeToFile()

    def as_dict(self):
        """a dict of dicts"""
        result = defaultdict(dict)
        for item in self.items:
            result[str(item.group)][str(item.key)] = item.pythonValue()
        return result

    def setCurrentGroup(self, group):
        """to be used by following add* calls"""
        self.currentGroup = group

    def addItemString(self, key, value, default=None):
        """add a string preference"""
        result = ItemString(self, key, value, default)
        result.getFromConfig()
        self.items.append(result)
        return result

    def addItemBool(self, key, value, default=False):
        """add a boolean preference"""
        result = ItemBool(self, key, value, default)
        result.getFromConfig()
        self.items.append(result)
        return result

    def addItemInt(self, key, value, default=0):
        """add an integer preference"""
        result = ItemInt(self, key, value, default)
        result.getFromConfig()
        self.items.append(result)
        return result

class AboutKajonggDialog(KDialog):
    """about kajongg dialog"""
    def __init__(self, parent):
        # pylint: disable=too-many-locals, too-many-statements
        KDialog.__init__(self, parent)
        self.setCaption(i18n('About Kajongg'))
        self.setButtons(KDialog.Close)
        vLayout = QVBoxLayout()
        hLayout1 = QHBoxLayout()
        hLayout1.addWidget(IconLabel('kajongg', self))
        h1vLayout = QVBoxLayout()
        h1vLayout.addWidget(QLabel('Kajongg'))
        h1vLayout.addWidget(QLabel(i18n('Version %1', Internal.version)))
        underVersions = []
        try:
            versions = subprocess.Popen(['kde4-config', '-v'],
                stdout=subprocess.PIPE).communicate()[0]
            versions = versions.split('\n')
            versions = (x.strip() for x in versions if ': ' in x.strip())
            versions = dict(x.split(': ') for x in versions)
            underVersions.append('KDE %s' % versions['KDE'])
        except OSError:
            underVersions.append(i18n('KDE (not installed)'))
        underVersions.append('Qt %s' % QT_VERSION_STR)
        underVersions.append('PyQt %s' % PYQT_VERSION_STR)
        h1vLayout.addWidget(QLabel(i18nc('running under version', 'Under %s' % ', '.join(underVersions))))
        h1vLayout.addWidget(QLabel(i18n('Not using Python KDE bindings')))
        hLayout1.addLayout(h1vLayout)
        spacerItem = QSpacerItem(20, 20, QSizePolicy.Expanding, QSizePolicy.Expanding)
        hLayout1.addItem(spacerItem)
        vLayout.addLayout(hLayout1)
        tabWidget = QTabWidget()

        data = KGlobal.aboutData

        aboutWidget = QWidget()
        aboutLayout = QVBoxLayout()
        aboutLabel = QLabel()
        aboutLabel.setWordWrap(True)
        aboutLabel.setOpenExternalLinks(True)
        aboutLabel.setText('<br /><br />'.join([data.description, data.aboutText,
            data.kajCopyright,
            '<a href="{link}">{link}</a>'.format(link=data.homePage)]))
        licenseLabel = QLabel()
        licenseLabel.setText(
            '<a href="file://{link}">GNU General Public License Version 2</a>'.format(
            link=data.licenseFile()))
        licenseLabel.linkActivated.connect(self.showLicense)
        aboutLayout.addWidget(aboutLabel)
        aboutLayout.addWidget(licenseLabel)
        aboutWidget.setLayout(aboutLayout)
        tabWidget.addTab(aboutWidget, '&About')

        authorWidget = QWidget()
        authorLayout = QVBoxLayout()
        bugsLabel = QLabel(i18n('Please use <a href="http://bugs.kde.org">http://bugs.kde.org</a> to report bugs.'))
        bugsLabel.setContentsMargins(0, 2, 0, 4)
        bugsLabel.setOpenExternalLinks(True)
        authorLayout.addWidget(bugsLabel)

        titleLabel = QLabel(i18n('Authors:'))
        authorLayout.addWidget(titleLabel)

        for name, description, mail in data.authors():
            label = QLabel(u'{name} <a href="mailto:{mail}">{mail}</a>: {description}'.format(
                name=name, mail=mail, description=description))
            label.setOpenExternalLinks(True)
            authorLayout.addWidget(label)
        spacerItem = QSpacerItem(20, 20, QSizePolicy.Expanding, QSizePolicy.Expanding)
        authorLayout.addItem(spacerItem)
        authorWidget.setLayout(authorLayout)
        tabWidget.addTab(authorWidget, 'A&uthor')
        vLayout.addWidget(tabWidget)

        vLayout.addWidget(self.buttonBox)
        self.setLayout(vLayout)
        self.buttonBox.setFocus()

    @staticmethod
    def showLicense():
        """as the name says"""
        LicenseDialog(Internal.mainWindow).exec_()

class LicenseDialog(KDialog):
    """see kaboutapplicationdialog.cpp"""
    def __init__(self, parent):
        KDialog.__init__(self, parent)
        self.setAttribute(Qt.WA_DeleteOnClose)
        self.setCaption(i18n("License Agreement"))
        self.setButtons(KDialog.Close)
        self.buttonBox.setFocus()
        licenseText = open(KGlobal.aboutData.licenseFile()).read()
        self.licenseBrowser = QTextBrowser()
        self.licenseBrowser.setLineWrapMode(QTextEdit.NoWrap)
        self.licenseBrowser.setText(licenseText)

        vLayout = QVBoxLayout()
        vLayout.addWidget(self.licenseBrowser)
        vLayout.addWidget(self.buttonBox)
        self.setLayout(vLayout)

    def sizeHint(self):
        """try to set up the dialog such that the full width of the
        document is visible without horizontal scroll-bars being required"""
        idealWidth = self.licenseBrowser.document().idealWidth() + (2 * self.marginHint()) \
            + self.licenseBrowser.verticalScrollBar().width() * 2 + 1
        # try to allow enough height for a reasonable number of lines to be shown
        metrics = QFontMetrics(self.licenseBrowser.font())
        idealHeight = metrics.height() * 30
        return KDialog.sizeHint(self).expandedTo(QSize(idealWidth, idealHeight))

class KConfigDialog(KDialog):
    """for the game preferences"""
    settingsChanged = pyqtSignal()
    dialog = None
    getFunc = {
            'QCheckBox': 'isChecked',
            'QSlider': 'value',
            'QLineEdit': 'text'}
    setFunc = {
            'QCheckBox': 'setChecked',
            'QSlider': 'setValue',
            'QLineEdit': 'setText'}

    def __init__(self, parent, name, preferences):
        KDialog.__init__(self, parent)
        self.setCaption(i18n('Configure'))
        self.name = name
        self.preferences = preferences
        self.orgPref = None
        self.configWidgets = {}
        self.iconList = QListWidget()
        self.iconList.setViewMode(QListWidget.IconMode)
        self.iconList.setFlow(QListWidget.TopToBottom)
        self.iconList.setUniformItemSizes(True)
        self.iconList.itemClicked.connect(self.iconClicked)
        self.iconList.currentItemChanged.connect(self.iconClicked)
        self.tabSpace = QStackedWidget()
        self.tabSpace.setVisible(True)
        self.setButtons(KDialog.Help | KDialog.Ok | KDialog.Apply | KDialog.Cancel | KDialog.RestoreDefaults)
        self.buttonBox.button(KDialog.Apply).clicked.connect(self.applySettings)
        cmdLayout = QHBoxLayout()
        cmdLayout.addWidget(self.buttonBox)
        self.contentLayout = QHBoxLayout()
        self.contentLayout.addWidget(self.iconList)
        self.contentLayout.addWidget(self.tabSpace)
        layout = QVBoxLayout()
        layout.addLayout(self.contentLayout)
        layout.addLayout(cmdLayout)
        self.setLayout(layout)

    @classmethod
    def showDialog(cls, settings):
        """constructor"""
        assert settings == 'settings'
        if cls.dialog:
            cls.dialog.updateWidgets()
            cls.dialog.updateButtons()
            cls.dialog.show()
            return cls.dialog

    def showEvent(self, dummyEvent):
        """if the settings dialog shows, rememeber current values
        and show them in the widgets"""
        self.orgPref = self.preferences.as_dict()
        self.updateWidgets()

    def iconClicked(self, item):
        """show the wanted config tab"""
        self.setCurrentPage(self.pages[self.iconList.indexFromItem(item).row()])

    @classmethod
    def allChildren(cls, widget):
        """recursively find all widgets holding settings: Their object name
        starts with kcfg_"""
        result = []
        for child in widget.children():
            if str(child.objectName()).startswith('kcfg_'):
                result.append(child)
            else:
                result.extend(cls.allChildren(child))
        return result

    def addPage(self, configTab, name, iconName):
        """add a page to the config dialog"""
        item = QListWidgetItem(KIcon(iconName), name)
        item.setTextAlignment(Qt.AlignHCenter)
        font = item.font()
        font.setBold(True)
        item.setFont(font)
        item.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled)
        self.iconList.addItem(item)
        self.tabSpace.addWidget(configTab)
        icons = list(self.iconList.item(x) for x in range(len(self.iconList)))
        neededIconWidth = max(self.iconList.visualItemRect(x).width() for x in icons)
        margins = self.iconList.contentsMargins()
        neededIconWidth +=  margins.left() + margins.right()
        self.iconList.setMaximumWidth(neededIconWidth)
        self.iconList.setMinimumWidth(neededIconWidth)
        for child in self.allChildren(self):
            self.configWidgets[str(child.objectName()).replace('kcfg_', '')] = child
            if isinstance(child, QCheckBox):
                child.stateChanged.connect(self.updateButtons)
            elif isinstance(child, QSlider):
                child.valueChanged.connect(self.updateButtons)
            elif isinstance(child, KLineEdit):
                child.textChanged.connect(self.updateButtons)
        self.updateButtons()
        return configTab

    def applySettings(self):
        """Apply pressed"""
        changed = self.updateButtons()
        self.updateSettings()
        if changed:
            self.settingsChanged.emit()
        self.updateButtons()

    def accept(self):
        """OK pressed"""
        changed = self.updateButtons()
        self.updateSettings()
        if changed:
            self.settingsChanged.emit()
        KDialog.accept(self)

    def updateButtons(self):
        """Updates the Apply and Default buttons. Returns True if there was a changed setting"""
        changed = False
        for name, widget in self.configWidgets.items():
            oldValue = self.preferences[name]
            newValue = getattr(widget, self.getFunc[widget.__class__.__name__])()
            if oldValue != newValue:
                changed = True
                break
        self.buttonBox.button(KDialog.Apply).setEnabled(changed)
        return changed

    def updateSettings(self):
        """Update the settings from the dialog"""
        for name, widget in self.configWidgets.items():
            self.preferences[name] = getattr(widget, self.getFunc[widget.__class__.__name__])()
        self.preferences.writeConfig()

    def updateWidgets(self):
        """Update the dialog based on the settings"""
        self.preferences.readConfig()
        for name, widget in self.configWidgets.items():
            getattr(widget, self.setFunc[widget.__class__.__name__])(getattr(self.preferences, name))

    def setCurrentPage(self, page):
        """show wanted page and select its icon"""
        self.tabSpace.setCurrentWidget(page)
        for idx in range(self.tabSpace.count()):
            self.iconList.item(idx).setSelected(idx==self.tabSpace.currentIndex())

KGlobal.initStatic()
