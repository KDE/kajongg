"""
Authors of original libkmahjongg in C++:
    Copyright (C) 1997 Mathias Mueller <in5y158@public.uni-hamburg.de>
    Copyright (C) 2006 Mauricio Piacentini <mauricio@tabuleiro.com>

this python code:
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
"""

from qt import Qt, QPainter, QBrush, QPalette, QPixmapCache, QPixmap
from qt import QSvgRenderer

from log import logException, i18n
from mjresource import Resource


class Background(Resource):

    """represents a background"""

    resourceName = 'background'
    configGroupName = 'KMahjonggBackground'
    cache = {}

    def __init__(self, name):
        """continue __build"""
        super(Background, self).__init__(name)
        self.__svg = None
        self.__pmap = None
        self.graphicsPath = None
        QPixmapCache.setCacheLimit(20480)  # the chinese landscape needs much

        self.tiled = self.group.readEntry('Tiled') == '1'
        if self.tiled:
            try:
                self.imageWidth = self.group.readInteger('Width')
                self.imageHeight = self.group.readInteger('Height')
            except Exception as exc:
                logException(exc)  # TODO: simplify if we switch to twisted logger
                raise
        self.isPlain = bool(self.group.readEntry('Plain'))
        if not self.isPlain:
            graphName = self.group.readEntry("FileName")
            self.graphicsPath = self.locate(graphName)
            if not self.graphicsPath:
                logException(
                    'cannot find kmahjongglib/backgrounds/%s for %s' %
                    (graphName, self.desktopFileName))

    def pixmap(self, size):
        """returns a background pixmap or None for isPlain"""
        self.__pmap = QBrush()
        if not self.isPlain:
            width = size.width()
            height = size.height()
            if self.tiled:
                width = self.imageWidth
                height = self.imageHeight
            cachekey = '{name}W{width}H{height}'.format(name=self.name, width=width, height=height)
            self.__pmap = QPixmapCache.find(cachekey)
            if not self.__pmap:
                renderer = QSvgRenderer(self.graphicsPath)
                if not renderer.isValid():
                    logException(
                        i18n('file <filename>%1</filename> contains no valid SVG', self.graphicsPath))
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
