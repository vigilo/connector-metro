# -*- coding: utf-8 -*-
# vim: set et sw=4 ts=4 ai:
# pylint: disable-msg=R0904,C0111,W0613
# Copyright (C) 2006-2020 CS GROUP - France
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

from mock import Mock

from twisted.internet import defer

from vigilo.connector_metro.rrdtool import RRDToolPoolManager


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



