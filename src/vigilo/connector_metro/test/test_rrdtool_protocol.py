# -*- coding: utf-8 -*-
# vim: set et sw=4 ts=4 ai:
# pylint: disable-msg=R0904,C0111,W0613
# Copyright (C) 2006-2021 CS GROUP - France
# License: GNU GPL v2 <http://www.gnu.org/licenses/gpl-2.0.html>

from __future__ import absolute_import

import tempfile
import os
from shutil import rmtree
import unittest

# ATTENTION: ne pas utiliser twisted.trial, car nose va ignorer les erreurs
# produites par ce module !!!
#from twisted.trial import unittest
from nose.twistedtools import reactor, deferred

from twisted.internet import defer
from twisted.python.failure import Failure
from twisted.internet.error import ProcessDone, ProcessTerminated

from vigilo.connector_metro.rrdtool import RRDToolProcessProtocol
from vigilo.connector_metro.rrdtool import RRDToolError

from vigilo.connector_metro.test.helpers import TransportStub



class RRDToolProcessProtocolTest(unittest.TestCase):
    """
    Test du processus RRDTool
    """


    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="test-connector-metro-")
        self.rrd_base_dir = os.path.join(self.tmpdir, "rrds")
        os.mkdir(self.rrd_base_dir)
        self.transport = TransportStub()
        self.process = RRDToolProcessProtocol("/usr/bin/rrdtool")
        self.process.transport = self.transport

    def tearDown(self):
        rmtree(self.tmpdir)


    def test_start(self):
        """Démarrage"""
        d = self.process.start()
        def cb(r):
            self.assertEqual(r, 42)
        d.addCallback(cb)


    @deferred(timeout=30)
    def test_connectionMade(self):
        """Déclenchement du deferred_start"""
        d = defer.Deferred()
        self.process.deferred_start = d
        def cb(r):
            self.assertEqual(r, 42)
        d.addCallback(cb)
        self.process.connectionMade()
        return d


    @deferred(timeout=30)
    def test_run(self):
        """Exécution d'une commande"""
        command = "dummycommand"
        filename = os.path.join(self.tmpdir, "dummy")
        args = ["dummy", "args", "list"]
        d = self.process.run(command, filename, args)
        self.assertEqual(self.process.working, True)
        self.assertEqual(self.transport.getvalue(), "%s %s %s\n"
                         % (command, filename, " ".join(args)))
        def cb(r):
            self.assertEqual(self.process.working, False)
            self.assertEqual(self.process.deferred, None)
        d.addCallback(cb)
        self.process.outReceived("OK dummy\n")
        return d


    def test_run_args_string(self):
        """Exécution d'une commande avec une string comme arguments"""
        command = "dummycommand"
        filename = os.path.join(self.tmpdir, "dummy")
        args = "dummy args string"
        self.process.run(command, filename, args)
        self.assertEqual(self.transport.getvalue(), "%s %s %s\n"
                         % (command, filename, args))


    @deferred(timeout=30)
    def test_run_output(self):
        """Récupération de la sortie d'une commande"""
        fake_output = ["dummy 1", "dummy 2", "dummy 3", "OK done"]
        d = self.process.run("", "", "")
        def cb(r):
            self.assertEqual(r, "\n".join(fake_output[:-1]))
        d.addCallback(cb)
        for output in fake_output:
            self.process.outReceived(output+"\n")
        return d


    @deferred(timeout=30)
    def test_run_error(self):
        """Récupération de la sortie d'une commande"""
        fake_output = ["dummy 1", "dummy 2", "dummy 3", "ERROR: dummy error"]
        d = self.process.run("", "dummy_filename", "")
        def cb(r):
            self.fail("Il y aurait dû y avoir un errback")
        def eb(f):
            self.assertEqual(f.type, RRDToolError)
            self.assertEqual(f.value.filename, "dummy_filename")
            self.assertEqual(f.value.args[0], "dummy error")
        d.addCallbacks(cb, eb)
        for output in fake_output:
            self.process.outReceived(output+"\n")
        return d


    @deferred(timeout=30)
    def test_run_transport_error(self):
        """Problème dans la communication avec le transport"""
        self.process.transport = object()
        d = self.process.run("", "", "")
        def cb(r):
            self.fail("Il y aurait dû y avoir un errback")
        def eb(f):
            self.assertEqual(f.type, AttributeError)
            self.assertFalse(self.process.working)
        d.addCallbacks(cb, eb)
        return d


    def test_quit(self):
        """Arrêt du processus"""
        self.process.quit()
        self.assertEqual(self.transport.getvalue(), "quit\n")


    def test_respawn_ProcessDone(self):
        """Redémarrage en cas d'arrêt"""
        self.start_calls = 0
        def start_fake():
            self.start_calls += 1
        self.process.start = start_fake
        self.process.processEnded(Failure(ProcessDone("dummy")))
        self.assertEqual(self.start_calls, 1)


    def test_respawn_ProcessExited(self):
        """Redémarrage en cas d'erreur"""
        self.start_calls = 0
        def start_fake():
            self.start_calls += 1
        self.process.start = start_fake
        self.process.processEnded(Failure(ProcessTerminated()))
        self.assertEqual(self.start_calls, 1)


    def test_no_respawn(self):
        """Pas de redémarrage si on a quitté avant"""
        self.start_calls = 0
        def start_fake():
            self.start_calls += 1
        self.process.start = start_fake
        self.process.quit()
        self.process.processEnded(Failure(ProcessDone("dummy")))
        self.assertEqual(self.start_calls, 0)
