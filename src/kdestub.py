# pylint: disable=too-many-lines
# -*- coding: utf-8 -*-

"""
Copyright (C) 2008-2016 Wolfgang Rohdewald <wolfgang@rohdewald.de>

SPDX-License-Identifier: GPL-2.0-only



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
import urllib
from collections import defaultdict
from typing import List, Dict, TYPE_CHECKING, Optional, Union, Callable, Any, Type, cast

# pylint: disable=wrong-import-order

ParamValue = Union[str, int, bool]

if TYPE_CHECKING:
    from deferredutil import Deferred
    from mainwindow import MainWindow
    from config import SetupPreferences

# pylint: disable=wrong-import-position

from configparser import ConfigParser, NoSectionError, NoOptionError

# here come the replacements:

# pylint: disable=wildcard-import,unused-wildcard-import
from qt import *
from qtpy import QT6, PYSIDE6, QT_VERSION, API_NAME, PYQT_VERSION

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

    def __init__(self) ->None:
        assert not Internal.isServer, 'KApplication is not supported for the server'
        super().__init__(sys.argv)

        # Qt uses sys.argv[0] as application name
        # which is used by QStandardPaths - if we start kajongg.py directly,
        # the search path would look like /usr/share/kajongg.py/

        self.translators:List[KDETranslator] = []
        self.setApplicationName('kajongg')
        self.setApplicationVersion(str(Internal.defaultPort))

        self.initQtTranslator()

    def installTranslatorFile(self, qmName:str) ->None:
        """qmName is a full path to a .qm file"""
        if os.path.exists(qmName):
            translator = KDETranslator(self)
            translator.load(qmName)
            self.installTranslator(translator)
            self.translators.append(translator)
            if Debug.i18n:
                Internal.logger.debug('Installed Qt translator from %s', qmName)


    def initQtTranslator(self) ->None:
        """load translators using Qt .qm files"""
        for _ in self.translators:
            self.removeTranslator(_)
        self.translators = []
        _ = KDETranslator(self)
        self.translators.append(_)
        self.installTranslator(_)
        for language in reversed(list(MLocale.extendRegionLanguages(MLocale.currentLanguages()))):
            _ = QLibraryInfo.path(QLibraryInfo.LibraryPath.TranslationsPath)
            self.installTranslatorFile(os.path.join( _, f'qtbase_{language}.qm'))
            self.installTranslatorFile(f'/usr/share/locale/{language}/LC_MESSAGES/kwidgetsaddons5_qt.qm')

    @classmethod
    def desktopSize(cls) -> QSize:
        """The size of the current screen"""
        try:
            result = Internal.app.desktop().availableGeometry()
        except AttributeError:
            assert Internal.mainWindow
            screen = Internal.mainWindow.screen()
            assert screen
            result = screen.availableGeometry()
        return result


class CaptionMixin:

    """used by KDialog and KXmlGuiWindow"""

    def setCaption(self, caption:str) ->None:
        """append app name"""
        if caption:
            if not caption.endswith(i18n('Kajongg')):
                caption += f" – {i18n('Kajongg')}"
        else:
            caption = i18n('Kajongg')
        self.setWindowTitle(caption)  # type:ignore
        self.setWindowIcon(KIcon('kajongg'))  # type:ignore


class Help:
    """Interface to the KDE help system"""

    @staticmethod
    def url_for_language(lang:str) ->str:
        """The url for a given language"""
        return f'https://docs.kde.org/stable/{lang}/kajongg/kajongg/index.html'

    @staticmethod
    def find_help_url() ->str:
        """find an existing help url for preferred language"""
        for language in Internal.kajonggrc.group('Locale').readEntry('Language').split(':'):
            try:
                url = Help.url_for_language(language)
                with urllib.request.urlopen(url) as _:
                    if _.status == 200:
                        return url
            except urllib.error.HTTPError:
                pass
        return Help.url_for_language('en')

    @staticmethod
    def start() ->None:
        """start the KDE help center for kajongg or go to docs.kde.org"""
        try:
            subprocess.Popen(['khelpcenter', 'help:/kajongg/index.html'])  # pylint:disable=consider-using-with
        except OSError:
            webbrowser.open(Help.find_help_url())


class IconLabel(QLabel):

    """for use in messages and about dialog"""

    def __init__(self, iconName:str, dialog:QDialog) ->None:
        super().__init__()
        icon = KIcon(iconName)
        option = QStyleOption()
        option.initFrom(dialog)
        style = dialog.style()
        assert style
        self.setPixmap(icon.pixmap(style.pixelMetric(QStyle.PixelMetric.PM_MessageBoxIconSize, option, dialog)))


class KMessageBox:

    """again only what we need"""
    NoExec = 1
    AllowLink = 2
    Options = int

    @staticmethod
    def createKMessageBox(
            dialog:'KDialog', icon:QMessageBox.Icon, text:str, unusedStrlist:List[str],
            unusedAsk:str, unusedCheckboxReturn:bool, options:int) ->None:
        """translated as far as needed from kmessagegox.cpp"""
        mainLayout = QVBoxLayout()

        hLayout = QHBoxLayout()
        hLayout.setContentsMargins(0, 0, 0, 0)
        hLayout.setSpacing(-1)
        mainLayout.addLayout(hLayout, 5)

        iconName = {
            QMessageBox.Icon.Information: 'dialog-information',
            QMessageBox.Icon.Warning: 'dialog-warning',
            QMessageBox.Icon.Question: 'dialog-question'}[icon]
        iconLayout = QVBoxLayout()
        iconLayout.addStretch(1)
        iconLayout.addWidget(IconLabel(iconName, dialog))
        iconLayout.addStretch(5)
        hLayout.addLayout(iconLayout, 0)

        messageLabel = QLabel(text)
        flags = Qt.TextInteractionFlag.TextSelectableByMouse
        if options & KMessageBox.AllowLink:
            flags = cast(Qt.TextInteractionFlag, flags | Qt.TextInteractionFlag.LinksAccessibleByMouse)
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
            scrollArea.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            scrollPal = QPalette(scrollArea.palette())
            viewport = scrollArea.viewport()
            if viewport:
                viewport.setPalette(scrollPal)
            hLayout.addWidget(scrollArea, 5)
        else:
            hLayout.addWidget(messageLabel, 5)

        mainLayout.addWidget(dialog.buttonBox)
        dialog.setLayout(mainLayout)

KDialogButtonBox = QDialogButtonBox


class KDialog(CaptionMixin, QDialog):

    """QDialog should be enough for kajongg"""
    NoButton = QDialogButtonBox.StandardButton.NoButton
    Ok = QDialogButtonBox.StandardButton.Ok
    Cancel = QDialogButtonBox.StandardButton.Cancel
    Yes = QDialogButtonBox.StandardButton.Yes
    No = QDialogButtonBox.StandardButton.No
    Help = QDialogButtonBox.StandardButton.Help
    Apply = QDialogButtonBox.StandardButton.Apply
    RestoreDefaults = QDialogButtonBox.StandardButton.RestoreDefaults
    Default = QDialogButtonBox.StandardButton.RestoreDefaults
    Close = QDialogButtonBox.StandardButton.Close

    def __init__(self, parent:Optional[QWidget]=None) ->None:
        super().__init__(parent)
        self.buttonBox = QDialogButtonBox()
        self.buttonBox.accepted.connect(self.accept)
        self.buttonBox.rejected.connect(self.reject)
        self.__mainWidget:Optional[QWidget] = None

    def __set_text(self, buttonMask: QDialogButtonBox.StandardButton,
        which:QDialogButtonBox.StandardButton, text:str) ->None:
        """set button text"""
        if which & buttonMask:
            button = self.buttonBox.button(which)
            if button:
                button.setText(text)

    def __connect_button(self, buttonMask: QDialogButtonBox.StandardButton,
        which:QDialogButtonBox.StandardButton, connector:Any) ->None:
        """set connector"""
        if which & buttonMask:
            button = self.buttonBox.button(which)
            if button:
                button.clicked.connect(connector)

    def setButtons(self, buttonMask:QDialogButtonBox.StandardButton) ->None:
        """(re)create the buttonbox and put all wanted buttons into it"""
        if not buttonMask:
            self.buttonBox.clear()
            return
        self.buttonBox.setStandardButtons(buttonMask)
        self.__set_text(buttonMask, KDialog.Ok, i18n('&OK'))
        self.__set_text(buttonMask, KDialog.Apply, i18n('&Apply'))
        self.__set_text(buttonMask, KDialog.Cancel, i18n('&Cancel'))
        self.__set_text(buttonMask, KDialog.Help, i18n('&Help'))
        self.__set_text(buttonMask, KDialog.RestoreDefaults, i18n('&Defaults'))
        self.__connect_button(buttonMask, KDialog.RestoreDefaults, self.restoreDefaults)
        self.__connect_button(buttonMask, KDialog.Help, Help.start)

    def restoreDefaults(self) ->None:
        """virtual"""

    def setMainWidget(self, widget:QWidget) ->None:
        """see KDialog.setMainWidget"""
        if self.layout() is None:
            QVBoxLayout(self)
            _ = self.layout()
            assert _ is not None
            _.addWidget(self.buttonBox)
        layout = self.layout()
        assert layout is not None
        if self.__mainWidget:
            layout.removeWidget(self.__mainWidget)
            layout.removeWidget(self.buttonBox)
        self.__mainWidget = widget
        layout.addWidget(widget)
        layout.addWidget(self.buttonBox)

    def button(self, buttonCode:QDialogButtonBox.StandardButton) ->QPushButton:
        """return the matching button"""
        result = self.buttonBox.button(buttonCode)
        assert result
        return result

    def returns(self, button:Optional['QDialogButtonBox.StandardButton']=None) ->Any:
        """the user answered"""
        if button is None:
            button = self.default  # type:ignore[attr-defined]
        return button in (KDialog.Yes, KDialog.Ok)


class KUser:

    """only the things kajongg needs"""

    def __init__(self, uid:Optional[int]=None) ->None:
        pass

    def fullName(self) ->str:
        """stub"""
        if sys.platform == 'win32':
            return self.loginName()
        return pwd.getpwnam(self.loginName()).pw_gecos.replace(',', '')  # pylint:disable=possibly-used-before-assignment

    @staticmethod
    def loginName() ->str:
        """stub"""
        return getpass.getuser()


class KStandardAction:

    """stub"""
    @classmethod
    def preferences(cls, slot:Callable, actionCollection:'KActionCollection') ->None:
        """should add config dialog menu entry"""
        mainWindow = Internal.mainWindow
        assert mainWindow
        separator = Action(mainWindow)
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

        action = Action(mainWindow)
        action.triggered.connect(mainWindow.configureToolBar)
        action.setText(i18n('Configure Tool&bars...'))
        action.setIcon(KIcon('configure-toolbars'))
        action.setIconText(i18n('Configure toolbars'))
        separator = Action(mainWindow)
        separator.setSeparator(True)
        actionCollection.addAction('options_configure_toolbars', action)

        action = Action(mainWindow)
        action.triggered.connect(slot)
        action.setText(i18n('Configure &Kajongg...'))
        action.setIcon(KIcon('configure'))
        action.setIconText(i18n('Configure'))
        actionCollection.addAction('options_configure', action)


class KActionCollection:

    """stub"""

    def __init__(self, mainWindow:'KXmlGuiWindow') ->None:
        self.__actions:Dict[str,'Action'] = {}
        self.mainWindow = mainWindow

    def addAction(self, name:str, action:'Action') ->None:
        """stub"""
        self.__actions[name] = action
        for content in self.mainWindow.menus.values():
            if name in content[1]:
                content[0].addAction(action)
                break

    def actions(self) ->Dict[str, 'Action']:
        """the actions in this collection"""
        return self.__actions


class MyStatusBarItem:

    """one of the four player items"""

    def __init__(self, text:str, idx:int, stretch:int=0) ->None:
        self.idx = idx
        self.stretch = stretch
        self.label = QLabel()
        self.label.setText(text)
        self.label.setAlignment(cast(Qt.AlignmentFlag, Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter))


class KStatusBar(QStatusBar):

    """stub"""

    def __init__(self, *args:Any, **kwargs:Any) ->None:
        super().__init__(*args, **kwargs)
        self.__items:List[MyStatusBarItem] = []

    def hasItem(self, idx:int) ->bool:
        """stub"""
        return len(self.__items) > idx

    def changeItem(self, text:str, idx:int) ->None:
        """stub"""
        self.__items[idx].label.setText(text)

    def insertItem(self, text:str, idx:int, stretch:int) ->None:
        """stub"""
        item = MyStatusBarItem(text, idx, stretch)
        self.__items.append(item)
        self.insertWidget(item.idx, item.label, stretch=item.stretch)

    def removeItem(self, idx:int) ->None:
        """stub"""
        item = self.__items[idx]
        self.removeWidget(item.label)
        del self.__items[idx]

    def setItemAlignment(self, idx:int, alignment:Qt.AlignmentFlag) ->None:
        """stub"""
        self.__items[idx].label.setAlignment(alignment)


class KXmlGuiWindow(CaptionMixin, QMainWindow):

    """stub"""

    def __init__(self) ->None:
        super().__init__()
        self.actionStatusBar: 'Action'
        self.actionToolBar: 'Action'
        self.actionFullscreen: 'Action'
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
            menu_bar = self.menuBar()
            if menu_bar:
                menu_bar.addMenu(mainMenu)
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
        self.toolBar().setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)

    def statusBar(self) -> KStatusBar:
        """for mypy"""
        return cast(KStatusBar, QMainWindow.statusBar(self))

    def showEvent(self, event:Optional[QShowEvent]) ->None:
        """now that the MainWindow code has run, we know all actions"""
        self.refreshToolBar()
        assert Internal.Preferences
        self.toolBar().setVisible(bool(Internal.Preferences.toolBarVisible))
        self.actionStatusBar.setChecked(self.statusBar().isVisible())
        self.actionToolBar.setChecked(self.toolBar().isVisible())
        self.actionFullscreen.setChecked(
            self.windowState() & Qt.WindowState.WindowFullScreen == Qt.WindowState.WindowFullScreen)
        if event:
            super().showEvent(event)

    def hideEvent(self, event:Optional[QHideEvent]) ->None:
        """save status"""
        assert Internal.Preferences
        Internal.Preferences.toolBarVisible = self.toolBar(
        ).isVisible()
        if event:
            super().hideEvent(event)

    def toggleStatusBar(self, checked:bool) ->None:
        """show / hide status bar"""
        self.statusBar().setVisible(checked)

    def toggleToolBar(self, checked:bool) ->None:
        """show / hide status bar"""
        self.toolBar().setVisible(checked)

    def configureToolBar(self) ->None:
        """configure toolbar"""
        dlg = KEditToolBar(self)
        dlg.show()

    def refreshToolBar(self) ->None:
        """reload settings for toolbar actions"""
        self.toolBar().clear()
        assert Internal.Preferences
        for name in Internal.Preferences.toolBarActions.split(','):
            self.toolBar().addAction(self.actionCollection().actions()[name])

    def actionCollection(self) ->'KActionCollection':
        """stub"""
        return self._actions

    def setupGUI(self) ->None:
        """stub"""

    def toolBar(self) ->QToolBar:
        """stub"""
        return self._toolBar

    @staticmethod
    def selectLanguage() ->None:
        """switch the language"""
        assert Internal.mainWindow
        KSwitchLanguageDialog(Internal.mainWindow).exec()

    @staticmethod
    def aboutKajongg() ->None:
        """show an about dialog"""
        assert Internal.mainWindow
        AboutKajonggDialog(Internal.mainWindow).exec()

    def queryClose(self) ->bool:
        """default"""
        return True

    def queryExit(self) ->bool:
        """default"""
        return True

    def closeEvent(self, event:Optional[QEvent]) ->None:
        """call queryClose/queryExit"""
        if event:
            if self.queryClose() and self.queryExit():
                event.accept()
            else:
                event.ignore()


class KConfigGroup:

    """mimic KConfigGroup as far as we need it"""

    def __init__(self, config:'KConfig', groupName:str) ->None:
        self.config = weakref.ref(config)
        self.groupName = groupName

    def __default(self, name:str) ->Optional[ParamValue]:
        """defer computation of Languages until really needed"""
        if self.groupName == 'Locale' and name == 'Language':
            return QLocale().name()
        return None

    def readEntry(self, name:str) ->Optional[ParamValue]:
        """get an entry from this group."""
        try:
            _ = self.config()
            assert _
            items = _.items(self.groupName)
        except NoSectionError:
            return self.__default(name)
        items = {x: y for x, y in items if x.startswith(name)}
        i18nItems = {x: y for x, y in items.items() if x.startswith(name + '[')}
        if i18nItems:
            languages = Internal.kajonggrc.group('Locale').readEntry('Language').split(':')
            languages = [x.split('_')[0] for x in languages]
            for language in languages:
                key = f'{name}[{language}]'
                if key in i18nItems:
                    return i18nItems[key]
        if name in items:
            if self.groupName == 'Locale' and name == 'Language':
                languages = [x for x in items[name].split(':') if MLocale.isLanguageInstalled(x)]
                if languages:
                    return ':'.join(languages)
                return QLocale().name()
            return items[name]
        return self.__default(name)

    def readInteger(self, name:str) ->int:
        """calls readEntry and returns it as an int or raises an Exception."""
        result = self.readEntry(name)
        if result is None:
            raise ValueError(f'{self}: cannot find {name}')
        try:
            return int(result)
        except ValueError as _:
            raise ValueError(f'{self}: cannot parse {name}') from _

    def __str__(self) ->str:
        config = self.config()
        path = config.path if config else 'NO_PATH'
        return f'{path}:[{self.groupName}]'


class KGlobal:

    """stub"""

    @classmethod
    def initStatic(cls) ->None:
        """init class members"""
        Internal.kajonggrc = KConfig()

class KConfig(ConfigParser):

    """Parse KDE config files.
    This mimics KDE KConfig but can also be used like any ConfigParser but
    without support for a default section."""

    def __init__(self, path:Optional[str]=None) ->None:
        super().__init__(delimiters=('=', ))
        if path is None:
            path = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppConfigLocation)
            path = os.path.join(path, 'kajonggrc')
        self.path = os.path.expanduser(path)
        if os.path.exists(self.path):
            with codecs.open(self.path, 'r', encoding='utf-8') as cfgFile:
                self.read_file(cfgFile)

    def optionxform(self, optionstr:str) ->str:
        """KDE needs upper/lowercase distinction"""
        return optionstr

    def setValue(self, section:str, option:str, value:int) ->None:
        """like set but add missing section"""
        if section not in self.sections():
            self.add_section(section)
        self.set(section, option, str(value))

    def writeToFile(self) ->None:
        """Write an .ini-format representation of the configuration state."""
        with open(self.path, 'w', encoding='utf-8') as filePointer:
            self.write(filePointer, space_around_delimiters=False)

    def group(self, groupName:str) ->KConfigGroup:
        """just like KConfig"""
        return KConfigGroup(self, groupName)

def KIcon(name:Optional[str]=None) ->QIcon:  # pylint: disable=invalid-name
    """simple wrapper"""
    if sys.platform == 'win32':
        return QIcon(os.path.join('share', 'icons', name) if name else None)
    if name:
        return QIcon.fromTheme(name)
    return QIcon()


class Action(QAction):

    """helper for creation QAction"""

    def __init__(self, parent:'KXmlGuiWindow', name:Optional[str]=None,
        icon:Optional[str]=None, slot:Optional[Callable]=None,
        shortcut:Optional[str]=None, actionData:Optional[Union[str, Type[QWidget]]]=None) ->None:
        super().__init__(parent)
        if icon:
            self.setIcon(KIcon(icon))
        if slot:
            self.triggered.connect(slot)
        if parent:
            if name is None:
                name = ''
            parent.actionCollection().addAction(name, self)
        if shortcut:
            self.setShortcut(QKeySequence(shortcut))
            self.setShortcutContext(Qt.ShortcutContext.ApplicationShortcut)
        if actionData is not None:
            self.setData(actionData)


class KConfigSkeletonItem:

    """one preferences setting used by KOnfigSkeleton"""

    def __init__(self, skeleton:'KConfigSkeleton', key:str, value:ParamValue,
        default:ParamValue) ->None:
        assert skeleton
        self.skeleton = skeleton
        self.group = skeleton.currentGroup
        self.key = key
        self._value = value
        if value is None:
            self._value = default
        self.default = default

    def value(self) ->ParamValue:
        """default getter"""
        return self._value

    def setValue(self, value:ParamValue) ->None:
        """default setter"""
        if self._value != value:
            self._value = value
            self.skeleton.configChanged.emit()

    def getFromConfig(self) ->None:
        """if not there, use default"""
        try:
            self._value = Internal.kajonggrc.get(self.group, self.key)
        except (NoSectionError, NoOptionError):
            self._value = self.default  # type:ignore


class ItemBool(KConfigSkeletonItem):

    """boolean preferences setting used by KOnfigSkeleton"""

    def __init__(self, skeleton:'KConfigSkeleton', key:str, value:bool, default:bool) ->None:
        super().__init__(skeleton, key, value, default)

    def getFromConfig(self) ->None:
        """if not there, use default"""
        try:
            self._value = Internal.kajonggrc.getboolean(self.group, self.key)
        except (NoSectionError, NoOptionError):
            self._value = self.default


class ItemString(KConfigSkeletonItem):

    """string preferences setting used by KOnfigSkeleton"""

    def __init__(self, skeleton:'KConfigSkeleton', key:str, value:str, default:str) ->None:
        if value == '':
            value = default
        super().__init__(skeleton, key, value, default)


class ItemInt(KConfigSkeletonItem):

    """integer preferences setting used by KOnfigSkeleton"""

    def __init__(self, skeleton:'KConfigSkeleton', key:str, value:int, default:int) ->None:
        super().__init__(skeleton, key, value, default)
        self.minValue = -99999
        self.maxValue = 99999999

    def getFromConfig(self) ->None:
        """if not there, use default"""
        try:
            self._value = Internal.kajonggrc.getint(self.group, self.key)
        except (NoSectionError, NoOptionError):
            self._value = self.default

    def setMinValue(self, value:int) ->None:
        """minimum value for this setting"""
        self.minValue = value

    def setMaxValue(self, value:int) ->None:
        """maximum value for this setting"""
        self.maxValue = value


class KConfigSkeleton(QObject):

    """handles preferences settings"""
    configChanged = Signal()

    def __init__(self) ->None:
        super().__init__()
        self.currentGroup:str
        self.items:List[KConfigSkeletonItem] = []
        self.toolBarActions:str
        self.addBool('MainWindow', 'toolBarVisible', True)
        self.addString(
            'MainWindow',
            'toolBarActions',
            'quit,play,scoreTable,explain,players,options_configure')

    def addBool(self, group:str, name:str, default:Optional[bool]=None) ->None:
        """to be overridden"""

    def addString(self, group:str, name:str, default:Optional[str]=None) ->None:
        """to be overridden"""

    def readConfig(self) ->None:
        """init already read config"""
        for item in self.items:
            item.getFromConfig()

    def writeConfig(self) ->None:
        """to the same file name"""
        for item in self.items:
            Internal.kajonggrc.setValue(item.group, item.key, item.value())
        Internal.kajonggrc.writeToFile()

    def as_dict(self) ->defaultdict:
        """a dict of dicts"""
        result: defaultdict = defaultdict(dict)
        for item in self.items:
            result[item.group][item.key] = item.value()
        return result

    def setCurrentGroup(self, group:str) ->None:
        """to be used by following add* calls"""
        self.currentGroup = group

    def addItem(self, key:str, value:ParamValue,
        default:ParamValue) ->KConfigSkeletonItem:
        """add a string preference"""
        cls: Type[KConfigSkeletonItem]
        if isinstance(value, bool):
            cls = ItemBool
        elif isinstance(value, int):
            cls = ItemInt
        elif isinstance(value, str):
            cls = ItemString
        else:
            raise TypeError(f'addiItem accepts only bool, int, str but not {type(value)}/{value}')
        result = cls(self, key, value, default)
        result.getFromConfig()
        self.items.append(result)
        return result


class KSwitchLanguageDialog(KDialog):
    """select application language"""

    def __init__(self, parent:QWidget) ->None:
        super().__init__(parent)
        self.languageRows:Dict[QWidget, Any] = {}
        self.languageButtons:List[KLanguageButton] = []
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

    def addLanguageButton(self, languageCode: str, isPrimaryLanguage: bool) ->None:
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
        self.languagesLayout.addWidget(languageLabel, numRows + 1, 1, Qt.AlignmentFlag.AlignLeft)
        self.languagesLayout.addWidget(languageButton.button, numRows + 1, 2, Qt.AlignmentFlag.AlignLeft)

        if not isPrimaryLanguage:
            assert removeButton
            self.languagesLayout.addWidget(removeButton, numRows + 1, 3, Qt.AlignmentFlag.AlignLeft)
            removeButton.show()
            self.languageRows[removeButton] = tuple([languageLabel, languageButton])

        self.languageRows[languageButton] = tuple([languageLabel, languageButton])
        self.languageButtons.append(languageButton)

    def accept(self) ->None:
        """OK"""
        newValue = ':'.join(x.current for x in self.languageButtons)
        Internal.kajonggrc.setValue('Locale', 'Language', newValue)
        super().accept()

    def slotAddLanguageButton(self) ->None:
        """adding a new button with en_US as it should always be present"""
        self.addLanguageButton('en_US', len(self.languageButtons) == 0)

    def restoreDefaults(self) ->None:
        """reset values to default"""
        for _ in self.languageRows:
            if isinstance(_, KLanguageButton):
                self.removeLanguage(_)
        for removeButton in self.languageRows:
            if isAlive(removeButton):
                removeButton.deleteLater()
        self.languageRows = {}
        self.addLanguageButton(QLocale().name(), True)

    def removeButtonClicked(self) ->None:
        """remove this language"""
        _ = self.sender()
        assert isinstance(_, KLanguageButton)
        self.removeLanguage(_)

    def removeLanguage(self, button:'KLanguageButton') ->None:
        """remove this language"""
        label, languageButton = self.languageRows[button]
        label.deleteLater()
        languageButton.deleteLater()
        button.deleteLater()
        del self.languageRows[languageButton]
        self.languageButtons.remove(languageButton)


class KLanguageButton(QWidget):
    """A language button for KSwitchLanguageDialog"""

    def __init__(self, txt:str, parent:QWidget) ->None:
        super().__init__(parent)
        self.button = QPushButton(txt)
        self.popup = QMenu()
        self.button.setMenu(self.popup)
        self.setText(txt)
        self.__currentItem:str
        for _ in MLocale.availableLanguages_().split(':'):
            self.addLanguage(_)
        self.popup.triggered.connect(self.slotTriggered)
        self.popup.show()
        self.button.show()
        self.show()

    def deleteLater(self) ->None:
        """self and children"""
        self.button.deleteLater()
        self.popup.deleteLater()
        super().deleteLater()

    def setText(self, txt:str) ->None:
        """proxy: sets the button text"""
        self.button.setText(txt)


    def addLanguage(self, languageCode:str) ->None:
        """add language to popup"""
        text = languageCode
        locale = QLocale(languageCode)
        if locale != QLocale.c():
            text = locale.nativeLanguageName()

        action = QAction(QIcon(), text, self)
        action.setData(languageCode)
        self.popup.addAction(action)

    @property
    def current(self) ->str:
        """current languageCode"""
        return self.__currentItem

    @current.setter
    def current(self, languageCode:str) ->None:
        """point to languageCode"""
        action = (
            self.findAction(languageCode)
            or self.findAction(languageCode.split('_')[0])
            or self.popup.actions()[0])
        self.__currentItem = action.data()
        self.button.setText(action.text())

    def slotTriggered(self, action:Action) ->None:
        """another language has been selected from the popup"""
        self.current = action.data()

    def findAction(self, data:str) ->Optional[QAction]:
        """find action by name"""
        for action in self.popup.actions():
            if action.data() == data:
                assert isinstance(action, QAction)
                return action
        return None


class AboutKajonggDialog(KDialog):
    """about kajongg dialog"""

    def __init__(self, parent:QWidget) ->None:
        # pylint: disable=too-many-locals, too-many-statements
        from twisted import __version__

        super().__init__(parent)
        self.setCaption(i18n('About Kajongg'))
        self.setButtons(KDialog.Close)
        vLayout = QVBoxLayout()
        hLayout1 = QHBoxLayout()
        hLayout1.addWidget(IconLabel('kajongg', self))
        h1vLayout = QVBoxLayout()
        h1vLayout.addWidget(QLabel('Kajongg'))
        try:
            from appversion import VERSION  # type:ignore[import]
        except ImportError:
            VERSION = "Unknown"

        assert isinstance(QT_VERSION, str)
        underVersions = ['Qt' + QT_VERSION +' API=' + API_NAME]
        if PYQT_VERSION:
            underVersions.append('sip ' + SIP_VERSION_STR)
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
            underVersions.append(f"KDE Frameworks {versionsDict['KDE Frameworks']}")
        except OSError:
            underVersions.append(i18n('KDE Frameworks (not installed or not usable)'))
        underVersions.append(f'Twisted {__version__}')
        underVersions.append('Python {}.{}.{} {}'.format(*sys.version_info[:5]))  # pylint:disable=consider-using-f-string
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
                '<a href="https://apps.kde.org/kajongg">https://apps.kde.org/kajongg</a>']))
        licenseLabel = QLabel()
        licenseLabel.setOpenExternalLinks(True)
        licenseLabel.setText(
            '<a href="https://spdx.org/licenses/GPL-2.0-only.html">GNU General Public License Version 2</a>')
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
            label = QLabel(f'{name} <a href="mailto:{mail}">{mail}</a>: {description}')
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

    def __init__(self, parent:QWidget, name:str, preferences:'SetupPreferences') ->None:
        super().__init__(parent)
        self.pages: List[QWidget]
        self.setCaption(i18n('Configure'))
        self.name = name
        self.preferences = preferences
        self.orgPref:defaultdict[Any, Any]
        self.configWidgets:Dict[str, QWidget] = {}
        self.iconList = QListWidget()
        self.iconList.setViewMode(QListWidget.ViewMode.IconMode)
        self.iconList.setFlow(QListWidget.Flow.TopToBottom)
        self.iconList.setUniformItemSizes(True)
        self.iconList.itemClicked.connect(self.iconClicked)
        self.iconList.currentItemChanged.connect(self.iconClicked)
        self.tabSpace = QStackedWidget()
        self.setButtons(KDialog.Help | KDialog.Ok |
                        KDialog.Apply | KDialog.Cancel | KDialog.RestoreDefaults)
        if button := self.buttonBox.button(KDialog.Apply):
            button.clicked.connect(self.applySettings)
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
    def showDialog(cls, settings:str) ->None:
        """constructor"""
        assert settings == 'settings'
        if cls.dialog:
            cls.dialog.updateWidgets()
            cls.dialog.updateButtons()
            cls.dialog.show()
            return cls.dialog
        return None

    def showEvent(self, unusedEvent:Optional[QEvent]) ->None:
        """if the settings dialog shows, remember current values
        and show them in the widgets"""
        self.orgPref = self.preferences.as_dict() # FIXME: unused
        self.updateWidgets()

    def iconClicked(self, item:QListWidgetItem) ->None:
        """show the wanted config tab"""
        self.setCurrentPage(
            self.pages[self.iconList.indexFromItem(item).row()])

    @classmethod
    def allChildren(cls, widget:QObject) ->List[QObject]:
        """recursively find all widgets holding settings: Their object name
        starts with kcfg_"""
        result:List[QObject] = []
        for child in widget.children():
            assert isinstance(child, QObject), f'child is:{type(child)}'
            if child.objectName().startswith('kcfg_'):
                result.append(child)
            else:
                result.extend(cls.allChildren(child))
        return result

    def addPage(self, configTab:QWidget, name:str, iconName:str) ->QWidget:
        """add a page to the config dialog"""
        item = QListWidgetItem(KIcon(iconName), name)
        item.setTextAlignment(Qt.AlignmentFlag.AlignHCenter)
        font = item.font()
        font.setBold(True)
        item.setFont(font)
        item.setFlags(cast(Qt.ItemFlag, Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled))
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
            assert isinstance(child, QWidget)
            self.configWidgets[
                child.objectName().replace('kcfg_', '')] = child
            if isinstance(child, QCheckBox):
                child.stateChanged.connect(self.updateButtons)  # type:ignore[arg-type]
            elif isinstance(child, QSlider):
                child.valueChanged.connect(self.updateButtons)  # type:ignore[arg-type]
            elif isinstance(child, QLineEdit):
                child.textChanged.connect(self.updateButtons)  # type:ignore[arg-type]
        self.updateButtons()
        return configTab

    def applySettings(self) ->None:
        """Apply pressed"""
        if self.updateButtons():
            self.updateSettings()
            self.updateButtons()

    def accept(self) ->None:
        """OK pressed"""
        if self.updateButtons():
            self.updateSettings()
        super().accept()

    def updateButtons(self) ->bool:
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
        if button := self.buttonBox.button(KDialog.Apply):
            button.setEnabled(changed)
        return changed

    def updateSettings(self) ->None:
        """Update the settings from the dialog"""
        for name, widget in self.configWidgets.items():
            self.preferences[name] = getattr(
                widget,
                self.getFunc[widget.__class__.__name__])()
        self.preferences.writeConfig()

    def updateWidgets(self) ->None:
        """Update the dialog based on the settings"""
        self.preferences.readConfig()
        for name, widget in self.configWidgets.items():
            getattr(widget, self.setFunc[widget.__class__.__name__])(
                getattr(self.preferences, name))

    def setCurrentPage(self, page:QWidget) ->None:
        """show wanted page and select its icon"""
        self.tabSpace.setCurrentWidget(page)
        for idx in range(self.tabSpace.count()):
            if item := self.iconList.item(idx):
                item.setSelected(idx == self.tabSpace.currentIndex())


class KSeparator(QFrame):

    """used for toolbar editor"""

    def __init__(self, parent:QWidget) ->None:
        super().__init__(parent)
        self.setLineWidth(1)
        self.setMidLineWidth(0)
        self.setFrameShape(QFrame.Shape.HLine)
        self.setFrameShadow(QFrame.Shadow.Sunken)
        self.setMinimumSize(0, 2)


class ToolBarItem(QListWidgetItem):

    """a toolbar item"""

    def __init__(self, action:Action, parent:QListWidget) ->None:
        self.action = action
        self.parent = parent
        self.emptyIcon:QIcon
        super().__init__(self.__icon(), self.__text(), parent)
        # drop between items, not onto items
        self.setFlags(
            cast(Qt.ItemFlag, (self.flags() | Qt.ItemFlag.ItemIsDragEnabled) & ~Qt.ItemFlag.ItemIsDropEnabled))

    def __icon(self) ->QIcon:
        """the action icon, default is an empty icon"""
        result = self.action.icon()
        if result.isNull():
            if not hasattr(self, 'emptyIcon'):
                if style := self.parent.style():
                    iconSize = style.pixelMetric(
                        QStyle.PixelMetric.PM_SmallIconSize)
                    _ = QPixmap(iconSize, iconSize)
                    _.fill(Qt.GlobalColor.transparent)
                    self.emptyIcon = QIcon(_)
            result = self.emptyIcon
        return result

    def __text(self) ->str:
        """the action text"""
        return self.action.text().replace('&', '')


class ToolBarList(QListWidget):

    """QListWidget without internal moves"""

    def __init__(self, parent:QWidget) ->None:
        super().__init__(parent)
        self.setDragDropMode(QAbstractItemView.DragDropMode.DragDrop)  # no internal moves


class KEditToolBar(KDialog):

    """stub"""

    def __init__(self, parent:Optional[QWidget]=None) ->None:
        # pylint: disable=too-many-statements
        super().__init__(parent)
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
        self._insertAction:QToolButton = QToolButton(self)
        self._insertAction.setIcon(
            KIcon('go-next' if QApplication.isRightToLeft() else 'go-previous'))
        self._insertAction.setEnabled(False)
        self._insertAction.clicked.connect(self.insertButton)
        self._removeAction:QToolButton = QToolButton(self)
        self._removeAction.setIcon(
            KIcon('go-previous' if QApplication.isRightToLeft() else 'go-next'))
        self._removeAction.setEnabled(False)
        self._removeAction.clicked.connect(self.removeButton)
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
        button_layout.addWidget(self._removeAction, 2, 0)
        button_layout.addWidget(self._insertAction, 2, 2)
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

    def accept(self) ->None:
        """save and close"""
        self.saveActions()
        self.hide()

    def reject(self) ->None:
        """do not save and close"""
        self.hide()

    def inactiveSelectionChanged(self) ->None:
        """update buttons"""
        if self.inactiveList.selectedItems():
            self._insertAction.setEnabled(True)
        else:
            self._insertAction.setEnabled(False)

    def activeSelectionChanged(self) ->None:
        """update buttons"""
        row = self.activeList.currentRow()
        toolItem = None
        if self.activeList.selectedItems():
            toolItem = self.activeList.selectedItems()[0]
        self._removeAction.setEnabled(bool(toolItem))
        if toolItem:
            self.upAction.setEnabled(bool(row))
            self.downAction.setEnabled(row < self.activeList.count() - 1)
        else:
            self.upAction.setEnabled(False)
            self.downAction.setEnabled(False)

    def insertButton(self) ->None:
        """activate an action"""
        self.__moveItem(toActive=True)

    def removeButton(self) ->None:
        """deactivate an action"""
        self.__moveItem(toActive=False)

    def __moveItem(self, toActive:bool) ->None:
        """move item between the two lists"""
        if toActive:
            fromList = self.inactiveList
            toList = self.activeList
        else:
            fromList = self.activeList
            toList = self.inactiveList
        item = cast(ToolBarItem, fromList.takeItem(fromList.currentRow()))
        ToolBarItem(item.action, toList)

    def upButton(self) ->None:
        """move action up"""
        self.__moveUpDown(moveUp=True)

    def downButton(self) ->None:
        """move action down"""
        self.__moveUpDown(moveUp=False)

    def __moveUpDown(self, moveUp:bool) ->None:
        """change place of action in list"""
        active = self.activeList
        row = active.currentRow()
        item = active.takeItem(row)
        offset = -1 if moveUp else 1
        newRow = row + offset
        active.insertItem(newRow, item)
        active.setCurrentRow(newRow)

    def loadActions(self) ->None:
        """load active actions from Preferences"""
        assert Internal.mainWindow
        assert Internal.Preferences
        for name, action in Internal.mainWindow.actionCollection().actions().items():
            if action.text():
                if name in Internal.Preferences.toolBarActions:  # type:ignore
                    ToolBarItem(action, self.activeList)
                else:
                    ToolBarItem(action, self.inactiveList)

    def saveActions(self) ->None:
        """write active actions into Preferences"""
        if Internal.mainWindow is None:
            return
        activeActions = (cast(ToolBarItem, self.activeList.item(
            x)).action for x in range(self.activeList.count()))
        names = {
            v: k for k,
            v in Internal.mainWindow.actionCollection(
            ).actions(
            ).items(
            )}
        assert Internal.Preferences
        Internal.Preferences.toolBarActions = ','.join(
            names[x] for x in activeActions)
        Internal.mainWindow.refreshToolBar()

KGlobal.initStatic()
