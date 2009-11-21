#!/usr/bin/env python
# -*- coding: utf-8 -*-


"""
Copyright (C) 2009 Wolfgang Rohdewald <wolfgang@rohdewald.de>

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

from time import sleep
import sys
from twisted.spread import pb
from twisted.cred import credentials

from comm import *

class Client(pb.Referenceable):
    def __init__(self, field,  reactor,  host,  port, username, password):
        self.field = field
        self.reactor = reactor
        self.host = host
        self.port = port
        self.username = username
        self.password = password
    def remote_print(self, message):
        print 'message from server:', message
    def connect(self):
        factory = pb.PBClientFactory()
        self.connector = self.reactor.connectTCP(self.host, self.port, factory)
        self.credentials = credentials.UsernamePassword(self.username,  self.password)
        def1 = factory.login(self.credentials, client=self)
#        def1.addCallback(self._connected)
#       def1.addErrback(self._loginFailed)
        return def1
    def _loginFailed(self, what):
        print 'login failed:', what
        raise what
    def _connected(self, perspective):
        self.perspective = perspective
        print 'connected:', perspective
    @staticmethod
    def _notConnected(failure):
        print failure.getErrorMessage()
#        print 'STOPPING'
   #     raise failure
    def remote(self, *args):
        return self.perspective.callRemote(*args)
    def runTest(self):
        d = self.connect()
        d.addCallback(lambda _:self.listTables())
        d.addErrback(self._notConnected)
    def disconnect(self):
        print 'client.disconnect'
        d = self.connector.disconnect()
        self.reactor.stop()
    def listTables(self):
        print 'ich bin listTables'
        return self.remote('listTables').addCallback(self.gotTables)
    def gotTables(self, tables):
        print 'gotTables:', tables
        if len(tables) > 0:
            pass
            tableid = tables[0][0]
            self.remote('takeSeat', tableid)
        else:
            print 'client ruft newTable'
            self.remote('newTable').addErrback(self.noAlloc)
    def noAlloc(self, what):
        print 'table alloc failed:', what

    def seatFailed(self, what):
        print 'seatFailed:', what.getErrorMessage()

    def tableStarted(self, answer):
        print 'table started', answer
        self.disconnect()

if __name__ =='__main__':
    from twisted.internet import reactor
    try:
        username = sys.argv[1]
        cl = Client(None, reactor, 'localhost',8082, username, 'xxx')
        cl.runTest()
        reactor.run()
    except Exception as e:
        print 'have no cl:', e, e.getErrorMessage()

