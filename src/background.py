"""
Authors of original libkmahjongg in C++:
    Copyright (C) 1997 Mathias Mueller <in5y158@public.uni-hamburg.de>
    Copyright (C) 2006 Mauricio Piacentini <mauricio@tabuleiro.com>

this python code:
    Copyright (C) 2008-2016 Wolfgang Rohdewald <wolfgang@rohdewald.de>

SPDX-License-Identifier: GPL-2.0

"""

from typing import TYPE_CHECKING, Union, Optional


from qt import Qt, QPainter, QBrush, QPalette, QPixmapCache, QPixmap
from qt import QSvgRenderer

from log import logException, i18n
from mjresource import Resource

if TYPE_CHECKING:
    from qt import QSizeF

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
                    'cannot find kmahjongglib/backgrounds/%s for %s' %
                    (graphName, self.desktopFileName))

    def pixmap(self, size:'QSizeF') ->Union[QBrush, QPixmap]:
        """return a background pixmap or None for isPlain"""
        self.__pmap = QBrush()  # pylint:disable=attribute-defined-outside-init
        if not self.isPlain:
            width = size.width()
            height = size.height()
            if self.tiled:
                width = self.imageWidth
                height = self.imageHeight
            cachekey = '{name}W{width}H{height}'.format(name=self.name, width=width, height=height)
            self.__pmap = QPixmapCache.find(cachekey)  # pylint:disable=attribute-defined-outside-init
            if not self.__pmap:
                renderer = QSvgRenderer(self.graphicsPath)
                if not renderer.isValid():
                    logException(
                        i18n('file <filename>%1</filename> contains no valid SVG', self.graphicsPath))
                self.__pmap = QPixmap(width, height)  # pylint:disable=attribute-defined-outside-init
                self.__pmap.fill(Qt.GlobalColor.transparent)
                painter = QPainter(self.__pmap)
                renderer.render(painter)
                QPixmapCache.insert(cachekey, self.__pmap)
        return self.__pmap

    def brush(self, size:'QSizeF') ->QBrush:
        """background brush"""
        return QBrush(self.pixmap(size))

    def setPalette(self, onto:QBrush) ->None:
        """set a background palette for widget onto"""
        palette = QPalette()
        mybrush = self.brush(onto.size())
        palette.setBrush(QPalette.Window, mybrush)
        onto.setPalette(palette)
