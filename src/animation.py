# -*- coding: utf-8 -*-

"""
Copyright (C) 2010-2016 Wolfgang Rohdewald <wolfgang@rohdewald.de>

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

import functools
import types

from twisted.internet.defer import Deferred, succeed

from qt import QPropertyAnimation, QParallelAnimationGroup, \
    QAbstractAnimation, QEasingCurve, QVariant, usingQt5
from qt import pyqtProperty, QGraphicsObject, QGraphicsItem

from common import Internal, Debug, isAlive, isPython3, nativeString
from common import StrMixin
from log import logDebug, id4


class Animation(QPropertyAnimation, StrMixin):

    """a Qt4 animation with helper methods"""

    nextAnimations = []
    clsUid = 0

    def __init__(self, graphicsObject, propName, endValue, parent=None):
        Animation.clsUid += 1
        self.uid = Animation.clsUid
        pName = propName
        if isPython3 and usingQt5:
            # in this case they want bytes
            pName = pName.encode()
        QPropertyAnimation.__init__(self, graphicsObject, pName, parent)
        QPropertyAnimation.setEndValue(self, endValue)
        duration = Internal.Preferences.animationDuration()
        self.setDuration(duration)
        self.setEasingCurve(QEasingCurve.InOutQuad)
        graphicsObject.queuedAnimations.append(self)
        Animation.nextAnimations.append(self)
        self.debug = graphicsObject.name() in Debug.animation or Debug.animation == 'all'
        self.debug |= 'T{}t'.format(id4(graphicsObject)) in Debug.animation
        if self.debug:
            oldAnimation = graphicsObject.activeAnimation.get(propName, None)
            if isAlive(oldAnimation):
                logDebug(
                    u'new Animation(%s) (after %s is done)' %
                    (self, oldAnimation.ident()))
            else:
                logDebug(u'Animation(%s)' % self)

    def setEndValue(self, endValue):
        """wrapper with debugging code"""
        graphicsObject = self.targetObject()
        if not isAlive(graphicsObject):
            # may happen when aborting a game because animations are cancelled first,
            # before the last move from server is executed
            return
        if graphicsObject.name() in Debug.animation or Debug.animation == 'all':
            pName = self.pName()
            logDebug(
                u'%s: change endValue for %s: %s->%s  %s' % (
                    self.ident(), pName,
                    self.formatValue(self.endValue()),
                    self.formatValue(endValue), graphicsObject))
        QPropertyAnimation.setEndValue(self, endValue)

    def ident(self):
        """the identifier to be used in debug messages"""
        pGroup = self.group() if isAlive(self) else 'notAlive'
        if pGroup or not isAlive(self):
            return '%s/A%s' % (pGroup, id4(self))
        else:
            return 'A%s-%s' % (id4(self), self.targetObject().name())

    def pName(self):
        """
        Return self.propertyName() as a python string.

        @return: C{str}
        """
        if isAlive(self):
            return nativeString(self.propertyName())
        else:
            return 'notAlive'

    def unpackValue(self, qvariant):
        """get the wanted value from the QVariant"""
        if not isinstance(qvariant, QVariant):
            return qvariant  # is already autoconverted
        pName = self.pName()
        if pName == 'pos':
            return qvariant.toPointF()
        if pName == 'rotation':
            return qvariant.toInt()[0]
        elif pName == 'scale':
            return qvariant.toFloat()[0]

    def unpackEndValue(self):
        """unpacked end value"""
        if isAlive(self) and isAlive(self.targetObject()):
            return self.unpackValue(self.endValue())

    def formatValue(self, value):
        """string format the wanted value from qvariant"""
        if isinstance(value, QVariant):
            value = self.unpackValue(value)
        pName = self.pName()
        if pName == 'pos':
            return '%.0f/%.0f' % (value.x(), value.y())
        if pName == 'rotation':
            return '%d' % value
        if pName == 'scale':
            return '%.2f' % value

    def __unicode__(self):
        """for debug messages"""
        if isAlive(self) and isAlive(self.targetObject()):
            currentValue = getattr(self.targetObject(), self.pName())
            endValue = self.endValue()
            targetObject = self.targetObject()
        else:
            currentValue = 'notAlive'
            endValue = 'notAlive'
            targetObject = 'notAlive'
        return u'%s %s: %s->%s for %s' % (
            self.ident(), self.pName(),
            self.formatValue(currentValue),
            self.formatValue(endValue),
            targetObject)


class ParallelAnimationGroup(QParallelAnimationGroup, StrMixin):

    """
    current is the currently executed group
    doAfter is a list of Deferred to be called when this group
    is done. If another group is chained to this one, transfer
    doAfter to that other group.
    """

    running = []  # we need a reference to active animation groups
    current = None
    clsUid = 0


    def __init__(self, animations, parent=None):
        QParallelAnimationGroup.__init__(self, parent)
        self.animations = animations
        self.uid = ParallelAnimationGroup.clsUid
        ParallelAnimationGroup.clsUid += 1
        self.deferred = Deferred()
        self.steps = 0
        self.debug = any(x.debug for x in self.animations)
        self.debug |= 'G{}g'.format(id4(self)) in Debug.animation
        self.doAfter = list()
        if ParallelAnimationGroup.current:
            if self.debug or ParallelAnimationGroup.current.debug:
                logDebug(u'Chaining Animation group G%s to G%s' %
                         (id4(self), ParallelAnimationGroup.current))
            self.doAfter = ParallelAnimationGroup.current.doAfter
            ParallelAnimationGroup.current.doAfter = list()
            ParallelAnimationGroup.current.deferred.addCallback(self.start)
        else:
            self.start()
        ParallelAnimationGroup.running.append(self)
        ParallelAnimationGroup.current = self
        self.stateChanged.connect(self.showState)

    @staticmethod
    def cancelAll():
        """cancel all animations"""
        if Debug.quit:
            logDebug('Cancelling all animations')
        for group in ParallelAnimationGroup.running:
            if isAlive(group):
                group.clear()

    def showState(self, newState, oldState):
        """overrides Qt method"""
        if self.debug:
            logDebug('G{}: {} -> {} isAlive:{}'.format(
                self.uid, self.stateName(oldState), self.stateName(newState), isAlive(self)))

    def updateCurrentTime(self, value):
        """count how many steps an animation does."""
        self.steps += 1
        if self.steps % 50 == 0:
            # periodically check if the board still exists.
            # if not (game end), we do not want to go on
            for animation in self.animations:
                graphicsObject = animation.targetObject()
                if hasattr(graphicsObject, 'board') and not isAlive(graphicsObject.board):
                    graphicsObject.clearActiveAnimation(animation)
                    self.removeAnimation(animation)
        QParallelAnimationGroup.updateCurrentTime(self, value)

    def start(self, dummyResults='DIREKT'):
        """start the animation, returning its deferred"""
        assert self.state() != QAbstractAnimation.Running
        for animation in self.animations:
            graphicsObject = animation.targetObject()
            graphicsObject.setActiveAnimation(animation)
            self.addAnimation(animation)
            propName = animation.pName()
            animation.setStartValue(graphicsObject.getValue(propName))
            if propName == 'rotation':
                # change direction if that makes the difference smaller
                endValue = animation.unpackEndValue()
                currValue = graphicsObject.rotation
                if endValue - currValue > 180:
                    animation.setStartValue(currValue + 360)
                if currValue - endValue > 180:
                    animation.setStartValue(currValue - 360)
        for animation in self.animations:
            animation.targetObject().setDrawingOrder()
        self.finished.connect(self.allFinished)
        scene = Internal.scene
        scene.focusRect.hide()
        QParallelAnimationGroup.start(
            self,
            QAbstractAnimation.DeleteWhenStopped)
        if self.debug:
            logDebug(u'Animation group G%s started with speed %d (%s)' % (
                self, Internal.Preferences.animationSpeed,
                ','.join('A%s' % id4(x) for x in self.animations)))
        return succeed(None)

    def allFinished(self):
        """all animations have finished. Cleanup and callback"""
        self.fixAllBoards()
        if self == ParallelAnimationGroup.current:
            ParallelAnimationGroup.current = None
            ParallelAnimationGroup.running = []
        if Debug.animationSpeed and self.duration():
            perSecond = self.steps * 1000.0 / self.duration()
            if perSecond < 50:
                logDebug(u'%d steps for %d animations, %.1f/sec' %
                         (self.steps, len(self.children()), perSecond))
        # if we have a deferred, callback now
        assert self.deferred
        if self.debug:
            logDebug(u'Animation group G%s done' % self)
        if self.deferred:
            self.deferred.callback(None)
        for after in self.doAfter:
            after.callback(None)

    def fixAllBoards(self):
        """set correct drawing order for all moved graphics objects"""
        for animation in self.children():
            graphicsObject = animation.targetObject()
            if graphicsObject:
                graphicsObject.clearActiveAnimation(animation)
        if Internal.scene:
            Internal.scene.focusRect.refresh()
        return

    def stateName(self, state=None):
        """for debug output"""
        if not isAlive(self):
            return 'not alive'
        if state is None:
            state = self.state()
        if state == QAbstractAnimation.Stopped:
            return 'stopped'
        elif state == QAbstractAnimation.Running:
            return 'running'
        else:
            assert False

    def __unicode__(self):
        """for debugging"""
        return u'G{}({}:{})'.format(self.uid, len(self.animations), self.stateName())

class AnimatedMixin(object):
    """for UITile and PlayerWind"""

    def __init__(self):
        super(AnimatedMixin, self).__init__()
        self.activeAnimation = dict()  # key is the property name
        self.queuedAnimations = []

    def _get_pos(self):
        """getter for property pos"""
        return QGraphicsObject.pos(self)

    def _set_pos(self, pos):
        """setter for property pos"""
        QGraphicsObject.setPos(self, pos)

    pos = pyqtProperty('QPointF', fget=_get_pos, fset=_set_pos)

    def _get_scale(self):
        """getter for property scale"""
        return QGraphicsObject.scale(self)

    def _set_scale(self, scale):
        """setter for property scale"""
        QGraphicsObject.setScale(self, scale)

    scale = pyqtProperty(float, fget=_get_scale, fset=_set_scale)

    def _get_rotation(self):
        """getter for property rotation"""
        return QGraphicsObject.rotation(self)

    def _set_rotation(self, rotation):
        """setter for property rotation"""
        QGraphicsObject.setRotation(self, rotation)

    rotation = pyqtProperty(float, fget=_get_rotation, fset=_set_rotation)

    def queuedAnimation(self, propertyName):
        """return the last queued animation for this graphics object and propertyName"""
        for item in reversed(self.queuedAnimations):
            if item.pName() == propertyName:
                return item

    def shortcutAnimation(self, animation):
        """directly set the end value of the animation"""
        if animation.debug:
            logDebug('shortcutAnimation: UTile {}: clear queuedAnimations'.format(self.name()))
        setattr(
            self,
            animation.pName(),
            animation.unpackValue(animation.endValue()))
        self.queuedAnimations = []
        self.setDrawingOrder()

    def getValue(self, pName):
        """gets a property value by not returning a QVariant"""
        return {'pos': self.pos, 'rotation': self.rotation,
                'scale': self.scale}[pName]

    def setActiveAnimation(self, animation):
        """the graphics object knows which of its properties are currently animated"""
        self.queuedAnimations = []
        propName = animation.pName()
        if self.name() in Debug.animation:
            oldAnimation = self.activeAnimation.get(propName, None)
            if not isAlive(oldAnimation):
                oldAnimation = None
            if oldAnimation:
                logDebug('**** setActiveAnimation {} {}: {} OVERRIDES {}'.format(
                    self.name(), propName, animation, oldAnimation))
            else:
                logDebug('setActiveAnimation {} {}: set {}'.format(self.name(), propName, animation))
        self.activeAnimation[propName] = animation
        self.setCacheMode(QGraphicsItem.ItemCoordinateCache)

    def clearActiveAnimation(self, animation):
        """an animation for this graphics object has ended.
        Finalize graphics object in its new position"""
        del self.activeAnimation[animation.pName()]
        if self.name() in Debug.animation:
            logDebug('UITile {}: clear activeAnimation[{}]'.format(self.name(), animation.pName()))
        self.setDrawingOrder()
        if not len(self.activeAnimation):
            self.setCacheMode(QGraphicsItem.DeviceCoordinateCache)
            self.update()

    def setupAnimations(self):
        """move the item to its new place. This puts new Animation
        objects into the queue to be animated by calling animate()"""
        for pName, newValue in self.moveDict().items():
            if self.scene() != Internal.scene:
                # not part of the playing scene, like tiles in tilesetselector
                setattr(self, pName, newValue)
                continue
            animation = self.queuedAnimation(pName)
            if animation:
                curValue = animation.unpackValue(animation.endValue())
                if curValue != newValue:
                    # change a queued animation
                    if self.name() in Debug.animation:
                        logDebug('setEndValue for {}: {}: {}->{}'.format(
                            animation, pName, animation.formatValue(curValue), animation.formatValue(newValue)))
                    animation.setEndValue(newValue)
            else:
                animation = self.activeAnimation.get(pName, None)
                if isAlive(animation):
                    curValue = animation.unpackValue(animation.endValue())
                else:
                    curValue = self.getValue(pName)
                if pName != 'scale' or abs(curValue - newValue) > 0.00001:
                    # ignore rounding differences for scale
                    if curValue != newValue:
                        Animation(self, pName, newValue)


class AnimationSpeed(object):

    """a helper class for moving graphics with a given speed. 99=immediate."""

    def __init__(self, speed=None):
        if speed is None:
            speed = 99
        if Internal.Preferences:
            self.__speed = speed
            self.prevAnimationSpeed = Internal.Preferences.animationSpeed
            if Internal.Preferences.animationSpeed != speed:
                Internal.Preferences.animationSpeed = speed
                if Debug.animationSpeed:
                    logDebug('AnimationSpeed sets speed %d' % speed)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, trback):
        """reset previous animation speed"""
        if Internal.Preferences:
            if self.__speed < 99:
                animate()
            if Internal.Preferences.animationSpeed != self.prevAnimationSpeed:
                if Debug.animationSpeed:
                    logDebug('AnimationSpeed restores speed %d to %d' % (
                        Internal.Preferences.animationSpeed, self.prevAnimationSpeed))
                Internal.Preferences.animationSpeed = self.prevAnimationSpeed


def __afterCurrentAnimationDo(callback, *args, **kwargs):
    """a helper, delaying some action until all active
    animations have finished"""
    current = ParallelAnimationGroup.current
    if current:
        deferred = Deferred()
        deferred.addCallback(callback, *args, **kwargs)
        current.doAfter.append(deferred)
        if current.debug:
            logDebug(u'after current animation group G%s do %s %s' %
                     (current, callback, ','.join(args) if args else ''))
    else:
        callback(None, *args, **kwargs)


def afterQueuedAnimations(doAfter):
    """A decorator"""

    @functools.wraps(doAfter)
    def doAfterQueuedAnimations(*args, **kwargs):
        """do this after all queued animations have finished"""
        animate()
        method = types.MethodType(doAfter, args[0])
        args = args[1:]
        varnames = doAfter.__code__.co_varnames if isPython3 else doAfter.func_code.co_varnames
        assert varnames[1] in ('deferredResult', 'dummyDeferredResult'), \
            '{} passed {} instead of deferredResult'.format(
                doAfter.__qualname__ if isPython3 else doAfter.__name__, varnames[1])
        return __afterCurrentAnimationDo(method, *args, **kwargs)

    return doAfterQueuedAnimations


def animate():
    """now run all prepared animations. Returns a Deferred
        so callers can attach callbacks to be executed when
        animation is over.
        We do not animate objects if
             - we are in a graphics object drag/drop operation
             - the user disabled animation
             - there are too many animations in the group so it would be too slow
             - the object has duration 0
    """
    if Animation.nextAnimations:
        shortcutAll = (Internal.scene is None
                       or Internal.mainWindow.centralView.dragObject
                       or Internal.Preferences.animationSpeed == 99
                       or len(Animation.nextAnimations) > 1000)
                # change 1000 to 100 if we do not want to animate shuffling and
                # initial deal
        for animation in Animation.nextAnimations[:]:
            if shortcutAll or animation.duration() == 0:
                animation.targetObject().shortcutAnimation(animation)
                Animation.nextAnimations.remove(animation)
        if not Animation.nextAnimations:
            if Internal.scene:
                Internal.scene.focusRect.refresh()
            return succeed(None)
        animations = Animation.nextAnimations
        Animation.nextAnimations = []
        return ParallelAnimationGroup(animations).deferred
    elif ParallelAnimationGroup.current:
        return ParallelAnimationGroup.current.deferred
    else:
        return succeed(None)
