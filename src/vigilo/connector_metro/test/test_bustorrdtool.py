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
from vigilo.connector_metro.rrdtool import RRDToolManager
from vigilo.connector_metro.exceptions import NotInConfiguration
from vigilo.connector_metro.exceptions import WrongMessageType
from vigilo.connector_metro.exceptions import InvalidMessage
from vigilo.connector_metro.confdb import ConfDB

from .helpers import RRDToolPoolManagerStub



class BusToRRDtoolTestCase(unittest.TestCase):
    """
    Vérification que le passage d'un message produit bien un fichier RRD.
    (création du fichier)
    """


    @deferred(timeout=30)
    def setUp(self):
        #client = ClientStub("testhostname", None, None)
        #confdb = ConfDB(os.path.join(os.path.dirname(__file__),
        #                             "connector-metro.db"))
        self.btr = BusToRRDtool(Mock(), Mock(), Mock())
        #self.btr.setClient(client)
        return self.btr.startService()

    @deferred(timeout=30)
    def tearDown(self):
        return self.btr.stopService()


    @deferred(timeout=30)
    def test_handled_host(self):
        """Prise en compte de messages sur des hôtes déclarés."""
        msg = { "type": "perf",
                "timestamp": "1165939739",
                "host": "server1.example.com",
                "datasource": "Load",
                "value": "12",
                }
        self.btr.confdb.has_host.return_value = True
        self.btr.threshold_checker.hasThreshold.return_value = True
        d = self.btr.write(msg)
        def check(r):
            self.assertTrue(self.btr.rrdtool.createIfNeeded.called)
            self.assertTrue(self.btr.rrdtool.processMessage.called)
            self.assertTrue(self.btr.threshold_checker.hasThreshold.called)
            self.assertTrue(self.btr.threshold_checker.checkMessage.called)
        d.addCallback(check)
        return d


    @deferred(timeout=30)
    def test_unhandled_host(self):
        """Le connecteur doit ignorer les hôtes non-déclarés."""
        msg = { "type": "perf",
                "timestamp": "1165939739",
                "host": "unknown.example.com",
                "datasource": "Load",
                "value": "12",
                }
        self.btr.confdb.has_host.return_value = False
        d = self.btr.write(msg)
        # on vérifie que le fichier correspondant n'a pas été créé
        def check(r):
            self.assertFalse(self.btr.rrdtool.createIfNeeded.called)
            self.assertFalse(self.btr.rrdtool.processMessage.called)
        d.addCallback(check)
        return d


    @deferred(timeout=30)
    def test_non_existing_host(self):
        """Reception d'un message pour un hôte absent du fichier de conf"""
        msg = {"type": "perf",
               "timestamp": "123456789",
               "host": "dummy_host",
               "datasource": "dummy_datasource",
               "value": "dummy_value",
               }
        self.btr.confdb.has_host.return_value = False
        d = self.btr._parse_message(msg)
        def check_failure(f):
            if not isinstance(f.value, NotInConfiguration):
                self.fail("Raised exeception is not of the right type (got %s)"
                          % type(f.value))
        d.addCallbacks(lambda x: self.fail("No exception raised"),
                       check_failure)
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

