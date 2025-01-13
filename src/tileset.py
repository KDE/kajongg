# -*- coding: utf-8 -*-

"""
Authors of original libkmahjongg in C++:
    Copyright (C) 1997 Mathias Mueller <in5y158@public.uni-hamburg.de>
    Copyright (C) 2006 Mauricio Piacentini <mauricio@tabuleiro.com>

this adapted python code:
    Copyright (C) 2008-2016 Wolfgang Rohdewald <wolfgang@rohdewald.de>

SPDX-License-Identifier: GPL-2.0-only

"""

from typing import Optional, List, Tuple

from qt import QSizeF, QSvgRenderer
from log import logException, i18n
from mjresource import Resource

from common import LIGHTSOURCES, Internal, ReprMixin


class Tileset(Resource, ReprMixin):

    """represents a complete tileset"""

    resourceName : Optional[str] = 'tileset'
    configGroupName : str = 'KMahjonggTileset'

    def __init__(self, name:Optional[str]=None) ->None:
        """continue __build"""
        super().__init__(name)
        self.tileSize:QSizeF
        self.faceSize:QSizeF
        self.__shadowOffsets:List[List[Tuple[int,int]]]
        self.darkenerAlpha = 120 if self.desktopFileName == 'jade' else 50

        graphName = str(self.group.readEntry("FileName"))
        self.graphicsPath = Tileset.locate(graphName)
        if not self.graphicsPath:
            logException(
                f'cannot find kmahjongglib/tilesets/{graphName} for {self.desktopFileName}')
        self.renderer = QSvgRenderer(self.graphicsPath)
        if not self.renderer.isValid():
            logException(
                i18n(
                    'file <filename>%1</filename> contains no valid SVG',
                self.graphicsPath))
        distance = 0
        if self.desktopFileName == 'classic':
            distance = 2
        distanceSize = QSizeF(distance, distance)
        self.faceSize = self.renderer.boundsOnElement('BAMBOO_1').size()
        self.faceSize += distanceSize
        self.tileSize = self.renderer.boundsOnElement('TILE_2').size()
        self.tileSize += distanceSize
        shW = self.shadowWidth()
        shH = self.shadowHeight()
        self.__shadowOffsets = [
            [(-shW, 0), (0, 0), (0, shH), (-shH, shW)],
            [(0, 0), (shH, 0), (shW, shH), (0, shW)],
            [(0, -shH), (shH, -shW), (shW, 0), (0, 0)],
            [(-shW, -shH), (0, -shW), (0, 0), (-shH, 0)]]

        self.svgName = {
            'wn': 'WIND_1', 'ws': 'WIND_2', 'we': 'WIND_3', 'ww': 'WIND_4',
            'db': 'DRAGON_1', 'dg': 'DRAGON_2', 'dr': 'DRAGON_3'}
        for value in '123456789':
            self.svgName[f's{value}'] = f'ROD_{value}'
            self.svgName[f'b{value}'] = f'BAMBOO_{value}'
            self.svgName[f'c{value}'] = f'CHARACTER_{value}'
        for idx, wind in enumerate('eswn'):
            self.svgName[f'f{wind}'] = f'FLOWER_{int(idx + 1)}'
            self.svgName[f'y{wind}'] = f'SEASON_{int(idx + 1)}'

    def __str__(self) ->str:
        return self.desktopFileName

    @staticmethod
    def current() ->'Tileset':
        """the currently wanted tileset. If not yet defined, do so"""
        assert Internal.Preferences
        return Tileset(str(Internal.Preferences.tilesetName))

    def shadowWidth(self) ->int:
        """the size of border plus shadow"""
        return int(self.tileSize.width() - self.faceSize.width())

    def shadowHeight(self) ->int:
        """the size of border plus shadow"""
        return int(self.tileSize.height() - self.faceSize.height())

    def shadowOffsets(self, lightSource:str, rotation:int) ->Tuple[int, int]:
        """real offset of the shadow on the screen"""
        assert Internal.Preferences
        if not Internal.Preferences.showShadows:
            return (0, 0)
        lightSourceIndex = LIGHTSOURCES.index(lightSource)
        return self.__shadowOffsets[lightSourceIndex][rotation // 90]

    def tileFaceRelation(self) ->Tuple[float,float]:
        """return how much bigger the tile is than the face"""
        return (self.tileSize.width() / self.faceSize.width(),
                self.tileSize.height() / self.faceSize.height())
