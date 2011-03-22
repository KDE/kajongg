"""
Authors of original libkmahjongg in C++:
    Copyright (C) 1997 Mathias Mueller <in5y158@public.uni-hamburg.de>
    Copyright (C) 2006 Mauricio Piacentini <mauricio@tabuleiro.com>

this python code:
    Copyright (C) 2008,2009,2010,2011 Wolfgang Rohdewald <wolfgang@rohdewald.de>

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
"""

from PyQt4.QtCore import QString, QVariant, Qt
from PyQt4.QtGui import QPainter, QBrush, QPalette, \
    QPixmapCache, QPixmap
from PyQt4.QtSvg import QSvgRenderer
from kde import KGlobal, KStandardDirs

from util import logWarning, logException, m18n
from guiutil import konfigGroup

BACKGROUNDVERSIONFORMAT = 1

class BackgroundException(Exception):
    """will be thrown if the tileset cannot be loaded"""
    pass


def locatebackground(which):
    """locate the file with a background"""
    return QString(KStandardDirs.locate("kmahjonggbackground",
                QString(which)))

class Background(object):
    """represents a background"""
    catalogDefined = False

    @staticmethod
    def defineCatalog():
        """whatever this does"""
        if not Background.catalogDefined:
            KGlobal.dirs().addResourceType("kmahjonggbackground",
                "data", QString.fromLatin1("kmahjongglib/backgrounds"))
            KGlobal.locale().insertCatalog("libkmahjongglib")
            Background.catalogDefined = True

    @staticmethod
    def backgroundsAvailable():
        """returns all available backgrounds"""
        Background.defineCatalog()
        backgroundsAvailableQ = KGlobal.dirs().findAllResources(
            "kmahjonggbackground", "*.desktop", KStandardDirs.Recursive)
        # now we have a list of full paths. Use the base name minus .desktop:
        backgrounds = [str(x).rsplit('/')[-1].split('.')[0] for x in backgroundsAvailableQ ]
        return [Background(x) for x in backgrounds]

    def __init__(self, desktopFileName=None):
        if desktopFileName is None:
            desktopFileName = 'default'
        self.__svg = None
        self.__pmap = None
        QPixmapCache.setCacheLimit(20480) # the chinese landscape needs much
        self.defineCatalog()
        self.desktopFileName = desktopFileName
        self.path = locatebackground(desktopFileName + '.desktop')
        if self.path.isEmpty():
            self.path = locatebackground('default.desktop')
            if self.path.isEmpty():
                directories = '\n\n' +'\n'.join(str(x) for x in KGlobal.dirs().resourceDirs("kmahjonggbackground"))
                logException(BackgroundException(m18n( \
                'cannot find any background in the following directories, is libkmahjongg installed?') + directories))
            else:
                logWarning(m18n('cannot find background %1, using default', desktopFileName))
                self.desktopFileName = 'default'
        config, group = konfigGroup(self.path, "KMahjonggBackground")
        assert config
        self.name = group.readEntry("Name",  "unknown background").toString() # Returns translated data

        #Version control
        backgroundversion, entryOK = group.readEntry("VersionFormat", QVariant(0)).toInt()
        #Format is increased when we have incompatible changes, meaning that
        # older clients are not able to use the remaining information safely
        if not entryOK or backgroundversion > BACKGROUNDVERSIONFORMAT:
            logException(BackgroundException('backgroundversion file / program: %d/%d' %  \
                (backgroundversion, BACKGROUNDVERSIONFORMAT)))

        self.tiled = group.readEntry('Tiled') == '1'
        if self.tiled:
            self.imageWidth, entryOk = group.readEntry('Width').toInt()
            if not entryOk:
                raise Exception('cannot scan Width from background file')
            self.imageHeight, entryOk = group.readEntry('Height').toInt()
            if not entryOk:
                raise Exception('cannot scan Height from background file')
        self.isPlain = bool(group.readEntry('Plain'))
        if not self.isPlain:
            graphName = QString(group.readEntry("FileName"))
            self.__graphicspath = locatebackground(graphName)
            if self.__graphicspath.isEmpty():
                logException(BackgroundException(
                    'cannot find kmahjongglib/backgrounds/%s for %s' % \
                        (graphName, self.desktopFileName )))

    def pixmap(self, size):
        """returns a background pixmap or None for isPlain"""
        self.__pmap = None
        if not self.isPlain:
            width = size.width()
            height = size.height()
            if self.tiled:
                width = self.imageWidth
                height = self.imageHeight
            cachekey = QString("%1W%2H%3") \
                .arg(self.name).arg(width).arg(height)
            self.__pmap = QPixmapCache.find(cachekey)
            if not self.__pmap:
                renderer = QSvgRenderer(self.__graphicspath)
                if not renderer.isValid():
                    logException(BackgroundException( \
                    m18n('file <filename>%1</filename> contains no valid SVG', self.__graphicspath)))
                self.__pmap = QPixmap(width, height)
                self.__pmap.fill(Qt.transparent)
                painter = QPainter(self.__pmap)
                renderer.render(painter)
                QPixmapCache.insert(cachekey, self.__pmap)
        return self.__pmap

    def brush(self, size):
        """background brush"""
        return QBrush(self.pixmap(size))

    def setPalette(self, onto):
        """sets a background palette for widget onto"""
        palette = QPalette()
        mybrush = self.brush(onto.size())
        palette.setBrush(QPalette.Window, mybrush)
        onto.setPalette(palette)
