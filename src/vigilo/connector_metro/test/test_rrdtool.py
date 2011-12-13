# -*- coding: utf-8 -*-
# vim: set et sw=4 ts=4 ai:
# pylint: disable-msg=R0904,C0111,W0613
# Copyright (C) 2006-2011 CS-SI
# License: GNU GPL v2 <http://www.gnu.org/licenses/gpl-2.0.html>

"""
Test des classes RRDToolManager et RRDToolProcessProtocol
"""

# Teste la creation d'un fichier RRD
from __future__ import absolute_import

import tempfile
import os
from shutil import rmtree
import unittest

# ATTENTION: ne pas utiliser twisted.trial, car nose va ignorer les erreurs
# produites par ce module !!!
#from twisted.trial import unittest
from nose.twistedtools import reactor, deferred

from mock import Mock

from twisted.internet import defer
from twisted.python.failure import Failure
from twisted.internet.error import ProcessDone, ProcessTerminated

from vigilo.connector_metro.rrdtool import RRDToolManager
from vigilo.connector_metro.rrdtool import RRDToolPoolManager
from vigilo.connector_metro.rrdtool import RRDToolProcessProtocol
from vigilo.connector_metro.rrdtool import RRDToolError
from vigilo.connector_metro.confdb import ConfDB
from vigilo.connector_metro.exceptions import NotInConfiguration

from vigilo.connector_metro.test.helpers import TransportStub



class RRDToolManagerTestCase(unittest.TestCase):


    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="test-connector-metro-")
        self.rrd_base_dir = os.path.join(self.tmpdir, "rrds")
        os.mkdir(self.rrd_base_dir)

        confdb = ConfDB(os.path.join(os.path.dirname(__file__),
                                     "connector-metro.db"))
        confdb.start_db()
        rrdtool = Mock()
        rrdtool.run.side_effect = lambda *a, **kw: defer.succeed(None)
        rrdtool.rrd_base_dir = self.rrd_base_dir
        rrdtool.rrd_path_mode = "flat"
        self.mgr = RRDToolManager(rrdtool, confdb)
        self.mgr._fixperms = Mock()

    def tearDown(self):
        rmtree(self.tmpdir)


    @deferred(timeout=30)
    def test_create_needed(self):
        msg = { "type": "perf",
                "timestamp": "1165939739",
                "host": "server1.example.com",
                "datasource": "Load",
                "value": "12",
                }
        d = self.mgr.createIfNeeded(msg)
        def check(_ignored):
            print self.mgr.rrdtool.run.call_args_list
            self.assertEqual(len(self.mgr.rrdtool.run.call_args_list), 1)
            self.assertEqual(self.mgr.rrdtool.run.call_args_list[0][0],
                    ('create', self.rrd_base_dir+"/server1.example.com/Load.rrd",
                    ['--step', '300', '--start', '1165939729',
                     'RRA:AVERAGE:0.5:1:600', 'RRA:AVERAGE:0.5:6:700',
                     'RRA:AVERAGE:0.5:24:775', 'RRA:AVERAGE:0.5:288:732',
                     'DS:DS:GAUGE:600:U:U']))
        d.addCallback(check)
        return d


    @deferred(timeout=30)
    def test_already_created(self):
        """Pas de création si le fichier existe déjà"""
        rrdfile = os.path.join(self.rrd_base_dir,
                               "server1.example.com", "Load.rrd")
        os.makedirs(os.path.dirname(rrdfile))
        open(rrdfile, "w").close()
        msg = { "type": "perf",
                "timestamp": "123456789",
                "host": "server1.example.com",
                "datasource": "Load",
                "value": "42",
                }
        d = self.mgr.createIfNeeded(msg)
        def check(r):
            self.assertFalse(self.mgr.rrdtool.run.called)
        d.addCallback(check)
        return d


    @deferred(timeout=30)
    def test_update(self):
        msg = { "type": "perf",
                "timestamp": "1165939739",
                "host": "server1.example.com",
                "datasource": "Load",
                "value": "12",
                "has_thresholds": False,
                }
        #self.mgr.getFilename = Mock(return_value=self.rrd_base_dir+"")
        #self.mgr.getOldFilename = Mock(return_value=self.rrd_base_dir+"")
        d = self.mgr.processMessage(msg)
        def check(_ignored):
            print self.mgr.rrdtool.run.call_args_list
            self.assertEqual(len(self.mgr.rrdtool.run.call_args_list), 1)
            self.assertEqual(self.mgr.rrdtool.run.call_args_list[0][0],
                     ('update', self.rrd_base_dir+"/server1.example.com/Load.rrd",
                      '1165939739:12'))
        d.addCallback(check)
        return d


    def test_special_chars_in_pds_name(self):
        msg = { "type": "perf",
                "timestamp": "1165939739",
                "host": "server1.example.com",
                "datasource": "A B/C\\D.E%F",
                "value": "42",
                }
        print self.mgr.getFilename(msg)
        expected = (self.rrd_base_dir+"/server1.example.com/"
                    "A+B%2FC%5CD.E%25F.rrd")
        self.assertEqual(expected, self.mgr.getFilename(msg))


    def test_special_chars_in_host_name(self):
        """Caractères spéciaux dans le nom de l'hôte (#454)."""
        msg = { "type": "perf",
                "timestamp": "1165939739",
                "host": "A b/c.example.com",
                "datasource": "Load",
                "value": "42",
                }
        print self.mgr.getFilename(msg)
        expected = self.rrd_base_dir+"/A+b%2Fc.example.com/Load.rrd"
        self.assertEqual(expected, self.mgr.getFilename(msg))


    @deferred(timeout=30)
    def test_non_existing_host(self):
        """Reception d'un message pour un hôte absent du fichier de conf"""
        msg = {"type": "perf",
               "timestamp": "123456789",
               "host": "dummy_host",
               "datasource": "dummy_datasource",
               "value": "dummy_value",
               }
        d = self.mgr._create(self.rrd_base_dir+"/nonexistant", msg)
        def check_failure(f):
            if not isinstance(f.value, NotInConfiguration):
                self.fail("Raised exeception is not of the right type (got %s)"
                          % type(f.value))
        d.addCallbacks(lambda x: self.fail("No exception raised"),
                       check_failure)
        return d



class RRDToolPoolManagerTestCase(unittest.TestCase):
    """
    Test du gestionnaire de pool de processus RRDTool
    """


    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="test-connector-metro-")
        self.rrd_base_dir = os.path.join(self.tmpdir, "rrds")
        os.mkdir(self.rrd_base_dir)

    def tearDown(self):
        rmtree(self.tmpdir)


    def test_no_binary_1(self):
        """L'exécutable rrdtool n'existe pas (checkBinary)"""
        rrd_bin = os.path.join(self.tmpdir, "dummy")
        mgr = RRDToolPoolManager(self.rrd_base_dir, "flat", rrd_bin)
        self.assertRaises(OSError, mgr.checkBinary)


    @deferred(timeout=30)
    def test_no_binary_2(self):
        """L'exécutable rrdtool n'existe pas (start)"""
        rrd_bin = os.path.join(self.tmpdir, "dummy")
        mgr = RRDToolPoolManager(self.rrd_base_dir, "flat", rrd_bin)
        d = mgr.start()
        def cb(r):
            self.fail("Il y aurait dû y avoir un errback")
        def eb(f):
            self.assertEqual(f.type, OSError)
        d.addCallbacks(cb, eb)
        return d


    def test_not_executable_1(self):
        """L'exécutable rrdtool n'est pas exécutable (checkBinary)"""
        rrd_bin = os.path.join(self.tmpdir, "dummy")
        mgr = RRDToolPoolManager(self.rrd_base_dir, "flat", rrd_bin)
        open(rrd_bin, "w").close()
        self.assertRaises(OSError, mgr.checkBinary)


    @deferred(timeout=30)
    def test_not_executable_2(self):
        """L'exécutable rrdtool n'est pas exécutable (start)"""
        rrd_bin = os.path.join(self.tmpdir, "dummy")
        mgr = RRDToolPoolManager(self.rrd_base_dir, "flat", rrd_bin)
        open(rrd_bin, "w").close()
        d = mgr.start()
        def cb(r):
            self.fail("Il y aurait dû y avoir un errback")
        def eb(f):
            self.assertEqual(f.type, OSError)
        d.addCallbacks(cb, eb)
        return d


    @deferred(timeout=30)
    def test_with_rrdcached(self):
        """
        Si RRDcached est activé, la bonne variable d'env doit être propagée
        """
        mgr = RRDToolPoolManager(self.rrd_base_dir, "flat", "/usr/bin/rrdtool",
                    rrdcached=self.tmpdir)
        # Ne rien forker
        mgr.pool.build()
        mgr.pool_direct.build()
        for p in mgr.pool.pool + mgr.pool_direct.pool:
            p.start = lambda: defer.succeed(None)
        d = mgr.start()
        def check(r):
            self.assertTrue(len(mgr.pool) > 0)
            for p in mgr.pool:
                self.assertTrue("RRDCACHED_ADDRESS" in p.env)
                self.assertEqual(p.env["RRDCACHED_ADDRESS"], self.tmpdir)
        d.addCallback(check)
        return d


    @deferred(timeout=30)
    def test_with_check_thresholds(self):
        """
        Si la vérification de seuils est activée, il faut un second pool
        """
        mgr = RRDToolPoolManager(self.rrd_base_dir, "flat", "/usr/bin/rrdtool",
                    rrdcached=self.tmpdir)
        # Ne rien forker
        mgr.pool.build()
        mgr.pool_direct.build()
        for p in mgr.pool.pool + mgr.pool_direct.pool:
            p.start = lambda: defer.succeed(None)
        d = mgr.start()
        def check(r):
            self.assertTrue(mgr.pool_direct is not None)
            self.assertTrue(len(mgr.pool_direct) > 0)
            for p in mgr.pool_direct:
                self.assertTrue("RRDCACHED_ADDRESS" not in p.env)
        d.addCallback(check)
        return d


    def test_without_check_thresholds(self):
        """
        Si la vérification de seuils est désactivée, pas besoin de second pool
        """
        mgr = RRDToolPoolManager(self.rrd_base_dir, "flat", "/usr/bin/rrdtool",
                    rrdcached=self.tmpdir, check_thresholds=False)
        self.assertTrue(mgr.pool_direct is None)


    @deferred(timeout=30)
    def test_with_or_without_rrdcached(self):
        """L'argument no_rrdcached doit envoyer sur le bon pool"""
        mgr = RRDToolPoolManager(self.rrd_base_dir, "flat", "/usr/bin/rrdtool",
                    rrdcached=self.tmpdir)
        mgr.pool.run = Mock(name="with")
        mgr.pool_direct.run = Mock(name="without")
        # Ne rien forker
        mgr.pool.build()
        mgr.pool_direct.build()
        for p in mgr.pool.pool + mgr.pool_direct.pool:
            p.start = lambda: defer.succeed(None)
        d = mgr.start()
        def run_with_rrdcached(r):
            return mgr.run("with", "with", ["with"])
        def run_without_rrdcached(r):
            return mgr.run("without", "without", ["without"], no_rrdcached=True)
        def check(r):
            mgr.pool.run.assert_called_with("with", "with", ["with"])
            mgr.pool_direct.run.assert_called_with("without", "without", ["without"])
        d.addCallback(run_with_rrdcached)
        d.addCallback(run_without_rrdcached)
        d.addCallback(check)
        return d



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


