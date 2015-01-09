# -*- coding: utf-8 -*-
# vim: set et sw=4 ts=4 ai:
# pylint: disable-msg=R0904,C0111,W0613,W0212
# Copyright (C) 2006-2015 CS-SI
# License: GNU GPL v2 <http://www.gnu.org/licenses/gpl-2.0.html>

from __future__ import absolute_import

import tempfile
import os
import stat
from shutil import rmtree
import unittest

# ATTENTION: ne pas utiliser twisted.trial, car nose va ignorer les erreurs
# produites par ce module !!!
#from twisted.trial import unittest
from nose.twistedtools import reactor, deferred

from mock import patch

from vigilo.connector_metro.bustorrdtool import BusToRRDtool
from vigilo.connector_metro.rrdtool import RRDToolManager
from vigilo.connector_metro.threshold import ThresholdChecker
from vigilo.connector_metro.confdb import MetroConfDB

from vigilo.connector.test.helpers import ClientStub
from .helpers import RRDToolPoolManagerStub



class FunctionalTestCase(unittest.TestCase):
    """
    Vérification que le passage d'un message produit bien un fichier RRD.
    (création du fichier)
    """


    @deferred(timeout=30)
    @patch('signal.signal') # erreurs de threads
    def setUp(self, signal):
        self.tmpdir = tempfile.mkdtemp(prefix="test-connector-metro-")
        client = ClientStub("testhostname", None, None)
        rrd_base_dir = os.path.join(self.tmpdir, "rrds")
        os.mkdir(rrd_base_dir)
        confdb = MetroConfDB(os.path.join(os.path.dirname(__file__),
                                          "connector-metro.db"))
        self.rrdtool_pool = RRDToolPoolManagerStub(rrd_base_dir,
                    "flat", "/usr/bin/rrdtool")
        rrdtool = RRDToolManager(self.rrdtool_pool, confdb)
        threshold_checker = ThresholdChecker(rrdtool, confdb)
        self.btr = BusToRRDtool(confdb, rrdtool, threshold_checker)
        self.btr.setClient(client)
        d = self.btr.startService()
        d.addCallback(lambda _x: confdb.reload())
        return d

    @deferred(timeout=30)
    def tearDown(self):
        d = self.btr.stopService()
        d.addCallback(lambda _x: rmtree(self.tmpdir))
        return d


    @deferred(timeout=30)
    def test_handled_host(self):
        """Functionnal: messages sur des hôtes déclarés."""

        rrdfile = os.path.join(self.tmpdir, "rrds",
                               "server1.example.com", "Load.rrd")
        # on vérifie que le fichier n'existe pas encore
        # (ce qui lève une exception quand on teste le fichier).
        self.assertRaises(OSError, os.stat, rrdfile)
        msg = { "type": "perf",
                "timestamp": "1165939739",
                "host": "server1.example.com",
                "datasource": "Load",
                "value": "12",
                }
        d = self.btr.processMessage(msg)
        # on vérifie que le fichier correspondant a bien été créé
        def check_created(r):
            self.assertTrue(os.path.exists(rrdfile),
                            "Le fichier n'a pas été créé")
            self.assertTrue(stat.S_ISREG(os.stat(rrdfile).st_mode))
        def check_creation_command(r):
            self.assertTrue(len(self.rrdtool_pool.commands) > 0)
            self.assertEqual(self.rrdtool_pool.commands[0],
                    ('create', rrdfile,
                    ['--step', '300', '--start', '1165939729',
                     'RRA:AVERAGE:0.5:1:600', 'RRA:AVERAGE:0.5:6:700',
                     'RRA:AVERAGE:0.5:24:775', 'RRA:AVERAGE:0.5:288:732',
                     'DS:DS:GAUGE:600:U:U']))
        def check_update_command(r):
            self.assertEqual(self.rrdtool_pool.commands[1],
                             ('update', rrdfile, '1165939739:12'))
        d.addCallback(check_created)
        d.addCallback(check_creation_command)
        d.addCallback(check_update_command)
        return d

