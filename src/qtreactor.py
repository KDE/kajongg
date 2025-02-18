# -*- coding: utf-8 -*-
# pylint: skip-file

"""
Copyright (c) 2001-2011 Twisted Matrix Laboratories <twisted-python@twistedmatrix.com>
Copyright (C) 2008-2016 Wolfgang Rohdewald <wolfgang@rohdewald.de>

SPDX-License-Identifier: GPL-2.0-only

"""

"""
This module provides support for Twisted to be driven by the Qt mainloop.

In order to use this support, simply do the following::
    |  app = QApplication(sys.argv) # your code to init Qt
    |  import qtreactor
    |  qtreactor.install()

alternatively:

    |  from twisted.application import reactors
    |  reactors.installReactor('qt')

Then use twisted.internet APIs as usual.  The other methods here are not
intended to be called directly.

If you don't instantiate a QApplication or QCoreApplication prior to
installing the reactor, a QCoreApplication will be constructed
by the reactor.  QCoreApplication does not require a GUI so trial testing
can occur normally.

Twisted can be initialized after QApplication.exec() with a call to
reactor.runReturn().  calling reactor.stop() will unhook twisted but
leave your Qt application running

API Stability: stable

Maintainer: U{Glenn H Tarbox, PhD<mailto:glenn@tarbox.org>}

Previous maintainer: U{Itamar Shtull-Trauring<mailto:twisted@itamarst.org>}
Original port to QT4: U{Gabe Rudy<mailto:rudy@goldenhelix.com>}
Subsequent port by therve
"""

import sys
from _collections_abc import dict_keys
from typing import List, Any, Optional, Callable, Dict, TYPE_CHECKING, Type, Tuple, Union

from zope.interface import implementer
from twisted.internet.interfaces import IReactorFDSet
from twisted.python import log, runtime
from twisted.internet import base, posixbase, unix

from qt import QSocketNotifier, QObject, QTimer, QCoreApplication
from qt import QEvent, QEventLoop


#if TYPE_CHECKING:

class TwistedSocketNotifier(QObject):

    """
    Connection between an fd event and reader/writer callbacks.
    """

    def __init__(self, parent:Optional[QObject], reactor:'QtReactor', watcher:unix.Client, socketType:QSocketNotifier.Type) ->None:
        super().__init__(parent)
        self.reactor = reactor
        self.watcher:Optional[unix.Client] = watcher
        fd = watcher.fileno()
        self.fn:Optional[Callable[...,None]]
        self.notifier = QSocketNotifier(fd, socketType, parent)
        self.notifier.setEnabled(True)
        if socketType == QSocketNotifier.Type.Read:
            self.fn = self.read
        else:
            self.fn = self.write
        self.notifier.activated.connect(self.fn)

    def shutdown(self) ->None:
        self.notifier.setEnabled(False)
        assert self.fn
        self.notifier.activated.disconnect(self.fn)
        self.fn = None
        self.watcher = None
        self.notifier.deleteLater()
        self.deleteLater()

    def read(self, fd:int) ->None:
        if not self.watcher:
            return
        w = self.watcher
        # doRead can cause self.shutdown to be called so keep a reference to
        # self.watcher

        def _read() ->None:
            # Don't call me again, until the data has been read
            self.notifier.setEnabled(False)
            why = None
            try:
                why = w.doRead()
                inRead = True
            except:
                inRead = False
                log.err()
                why = sys.exc_info()[1]
            if why:
                self.reactor._disconnectSelectable(w, why, inRead)
            elif self.watcher:
                self.notifier.setEnabled(
                    True)  # Re enable notification following successful read
            self.reactor._iterate(fromqt=True)
        log.callWithLogger(w, _read)

    def write(self, fd:int) ->None:
        if not self.watcher:
            return
        w = self.watcher

        def _write() ->None:
            why = None
            self.notifier.setEnabled(False)

            try:
                why = w.doWrite()
            except:
                log.err()
                why = sys.exc_info()[1]
            if why:
                self.reactor._disconnectSelectable(w, why, False)
            elif self.watcher:
                self.notifier.setEnabled(True)
            self.reactor._iterate(fromqt=True)
        log.callWithLogger(w, _write)


@implementer(IReactorFDSet)
class QtReactor(posixbase.PosixReactorBase):

    def __init__(self) ->None:
#        self._reads:Dict[posixbase._UnixWaker, TwistedSocketNotifier] = {}
        self._reads:Dict[unix.Client, TwistedSocketNotifier] = {}
        self._writes:Dict[Any, Any] = {}
        self._notifiers:Dict[Any, Any] = {}
        self._timer = QTimer()
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self.iterate)  # type:ignore[has-type]

        self.qApp:QCoreApplication
        if QCoreApplication.instance() is None:
            # Application Object has not been started yet
            self.qApp = QCoreApplication([])
            self._ownApp = True
        else:
            _ = QCoreApplication.instance()
            assert _
            self.qApp = _
            self._ownApp = False
        self._blockApp:Union[QCoreApplication, QEventLoop, None] = None
        posixbase.PosixReactorBase.__init__(self)

    def _add(self, xer:unix.Client, primary:Dict[unix.Client, TwistedSocketNotifier], typus:QSocketNotifier.Type) ->None:
        """
        Private method for adding a descriptor from the event loop.

        It takes care of adding it if  new or modifying it if already added
        for another state (read -> read/write for example).
        """
        if xer not in primary:
            primary[xer] = TwistedSocketNotifier(None, self, xer, typus)

    def addReader(self, reader:unix.Client) ->None:
        """
        Add a FileDescriptor for notification of data available to read.
        """
        self._add(reader, self._reads, QSocketNotifier.Type.Read)

    def addWriter(self, writer:unix.Client) ->None:
        """
        Add a FileDescriptor for notification of data available to write.
        """
        self._add(writer, self._writes, QSocketNotifier.Type.Write)

    def _remove(self, xer:unix.Client, primary:Dict[unix.Client, TwistedSocketNotifier]) ->None:
        """
        Private method for removing a descriptor from the event loop.

        It does the inverse job of _add, and also add a check in case of the fd
        has gone away.
        """
        if xer in primary:
            notifier = primary.pop(xer)
            notifier.shutdown()

    def removeReader(self, reader:unix.Client) ->None:
        """
        Remove a Selectable for notification of data available to read.
        """
        self._remove(reader, self._reads)

    def removeWriter(self, writer:unix.Client) ->None:
        """
        Remove a Selectable for notification of data available to write.
        """
        self._remove(writer, self._writes)

    def removeAll(self) ->List[Any]:
        """
        Remove all selectables, and return a list of them.
        """
        rv = self._removeAll(self._reads, self._writes)
        return rv

    def getReaders(self) ->Any:#dict_keys[Any, TwistedSocketNotifier]:
        result =self._reads.keys()
        print('result:',type(result))
        return result 

    def getWriters(self) ->Any:#dict_keys[Any, TwistedSocketNotifier]:
        return self._writes.keys()

    def callLater(self, delay:float, *args:Any, **kargs:Any) ->base.DelayedCall:
        rval = super(QtReactor, self).callLater(delay, *args, **kargs)
        self.reactorInvocation()
        return rval

    def reactorInvocation(self) ->None:
        self._timer.stop()
        self._timer.setInterval(0)
        self._timer.start()

    def _iterate(self, delay:Optional[int]=None, fromqt:bool=False) ->None:
        """See twisted.internet.interfaces.IReactorCore.iterate.
        """
        self.runUntilCurrent()
        self.doIteration(delay, fromqt)

    iterate = _iterate  # type:ignore[assignment]

    def doIteration(self, delay:Optional[float]=None, fromqt:bool=False) ->None:
        'This method is called by a Qt timer or by network activity on a file descriptor'

        if not self.running and self._blockApp:
            self._blockApp.quit()
        self._timer.stop()
        delay = max(int(delay or 0), 1)
        if not fromqt:
            self.qApp.processEvents(QEventLoop.ProcessEventsFlag.AllEvents, delay * 1000)
        timeout = self.timeout() or 0.1
        self._timer.setInterval(int(timeout * 1000))
        self._timer.start()

    def runReturn(self, installSignalHandlers:bool=True) ->None:
        self.startRunning(installSignalHandlers=installSignalHandlers)
        self.reactorInvocation()

    def run(self, installSignalHandlers:bool=True) ->None:
        if self._ownApp:
            self._blockApp = self.qApp
        else:
            self._blockApp = QEventLoop()
        self.runReturn()
        assert self._blockApp
        self._blockApp.exec()


class QtEventReactor(QtReactor):

    def __init__(self, *args:Any, **kwargs:Any) ->None:
        self._events:Dict[QEvent, Tuple[int, str]] = {}
        super(QtEventReactor, self).__init__()

    def addEvent(self, event:QEvent, fd:int, action:str) ->None:
        """
        Add a new win32 event to the event loop.
        """
        self._events[event] = (fd, action)

    def removeEvent(self, event:QEvent) ->None:
        """
        Remove an event.
        """
        if event in self._events:
            del self._events[event]

    def _runAction(self, action:str, fd:int) ->None:
        try:
            closed = getattr(fd, action)()
        except:
            closed = sys.exc_info()[1]
            log.deferr()

        if closed:
            self._disconnectSelectable(fd, closed, action == 'doRead')

    def timeout(self) ->Optional[float]:
        t = super(QtEventReactor, self).timeout()
        if t is not None:
            return min(t, 0.01)
        return None

    def iterate(self, delay:Optional[int]=None) ->None:  # type:ignore
        """See twisted.internet.interfaces.IReactorCore.iterate
        """
        self.runUntilCurrent()
        self.doIteration(delay)


def posixinstall() ->None:
    """
    Install the Qt reactor.
    """
    p = QtReactor()
    from twisted.internet.main import installReactor
    installReactor(p)


def win32install() ->None:
    """
    Install the Qt reactor.
    """
    p = QtEventReactor()
    from twisted.internet.main import installReactor
    installReactor(p)


if sys.platform == 'win32':
    install = win32install
else:
    install = posixinstall


__all__ = ["install"]
