# -*- coding: utf-8 -*-
# vim: set et sw=4 ts=4 ai:
# pylint: disable-msg=R0904,C0111,W0613,W0212
# Copyright (C) 2006-2011 CS-SI
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

from mock import Mock

#from twisted.words.protocols.jabber.jid import JID
from twisted.internet import defer
from twisted.python.failure import Failure
from vigilo.connector.test.helpers import ClientStub

from vigilo.common.conf import settings
settings.load_module(__name__)
from vigilo.connector_metro.bustorrdtool import BusToRRDtool
from vigilo.connector_metro.bustorrdtool import WrongMessageType
from vigilo.connector_metro.bustorrdtool import InvalidMessage
from vigilo.connector_metro.rrdtool import RRDToolManager
from vigilo.connector_metro.rrdtool import NotInConfiguration
from vigilo.connector_metro.confdb import ConfDB

from .helpers import RRDToolPoolManagerStub



class BusToRRDtoolTestCase(unittest.TestCase):
    """
    Vérification que le passage d'un message produit bien un fichier RRD.
    (création du fichier)
    """


    @deferred(timeout=30)
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="test-connector-metro-")
        client = ClientStub("testhostname", None, None)
        rrd_base_dir = os.path.join(self.tmpdir, "rrds")
        os.mkdir(rrd_base_dir)
        confdb = ConfDB(os.path.join(os.path.dirname(__file__),
                                     "connector-metro.db"))
        rrdtool_pool = RRDToolPoolManagerStub(rrd_base_dir, "flat",
                                              "/usr/bin/rrdtool")
        rrdtool = RRDToolManager(rrdtool_pool, confdb)
        self.btr = BusToRRDtool(confdb, rrdtool, threshold_checker)
        self.btr.setClient(client)
        return self.btr.startService()

    @deferred(timeout=30)
    def tearDown(self):
        d = self.btr.stopService()
        d.addCallback(lambda _x: rmtree(self.tmpdir))
        return d


    @deferred(timeout=30)
    def test_handled_host(self):
        """Prise en compte de messages sur des hôtes déclarés."""

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
        d = self.btr.write(msg)
        # on vérifie que le fichier correspondant a bien été créé
        def check_created(r):
            self.assertTrue(stat.S_ISREG(os.stat(rrdfile).st_mode))
        def check_creation_command(r):
            self.assertTrue(len(self.rrdtool.commands) > 0)
            self.assertEqual(self.rrdtool.commands[0], ('create', rrdfile,
                ['--step', '300', '--start', '1165939729',
                 'RRA:AVERAGE:0.5:1:600', 'RRA:AVERAGE:0.5:6:700',
                 'RRA:AVERAGE:0.5:24:775', 'RRA:AVERAGE:0.5:288:732',
                 'DS:DS:GAUGE:600:U:U']))
        def check_update_command(r):
            self.assertEqual(self.rrdtool.commands[1],
                             ('update', rrdfile, '1165939739:12'))
        d.addCallback(check_created)
        d.addCallback(check_creation_command)
        d.addCallback(check_update_command)
        return d


    @deferred(timeout=30)
    def test_unhandled_host(self):
        """Le connecteur doit ignorer les hôtes non-déclarés."""
        rrdfile = os.path.join(self.tmpdir, "rrds",
                               "unknown.example.com", "Load.rrd")
        # on vérifie que le fichier n'existe pas encore
        # (ce qui lève une exception quand on teste le fichier).
        self.assertRaises(OSError, os.stat, rrdfile)
        msg = { "type": "perf",
                "timestamp": "1165939739",
                "host": "unknown.example.com",
                "datasource": "Load",
                "value": "12",
                }
        d = self.btr.write(msg)
        # on vérifie que le fichier correspondant n'a pas été créé
        def cb(_):
            self.assertRaises(OSError, os.stat, rrdfile)
        return d.addCallback(cb)


    @deferred(timeout=30)
    def test_non_existing_host(self):
        """Reception d'un message pour un hôte absent du fichier de conf"""
        msg = {"type": "perf",
               "timestamp": "123456789",
               "host": "dummy_host",
               "datasource": "dummy_datasource",
               "value": "dummy_value",
               }
        d = self.btr.rrdtool._create("/tmp/nonexistant", msg)
        def check_failure(f):
            if not isinstance(f.value, NotInConfiguration):
                self.fail("Raised exeception is not of the right type (got %s)"
                          % type(f.value))
        d.addCallbacks(lambda x: self.fail("No exception raised"),
                       check_failure)
        return d


    @deferred(timeout=30)
    def test_special_chars_in_pds_name(self):
        """Caractères spéciaux dans le nom de la source de données."""
        rrdfile = os.path.join(self.tmpdir, "rrds",
                               "server1.example.com", "A+B%2FC%5CD.E%25F.rrd")
        # on vérifie que le fichier n'existe pas encore
        # (ce qui lève une exception quand on teste le fichier).
        self.assertRaises(OSError, os.stat, rrdfile)
        msg = { "type": "perf",
                "timestamp": "1165939739",
                "host": "server1.example.com",
                "datasource": "A B/C\\D.E%F",
                "value": "42",
                }
        d = self.btr.write(msg)
        # on vérifie que le fichier correspondant a bien été créé
        def cb(_):
            self.assertTrue(stat.S_ISREG(os.stat(rrdfile).st_mode))
        d.addCallback(cb)
        return d


    @deferred(timeout=30)
    def test_special_chars_in_host_name(self):
        """Caractères spéciaux dans le nom de l'hôte (#454)."""
        rrdfile = os.path.join(self.tmpdir, "rrds",
                               "A+b%2Fc.example.com", "Load.rrd")
        # on vérifie que le fichier n'existe pas encore
        # (ce qui lève une exception quand on teste le fichier).
        self.assertRaises(OSError, os.stat, rrdfile)
        msg = { "type": "perf",
                "timestamp": "1165939739",
                "host": "A b/c.example.com",
                "datasource": "Load",
                "value": "42",
                }
        d = self.btr.write(msg)
        # on vérifie que le fichier correspondant a bien été créé
        def cb(_):
            self.assertTrue(stat.S_ISREG(os.stat(rrdfile).st_mode))
        d.addCallback(cb)
        return d


    @deferred(timeout=30)
    def test_wrong_message_type_1(self):
        """Réception d'un autre message que perf (_parse_message)"""
        msg = { "type": "event",
                "timestamp": "1165939739",
                "host": "host",
                "service": "service",
                "status": "CRITICAL",
                "message": "message",
                }
        d = self.btr._parse_message(msg)
        def cb(r):
            self.fail("Il y aurait dû y avoir un errback")
        def eb(f):
            self.assertEqual(f.type, WrongMessageType)
        d.addCallbacks(cb, eb)
        return d


    @deferred(timeout=30)
    def test_wrong_message_type_2(self):
        """Réception d'un autre message que perf (processMessage)"""
        msg = { "type": "event",
                "timestamp": "1165939739",
                "host": "host",
                "service": "service",
                "status": "CRITICAL",
                "message": "message",
                }
        d = self.btr.write(msg)
        def cb(r):
            self.assertEqual(len(self.ntrf.rrdtool.commands), 0)
            self.assertEqual(self.ntrf._messages_forwarded, -1)
        d.addCallback(cb)
        return d


    @deferred(timeout=30)
    def test_invalid_message_1(self):
        """Réception d'un message invalide (_parse_message)"""
        msg = { "type": "perf",
                "timestamp": "1165939739",
                "host": "server1.example.com",
                # pas de clé datasource
                "value": "12",
                }
        d = self.btr._parse_message(msg)
        def cb(r):
            self.fail("Il y aurait dû y avoir un errback")
        def eb(f):
            self.assertEqual(f.type, InvalidMessage)
        d.addCallbacks(cb, eb)
        return d


    @deferred(timeout=30)
    def test_invalid_message_2(self):
        """Réception d'un message invalide (processMessage)"""
        msg = { "type": "perf",
                "timestamp": "1165939739",
                "host": "server1.example.com",
                # pas de clé datasource
                "value": "12",
                }
        d = self.btr.write(msg)
        def cb(r):
            self.assertEqual(len(self.ntrf.rrdtool.commands), 0)
        d.addCallback(cb)
        return d


    @deferred(timeout=30)
    def test_valid_values(self):
        """Réception d'un message avec une valeur valide"""
        msg_tpl = { "type": "perf",
                    "timestamp": "1165939739",
                    "host": "server1.example.com",
                    "datasource": "Load",
                    }
        valid_values = ["1", "1.2", "U"]
        dl = []
        for value in valid_values:
            msg = msg_tpl.copy()
            msg["value"] = value
            d = self.btr._parse_message(msg)
            dl.append(d)
        return defer.DeferredList(dl, fireOnOneErrback=True)


    @deferred(timeout=30)
    def test_invalid_value_1(self):
        """Réception d'un message avec une valeur invalide (#802)"""
        msg = { "type": "perf",
                "timestamp": "1165939739",
                "host": "server1.example.com",
                "datasource": "Load",
                "value": "Invalid value",
                }
        d = self.btr._parse_message(msg)
        def cb(r):
            self.fail("Il y aurait du y avoir un errback")
        def eb(f):
            self.assertEqual(f.type, InvalidMessage)
        d.addCallbacks(cb, eb)
        return d


    @deferred(timeout=30)
    def test_already_created(self):
        """Pas de création si le fichier existe déjà"""
        rrdfile = os.path.join(self.tmpdir, "rrds",
                               "server1.example.com", "Load.rrd")
        os.makedirs(os.path.dirname(rrdfile))
        open(rrdfile, "w").close()
        msg = { "type": "perf",
                "timestamp": "123456789",
                "host": "server1.example.com",
                "datasource": "Load",
                "value": "42",
                }
        d = self.btr.rrdtool.createIfNeeded(msg)
        def cb(r):
            self.assertEqual(len(self.btr.rrdtool.rrdtool.commands), 0)
        d.addCallback(cb)
        return d

    @deferred(timeout=30)
    def test_stats(self):
        """Statistiques"""
        d = self.btr.getStats()
        def cb(r):
            self.assertEqual(r, {
                'queue': 0,
                'forwarded': 0,
                'pds_count': 4,
                'sent': 0,
                'illegal_updates': 0,
            })
        d.addCallback(cb)
        return d

