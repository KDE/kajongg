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
from PyKDE4 import kdecore, kdeui

TILESETVERSIONFORMAT = 1

class TileException(Exception): 
    """will be thrown if the tileset cannot be loaded"""
    pass
    
class TilesetMetricsData(object):
    """helper class holding tile size"""
    def __init__(self):
        self.tilewidth = 0    # ( +border +shadow)
        self.tileheight = 0   # ( +border +shadow)
        self.facewidth = 0
        self.faceheight = 0
    
    def rowWidth(self, xsize):
        """the width of xsize tiles glued together horizontally"""
        return float(self.facewidth * (xsize - 1) + self.tilewidth) 
        
    def colHeight(self, ysize):
        """the width of ysize tiles glued together vertically"""
        return float(self.faceheight * (ysize - 1) + self.tileheight)

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
        self.__originaldata = TilesetMetricsData()
        self.__scaleddata = TilesetMetricsData()
        self.__svg = None
        self.defineCatalog()
        self.path = locateTileset(desktopFileName + '.desktop')
        if self.path.isEmpty():
            self.path = locateTileset('default.desktop')
            if self.path.isEmpty():
                raise TileException('cannot find any tileset, is libkmahjongg installed?')
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
        
        self.__originaldata.tilewidth,  entryOK = \
            group.readEntry("TileWidth", QtCore.QVariant(30)).toInt()
        self.__originaldata.tileheight,  entryOK = \
            group.readEntry("TileHeight", QtCore.QVariant(50)).toInt()
        self.__originaldata.facewidth,  entryOK = \
            group.readEntry("TileFaceWidth", QtCore.QVariant(30)).toInt()
        self.__originaldata.faceheight,  entryOK = \
            group.readEntry("TileFaceHeight", QtCore.QVariant(50)).toInt()
        self.updateScaleInfo(self.__originaldata.tilewidth, self.__originaldata.tileheight)

    def updateScaleInfo(self, tilew, tileh):
        """update tile sizes"""
        if self.__scaleddata.tilewidth != tilew or self.__scaleddata.tileheight != tileh:
            self.__scaleddata.tilewidth = tilew
            self.__scaleddata.tileheight = tileh
            ratio = float( self.__scaleddata.tilewidth) / float(self.__originaldata.tilewidth)
            self.__scaleddata.facewidth = int(self.__originaldata.facewidth * ratio)
            ratio = float( self.__scaleddata.tileheight) / float(self.__originaldata.tileheight)
            self.__scaleddata.faceheight = int(self.__originaldata.faceheight * ratio)

    def preferredTileSize(self, boardsize, horizontalCells, verticalCells):
        """calculate our best tile size to fit the boardsize passed to us"""
        bwidth = float(int(boardsize.width() / self.sizeIncrement) * self.sizeIncrement)
        bheight = float(int(boardsize.height() / self.sizeIncrement) * self.sizeIncrement)
        fullw = self.__originaldata.rowWidth(horizontalCells)
        fullh = self.__originaldata.colHeight(verticalCells)
        aspectratio = bwidth / fullw if fullw / fullh > bwidth / bheight else bheight / fullh
        newtilew = int(aspectratio * self.__originaldata.tilewidth)
        newtileh = int(aspectratio * self.__originaldata.tileheight)
        return QtCore.QSize(newtilew, newtileh)
    
    def width(self):
        """current tile width"""
        return self.__scaleddata.tilewidth

    def height(self):
        """current tile height"""
        return self.__scaleddata.tileheight

    def faceWidth(self):
        """current face width"""
        return self.__scaleddata.facewidth

    def faceHeight(self):
        """current face height"""
        return self.__scaleddata.faceheight

    def rowWidth(self,  rows):
        """current row width"""
        return self.__scaleddata.rowWidth(rows)

    def colHeight(self,  cols):
        """current column height"""
        return self.__scaleddata.colHeight(cols)

    def gridSize(self,  rows,  cols):
        """current grid size"""
        return QtCore.QSize(self.rowWidth(rows), self.colHeight(cols))
        
    def renderElement(self, elementid, width, height):
        """make a pixmap from the svg image"""
        if self.__svg is None:
            self.__svg = kdeui.KSvgRenderer(self.__graphicspath)
            if not self.__svg.isValid():
                raise TileException('file %s contains no valid SVG' % self.__graphicspath)
        pmap = QtGui.QPixmap(width, height)
        pmap.fill(QtCore.Qt.transparent)
        self.__svg.render(QtGui.QPainter(pmap), elementid)
        return pmap

    def tile(self,  element, angle, selected=False):
        """returns a complete pixmap of the tile with correct borders"""
        cachekey = QtCore.QString("%1%2A%3W%4H%5S%6") \
            .arg(self.name).arg(element) \
            .arg(angle).arg(self.__scaleddata.tilewidth) \
            .arg(self.__scaleddata.tileheight).arg(selected)
        pmap = QtGui.QPixmapCache.find(cachekey)
        if not pmap:
            tilename = "TILE_"+str(angle)
            pmap = self.selectedTile(tilename) if selected else self.unselectedTile(tilename)
            painter = QtGui.QPainter(pmap)
            xoffset = self.__scaleddata.tilewidth - self.__scaleddata.facewidth \
                if angle == 1 or angle == 4 else 0
            yoffset = self.__scaleddata.tileheight - self.__scaleddata.faceheight \
                if angle >= 3 else 0
            painter.drawPixmap(xoffset, yoffset, self.face(element))
            QtGui.QPixmapCache.insert(cachekey, pmap)
        return pmap

    def selectedTile(self, element):
        """returns a selected tile without face"""
        return self.unselectedTile(QtCore.QString('%1_SEL').arg(element))

    def unselectedTile(self, element):
        """returns an unselected tile without face"""
        return self.renderElement(QtCore.QString('%1').arg(element),
                    self.__scaleddata.tilewidth, self.__scaleddata.tileheight)

    def face(self, element):
        """returns the face for a tile"""
        return self.renderElement(QtCore.QString('%1').arg(element),
                    self.__scaleddata.facewidth, self.__scaleddata.faceheight)
