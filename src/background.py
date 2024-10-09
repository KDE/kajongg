"""
Authors of original libkmahjongg in C++:
    Copyright (C) 1997 Mathias Mueller <in5y158@public.uni-hamburg.de>
    Copyright (C) 2006 Mauricio Piacentini <mauricio@tabuleiro.com>

this python code:
    Copyright (C) 2008-2016 Wolfgang Rohdewald <wolfgang@rohdewald.de>

SPDX-License-Identifier: GPL-2.0

"""

from typing import TYPE_CHECKING, Optional


from qt import Qt, QPainter, QBrush, QPalette, QPixmapCache, QPixmap
from qt import QSvgRenderer

from log import logException, i18n
from mjresource import Resource

if TYPE_CHECKING:
    from qt import QWidget, QSize

class Background(Resource):

    """represents a background"""

    resourceName = 'background'
    configGroupName = 'KMahjonggBackground'
    cache = {}

    def __init__(self, name:Optional[str]=None) ->None:
        """continue __build"""
        super().__init__(name)
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
            assert isinstance(graphName, str)
            self.graphicsPath = self.locate(graphName)
            if not self.graphicsPath:
                logException(
                    f'cannot find kmahjongglib/backgrounds/{graphName} for {self.desktopFileName}')

    def __pixmap(self, size:'QSize') ->QPixmap:
        """return a background pixmap"""
        if self.isPlain:
            return QPixmap()
        width = size.width()
        height = size.height()
        if self.tiled:
            width = self.imageWidth
            height = self.imageHeight
        cachekey = f'{self.name}W{width}H{height}'
        result = QPixmapCache.find(cachekey)  # type:ignore[call-overload]
        if not result:
            renderer = QSvgRenderer(self.graphicsPath)
            if not renderer.isValid():
                logException(
                    i18n('file <filename>%1</filename> contains no valid SVG', self.graphicsPath))
            result = QPixmap(int(width), int(height))
            result.fill(Qt.GlobalColor.transparent)
            painter = QPainter(result)
            renderer.render(painter)
            QPixmapCache.insert(cachekey, result)
        return result

    def brush(self, size:'QSize') ->QBrush:
        """background brush"""
        return QBrush(self.__pixmap(size))

    def setPalette(self, onto:'QWidget') ->None:
        """set a background palette for widget onto"""
        palette = QPalette()
        mybrush = self.brush(onto.size())
        palette.setBrush(QPalette.ColorRole.Window, mybrush)
        onto.setPalette(palette)
