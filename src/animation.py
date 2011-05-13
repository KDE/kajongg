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
Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301, USA.
"""

from twisted.internet.defer import Deferred, succeed

from PyQt4.QtCore import QPropertyAnimation, QParallelAnimationGroup, \
    QAbstractAnimation, QEasingCurve, SIGNAL

from common import InternalParameters, PREF, Debug
from util import logDebug, isAlive

class Animation(QPropertyAnimation):
    """a Qt4 animation with helper methods"""

    nextAnimations = []

    def __init__(self, target, propName, endValue, parent=None):
        QPropertyAnimation.__init__(self, target, propName, parent)
        QPropertyAnimation.setEndValue(self, endValue)
        duration = (99 - PREF.animationSpeed) * 100 // 4
        self.setDuration(duration)
        self.setEasingCurve(QEasingCurve.InOutQuad)
        target.queuedAnimations.append(self)
        Animation.nextAnimations.append(self)
        if target.element in Debug.animation:
            oldAnimation = target.activeAnimation.get(propName, None)
            if isAlive(oldAnimation):
                logDebug('new animation %s (after %s is done)' % (self, oldAnimation.ident()))
            else:
                logDebug('new animation %s' % self)

    def setEndValue(self, endValue):
        """wrapper with debugging code"""
        tile = self.targetObject()
        if tile.element in Debug.animation:
            pName = self.pName()
            logDebug('%s: change endValue for %s: %s->%s  %s' % (self.ident(), pName, self.formatValue(self.endValue()),
                    self.formatValue(endValue), str(tile)))
        QPropertyAnimation.setEndValue(self, endValue)

    def ident(self):
        """the identifier to be used in debug messages"""
        pGroup = self.group()
        if pGroup:
            return '%d/A%d' % (id(pGroup)%10000, id(self) % 10000)
        else:
            return 'A%d' % (id(self) % 10000)

    def pName(self):
        """return self.propertyName() as a python string"""
        return str(self.propertyName())

    def unpackValue(self, qvariant):
        """get the wanted value from the QVariant"""
        pName = self.pName()
        if pName == 'pos':
            return qvariant.toPointF()
        if pName == 'rotation':
            return qvariant.toInt()[0]
        elif pName == 'scale':
            return qvariant.toFloat()[0]

    def unpackEndValue(self):
        """unpacked end value"""
        return self.unpackValue(self.endValue())

    def formatValue(self, qvariant):
        """string format the wanted value from qvariant"""
        value = self.unpackValue(qvariant)
        pName = self.pName()
        if pName == 'pos':
            return '%.1f/%.1f' % (value.x(), value.y())
        if pName == 'rotation':
            return '%d' % value
        if pName == 'scale':
            return '%.2f' % value

    def __str__(self):
        """for debug messages"""
        pName = self.pName()
        tile = self.targetObject()
        return '%s: %s->%s for %s' % (self.ident(), pName, self.formatValue(self.endValue()), str(tile))

class ParallelAnimationGroup(QParallelAnimationGroup):
    """override __init__"""

    running = [] # we need a reference to active animation groups
    current = None

    def __init__(self, parent=None):
        QParallelAnimationGroup.__init__(self, parent)
        assert Animation.nextAnimations
        self.animations = Animation.nextAnimations
        Animation.nextAnimations = []
        self.deferred = Deferred()
        self.steps = 0
        self.timerWasActive = False
        self.debug = False
        if ParallelAnimationGroup.current:
            if self.debug or ParallelAnimationGroup.current.debug:
                logDebug('Chaining Animation group %d to %d' % \
                        (id(self), id(ParallelAnimationGroup.current)))
            ParallelAnimationGroup.current.deferred.addCallback(self.start)
        else:
            self.start()
        ParallelAnimationGroup.running.append(self)
        ParallelAnimationGroup.current = self

    def updateCurrentTime(self, value):
        """count how many steps an animation does.
        If the client dialog progress bar is running, stop it until the
        animation is done.
        When the progress bar runs AND tiles move, they sometimes
        leave artifacts near the hand where the client dialog is shown.
        Try to get rid of this workaround with next Qt"""
        self.steps += 1
        QParallelAnimationGroup.updateCurrentTime(self, value)
        if not self.timerWasActive:
            clientDialog = InternalParameters.field.clientDialog
            self.timerWasActive = clientDialog and clientDialog.timer.isActive()
            if self.timerWasActive:
                clientDialog.timer.stop()

    def start(self, dummyResults='DIREKT'):
        """start the animation, returning its deferred"""
        assert self.state() != QAbstractAnimation.Running
        tiles = set()
        for animation in self.animations:
            tile = animation.targetObject()
            self.debug |= tile.element in Debug.animation
            tiles.add(tile)
            tile.setActiveAnimation(animation)
            self.addAnimation(animation)
            propName = animation.pName()
            animation.setStartValue(tile.getValue(propName))
            if propName == 'rotation':
                # change direction if that makes the difference smaller
                endValue = animation.unpackEndValue()
                currValue = tile.rotation
                if endValue - currValue > 180:
                    animation.setStartValue(currValue + 360)
                if currValue - endValue > 180:
                    animation.setStartValue(currValue - 360)
        for tile in tiles:
            tile.graphics.setDrawingOrder()
        self.connect(self, SIGNAL('finished()'), self.allFinished)
        scene = InternalParameters.field.centralScene
        scene.disableFocusRect = True
        QParallelAnimationGroup.start(self, QAbstractAnimation.DeleteWhenStopped)
        if self.debug:
            logDebug('Animation group %d started (%s)' % (
                    id(self), ','.join('A%d' % (id(x) % 10000) for x in self.animations)))
        return succeed(None)

    def allFinished(self):
        """all animations have finished. Cleanup and callback"""
        self.fixAllBoards()
        clientDialog = InternalParameters.field.clientDialog
        if self.timerWasActive:
            clientDialog.timer.start()
        if self == ParallelAnimationGroup.current:
            ParallelAnimationGroup.current = None
            ParallelAnimationGroup.running = []
        if Debug.animationSpeed and self.duration():
            perSecond = self.steps * 1000.0 / self.duration()
            if perSecond < 50:
                logDebug('%d steps for %d animations, %.1f/sec' % \
                (self.steps, len(self.children()), perSecond))
        # if we have a deferred, callback now
        assert self.deferred
        if self.debug:
            logDebug('Animation group %d done' % id(self))
        if self.deferred:
            self.deferred.callback(None)

    def fixAllBoards(self):
        """set correct drawing order for all moved tiles"""
        for animation in self.children():
            tile = animation.targetObject()
            if tile:
                tile.clearActiveAnimation(animation)
        scene = InternalParameters.field.centralScene
        scene.disableFocusRect = False
        return

class Animated(object):
    """a helper class for moving tiles with or without animation"""
    def __init__(self, animateMe=True):
        if PREF:
            self.__animateMe = animateMe
            self.prevAnimationSpeed = PREF.animationSpeed
            if not animateMe:
                PREF.animationSpeed = 99

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, trback):
        """reset previous animation speed"""
        if PREF:
            if not self.__animateMe:
                animate()
                PREF.animationSpeed = self.prevAnimationSpeed


def afterCurrentAnimationDo(callback, *args, **kwargs):
    """a helper, delaying some action until all active
    animations have finished"""
    current = ParallelAnimationGroup.current
    if current:
        current.deferred.addCallback(callback, *args, **kwargs)
        if current.debug:
            logDebug('after current animation %d do %s %s' % \
                (id(current), callback, ','.join(args) if args else ''))
    else:
        callback(None, *args, **kwargs)

def animate():
    """now run all prepared animations. Returns a Deferred
        so callers can attach callbacks to be executed when
        animation is over.
        We do not animate if
             - we are in a tile drag/drop operation
             - the user disabled animation
             - there are too many animations in the group so it would be too slow
    """
    if Animation.nextAnimations:
        field = InternalParameters.field
        shortcutMe = (field is None
                or field.centralView.dragObject
                or PREF.animationSpeed == 99
                or len(Animation.nextAnimations) > 1000)
                # change 1000 to 100 if we do not want to animate shuffling and initial deal
        if not shortcutMe:
            duration = 0
            for animation in Animation.nextAnimations:
                duration = animation.duration()
                if duration:
                    break
            shortcutMe = duration == 0
        if shortcutMe:
            for animation in Animation.nextAnimations:
                tile = animation.targetObject()
                tile.shortcutAnimation(animation)
            Animation.nextAnimations = []
            scene = InternalParameters.field.centralScene
            scene.disableFocusRect = False
            return succeed(None)
        else:
            return ParallelAnimationGroup().deferred
    elif ParallelAnimationGroup.current:
        return ParallelAnimationGroup.current.deferred
    else:
        return succeed(None)
