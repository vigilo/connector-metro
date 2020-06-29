# -*- coding: utf-8 -*-
# vim: set et sw=4 ts=4 ai:
# Copyright (C) 2006-2020 CS GROUP – France
# License: GNU GPL v2 <http://www.gnu.org/licenses/gpl-2.0.html>

from __future__ import absolute_import, print_function

from StringIO import StringIO

from twisted.internet import defer

from vigilo.connector_metro.rrdtool import RRDToolPoolManager


class RRDToolPoolManagerStub(RRDToolPoolManager):
    """
    On a pas le droit de lancer des sous-processus dans un test unitaire, sous
    peine de les voir se transformer en zombies. Le virus vient de
    l'intégration de twisted avec nose, parce qu'il lance le réacteur dans un
    thread, et qu'il n'installe pas les gestionnaires de signaux (SIGCHLD)
    @see: U{http://twistedmatrix.com/pipermail/twisted-python/2007-February/014782.html}
    """
    def __init__(self, *args, **kwargs):
        self.commands = []
        super(RRDToolPoolManagerStub, self).__init__(*args, **kwargs)

    def createPools(self, check_thresholds, rrdcached, pool_size):
        super(RRDToolPoolManagerStub, self).createPools(check_thresholds,
                    rrdcached, pool_size)
        self.pool.processProtocolFactory = \
                lambda *a: RRDToolProcessProtocolStub(self.commands)


class RRDToolProcessProtocolStub(object):
    def __init__(self, commands):
        self.working = False
        self.commands = commands
    def start(self):
        return defer.succeed(None)
    def quit(self):
        return defer.succeed(None)
    def run(self, command, filename, args):
        self.commands.append((command, filename, args))
        print("Running: %s on %s with %r" % (command, filename, args))
        open(filename, "w").close() # touch filename
        return defer.succeed("")


class TransportStub(StringIO):
    pid = 42
    def loseConnection(self):
        pass

