# -*- coding: utf-8 -*-

"""
 (C) 2010 Wolfgang Rohdewald <wolfgang@rohdewald.de>

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
Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.
"""

from PyQt4.QtCore import QPropertyAnimation, QParallelAnimationGroup, \
    QSequentialAnimationGroup, QAbstractAnimation, QEasingCurve,  \
    SIGNAL

from common import InternalParameters, PREF, ZValues
from util import debugMessage

class Animation(QPropertyAnimation):
    """a Qt4 animation with helper methods"""
    def __init__(self, target, propName, endValue, parent=None):
        QPropertyAnimation.__init__(self, target, propName, parent)
        self.setEndValue(endValue)
        duration = (99 - PREF.animationSpeed) * 100 / 4
        self.setDuration(duration)
        self.setEasingCurve(QEasingCurve.InOutQuad)

    def ident(self):
        """the identifier to be used in debug messages"""
        pGroup = self.group()
        if pGroup:
            sGroup = pGroup.group()
            groupIdx = sGroup.children().index(pGroup)
            return '%d/%d' % (id(sGroup)%10000, groupIdx)
        else:
            return 'A%d' % (id(self) % 10000)

    def __str__(self):
        """for debug messages"""
        pName = self.propertyName()
        tile = self.targetObject()
        if pName == 'pos':
            value = self.endValue().toPointF()
            value = '%.1f/%.1f' % (value.x(), value.y())
        elif pName == 'rotation':
            value = '%d' % self.endValue().toInt()[0]
        elif pName == 'scale':
            value = '%.2f' % self.endValue().toFloat()[0]
        return '%s: %s->%s for %s' % (self.ident(), pName, value, str(tile))

class ParallelAnimationGroup(QParallelAnimationGroup):
    """override __init__"""
    def __init__(self, animations, parent=None):
        QParallelAnimationGroup.__init__(self, parent)
        for animation in animations:
            self.addAnimation(animation)

class SequentialAnimationGroup(QSequentialAnimationGroup):
    """the Qt4 class with helper methods and a deferred callback.
    The structure to be expected is: The SequentialAnimationGroup
    holds only ParallelAnimationsGroups which hold only Animation items
    """
    def __init__(self, animations, deferred, parent=None):
        QSequentialAnimationGroup.__init__(self, parent)
        self.deferred = deferred
        if not animations:
            self.callDeferred()
            return
        for group in animations:
            self.addAnimation(group)
            for animation in group.children():
                # we cannot do this in Animation.__init__ because
                # there might be some setDrawingOrder() interfering
                tile = animation.targetObject()
                tile.setZValue(tile.zValue() + ZValues.moving)
        self.connect(self, SIGNAL('finished()'), self.allFinished)
        InternalParameters.field.centralScene.focusRect.hide()
        self.start(QAbstractAnimation.KeepWhenStopped)
        if self.state() != QAbstractAnimation.Running:
            # this happens if a player claims a tile for mah jongg.
            # I have no idea why - wait for a Qt update, maybe that
            # fixes it...
            debugMessage('CANNOT ANIMATE %d!'% (id(self)%10000))
            self.fixAnimations()
            self.fixAllBoards()
            self.callDeferred()

    def callDeferred(self):
        """if we have a deferred, callback now and make sure we dont call again"""
        if self.deferred:
            deferred = self.deferred
            self.deferred = None
            deferred.callback('done')

    def fixAnimations(self):
        """if the animation did not succeed, fix the end values."""
        animations = sum([x.children() for x in self.children()], [])
        tilesFixed = set()
        for animation in animations:
            groupIdx = self.children().index(animation.group())
            ident = '%d/%d' % (id(self)%10000, groupIdx)
            tile = animation.targetObject()
            if tile not in tilesFixed:
                tilesFixed.add(tile)
                newPos, newRotation, newScale = tile.board.tilePlace(tile)
                if newPos != tile.pos():
                    debugMessage('Fixing pos to %.1f/%.1f after animation %s' % \
                        (newPos.x(), newPos.y(), str(animation)))
                    tile.setPos(newPos)
                if newRotation != tile.rotation():
                    debugMessage('After animation %s, fixing rotation to %d for tile %s' % \
                        (ident, newRotation, str(tile)))
                    tile.setRotation(newRotation)
                if int(newScale*100) != int(tile.scale()*100):
                    debugMessage('After animation %s, fixing scale to %.2f for tile %s' % \
                        (ident, newScale, str(tile)))
                    tile.setScale(newScale)

    def allFinished(self):
        """all animations have finished. Cleanup and callback"""
        self.fixAnimations()
        self.fixAllBoards()
        self.callDeferred()

    def fixAllBoards(self):
        """set correct drawing order for all changed boards"""
        animations = sum([x.children() for x in self.children()], [])
        boards = list(x.targetObject().board for x in animations)
        boardsFixed = set()
        for board in boards:
            if board not in boardsFixed:
                boardsFixed.add(board)
                board.setDrawingOrder()# TODO: how often do we really need to call it?
        InternalParameters.field.centralScene.placeFocusRect()
