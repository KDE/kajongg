# -*- coding: utf-8 -*-
"""
Copyright (C) 2010-2016 Wolfgang Rohdewald <wolfgang@rohdewald.de>

partially based on C++ code from:
Copyright (C) 2006 Mauricio Piacentini <mauricio@tabuleiro.com>

SPDX-License-Identifier: GPL-2.0-only

"""

from typing import TYPE_CHECKING, Optional, List, Any, Type, Tuple, Dict, Sequence

from qt import QComboBox, QTableView, QSizePolicy, QAbstractItemView
from qt import QTransform

from kde import KIcon

from log import i18n

if TYPE_CHECKING:
    from qt import QObject, QWidget, QPainter, QGraphicsItem
    from rule import Ruleset


class MJTableView(QTableView):

    """a QTableView with app specific defaults"""

    def __init__(self, parent:Optional['QWidget']=None) ->None:
        QTableView.__init__(self, parent)
        if header := self.horizontalHeader():
            header.setStretchLastSection(True)
        self.setAlternatingRowColors(True)
        pol = QSizePolicy()
        pol.setHorizontalPolicy(QSizePolicy.Policy.Expanding)
        pol.setVerticalPolicy(QSizePolicy.Policy.Expanding)
        self.setSizePolicy(pol)
        if header := self.verticalHeader():
            header.hide()

    def initView(self) ->None:
        """set some app specific defaults"""
        self.selectRow(0)
        self.resizeColumnsToContents()
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)


class ListComboBox(QComboBox):

    """easy to use with a python list. The elements must have an
    attribute 'name'."""

    def __init__(self, items:List[Any], parent:Optional['QWidget']=None) ->None:
        QComboBox.__init__(self, parent)
        self.items = items

    @property
    def items(self) ->List[Any]:
        """combo box items"""
        return [self.itemData(idx) for idx in range(self.count())]

    @items.setter
    def items(self, items:List['Ruleset']) ->None:
        """combo box items"""
        self.clear()
        if items:
            for item in items:
                self.addItem(i18n(item.name), item)

    def findItem(self, search:Any) ->int:
        """return the index or -1 of not found """
        for idx, item in enumerate(self.items):
            if item == search:
                return idx
        return -1

    def names(self) ->List[str]:
        """a list with all item names"""
        return list(x.name for x in self.items)

    @property
    def current(self) ->Any:
        """current item"""
        return self.itemData(self.currentIndex())

    @current.setter
    def current(self, item:Any) ->None:
        """current item"""
        newIdx = self.findItem(item)
        if newIdx < 0:
            raise IndexError(f'{item.name} not found in ListComboBox')
        self.setCurrentIndex(newIdx)


class Painter:

    """a helper class for painting: saves/restores painter"""

    def __init__(self, painter:'QPainter') ->None:
        """painter is the painter to be saved/restored"""
        self.painter = painter

    def __enter__(self) ->'Painter':
        self.painter.save()
        return self

    def __exit__(self, exc_type:Type[Exception], exc_value:Exception, trback:Any) ->None:
        """now check time passed"""
        self.painter.restore()


class BlockSignals:

    """a helper class for temporary blocking of Qt signals"""

    def __init__(self, qobjects:Sequence['QObject']) ->None:
        self.qobjects = qobjects

    def __enter__(self) ->None:
        for obj in self.qobjects:
            obj.blockSignals(True)

    def __exit__(self, exc_type:Type[Exception], exc_value:Exception, trback:Any) ->None:
        for obj in self.qobjects:
            obj.blockSignals(False)


def decorateWindow(window:'QWidget', name:str='') ->None:
    """standard Kajongg window title and icon"""
    if name:
        window.setWindowTitle(f"{name} – {i18n('kajongg')}")
    else:
        window.setWindowTitle(i18n('Kajongg'))
    window.setWindowIcon(KIcon('kajongg'))


def rotateCenter(item:'QGraphicsItem', angle:float) ->None:
    """rotates a QGraphicsItem around its center
    rotateCenter and sceneRotation could be a mixin class but there are so many
    classes needing this. If and when more QGraphicsItem* classes are changed
    to QGraphicsObject, those could be moved to GraphicsObject(QGraphicsObject)"""
    center = item.boundingRect().center()
    centerX, centerY = center.x() * item.scale(), center.y() * item.scale()
    item.setTransform(QTransform().translate(
        centerX, centerY).rotate(angle).translate(-centerX, -centerY))

def sceneRotation(item:'QGraphicsItem') ->int:
    """the combined rotation of item and all parents in degrees: 0,90,180 or 270"""
    transform = item.sceneTransform()
    matrix:Tuple[int, ...] = (
        round(transform.m11()),
        round(transform.m12()),
        round(transform.m21()),
        round(transform.m22()))
    matrix = tuple(1 if x > 0 else -1 if x < 0 else 0 for x in matrix)
    rotations:Dict[Tuple[int, ...], int] = {(0, 0, 0, 0): 0, (1, 0, 0, 1): 0, (
        0, 1, -1, 0): 90, (-1, 0, 0, -1): 180, (0, -1, 1, 0): 270}
    if matrix not in rotations:
        raise ValueError(f'matrix unknown:{str(matrix)}')
    return rotations[matrix]
