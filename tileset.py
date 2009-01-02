"""
Authors of original libkmahjongg in C++:
    Copyright (C) 1997 Mathias Mueller   <in5y158@public.uni-hamburg.de>
    Copyright (C) 2006 Mauricio Piacentini  <mauricio@tabuleiro.com>

this adapted python code:
    Copyright (C) 2008 Wolfgang Rohdewald <wolfgang@rohdewald.de>

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
from PyQt4.QtCore import QString,  QPointF,  QRectF,  QSize,  QSizeF
from PyQt4.QtGui import QPainter
from PyKDE4 import kdecore, kdeui
from PyKDE4.kdecore import i18n

TILESETVERSIONFORMAT = 1

class TileException(Exception): 
    """will be thrown if the tileset cannot be loaded"""
    pass
    
class TilesetMetricsData(object):
    """helper class holding tile size"""
    def __init__(self):
        self.tileSize = QSizeF()    # ( +border +shadow)
        self.faceSize = QSizeF()
        
    def shadowWidth(self):
        """the size of border plus shadow"""
        return self.tileSize.width() - self.faceSize.width()
    
    def shadowHeight(self):
        """the size of border plus shadow"""
        return self.tileSize.height() - self.faceSize.height()
    
    def shadowSize(self):
        """the size of border plus shadow"""
        return QSizeF(self.shadowWidth(), self.shadowHeight())
        
    def computeFaceSize(self, unscaled):
        """as the name says."""
        ratio = float( self.tileSize.width()) / float(unscaled.tileSize.width())
        width = int(unscaled.faceSize.width() * ratio)
        ratio = float( self.tileSize.height()) / float(unscaled.tileSize.height())
        height = int(unscaled.faceSize.height() * ratio)
        if width == 0 or height == 0:
            print 'computeFaceSize: width is 0', self.tileSize, \
                unscaled.tileSize, unscaled.faceSize  
            raise TileException('face width 0')
        self.faceSize = QSizeF(width, height)
        
def locateTileset(which):
    """locate the file with a tileset"""
    return QtCore.QString(kdecore.KStandardDirs.locate("kmahjonggtileset", 
                QtCore.QString(which)))

class Tileset(object):
    """represents a complete tileset"""
    catalogDefined = False
      
    @staticmethod
    def defineCatalog():
        """whatever this does"""
        if not Tileset.catalogDefined:
            kdecore.KGlobal.dirs().addResourceType("kmahjonggtileset", 
                "data", QtCore.QString.fromLatin1("kmahjongglib/tilesets"))
            kdecore.KGlobal.locale().insertCatalog("libkmahjongglib")
            Tileset.catalogDefined = True
    
    @staticmethod
    def tilesAvailable():
        """returns all available tile sets"""
        Tileset.defineCatalog()
        tilesAvailableQ = kdecore.KGlobal.dirs().findAllResources(
            "kmahjonggtileset", "*.desktop", kdecore.KStandardDirs.Recursive)
        # now we have a list of full paths. Use the base name minus .desktop:
        return [Tileset(str(x).rsplit('/')[-1].split('.')[0]) for x in tilesAvailableQ ]
    
    def __init__(self, desktopFileName='default'):
        self.sizeIncrement = 10
        self.unscaled = TilesetMetricsData()
        self.minimum = TilesetMetricsData()
        self.scaled = TilesetMetricsData()
        self.__svg = None
        self.defineCatalog()
        self.path = locateTileset(desktopFileName + '.desktop')
        if self.path.isEmpty():
            self.path = locateTileset('default.desktop')
            if self.path.isEmpty():
                raise TileException(i18n('cannot find any tileset, is libkmahjongg installed?'))
            else:
                print 'cannot find tileset %s, using default' % desktopFileName
                self.desktopFileName = 'default'
        else:
            self.desktopFileName = desktopFileName
        tileconfig = kdecore.KConfig(self.path, kdecore.KConfig.SimpleConfig)
        group = kdecore.KConfigGroup(tileconfig.group("KMahjonggTileset"))
        
        self.name = group.readEntry("Name",  "unknown tileset") # Returns translated data
        self.author = group.readEntry("Author",  "unknown author")
        self.description = group.readEntry("Description",  "no description available")
        self.authorEmail = group.readEntry("AuthorEmail",  "no E-Mail address available")
        
        #Version control
        tileversion,  entryOK = group.readEntry("VersionFormat", QtCore.QVariant(0)).toInt()
        #Format is increased when we have incompatible changes, meaning that
        # older clients are not able to use the remaining information safely
        if not entryOK or tileversion > TILESETVERSIONFORMAT:
            raise TileException('tileversion file / program: %d/%d' %  \
                (tileversion,  TILESETVERSIONFORMAT))
        
        graphName = QtCore.QString(group.readEntry("FileName"))
        self.__graphicspath = locateTileset(graphName)
        if self.__graphicspath.isEmpty():
            raise TileException('cannot find kmahjongglib/tilesets/%s for %s' % \
                        (graphName,  self.desktopFileName ))
        
        width,  entryOK = group.readEntry("TileWidth", QtCore.QVariant(30)).toInt()
        height,  entryOK = group.readEntry("TileHeight", QtCore.QVariant(50)).toInt()
        self.unscaled.tileSize = QSize(width, height)
        width,  entryOK = group.readEntry("TileFaceWidth", QtCore.QVariant(30)).toInt()
        height,  entryOK = group.readEntry("TileFaceHeight", QtCore.QVariant(50)).toInt()
        self.unscaled.faceSize = QSize(width, height)
        self.updateScaleInfo(self.unscaled.tileSize)
        self.minimum.tileSize = QSize(float(width/4), float(height/4))
        self.minimum.computeFaceSize(self.unscaled)


    def updateScaleInfo(self, tileSize):
        """update tile sizes"""
        if self.scaled.tileSize != tileSize:
            self.scaled.tileSize = tileSize
            self.scaled.computeFaceSize(self.unscaled)

    def width(self):
        """current tile width"""
        return self.scaled.tileSize.width()

    def height(self):
        """current tile height"""
        return self.scaled.tileSize.height()

    def initSvgRenderer(self):
        """initialize the svg renderer with the selected svg file"""
        if self.__svg is None:
            self.__svg = kdeui.KSvgRenderer(self.__graphicspath)
            if not self.__svg.isValid():
                raise TileException(i18n('file %1 contains no valid SVG').arg(self.__graphicspath))
        
    def tilePixmap(self,  element, angle, rotation,  selected=False):
        """returns a complete pixmap of the tile with correct borders.
        If element is None, returns an empty pixmap.
        If element is an empty string, returns a faceless tile
        angle: 1 = topright, 2 = topleft, 3 = bottomleft, 4 = bottomright"""
        if element is None:
            size = QSize(self.scaled.tileSize)
            if rotation % 180 != 0:
                size.transpose()
            pmap = QtGui.QPixmap(size)
            pmap.fill(QtCore.Qt.transparent)
            return pmap
        cachekey = QtCore.QString("%1%2A%3W%4H%5S%6R%7") \
            .arg(self.name).arg(element) \
            .arg(angle).arg(self.scaled.tileSize.width()) \
            .arg(self.scaled.tileSize.height()).arg(selected)\
            .arg(rotation)
        pmap = QtGui.QPixmapCache.find(cachekey)
        if not pmap:
            self.initSvgRenderer()
            if rotation % 180 == 0:
                tileName = QString("TILE_%1").arg(angle)
            else:
                tileName = QString("TILE_%1").arg(angle%4+1)
            if selected:
                tileName += '_SEL'
            size = QSize(self.scaled.tileSize)
            tileRect = QRectF(QPointF(0, 0), QSizeF(size))
            if rotation % 180 != 0:
                size.transpose()
            pmap = QtGui.QPixmap(size)
            pmap.fill(QtCore.Qt.transparent)
            painter = QPainter(pmap)
            if rotation % 180 != 0:
                painter.rotate(90)
                painter.translate(0, -size.width())
            self.__svg.render(painter,  tileName, tileRect)
            if element != "":
                self.renderFace(painter, element, angle,  rotation)
                painter.end()
            QtGui.QPixmapCache.insert(cachekey, pmap)
        return pmap

    def renderFace(self, painter, element, angle, rotation):
        """render the tile face"""
        faceSize = QSizeF(self.scaled.faceSize)
        facerect = QRectF(QPointF(0.0, 0.0), faceSize)
        painter.resetMatrix()
        painter.rotate(rotation)
        shadowW = self.scaled.shadowWidth()
        shadowH = self.scaled.shadowHeight()
        faceH = faceSize.height()
        faceW = faceSize.width()
        if rotation % 90 != 0 or rotation < 0 or rotation > 270:
            raise TileException('illegal rotation'+str(rotation))
        offsets = [[(shadowW, 0), (0, -faceH-shadowH), (-faceW-shadowW, -faceH), 
                        (-faceW, shadowH)], 
                    [(0, 0), (0, -faceH), (-faceW, -faceH), (-faceW, 0)], 
                    [(0, shadowH), (shadowW, -faceH), (-faceW, -faceH-shadowH),
                        (-faceW-shadowW, 0)], 
                    [(shadowW, shadowH), (shadowW, -faceH-shadowH), 
                        (-faceW-shadowW, -faceH-shadowH), (-faceW-shadowW, shadowH)]]
        painter.translate(*offsets[int(angle-1)][int(rotation/90)])
        self.__svg.render(painter, QString('%1').arg(element), facerect)
