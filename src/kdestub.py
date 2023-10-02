# pylint: disable=too-many-lines
# -*- coding: utf-8 -*-

"""
Copyright (C) 2008-2016 Wolfgang Rohdewald <wolfgang@rohdewald.de>

SPDX-License-Identifier: GPL-2.0



Here we define replacement classes for the case that we have no
python interface to KDE.

"""


import sys
import os
import subprocess
import getpass
import webbrowser
import codecs
import weakref
from collections import defaultdict

# pylint: disable=wrong-import-order

from configparser import ConfigParser, NoSectionError, NoOptionError

# here come the replacements:

# pylint: disable=wildcard-import,unused-wildcard-import
from qt import *
from qtpy import QT6, PYSIDE2, PYSIDE6, QT_VERSION, API_NAME, PYQT_VERSION
if QT6:
    from qtpy.QtCore import QKeyCombination  # pylint:disable=no-name-in-module

# pylint: disable=wrong-import-position

from mi18n import MLocale, KDETranslator, i18n, i18nc

from common import Internal, isAlive, Debug
from util import popenReadlines
from statesaver import StateSaver

if sys.platform != 'win32':
    import pwd

__all__ = ['KApplication', 'KConfig',
           'KMessageBox', 'KConfigSkeleton', 'KDialogButtonBox',
           'KConfigDialog', 'KDialog',
           'KUser', 'KStandardAction',
           'KXmlGuiWindow', 'KGlobal', 'KIcon']


class KApplication(QApplication):

    """stub"""

    def __init__(self):
        assert not Internal.isServer, 'KApplication is not supported for the server'
        QApplication.__init__(self, sys.argv)

        # Qt uses sys.argv[0] as application name
        # which is used by QStandardPaths - if we start kajongg.py directly,
        # the search path would look like /usr/share/kajongg.py/

        self.translators = []
        self.setApplicationName('kajongg')
        self.setApplicationVersion(str(Internal.defaultPort))

        self.initQtTranslator()

    def installTranslatorFile(self, qmName):
        """qmName is a full path to a .qm file"""
        if os.path.exists(qmName):
            translator = KDETranslator(self)
            translator.load(qmName)
            self.installTranslator(translator)
            self.translators.append(translator)
            if Debug.i18n:
                Internal.logger.debug('Installed Qt translator from %s', qmName)


    def initQtTranslator(self):
        """load translators using Qt .qm files"""
        for _ in self.translators:
            self.removeTranslator(_)
        self.translators = []
        _ = KDETranslator(self)
        self.translators.append(_)
        self.installTranslator(_)
        for language in reversed(list(MLocale.extendRegionLanguages(MLocale.currentLanguages()))):
            self.installTranslatorFile(os.path.join(
                QLibraryInfo.location(QLibraryInfo.TranslationsPath), 'qtbase_{}.qm'.format(language)))
            self.installTranslatorFile('/usr/share/locale/{}/LC_MESSAGES/kwidgetsaddons5_qt.qm'.format(language))

    @classmethod
    def desktopSize(cls) -> QSize:
        """The size of the current screen"""
        try:
            result = Internal.app.desktop().availableGeometry()
        except AttributeError:
            result = Internal.mainWindow.screen().availableGeometry()
        return result


class CaptionMixin:

    """used by KDialog and KXmlGuiWindow"""

    def setCaption(self, caption):
        """append app name"""
        if caption:
            if not caption.endswith(i18n('Kajongg')):
                caption += ' – {}'.format(i18n('Kajongg'))
        else:
            caption = i18n('Kajongg')
        self.setWindowTitle(caption)
        self.setWindowIcon(KIcon('kajongg'))




class Help:
    """Interface to the KDE help system"""

    @staticmethod
    def __getDocUrl(languages):
        """return the best match for the online user manual"""
        from twisted.web import client

        def processResult(unusedResult, fallbacks):
            """if status 404, try the next fallback language"""
            return Help.__getDocUrl(fallbacks) if factory.status == '404' else url
        host = 'docs.kde.org'
        path = '?application=kajongg&language={}'.format(languages[0])
        url = 'https://' + host + path
        factory = client.HTTPClientFactory(url.encode('ascii'))
        factory.protocol = client.HTTPPageGetter
        factory.protocol.handleEndHeaders = lambda x: x
        Internal.reactor.connectTCP(host, 80, factory)
        factory.deferred.addCallback(processResult, languages[1:])
        return factory.deferred

    @staticmethod
    def start():
        """start the KDE help center for kajongg or go to docs.kde.org"""
        try:
            subprocess.Popen(['khelpcenter', 'help:/kajongg/index.html'])  # pylint:disable=consider-using-with
        except OSError:
            def gotUrl(url):
                """now we know where the manual is"""
                webbrowser.open(url)
            languages = Internal.kajonggrc.group(
                'Locale').readEntry('Language').split(':')
            Help.__getDocUrl(languages).addCallback(gotUrl)


class IconLabel(QLabel):

    """for use in messages and about dialog"""

    def __init__(self, iconName, dialog):
        QLabel.__init__(self)
        icon = KIcon(iconName)
        option = QStyleOption()
        option.initFrom(dialog)
        self.setPixmap(icon.pixmap(dialog.style().pixelMetric(
            QStyle.PM_MessageBoxIconSize, option, dialog)))


class KMessageBox:

    """again only what we need"""
    NoExec = 1
    AllowLink = 2
    Options = int

    @staticmethod
    def createKMessageBox(
            dialog, icon, text, unusedStrlist, unusedAsk, unusedCheckboxReturn, options):
        """translated as far as needed from kmessagegox.cpp"""
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
        flags = Qt.TextSelectableByMouse
        if options & KMessageBox.AllowLink:
            flags |= Qt.LinksAccessibleByMouse
            messageLabel.setOpenExternalLinks(True)
        messageLabel.setTextInteractionFlags(flags)

        desktop = KApplication.desktopSize()
        if messageLabel.sizeHint().width() > desktop.width() * 0.5:
            messageLabel.setWordWrap(True)

        usingScrollArea = desktop.height(
        ) // 3 < messageLabel.sizeHint(
        ).height(
        )
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

KDialogButtonBox = QDialogButtonBox


class KDialog(CaptionMixin, QDialog):

    """QDialog should be enough for kajongg"""
    NoButton = 0
    Ok = QDialogButtonBox.Ok
    Cancel = QDialogButtonBox.Cancel
    Yes = QDialogButtonBox.Yes
    No = QDialogButtonBox.No
    Help = QDialogButtonBox.Help
    Apply = QDialogButtonBox.Apply
    RestoreDefaults = QDialogButtonBox.RestoreDefaults
    Default = QDialogButtonBox.RestoreDefaults
    Close = QDialogButtonBox.Close

    def __init__(self, parent=None):
        QDialog.__init__(self, parent)
        self.buttonBox = QDialogButtonBox()
        self.buttonBox.accepted.connect(self.accept)
        self.buttonBox.rejected.connect(self.reject)
        self.__mainWidget = None

    def setButtons(self, buttonMask):
        """(re)create the buttonbox and put all wanted buttons into it"""
        if not buttonMask:
            self.buttonBox.clear()
            return
        self.buttonBox.setStandardButtons(buttonMask)
        if KDialog.Ok & buttonMask:
            self.buttonBox.button(KDialog.Ok).setText(i18n('&OK'))
        if KDialog.Apply & buttonMask:
            self.buttonBox.button(KDialog.Apply).setText(i18n('&Apply'))
        if KDialog.Cancel & buttonMask:
            self.buttonBox.button(KDialog.Cancel).setText(i18n('&Cancel'))
        if KDialog.Help & buttonMask:
            self.buttonBox.button(KDialog.Help).setText(i18n('&Help'))
        if KDialog.RestoreDefaults & buttonMask:
            self.buttonBox.button(
                KDialog.RestoreDefaults).setText(i18n('&Defaults'))
            self.buttonBox.button(KDialog.RestoreDefaults).clicked.connect(self.restoreDefaults)
        if KDialog.Help & buttonMask:
            self.buttonBox.button(KDialog.Help).clicked.connect(Help.start)

    def restoreDefaults(self):
        """virtual"""

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
        """return the matching button"""
        return self.buttonBox.button(buttonCode)

    @staticmethod
    def ButtonCode(value):  # pylint: disable=invalid-name
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


class KUser:

    """only the things kajongg needs"""

    def __init__(self, uid=None):
        pass

    def fullName(self):
        """stub"""
        if sys.platform == 'win32':
            return self.loginName()
        return pwd.getpwnam(self.loginName()).pw_gecos.replace(',', '')

    @staticmethod
    def loginName():
        """stub"""
        return getpass.getuser()


class KStandardAction:

    """stub"""
    @classmethod
    def preferences(cls, slot, actionCollection):
        """should add config dialog menu entry"""
        mainWindow = Internal.mainWindow
        separator = QAction(Internal.mainWindow)
        separator.setSeparator(True)
        mainWindow.actionStatusBar = Action(mainWindow, 'options_show_statusbar', None)
        mainWindow.actionStatusBar.setCheckable(True)
        mainWindow.actionStatusBar.setEnabled(True)
        mainWindow.actionStatusBar.toggled.connect(mainWindow.toggleStatusBar)
        mainWindow.actionStatusBar.setText(
            i18nc('@action:inmenu', "Show St&atusbar"))
        mainWindow.actionToolBar = Action(mainWindow, 'options_show_toolbar', None)
        mainWindow.actionToolBar.setCheckable(True)
        mainWindow.actionToolBar.setEnabled(True)
        mainWindow.actionToolBar.toggled.connect(mainWindow.toggleToolBar)
        mainWindow.actionToolBar.setText(
            i18nc('@action:inmenu', "Show &Toolbar"))

        actionCollection.addAction('', separator)

        action = QAction(mainWindow)
        action.triggered.connect(mainWindow.configureToolBar)
        action.setText(i18n('Configure Tool&bars...'))
        action.setIcon(KIcon('configure-toolbars'))  # TODO: winprep
        action.setIconText(i18n('Configure toolbars'))
        separator = QAction(Internal.mainWindow)
        separator.setSeparator(True)
        actionCollection.addAction('options_configure_toolbars', action)

        action = QAction(mainWindow)
        action.triggered.connect(slot)
        action.setText(i18n('Configure &Kajongg...'))
        action.setIcon(KIcon('configure'))
        action.setIconText(i18n('Configure'))
        actionCollection.addAction('options_configure', action)


class KActionCollection:

    """stub"""

    def __init__(self, mainWindow):
        self.__actions = {}
        self.mainWindow = mainWindow

    def addAction(self, name, action):
        """stub"""
        self.__actions[name] = action
        for content in self.mainWindow.menus.values():
            if name in content[1]:
                content[0].addAction(action)
                break

    def actions(self):
        """the actions in this collection"""
        return self.__actions


class MyStatusBarItem:

    """one of the four player items"""

    def __init__(self, text, idx, stretch=0):
        self.idx = idx
        self.stretch = stretch
        self.label = QLabel()
        self.label.setText(text)
        self.label.setAlignment(Qt.AlignHCenter | Qt.AlignVCenter)


class KStatusBar(QStatusBar):

    """stub"""

    def __init__(self, *args, **kwargs):
        QStatusBar.__init__(self, *args, **kwargs)
        self.__items = []

    def hasItem(self, idx):
        """stub"""
        return len(self.__items) > idx

    def changeItem(self, text, idx):
        """stub"""
        self.__items[idx].label.setText(text)

    def insertItem(self, text, idx, stretch):
        """stub"""
        item = MyStatusBarItem(text, idx, stretch)
        self.__items.append(item)
        self.insertWidget(item.idx, item.label, stretch=item.stretch)

    def removeItem(self, idx):
        """stub"""
        item = self.__items[idx]
        self.removeWidget(item.label)
        del self.__items[idx]

    def setItemAlignment(self, idx, alignment):
        """stub"""
        self.__items[idx].label.setAlignment(alignment)


class KXmlGuiWindow(CaptionMixin, QMainWindow):

    """stub"""

    def __init__(self):
        QMainWindow.__init__(self)
        self._actions = KActionCollection(self)
        self._toolBar = QToolBar(self)
        self._toolBar.setObjectName('Toolbar')
        self.addToolBar(self.toolBar())
        self.setStatusBar(KStatusBar(self))
        self.statusBar().setObjectName('StatusBar')
        self.menus = {}
        # the menuItems are added to the main  menu by KActionCollection.addAction
        # their order is not defined by this here but by the order in which MainWindow
        # creates the menu entries. This only defines which action goes into which main menu.
        for menu, menuItems in (
                (i18n('&Game'), ('scoreGame', 'play', 'abort', 'quit')),
                (i18n('&View'), ('scoreTable', 'explain', 'chat', 'fullscreen')),
                (i18n('&Settings'), ('players', 'rulesets', 'angle', 'demoMode', '', 'options_show_statusbar',
                                     'options_show_toolbar', '', 'options_configure_toolbars', 'options_configure')),
                (i18n('&Help'), ('help', 'language', 'aboutkajongg'))):
            mainMenu = QMenu(menu)
            self.menus[menu] = (mainMenu, menuItems)
            self.menuBar().addMenu(mainMenu)
        self.setCaption('')
        self.actionHelp = Action(self, "help", "help-contents", Help.start)
        self.actionHelp.setText(i18nc('@action:inmenu', '&Help'))
        self.actionLanguage = Action(self,
            "language", "preferences-desktop-locale", self.selectLanguage)
        self.actionLanguage.setText(i18n('Switch Application Language'))
        self.actionAboutKajongg = Action(self,
            'aboutkajongg', 'kajongg', self.aboutKajongg)
        self.actionAboutKajongg.setText(
            i18nc('@action:inmenu', 'About &Kajongg'))
        self.toolBar().setMovable(False)
        self.toolBar().setFloatable(False)
        self.toolBar().setToolButtonStyle(Qt.ToolButtonTextBesideIcon)

    def showEvent(self, event):
        """now that the MainWindow code has run, we know all actions"""
        self.refreshToolBar()
        self.toolBar().setVisible(Internal.Preferences.toolBarVisible)
        self.actionStatusBar.setChecked(self.statusBar().isVisible())
        self.actionToolBar.setChecked(self.toolBar().isVisible())
        self.actionFullscreen.setChecked(self.windowState() & Qt.WindowFullScreen == Qt.WindowFullScreen)
        QMainWindow.showEvent(self, event)

    def hideEvent(self, event):
        """save status"""
        Internal.Preferences.toolBarVisible = self.toolBar(
        ).isVisible()
        QMainWindow.hideEvent(self, event)

    def toggleStatusBar(self, checked):
        """show / hide status bar"""
        self.statusBar().setVisible(checked)

    def toggleToolBar(self, checked):
        """show / hide status bar"""
        self.toolBar().setVisible(checked)

    def configureToolBar(self):
        """configure toolbar"""
        dlg = KEditToolBar(self)
        dlg.show()

    def refreshToolBar(self):
        """reload settings for toolbar actions"""
        self.toolBar().clear()
        for name in Internal.Preferences.toolBarActions.split(','):
            self.toolBar().addAction(self.actionCollection().actions()[name])

    def actionCollection(self):
        """stub"""
        return self._actions

    def setupGUI(self):
        """stub"""

    def toolBar(self):
        """stub"""
        return self._toolBar

    @staticmethod
    def selectLanguage():
        """switch the language"""
        KSwitchLanguageDialog(Internal.mainWindow).exec_()

    @staticmethod
    def aboutKajongg():
        """show an about dialog"""
        AboutKajonggDialog(Internal.mainWindow).exec_()

    def queryClose(self):
        """default"""
        return True

    def queryExit(self):
        """default"""
        return True

    def closeEvent(self, event):
        """call queryClose/queryExit"""
        if self.queryClose() and self.queryExit():
            event.accept()
        else:
            event.ignore()


class KConfigGroup:

    """mimic KConfigGroup as far as we need it"""

    def __init__(self, config, groupName):
        self.config = weakref.ref(config)
        self.groupName = groupName

    def __default(self, name, default):
        """defer computation of Languages until really needed"""
        if default is not None:
            return default
        if self.groupName == 'Locale' and name == 'Language':
            return QLocale().name()
        return None

    def readEntry(self, name, default=None):
        """get an entry from this group."""
        try:
            items = self.config().items(self.groupName)
        except NoSectionError:
            return self.__default(name, default)
        items = {x: y for x, y in items if x.startswith(name)}
        i18nItems = {x: y for x, y in items.items() if x.startswith(name + '[')}
        if i18nItems:
            languages = Internal.kajonggrc.group('Locale').readEntry('Language').split(':')
            languages = [x.split('_')[0] for x in languages]
            for language in languages:
                key = '%s[%s]' % (name, language)
                if key in i18nItems:
                    return i18nItems[key]
        if name in items:
            if self.groupName == 'Locale' and name == 'Language':
                languages = [x for x in items[name].split(':') if MLocale.isLanguageInstalled(x)]
                if languages:
                    return ':'.join(languages)
                return QLocale().name()
            return items[name]
        return self.__default(name, default)

    def readInteger(self, name, default=None):
        """calls readEntry and returns it as an int or raises an Exception."""
        try:
            return int(self.readEntry(name, default))
        except Exception as _:
            raise ValueError('cannot parse group {} in {}: {}={}'.format(
                self.groupName, self.config().path, name,
                self.readEntry(name, default)
                )) from _

    def __str__(self) ->str:
        config = self.config()
        path = config.path if config else 'NO_PATH'
        return '{}:[{}]'.format(path, self.groupName)


class KGlobal:

    """stub"""

    @classmethod
    def initStatic(cls):
        """init class members"""
        Internal.kajonggrc = KConfig()

class KConfig(ConfigParser):

    """Parse KDE config files.
    This mimics KDE KConfig but can also be used like any ConfigParser but
    without support for a default section."""

    def __init__(self, path=None):
        ConfigParser.__init__(self, delimiters=('=', ))
        if path is None:
            path = QStandardPaths.writableLocation(QStandardPaths.AppConfigLocation)
            path = os.path.join(path, 'kajonggrc')
        self.path = os.path.expanduser(path)
        if os.path.exists(self.path):
            with codecs.open(self.path, 'r', encoding='utf-8') as cfgFile:
                self.read_file(cfgFile)

    def optionxform(self, optionstr):
        """KDE needs upper/lowercase distinction"""
        return optionstr

    def setValue(self, section, option, value):
        """like set but add missing section"""
        if section not in self.sections():
            self.add_section(section)
        self.set(section, option, str(value))

    def writeToFile(self):
        """Write an .ini-format representation of the configuration state."""
        with open(self.path, 'w', encoding='utf-8') as filePointer:
            self.write(filePointer, space_around_delimiters=False)

    def group(self, groupName):
        """just like KConfig"""
        return KConfigGroup(self, groupName)

def KIcon(name=None):  # pylint: disable=invalid-name
    """simple wrapper"""
    if sys.platform == 'win32':
        return QIcon(os.path.join('share', 'icons', name) if name else None)
    return QIcon.fromTheme(name)


class Action(QAction):

    """helper for creation QAction"""

    def __init__(self, parent, name, icon, slot=None, shortcut=None, actionData=None):
        super().__init__(parent)
        if icon:
            self.setIcon(KIcon(icon))
        if slot:
            self.triggered.connect(slot)
        if parent:
            parent.actionCollection().addAction(name, self)
        if shortcut:
            if QT6:
                if isinstance(shortcut, QKeyCombination):
                    shortcut = shortcut.key()
            self.setShortcut(QKeySequence(shortcut | Qt.CTRL))
            self.setShortcutContext(Qt.ApplicationShortcut)
        if actionData is not None:
            self.setData(actionData)


class KConfigSkeletonItem:

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

    def setValue(self, value):
        """default setter"""
        if self._value != value:
            self._value = value
            self.skeleton.configChanged.emit()

    def getFromConfig(self):
        """if not there, use default"""
        try:
            self._value = Internal.kajonggrc.get(self.group, self.key)
        except (NoSectionError, NoOptionError):
            self._value = self.default


class ItemBool(KConfigSkeletonItem):

    """boolean preferences setting used by KOnfigSkeleton"""

    def __init__(self, skeleton, key, value, default=None):
        KConfigSkeletonItem.__init__(self, skeleton, key, value, default)

    def getFromConfig(self):
        """if not there, use default"""
        try:
            self._value = Internal.kajonggrc.getboolean(self.group, self.key)
        except (NoSectionError, NoOptionError):
            self._value = self.default


class ItemString(KConfigSkeletonItem):

    """string preferences setting used by KOnfigSkeleton"""

    def __init__(self, skeleton, key, value, default=None):
        if value == '':
            value = default
        KConfigSkeletonItem.__init__(self, skeleton, key, value, default)


class ItemInt(KConfigSkeletonItem):

    """integer preferences setting used by KOnfigSkeleton"""

    def __init__(self, skeleton, key, value, default=0):
        KConfigSkeletonItem.__init__(self, skeleton, key, value, default)
        self.minValue = -99999
        self.maxValue = 99999999

    def getFromConfig(self):
        """if not there, use default"""
        try:
            self._value = Internal.kajonggrc.getint(self.group, self.key)
        except (NoSectionError, NoOptionError):
            self._value = self.default

    def setMinValue(self, value):
        """minimum value for this setting"""
        self.minValue = value

    def setMaxValue(self, value):
        """maximum value for this setting"""
        self.maxValue = value


class KConfigSkeleton(QObject):

    """handles preferences settings"""
    configChanged = Signal()

    def __init__(self):
        QObject.__init__(self)
        self.currentGroup = None
        self.items = []
        self.addBool('MainWindow', 'toolBarVisible', True)
        self.addString(
            'MainWindow',
            'toolBarActions',
            'quit,play,scoreTable,explain,players,options_configure')

    def addBool(self, group, name, default=None):
        """to be overridden"""

    def addString(self, group, name, default=None):
        """to be overridden"""

    def readConfig(self):
        """init already read config"""
        for item in self.items:
            item.getFromConfig()

    def writeConfig(self):
        """to the same file name"""
        for item in self.items:
            Internal.kajonggrc.setValue(item.group, item.key, item.value())
        Internal.kajonggrc.writeToFile()

    def as_dict(self):
        """a dict of dicts"""
        result = defaultdict(dict)
        for item in self.items:
            result[item.group][item.key] = item.value()
        return result

    def setCurrentGroup(self, group):
        """to be used by following add* calls"""
        self.currentGroup = group

    def addItem(self, key, value, default=None):
        """add a string preference"""
        if isinstance(value, bool):
            cls = ItemBool
        elif isinstance(value, int):
            cls = ItemInt
        elif isinstance(value, str):
            cls = ItemString
        else:
            raise TypeError('addiItem accepts only bool, int, str but not {}/{}'.format(type(value), value))
        result = cls(self, key, value, default)
        result.getFromConfig()
        self.items.append(result)
        return result


class KSwitchLanguageDialog(KDialog):
    """select application language"""

    def __init__(self, parent):
        super().__init__(parent)
        self.languageRows = {}
        self.languageButtons = []
        self.setCaption(i18n('Switch Application Language'))
        self.widget = QWidget()
        topLayout = QVBoxLayout()
        self.widget.setLayout(topLayout)

        topLayout.addWidget(QLabel(i18n("Please choose the language which should be used for this application:")))

        languageHorizontalLayout = QHBoxLayout()
        topLayout.addLayout(languageHorizontalLayout)

        self.languagesLayout = QGridLayout()
        languageHorizontalLayout.addLayout(self.languagesLayout)
        languageHorizontalLayout.addStretch()

        defined = Internal.kajonggrc.group(
            'Locale').readEntry('Language').split(':')
        if not defined:
            defined = [QLocale().name()]
        for idx, _ in enumerate(defined):
            self.addLanguageButton(_, isPrimaryLanguage=idx == 0)

        addButtonHorizontalLayout = QHBoxLayout()
        topLayout.addLayout(addButtonHorizontalLayout)

        addLangButton = QPushButton(i18n("Add Fallback Language"), self)
        addLangButton.clicked.connect(self.slotAddLanguageButton)
        addButtonHorizontalLayout.addWidget(addLangButton)
        addButtonHorizontalLayout.addStretch()

        topLayout.addStretch(10)

        self.setButtons(KDialog.Ok | KDialog.Cancel | KDialog.RestoreDefaults)
        self.setMainWidget(self.widget)

    def addLanguageButton(self, languageCode, isPrimaryLanguage):
        """add button for language"""
        labelText = i18n("Primary language:") if isPrimaryLanguage else i18n("Fallback language:")
        languageButton = KLanguageButton('', self.widget)
        languageButton.current = languageCode

        removeButton = None
        if not isPrimaryLanguage:
            removeButton = QPushButton(i18n("Remove"))
            removeButton.clicked.connect(self.removeButtonClicked)

        languageButton.setToolTip(
            i18n("This is the main application language which will be used first, before any other languages.")
            if isPrimaryLanguage else
            i18n("This is the language which will be used if any previous "
                 "languages do not contain a proper translation."))

        numRows = self.languagesLayout.rowCount()

        languageLabel = QLabel(labelText)
        self.languagesLayout.addWidget(languageLabel, numRows + 1, 1, Qt.AlignLeft)
        self.languagesLayout.addWidget(languageButton.button, numRows + 1, 2, Qt.AlignLeft)

        if not isPrimaryLanguage:
            self.languagesLayout.addWidget(removeButton, numRows + 1, 3, Qt.AlignLeft)
            removeButton.show()
            self.languageRows[removeButton] = tuple([languageLabel, languageButton])

        self.languageRows[languageButton] = tuple([languageLabel, languageButton])
        self.languageButtons.append(languageButton)

    def accept(self):
        """OK"""
        newValue = ':'.join(x.current for x in self.languageButtons)
        Internal.kajonggrc.setValue('Locale', 'Language', newValue)
        super().accept()

    def slotAddLanguageButton(self):
        """adding a new button with en_US as it should always be present"""
        self.addLanguageButton('en_US', len(self.languageButtons) == 0)

    def restoreDefaults(self):
        """reset values to default"""
        for _ in self.languageRows:
            if isinstance(_, KLanguageButton):
                self.removeLanguage(_)
        for removeButton in self.languageRows:
            if isAlive(removeButton):
                removeButton.deleteLater()
        self.languageRows = {}
        self.addLanguageButton(QLocale().name(), True)

    def removeButtonClicked(self):
        """remove this language"""
        self.removeLanguage(self.sender())

    def removeLanguage(self, button):
        """remove this language"""
        label, languageButton = self.languageRows[button]
        label.deleteLater()
        languageButton.deleteLater()
        button.deleteLater()
        del self.languageRows[languageButton]
        self.languageButtons.remove(languageButton)


class KLanguageButton(QWidget):
    """A language button for KSwitchLanguageDialog"""

    def __init__(self, txt, parent=None):
        super().__init__(parent)
        self.button = QPushButton(txt)
        self.popup = QMenu()
        self.button.setMenu(self.popup)
        self.setText(txt)
        self.__currentItem = None
        for _ in MLocale.availableLanguages_().split(':'):
            self.addLanguage(_)
        self.popup.triggered.connect(self.slotTriggered)
        self.popup.show()
        self.button.show()
        self.show()

    def deleteLater(self):
        """self and children"""
        self.button.deleteLater()
        self.popup.deleteLater()
        QWidget.deleteLater(self)

    def setText(self, txt):
        """proxy: sets the button text"""
        self.button.setText(txt)


    def addLanguage(self, languageCode):
        """add language to popup"""
        text = languageCode
        locale = QLocale(languageCode)
        if locale != QLocale.c():
            text = locale.nativeLanguageName()

        action = QAction(QIcon(), text, self)
        action.setData(languageCode)
        self.popup.addAction(action)

    @property
    def current(self):
        """current languageCode"""
        return self.__currentItem

    @current.setter
    def current(self, languageCode):
        """point to languageCode"""
        action = (
            self.findAction(languageCode)
            or self.findAction(languageCode.split('_')[0])
            or self.popup.actions()[0])
        self.__currentItem = action.data()
        self.button.setText(action.text())

    def slotTriggered(self, action):
        """another language has been selected from the popup"""
        self.current = action.data()

    def findAction(self, data):
        """find action by name"""
        for action in self.popup.actions():
            if action.data() == data:
                return action
        return None


class AboutKajonggDialog(KDialog):
    """about kajongg dialog"""

    def __init__(self, parent):
        # pylint: disable=too-many-locals, too-many-statements
        from twisted import __version__

        KDialog.__init__(self, parent)
        self.setCaption(i18n('About Kajongg'))
        self.setButtons(KDialog.Close)
        vLayout = QVBoxLayout()
        hLayout1 = QHBoxLayout()
        hLayout1.addWidget(IconLabel('kajongg', self))
        h1vLayout = QVBoxLayout()
        h1vLayout.addWidget(QLabel('Kajongg'))
        try:
            from appversion import VERSION
        except ImportError:
            VERSION = "Unknown"

        underVersions = ['Qt' + QT_VERSION +' API=' + API_NAME]
        if PYQT_VERSION:
            from sip import SIP_VERSION_STR
            underVersions.append('sip ' + SIP_VERSION_STR)
        if PYSIDE2:
            import PySide2
            underVersions.append('PySide2 ' + PySide2.__version__)
        if PYSIDE6:
            import PySide6
            underVersions.append('PySide6 ' + PySide6.__version__)

        h1vLayout.addWidget(QLabel(i18n('Version: %1', VERSION)))
        h1vLayout.addWidget(QLabel(i18n('Protocol version %1', Internal.defaultPort)))
        authors = ((
            "Wolfgang Rohdewald",
            i18n("Original author"),
            "wolfgang@rohdewald.de"), )
        try:
            versions = popenReadlines('kf5-config -v')
            versionsDict = dict(x.split(': ') for x in versions if ':' in x)
            underVersions.append('KDE Frameworks %s' % versionsDict['KDE Frameworks'])
        except OSError:
            underVersions.append(i18n('KDE Frameworks (not installed or not usable)'))
        underVersions.append('Twisted %s' % __version__)
        underVersions.append(
            'Python {}.{}.{} {}'.format(*sys.version_info[:5]))
        h1vLayout.addWidget(
            QLabel(
                i18nc('kajongg',
                      'Using versions %1',
                      ', '.join(
                          underVersions))))
        hLayout1.addLayout(h1vLayout)
        spacerItem = QSpacerItem(
            20,
            20,
            QSizePolicy.Expanding,
            QSizePolicy.Expanding)
        hLayout1.addItem(spacerItem)
        vLayout.addLayout(hLayout1)
        tabWidget = QTabWidget()

        aboutWidget = QWidget()
        aboutLayout = QVBoxLayout()
        aboutLabel = QLabel()
        aboutLabel.setWordWrap(True)
        aboutLabel.setOpenExternalLinks(True)
        aboutLabel.setText(
            '<br /><br />'.join([
                i18n("Mah Jongg - the ancient Chinese board game for 4 players"),
                i18n("This is the classical Mah Jongg for four players. "
                     "If you are looking for Mah Jongg solitaire please "
                     "use the application kmahjongg."),
                "(C) 2008-2017 Wolfgang Rohdewald",
                '<a href="{link}">{link}</a>'.format(
                    link='https://apps.kde.org/kajongg')]))
        licenseLabel = QLabel()
        licenseLabel.setText(
            '<a href="file://{link}">GNU General Public License Version 2</a>'.format(
                link=self.licenseFile()))
        licenseLabel.linkActivated.connect(self.showLicense)
        aboutLayout.addWidget(aboutLabel)
        aboutLayout.addWidget(licenseLabel)
        aboutWidget.setLayout(aboutLayout)
        tabWidget.addTab(aboutWidget, '&About')

        authorWidget = QWidget()
        authorLayout = QVBoxLayout()
        bugsLabel = QLabel(
            i18n('Please use <a href="https://bugs.kde.org">https://bugs.kde.org</a> to report bugs.'))
        bugsLabel.setContentsMargins(0, 2, 0, 4)
        bugsLabel.setOpenExternalLinks(True)
        authorLayout.addWidget(bugsLabel)

        titleLabel = QLabel(i18n('Authors:'))
        authorLayout.addWidget(titleLabel)

        for name, description, mail in authors:
            label = QLabel('{name} <a href="mailto:{mail}">{mail}</a>: {description}'.format(
                name=name, mail=mail, description=description))
            label.setOpenExternalLinks(True)
            authorLayout.addWidget(label)
        spacerItem = QSpacerItem(
            20,
            20,
            QSizePolicy.Expanding,
            QSizePolicy.Expanding)
        authorLayout.addItem(spacerItem)
        authorWidget.setLayout(authorLayout)
        tabWidget.addTab(authorWidget, 'A&uthor')
        vLayout.addWidget(tabWidget)

        vLayout.addWidget(self.buttonBox)
        self.setLayout(vLayout)
        self.buttonBox.setFocus()

    @staticmethod
    def licenseFile():
        """which may currently only be 1: GPL_V2"""
        prefix = QLibraryInfo.location(QLibraryInfo.PrefixPath)
        for path in ('COPYING', '../COPYING',
                     '%s/share/kf5/licenses/GPL_V2' % prefix):
            path = os.path.abspath(path)
            if os.path.exists(path):
                return path
        return None

    @classmethod
    def showLicense(cls):
        """as the name says"""
        LicenseDialog(Internal.mainWindow, cls.licenseFile()).exec_()


class LicenseDialog(KDialog):

    """see kaboutapplicationdialog.cpp"""

    def __init__(self, parent, licenseFile):
        KDialog.__init__(self, parent)
        self.setAttribute(Qt.WA_DeleteOnClose)
        self.setCaption(i18n("License Agreement"))
        self.setButtons(KDialog.Close)
        self.buttonBox.setFocus()
        with open('x' + licenseFile, 'r', encoding='utf-8') as _:
            licenseText = _.read()
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
        # try to allow enough height for a reasonable number of lines to be
        # shown
        metrics = QFontMetrics(self.licenseBrowser.font())
        idealHeight = metrics.height() * 30
        return KDialog.sizeHint(self).expandedTo(QSize(idealWidth, idealHeight))


class KConfigDialog(KDialog):

    """for the game preferences"""
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
        self.setButtons(KDialog.Help | KDialog.Ok |
                        KDialog.Apply | KDialog.Cancel | KDialog.RestoreDefaults)
        self.buttonBox.button(
            KDialog.Apply).clicked.connect(
                self.applySettings)
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
        return None

    def showEvent(self, unusedEvent):
        """if the settings dialog shows, remember current values
        and show them in the widgets"""
        self.orgPref = self.preferences.as_dict()
        self.updateWidgets()

    def iconClicked(self, item):
        """show the wanted config tab"""
        self.setCurrentPage(
            self.pages[self.iconList.indexFromItem(item).row()])

    @classmethod
    def allChildren(cls, widget):
        """recursively find all widgets holding settings: Their object name
        starts with kcfg_"""
        result = []
        for child in widget.children():
            if child.objectName().startswith('kcfg_'):
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
        self.iconList.setIconSize(QSize(80, 80))
        icons = [self.iconList.item(x) for x in range(self.iconList.count())]
        neededIconWidth = max(self.iconList.visualItemRect(x).width()
                              for x in icons)
        margins = self.iconList.contentsMargins()
        neededIconWidth += margins.left() + margins.right()
        self.iconList.setFixedWidth(neededIconWidth)
        self.iconList.setMinimumHeight(120 * self.iconList.count())
        for child in self.allChildren(self):
            self.configWidgets[
                child.objectName().replace('kcfg_', '')] = child
            if isinstance(child, QCheckBox):
                child.stateChanged.connect(self.updateButtons)
            elif isinstance(child, QSlider):
                child.valueChanged.connect(self.updateButtons)
            elif isinstance(child, QLineEdit):
                child.textChanged.connect(self.updateButtons)
        self.updateButtons()
        return configTab

    def applySettings(self):
        """Apply pressed"""
        if self.updateButtons():
            self.updateSettings()
            self.updateButtons()

    def accept(self):
        """OK pressed"""
        if self.updateButtons():
            self.updateSettings()
        KDialog.accept(self)

    def updateButtons(self):
        """Updates the Apply and Default buttons. Returns True if there was a changed setting"""
        changed = False
        for name, widget in self.configWidgets.items():
            oldValue = self.preferences[name]
            newValue = getattr(
                widget,
                self.getFunc[widget.__class__.__name__])()
            if oldValue != newValue:
                changed = True
                break
        self.buttonBox.button(KDialog.Apply).setEnabled(changed)
        return changed

    def updateSettings(self):
        """Update the settings from the dialog"""
        for name, widget in self.configWidgets.items():
            self.preferences[name] = getattr(
                widget,
                self.getFunc[widget.__class__.__name__])()
        self.preferences.writeConfig()

    def updateWidgets(self):
        """Update the dialog based on the settings"""
        self.preferences.readConfig()
        for name, widget in self.configWidgets.items():
            getattr(widget, self.setFunc[widget.__class__.__name__])(
                getattr(self.preferences, name))

    def setCurrentPage(self, page):
        """show wanted page and select its icon"""
        self.tabSpace.setCurrentWidget(page)
        for idx in range(self.tabSpace.count()):
            self.iconList.item(idx).setSelected(
                idx == self.tabSpace.currentIndex())


class KSeparator(QFrame):

    """used for toolbar editor"""

    def __init__(self, parent=None):
        QFrame.__init__(self, parent)
        self.setLineWidth(1)
        self.setMidLineWidth(0)
        self.setFrameShape(QFrame.HLine)
        self.setFrameShadow(QFrame.Sunken)
        self.setMinimumSize(0, 2)


class ToolBarItem(QListWidgetItem):

    """a toolbar item"""
    emptyIcon = None

    def __init__(self, action, parent):
        self.action = action
        self.parent = parent
        QListWidgetItem.__init__(self, self.__icon(), self.__text(), parent)
        # drop between items, not onto items
        self.setFlags(
            (self.flags() | Qt.ItemIsDragEnabled) & ~Qt.ItemIsDropEnabled)

    def __icon(self):
        """the action icon, default is an empty icon"""
        result = self.action.icon()
        if result.isNull():
            if not self.emptyIcon:
                iconSize = self.parent.style().pixelMetric(
                    QStyle.PM_SmallIconSize)
                self.emptyIcon = QPixmap(iconSize, iconSize)
                self.emptyIcon.fill(Qt.transparent)
                self.emptyIcon = QIcon(self.emptyIcon)
            result = self.emptyIcon
        return result

    def __text(self):
        """the action text"""
        return self.action.text().replace('&', '')


class ToolBarList(QListWidget):

    """QListWidget without internal moves"""

    def __init__(self, parent):
        QListWidget.__init__(self, parent)
        self.setDragDropMode(QAbstractItemView.DragDrop)  # no internal moves


class KEditToolBar(KDialog):

    """stub"""

    def __init__(self, parent=None):
        # pylint: disable=too-many-statements
        KDialog.__init__(self, parent)
        self.setCaption(i18n('Configure Toolbars'))
        StateSaver(self)
        self.inactiveLabel = QLabel(i18n("A&vailable actions:"), self)
        self.inactiveList = ToolBarList(self)
        self.inactiveList.setDragEnabled(True)
        self.inactiveList.setMinimumSize(180, 250)
        self.inactiveList.setDropIndicatorShown(False)
        self.inactiveLabel.setBuddy(self.inactiveList)
        self.inactiveList.itemSelectionChanged.connect(
            self.inactiveSelectionChanged)
        self.inactiveList.itemDoubleClicked.connect(self.insertButton)
        self.inactiveList.setSortingEnabled(True)

        self.activeLabel = QLabel(i18n('Curr&ent actions:'), self)
        self.activeList = ToolBarList(self)
        self.activeList.setDragEnabled(True)
        self.activeLabel.setBuddy(self.activeList)
        self.activeList.itemSelectionChanged.connect(
            self.activeSelectionChanged)
        self.activeList.itemDoubleClicked.connect(self.removeButton)

        self.upAction = QToolButton(self)
        self.upAction.setIcon(KIcon('go-up'))
        self.upAction.setEnabled(False)
        self.upAction.setAutoRepeat(True)
        self.upAction.clicked.connect(self.upButton)
        self.insertAction = QToolButton(self)
        self.insertAction.setIcon(
            KIcon('go-next' if QApplication.isRightToLeft() else 'go-previous'))
        self.insertAction.setEnabled(False)
        self.insertAction.clicked.connect(self.insertButton)
        self.removeAction = QToolButton(self)
        self.removeAction.setIcon(
            KIcon('go-previous' if QApplication.isRightToLeft() else 'go-next'))
        self.removeAction.setEnabled(False)
        self.removeAction.clicked.connect(self.removeButton)
        self.downAction = QToolButton(self)
        self.downAction.setIcon(KIcon('go-down'))
        self.downAction.setEnabled(False)
        self.downAction.setAutoRepeat(True)
        self.downAction.clicked.connect(self.downButton)

        top_layout = QVBoxLayout(self)
        top_layout.setContentsMargins(0, 0, 0, 0)
        list_layout = QHBoxLayout()

        inactive_layout = QVBoxLayout()
        active_layout = QVBoxLayout()

        button_layout = QGridLayout()

        button_layout.setSpacing(0)
        button_layout.setRowStretch(0, 10)
        button_layout.addWidget(self.upAction, 1, 1)
        button_layout.addWidget(self.removeAction, 2, 0)
        button_layout.addWidget(self.insertAction, 2, 2)
        button_layout.addWidget(self.downAction, 3, 1)
        button_layout.setRowStretch(4, 10)

        inactive_layout.addWidget(self.inactiveLabel)
        inactive_layout.addWidget(self.inactiveList, 1)
        active_layout.addWidget(self.activeLabel)
        active_layout.addWidget(self.activeList, 1)

        list_layout.addLayout(inactive_layout)
        list_layout.addLayout(button_layout)
        list_layout.addLayout(active_layout)

        top_layout.addLayout(list_layout, 10)
        top_layout.addWidget(KSeparator(self))
        self.loadActions()

        self.buttonBox = QDialogButtonBox()
        top_layout.addWidget(self.buttonBox)
        self.setButtons(KDialog.Ok | KDialog.Cancel)
        self.buttonBox.accepted.connect(self.accept)
        self.buttonBox.rejected.connect(self.reject)

    def accept(self):
        """save and close"""
        self.saveActions()
        self.hide()

    def reject(self):
        """do not save and close"""
        self.hide()

    def inactiveSelectionChanged(self):
        """update buttons"""
        if self.inactiveList.selectedItems():
            self.insertAction.setEnabled(True)
        else:
            self.insertAction.setEnabled(False)

    def activeSelectionChanged(self):
        """update buttons"""
        row = self.activeList.currentRow()
        toolItem = None
        if self.activeList.selectedItems():
            toolItem = self.activeList.selectedItems()[0]
        self.removeAction.setEnabled(bool(toolItem))
        if toolItem:
            self.upAction.setEnabled(bool(row))
            self.downAction.setEnabled(row < len(self.activeList) - 1)
        else:
            self.upAction.setEnabled(False)
            self.downAction.setEnabled(False)

    def insertButton(self):
        """activate an action"""
        self.__moveItem(toActive=True)

    def removeButton(self):
        """deactivate an action"""
        self.__moveItem(toActive=False)

    def __moveItem(self, toActive):
        """move item between the two lists"""
        if toActive:
            fromList = self.inactiveList
            toList = self.activeList
        else:
            fromList = self.activeList
            toList = self.inactiveList
        item = fromList.takeItem(fromList.currentRow())
        ToolBarItem(item.action, toList)

    def upButton(self):
        """move action up"""
        self.__moveUpDown(moveUp=True)

    def downButton(self):
        """move action down"""
        self.__moveUpDown(moveUp=False)

    def __moveUpDown(self, moveUp):
        """change place of action in list"""
        active = self.activeList
        row = active.currentRow()
        item = active.takeItem(row)
        offset = -1 if moveUp else 1
        newRow = row + offset
        active.insertItem(newRow, item)
        active.setCurrentRow(newRow)

    def loadActions(self):
        """load active actions from Preferences"""
        for name, action in Internal.mainWindow.actionCollection().actions().items():
            if action.text():
                if name in Internal.Preferences.toolBarActions:
                    ToolBarItem(action, self.activeList)
                else:
                    ToolBarItem(action, self.inactiveList)

    def saveActions(self):
        """write active actions into Preferences"""
        activeActions = (self.activeList.item(
            x).action for x in range(len(self.activeList)))
        names = {
            v: k for k,
            v in Internal.mainWindow.actionCollection(
            ).actions(
            ).items(
            )}
        Internal.Preferences.toolBarActions = ','.join(
            names[x] for x in activeActions)
        Internal.mainWindow.refreshToolBar()

KGlobal.initStatic()
