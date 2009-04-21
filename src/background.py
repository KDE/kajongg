"""
Authors of original libkmahjongg in C++:
    Copyright (C) 1997 Mathias Mueller   <in5y158@public.uni-hamburg.de>
    Copyright (C) 2006 Mauricio Piacentini  <mauricio@tabuleiro.com>

this python code:
    Copyright (C) 2008,2009 Wolfgang Rohdewald <wolfgang@rohdewald.de>

    kmj is free software you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation either version 2 of the License, or
    (at your option) any later version.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with this program if not, write to the Free Software
    Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.
"""

from PyQt4 import QtCore, QtGui
from PyQt4.QtGui import QPainter,  QColor,  QBrush,  QPalette
from PyKDE4 import kdecore, kdeui
from PyKDE4.kdecore import i18n

from util import logException

BACKGROUNDVERSIONFORMAT = 1

class BackgroundException(Exception):
    """will be thrown if the tileset cannot be loaded"""
    pass


def locatebackground(which):
    """locate the file with a background"""
    return QtCore.QString(kdecore.KStandardDirs.locate("kmahjonggbackground",
                QtCore.QString(which)))

class Background(object):
    """represents a background"""
    catalogDefined = False

    @staticmethod
    def defineCatalog():
        """whatever this does"""
        if not Background.catalogDefined:
            kdecore.KGlobal.dirs().addResourceType("kmahjonggbackground",
                "data", QtCore.QString.fromLatin1("kmahjongglib/backgrounds"))
            kdecore.KGlobal.locale().insertCatalog("libkmahjongglib")
            Background.catalogDefined = True

    @staticmethod
    def backgroundsAvailable():
        """returns all available backgrounds"""
        Background.defineCatalog()
        backgroundsAvailableQ = kdecore.KGlobal.dirs().findAllResources(
            "kmahjonggbackground", "*.desktop", kdecore.KStandardDirs.Recursive)
        # now we have a list of full paths. Use the base name minus .desktop:
        backgrounds = [str(x).rsplit('/')[-1].split('.')[0] for x in backgroundsAvailableQ ]
        return [Background(x) for x in backgrounds]

    def __init__(self, desktopFileName=None):
        if desktopFileName is None:
            desktopFileName = 'default'
        self.__svg = None
        self.pmap = None
        QtGui.QPixmapCache.setCacheLimit(20480) # the chinese landscape needs much
        self.defineCatalog()
        self.path = locatebackground(desktopFileName + '.desktop')
        if self.path.isEmpty():
            self.path = locatebackground('default.desktop')
            if self.path.isEmpty():
                logException(BackgroundException(i18n( \
                'cannot find any background, is libkmahjongg installed?')))
            else:
                print('cannot find background %s, using default' % desktopFileName)
                self.desktopFileName = 'default'
        else:
            self.desktopFileName = desktopFileName
        backgroundconfig = kdecore.KConfig(self.path, kdecore.KConfig.SimpleConfig)
        group = kdecore.KConfigGroup(backgroundconfig.group("KMahjonggBackground"))

        self.name = group.readEntry("Name",  "unknown background") # Returns translated data
        self.author = group.readEntry("Author",  "unknown author")
        self.description = group.readEntry("Description",  "")
        self.authorEmail = group.readEntry("AuthorEmail",  "no E-Mail address available")

        #Version control
        backgroundversion,  entryOK = group.readEntry("VersionFormat", QtCore.QVariant(0)).toInt()
        #Format is increased when we have incompatible changes, meaning that
        # older clients are not able to use the remaining information safely
        if not entryOK or backgroundversion > BACKGROUNDVERSIONFORMAT:
            logException(BackgroundException('backgroundversion file / program: %d/%d' %  \
                (backgroundversion,  BACKGROUNDVERSIONFORMAT)))

        self.tiled = group.readEntry('Tiled') == '1'
        if self.tiled:
            self.imageWidth = int(group.readEntry('Width'))
            self.imageHeight = int(group.readEntry('Height'))
        self.type = group.readEntry('Type')
        if self.type == 'SVG':
            self.graphName = QtCore.QString(group.readEntry("FileName"))
            self.__graphicspath = locatebackground(self.graphName)
            if self.__graphicspath.isEmpty():
                logException(BackgroundException(
                    'cannot find kmahjongglib/backgrounds/%s for %s' % \
                        (self.graphName,  self.desktopFileName )))
        elif self.type == 'Color':
            self.rgbColor = group.readEntry('RGBColor_1')
        else:
            logException(BackgroundException('unknown type in %s' % self.desktopFileName))

    def initSvgRenderer(self):
        """initialize the svg renderer with the selected svg file"""
        if self.__svg is None:
            self.__svg = kdeui.KSvgRenderer(self.__graphicspath)
            if not self.__svg.isValid():
                logException(BackgroundException( \
                i18n('file <filename>%1</filename> contains no valid SVG', self.__graphicspath)))

    def pixmap(self, size):
        """returns a background pixmap"""
        width = size.width()
        height = size.height()
        if self.type == 'SVG':
            if self.tiled:
                width = self.imageWidth
                height = self.imageHeight
            cachekey = QtCore.QString("%1W%2H%3") \
                .arg(self.name).arg(width).arg(height)
            self.pmap = QtGui.QPixmapCache.find(cachekey)
            if not self.pmap:
                self.initSvgRenderer()
                self.pmap = QtGui.QPixmap(width, height)
                self.pmap.fill(QtCore.Qt.transparent)
                painter = QPainter(self.pmap)
                self.__svg.render(painter)
                QtGui.QPixmapCache.insert(cachekey, self.pmap)
        else:
            self.pmap = QtGui.QPixmap(width, height)
            self.pmap.fill(QColor(self.rgbColor))
        return self.pmap

    def unusedpaint(self, painter, rect):
        """FittingView.drawBackground would use this"""
        if self.tiled:
            painter.drawTiledPixmap(rect, self.pixmap(rect))
        else:
            painter.drawPixmap(rect.toRect(), self.pixmap(rect))

    def brush(self, size):
        """background brush"""
        return QBrush(self.pixmap(size))

    def setPalette(self, onto):
        """sets a background palette for widget onto"""
        palette = QPalette()
        mybrush = self.brush(onto.size())
        palette.setBrush(QPalette.Window, mybrush)
        onto.setPalette(palette)


